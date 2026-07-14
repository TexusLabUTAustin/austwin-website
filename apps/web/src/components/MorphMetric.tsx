import HoverTip from './HoverTip'
import styles from './MorphMetric.module.css'

export const MORPH_TOOLTIPS = {
  section:
    'CityForesight blends weather data with land-cover traits (KIL) to nudge the airport forecast up or down for each tract.',
  impervious:
    'More paved and built surface usually increases heat index here — hard surfaces store and release more heat.',
  canopy:
    'More tree canopy usually lowers heat index — shade and evaporation cool the tract relative to open pavement.',
  drainage:
    'Better drainage is tied to slightly lower heat stress in the model by reducing pooled moisture and humidity near the surface.',
} as const

type MetricKey = 'impervious' | 'canopy' | 'drainage'

type Props = {
  label: string
  value: string
  metric: MetricKey
}

export function MorphSectionHint() {
  return (
    <div className={styles.sectionBlock}>
      <div className={styles.sectionWrap}>
      <span className={styles.morphTitle}>Land cover context</span>
      <HoverTip
        label="How land cover affects forecasts"
        text={MORPH_TOOLTIPS.section}
      />
      </div>
    </div>
  )
}

export default function MorphMetric({ label, value, metric }: Props) {
  return (
    <div className={styles.morphItem}>
      <span className={styles.labelRow}>
        <span>{label}</span>
        <HoverTip
          label={`How ${label} affects this forecast`}
          text={MORPH_TOOLTIPS[metric]}
        />
      </span>
      <strong>{value}</strong>
    </div>
  )
}
