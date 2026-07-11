import type { FeatureCollection } from 'geojson'
import { heatIndexColor } from './forecastUtils'

export type TractSnapshot = {
  geoid: string
  name: string
  value: number
  impervious?: number
  canopy?: number
  populationDensity?: number
}

export type HorizonInsights = {
  horizon: number
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
): TractSnapshot[] {
  return features.features.map((f) => {
    const props = f.properties ?? {}
    const forecasts = props.forecasts as Record<string, number> | undefined
    return {
      geoid: String(props.GEOID ?? ''),
      name: String(props.NAME ?? props.GEOID ?? 'Tract'),
      value: forecasts?.[String(horizon)] ?? 0,
      impervious: props.impervious_ratio as number | undefined,
      canopy: props.canopy_cover as number | undefined,
      populationDensity: props.population_density as number | undefined,
    }
  })
}

export function computeHorizonInsights(
  features: FeatureCollection,
  horizon: number,
): HorizonInsights {
  const tracts = getTractSnapshots(features, horizon)
  const values = tracts.map((t) => t.value)
  const average = values.reduce((a, b) => a + b, 0) / values.length
  const min = Math.min(...values)
  const max = Math.max(...values)
  const hottest = tracts.find((t) => t.value === max)!
  const coolest = tracts.find((t) => t.value === min)!

  return {
    horizon,
    average,
    min,
    max,
    spread: max - min,
    hottest,
    coolest,
    comfortable: values.filter((v) => v < 80).length,
    caution: values.filter((v) => v >= 80 && v < 90).length,
    elevated: values.filter((v) => v >= 90 && v < 100).length,
    extreme: values.filter((v) => v >= 100).length,
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

export function formatPercent(ratio: number | undefined): string {
  if (ratio === undefined) return '—'
  return `${(ratio * 100).toFixed(0)}%`
}
