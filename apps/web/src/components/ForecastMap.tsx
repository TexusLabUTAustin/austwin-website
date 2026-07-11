import { useEffect } from 'react'
import { GeoJSON, MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { PathOptions } from 'leaflet'
import type { Feature, FeatureCollection } from 'geojson'
import 'leaflet/dist/leaflet.css'
import { heatIndexColor } from '../lib/forecastUtils'
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

export default function ForecastMap({ geojson, horizon, onTractSelect, pin }: Props) {
  const style = (feature?: Feature): PathOptions => {
    const forecasts = feature?.properties?.forecasts as Record<string, number> | undefined
    const value = forecasts?.[String(horizon)] ?? 85
    return {
      fillColor: heatIndexColor(value),
      fillOpacity: 0.78,
      color: '#1a3c8f',
      weight: 0.5,
      opacity: 0.55,
    }
  }

  const onEach = (feature: Feature, layer: L.Layer) => {
    const forecasts = feature.properties?.forecasts as Record<string, number> | undefined
    const value = forecasts?.[String(horizon)]
    const name = feature.properties?.NAME ?? feature.properties?.GEOID
    layer.bindPopup(
      `<strong>${name}</strong><br/>Heat index (+${horizon}h): <strong>${value?.toFixed(1) ?? '—'}°F</strong>`,
    )
    layer.on('click', () => {
      const geoid = feature.properties?.GEOID as string
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
          key={horizon}
          data={geojson}
          style={style}
          onEachFeature={onEach}
        />
        {pin && (
          <Marker position={[pin.lat, pin.lon]}>
            <Popup>
              <strong>{pin.label ?? 'Your search'}</strong>
              {pin.heatIndex !== undefined && (
                <>
                  <br />
                  Heat index (+{horizon}h):{' '}
                  <strong>{pin.heatIndex.toFixed(1)}°F</strong>
                </>
              )}
            </Popup>
          </Marker>
        )}
        {!pin && <FitBounds geojson={geojson} />}
        <MapFlyTo pin={pin} />
      </MapContainer>
    </div>
  )
}
