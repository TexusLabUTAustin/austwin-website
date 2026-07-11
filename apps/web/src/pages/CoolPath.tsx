import { useEffect } from 'react'

const COOLPATH_URL = 'https://coolest-route-planner.vercel.app/'

export default function CoolPathRedirect() {
  useEffect(() => {
    window.location.replace(COOLPATH_URL)
  }, [])

  return (
    <p
      style={{
        padding: '2rem',
        textAlign: 'center',
        color: '#5c6c7d',
      }}
    >
      Redirecting…
    </p>
  )
}
