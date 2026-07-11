import { useState, type FormEvent } from 'react'
import {
  isAddressSearchResult,
  lookupForecastAtPoint,
  searchForecastByAddress,
  type AddressSearchCandidate,
  type AddressSearchResult,
} from '../lib/api'
import styles from '../pages/CityForesight.module.css'

const DISCLAIMER =
  'Neighborhood estimate based on census tract data and airport weather — not a reading at your exact address.'

type Props = {
  onResolved: (result: AddressSearchResult) => void
  disabled?: boolean
}

export default function AddressSearch({ onResolved, disabled }: Props) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [candidates, setCandidates] = useState<AddressSearchCandidate[] | null>(null)

  const runSearch = async (searchQuery: string) => {
    const trimmed = searchQuery.trim()
    if (trimmed.length < 3) {
      setError('Enter at least 3 characters')
      return
    }
    setLoading(true)
    setError(null)
    setCandidates(null)
    try {
      const response = await searchForecastByAddress(trimmed)
      if (isAddressSearchResult(response)) {
        onResolved(response)
        return
      }
      if (response.candidates.length === 1) {
        const c = response.candidates[0]
        const resolved = await lookupForecastAtPoint(c.lat, c.lon, trimmed)
        onResolved(resolved)
        return
      }
      setCandidates(response.candidates)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void runSearch(query)
  }

  const onPickCandidate = async (c: AddressSearchCandidate) => {
    setLoading(true)
    setError(null)
    try {
      const resolved = await lookupForecastAtPoint(c.lat, c.lon, query.trim() || undefined)
      setCandidates(null)
      onResolved(resolved)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Lookup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.searchGroup}>
      <span className={styles.toolbarLabel}>Find your area</span>
      <form className={styles.searchRow} onSubmit={onSubmit}>
        <input
          type="search"
          className={styles.searchInput}
          placeholder="Enter address or place in Austin"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={disabled || loading}
          aria-label="Search address or place"
        />
        <button
          type="submit"
          className={styles.searchButton}
          disabled={disabled || loading}
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>
      <p className={styles.searchDisclaimer}>{DISCLAIMER}</p>
      {error && (
        <p className={styles.searchError} role="alert">
          {error}
        </p>
      )}
      {candidates && candidates.length > 1 && (
        <ul className={styles.searchCandidates} aria-label="Matching addresses">
          {candidates.map((c) => (
            <li key={`${c.lat}-${c.lon}`}>
              <button
                type="button"
                className={styles.searchCandidateBtn}
                onClick={() => void onPickCandidate(c)}
                disabled={loading}
              >
                {c.matched_address}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export { DISCLAIMER as ADDRESS_SEARCH_DISCLAIMER }
