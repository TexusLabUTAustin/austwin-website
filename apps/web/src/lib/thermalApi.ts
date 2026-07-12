import type { UtciMeta, UtciSample } from './utciUtils'

export async function fetchUtciMeta(): Promise<UtciMeta | null> {
  const res = await fetch('/api/thermal/utci')
  if (!res.ok) return null
  return res.json()
}

export async function sampleUtciAt(lat: number, lon: number): Promise<UtciSample | null> {
  const q = new URLSearchParams({ lat: String(lat), lon: String(lon) })
  const res = await fetch(`/api/thermal/utci/sample?${q}`)
  if (!res.ok) return null
  return res.json()
}
