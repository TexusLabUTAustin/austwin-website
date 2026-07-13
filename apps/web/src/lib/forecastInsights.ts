import type { FeatureCollection } from 'geojson'
import { heatIndexColor } from './forecastUtils'
import {
  floodRiskColor,
  getHazardForecasts,
  gridStressColor,
  type HazardId,
} from './hazardUtils'

export type TractSnapshot = {
  geoid: string
  name: string
  value: number
  impervious?: number
  canopy?: number
  populationDensity?: number
  anomalySeverity?: string
  anomalyScore?: number
}

export type HorizonInsights = {
  horizon: number
  hazard: HazardId
  average: number
  min: number
  max: number
  spread: number
  hottest: TractSnapshot
  coolest: TractSnapshot
  comfortable: number
  caution: number
  elevated: number
  extreme: number
  total: number
}

export type TractTrend = {
  values: number[]
  horizons: number[]
  delta: number
  direction: 'rising' | 'falling' | 'steady'
  vsCityAvg: number
}

export function getTractSnapshots(
  features: FeatureCollection,
  horizon: number,
  hazard: HazardId = 'heat',
): TractSnapshot[] {
  return features.features.map((f) => {
    const props = (f.properties ?? {}) as Record<string, unknown>
    const forecasts = getHazardForecasts(props, hazard)
    return {
      geoid: String(props.GEOID ?? ''),
      name: String(props.NAME ?? props.GEOID ?? 'Tract'),
      value: forecasts[String(horizon)] ?? 0,
      impervious: props.impervious_ratio as number | undefined,
      canopy: props.canopy_cover as number | undefined,
      populationDensity: props.population_density as number | undefined,
      anomalySeverity: props.anomaly_severity as string | undefined,
      anomalyScore: props.anomaly_score as number | undefined,
    }
  })
}

function riskBuckets(hazard: HazardId, values: number[]) {
  if (hazard === 'heat') {
    return {
      comfortable: values.filter((v) => v < 80).length,
      caution: values.filter((v) => v >= 80 && v < 90).length,
      elevated: values.filter((v) => v >= 90 && v < 100).length,
      extreme: values.filter((v) => v >= 100).length,
    }
  }
  return {
    comfortable: values.filter((v) => v < 25).length,
    caution: values.filter((v) => v >= 25 && v < 50).length,
    elevated: values.filter((v) => v >= 50 && v < 75).length,
    extreme: values.filter((v) => v >= 75).length,
  }
}

export function computeHorizonInsights(
  features: FeatureCollection,
  horizon: number,
  hazard: HazardId = 'heat',
): HorizonInsights {
  const tracts = getTractSnapshots(features, horizon, hazard)
  const values = tracts.map((t) => t.value)
  const average = values.reduce((a, b) => a + b, 0) / Math.max(values.length, 1)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const hottest = tracts.find((t) => t.value === max)!
  const coolest = tracts.find((t) => t.value === min)!
  const buckets = riskBuckets(hazard, values)

  return {
    horizon,
    hazard,
    average,
    min,
    max,
    spread: max - min,
    hottest,
    coolest,
    ...buckets,
    total: tracts.length,
  }
}

export function computeTractTrend(
  forecasts: Record<string, number>,
  horizons: number[],
  cityAverage: number,
): TractTrend {
  const values = horizons.map((h) => forecasts[String(h)] ?? 0)
  const delta = values[values.length - 1] - values[0]
  const direction =
    Math.abs(delta) < 0.5 ? 'steady' : delta > 0 ? 'rising' : 'falling'
  const midHorizon = horizons[Math.floor(horizons.length / 2)]
  const vsCityAvg = (forecasts[String(midHorizon)] ?? 0) - cityAverage

  return { values, horizons, delta, direction, vsCityAvg }
}

export function heatRiskLabel(value: number): string {
  if (value < 80) return 'Comfortable'
  if (value < 90) return 'Caution'
  if (value < 100) return 'Elevated heat stress'
  if (value < 110) return 'High heat risk'
  return 'Extreme heat'
}

export function heatRiskClass(value: number): string {
  return heatIndexColor(value)
}

export function hazardMapColor(hazard: HazardId, value: number): string {
  if (hazard === 'flood') return floodRiskColor(value)
  if (hazard === 'grid') return gridStressColor(value)
  return heatIndexColor(value)
}

export function formatPercent(ratio: number | undefined): string {
  if (ratio === undefined) return '—'
  return `${(ratio * 100).toFixed(0)}%`
}
