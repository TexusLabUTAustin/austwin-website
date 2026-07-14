import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as Cesium from 'cesium'
import type { FeatureCollection } from 'geojson'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import { hazardMapColor } from '../lib/forecastInsights'
import {
  formatHazardValue,
  getHazardValue,
  type HazardId,
} from '../lib/hazardUtils'
import { fetchUtciMeta, sampleUtciAt } from '../lib/thermalApi'
import { inUtciBounds, utciInsightLine, type UtciMeta, type UtciSample } from '../lib/utciUtils'
import type { MapPin } from './ForecastMap'
import UtciInsightPanel from './UtciInsightPanel'
import {
  fetchCameras,
  makeGoesLayer,
  makeRadarLayer,
  makeTrafficLayer,
  makeUtciLayer,
  type CameraPoint,
} from './liveLayers'
import styles from './ForecastMap.module.css'

const TOMTOM_KEY = import.meta.env.VITE_TOMTOM_KEY as string | undefined

const ION_TOKEN = import.meta.env.VITE_CESIUM_ION_TOKEN as string | undefined
if (ION_TOKEN) Cesium.Ion.defaultAccessToken = ION_TOKEN

const AUSTIN_LON = -97.74
const AUSTIN_LAT = 30.27
const PITCH_TILTED = Cesium.Math.toRadians(-55)
const PITCH_TOP = Cesium.Math.toRadians(-89.9)

function cesiumColor(hex: string, alpha = 0.62): Cesium.Color {
  return Cesium.Color.fromCssColorString(hex).withAlpha(alpha)
}

/** Bounding sphere of the tract collection — the anchor for all camera moves. */
function boundsSphere(geojson: FeatureCollection): Cesium.BoundingSphere {
  let minLon = 180
  let minLat = 90
  let maxLon = -180
  let maxLat = -90
  const walk = (coords: unknown): void => {
    if (Array.isArray(coords) && typeof coords[0] === 'number') {
      const [lon, lat] = coords as number[]
      minLon = Math.min(minLon, lon)
      maxLon = Math.max(maxLon, lon)
      minLat = Math.min(minLat, lat)
      maxLat = Math.max(maxLat, lat)
    } else if (Array.isArray(coords)) {
      coords.forEach(walk)
    }
  }
  for (const f of geojson.features) {
    if (f.geometry && 'coordinates' in f.geometry) walk(f.geometry.coordinates)
  }
  if (minLon > maxLon) {
    return new Cesium.BoundingSphere(
      Cesium.Cartesian3.fromDegrees(AUSTIN_LON, AUSTIN_LAT),
      20000,
    )
  }
  const pts = Cesium.Cartesian3.fromDegreesArray([
    minLon, minLat, maxLon, minLat, maxLon, maxLat, minLon, maxLat,
  ])
  return Cesium.BoundingSphere.fromPoints(pts)
}

type Props = {
  geojson: FeatureCollection
  horizon: number
  hazard?: HazardId
  onTractSelect?: (geoid: string) => void
  pin?: MapPin | null
}

