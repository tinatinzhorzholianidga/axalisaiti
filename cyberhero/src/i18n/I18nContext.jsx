import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { getRuntime, langSwitchUrl } from '../lib/runtime.js'
import en from './en.js'
import ka from './ka.js'

const dicts = { en, ka }

const I18nContext = createContext(null)

/* The language is a server-side choice (Flask session, `<html lang>`): the
   shell tells us the active locale through data-locale, and switching
   navigates to `?lang=xx` so every part of the platform agrees. */
function detectLang(runtime) {
  if (typeof window !== 'undefined') {
    const fromQuery = new URLSearchParams(window.location.search).get('lang')
    if (fromQuery === 'en' || fromQuery === 'ka') return fromQuery
  }
  return runtime.locale === 'en' ? 'en' : 'ka'
}

function lookup(dict, key) {
  return key.split('.').reduce((node, part) => (node == null ? node : node[part]), dict)
}

export function I18nProvider({ children, initialLang, runtime = getRuntime(), navigate }) {
  const [lang, setLangState] = useState(() => initialLang || detectLang(runtime))

  useEffect(() => {
    if (typeof document !== 'undefined') document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback(
    (next) => {
      if (next !== 'en' && next !== 'ka') return
      setLangState(next)
      const url = langSwitchUrl(next, runtime)
      if (navigate) navigate(url)
      else if (typeof window !== 'undefined' && url) window.location.assign(url)
    },
    [runtime, navigate],
  )

  // t(): UI strings from the en/ka dictionaries, addressed by dot path
  const t = useCallback(
    (key) => {
      const value = lookup(dicts[lang], key) ?? lookup(dicts.en, key)
      return value ?? key
    },
    [lang],
  )

  // tx(): content leaves shaped as { en: ..., ka: ... }
  const tx = useCallback((node) => (node == null ? '' : typeof node === 'string' ? node : (node[lang] ?? node.en ?? '')), [lang])

  const value = useMemo(() => ({ lang, setLang, t, tx }), [lang, setLang, t, tx])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used inside I18nProvider')
  return ctx
}
