import { heatIndexColor } from '../lib/forecastUtils'
import styles from './ForecastSparkline.module.css'

type Props = {
  values: number[]
  horizons: number[]
  activeHorizon: number
}

export default function ForecastSparkline({ values, horizons, activeHorizon }: Props) {
  if (values.length < 2) return null

  const width = 200
  const height = 56
  const pad = 6
  const min = Math.min(...values) - 1
  const max = Math.max(...values) + 1
  const range = max - min || 1

  const points = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (width - pad * 2)
    const y = height - pad - ((v - min) / range) * (height - pad * 2)
    return { x, y, v, h: horizons[i] }
  })

  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
  const active = points.find((p) => p.h === activeHorizon)

  return (
    <div className={styles.wrap} aria-hidden>
      <svg viewBox={`0 0 ${width} ${height}`} className={styles.svg}>
        <defs>
          <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2a8fd4" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#2a8fd4" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d={`${path} L ${points[points.length - 1].x} ${height - pad} L ${points[0].x} ${height - pad} Z`}
          fill="url(#sparkGrad)"
        />
        <path d={path} fill="none" stroke="#2a8fd4" strokeWidth="2" strokeLinecap="round" />
        {points.map((p) => (
          <circle
            key={p.h}
            cx={p.x}
            cy={p.y}
            r={p.h === activeHorizon ? 4 : 2.5}
            fill={p.h === activeHorizon ? '#1a3c8f' : '#2a8fd4'}
            opacity={p.h === activeHorizon ? 1 : 0.6}
          />
        ))}
      </svg>
      <div className={styles.labels}>
        <span>{values[0].toFixed(0)}°F</span>
        <span style={{ color: active ? heatIndexColor(active.v) : undefined }}>
          {active?.v.toFixed(0)}°F @ +{activeHorizon}h
        </span>
        <span>{values[values.length - 1].toFixed(0)}°F</span>
      </div>
    </div>
  )
}
