import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import AddressSearch from '../components/AddressSearch'
import ForecastLegend from '../components/ForecastLegend'
import ForecastMap, { type MapPin } from '../components/ForecastMap'
import ForecastGlobe from '../components/ForecastGlobe'
import CityGuideWidget from '../components/CityGuideWidget'
import ForecastSparkline from '../components/ForecastSparkline'
import MorphMetric, { MorphSectionHint } from '../components/MorphMetric'
import {
  fetchCurrentForecast,
  fetchTractForecast,
  type AddressSearchResult,
  type ForecastResponse,
} from '../lib/api'
import {
  computeHorizonInsights,
  computeTractTrend,
  formatPercent,
  heatRiskLabel,
} from '../lib/forecastInsights'
import { formatRelative, heatIndexColor } from '../lib/forecastUtils'
import styles from './CityForesight.module.css'

export default function CityForesightDashboard() {
  const [forecast, setForecast] = useState<ForecastResponse | null>(null)
  const [horizon, setHorizon] = useState(1)
  const [selectedTract, setSelectedTract] = useState<string | null>(null)
  const [tractDetail, setTractDetail] = useState<{
    geoid: string
    name: string
    forecasts: Record<string, number>
    morphology?: {
      impervious_ratio: number
      canopy_cover: number
      drainage_capacity: number
      population_density: number
    }
  } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchPin, setSearchPin] = useState<MapPin | null>(null)
  const [fromAddressSearch, setFromAddressSearch] = useState(false)
  const [searchAddress, setSearchAddress] = useState<string | null>(null)
  const [coverageNote, setCoverageNote] = useState<string | null>(null)
  const [view, setView] = useState<'2d' | '3d'>('3d')
  const [, setClockTick] = useState(0)

  const handleTractSelect = useCallback((geoid: string) => {
    setFromAddressSearch(false)
    setSearchAddress(null)
    setCoverageNote(null)
    setSearchPin(null)
    setSelectedTract(geoid)
  }, [])

  const handleAddressResolved = useCallback((result: AddressSearchResult) => {
    setFromAddressSearch(true)
    setSearchAddress(result.matched_address)
    setCoverageNote(result.coverage_note)
    setSelectedTract(result.geoid)
    setTractDetail({
      geoid: result.geoid,
      name: result.name,
      forecasts: result.forecasts,
      morphology: result.morphology,
    })
    const hi = result.forecasts['1']
    setSearchPin({
      lat: result.lat,
      lon: result.lon,
      label: result.matched_address,
      heatIndex: hi,
    })
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedTract(null)
    setSearchPin(null)
    setFromAddressSearch(false)
    setSearchAddress(null)
    setCoverageNote(null)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const fc = await fetchCurrentForecast()
      setForecast(fc)
      if (fc.horizons.length) setHorizon(fc.horizons[0])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load forecast')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const POLL_MS = 120_000
    let cancelled = false
    const refresh = async () => {
      try {
        const fc = await fetchCurrentForecast()
        if (cancelled) return
        setForecast((prev) =>
          prev && prev.last_updated === fc.last_updated ? prev : fc,
        )
      } catch {
        /* keep last good forecast */
      }
    }
    const timer = window.setInterval(refresh, POLL_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  useEffect(() => {
    const id = window.setInterval(() => setClockTick((t) => t + 1), 30_000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    if (!selectedTract) {
      setTractDetail(null)
      return
    }
    if (fromAddressSearch) return
    fetchTractForecast(selectedTract)
      .then((d) =>
        setTractDetail({
          geoid: d.geoid,
          name: d.name,
          forecasts: d.forecasts,
          morphology: d.morphology,
        }),
      )
      .catch(() => setTractDetail(null))
  }, [selectedTract, fromAddressSearch])

  useEffect(() => {
    if (!searchPin || !tractDetail) return
    const hi = tractDetail.forecasts[String(horizon)]
    if (hi === undefined) return
    setSearchPin((prev) =>
      prev ? { ...prev, heatIndex: hi } : prev,
    )
  }, [horizon, tractDetail, searchPin?.lat, searchPin?.lon])

  const insights = useMemo(
    () =>
      forecast
        ? computeHorizonInsights(forecast.features, horizon)
        : null,
    [forecast, horizon],
  )

  const tractTrend = useMemo(() => {
    if (!tractDetail || !forecast || !insights) return null
    return computeTractTrend(
      tractDetail.forecasts,
      forecast.horizons,
      insights.average,
    )
  }, [tractDetail, forecast, insights])

  const selectedValue = tractDetail?.forecasts[String(horizon)]

  return (
    <div className={styles.shell}>
      <header className={styles.topBar}>
        <div className={styles.topBrand}>
          <Link to="/one-pager" className={styles.backLink}>
            ←
          </Link>
          <h1 className={styles.title}>
            <span className={styles.titleAccent}>City</span>Foresight
          </h1>
          {forecast && (
            <span className={styles.topMeta}>
              {forecast.station} · {formatRelative(forecast.last_updated)}
            </span>
          )}
        </div>

        {forecast && (
          <div className={styles.topControls}>
            <AddressSearch
              onResolved={handleAddressResolved}
              disabled={loading}
              compact
            />
            <div className={styles.horizonPills} role="group" aria-label="Forecast horizon">
              {forecast.horizons.map((h) => (
                <button
                  key={h}
                  type="button"
                  className={`${styles.horizonPill} ${horizon === h ? styles.horizonPillActive : ''}`}
                  onClick={() => setHorizon(h)}
                  aria-pressed={horizon === h}
                >
                  +{h}h
                </button>
              ))}
            </div>
            <div className={styles.viewToggle} role="group" aria-label="Map view mode">
              <button
                type="button"
                className={`${styles.viewBtn} ${view === '2d' ? styles.viewBtnActive : ''}`}
                onClick={() => setView('2d')}
                aria-pressed={view === '2d'}
              >
                2D
              </button>
              <button
                type="button"
                className={`${styles.viewBtn} ${view === '3d' ? styles.viewBtnActive : ''}`}
                onClick={() => setView('3d')}
                aria-pressed={view === '3d'}
              >
                3D
              </button>
            </div>
          </div>
        )}

        <CityGuideWidget placement="header" />
      </header>

      {loading && <p className={styles.status}>Loading forecast…</p>}
      {error && (
        <p className={styles.error}>
          {error}. Ensure the CityForesight API is running (default port 8010).
        </p>
      )}

      {forecast && insights && (
        <div className={styles.workspace}>
          <div className={styles.mapStage}>
            {view === '3d' ? (
              <ForecastGlobe
                geojson={forecast.features}
                horizon={horizon}
                onTractSelect={handleTractSelect}
                pin={searchPin}
              />
            ) : (
              <ForecastMap
                geojson={forecast.features}
                horizon={horizon}
                onTractSelect={handleTractSelect}
                pin={searchPin}
              />
            )}
            <div className={styles.mapLegend}>
              <ForecastLegend />
            </div>
          </div>

          {tractDetail && tractTrend ? (
            <aside className={styles.sidePanel} aria-label="Tract forecast detail">
              <div className={styles.sidePanelHead}>
                <span className={styles.sidePanelKicker}>
                  {fromAddressSearch ? 'Your area' : 'Selected tract'}
                </span>
                <button
                  type="button"
                  className={styles.tractClose}
                  onClick={clearSelection}
                  aria-label="Close tract details"
                >
                  ×
                </button>
              </div>

              {fromAddressSearch && searchAddress && (
                <p className={styles.panelAddress}>{searchAddress}</p>
              )}
              <h2 className={styles.sidePanelTitle}>
                {fromAddressSearch
                  ? `You're in ${tractDetail.name}`
                  : tractDetail.name}
              </h2>
              {fromAddressSearch && coverageNote && (
                <p className={styles.panelDisclaimer}>{coverageNote}</p>
              )}

              {selectedValue !== undefined && (
                <div className={styles.tractHero}>
                  <span
                    className={styles.tractHeroValue}
                    style={{ color: heatIndexColor(selectedValue) }}
                  >
                    {selectedValue.toFixed(1)}°F
                  </span>
                  <span className={styles.tractHeroLabel}>
                    Heat index · +{horizon}h · {heatRiskLabel(selectedValue)}
                  </span>
                </div>
              )}

              <div className={styles.insightBlock}>
                <p className={styles.insightLine}>
                  {tractTrend.direction === 'falling' && (
                    <>
                      Cooling <strong>{Math.abs(tractTrend.delta).toFixed(1)}°F</strong>{' '}
                      over the next {forecast.horizons[forecast.horizons.length - 1]} hours.
                    </>
                  )}
                  {tractTrend.direction === 'rising' && (
                    <>
                      Warming <strong>{tractTrend.delta.toFixed(1)}°F</strong> over the
                      next {forecast.horizons[forecast.horizons.length - 1]} hours.
                    </>
                  )}
                  {tractTrend.direction === 'steady' && (
                    <>Heat index holds steady across the forecast window.</>
                  )}
                </p>
                <p className={styles.insightLine}>
                  {tractTrend.vsCityAvg > 0.5 && (
                    <>
                      <strong>{tractTrend.vsCityAvg.toFixed(1)}°F hotter</strong> than the
                      city average at this horizon.
                    </>
                  )}
                  {tractTrend.vsCityAvg < -0.5 && (
                    <>
                      <strong>{Math.abs(tractTrend.vsCityAvg).toFixed(1)}°F cooler</strong>{' '}
                      than the city average at this horizon.
                    </>
                  )}
                  {Math.abs(tractTrend.vsCityAvg) <= 0.5 && (
                    <>Near the city-wide average for this horizon.</>
                  )}
                </p>
              </div>

              <ForecastSparkline
                values={tractTrend.values}
                horizons={tractTrend.horizons}
                activeHorizon={horizon}
              />

              {tractDetail.morphology && (
                <div className={styles.morphGrid}>
                  <MorphSectionHint />
                  <MorphMetric
                    label="Impervious"
                    value={formatPercent(tractDetail.morphology.impervious_ratio)}
                    metric="impervious"
                  />
                  <MorphMetric
                    label="Tree canopy"
                    value={formatPercent(tractDetail.morphology.canopy_cover)}
                    metric="canopy"
                  />
                  <MorphMetric
                    label="Drainage"
                    value={formatPercent(tractDetail.morphology.drainage_capacity)}
                    metric="drainage"
                  />
                </div>
              )}

              <div className={styles.horizonTable}>
                <span className={styles.toolbarLabel}>All horizons</span>
                <ul className={styles.tractList}>
                  {Object.entries(tractDetail.forecasts).map(([h, v]) => (
                    <li
                      key={h}
                      className={Number(h) === horizon ? styles.tractListActive : ''}
                    >
                      <button
                        type="button"
                        className={styles.tractListBtn}
                        onClick={() => setHorizon(Number(h))}
                      >
                        <span>+{h}h</span>
                        <strong>{v.toFixed(1)}°F</strong>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </aside>
          ) : (
            <aside className={styles.sidePanel} aria-label="City overview">
              <span className={styles.sidePanelKicker}>City overview · +{horizon}h</span>
              <h2 className={styles.sidePanelTitle}>Austin heat right now</h2>
              <p className={styles.guideLead}>
                Search an address or click a tract on the map.
              </p>

              <div className={styles.cityStats}>
                <div className={styles.cityStat}>
                  <span className={styles.hintStatLabel}>Average</span>
                  <span className={styles.cityStatValue}>
                    {insights.average.toFixed(1)}°F
                  </span>
                </div>
                <div className={styles.cityStat}>
                  <span className={styles.hintStatLabel}>Hottest</span>
                  <span
                    className={styles.cityStatValue}
                    style={{ color: heatIndexColor(insights.hottest.value) }}
                  >
                    {insights.hottest.value.toFixed(1)}°F
                  </span>
                  <span className={styles.hintStatSub}>{insights.hottest.name}</span>
                </div>
                <div className={styles.cityStat}>
                  <span className={styles.hintStatLabel}>Coolest</span>
                  <span
                    className={styles.cityStatValue}
                    style={{ color: heatIndexColor(insights.coolest.value) }}
                  >
                    {insights.coolest.value.toFixed(1)}°F
                  </span>
                  <span className={styles.hintStatSub}>{insights.coolest.name}</span>
                </div>
                <div className={styles.cityStat}>
                  <span className={styles.hintStatLabel}>Elevated risk</span>
                  <span className={styles.cityStatValue}>
                    {insights.elevated + insights.extreme}
                    <span className={styles.cityStatOf}> / {insights.total}</span>
                  </span>
                </div>
              </div>

              <div className={styles.riskMini} aria-label="Heat risk distribution">
                <div className={styles.riskSegments}>
                  {insights.comfortable > 0 && (
                    <span
                      className={styles.riskSegment}
                      style={{ flex: insights.comfortable, backgroundColor: '#4ade80' }}
                      title={`${insights.comfortable} comfortable`}
                    />
                  )}
                  {insights.caution > 0 && (
                    <span
                      className={styles.riskSegment}
                      style={{ flex: insights.caution, backgroundColor: '#facc15' }}
                      title={`${insights.caution} caution`}
                    />
                  )}
                  {insights.elevated > 0 && (
                    <span
                      className={styles.riskSegment}
                      style={{ flex: insights.elevated, backgroundColor: '#fb923c' }}
                      title={`${insights.elevated} elevated`}
                    />
                  )}
                  {insights.extreme > 0 && (
                    <span
                      className={styles.riskSegment}
                      style={{ flex: insights.extreme, backgroundColor: '#dc2626' }}
                      title={`${insights.extreme} extreme`}
                    />
                  )}
                </div>
                <div className={styles.riskLegend}>
                  <span>{insights.comfortable} ok</span>
                  <span>{insights.caution} caution</span>
                  <span>{insights.elevated + insights.extreme} elevated+</span>
                </div>
              </div>

              <p className={styles.guideHint}>
                {view === '3d'
                  ? 'In 3D: pause (⏸) to zoom. Live layers → UTCI for street comfort.'
                  : 'Warm colors = higher heat index.'}
              </p>

              <Link to="/urbansense" className={styles.guideLink}>
                Check anomalies in UrbanSense →
              </Link>
            </aside>
          )}
        </div>
      )}
    </div>
  )
}
