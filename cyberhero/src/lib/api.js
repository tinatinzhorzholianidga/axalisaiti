// Tiny fetch wrapper for the CyberHero JSON API.
// - same-origin cookies (Flask session) are always sent
// - the `locale` query parameter follows the UI language
// - writes carry the CSRF token from <meta name="csrf-token"> (or the
//   /api/v1/auth/csrf endpoint) in the X-CSRFToken header
import { getRuntime } from './runtime.js'

export class ApiError extends Error {
  constructor(status, message, payload) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

let csrfToken = null

function metaCsrf() {
  if (typeof document === 'undefined') return null
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || null
}

export async function getCsrfToken() {
  if (csrfToken) return csrfToken
  csrfToken = metaCsrf()
  if (csrfToken) return csrfToken
  const response = await fetch('/api/v1/auth/csrf', { credentials: 'same-origin' })
  if (!response.ok) throw new ApiError(response.status, 'Could not obtain a CSRF token')
  const data = await response.json()
  csrfToken = data.csrf_token
  return csrfToken
}

/** Test helper. */
export function resetCsrfToken() {
  csrfToken = null
}

export function apiUrl(path, params = {}) {
  const { apiBase } = getRuntime()
  const [pathname, existing] = path.split('?')
  const search = new URLSearchParams(existing || '')
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== '') search.set(key, String(value))
  }
  const query = search.toString()
  return `${apiBase}${pathname.startsWith('/') ? pathname : `/${pathname}`}${query ? `?${query}` : ''}`
}

async function parse(response) {
  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }
  if (!response.ok) {
    const message = payload?.error?.message || `Request failed (${response.status})`
    throw new ApiError(response.status, message, payload)
  }
  return payload
}

export async function apiGet(path, params = {}, { locale } = {}) {
  const url = apiUrl(path, { locale, ...params })
  const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
  return parse(response)
}

async function write(method, path, body) {
  const token = await getCsrfToken()
  const response = await fetch(apiUrl(path), {
    method,
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': token,
    },
    body: JSON.stringify(body ?? {}),
  })
  return parse(response)
}

export const apiPost = (path, body) => write('POST', path, body)
export const apiPut = (path, body) => write('PUT', path, body)
