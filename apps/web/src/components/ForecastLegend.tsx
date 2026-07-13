import styles from './ForecastLegend.module.css'
import { HEAT_INDEX_LEGEND_TICKS, heatIndexGradientCss } from '../lib/forecastUtils'
import {
  FLOOD_LEGEND_TICKS,
  GRID_LEGEND_TICKS,
  hazardGradientCss,
  type HazardId,
} from '../lib/hazardUtils'

type Props = {
  hazard?: HazardId
}

export default function ForecastLegend({ hazard = 'heat' }: Props) {
  if (hazard === 'flood') {
    return (
      <div className={styles.legend} aria-label="Flood risk legend">
        <span className={styles.title}>Flood risk</span>
        <div
          className={styles.gradientBar}
          style={{ background: hazardGradientCss('flood') }}
          role="img"
          aria-hidden
        />
        <div className={styles.ticks}>
          {FLOOD_LEGEND_TICKS.map((tick) => (
            <span key={tick.label} className={styles.tick}>
              {tick.label}
            </span>
          ))}
        </div>
      </div>
    )
  }

  if (hazard === 'grid') {
    return (
      <div className={styles.legend} aria-label="Grid stress legend">
        <span className={styles.title}>Grid stress</span>
        <div
          className={styles.gradientBar}
          style={{ background: hazardGradientCss('grid') }}
          role="img"
          aria-hidden
        />
        <div className={styles.ticks}>
          {GRID_LEGEND_TICKS.map((tick) => (
            <span key={tick.label} className={styles.tick}>
              {tick.label}
            </span>
          ))}
        </div>
      </div>
    )
  }

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
