import { useMemo } from 'react'
import type { FeatureCollection } from 'geojson'
import { computeAnomalyInsights } from '../lib/anomalyUtils'
import styles from './ForecastSummary.module.css'

type Props = {
  features: FeatureCollection
}

export default function AnomalySummary({ features }: Props) {
  const insights = useMemo(() => computeAnomalyInsights(features), [features])

  return (
    <section className={styles.summary} aria-label="Anomaly summary">
      <div className={styles.stat}>
        <span className={styles.statLabel}>Tracts monitored</span>
        <span className={styles.statValue}>{insights.total}</span>
        <span className={styles.statHint}>Travis County</span>
      </div>

      <div className={styles.stat}>
        <span className={styles.statLabel}>Watch</span>
        <span className={styles.statValue} style={{ color: '#f59e0b' }}>
          {insights.watch}
        </span>
        <span className={styles.statHint}>elevated deviation</span>
      </div>

      <div className={styles.stat}>
        <span className={styles.statLabel}>Alert</span>
        <span className={styles.statValue} style={{ color: '#dc2626' }}>
          {insights.alert}
        </span>
        <span className={styles.statHint}>significant anomaly</span>
      </div>

      <div className={styles.stat}>
        <span className={styles.statLabel}>Extreme</span>
        <span className={styles.statValue} style={{ color: '#7f1d1d' }}>
          {insights.extreme}
        </span>
        <span className={styles.statHint}>highest concern</span>
      </div>

      <div className={styles.riskBar}>
        <span className={styles.statLabel}>Severity distribution</span>
        <div className={styles.riskSegments}>
          {insights.total - insights.watch - insights.alert - insights.extreme > 0 && (
            <span
              className={styles.riskSegment}
              style={{
                flex: insights.total - insights.watch - insights.alert - insights.extreme,
                backgroundColor: '#86efac',
              }}
            />
          )}
          {insights.watch > 0 && (
            <span
              className={styles.riskSegment}
              style={{ flex: insights.watch, backgroundColor: '#f59e0b' }}
            />
          )}
          {insights.alert > 0 && (
            <span
              className={styles.riskSegment}
              style={{ flex: insights.alert, backgroundColor: '#dc2626' }}
            />
          )}
          {insights.extreme > 0 && (
            <span
              className={styles.riskSegment}
              style={{ flex: insights.extreme, backgroundColor: '#7f1d1d' }}
            />
          )}
        </div>
        {insights.hottest && (
          <div className={styles.riskLegend}>
            <span>
              Peak: {insights.hottest.name} ({(insights.hottest.score * 100).toFixed(0)}%)
            </span>
          </div>
        )}
      </div>
    </section>
  )
}
