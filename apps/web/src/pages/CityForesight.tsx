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
  type TractForecastDetail,
} from '../lib/api'
import {
  computeHorizonInsights,
  computeTractTrend,
  formatPercent,
  hazardMapColor,
} from '../lib/forecastInsights'
import { formatRelative } from '../lib/forecastUtils'
import {
  formatHazardValue,
  getHazardConfidence,
  getHazardForecasts,
  HAZARD_CUE,
  HAZARD_EXPLAIN,
  HAZARD_OPTIONS,
  hazardRiskLabel,
  type HazardId,
} from '../lib/hazardUtils'
import styles from './CityForesight.module.css'

export default function CityForesightDashboard() {
  const [forecast, setForecast] = useState<ForecastResponse | null>(null)
  const [horizon, setHorizon] = useState(1)
  const [hazard, setHazard] = useState<HazardId>('heat')
  const [selectedTract, setSelectedTract] = useState<string | null>(null)
  const [tractDetail, setTractDetail] = useState<TractForecastDetail | null>(null)
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
      flood_forecasts: result.flood_forecasts,
      grid_forecasts: result.grid_forecasts,
      confidence: result.confidence,
      anomaly_severity: result.anomaly_severity,
      anomaly_score: result.anomaly_score,
      morphology: result.morphology,
      last_updated: result.last_updated,
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
      .then(setTractDetail)
      .catch(() => setTractDetail(null))
  }, [selectedTract, fromAddressSearch])

  useEffect(() => {
    if (!searchPin || !tractDetail) return
    const hi = tractDetail.forecasts[String(horizon)]
    if (hi === undefined) return
    setSearchPin((prev) => (prev ? { ...prev, heatIndex: hi } : prev))
  }, [horizon, tractDetail, searchPin?.lat, searchPin?.lon])

  const insights = useMemo(
    () =>
      forecast
        ? computeHorizonInsights(forecast.features, horizon, hazard)
        : null,
    [forecast, horizon, hazard],
  )

  const activeForecasts = useMemo(() => {
    if (!tractDetail) return null
    const props = {
      forecasts: tractDetail.forecasts,
      flood_forecasts: tractDetail.flood_forecasts,
      grid_forecasts: tractDetail.grid_forecasts,
    }
    return getHazardForecasts(props, hazard)
  }, [tractDetail, hazard])

  const tractTrend = useMemo(() => {
    if (!activeForecasts || !forecast || !insights) return null
    return computeTractTrend(activeForecasts, forecast.horizons, insights.average)
  }, [activeForecasts, forecast, insights])

  const selectedValue = activeForecasts?.[String(horizon)]
  const selectedConfidence =
    tractDetail &&
    getHazardConfidence(
      { confidence: tractDetail.confidence } as Record<string, unknown>,
      hazard,
      horizon,
    )

  const trendNoun =
    hazard === 'heat' ? 'Heat index' : hazard === 'flood' ? 'Flood risk' : 'Grid stress'
  const trendUnit = hazard === 'heat' ? '°F' : ' pts'

  const heatInsights = useMemo(
    () =>
      forecast ? computeHorizonInsights(forecast.features, horizon, 'heat') : null,
    [forecast, horizon],
  )
  const floodInsights = useMemo(
    () =>
      forecast ? computeHorizonInsights(forecast.features, horizon, 'flood') : null,
    [forecast, horizon],
  )
  const gridInsights = useMemo(
    () =>
      forecast ? computeHorizonInsights(forecast.features, horizon, 'grid') : null,
    [forecast, horizon],
  )

  const jumpToHottest = () => {
    if (!insights?.hottest?.geoid) return
    handleTractSelect(insights.hottest.geoid)
  }

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
            <div className={styles.viewToggle} role="group" aria-label="Hazard layer">
              {HAZARD_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={`${styles.viewBtn} ${hazard === opt.id ? styles.viewBtnActive : ''}`}
                  onClick={() => setHazard(opt.id)}
                  aria-pressed={hazard === opt.id}
                >
                  {opt.short}
                </button>
              ))}
            </div>
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

      {forecast && insights && heatInsights && floodInsights && gridInsights && (
        <>
          <section className={styles.insightsStrip} aria-label="City insights">
            <button
              type="button"
              className={`${styles.insightCard} ${hazard === 'heat' ? styles.insightCardActive : ''}`}
              onClick={() => setHazard('heat')}
            >
              <span className={styles.insightCardLabel}>Heat avg · +{horizon}h</span>
              <span
                className={styles.insightCardValue}
                style={{ color: hazardMapColor('heat', heatInsights.average) }}
              >
                {formatHazardValue('heat', heatInsights.average)}
              </span>
              <span className={styles.insightCardMeta}>
                Peak {heatInsights.hottest.name.split(' ').slice(0, 3).join(' ')}
              </span>
            </button>
            <button
              type="button"
              className={`${styles.insightCard} ${hazard === 'flood' ? styles.insightCardActive : ''}`}
              onClick={() => setHazard('flood')}
            >
              <span className={styles.insightCardLabel}>Flood avg · +{horizon}h</span>
              <span
                className={styles.insightCardValue}
                style={{ color: hazardMapColor('flood', floodInsights.average) }}
              >
                {formatHazardValue('flood', floodInsights.average)}
              </span>
              <span className={styles.insightCardMeta}>
                {forecast.inputs?.usgs_gauge_count ?? 0} USGS gauges
              </span>
            </button>
            <button
              type="button"
              className={`${styles.insightCard} ${hazard === 'grid' ? styles.insightCardActive : ''}`}
              onClick={() => setHazard('grid')}
            >
              <span className={styles.insightCardLabel}>Grid avg · +{horizon}h</span>
              <span
                className={styles.insightCardValue}
                style={{ color: hazardMapColor('grid', gridInsights.average) }}
              >
                {formatHazardValue('grid', gridInsights.average)}
              </span>
              <span className={styles.insightCardMeta}>
                {forecast.inputs?.ercot_demand_mw != null
                  ? `ERCOT ${(forecast.inputs.ercot_demand_mw / 1000).toFixed(1)} GW`
                  : 'ERCOT pending'}
              </span>
            </button>
            <div className={styles.insightCardWide}>
              <span className={styles.insightCardLabel}>Live feeds</span>
              <p className={styles.liveFeedLine}>
                Rain {(forecast.inputs?.precip_in_6h ?? forecast.inputs?.precip_in_3h)?.toFixed(2) ?? '—'}″ / 6h
                {forecast.inputs?.ercot_utilization_pct != null &&
                  ` · Grid ${forecast.inputs.ercot_utilization_pct.toFixed(0)}% utilized`}
                {forecast.inputs?.usgs_city_flood_factor != null &&
                  ` · Stream stress ${(forecast.inputs.usgs_city_flood_factor * 100).toFixed(0)}%`}
              </p>
              <button type="button" className={styles.hotspotBtn} onClick={jumpToHottest}>
                Jump to hottest {hazard} tract →
              </button>
            </div>
          </section>

          <div className={styles.explainRow}>
            <p className={styles.mapCue}>{HAZARD_CUE[hazard]}</p>
            <details className={styles.explainDetails}>
              <summary>What does this score mean?</summary>
              <p>{HAZARD_EXPLAIN[hazard]}</p>
              {hazard === 'flood' && forecast.inputs?.usgs_top_gauges?.length ? (
                <ul className={styles.gaugeList}>
                  {forecast.inputs.usgs_top_gauges.slice(0, 3).map((g) => (
                    <li key={g.site}>
                      {g.name?.replace(', TX', '')}:{' '}
                      {g.gage_height_ft != null ? `${g.gage_height_ft.toFixed(1)} ft` : '—'}
                      {g.discharge_cfs != null ? ` · ${g.discharge_cfs.toFixed(0)} cfs` : ''}
                    </li>
                  ))}
                </ul>
              ) : null}
              {hazard === 'grid' && forecast.inputs?.ercot_demand_mw != null ? (
                <p className={styles.explainMeta}>
                  Demand {forecast.inputs.ercot_demand_mw.toLocaleString()} MW / capacity{' '}
                  {forecast.inputs.ercot_capacity_mw?.toLocaleString() ?? '—'} MW
                  {forecast.inputs.ercot_timestamp ? ` · ${forecast.inputs.ercot_timestamp}` : ''}
                </p>
              ) : null}
            </details>
          </div>

          <div className={styles.workspace}>
            <div className={styles.mapStage}>
              {view === '3d' ? (
                <ForecastGlobe
                  geojson={forecast.features}
                  horizon={horizon}
                  hazard={hazard}
                  onTractSelect={handleTractSelect}
                  pin={searchPin}
                />
              ) : (
                <ForecastMap
                  geojson={forecast.features}
                  horizon={horizon}
                  hazard={hazard}
                  onTractSelect={handleTractSelect}
                  pin={searchPin}
                />
              )}
              <div className={styles.mapLegend}>
                <ForecastLegend hazard={hazard} />
              </div>
            </div>

            {tractDetail && tractTrend && activeForecasts ? (
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
                <p className={styles.scoreExplain}>{HAZARD_EXPLAIN[hazard]}</p>

                {tractDetail.anomaly_severity &&
                  tractDetail.anomaly_severity !== 'normal' && (
                    <span
                      className={`${styles.anomalyPill} ${
                        tractDetail.anomaly_severity === 'watch'
                          ? styles.anom_watch
                          : tractDetail.anomaly_severity === 'extreme'
                            ? styles.anom_extreme
                            : styles.anom_alert
                      }`}
                    >
                      Anomaly · {tractDetail.anomaly_severity}
                      {tractDetail.anomaly_score != null
                        ? ` · ${(tractDetail.anomaly_score * 100).toFixed(0)}%`
                        : ''}
                    </span>
                  )}

                {selectedValue !== undefined && (
                  <div className={styles.tractHero}>
                    <span
                      className={styles.tractHeroValue}
                      style={{ color: hazardMapColor(hazard, selectedValue) }}
                    >
                      {formatHazardValue(hazard, selectedValue)}
                    </span>
                    <span className={styles.tractHeroLabel}>
                      {trendNoun} · +{horizon}h · {hazardRiskLabel(hazard, selectedValue)}
                    </span>
                    {selectedConfidence != null && (
                      <div className={styles.confMeter} aria-label="Forecast confidence">
                        <div className={styles.confTrack}>
                          <div
                            className={styles.confFill}
                            style={{ width: `${Math.round(selectedConfidence * 100)}%` }}
                          />
                        </div>
                        <span className={styles.confLabel}>
                          Confidence {Math.round(selectedConfidence * 100)}%
                        </span>
                      </div>
                    )}
                  </div>
                )}

                <div className={styles.insightBlock}>
                  <p className={styles.insightLine}>
                    {tractTrend.direction === 'falling' && (
                      <>
                        Falling{' '}
                        <strong>
                          {Math.abs(tractTrend.delta).toFixed(hazard === 'heat' ? 1 : 0)}
                          {trendUnit}
                        </strong>{' '}
                        over the next {forecast.horizons[forecast.horizons.length - 1]} hours.
                      </>
                    )}
                    {tractTrend.direction === 'rising' && (
                      <>
                        Rising{' '}
                        <strong>
                          {tractTrend.delta.toFixed(hazard === 'heat' ? 1 : 0)}
                          {trendUnit}
                        </strong>{' '}
                        over the next {forecast.horizons[forecast.horizons.length - 1]} hours.
                      </>
                    )}
                    {tractTrend.direction === 'steady' && (
                      <>Holds steady across the forecast window.</>
                    )}
                  </p>
                  <p className={styles.insightLine}>
                    {Math.abs(tractTrend.vsCityAvg) > (hazard === 'heat' ? 0.5 : 3) ? (
                      <>
                        <strong>
                          {Math.abs(tractTrend.vsCityAvg).toFixed(hazard === 'heat' ? 1 : 0)}
                          {trendUnit} {tractTrend.vsCityAvg > 0 ? 'above' : 'below'}
                        </strong>{' '}
                        the city average at this horizon.
                      </>
                    ) : (
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
                    {Object.entries(activeForecasts).map(([h, v]) => (
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
                          <strong>{formatHazardValue(hazard, v)}</strong>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              </aside>
            ) : (
              <aside className={styles.sidePanel} aria-label="City overview">
                <span className={styles.sidePanelKicker}>
                  City overview · {hazard} · +{horizon}h
                </span>
                <h2 className={styles.sidePanelTitle}>
                  {hazard === 'heat'
                    ? 'Austin heat right now'
                    : hazard === 'flood'
                      ? 'Flood-risk outlook'
                      : 'Grid-stress outlook'}
                </h2>
                <p className={styles.scoreExplain}>{HAZARD_EXPLAIN[hazard]}</p>
                <p className={styles.guideLead}>
                  Click a snapshot card above, search an address, or click a tract on the map.
                </p>

                <div className={styles.cityStats}>
                  <div className={styles.cityStat}>
                    <span className={styles.hintStatLabel}>Average</span>
                    <span className={styles.cityStatValue}>
                      {formatHazardValue(hazard, insights.average)}
                    </span>
                  </div>
                  <div className={styles.cityStat}>
                    <span className={styles.hintStatLabel}>Highest</span>
                    <span
                      className={styles.cityStatValue}
                      style={{ color: hazardMapColor(hazard, insights.hottest.value) }}
                    >
                      {formatHazardValue(hazard, insights.hottest.value)}
                    </span>
                    <span className={styles.hintStatSub}>{insights.hottest.name}</span>
                  </div>
                  <div className={styles.cityStat}>
                    <span className={styles.hintStatLabel}>Lowest</span>
                    <span
                      className={styles.cityStatValue}
                      style={{ color: hazardMapColor(hazard, insights.coolest.value) }}
                    >
                      {formatHazardValue(hazard, insights.coolest.value)}
                    </span>
                    <span className={styles.hintStatSub}>{insights.coolest.name}</span>
                  </div>
                  <div className={styles.cityStat}>
                    <span className={styles.hintStatLabel}>Elevated+</span>
                    <span className={styles.cityStatValue}>
                      {insights.elevated + insights.extreme}
                      <span className={styles.cityStatOf}> / {insights.total}</span>
                    </span>
                  </div>
                </div>

                <button type="button" className={styles.hotspotBtn} onClick={jumpToHottest}>
                  Open highest {hazard} tract
                </button>

                <Link to="/urbansense" className={styles.guideLink}>
                  Check anomalies in UrbanSense →
                </Link>
              </aside>
            )}
          </div>
        </>
      )}
    </div>
  )
}

