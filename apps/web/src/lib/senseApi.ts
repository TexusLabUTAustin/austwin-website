const SENSE_API_BASE =
  import.meta.env.VITE_SENSE_API_URL?.replace(/\/$/, '') ||
  (import.meta.env.DEV ? '/api/sense' : '/api/sense')

export type AnomalyFactors = {
  spatial: number
  temporal: number
  morphology: number
}

export type AnomalyResponse = {
  last_updated: string
  station: string
  horizon: number
  horizons: number[]
  cityforesight_model: string
  features: import('geojson').FeatureCollection
  summary: {
    watch: number
    alert: number
    extreme: number
    max_score: number
  }
}

export type TractAnomalyDetail = {
  geoid: string
  name: string
  anomaly: {
    anomaly_score: number
    severity: string
    horizon: number
    tract_forecast: number
    city_median: number
    observed_heat_index: number
    factors: AnomalyFactors
  }
  last_updated: string
  ontology: unknown
}

export async function fetchAnomalies(): Promise<AnomalyResponse> {
  const res = await fetch(`${SENSE_API_BASE}/anomalies/current`)
  if (!res.ok) throw new Error('Failed to load anomalies')
  return res.json()
}

export async function fetchTractAnomaly(geoid: string): Promise<TractAnomalyDetail> {
  const res = await fetch(`${SENSE_API_BASE}/anomalies/tract/${geoid}`)
  if (!res.ok) throw new Error('Tract not found')
  return res.json()
}
