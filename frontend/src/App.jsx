import React from 'react'
import { useState, useEffect } from 'react'
import './styles.css'
import WorkloadForm from './components/WorkloadForm.jsx'
import Results from './components/Results.jsx'
import Simulator from './components/Simulator.jsx'
import { plan, health } from './api.js'

export default function App() {
  const [busy, setBusy] = useState(false)
  const [data, setData] = useState(null)
  const [ok, setOk] = useState(null)
  const [showSimulator, setShowSimulator] = useState(false)
  const [baselineWorkload, setBaselineWorkload] = useState(null)
  const [sharedWorkload, setSharedWorkload] = useState(null)

  // Load shared workload from URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const workloadParam = params.get('workload')
    if (workloadParam) {
      try {
        const decoded = JSON.parse(atob(workloadParam))
        setSharedWorkload(decoded)
      } catch (e) {
        console.error('Failed to decode shared workload:', e)
      }
    }
  }, [])

  async function check() {
    const live = await health().catch(()=>false)
    setOk(live)
  }

  async function onSubmit(workload) {
    setBusy(true)
    setData(null)
    setBaselineWorkload(workload)
    setShowSimulator(false)
    try {
      const res = await plan(workload)
      setData(res)
    } catch (e) {
      alert(e.message)
    } finally {
      setBusy(false)
    }
  }

  function openSimulator() {
    if (!baselineWorkload) {
      alert('Please run a plan first to use the simulator')
      return
    }
    setShowSimulator(true)
  }

  return (
    <div className="container">
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8}}>
        <div className="small">Health: {ok===null ? <em>unknown</em> : ok ? <span className="ok">OK</span> : <span className="warn">DOWN</span>}</div>
        <div style={{display:'flex', gap:8}}>
          {data && !showSimulator && (
            <button className="btn" onClick={openSimulator} style={{background:'#059669'}}>
              What-If Simulator
            </button>
          )}
          <button className="btn" onClick={check}>Check API</button>
        </div>
      </div>

      {!showSimulator && <WorkloadForm busy={busy} onSubmit={onSubmit} sharedWorkload={sharedWorkload}/>}
      {!showSimulator && <Results data={data} workload={baselineWorkload}/>}
      {showSimulator && <Simulator baselineWorkload={baselineWorkload} onClose={()=>setShowSimulator(false)}/>}
    </div>
  )
}
