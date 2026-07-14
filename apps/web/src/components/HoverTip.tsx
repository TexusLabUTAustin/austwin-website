import { useCallback, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import styles from './HoverTip.module.css'

type Props = {
  text: string
  label: string
}

export default function HoverTip({ text, label }: Props) {
  const [visible, setVisible] = useState(false)
  const [coords, setCoords] = useState({ top: 0, left: 0 })
  const btnRef = useRef<HTMLButtonElement>(null)

  const positionTip = useCallback(() => {
    const el = btnRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const tipWidth = 210
    const margin = 10
    let left = rect.left + rect.width / 2 - tipWidth / 2
    left = Math.max(margin, Math.min(left, window.innerWidth - tipWidth - margin))

    let top = rect.bottom + 8
    const estimatedHeight = 88
    if (top + estimatedHeight > window.innerHeight - margin) {
      top = rect.top - estimatedHeight - 8
    }

    setCoords({ top, left })
  }, [])

  const show = () => {
    positionTip()
    setVisible(true)
  }

  const hide = () => setVisible(false)

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className={styles.btn}
        aria-label={label}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
      >
        ?
      </button>
      {visible &&
        createPortal(
          <div
            className={styles.tip}
            style={{ top: coords.top, left: coords.left, width: 210 }}
            role="tooltip"
          >
            {text}
          </div>,
          document.body,
        )}
    </>
  )
}
