import { useMemo } from 'react'
import type { FeatureCollection } from 'geojson'
import { computeHorizonInsights } from '../lib/forecastInsights'
import { heatIndexColor } from '../lib/forecastUtils'
import styles from './ForecastSummary.module.css'

type Props = {
  features: FeatureCollection
  horizon: number
}

export default function ForecastSummary({ features, horizon }: Props) {
  const insights = useMemo(
    () => computeHorizonInsights(features, horizon),
    [features, horizon],
  )

  return (
    <section className={styles.summary} aria-label="City-wide forecast summary">
      <div className={styles.stat}>
        <span className={styles.statLabel}>City average</span>
        <span className={styles.statValue}>{insights.average.toFixed(1)}°F</span>
        <span className={styles.statHint}>across {insights.total} tracts</span>
      </div>

      <div className={styles.stat}>
        <span className={styles.statLabel}>Hottest tract</span>
        <span
          className={styles.statValue}
          style={{ color: heatIndexColor(insights.hottest.value) }}
        >
          {insights.hottest.value.toFixed(1)}°F
        </span>
        <span className={styles.statHint}>{insights.hottest.name}</span>
      </div>

      <div className={styles.stat}>
        <span className={styles.statLabel}>Coolest tract</span>
        <span
          className={styles.statValue}
          style={{ color: heatIndexColor(insights.coolest.value) }}
        >
          {insights.coolest.value.toFixed(1)}°F
        </span>
        <span className={styles.statHint}>{insights.coolest.name}</span>
      </div>

      <div className={styles.stat}>
        <span className={styles.statLabel}>Urban spread</span>
        <span className={styles.statValue}>{insights.spread.toFixed(1)}°F</span>
        <span className={styles.statHint}>max − min across metro</span>
      </div>

      <div className={styles.riskBar} aria-label="Heat risk distribution">
        <span className={styles.statLabel}>Risk distribution (+{horizon}h)</span>
        <div className={styles.riskSegments}>
          {insights.comfortable > 0 && (
            <span
              className={styles.riskSegment}
              style={{ flex: insights.comfortable, backgroundColor: '#4ade80' }}
              title={`${insights.comfortable} tracts < 80°F`}
            />
          )}
          {insights.caution > 0 && (
            <span
              className={styles.riskSegment}
              style={{ flex: insights.caution, backgroundColor: '#facc15' }}
              title={`${insights.caution} tracts 80–90°F`}
            />
          )}
          {insights.elevated > 0 && (
            <span
              className={styles.riskSegment}
              style={{ flex: insights.elevated, backgroundColor: '#fb923c' }}
              title={`${insights.elevated} tracts 90–100°F`}
            />
          )}
          {insights.extreme > 0 && (
            <span
              className={styles.riskSegment}
              style={{ flex: insights.extreme, backgroundColor: '#dc2626' }}
              title={`${insights.extreme} tracts ≥ 100°F`}
            />
          )}
        </div>
        <div className={styles.riskLegend}>
          <span>{insights.comfortable} comfortable</span>
          <span>{insights.caution} caution</span>
          <span>{insights.elevated + insights.extreme} elevated+</span>
        </div>
      </div>
    </section>
  )
}
