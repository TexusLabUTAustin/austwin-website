/** Heat index choropleth: static cool band below 60°F, smooth gradient above. */

const COOL_STATIC_MAX = 60
const COOL_STATIC_COLOR = '#93c5fd'

/** Control points (°F) — tighter spacing above 90°F for finer hot-range contrast. */
const COLOR_STOPS: { temp: number; hex: string }[] = [
  { temp: 60, hex: '#86efac' },
  { temp: 70, hex: '#4ade80' },
  { temp: 80, hex: '#bef264' },
  { temp: 85, hex: '#facc15' },
  { temp: 90, hex: '#fde047' },
  { temp: 95, hex: '#fb923c' },
  { temp: 100, hex: '#f97316' },
  { temp: 105, hex: '#f87171' },
  { temp: 110, hex: '#ef4444' },
  { temp: 115, hex: '#dc2626' },
  { temp: 120, hex: '#991b1b' },
]

function parseHex(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

function toHex(r: number, g: number, b: number): string {
  const clamp = (n: number) => Math.round(Math.max(0, Math.min(255, n)))
  return `#${[r, g, b].map((c) => clamp(c).toString(16).padStart(2, '0')).join('')}`
}

function lerpHex(a: string, b: string, t: number): string {
  const [ar, ag, ab] = parseHex(a)
  const [br, bg, bb] = parseHex(b)
  return toHex(ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t)
}

export function heatIndexColor(value: number): string {
  if (value < COOL_STATIC_MAX) return COOL_STATIC_COLOR

  const maxStop = COLOR_STOPS[COLOR_STOPS.length - 1]
  if (value >= maxStop.temp) return maxStop.hex

  for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
    const low = COLOR_STOPS[i]
    const high = COLOR_STOPS[i + 1]
    if (value >= low.temp && value < high.temp) {
      const t = (value - low.temp) / (high.temp - low.temp)
      return lerpHex(low.hex, high.hex, t)
    }
  }

  return maxStop.hex
}

/** CSS linear-gradient for the legend bar (flat cool band, then smooth hot ramp). */
export function heatIndexGradientCss(minDisplay = 55, maxTemp = 115): string {
  const range = maxTemp - minDisplay
  const coolEndPct = ((COOL_STATIC_MAX - minDisplay) / range) * 100
  const parts = [
    `${COOL_STATIC_COLOR} 0%`,
    `${COOL_STATIC_COLOR} ${coolEndPct.toFixed(1)}%`,
    ...COLOR_STOPS.filter((s) => s.temp <= maxTemp).map(({ temp, hex }) => {
      const pct = ((temp - minDisplay) / range) * 100
      return `${hex} ${pct.toFixed(1)}%`
    }),
  ]
  return `linear-gradient(to right, ${parts.join(', ')})`
}

export const HEAT_INDEX_LEGEND_TICKS = [
  { label: '<60°F', temp: 55 },
  { label: '60', temp: 60 },
  { label: '80', temp: 80 },
  { label: '90', temp: 90 },
  { label: '100', temp: 100 },
  { label: '110+', temp: 115 },
] as const

/** Compact "live" relative time, e.g. "just now", "3m ago", "1h ago". */
export function formatRelative(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000))
  if (secs < 45) return 'just now'
  const mins = Math.round(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}

export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    timeZone: 'America/Chicago',
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}
