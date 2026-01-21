import React from 'react'
import { useState } from 'react'
import { generateTerraform } from '../utils/terraform.js'

export default function Results({ data, workload }) {
  const [expandedIdx, setExpandedIdx] = useState(null)
  const [copyStatus, setCopyStatus] = useState('')
  const [exportStatus, setExportStatus] = useState('')
  const [tfStatus, setTfStatus] = useState('')

  if (!data) return null
  const { winner, winner_reason, top3, evals, why, constraints, assumptions } = data

  function copyShareLink() {
    const encoded = btoa(JSON.stringify(workload))
    const url = `${window.location.origin}${window.location.pathname}?workload=${encoded}`
    navigator.clipboard.writeText(url).then(() => {
      setCopyStatus('✓ Copied!')
      setTimeout(() => setCopyStatus(''), 2500)
    })
  }

  function exportJSON() {
    const exportData = {
      workload,
      results: data,
      exported_at: new Date().toISOString()
    }
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `case-optimizer-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
    setExportStatus('✓ Exported!')
    setTimeout(() => setExportStatus(''), 2500)
  }

  function exportTerraform() {
    if (!winner || !workload) {
      alert('No winner available for Terraform export')
      return
    }
    const tf = generateTerraform(winner, workload)
    const blob = new Blob([tf], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `case-optimizer-${winner.vendor}-${winner.compute_service}.tf`
    a.click()
    URL.revokeObjectURL(url)
    setTfStatus('✓ Generated!')
    setTimeout(() => setTfStatus(''), 2500)
  }

  function getScoreColor(score) {
    if (score >= 80) return '#21c87a'
    if (score >= 60) return '#7aa2ff'
    if (score >= 40) return '#ffcc66'
    return '#ff6b6b'
  }

  function getRankBadge(rank) {
    const badges = {
      0: '🥇',
      1: '🥈',
      2: '🥉'
    }
    return badges[rank] || `#${rank + 1}`
  }

  return (
    <div className="card" style={{animation: 'fadeInUp 0.5s ease'}}>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:24, flexWrap:'wrap', gap:16}}>
        <div>
          <h1 style={{margin:'0 0 6px 0', fontSize:'32px'}}>Results</h1>
          <div className="small" style={{fontSize:'14px', opacity:0.8}}>Optimized cloud architecture recommendations</div>
        </div>
        <div style={{display:'flex', gap:10, flexWrap:'wrap'}}>
          <button className="btn" onClick={copyShareLink} style={{fontSize:13, padding:'10px 16px', background: copyStatus ? '#21c87a' : '#7aa2ff'}}>
            {copyStatus || '📋 Share'}
          </button>
          <button className="btn" onClick={exportJSON} style={{fontSize:13, padding:'10px 16px', background: exportStatus ? '#21c87a' : '#7aa2ff'}}>
            {exportStatus || '📄 JSON'}
          </button>
          {winner && (
            <button className="btn" onClick={exportTerraform} style={{fontSize:13, padding:'10px 16px', background: tfStatus ? '#21c87a' : '#059669'}}>
              {tfStatus || '🚀 Terraform'}
            </button>
          )}
        </div>
      </div>

      {winner ? (
        <>
          <div style={{
            background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)',
            border: '1.5px solid rgba(122, 162, 255, 0.3)',
            borderRadius: '16px',
            padding: '20px',
            marginBottom: '20px'
          }}>
            <div style={{display:'flex', alignItems:'center', gap:12, marginBottom:16}}>
              <span style={{fontSize:'32px'}}>🏆</span>
              <div>
                <div style={{fontSize:'18px', fontWeight:600, marginBottom:4}}>Winner</div>
                <div className="small" style={{opacity:0.8}}>Best overall architecture for your workload</div>
              </div>
            </div>

            <div className="kv" style={{marginBottom:16}}>
              <div className="item" style={{borderColor:'rgba(122, 162, 255, 0.4)'}}>
                <span style={{opacity:0.7}}>Vendor:</span> <b>{winner.vendor.toUpperCase()}</b>
              </div>
              <div className="item" style={{borderColor:'rgba(122, 162, 255, 0.4)'}}>
                <span style={{opacity:0.7}}>Compute:</span> <b>{winner.compute_service}</b>
              </div>
              <div className="item" style={{borderColor:'rgba(122, 162, 255, 0.4)'}}>
                <span style={{opacity:0.7}}>Storage:</span> <b>{winner.storage_service}</b>
              </div>
              <div className="item" style={{borderColor:'rgba(33, 200, 122, 0.4)', background:'rgba(33, 200, 122, 0.05)'}}>
                <span style={{opacity:0.7}}>Cost:</span> <b style={{color:'#21c87a'}}>${winner.monthly_cost.toFixed(2)}/mo</b>
              </div>
            </div>

            {winner_reason && (
              <div style={{
                background: 'rgba(15, 27, 63, 0.5)',
                borderRadius: '12px',
                padding: '16px',
                border: '1px solid rgba(122, 162, 255, 0.2)'
              }}>
                <div style={{fontSize:14, fontWeight:600, marginBottom:10, color:'#7aa2ff'}}>Why This Won</div>
                <div className="small" style={{marginBottom:8, lineHeight:1.6}}>{winner_reason.summary}</div>
                <div className="small" style={{marginBottom:6, opacity:0.9}}>
                  💰 {winner_reason.cost_analysis}
                </div>
                <div className="small" style={{marginBottom:6, opacity:0.9}}>
                  ⚡ {winner_reason.performance_analysis}
                </div>
                {winner_reason.preference_match && (
                  <div className="small" style={{color:'#21c87a', fontWeight:500}}>
                    ✓ Matches your vendor preference
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      ) : <div className="warn" style={{padding:16, background:'rgba(255, 204, 102, 0.1)', borderRadius:12, border:'1px solid rgba(255, 204, 102, 0.3)'}}>No feasible winner found for your constraints.</div>}

      {top3?.length ? (
        <>
          <h3 style={{marginTop:24, marginBottom:16, fontSize:'20px'}}>Top 3 Recommendations</h3>
          <div style={{overflowX:'auto'}}>
            <table className="table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Vendor</th>
                  <th>Compute</th>
                  <th>Storage</th>
                  <th>Cost ($/mo)</th>
                  <th>p95 (ms)</th>
                  <th>Score</th>
                  <th>Cost</th>
                  <th>Perf</th>
                  <th>Pref</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {top3.map((o,i)=>(
                  <React.Fragment key={i}>
                    <tr
                      className={i===0?'winner-row':''}
                      style={{cursor: o.cost_breakdown ? 'pointer' : 'default'}}
                      onClick={()=>o.cost_breakdown && setExpandedIdx(expandedIdx===i ? null : i)}
                    >
                      <td><span style={{fontSize:'18px'}}>{getRankBadge(i)}</span></td>
                      <td><b>{o.vendor.toUpperCase()}</b></td>
                      <td><span className="badge" style={{background:'rgba(122, 162, 255, 0.1)', border:'1px solid rgba(122, 162, 255, 0.3)', color:'var(--text)'}}>{o.compute_service}</span></td>
                      <td><span className="badge" style={{background:'rgba(102, 126, 234, 0.1)', border:'1px solid rgba(102, 126, 234, 0.3)', color:'var(--text)'}}>{o.storage_service}</span></td>
                      <td><b>${o.monthly_cost.toFixed(2)}</b></td>
                      <td>{o.p95_ms.toFixed(1)}ms</td>
                      <td>
                        <div style={{display:'flex', alignItems:'center', gap:6}}>
                          <div style={{
                            width:6,
                            height:20,
                            borderRadius:3,
                            background: getScoreColor(o.score_breakdown.composite)
                          }}/>
                          <b style={{color: getScoreColor(o.score_breakdown.composite)}}>{o.score_breakdown.composite.toFixed(0)}</b>
                        </div>
                      </td>
                      <td style={{opacity:0.8}}>{o.score_breakdown.cost_score.toFixed(0)}</td>
                      <td style={{opacity:0.8}}>{o.score_breakdown.perf_score.toFixed(0)}</td>
                      <td style={{opacity:0.8}}>{o.score_breakdown.preference_score}</td>
                      <td style={{textAlign:'center'}}>
                        {o.cost_breakdown && (
                          <span style={{fontSize:12, opacity:0.6}}>{expandedIdx===i ? '▼' : '▶'}</span>
                        )}
                      </td>
                    </tr>
                    {expandedIdx === i && o.cost_breakdown && (
                      <tr style={{animation: 'fadeInUp 0.3s ease'}}>
                        <td colSpan="11" style={{background:'rgba(15, 27, 63, 0.5)', padding:20, borderRadius:12}}>
                          <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(200px, 1fr))', gap:20}}>
                            <div>
                              <div className="small" style={{marginBottom:10, fontWeight:600, color:'#7aa2ff', fontSize:13}}>💰 Cost Breakdown</div>
                              <div style={{display:'flex', flexDirection:'column', gap:6}}>
                                <div className="small" style={{display:'flex', justifyContent:'space-between', padding:'6px 0', borderBottom:'1px solid rgba(43, 53, 93, 0.3)'}}>
                                  <span style={{opacity:0.7}}>Compute:</span>
                                  <b>${o.cost_breakdown.compute.toFixed(2)}</b>
                                </div>
                                <div className="small" style={{display:'flex', justifyContent:'space-between', padding:'6px 0', borderBottom:'1px solid rgba(43, 53, 93, 0.3)'}}>
                                  <span style={{opacity:0.7}}>Storage:</span>
                                  <b>${o.cost_breakdown.storage.toFixed(2)}</b>
                                </div>
                                {o.cost_breakdown.egress > 0 && (
                                  <div className="small" style={{display:'flex', justifyContent:'space-between', padding:'6px 0', borderBottom:'1px solid rgba(43, 53, 93, 0.3)'}}>
                                    <span style={{opacity:0.7}}>Egress:</span>
                                    <b>${o.cost_breakdown.egress.toFixed(2)}</b>
                                  </div>
                                )}
                                {o.cost_breakdown.addons > 0 && (
                                  <div className="small" style={{display:'flex', justifyContent:'space-between', padding:'6px 0', borderBottom:'1px solid rgba(43, 53, 93, 0.3)'}}>
                                    <span style={{opacity:0.7}}>Add-ons:</span>
                                    <b>${o.cost_breakdown.addons.toFixed(2)}</b>
                                  </div>
                                )}
                                <div className="small" style={{display:'flex', justifyContent:'space-between', padding:'6px 0', borderBottom:'1px solid rgba(43, 53, 93, 0.3)'}}>
                                  <span style={{opacity:0.7}}>Overhead (5%):</span>
                                  <b>${o.cost_breakdown.overhead.toFixed(2)}</b>
                                </div>
                                <div className="small" style={{display:'flex', justifyContent:'space-between', padding:'10px 0', marginTop:6}}>
                                  <span style={{fontWeight:600, color:'#7aa2ff'}}>Total:</span>
                                  <b style={{fontSize:15, color:'#21c87a'}}>${o.cost_breakdown.total.toFixed(2)}</b>
                                </div>
                              </div>
                            </div>
                            <div>
                              <div className="small" style={{marginBottom:10, fontWeight:600, color:'#7aa2ff', fontSize:13}}>⚙️ Models Used</div>
                              <div style={{display:'flex', flexDirection:'column', gap:8}}>
                                <div className="small">
                                  <span style={{opacity:0.7}}>Performance:</span> <span className="badge" style={{marginLeft:6}}>{o.perf_model || 'unknown'}</span>
                                </div>
                                <div className="small">
                                  <span style={{opacity:0.7}}>Availability:</span> <span className="badge" style={{marginLeft:6}}>{o.avail_model || 'unknown'}</span>
                                </div>
                                <div className="small">
                                  <span style={{opacity:0.7}}>Uptime:</span> <b style={{marginLeft:6, color:'#21c87a'}}>{o.availability}%</b>
                                </div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <div className="small" style={{marginTop:12, padding:12, background:'rgba(122, 162, 255, 0.05)', borderRadius:8, lineHeight:1.7}}>
            <b>Scoring:</b> Composite = Cost(50%) + Performance(30%) + Preference(20%). All scores 0-100, higher is better.
            <br/>
            <b>Tip:</b> Click on any row to see detailed cost breakdown.
          </div>
        </>
      ): null}

      {constraints?.length ? (
        <>
          <h3 style={{marginTop:24, marginBottom:12, fontSize:'18px'}}>🔒 Detected Constraints</h3>
          <div style={{display:'flex', flexDirection:'column', gap:8}}>
            {constraints.map((c,i)=>(
              <div key={i} style={{
                padding:'12px 16px',
                background:'rgba(255, 204, 102, 0.08)',
                border:'1px solid rgba(255, 204, 102, 0.3)',
                borderRadius:'10px',
                fontSize:'13px'
              }}>
                <b style={{color:'#ffcc66'}}>{c.type}:</b> <span style={{marginLeft:8, opacity:0.9}}>{c.reason}</span>
              </div>
            ))}
          </div>
        </>
      ) : null}

      <h3 style={{marginTop:24, marginBottom:16, fontSize:'18px'}}>📊 All Evaluations</h3>
      <div style={{overflowX:'auto'}}>
        <table className="table">
          <thead>
            <tr>
              <th>Vendor</th>
              <th>Compute</th>
              <th>Storage</th>
              <th>Feasible</th>
              <th>Cost ($/mo)</th>
              <th>p95 (ms)</th>
              <th>Avail</th>
              <th>Pricing</th>
              <th>Policy</th>
            </tr>
          </thead>
          <tbody>
            {evals.map((e,i)=>(
              <tr key={i}>
                <td><b>{e.vendor.toUpperCase()}</b></td>
                <td>{e.compute_service}</td>
                <td>{e.storage_service}</td>
                <td className={e.feasible==='yes'?'ok':'warn'}>
                  {e.feasible}
                  {e.policy_violations?.length > 0 && (
                    <span style={{marginLeft:6, cursor:'help', fontSize:14}} title={e.policy_violations.join('; ')}>⚠️</span>
                  )}
                </td>
                <td>${e.monthly_cost.toFixed(2)}</td>
                <td>{e.p95_ms.toFixed(1)}ms</td>
                <td>{e.availability}%</td>
                <td><span className="badge">{e.reason || 'evaluator'}</span></td>
                <td>
                  {e.policy_violations?.length > 0 ? (
                    <span className="warn" style={{fontSize:11, fontWeight:600}}>{e.policy_violations.length} violation(s)</span>
                  ) : (
                    <span className="ok" style={{fontSize:16}}>✓</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {why?.length ? (
        <>
          <h3 style={{marginTop:24, marginBottom:12, fontSize:'18px'}}>💡 Reasoning</h3>
          <div style={{display:'flex', flexDirection:'column', gap:8}}>
            {why.map((w,i)=>(
              <div key={i} style={{
                padding:'10px 14px',
                background:'rgba(122, 162, 255, 0.05)',
                border:'1px solid rgba(122, 162, 255, 0.2)',
                borderRadius:'8px',
                fontSize:'13px',
                lineHeight:1.6
              }}>
                • {w}
              </div>
            ))}
          </div>
        </>
      ) : null}

      {assumptions && (
        <>
          <h3 style={{marginTop:24, marginBottom:12, fontSize:'18px'}}>📋 Assumptions</h3>
          <div className="kv">
            <div className="item">
              <span style={{opacity:0.7}}>Pricing Model:</span> <b>{assumptions.pricing_model}</b>
            </div>
            <div className="item">
              <span style={{opacity:0.7}}>Region:</span> <b>{assumptions.region}</b>
            </div>
            <div className="item">
              <span style={{opacity:0.7}}>SLA Tier:</span> <b>{assumptions.sla_tier}</b>
            </div>
            {assumptions.compliance !== 'none' && (
              <div className="item">
                <span style={{opacity:0.7}}>Compliance:</span> <b>{assumptions.compliance.toUpperCase()}</b>
              </div>
            )}
          </div>
        </>
      )}

      <div className="footer" style={{marginTop:32}}>
        <div style={{opacity:0.5}}>Powered by CASE Optimizer • Built with ❤️</div>
      </div>
    </div>
  )
}
