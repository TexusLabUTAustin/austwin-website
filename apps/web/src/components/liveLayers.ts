/** Real-time "city right now" overlays for the Cesium twin. All free/no-key
 *  except TomTom traffic flow (needs VITE_TOMTOM_KEY). */
import * as Cesium from 'cesium'

export type CameraPoint = {
  id: string
  name: string
  lon: number
  lat: number
  img: string
}

const RAINVIEWER_META = 'https://api.rainviewer.com/public/weather-maps.json'
const AUSTIN_CAMERAS =
  'https://data.austintexas.gov/resource/b4k4-adkb.json?$limit=500&camera_status=TURNED_ON'

/** Latest animated precip radar (RainViewer). ~10-min refresh, free, no key. */
export async function makeRadarLayer(viewer: Cesium.Viewer): Promise<Cesium.ImageryLayer | null> {
  const meta = await fetch(RAINVIEWER_META).then((r) => r.json())
  const frames = meta?.radar?.past ?? []
  if (!frames.length) return null
  const frame = frames[frames.length - 1]
  const provider = new Cesium.UrlTemplateImageryProvider({
    url: `${meta.host}${frame.path}/256/{z}/{x}/{y}/4/1_1.png`,
    maximumLevel: 12,
    credit: 'RainViewer',
  })
  const layer = viewer.imageryLayers.addImageryProvider(provider)
  layer.alpha = 0.72
  return layer
}

/** GOES-East near-real-time cloud/GeoColor imagery (NASA GIBS). ~10-min. */
export function makeGoesLayer(viewer: Cesium.Viewer): Cesium.ImageryLayer {
  const provider = new Cesium.UrlTemplateImageryProvider({
    url: `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/GOES-East_ABI_GeoColor/default/${goesTimeIso()}/GoogleMapsCompatible_Level7/{z}/{y}/{x}.jpg`,
    maximumLevel: 7,
    credit: 'NASA GIBS / NOAA GOES-East',
  })
  const layer = viewer.imageryLayers.addImageryProvider(provider)
  layer.alpha = 0.6
  return layer
}

/** Current traffic-flow tiles (TomTom). Needs a free VITE_TOMTOM_KEY. */
export function makeTrafficLayer(viewer: Cesium.Viewer, key: string): Cesium.ImageryLayer {
  const provider = new Cesium.UrlTemplateImageryProvider({
    url: `https://api.tomtom.com/traffic/map/4/tile/flow/relative0/{z}/{x}/{y}.png?key=${key}`,
    maximumLevel: 20,
    credit: 'TomTom Traffic',
  })
  const layer = viewer.imageryLayers.addImageryProvider(provider)
  layer.alpha = 0.9
  return layer
}

/** Live Austin/TxDOT traffic cameras with current-snapshot URLs. */
export async function fetchCameras(): Promise<CameraPoint[]> {
  const rows = await fetch(AUSTIN_CAMERAS).then((r) => r.json())
  const out: CameraPoint[] = []
  for (const r of rows) {
    const coords = r?.location?.coordinates
    if (!Array.isArray(coords) || !r.screenshot_address) continue
    out.push({
      id: String(r.camera_id),
      name: String(r.location_name || '').trim() || `Camera ${r.camera_id}`,
      lon: Number(coords[0]),
      lat: Number(coords[1]),
      img: String(r.screenshot_address),
    })
  }
  return out
}

/** Street-level UTCI thermal-comfort tile (SOLWEIG-GPU) draped over its bounds. */
export async function makeUtciLayer(viewer: Cesium.Viewer): Promise<Cesium.ImageryLayer | null> {
  const meta = await fetch('/api/thermal/utci').then((r) => (r.ok ? r.json() : null))
  if (!meta?.bounds || !meta?.png_url) return null
  const b = meta.bounds
  const provider = new Cesium.SingleTileImageryProvider({
    url: meta.png_url,
    rectangle: Cesium.Rectangle.fromDegrees(b.west, b.south, b.east, b.north),
    tileWidth: 256,
    tileHeight: 256,
  })
  const layer = viewer.imageryLayers.addImageryProvider(provider)
  layer.alpha = 0.85
  return layer
}

/** Round to the most recent 10-minute GOES slot, with lag for availability. */
function goesTimeIso(lagMinutes = 25): string {
  const t = Date.now() - lagMinutes * 60_000
  const floored = Math.floor(t / 600_000) * 600_000
  return new Date(floored).toISOString().replace(/\.\d+Z$/, 'Z')
}
