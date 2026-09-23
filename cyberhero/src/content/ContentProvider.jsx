// All CyberHero content (tracks, missions, courses, agreement, mascot,
// courses…) comes from the Flask API. This provider loads the bootstrap
// payload once and gives pages a small cached fetch helper.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { apiGet } from '../lib/api.js'
import { getRuntime } from '../lib/runtime.js'

const ContentContext = createContext(null)

const EMPTY_MASCOT = { tips: [], reactions: {}, missionTopics: {} }

export function ContentProvider({ children, runtime = getRuntime() }) {
  const [boot, setBoot] = useState({ status: 'loading', data: null, error: null })
  const [attempt, setAttempt] = useState(0)
  const cache = useRef(new Map())

  useEffect(() => {
    let cancelled = false
    setBoot((prev) => ({ ...prev, status: 'loading', error: null }))
    apiGet('/bootstrap', {}, { locale: runtime.locale })
      .then((data) => {
        if (!cancelled) setBoot({ status: 'ready', data, error: null })
      })
      .catch((error) => {
        if (!cancelled) setBoot({ status: 'error', data: null, error })
      })
    return () => {
      cancelled = true
    }
  }, [runtime.locale, attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  /** Fetch a resource once and keep it for the session. */
  const load = useCallback(
    (path, params) => {
      const key = params ? `${path}?${new URLSearchParams(params).toString()}` : path
      const hit = cache.current.get(key)
      if (hit) return hit
      const promise = apiGet(path, params || {}, { locale: runtime.locale }).catch((error) => {
        cache.current.delete(key)
        throw error
      })
      cache.current.set(key, promise)
      return promise
    },
    [runtime.locale],
  )

  const value = useMemo(() => {
    const data = boot.data || {}
    const tiers = data.tiers || []
    const tiersById = Object.fromEntries(tiers.map((tier) => [tier.id, tier]))
    return {
      runtime,
      status: boot.status,
      error: boot.error,
      retry,
      load,
      tiers,
      tiersById,
      parentsTier: tiersById.parents || null,
      featuredTracks: data.featured_tracks || [],
      mascot: data.mascot || EMPTY_MASCOT,
      settings: data.settings || {
        emergency_phone: runtime.emergencyPhone,
        cybercrime_contact: runtime.cybercrimeContact,
        help_line: runtime.helpLine,
      },
      flags: { ...runtime.flags, ...(data.flags || {}) },
      user: data.user || (runtime.userId ? { id: Number(runtime.userId), display_name: runtime.userName } : null),
    }
  }, [boot, runtime, retry, load])

  return <ContentContext.Provider value={value}>{children}</ContentContext.Provider>
}

export function useContent() {
  const ctx = useContext(ContentContext)
  if (!ctx) throw new Error('useContent must be used inside ContentProvider')
  return ctx
}

/**
 * Load one API resource. Returns { data, status, error, reload }.
 * `status` is 'loading' | 'ready' | 'error' | 'idle' (when `enabled` is false).
 */
export function useResource(path, params, { enabled = true } = {}) {
  const { load } = useContent()
  const key = `${path}|${params ? JSON.stringify(params) : ''}`
  const [state, setState] = useState({ key: null, data: null, status: enabled ? 'loading' : 'idle', error: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!enabled || !path) {
      setState({ key, data: null, status: 'idle', error: null })
      return undefined
    }
    let cancelled = false
    setState((prev) => (prev.key === key && prev.status === 'ready' ? prev : { key, data: null, status: 'loading', error: null }))
    load(path, params)
      .then((data) => {
        if (!cancelled) setState({ key, data, status: 'ready', error: null })
      })
      .catch((error) => {
        if (!cancelled) setState({ key, data: null, status: 'error', error })
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled, attempt, load])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  return { data: state.key === key ? state.data : null, status: state.key === key ? state.status : 'loading', error: state.error, reload }
}

/* Convenience hooks that mirror the original content modules */
export const useMissions = (track = 'guardians') => useResource('/missions', { track })
export const useMission = (slug) => useResource(slug ? `/missions/${encodeURIComponent(slug)}` : null)
export const useAgreement = () => useResource('/agreement')
export const useResources = (kind) => useResource(`/resources/${kind}`)
export const useCourses = (track) => useResource('/courses', track ? { track } : undefined)
export const useCourse = (slug) => useResource(slug ? `/courses/${encodeURIComponent(slug)}` : null)
export const useLesson = (course, lesson) =>
  useResource(course && lesson ? `/courses/${encodeURIComponent(course)}/lessons/${encodeURIComponent(lesson)}` : null)
export const useKnowledge = (enabled) => useResource('/knowledge', undefined, { enabled })

/** Points available in a mission (the API sends `max`; fall back to the round rule). */
export function missionMax(mission) {
  if (!mission) return 0
  if (typeof mission.max === 'number') return mission.max
  return (mission.rounds || []).reduce((sum, round) => {
    if (round.type === 'choice') return sum + 10
    if (round.type === 'flags') return sum + round.items.filter((i) => i.flag).length * 5
    if (round.type === 'builder') return sum + 15
    if (round.type === 'branch') return sum + (round.max || 0)
    return sum
  }, 0)
}
