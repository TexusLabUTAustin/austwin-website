const GUIDE_API_BASE =
  import.meta.env.VITE_GUIDE_API_URL?.replace(/\/$/, '') ||
  (import.meta.env.DEV ? '/api/guide' : '/api/guide')

export type ChatSource = {
  type: 'live' | 'doc'
  title: string
}

export type ChatResponse = {
  answer: string
  grounded: boolean
  refused: boolean
  used_live: string[]
  sources: ChatSource[]
  model: string
}

export async function sendChat(message: string, horizon = 1): Promise<ChatResponse> {
  const res = await fetch(`${GUIDE_API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, horizon }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : 'CityGuide is unavailable'
    throw new Error(detail)
  }
  return res.json()
}
