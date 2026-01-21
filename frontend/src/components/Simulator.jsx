import React from 'react'
import { useState } from 'react'
import { simulate } from '../api.js'

export default function Simulator({ baselineWorkload, onClose }) {
  const [busy, setBusy] = useState(false)
  const [results, setResults] = useState(null)

  // Simulation parameters with sliders
  const [trafficMultiplier, setTrafficMultiplier] = useState(1)
  const [memoryMultiplier, setMemoryMultiplier] = useState(1)
  const [storageMultiplier, setStorageMultiplier] = useState(1)
  const [regionOverride, setRegionOverride] = useState('')
  const [vendorOverride, setVendorOverride] = useState('')

  async function runSimulation() {
    setBusy(true)
    setResults(null)

    const scenarios = []

    // Scenario 1: Traffic scaling
    if (trafficMultiplier !== 1) {
      scenarios.push({
        label: `${trafficMultiplier}x Traffic`,
        traffic_rps: Math.round(baselineWorkload.traffic_rps * trafficMultiplier)
      })
    }

    // Scenario 2: Memory scaling
    if (memoryMultiplier !== 1) {
      scenarios.push({
        label: `${memoryMultiplier}x Memory`,
        mem_gb: baselineWorkload.mem_gb * memoryMultiplier
      })
    }

    // Scenario 3: Storage scaling
    if (storageMultiplier !== 1) {
      scenarios.push({
        label: `${storageMultiplier}x Storage`,
        storage_gb_hot: baselineWorkload.storage_gb_hot * storageMultiplier
      })
    }

    // Scenario 4: Region change
    if (regionOverride && regionOverride !== baselineWorkload.region) {
      scenarios.push({
        label: `Region: ${regionOverride}`,
        region: regionOverride
      })
    }

    // Scenario 5: Vendor preference change
    if (vendorOverride && vendorOverride !== baselineWorkload.vendor_preference) {
      scenarios.push({
        label: `Vendor: ${vendorOverride}`,
        vendor_preference: vendorOverride
      })
    }

    // Scenario 6: Combined scenario (traffic + memory)
    if (trafficMultiplier !== 1 || memoryMultiplier !== 1) {
      scenarios.push({
        label: `${trafficMultiplier}x Traffic + ${memoryMultiplier}x Memory`,
        traffic_rps: Math.round(baselineWorkload.traffic_rps * trafficMultiplier),
        mem_gb: baselineWorkload.mem_gb * memoryMultiplier
      })
    }

    if (scenarios.length === 0) {
      alert('Please adjust at least one parameter to create a scenario')
      setBusy(false)
      return
    }

    try {
      const data = await simulate(baselineWorkload, scenarios)
      setResults(data)
    } catch (e) {
      alert(e.message)
    } finally {
      setBusy(false)
    }
  }

  function renderDelta(value, suffix = '') {
    if (value === null || value === undefined) return <span className="small" style={{color:'#64748b'}}>N/A</span>
    const color = value > 0 ? '#ef4444' : value < 0 ? '#22c55e' : '#64748b'
    const sign = value > 0 ? '+' : ''
    return <span style={{color, fontWeight:600}}>{sign}{value}{suffix}</span>
  }

  function renderRankChange(delta) {
    if (delta === null || delta === undefined) return <span className="badge">New</span>
    if (delta > 0) return <span style={{color:'#22c55e'}}>↑ {delta}</span>
    if (delta < 0) return <span style={{color:'#ef4444'}}>↓ {Math.abs(delta)}</span>
    return <span style={{color:'#64748b'}}>–</span>
  }

  return (
    <div className="card" style={{marginBottom:16}}>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
        <h2 style={{margin:0}}>What-If Simulator</h2>
        <button className="btn" onClick={onClose} style={{background:'#2b355d', fontSize:12, padding:'6px 12px'}}>
          Close
        </button>
      </div>
      <div className="small" style={{marginBottom:16, color:'#a7b1c6'}}>
        Adjust parameters below to see how changes affect your recommendations. Compare costs, rankings, and feasibility.
      </div>

      <h3 style={{fontSize:14, marginTop:16, marginBottom:8}}>Simulation Parameters</h3>

      <div className="grid">
        <div className="row">
          <label>Traffic Multiplier: {trafficMultiplier}x ({Math.round(baselineWorkload.traffic_rps * trafficMultiplier)} RPS)</label>
          <input
            type="range"
            min="0.5"
            max="5"
            step="0.5"
            value={trafficMultiplier}
            onChange={e=>setTrafficMultiplier(parseFloat(e.target.value))}
            style={{width:'100%'}}
          />
        </div>

        <div className="row">
          <label>Memory Multiplier: {memoryMultiplier}x ({(baselineWorkload.mem_gb * memoryMultiplier).toFixed(2)} GB)</label>
          <input
            type="range"
            min="0.5"
            max="5"
            step="0.5"
            value={memoryMultiplier}
            onChange={e=>setMemoryMultiplier(parseFloat(e.target.value))}
            style={{width:'100%'}}
          />
        </div>

        <div className="row">
          <label>Storage Multiplier: {storageMultiplier}x ({(baselineWorkload.storage_gb_hot * storageMultiplier).toFixed(0)} GB)</label>
          <input
            type="range"
            min="0.5"
            max="5"
            step="0.5"
            value={storageMultiplier}
            onChange={e=>setStorageMultiplier(parseFloat(e.target.value))}
            style={{width:'100%'}}
          />
        </div>

        <div className="row">
          <label>Region Override</label>
          <select value={regionOverride} onChange={e=>setRegionOverride(e.target.value)}>
            <option value="">Keep baseline ({baselineWorkload.region})</option>
            <option value="us-east-1">us-east-1</option>
            <option value="us-west-2">us-west-2</option>
            <option value="eu-west-1">eu-west-1</option>
            <option value="ap-southeast-1">ap-southeast-1</option>
          </select>
        </div>

        <div className="row">
          <label>Vendor Preference Override</label>
          <select value={vendorOverride} onChange={e=>setVendorOverride(e.target.value)}>
            <option value="">Keep baseline ({baselineWorkload.vendor_preference})</option>
            <option value="aws">AWS</option>
            <option value="azure">Azure</option>
            <option value="gcp">GCP</option>
          </select>
        </div>
      </div>

      <button
        className="btn"
        disabled={busy}
        onClick={runSimulation}
        style={{marginTop:16}}
      >
        {busy ? 'Running Simulation...' : 'Run Simulation'}
      </button>

      {results && (
        <>
          <h3 style={{fontSize:14, marginTop:24, marginBottom:8}}>Baseline</h3>
          <div className="kv" style={{marginBottom:16}}>
            <div className="item">Winner: <b>{results.baseline_result.winner.vendor}</b></div>
            <div className="item">Compute: <b>{results.baseline_result.winner.compute_service}</b></div>
            <div className="item">Cost: <b>${results.baseline_result.winner.monthly_cost.toFixed(2)}/mo</b></div>
            <div className="item">p95: <b>{results.baseline_result.winner.p95_ms.toFixed(1)}ms</b></div>
          </div>

          {results.scenarios.map((scenario, idx) => (
            <div key={idx} style={{marginTop:24}}>
              <h3 style={{fontSize:14, marginBottom:8}}>{scenario.label}</h3>

              {/* Winner comparison */}
              <div className="kv" style={{marginBottom:12}}>
                <div className="item">Winner: <b>{scenario.winner.vendor}</b></div>
                <div className="item">Compute: <b>{scenario.winner.compute_service}</b></div>
                <div className="item">
                  Cost: <b>${scenario.winner.monthly_cost.toFixed(2)}/mo</b>
                  {scenario.delta_analysis.deltas[0]?.cost_delta !== null && (
                    <> ({renderDelta(scenario.delta_analysis.deltas[0].cost_delta, '')} / {renderDelta(scenario.delta_analysis.deltas[0].cost_delta_pct, '%')})</>
                  )}
                </div>
                <div className="item">
                  p95: <b>{scenario.winner.p95_ms.toFixed(1)}ms</b>
                  {scenario.delta_analysis.deltas[0]?.p95_delta !== null && (
                    <> ({renderDelta(scenario.delta_analysis.deltas[0].p95_delta, 'ms')})</>
                  )}
                </div>
              </div>

              {/* Delta table */}
              <table className="table" style={{fontSize:12}}>
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Vendor</th>
                    <th>Compute</th>
                    <th>Cost</th>
                    <th>Cost Δ</th>
                    <th>p95</th>
                    <th>p95 Δ</th>
                    <th>Rank Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {scenario.delta_analysis.deltas.map((delta, i) => (
                    <tr key={i} className={i===0?'winner-row':''}>
                      <td><b>#{delta.rank}</b></td>
                      <td>{delta.vendor}</td>
                      <td>{delta.compute_service}</td>
                      <td>${delta.monthly_cost.toFixed(2)}</td>
                      <td>{renderDelta(delta.cost_delta, '')} ({renderDelta(delta.cost_delta_pct, '%')})</td>
                      <td>{delta.p95_ms.toFixed(1)}ms</td>
                      <td>{renderDelta(delta.p95_delta, 'ms')}</td>
                      <td>{renderRankChange(delta.rank_delta)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
