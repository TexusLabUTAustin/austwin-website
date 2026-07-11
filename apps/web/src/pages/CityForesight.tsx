import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import AddressSearch from '../components/AddressSearch'
import ForecastLegend from '../components/ForecastLegend'
import ForecastMap, { type MapPin } from '../components/ForecastMap'
import ForecastGlobe from '../components/ForecastGlobe'
import CityGuideWidget from '../components/CityGuideWidget'
import ForecastSparkline from '../components/ForecastSparkline'
import ForecastSummary from '../components/ForecastSummary'
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
import { formatRelative, formatTimestamp, heatIndexColor } from '../lib/forecastUtils'
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

  // Live feed: silently re-poll the auto-refreshing forecast API. Only swaps
  // state when the backend actually produced a newer run, so the map, camera,
  // and current selection stay put between updates.
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
        /* transient network error — keep last good forecast */
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

  // Tick the "updated Xm ago" label without refetching.
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
    <div className={styles.page}>
      <header className={styles.header}>
        <Link to="/one-pager" className={styles.backLink}>
          ← AusTwin
        </Link>
        <div className={styles.headerMain}>
          <h1 className={styles.title}>
            <span className={styles.titleAccent}>City</span>Foresight
          </h1>
          <p className={styles.subtitle}>
            Heat index forecasts across Austin census tracts — compare city-wide
            patterns, pick a time horizon, and click a tract for local detail.
          </p>
        </div>
      </header>

      {loading && <p className={styles.status}>Loading forecast…</p>}
      {error && (
        <p className={styles.error}>
          {error}. Ensure the CityForesight API is running on port 8000.
        </p>
      )}

      {forecast && insights && (
        <div className={styles.dashboard}>
          <div className={styles.mapCard}>
            <ForecastSummary features={forecast.features} horizon={horizon} />

            <div className={styles.toolbar}>
              <AddressSearch onResolved={handleAddressResolved} disabled={loading} />
              <div className={styles.horizonGroup}>
                <span className={styles.toolbarLabel}>Forecast ahead</span>
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
              </div>
              <div className={styles.horizonGroup}>
                <span className={styles.toolbarLabel}>View</span>
                <div className={styles.horizonPills} role="group" aria-label="Map view mode">
                  <button
                    type="button"
                    className={`${styles.horizonPill} ${view === '2d' ? styles.horizonPillActive : ''}`}
                    onClick={() => setView('2d')}
                    aria-pressed={view === '2d'}
                  >
                    2D
                  </button>
                  <button
                    type="button"
                    className={`${styles.horizonPill} ${view === '3d' ? styles.horizonPillActive : ''}`}
                    onClick={() => setView('3d')}
                    aria-pressed={view === '3d'}
                  >
                    3D
                  </button>
                </div>
              </div>
              <ForecastLegend />
            </div>

            <div className={styles.mapRow}>
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
              {tractDetail && tractTrend ? (
                <aside className={styles.tractPanel} aria-label="Tract forecast detail">
                  <button
                    type="button"
                    className={styles.tractClose}
                    onClick={() => {
                      setSelectedTract(null)
                      setSearchPin(null)
                      setFromAddressSearch(false)
                      setSearchAddress(null)
                      setCoverageNote(null)
                    }}
                    aria-label="Close tract details"
                  >
                    ×
                  </button>
                  {fromAddressSearch && searchAddress && (
                    <p className={styles.panelAddress}>{searchAddress}</p>
                  )}
                  <h2>
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
                        +{horizon}h · {heatRiskLabel(selectedValue)}
                      </span>
                    </div>
                  )}

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

                  <ul className={styles.tractList}>
                    {Object.entries(tractDetail.forecasts).map(([h, v]) => (
                      <li
                        key={h}
                        className={Number(h) === horizon ? styles.tractListActive : ''}
                      >
                        <span>+{h}h</span>
                        <strong>{v.toFixed(1)}°F</strong>
                      </li>
                    ))}
                  </ul>
                </aside>
              ) : (
                <div className={styles.mapHint}>
                  <p className={styles.hintTitle}>Explore the map</p>
                  <p>Click any tract to see its forecast trend and land-cover context.</p>
                  <div className={styles.hintStats}>
                    <div>
                      <span className={styles.hintStatLabel}>Right now (+{horizon}h)</span>
                      <span className={styles.hintStatValue}>
                        {insights.average.toFixed(1)}°F avg
                      </span>
                    </div>
                    <div>
                      <span className={styles.hintStatLabel}>Hotspot</span>
                      <span className={styles.hintStatValue}>
                        {insights.hottest.name} · {insights.hottest.value.toFixed(1)}°F
                      </span>
                    </div>
                    <div>
                      <span className={styles.hintStatLabel}>At elevated risk</span>
                      <span className={styles.hintStatValue}>
                        {insights.elevated + insights.extreme} of {insights.total} tracts
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <footer className={styles.meta}>
              <span className={styles.liveBadge}>
                <span className={styles.liveDot} aria-hidden="true" />
                Live
              </span>
              Austin-Bergstrom ({forecast.station}) · updated{' '}
              {formatRelative(forecast.last_updated)}
              <span className={styles.metaMuted}>
                {' '}({formatTimestamp(forecast.last_updated)})
              </span>
            </footer>
          </div>
        </div>
      )}

      <CityGuideWidget />
    </div>
  )
}
