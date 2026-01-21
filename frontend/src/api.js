const API_BASE = import.meta.env.VITE_API_BASE || '' // '' proxied in dev, same origin in prod

export async function plan(workload) {
  const res = await fetch(`${API_BASE}/api/plan`, {
    method: 'POST',
    headers: { 'Content-Type':'application/json' },
    body: JSON.stringify(workload)
  })
  if (!res.ok) {
    const text = await res.text().catch(()=> '')
    throw new Error(`API error ${res.status}: ${text}`)
  }
  return res.json()
}

export async function health() {
  const res = await fetch(`${API_BASE}/health`)
  return res.ok
}

export async function simulate(baseline, overrides) {
  const res = await fetch(`${API_BASE}/api/simulate`, {
    method: 'POST',
    headers: { 'Content-Type':'application/json' },
    body: JSON.stringify({ baseline, overrides })
  })
  if (!res.ok) {
    const text = await res.text().catch(()=> '')
    throw new Error(`API error ${res.status}: ${text}`)
  }
  return res.json()
}
