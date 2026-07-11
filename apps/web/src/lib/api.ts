const API_BASE =
  import.meta.env.VITE_API_URL?.replace(/\/$/, '') ||
  (import.meta.env.DEV ? '/api' : '/api')

export type ForecastResponse = {
  last_updated: string
  station: string
  horizons: number[]
  model: string
  features: import('geojson').FeatureCollection
  summary: { min_heat_index: number; max_heat_index: number }
}

export type BenchmarkResponse = {
  baseline_rmse: number
  kil_rmse: number
  improvement_pct: number
  gate_passed?: boolean
  gate_threshold_pct?: number
}

export async function fetchCurrentForecast(): Promise<ForecastResponse> {
  const res = await fetch(`${API_BASE}/forecasts/current`)
  if (!res.ok) throw new Error('Failed to load forecast')
  return res.json()
}

export async function fetchBenchmark(): Promise<BenchmarkResponse> {
  const res = await fetch(`${API_BASE}/metrics/benchmark`)
  if (!res.ok) throw new Error('Benchmark not available')
  return res.json()
}

export async function fetchTractForecast(geoid: string) {
  const res = await fetch(`${API_BASE}/forecasts/tract/${geoid}`)
  if (!res.ok) throw new Error('Tract not found')
  return res.json()
}

export type AddressSearchResult = {
  query?: string
  matched_address: string
  lat: number
  lon: number
  geoid: string
  name: string
  forecasts: Record<string, number>
  morphology: {
    impervious_ratio: number
    canopy_cover: number
    drainage_capacity: number
    population_density: number
  }
  last_updated: string
  coverage_note: string
}

export type AddressSearchCandidate = {
  matched_address: string
  lat: number
  lon: number
}

export type AddressSearchResponse =
  | AddressSearchResult
  | { query: string; candidates: AddressSearchCandidate[] }

export function isAddressSearchResult(
  r: AddressSearchResponse,
): r is AddressSearchResult {
  return 'geoid' in r && typeof r.geoid === 'string'
}

export async function searchForecastByAddress(q: string): Promise<AddressSearchResponse> {
  const res = await fetch(`${API_BASE}/forecasts/search?${new URLSearchParams({ q })}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : 'Address not found'
    throw new Error(detail)
  }
  return res.json()
}

export async function lookupForecastAtPoint(
  lat: number,
  lon: number,
  q?: string,
): Promise<AddressSearchResult> {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
  })
  if (q) params.set('q', q)
  const res = await fetch(`${API_BASE}/forecasts/lookup?${params}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : 'Location not in coverage'
    throw new Error(detail)
  }
  return res.json()
}
