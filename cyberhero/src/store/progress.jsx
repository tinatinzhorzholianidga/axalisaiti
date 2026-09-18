import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { apiGet, apiPut } from '../lib/api.js'
import { useContent } from '../content/ContentProvider.jsx'

const STORAGE_KEY = 'cyberhero.progress.v1'

const initial = {
  guardians: {
    // missions: { g1: { done: true, best: 40, total: 60 }, ... }
    missions: {},
    certName: '',
    certificate: null, // { public_id, issued_at, verify_url } once claimed
  },
  lessons: {}, // 'course-slug/lesson-slug': { done: true }
}

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return initial
    const parsed = JSON.parse(raw)
    return {
      ...initial,
      ...parsed,
      guardians: { ...initial.guardians, ...(parsed.guardians || {}) },
      lessons: { ...(parsed.lessons || {}) },
    }
  } catch {
    return initial
  }
}

/** Merge two progress trees: best score wins, `done` never regresses. */
export function mergeProgress(local, remote) {
  const missions = { ...local.guardians.missions }
  for (const [id, state] of Object.entries(remote?.guardians?.missions || {})) {
    const mine = missions[id]
    missions[id] = {
      done: Boolean(mine?.done || state?.done),
      best: Math.max(mine?.best ?? 0, state?.best ?? 0),
      total: Math.max(mine?.total ?? 0, state?.total ?? 0),
    }
  }
  const lessons = { ...local.lessons }
  for (const [key, state] of Object.entries(remote?.lessons || {})) {
    if (state?.done) lessons[key] = { done: true }
  }
  return { ...local, guardians: { ...local.guardians, missions }, lessons }
}

const ProgressContext = createContext(null)

export function ProgressProvider({ children }) {
  const { user } = useContent()
  const [progress, setProgress] = useState(load)
  const [syncState, setSyncState] = useState('local') // local | syncing | synced | error
  const userId = user?.id || null
  const pending = useRef([])

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(progress))
    } catch {
      /* private mode - progress just won't persist */
    }
  }, [progress])

  // signed-in learners: pull the server copy once and merge it in
  useEffect(() => {
    if (!userId) return undefined
    let cancelled = false
    setSyncState('syncing')
    apiGet('/progress')
      .then((remote) => {
        if (cancelled) return
        setProgress((prev) => mergeProgress(prev, remote))
        setSyncState('synced')
      })
      .catch(() => {
        if (!cancelled) setSyncState('error')
      })
    return () => {
      cancelled = true
    }
  }, [userId])

  const push = useCallback(
    (payload) => {
      if (!userId) return
      pending.current.push(payload)
      const flush = pending.current.splice(0)
      const merged = { guardians: { missions: {} }, lessons: {} }
      for (const item of flush) {
        Object.assign(merged.guardians.missions, item.guardians?.missions || {})
        Object.assign(merged.lessons, item.lessons || {})
      }
      setSyncState('syncing')
      apiPut('/progress', merged)
        .then((remote) => {
          setProgress((prev) => mergeProgress(prev, remote))
          setSyncState('synced')
        })
        .catch(() => setSyncState('error'))
    },
    [userId],
  )

  const recordMission = useCallback(
    (missionId, { score, total }) => {
      let entry = null
      setProgress((prev) => {
        const existing = prev.guardians.missions[missionId]
        const best = Math.max(existing?.best ?? 0, score)
        entry = { done: true, best, total }
        return {
          ...prev,
          guardians: { ...prev.guardians, missions: { ...prev.guardians.missions, [missionId]: entry } },
        }
      })
      push({ guardians: { missions: { [missionId]: entry || { done: true, best: score, total } } } })
    },
    [push],
  )

  const markLesson = useCallback(
    (courseSlug, lessonSlug) => {
      const key = `${courseSlug}/${lessonSlug}`
      setProgress((prev) => ({ ...prev, lessons: { ...prev.lessons, [key]: { done: true } } }))
      push({ lessons: { [key]: { done: true } } })
    },
    [push],
  )

  const setCertName = useCallback((certName) => {
    setProgress((prev) => ({ ...prev, guardians: { ...prev.guardians, certName } }))
  }, [])

  const setCertificate = useCallback((certificate) => {
    setProgress((prev) => ({ ...prev, guardians: { ...prev.guardians, certificate } }))
  }, [])

  const resetGuardians = useCallback(() => {
    setProgress((prev) => ({ ...prev, guardians: { ...initial.guardians } }))
  }, [])

  return (
    <ProgressContext.Provider
      value={{ progress, recordMission, markLesson, setCertName, setCertificate, resetGuardians, syncState, signedIn: Boolean(userId) }}
    >
      {children}
    </ProgressContext.Provider>
  )
}

export function useProgress() {
  const ctx = useContext(ProgressContext)
  if (!ctx) throw new Error('useProgress must be used inside ProgressProvider')
  return ctx
}
