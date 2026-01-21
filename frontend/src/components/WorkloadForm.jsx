import React from 'react'
import { useState, useEffect } from 'react'


const defaults = {
  workload_type: 'api',
  traffic_rps: 800,
  variability: 'spiky',
  latency: 60,
  statefulness: 'stateless',
  persistence_model: 'sql',
  data_size_gb: 120,
  compliance: 'none',
  sla_tier: 'standard',
  multi_region_needed: 'no',
  vendor_preference: 'none',
  region: 'us-east-1',
  avg_exec_ms: 80,
  p95_target_ms: 120,
  mem_gb: 0.5,
  cpu_vcpu: 0.5,
  storage_gb_hot: 50,
  storage_gb_cold: 0,
  read_qps: 0,
  write_qps: 0,
  egress_gb_month: 0,
  budget_monthly: 0,
  vendor_exclude: []
}

export default function WorkloadForm({ onSubmit, busy, sharedWorkload }) {
  const [w, setW] = useState(defaults)

  // Load shared workload if provided
  useEffect(() => {
    if (sharedWorkload) {
      setW({ ...defaults, ...sharedWorkload })
    }
  }, [sharedWorkload])

  function setField(k, v) {
    setW(prev => ({ ...prev, [k]: v }))
  }

  return (
    <div className="card" style={{marginBottom:16}}>
      <h1>CASE Optimizer</h1>
      <div className="small" style={{marginBottom:12}}>Fill in your workload and get the best cloud bundle by cost, latency, and availability.</div>

      <h3 style={{fontSize:14, marginTop:16, marginBottom:8}}>Workload Characteristics</h3>
      <div className="grid">
        <div className="row">
          <label>Workload Type</label>
          <select value={w.workload_type} onChange={e=>setField('workload_type', e.target.value)}>
            <option>web</option><option>api</option><option>batch</option><option>stream</option><option>analytics</option>
          </select>
        </div>
        <div className="row">
          <label>Traffic (RPS)</label>
          <input type="number" value={w.traffic_rps} onChange={e=>setField('traffic_rps', Number(e.target.value))}/>
        </div>
        <div className="row">
          <label>Variability</label>
          <select value={w.variability} onChange={e=>setField('variability', e.target.value)}>
            <option>steady</option><option>spiky</option>
          </select>
        </div>
      </div>

      <h3 style={{fontSize:14, marginTop:16, marginBottom:8}}>Performance Requirements</h3>
      <div className="grid">
        <div className="row">
          <label>Latency Target (ms)</label>
          <input type="number" value={w.latency} onChange={e=>setField('latency', Number(e.target.value))}/>
        </div>
        <div className="row">
          <label>p95 Target (ms) (0=no constraint)</label>
          <input type="number" value={w.p95_target_ms} onChange={e=>setField('p95_target_ms', Number(e.target.value))}/>
        </div>
        <div className="row">
          <label>Avg Exec (ms)</label>
          <input type="number" value={w.avg_exec_ms} onChange={e=>setField('avg_exec_ms', Number(e.target.value))}/>
        </div>
      </div>

      <h3 style={{fontSize:14, marginTop:16, marginBottom:8}}>Compute Resources</h3>
      <div className="grid">
        <div className="row">
          <label>Memory (GiB)</label>
          <input type="number" step="0.1" value={w.mem_gb} onChange={e=>setField('mem_gb', Number(e.target.value))}/>
        </div>
        <div className="row">
          <label>CPU (vCPU)</label>
          <input type="number" step="0.1" value={w.cpu_vcpu} onChange={e=>setField('cpu_vcpu', Number(e.target.value))}/>
        </div>
        <div className="row">
          <label>Statefulness</label>
          <select value={w.statefulness} onChange={e=>setField('statefulness', e.target.value)}>
            <option>stateless</option><option>stateful</option>
          </select>
        </div>
      </div>

      <h3 style={{fontSize:14, marginTop:16, marginBottom:8}}>Storage & Data</h3>
      <div className="grid">
        <div className="row">
          <label>Persistence Model</label>
          <select value={w.persistence_model} onChange={e=>setField('persistence_model', e.target.value)}>
            <option>none</option><option>sql</option><option>nosql</option><option>cache</option><option>object</option>
          </select>
        </div>
        <div className="row">
          <label>Hot Storage (GB)</label>
          <input type="number" step="1" value={w.storage_gb_hot} onChange={e=>setField('storage_gb_hot', Number(e.target.value))}/>
        </div>
        <div className="row">
          <label>Cold Storage (GB)</label>
          <input type="number" step="1" value={w.storage_gb_cold} onChange={e=>setField('storage_gb_cold', Number(e.target.value))}/>
        </div>
        <div className="row">
          <label>Read QPS</label>
          <input type="number" value={w.read_qps} onChange={e=>setField('read_qps', Number(e.target.value))}/>
        </div>
        <div className="row">
          <label>Write QPS</label>
          <input type="number" value={w.write_qps} onChange={e=>setField('write_qps', Number(e.target.value))}/>
        </div>
        <div className="row">
          <label>Egress (GB/month)</label>
          <input type="number" value={w.egress_gb_month} onChange={e=>setField('egress_gb_month', Number(e.target.value))}/>
        </div>
      </div>

      <h3 style={{fontSize:14, marginTop:16, marginBottom:8}}>Compliance & Preferences</h3>
      <div className="grid">
        <div className="row">
          <label>Compliance</label>
          <select value={w.compliance} onChange={e=>setField('compliance', e.target.value)}>
            <option>none</option><option>hipaa</option><option>pci-dss</option><option>gdpr</option><option>sox</option>
          </select>
        </div>
        <div className="row">
          <label>SLA Tier</label>
          <select value={w.sla_tier} onChange={e=>setField('sla_tier', e.target.value)}>
            <option>standard</option><option>high</option><option>critical</option>
          </select>
        </div>
        <div className="row">
          <label>Multi-Region</label>
          <select value={w.multi_region_needed} onChange={e=>setField('multi_region_needed', e.target.value)}>
            <option>no</option><option>yes</option>
          </select>
        </div>
        <div className="row">
          <label>Vendor Preference</label>
          <select value={w.vendor_preference} onChange={e=>setField('vendor_preference', e.target.value)}>
            <option>none</option><option>aws</option><option>azure</option><option>gcp</option>
          </select>
        </div>
        <div className="row">
          <label>Region</label>
          <input value={w.region} onChange={e=>setField('region', e.target.value)}/>
        </div>
      </div>

      <h3 style={{fontSize:14, marginTop:16, marginBottom:8}}>Policy Constraints</h3>
      <div className="grid">
        <div className="row">
          <label>Budget Cap ($/month, 0=unlimited)</label>
          <input type="number" value={w.budget_monthly} onChange={e=>setField('budget_monthly', Number(e.target.value))}/>
        </div>
        <div className="row">
          <label>Exclude Vendors (comma-separated: aws,azure,gcp)</label>
          <input
            value={w.vendor_exclude.join(',')}
            onChange={e=>setField('vendor_exclude', e.target.value.split(',').map(v=>v.trim()).filter(v=>v))}
            placeholder="e.g., gcp"
          />
        </div>
      </div>

      <div style={{marginTop:12, display:'flex', gap:8, alignItems:'center'}}>
        <button className="btn" disabled={busy} onClick={()=>onSubmit(w)}>
          {busy ? 'Planning…' : 'Plan'}
        </button>
        <span className="small">Live pricing is used when available (set <code>REALTIME_PRICING=1</code>).</span>
      </div>
    </div>
  )
}
