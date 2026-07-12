import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { sendChat } from '../lib/guideApi'
import styles from './CityGuide.module.css'

type Message = {
  role: 'user' | 'assistant'
  text: string
  refused?: boolean
  model?: string
}

const SUGGESTIONS = [
  'Which tracts are hottest right now?',
  'Are there any active heat anomalies?',
  'What does impervious ratio mean?',
  'How does the forecasting model work?',
  'When should we open cooling centers?',
]

const GREETING: Message = {
  role: 'assistant',
  text:
    "I'm CityGuide, the AusTwin operator copilot. Ask me about live heat forecasts, " +
    'active anomalies, metric definitions, how the models work, or heat-response ' +
    "protocols. I answer only from live system data and AusTwin's knowledge base — " +
    "if I don't have grounded evidence, I'll say so instead of guessing.",
}

export default function CityGuide() {
  const [messages, setMessages] = useState<Message[]>([GREETING])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

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
    <div className={styles.page}>
      <header className={styles.header}>
        <Link to="/one-pager" className={styles.backLink}>
          ← AusTwin
        </Link>
        <div className={styles.headerMain}>
          <h1 className={styles.title}>
            <span className={styles.titleAccent}>City</span>Guide
          </h1>
          <p className={styles.subtitle}>
            Operator Q&amp;A copilot — grounded on live CityForesight forecasts and
            UrbanSense anomalies, with a curated knowledge base. Runs a local
            open-source model; answers are cited and refuse-on-doubt.
          </p>
        </div>
      </header>

      <div className={styles.chatCard}>
        <div className={styles.messages} ref={scrollRef}>
          {messages.map((m, i) => (
            <div
              key={i}
              className={`${styles.msg} ${m.role === 'user' ? styles.msgUser : styles.msgBot} ${
                m.refused ? styles.msgRefused : ''
              }`}
            >
              <div className={styles.msgText}>{m.text}</div>
              {m.model && m.model !== 'guardrail' && (
                <div className={styles.modelTag}>{m.model}</div>
              )}
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
              <button key={s} type="button" className={styles.suggestion} onClick={() => ask(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        {error && <p className={styles.error}>{error}. Is the CityGuide API running on port 8012?</p>}

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
            placeholder="Ask about heat forecasts, anomalies, metrics, or protocols…"
            disabled={loading}
            aria-label="Ask CityGuide"
          />
          <button type="submit" className={styles.send} disabled={loading || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
