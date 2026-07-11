import { useEffect } from 'react'

const THERMALSCAPE_URL = 'https://tinyurl.com/colabthermalvr'

export default function ThermalscapeRedirect() {
  useEffect(() => {
    window.location.replace(THERMALSCAPE_URL)
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
