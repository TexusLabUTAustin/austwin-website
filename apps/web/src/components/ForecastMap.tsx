import { useEffect } from 'react'
import { GeoJSON, MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { PathOptions } from 'leaflet'
import type { Feature, FeatureCollection } from 'geojson'
import 'leaflet/dist/leaflet.css'
import { hazardMapColor } from '../lib/forecastInsights'
import {
  formatHazardValue,
  getHazardValue,
  type HazardId,
} from '../lib/hazardUtils'
import styles from './ForecastMap.module.css'

import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

const defaultIcon = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})
L.Marker.prototype.options.icon = defaultIcon

export type MapPin = {
  lat: number
  lon: number
  label?: string
  heatIndex?: number
}

type Props = {
  geojson: FeatureCollection
  horizon: number
  hazard?: HazardId
  onTractSelect?: (geoid: string) => void
  pin?: MapPin | null
}

function FitBounds({ geojson }: { geojson: FeatureCollection }) {
  const map = useMap()
  useEffect(() => {
    if (geojson.features.length === 0) return
    const layer = L.geoJSON(geojson)
    const bounds = layer.getBounds()
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [24, 24] })
    }
  }, [geojson, map])
  return null
}

function MapFlyTo({ pin }: { pin: MapPin | null | undefined }) {
  const map = useMap()
  useEffect(() => {
    if (pin) {
      map.flyTo([pin.lat, pin.lon], 14, { duration: 0.8 })
    }
  }, [pin, map])
  return null
}

function anomalyStroke(severity?: string): { color: string; weight: number } {
  if (severity === 'extreme') return { color: '#b91c1c', weight: 2.2 }
  if (severity === 'alert') return { color: '#ea580c', weight: 1.8 }
  if (severity === 'watch') return { color: '#ca8a04', weight: 1.2 }
  return { color: '#1a3c8f', weight: 0.5 }
}

export default function ForecastMap({
  geojson,
  horizon,
  hazard = 'heat',
  onTractSelect,
  pin,
}: Props) {
  const style = (feature?: Feature): PathOptions => {
    const props = (feature?.properties ?? {}) as Record<string, unknown>
    const value = getHazardValue(props, hazard, horizon) ?? (hazard === 'heat' ? 85 : 40)
    const stroke = anomalyStroke(props.anomaly_severity as string | undefined)
    return {
      fillColor: hazardMapColor(hazard, value),
      fillOpacity: 0.78,
      color: stroke.color,
      weight: stroke.weight,
      opacity: 0.7,
    }
  }

  const onEach = (feature: Feature, layer: L.Layer) => {
    const props = (feature.properties ?? {}) as Record<string, unknown>
    const value = getHazardValue(props, hazard, horizon)
    const name = props.NAME ?? props.GEOID
    const label =
      hazard === 'heat'
        ? `Heat index (+${horizon}h)`
        : hazard === 'flood'
          ? `Flood risk (+${horizon}h)`
          : `Grid stress (+${horizon}h)`
    layer.bindPopup(
      `<strong>${name}</strong><br/>${label}: <strong>${
        value != null ? formatHazardValue(hazard, value) : '—'
      }</strong>`,
    )
    layer.on('click', () => {
      const geoid = props.GEOID as string
      if (geoid && onTractSelect) onTractSelect(geoid)
    })
  }

  return (
    <div className={styles.mapWrap}>
      <MapContainer
        center={[30.27, -97.74]}
        zoom={11}
        className={styles.map}
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <GeoJSON
          key={`${horizon}-${hazard}-${geojson.features.length}`}
          data={geojson}
          style={style}
          onEachFeature={onEach}
        />
        <FitBounds geojson={geojson} />
        <MapFlyTo pin={pin} />
        {pin && (
          <Marker position={[pin.lat, pin.lon]}>
            {pin.label && <Popup>{pin.label}</Popup>}
          </Marker>
        )}
      </MapContainer>
    </div>
  )
}
