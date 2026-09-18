// Runtime configuration for the CyberHero app. The Flask shell (and the dev
// index.html) put everything the app needs on `#cyberhero-root` as data-*
// attributes, so no inline <script> is ever needed (strict CSP).

const DEFAULTS = {
  basename: '/cyberhero',
  locale: 'ka',
  apiBase: '/api/v1/cyberhero',
  staticBase: '/static/cyberhero',
  siteBase: '/',
  loginUrl: '/auth/login',
  userName: '',
  userId: '',
  flags: {},
  emergencyPhone: '112',
  cybercrimeContact: '',
  helpLine: '',
  tutorModelUrl: '',
  langSwitch: { ka: '', en: '' },
}

let cached = null

function parseFlags(raw) {
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

/** Read the runtime from a root element (defaults to `#cyberhero-root`). */
export function readRuntime(root) {
  const el = root || (typeof document !== 'undefined' ? document.getElementById('cyberhero-root') : null)
  const ds = el?.dataset || {}
  const basename = (ds.basename || DEFAULTS.basename).replace(/\/+$/, '') || ''
  return {
    ...DEFAULTS,
    basename,
    locale: ds.locale === 'en' ? 'en' : 'ka',
    apiBase: (ds.apiBase || DEFAULTS.apiBase).replace(/\/+$/, ''),
    staticBase: (ds.staticBase || DEFAULTS.staticBase).replace(/\/+$/, ''),
    siteBase: ds.siteBase || DEFAULTS.siteBase,
    loginUrl: ds.loginUrl || DEFAULTS.loginUrl,
    userName: ds.userName || '',
    userId: ds.userId || '',
    flags: parseFlags(ds.flags),
    emergencyPhone: ds.emergencyPhone || DEFAULTS.emergencyPhone,
    cybercrimeContact: ds.cybercrimeContact || '',
    helpLine: ds.helpLine || '',
    tutorModelUrl: ds.tutorModelUrl || '',
    langSwitch: { ka: ds.langSwitchKa || '', en: ds.langSwitchEn || '' },
  }
}

export function getRuntime() {
  if (!cached) cached = readRuntime()
  return cached
}

/** Test helper: forget the cached runtime. */
export function resetRuntime() {
  cached = null
}

/** Build the URL that switches the server-side locale and reloads this page. */
export function langSwitchUrl(lang, runtime = getRuntime()) {
  if (typeof window === 'undefined') return runtime.langSwitch[lang] || ''
  const url = new URL(window.location.href)
  url.searchParams.set('lang', lang)
  return `${url.pathname}${url.search}`
}
