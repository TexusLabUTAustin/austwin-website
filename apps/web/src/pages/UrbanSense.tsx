import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import AnomalyMap from '../components/AnomalyMap'
import AnomalySummary from '../components/AnomalySummary'
import {
  fetchAnomalies,
  fetchTractAnomaly,
  type AnomalyResponse,
  type TractAnomalyDetail,
} from '../lib/senseApi'
import {
  computeAnomalyInsights,
  formatFactorPct,
  severityColor,
  severityLabel,
} from '../lib/anomalyUtils'
import { formatTimestamp } from '../lib/forecastUtils'
import styles from './CityForesight.module.css'

export default function UrbanSenseDashboard() {
  const [data, setData] = useState<AnomalyResponse | null>(null)
  const [selectedTract, setSelectedTract] = useState<string | null>(null)
  const [tractDetail, setTractDetail] = useState<TractAnomalyDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchAnomalies()
      setData(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load anomalies')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!selectedTract) {
      setTractDetail(null)
      return
    }
    fetchTractAnomaly(selectedTract)
      .then(setTractDetail)
      .catch(() => setTractDetail(null))
  }, [selectedTract])

  const insights = useMemo(
    () => (data ? computeAnomalyInsights(data.features) : null),
    [data],
  )

  const anomaly = tractDetail?.anomaly

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link to="/one-pager" className={styles.backLink}>
          ← AusTwin
        </Link>
        <div className={styles.headerMain}>
          <h1 className={styles.title}>
            <span className={styles.titleAccent}>Urban</span>Sense
          </h1>
          <p className={styles.subtitle}>
            Heat anomaly detection across Austin census tracts — compares forecasts,
            live observations, and land-cover expectations.{' '}
            <Link to="/cityforesight">View forecasts →</Link>
          </p>
        </div>
      </header>

      {loading && <p className={styles.status}>Loading anomalies…</p>}
      {error && (
        <p className={styles.error}>
          {error}. Ensure UrbanSense (:8001) and CityForesight (:8000) are running.
        </p>
      )}

      {data && insights && (
        <div className={styles.dashboard}>
          <div className={styles.mapCard}>
            <AnomalySummary features={data.features} />

            <div className={styles.mapRow}>
              <AnomalyMap
                geojson={data.features}
                onTractSelect={setSelectedTract}
              />
              {tractDetail && anomaly ? (
                <aside className={styles.tractPanel} aria-label="Tract anomaly detail">
                  <button
                    type="button"
                    className={styles.tractClose}
                    onClick={() => setSelectedTract(null)}
                    aria-label="Close tract details"
                  >
                    ×
                  </button>
                  <h2>{tractDetail.name}</h2>
                  <div className={styles.tractHero}>
                    <span
                      className={styles.tractHeroValue}
                      style={{ color: severityColor(anomaly.severity) }}
                    >
                      {(anomaly.anomaly_score * 100).toFixed(0)}%
                    </span>
                    <span className={styles.tractHeroLabel}>
                      {severityLabel(anomaly.severity)} · +{anomaly.horizon}h
                    </span>
                  </div>

                  <p className={styles.insightLine}>
                    Forecast <strong>{anomaly.tract_forecast.toFixed(1)}°F</strong> vs city
                    median <strong>{anomaly.city_median.toFixed(1)}°F</strong>. Observed at
                    station: <strong>{anomaly.observed_heat_index.toFixed(1)}°F</strong>.
                  </p>

                  <div className={styles.morphGrid}>
                    <div className={styles.hintTitle}>Contributing factors</div>
                    <p className={styles.insightLine}>
                      Spatial {formatFactorPct(anomaly.factors.spatial)} · Temporal{' '}
                      {formatFactorPct(anomaly.factors.temporal)} · Morphology{' '}
                      {formatFactorPct(anomaly.factors.morphology)}
                    </p>
                  </div>

                  <details className={styles.insightLine}>
                    <summary>Ontology subgraph (JSON-LD)</summary>
                    <pre
                      style={{
                        fontSize: '0.65rem',
                        overflow: 'auto',
                        maxHeight: '120px',
                        background: '#f8fafc',
                        padding: '0.5rem',
                        borderRadius: '6px',
                      }}
                    >
                      {JSON.stringify(tractDetail.ontology, null, 2)}
                    </pre>
                  </details>
                </aside>
              ) : (
                <div className={styles.mapHint}>
                  <p className={styles.hintTitle}>Explore anomalies</p>
                  <p>Click a tract to see severity, contributing factors, and ontology context.</p>
                  <div className={styles.hintStats}>
                    <div>
                      <span className={styles.hintStatLabel}>Alert + extreme</span>
                      <span className={styles.hintStatValue}>
                        {insights.alert + insights.extreme} tracts
                      </span>
                    </div>
                    <div>
                      <span className={styles.hintStatLabel}>Peak score</span>
                      <span className={styles.hintStatValue}>
                        {(insights.maxScore * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <footer className={styles.meta}>
              {data.station} · CityForesight {data.cityforesight_model} · Updated{' '}
              {formatTimestamp(data.last_updated)}
            </footer>
          </div>
        </div>
      )}
    </div>
  )
}
