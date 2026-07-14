import { useEffect } from 'react'
import { GeoJSON, MapContainer, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { PathOptions } from 'leaflet'
import type { Feature, FeatureCollection } from 'geojson'
import 'leaflet/dist/leaflet.css'
import { scoreColor, severityLabel } from '../lib/anomalyUtils'
import styles from './ForecastMap.module.css'

type Props = {
  geojson: FeatureCollection
  onTractSelect?: (geoid: string) => void
}

function FitBounds({ geojson }: { geojson: FeatureCollection }) {
  const map = useMap()
  useEffect(() => {
    const layer = L.geoJSON(geojson)
    const bounds = layer.getBounds()
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [24, 24] })
    }
  }, [geojson, map])
  return null
}

export default function AnomalyMap({ geojson, onTractSelect }: Props) {
  const style = (feature?: Feature): PathOptions => {
    const score = Number(feature?.properties?.anomaly_score ?? 0)
    return {
      fillColor: scoreColor(score),
      fillOpacity: 0.78,
      color: '#1a3c8f',
      weight: 0.5,
      opacity: 0.55,
    }
  }

  const onEach = (feature: Feature, layer: L.Layer) => {
    const p = feature.properties ?? {}
    const score = Number(p.anomaly_score ?? 0)
    const severity = String(p.severity ?? 'normal')
    const name = p.NAME ?? p.GEOID
    layer.bindPopup(
      `<strong>${name}</strong><br/>Score: <strong>${(score * 100).toFixed(0)}%</strong><br/>${severityLabel(severity)}`,
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
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <GeoJSON data={geojson} style={style} onEachFeature={onEach} />
        <FitBounds geojson={geojson} />
      </MapContainer>
    </div>
  )
}
