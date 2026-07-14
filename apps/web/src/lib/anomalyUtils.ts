export type Severity = 'normal' | 'watch' | 'alert' | 'extreme'

export function severityColor(severity: string): string {
  switch (severity) {
    case 'extreme':
      return '#7f1d1d'
    case 'alert':
      return '#dc2626'
    case 'watch':
      return '#f59e0b'
    default:
      return '#22c55e'
  }
}

export function severityLabel(severity: string): string {
  switch (severity) {
    case 'extreme':
      return 'Extreme anomaly'
    case 'alert':
      return 'Alert'
    case 'watch':
      return 'Watch'
    default:
      return 'Normal'
  }
}

export function scoreColor(score: number): string {
  if (score >= 0.62) return '#7f1d1d'
  if (score >= 0.42) return '#dc2626'
  if (score >= 0.28) return '#f59e0b'
  return '#86efac'
}

export type AnomalyInsights = {
  total: number
  watch: number
  alert: number
  extreme: number
  maxScore: number
  hottest?: { geoid: string; name: string; score: number }
}

export function computeAnomalyInsights(
  features: import('geojson').FeatureCollection,
): AnomalyInsights {
  const rows = features.features.map((f) => {
    const p = f.properties ?? {}
    return {
      geoid: String(p.GEOID ?? ''),
      name: String(p.NAME ?? p.GEOID ?? 'Tract'),
      score: Number(p.anomaly_score ?? 0),
      severity: String(p.severity ?? 'normal'),
    }
  })
  const hottest = rows.reduce(
    (best, r) => (r.score > best.score ? r : best),
    rows[0] ?? { geoid: '', name: '', score: 0 },
  )
  return {
    total: rows.length,
    watch: rows.filter((r) => r.severity === 'watch').length,
    alert: rows.filter((r) => r.severity === 'alert').length,
    extreme: rows.filter((r) => r.severity === 'extreme').length,
    maxScore: Math.max(...rows.map((r) => r.score), 0),
    hottest: hottest.score > 0 ? hottest : undefined,
  }
}

export function formatFactorPct(value: number): string {
  return `${(value * 100).toFixed(0)}%`
}
