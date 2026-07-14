import type { UtciMeta, UtciSample } from '../lib/utciUtils'
import { formatUtciHours, utciLegendGradient, utciValueColor } from '../lib/utciUtils'
import styles from './ForecastMap.module.css'

type Props = {
  meta: UtciMeta | null
  sample: UtciSample | null
  sampling: boolean
  sampleError: string | null
}

export default function UtciInsightPanel({ meta, sample, sampling, sampleError }: Props) {
  if (!meta) return null

  const [lo, hi] = meta.range_c
  const sampleColor = sample ? utciValueColor(sample.utci_c, lo, hi) : undefined

  return (
    <div className={styles.utciPanel} role="region" aria-label="UTCI thermal comfort insights">
      <div className={styles.utciHead}>
        <span className={styles.utciTitle}>UTCI · Street thermal comfort</span>
        {meta.date && (
          <span className={styles.utciSub}>
            {meta.date}
            {meta.hours?.length ? ` · ${formatUtciHours(meta.hours)}` : ''}
          </span>
        )}
      </div>

      <div className={styles.utciLegend}>
        <div className={styles.utciLegendBar} style={{ background: utciLegendGradient() }} />
        <div className={styles.utciLegendTicks}>
          <span>{lo.toFixed(1)}°C</span>
          <span>cooler</span>
          <span>{hi.toFixed(1)}°C</span>
        </div>
      </div>

      <div className={styles.utciStats}>
        {meta.mean_c != null && (
          <span>
            Mean <strong>{meta.mean_c.toFixed(1)}°C</strong>
          </span>
        )}
        {meta.spread_c != null && (
          <span>
            Shade spread <strong>{meta.spread_c.toFixed(1)}°C</strong>
          </span>
        )}
      </div>

      {(meta.hotspot || meta.coolest) && (
        <div className={styles.utciExtremes}>
          {meta.hotspot && (
            <span>
              Warmest <strong>{meta.hotspot.utci_c.toFixed(1)}°C</strong>
            </span>
          )}
          {meta.coolest && (
            <span>
              Coolest <strong>{meta.coolest.utci_c.toFixed(1)}°C</strong>
            </span>
          )}
        </div>
      )}

      {meta.stress_scale && (
        <div className={styles.utciBands}>
          {meta.stress_scale.map((b) => (
            <span key={b.label} className={styles.utciBand}>
              <i style={{ background: b.color }} />
              {b.label}
            </span>
          ))}
        </div>
      )}

      <div className={styles.utciSample}>
        {sampling && <span className={styles.utciHint}>Reading UTCI at click…</span>}
        {sampleError && <span className={styles.utciError}>{sampleError}</span>}
        {sample && !sampling && (
          <>
            <span
              className={styles.utciValue}
              style={{ borderColor: sampleColor, color: sampleColor }}
            >
              {sample.utci_c.toFixed(1)}°C
            </span>
            <span className={styles.utciStress}>{sample.stress_label}</span>
            <span className={styles.utciCoords}>
              {sample.lat.toFixed(5)}°, {sample.lon.toFixed(5)}°
            </span>
          </>
        )}
        {!sample && !sampling && !sampleError && (
          <span className={styles.utciHint}>Click inside the overlay to read UTCI at a point</span>
        )}
      </div>

      <p className={styles.utciFoot}>
        Universal Thermal Climate Index from SOLWEIG-GPU — shade, buildings, and sun angle at
        pedestrian height. Blue/green is cooler; yellow/red is warmer or more heat stress.
      </p>
    </div>
  )
}
