import { useEffect, useRef, useState } from 'react'
import { sendChat } from '../lib/guideApi'
import styles from './CityGuideWidget.module.css'

type Message = {
  role: 'user' | 'assistant'
  text: string
  refused?: boolean
  model?: string
}

type Props = {
  /** Render in the page chrome instead of as a floating bottom-right button. */
  placement?: 'fab' | 'header'
}

const SUGGESTIONS = [
  'Which tracts are hottest right now?',
  'Where is flood risk highest?',
  'What is ERCOT utilization right now?',
  'Any active heat anomalies?',
]

const GREETING: Message = {
  role: 'assistant',
  text:
    "I'm CityGuide. Ask about live heat, flood, and grid scores, ERCOT/USGS feeds, " +
    "anomalies, metrics, or protocols. I answer only from grounded data — " +
    "if I'm not sure, I'll say so.",
}

export default function CityGuideWidget({ placement = 'fab' }: Props) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([GREETING])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const header = placement === 'header'

  useEffect(() => {
    if (open) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages, loading, open])

  const ask = async (text: string) => {
    const q = text.trim()
    if (!q || loading) return
    setError(null)
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: q }])
    setLoading(true)
    try {
      const res = await sendChat(q)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: res.answer,
          refused: res.refused,
          model: res.model,
        },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={header ? styles.rootHeader : styles.root}>
      {open && (
        <div
          className={`${styles.panel} ${header ? styles.panelHeaderAnchor : ''}`}
          role="dialog"
          aria-label="CityGuide chatbot"
        >
          <header className={styles.panelHeader}>
            <div className={styles.panelTitle}>
              <span className={styles.dot} aria-hidden="true" />
              <strong>
                <span className={styles.accent}>City</span>Guide
              </strong>
              <span className={styles.tag}>copilot</span>
            </div>
            <button
              type="button"
              className={styles.closeBtn}
              onClick={() => setOpen(false)}
              aria-label="Close chatbot"
            >
              ×
            </button>
          </header>

          <div className={styles.messages} ref={scrollRef}>
            {messages.map((m, i) => (
              <div
                key={i}
                className={`${styles.msg} ${m.role === 'user' ? styles.msgUser : styles.msgBot} ${
                  m.refused ? styles.msgRefused : ''
                }`}
              >
                <div className={styles.msgText}>{m.text}</div>
              </div>
            ))}
            {loading && (
              <div className={`${styles.msg} ${styles.msgBot}`}>
                <div className={styles.typing}>
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          {messages.length <= 1 && (
            <div className={styles.suggestions}>
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className={styles.suggestion}
                  onClick={() => ask(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {error && <p className={styles.error}>{error}</p>}

          <form
            className={styles.inputRow}
            onSubmit={(e) => {
              e.preventDefault()
              ask(input)
            }}
          >
            <input
              className={styles.input}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask CityGuide…"
              disabled={loading}
              aria-label="Ask CityGuide"
            />
            <button type="submit" className={styles.send} disabled={loading || !input.trim()}>
              ↑
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        className={
          header
            ? `${styles.headerBtn} ${open ? styles.headerBtnOpen : ''}`
            : `${styles.fab} ${open ? styles.fabClose : styles.fabOpen}`
        }
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? 'Close CityGuide chatbot' : 'Open CityGuide chatbot'}
        aria-expanded={open}
      >
        {open ? (
          header ? (
            <>
              <ChatIcon />
              <span>Close</span>
            </>
          ) : (
            '×'
          )
        ) : (
          <>
            <ChatIcon />
            <span className={header ? undefined : styles.fabLabel}>
              {header ? 'Ask CityGuide' : 'Ask CityGuide'}
            </span>
          </>
        )}
        {!open && !header && <span className={styles.fabPulse} aria-hidden="true" />}
      </button>
    </div>
  )
}

function ChatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8A2.5 2.5 0 0 1 17.5 16H9l-4 4v-4H6.5A2.5 2.5 0 0 1 4 13.5v-8Z"
        fill="currentColor"
      />
      <circle cx="9" cy="9.5" r="1.15" fill="#1a3c8f" />
      <circle cx="12" cy="9.5" r="1.15" fill="#1a3c8f" />
      <circle cx="15" cy="9.5" r="1.15" fill="#1a3c8f" />
    </svg>
  )
}
