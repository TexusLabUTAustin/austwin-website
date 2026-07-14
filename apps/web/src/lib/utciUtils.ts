/** UTCI thermal comfort helpers — matches SOLWEIG tile colormap and stress bands. */

export type UtciBounds = {
  west: number
  south: number
  east: number
  north: number
}

export type UtciHotspot = {
  lat: number
  lon: number
  utci_c: number
  label?: string
}

export type UtciMeta = {
  bounds: UtciBounds
  range_c: [number, number]
  mean_c?: number
  spread_c?: number
  hotspot?: UtciHotspot
  coolest?: UtciHotspot
  date?: string
  hours?: number[]
  png_url?: string
  sample_available?: boolean
  stress_scale?: { max_c: number; label: string; color: string }[]
}

export type UtciSample = {
  lat: number
  lon: number
  utci_c: number
  stress: string
  stress_label: string
  range_c: [number, number]
  normalized: number
}

/** Colormap stops from build_tile._utci_colormap (blue → green → yellow → red). */
const COLOR_STOPS: [number, string][] = [
  [0, '#2b83ba'],
  [0.35, '#78c6a3'],
  [0.5, '#ffffbf'],
  [0.7, '#fdae61'],
  [1, '#d73027'],
]

export function utciLegendGradient(): string {
  const parts = COLOR_STOPS.map(([t, c]) => `${c} ${Math.round(t * 100)}%`)
  return `linear-gradient(to right, ${parts.join(', ')})`
}

export function utciValueColor(value: number, lo: number, hi: number): string {
  const t = Math.max(0, Math.min(1, (value - lo) / Math.max(hi - lo, 1e-3)))
  let prev = COLOR_STOPS[0]
  for (let i = 1; i < COLOR_STOPS.length; i += 1) {
    const cur = COLOR_STOPS[i]
    if (t <= cur[0]) {
      return lerpColor(prev[1], cur[1], (t - prev[0]) / (cur[0] - prev[0]))
    }
    prev = cur
  }
  return COLOR_STOPS[COLOR_STOPS.length - 1][1]
}

function lerpColor(a: string, b: string, t: number): string {
  const pa = hexToRgb(a)
  const pb = hexToRgb(b)
  const r = Math.round(pa.r + (pb.r - pa.r) * t)
  const g = Math.round(pa.g + (pb.g - pa.g) * t)
  const bl = Math.round(pa.b + (pb.b - pa.b) * t)
  return `rgb(${r}, ${g}, ${bl})`
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace('#', '')
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  }
}

export function inUtciBounds(lat: number, lon: number, bounds: UtciBounds): boolean {
  return (
    bounds.west <= lon &&
    lon <= bounds.east &&
    bounds.south <= lat &&
    lat <= bounds.north
  )
}

export function formatUtciHours(hours?: number[]): string {
  if (!hours?.length) return ''
  if (hours.length === 1) return `${hours[0]}:00`
  return `${hours[0]}:00–${hours[hours.length - 1]}:00`
}

export function utciInsightLine(meta: UtciMeta): string {
  const [lo, hi] = meta.range_c
  const spread = meta.spread_c ?? hi - lo
  return `UTCI ${lo.toFixed(1)}–${hi.toFixed(1)}°C · Δ${spread.toFixed(1)}°C shade`
}