export default function ForecastGlobe({
  geojson,
  horizon,
  hazard = 'heat',
  onTractSelect,
  pin,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<Cesium.Viewer | null>(null)
  const dataSourceRef = useRef<Cesium.GeoJsonDataSource | null>(null)
  const pinEntityRef = useRef<Cesium.Entity | null>(null)
  const sphereRef = useRef<Cesium.BoundingSphere | null>(null)
  const framedRef = useRef(false)
  const osmBuildingsRef = useRef<Cesium.Cesium3DTileset | null>(null)

  // Live "drone" mode: continuous aerial orbit over the twin.
  const [drone, setDrone] = useState(true)
  const droneRef = useRef(true)
  const droneHeadingRef = useRef(0)
  const droneLockedRef = useRef(false)
  droneRef.current = drone

  const [clock, setClock] = useState('')

  // Real-time "city now" overlays.
  const [live, setLive] = useState({
    radar: false, goes: false, traffic: false, cams: false, utci: false,
  })
  const radarLayerRef = useRef<Cesium.ImageryLayer | null>(null)
  const goesLayerRef = useRef<Cesium.ImageryLayer | null>(null)
  const trafficLayerRef = useRef<Cesium.ImageryLayer | null>(null)
  const utciLayerRef = useRef<Cesium.ImageryLayer | null>(null)
  const utciSampleEntityRef = useRef<Cesium.Entity | null>(null)
  const camsDsRef = useRef<Cesium.CustomDataSource | null>(null)
  const camByEntityRef = useRef<Map<string, CameraPoint>>(new Map())
  const [activeCam, setActiveCam] = useState<CameraPoint | null>(null)
  const [utciMeta, setUtciMeta] = useState<UtciMeta | null>(null)
  const [utciSample, setUtciSample] = useState<UtciSample | null>(null)
  const [utciSampling, setUtciSampling] = useState(false)
  const [utciSampleError, setUtciSampleError] = useState<string | null>(null)
  const liveRef = useRef(live)
  const utciMetaRef = useRef<UtciMeta | null>(null)
  liveRef.current = live
  utciMetaRef.current = utciMeta

  const toggleLive = useCallback((key: 'radar' | 'goes' | 'traffic' | 'cams' | 'utci') => {
    setLive((s) => ({ ...s, [key]: !s[key] }))
  }, [])
  const viewRef = useRef({ heading: 0, pitch: PITCH_TILTED, range: 40000, base: 40000 })
  const horizonRef = useRef(horizon)
  const hazardRef = useRef(hazard)
  const onSelectRef = useRef(onTractSelect)
  horizonRef.current = horizon
  hazardRef.current = hazard
  onSelectRef.current = onTractSelect

  const applyView = useCallback((duration = 0.8) => {
    const viewer = viewerRef.current
    const sphere = sphereRef.current
    if (!viewer || !sphere) return
    const v = viewRef.current
    viewer.camera.flyToBoundingSphere(sphere, {
      duration,
      offset: new Cesium.HeadingPitchRange(v.heading, v.pitch, v.range),
    })
  }, [])

  const pauseDrone = useCallback(() => {
    droneRef.current = false
    setDrone(false)
    const viewer = viewerRef.current
    const sphere = sphereRef.current
    if (viewer && sphere && droneLockedRef.current) {
      viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY)
      droneLockedRef.current = false
      const dist = Cesium.Cartesian3.distance(viewer.camera.position, sphere.center)
      viewRef.current.range = Cesium.Math.clamp(dist, viewRef.current.base * 0.12, viewRef.current.base * 3)
    }
  }, [])

  const zoom = useCallback((factor: number) => {
    pauseDrone()
    const v = viewRef.current
    v.range = Cesium.Math.clamp(v.range * factor, v.base * 0.12, v.base * 3)
    applyView(0.5)
  }, [applyView, pauseDrone])

  const rotate = useCallback((deg: number) => {
    pauseDrone()
    const v = viewRef.current
    v.heading += Cesium.Math.toRadians(deg)
    applyView(0.6)
  }, [applyView, pauseDrone])

  const toggleTilt = useCallback(() => {
    pauseDrone()
    const v = viewRef.current
    v.pitch = v.pitch < PITCH_TOP + 0.02 ? PITCH_TILTED : PITCH_TOP
    applyView(0.8)
  }, [applyView, pauseDrone])

  const resetView = useCallback(() => {
    pauseDrone()
    const v = viewRef.current
    v.heading = 0
    v.pitch = PITCH_TILTED
    v.range = v.base
    applyView(1.0)
  }, [applyView, pauseDrone])

  const toggleBuildings = useCallback(() => {
    const b = osmBuildingsRef.current
    if (b) b.show = !b.show
  }, [])

  // Live HUD telemetry, derived from the current forecast data.
  const telemetry = useMemo(() => {
    let sum = 0
    let n = 0
    let hot = -Infinity
    let hotName = ''
    for (const f of geojson.features) {
      const v = (f.properties?.forecasts as Record<string, number> | undefined)?.[String(horizon)]
      if (v == null) continue
      sum += v
      n += 1
      if (v > hot) {
        hot = v
        hotName = (f.properties?.NAME as string) ?? (f.properties?.GEOID as string) ?? ''
      }
    }
    return n ? { avg: sum / n, n, hot, hotName } : null
  }, [geojson, horizon])

  // 1 Hz clock for the live feed timestamp.
  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString('en-US', {
          hour12: false,
          timeZone: 'UTC',
        }),
      )
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [])

  // Init viewer once.
  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return
    const viewer = new Cesium.Viewer(containerRef.current, {
      animation: false,
      timeline: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      baseLayerPicker: false,
      infoBox: false,
      selectionIndicator: false,
      // Tokenless Esri World Imagery — real satellite base, no Ion account needed.
      baseLayer: new Cesium.ImageryLayer(
        new Cesium.UrlTemplateImageryProvider({
          url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          maximumLevel: 19,
          credit: 'Esri, Maxar, Earthstar Geographics',
        }),
      ),
    })
    viewer.scene.globe.enableLighting = true

    // Constrain the mouse to pan + zoom only — no accidental tilt/rotate/look.
    // 3D moves live on the on-screen buttons instead.
    const cc = viewer.scene.screenSpaceCameraController
    cc.enableTilt = false
    cc.enableLook = false

    viewerRef.current = viewer

    // Digital-twin layers (need a free Cesium Ion token): real terrain
    // elevation + extruded OSM 3D buildings for the whole city.
    if (ION_TOKEN) {
      Cesium.createWorldTerrainAsync()
        .then((t) => {
          if (viewerRef.current) viewerRef.current.terrainProvider = t
        })
        .catch(() => undefined)
      Cesium.createOsmBuildingsAsync()
        .then((b) => {
          if (!viewerRef.current) return
          viewerRef.current.scene.primitives.add(b)
          osmBuildingsRef.current = b
        })
        .catch(() => undefined)
    }

    const onWheel = () => pauseDrone()
    viewer.scene.canvas.addEventListener('wheel', onWheel, { passive: true })

    // Live drone orbit: each frame, sweep the camera around the city center.
    const removeTick = viewer.clock.onTick.addEventListener(() => {
      const sphere = sphereRef.current
      if (!sphere) return
      if (droneRef.current) {
        droneHeadingRef.current += 0.0016
        viewer.camera.lookAt(
          sphere.center,
          new Cesium.HeadingPitchRange(
            droneHeadingRef.current,
            Cesium.Math.toRadians(-32),
            sphere.radius * 2.0,
          ),
        )
        droneLockedRef.current = true
      } else if (droneLockedRef.current) {
        // Release the lookAt transform so manual controls work again.
        viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY)
        droneLockedRef.current = false
      }
    })

    // Tract picking + UTCI point sampling.
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handler.setInputAction(async (e: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
      const picked = viewer.scene.pick(e.position)
      const id = picked?.id as Cesium.Entity | undefined
      if (id && camByEntityRef.current.has(id.id)) {
        setActiveCam(camByEntityRef.current.get(id.id) ?? null)
        return
      }

      const ray = viewer.camera.getPickRay(e.position)
      const cartesian = ray ? viewer.scene.globe.pick(ray, viewer.scene) : undefined
      if (cartesian && liveRef.current.utci && utciMetaRef.current?.bounds) {
        const carto = Cesium.Cartographic.fromCartesian(cartesian)
        const lat = Cesium.Math.toDegrees(carto.latitude)
        const lon = Cesium.Math.toDegrees(carto.longitude)
        if (inUtciBounds(lat, lon, utciMetaRef.current.bounds)) {
          pauseDrone()
          setUtciSampling(true)
          setUtciSampleError(null)
          const sample = await sampleUtciAt(lat, lon).catch(() => null)
          setUtciSampling(false)
          if (sample) {
            setUtciSample(sample)
            if (utciSampleEntityRef.current) {
              viewer.entities.remove(utciSampleEntityRef.current)
            }
            utciSampleEntityRef.current = viewer.entities.add({
              position: Cesium.Cartesian3.fromDegrees(lon, lat),
              point: {
                pixelSize: 11,
                color: Cesium.Color.fromCssColorString('#fbbf24'),
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 2,
                heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
              },
            })
          } else {
            setUtciSampleError('No UTCI value here (nodata or outside tile).')
          }
          return
        }
      }

      const geoid = id?.properties?.GEOID?.getValue?.()
      if (geoid && onSelectRef.current) onSelectRef.current(String(geoid))
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    return () => {
      viewer.scene.canvas.removeEventListener('wheel', onWheel)
      removeTick()
      handler.destroy()
      viewer.destroy()
      viewerRef.current = null
      dataSourceRef.current = null
      pinEntityRef.current = null
    }
  }, [])

  // Load / restyle tracts on geojson change — flat, draped on the ground.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    let cancelled = false

    const sphere = boundsSphere(geojson)
    sphereRef.current = sphere
    viewRef.current.base = sphere.radius * 2.4
    viewRef.current.range = sphere.radius * 2.4

    Cesium.GeoJsonDataSource.load(geojson, { clampToGround: true }).then((ds) => {
      if (cancelled || !viewerRef.current) return
      const prev = dataSourceRef.current
      if (prev) viewer.dataSources.remove(prev, true)
      styleEntities(ds, horizonRef.current, hazardRef.current)
      viewer.dataSources.add(ds)
      dataSourceRef.current = ds
      // Frame the city only on first load — later live-data swaps keep the
      // user's current camera so the view doesn't jump every refresh.
      if (!pin && !framedRef.current) {
        applyView(1.2)
        framedRef.current = true
      }
    })

    return () => {
      cancelled = true
    }
    // pin excluded — pin effect handles camera when a pin is set.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geojson, applyView])

  // Recolor when horizon or hazard changes (no reload).
  useEffect(() => {
    const ds = dataSourceRef.current
    if (ds) styleEntities(ds, horizon, hazard)
  }, [horizon, hazard])

  // Live radar overlay (RainViewer) — refresh every 5 min.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    let cancelled = false
    let timer: number | undefined
    const remove = () => {
      if (radarLayerRef.current) {
        viewer.imageryLayers.remove(radarLayerRef.current, true)
        radarLayerRef.current = null
      }
    }
    const add = async () => {
      const layer = await makeRadarLayer(viewer).catch(() => null)
      if (cancelled) {
        if (layer) viewer.imageryLayers.remove(layer, true)
        return
      }
      radarLayerRef.current = layer
    }
    if (live.radar) {
      add()
      timer = window.setInterval(() => {
        remove()
        add()
      }, 300_000)
    }
    return () => {
      cancelled = true
      if (timer) window.clearInterval(timer)
      remove()
    }
  }, [live.radar])

  // Live GOES cloud overlay (NASA GIBS) — refresh every 10 min for a new frame.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    let timer: number | undefined
    const remove = () => {
      if (goesLayerRef.current) {
        viewer.imageryLayers.remove(goesLayerRef.current, true)
        goesLayerRef.current = null
      }
    }
    const add = () => {
      goesLayerRef.current = makeGoesLayer(viewer)
    }
    if (live.goes) {
      add()
      timer = window.setInterval(() => {
        remove()
        add()
      }, 600_000)
    }
    return () => {
      if (timer) window.clearInterval(timer)
      remove()
    }
  }, [live.goes])

  // Live traffic flow (TomTom) — needs a key.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !TOMTOM_KEY) return
    const remove = () => {
      if (trafficLayerRef.current) {
        viewer.imageryLayers.remove(trafficLayerRef.current, true)
        trafficLayerRef.current = null
      }
    }
    if (live.traffic) trafficLayerRef.current = makeTrafficLayer(viewer, TOMTOM_KEY)
    return remove
  }, [live.traffic])

  // Street-level UTCI thermal-comfort tile (SOLWEIG-GPU).
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    let cancelled = false
    const remove = () => {
      if (utciLayerRef.current) {
        viewer.imageryLayers.remove(utciLayerRef.current, true)
        utciLayerRef.current = null
      }
    }
    const clearSample = () => {
      if (utciSampleEntityRef.current) {
        viewer.entities.remove(utciSampleEntityRef.current)
        utciSampleEntityRef.current = null
      }
      setUtciSample(null)
      setUtciSampleError(null)
      setUtciSampling(false)
    }
    const add = async () => {
      const meta = await fetchUtciMeta().catch(() => null)
      if (cancelled) return
      setUtciMeta(meta)
      const layer = await makeUtciLayer(viewer).catch(() => null)
      if (cancelled) {
        if (layer) viewer.imageryLayers.remove(layer, true)
        return
      }
      utciLayerRef.current = layer
    }
    if (live.utci) {
      add()
    } else {
      remove()
      clearSample()
      setUtciMeta(null)
    }
    return () => {
      cancelled = true
      remove()
    }
  }, [live.utci])

  // Live traffic cameras (Austin/TxDOT) as clickable points.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    let cancelled = false
    const remove = () => {
      if (camsDsRef.current) {
        viewer.dataSources.remove(camsDsRef.current, true)
        camsDsRef.current = null
      }
      camByEntityRef.current.clear()
    }
    const add = async () => {
      const cams = await fetchCameras().catch(() => [])
      if (cancelled || !viewerRef.current) return
      const ds = new Cesium.CustomDataSource('cameras')
      for (const c of cams) {
        const ent = ds.entities.add({
          position: Cesium.Cartesian3.fromDegrees(c.lon, c.lat),
          point: {
            pixelSize: 7,
            color: Cesium.Color.fromCssColorString('#22d3ee'),
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 1,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        })
        camByEntityRef.current.set(ent.id, c)
      }
      viewer.dataSources.add(ds)
      camsDsRef.current = ds
    }
    if (live.cams) add()
    else setActiveCam(null)
    return () => {
      cancelled = true
      remove()
    }
  }, [live.cams])

  // Pin marker + camera fly.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    if (pinEntityRef.current) {
      viewer.entities.remove(pinEntityRef.current)
      pinEntityRef.current = null
    }
    if (!pin) return
    pauseDrone()
    const ent = viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(pin.lon, pin.lat, 0),
      point: {
        pixelSize: 12,
        color: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.fromCssColorString('#1a3c8f'),
        outlineWidth: 3,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: pin.label
        ? {
            text: pin.label,
            font: '13px sans-serif',
            fillColor: Cesium.Color.WHITE,
            showBackground: true,
            backgroundColor: Cesium.Color.fromCssColorString('#1a3c8f').withAlpha(0.85),
            pixelOffset: new Cesium.Cartesian2(0, -22),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          }
        : undefined,
    })
    pinEntityRef.current = ent
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(pin.lon, pin.lat, 6000),
      orientation: { pitch: PITCH_TILTED },
      duration: 1.2,
    })
  }, [pin, pauseDrone])

  return (
    <div className={styles.mapWrap}>
      <div ref={containerRef} className={styles.map} />

      {/* Live drone-feed HUD overlay */}
      <div className={styles.hud} aria-hidden="true">
        <span className={`${styles.corner} ${styles.cTL}`} />
        <span className={`${styles.corner} ${styles.cTR}`} />
        <span className={`${styles.corner} ${styles.cBL}`} />
        <span className={`${styles.corner} ${styles.cBR}`} />
        {drone && <span className={styles.scanline} />}
        <div className={styles.hudTop}>
          <span className={`${styles.rec} ${drone ? '' : styles.recPaused}`}>
            <span className={styles.recDot} />
            {drone ? 'LIVE' : 'PAUSED'}
          </span>
          <span className={styles.hudTitle}>AUSTIN · CLIMATE TWIN</span>
          <span className={styles.hudClock}>{clock} UTC</span>
        </div>
        <div className={styles.hudBottom}>
          <span>CAM · AERIAL ORBIT</span>
          {live.utci && utciMeta ? (
            <span className={styles.hudUtci}>{utciInsightLine(utciMeta)}</span>
          ) : (
            telemetry && (
              <>
                <span>STATION KAUS</span>
                <span>AVG HI {telemetry.avg.toFixed(1)}°F</span>
                <span>
                  PEAK {telemetry.hotName} {telemetry.hot.toFixed(1)}°F
                </span>
                <span>
                  {telemetry.n} TRACTS · +{horizon}h
                </span>
              </>
            )
          )}
        </div>
      </div>

      {/* Real-time overlay toggles */}
      <div className={styles.liveLayers} role="group" aria-label="Live layers">
        <span className={styles.liveLayersTitle}>LIVE LAYERS</span>
        <button
          type="button"
          className={`${styles.layerChip} ${live.radar ? styles.layerOn : ''}`}
          onClick={() => toggleLive('radar')}
        >
          🌧 Radar
        </button>
        <button
          type="button"
          className={`${styles.layerChip} ${live.goes ? styles.layerOn : ''}`}
          onClick={() => toggleLive('goes')}
        >
          ☁ Clouds
        </button>
        <button
          type="button"
          className={`${styles.layerChip} ${live.utci ? styles.layerOn : ''}`}
          onClick={() => toggleLive('utci')}
          title="Street-level thermal comfort (SOLWEIG-GPU UTCI)"
        >
          🌡 UTCI
        </button>
        <button
          type="button"
          className={`${styles.layerChip} ${live.cams ? styles.layerOn : ''}`}
          onClick={() => toggleLive('cams')}
        >
          📷 Cameras
        </button>
        <button
          type="button"
          className={`${styles.layerChip} ${live.traffic ? styles.layerOn : ''}`}
          onClick={() => toggleLive('traffic')}
          disabled={!TOMTOM_KEY}
          title={TOMTOM_KEY ? 'Live traffic flow' : 'Set VITE_TOMTOM_KEY to enable'}
        >
          🚗 Traffic
        </button>
      </div>

      {live.utci && (
        <UtciInsightPanel
          meta={utciMeta}
          sample={utciSample}
          sampling={utciSampling}
          sampleError={utciSampleError}
        />
      )}

      {activeCam && <CameraPopup cam={activeCam} onClose={() => setActiveCam(null)} />}

      <div className={styles.globeControls} role="group" aria-label="Map controls">
        <button
          type="button"
          className={`${styles.globeBtn} ${drone ? styles.globeBtnLive : ''}`}
          onClick={() => {
            if (drone) pauseDrone()
            else setDrone(true)
          }}
          title={drone ? 'Pause live drone view (enables zoom)' : 'Resume live drone view'}
          aria-label="Toggle live drone view"
        >
          {drone ? '⏸' : '◉'}
        </button>
        <button type="button" className={styles.globeBtn} onClick={() => zoom(0.7)} title="Zoom in" aria-label="Zoom in">＋</button>
        <button type="button" className={styles.globeBtn} onClick={() => zoom(1.4)} title="Zoom out" aria-label="Zoom out">－</button>
        <button type="button" className={styles.globeBtn} onClick={toggleTilt} title="Toggle top-down / tilted" aria-label="Toggle tilt">⤢</button>
        <button type="button" className={styles.globeBtn} onClick={() => rotate(-45)} title="Rotate left" aria-label="Rotate left">⟲</button>
        <button type="button" className={styles.globeBtn} onClick={() => rotate(45)} title="Rotate right" aria-label="Rotate right">⟳</button>
        <button type="button" className={styles.globeBtn} onClick={resetView} title="Reset view" aria-label="Reset view">⌂</button>
        {ION_TOKEN && (
          <button type="button" className={styles.globeBtn} onClick={toggleBuildings} title="Toggle 3D buildings" aria-label="Toggle 3D buildings">🏙</button>
        )}
      </div>
    </div>
  )
}

