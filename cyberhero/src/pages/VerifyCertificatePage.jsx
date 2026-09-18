import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiGet, ApiError } from '../lib/api.js'
import { useI18n } from '../i18n/I18nContext.jsx'
import { useProgress } from '../store/progress.jsx'

/* Public verification of a CyberHero certificate (CH-YYYY-XXXXXXXX). */
export default function VerifyCertificatePage() {
  const { publicId } = useParams()
  const { t, tx } = useI18n()
  const { progress } = useProgress()
  const [value, setValue] = useState(publicId || progress.guardians.certificate?.public_id || '')
  const [result, setResult] = useState(null) // { status: 'ok'|'invalid'|'error', data }
  const [busy, setBusy] = useState(false)

  const check = async (id) => {
    const clean = (id || '').trim().toUpperCase()
    if (!clean) return
    setBusy(true)
    try {
      const data = await apiGet(`/certificates/${encodeURIComponent(clean)}`)
      setResult({ status: data.valid ? 'ok' : 'invalid', data })
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setResult({ status: 'invalid', data: null })
      else setResult({ status: 'error', data: null })
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (publicId) check(publicId)
  }, [publicId])

  return (
    <div className="fade-in u-narrow">
      <Link to="/" className="back-btn">
        ← {t('nav.back')}
      </Link>
      <div className="hub-head">
        <span className="emoji" aria-hidden="true">
          🔎
        </span>
        <h1>{t('verify.title')}</h1>
        <p>{t('verify.intro')}</p>
      </div>
      <form
        className="verify-form"
        onSubmit={(e) => {
          e.preventDefault()
          check(value)
        }}
      >
        <label htmlFor="cert-id" className="u-block u-bold u-mb-8">
          {t('verify.label')}
        </label>
        <div className="verify-row">
          <input
            id="cert-id"
            className="cert-input"
            type="text"
            value={value}
            maxLength={20}
            placeholder="CH-2026-XXXXXXXX"
            onChange={(e) => setValue(e.target.value)}
            autoComplete="off"
          />
          <button type="submit" className="btn-solid" disabled={busy || !value.trim()}>
            {t('verify.check')}
          </button>
        </div>
      </form>

      {result?.status === 'ok' && (
        <div className="feedback ok" role="status">
          <div className="f-title">
            <span aria-hidden="true">✅</span>
            {t('verify.valid')}
          </div>
          <dl className="verify-facts">
            <dt>{t('verify.name')}</dt>
            <dd>{result.data.display_name}</dd>
            <dt>{t('verify.track')}</dt>
            <dd>{tx(result.data.track_name)}</dd>
            <dt>{t('guardians.points')}</dt>
            <dd>
              {result.data.points} / {result.data.max_points}
            </dd>
            <dt>{t('verify.issued')}</dt>
            <dd>{new Date(result.data.issued_at).toLocaleDateString()}</dd>
            <dt>ID</dt>
            <dd>{result.data.public_id}</dd>
          </dl>
        </div>
      )}
      {result?.status === 'invalid' && (
        <div className="feedback bad" role="status">
          <div className="f-title">
            <span aria-hidden="true">⛔</span>
            {t('verify.invalid')}
          </div>
          <p>{t('verify.invalidText')}</p>
        </div>
      )}
      {result?.status === 'error' && (
        <div className="feedback bad" role="alert">
          <div className="f-title">
            <span aria-hidden="true">⚠️</span>
            {t('common.errorTitle')}
          </div>
          <p>{t('common.errorText')}</p>
        </div>
      )}
    </div>
  )
}
