/** Multi-hazard helpers for CityForesight map / panel. */

export type HazardId = 'heat' | 'flood' | 'grid'

export const HAZARD_OPTIONS: { id: HazardId; label: string; short: string }[] = [
  { id: 'heat', label: 'Heat', short: 'Heat' },
  { id: 'flood', label: 'Flood', short: 'Flood' },
  { id: 'grid', label: 'Grid', short: 'Grid' },
]

export const HAZARD_CUE: Record<HazardId, string> = {
  heat: 'Warm colors = higher heat index (°F) from KAUS weather + land-cover KIL.',
  flood: 'Flood score from live USGS gauges + Open-Meteo precip (0–100).',
  grid: 'Grid score from live ERCOT demand/capacity + heat + density (0–100).',
}

export const HAZARD_EXPLAIN: Record<HazardId, string> = {
  heat: 'Tract heat index blends airport observations with impervious/canopy morphology. Not a thermometer at your address.',
  flood: 'Built from USGS stream gage height/discharge near each tract and recent rainfall. Higher near rising creeks.',
  grid: 'Built from ERCOT system demand vs capacity, then raised where it is hotter and denser. Not an outage map.',
}


const PROP_KEY: Record<HazardId, string> = {
  heat: 'forecasts',
  flood: 'flood_forecasts',
  grid: 'grid_forecasts',
}

export function hazardForecastKey(hazard: HazardId): string {
  return PROP_KEY[hazard]
}

export function getHazardForecasts(
  props: Record<string, unknown> | null | undefined,
  hazard: HazardId,
): Record<string, number> {
  if (!props) return {}
  const key = PROP_KEY[hazard]
  const raw = props[key]
  if (raw && typeof raw === 'object') return raw as Record<string, number>
  // Backward compat: heat only
  if (hazard === 'heat' && props.forecasts && typeof props.forecasts === 'object') {
    return props.forecasts as Record<string, number>
  }
  return {}
}

export function getHazardValue(
  props: Record<string, unknown> | null | undefined,
  hazard: HazardId,
  horizon: number,
): number | undefined {
  const map = getHazardForecasts(props, hazard)
  const v = map[String(horizon)]
  return typeof v === 'number' ? v : undefined
}

export function getHazardConfidence(
  props: Record<string, unknown> | null | undefined,
  hazard: HazardId,
  horizon: number,
): number | undefined {
  const conf = props?.confidence as
    | Record<string, Record<string, number>>
    | undefined
  const v = conf?.[hazard]?.[String(horizon)]
  return typeof v === 'number' ? v : undefined
}

/** Flood risk 0–100 → blue ramp. */
export function floodRiskColor(score: number): string {
  const t = Math.max(0, Math.min(1, score / 100))
  const stops: [number, string][] = [
    [0, '#e0f2fe'],
    [0.25, '#7dd3fc'],
    [0.5, '#38bdf8'],
    [0.75, '#0284c7'],
    [1, '#0c4a6e'],
  ]
  return rampColor(stops, t)
}

/** Grid stress 0–100 → amber/red ramp. */
export function gridStressColor(score: number): string {
  const t = Math.max(0, Math.min(1, score / 100))
  const stops: [number, string][] = [
    [0, '#fef9c3'],
    [0.25, '#fde047'],
    [0.5, '#fb923c'],
    [0.75, '#ef4444'],
    [1, '#7f1d1d'],
  ]
  return rampColor(stops, t)
}

function rampColor(stops: [number, string][], t: number): string {
  let prev = stops[0]
  for (let i = 1; i < stops.length; i += 1) {
    const cur = stops[i]
    if (t <= cur[0]) {
      const u = (t - prev[0]) / Math.max(1e-6, cur[0] - prev[0])
      return lerpHex(prev[1], cur[1], u)
    }
    prev = cur
  }
  return stops[stops.length - 1][1]
}

function lerpHex(a: string, b: string, t: number): string {
  const pa = hexRgb(a)
  const pb = hexRgb(b)
  const r = Math.round(pa[0] + (pb[0] - pa[0]) * t)
  const g = Math.round(pa[1] + (pb[1] - pa[1]) * t)
  const bl = Math.round(pa[2] + (pb[2] - pa[2]) * t)
  return `#${[r, g, bl].map((c) => c.toString(16).padStart(2, '0')).join('')}`
}

function hexRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

export function hazardColor(hazard: HazardId, value: number): string {
  if (hazard === 'flood') return floodRiskColor(value)
  if (hazard === 'grid') return gridStressColor(value)
  // heat imported by caller to avoid circular deps — use dynamic
  return value < 60 ? '#93c5fd' : floodRiskColor(Math.min(100, (value - 60) * 2))
}

export function hazardGradientCss(hazard: HazardId): string {
  if (hazard === 'flood') {
    return 'linear-gradient(to right, #e0f2fe, #7dd3fc, #38bdf8, #0284c7, #0c4a6e)'
  }
  if (hazard === 'grid') {
    return 'linear-gradient(to right, #fef9c3, #fde047, #fb923c, #ef4444, #7f1d1d)'
  }
  return '' // heat uses heatIndexGradientCss
}

export function hazardUnit(hazard: HazardId): string {
  return hazard === 'heat' ? '°F' : ''
}

export function formatHazardValue(hazard: HazardId, value: number): string {
  if (hazard === 'heat') return `${value.toFixed(1)}°F`
  return `${value.toFixed(0)}`
}

export function hazardRiskLabel(hazard: HazardId, value: number): string {
  if (hazard === 'heat') {
    if (value < 80) return 'Comfortable'
    if (value < 90) return 'Caution'
    if (value < 100) return 'Elevated heat stress'
    if (value < 110) return 'High heat risk'
    return 'Extreme heat'
  }
  if (hazard === 'flood') {
    if (value < 25) return 'Low flood risk'
    if (value < 50) return 'Moderate flood risk'
    if (value < 75) return 'Elevated flood risk'
    return 'High flood risk'
  }
  if (value < 25) return 'Low grid stress'
  if (value < 50) return 'Moderate grid stress'
  if (value < 75) return 'Elevated grid stress'
  return 'High grid stress'
}

export const FLOOD_LEGEND_TICKS = [
  { label: '0' },
  { label: '25' },
  { label: '50' },
  { label: '75' },
  { label: '100' },
] as const

export const GRID_LEGEND_TICKS = FLOOD_LEGEND_TICKS
