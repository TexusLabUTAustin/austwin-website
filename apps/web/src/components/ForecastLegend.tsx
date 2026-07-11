import styles from './ForecastLegend.module.css'
import { HEAT_INDEX_LEGEND_TICKS, heatIndexGradientCss } from '../lib/forecastUtils'

export default function ForecastLegend() {
  return (
    <div className={styles.legend} aria-label="Heat index legend">
      <span className={styles.title}>Heat Index</span>
      <div
        className={styles.gradientBar}
        style={{ background: heatIndexGradientCss() }}
        role="img"
        aria-hidden
      />
      <div className={styles.ticks}>
        {HEAT_INDEX_LEGEND_TICKS.map((tick) => (
          <span key={tick.label} className={styles.tick}>
            {tick.label}
          </span>
        ))}
      </div>
    </div>
  )
}