function CameraPopup({ cam, onClose }: { cam: CameraPoint; onClose: () => void }) {
  const [bust, setBust] = useState(0)
  useEffect(() => {
    setBust(0)
    const id = window.setInterval(() => setBust((b) => b + 1), 15_000)
    return () => window.clearInterval(id)
  }, [cam.id])
  return (
    <div className={styles.camPopup}>
      <div className={styles.camHead}>
        <span className={styles.camLive}>
          <span className={styles.recDot} />
          LIVE CAM
        </span>
        <span className={styles.camName}>{cam.name}</span>
        <button type="button" className={styles.camClose} onClick={onClose} aria-label="Close camera">
          ×
        </button>
      </div>
      <img className={styles.camImg} src={`${cam.img}?t=${bust}`} alt={cam.name} />
      <div className={styles.camFoot}>Austin/TxDOT CCTV · #{cam.id} · refreshing 15s</div>
    </div>
  )
}

function styleEntities(
  ds: Cesium.GeoJsonDataSource,
  horizon: number,
  hazard: HazardId = 'heat',
) {
  for (const entity of ds.entities.values) {
    if (!entity.polygon) continue
    const props = entity.properties
    const raw: Record<string, unknown> = {}
    if (props) {
      for (const name of [
        'forecasts',
        'flood_forecasts',
        'grid_forecasts',
        'anomaly_severity',
        'NAME',
        'GEOID',
      ]) {
        try {
          raw[name] = props[name]?.getValue?.()
        } catch {
          /* ignore */
        }
      }
    }
    const value = getHazardValue(raw, hazard, horizon) ?? (hazard === 'heat' ? 85 : 40)
    const hex = hazardMapColor(hazard, value)
    entity.polygon.material = new Cesium.ColorMaterialProperty(cesiumColor(hex))
    entity.polygon.classificationType = new Cesium.ConstantProperty(
      Cesium.ClassificationType.TERRAIN,
    )
    const severity = raw.anomaly_severity as string | undefined
    if (severity === 'alert' || severity === 'extreme') {
      entity.polygon.outline = new Cesium.ConstantProperty(true)
      entity.polygon.outlineColor = new Cesium.ConstantProperty(
        Cesium.Color.fromCssColorString(severity === 'extreme' ? '#b91c1c' : '#ea580c'),
      )
      entity.polygon.outlineWidth = new Cesium.ConstantProperty(2)
    }
    const name = raw.NAME ?? raw.GEOID
    const label =
      hazard === 'heat'
        ? `Heat index (+${horizon}h)`
        : hazard === 'flood'
          ? `Flood risk (+${horizon}h)`
          : `Grid stress (+${horizon}h)`
    entity.description = new Cesium.ConstantProperty(
      `<strong>${name}</strong><br/>${label}: <strong>${formatHazardValue(hazard, value)}</strong>`,
    )
  }
}
