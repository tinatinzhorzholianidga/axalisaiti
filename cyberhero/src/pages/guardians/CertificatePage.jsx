import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { ErrorState, Loading } from '../../components/State.jsx'
import { missionMax, useContent, useMissions } from '../../content/ContentProvider.jsx'
import { useI18n } from '../../i18n/I18nContext.jsx'
import { apiPost } from '../../lib/api.js'
import { useProgress } from '../../store/progress.jsx'

// Format Georgian dates by hand - not every browser ships the ka locale,
// and the silent fallback would print an English date on the certificate.
const MONTHS_KA = ['იანვარი', 'თებერვალი', 'მარტი', 'აპრილი', 'მაისი', 'ივნისი', 'ივლისი', 'აგვისტო', 'სექტემბერი', 'ოქტომბერი', 'ნოემბერი', 'დეკემბერი']

export function formatCertDate(date, lang) {
  return lang === 'ka'
    ? `${date.getDate()} ${MONTHS_KA[date.getMonth()]}, ${date.getFullYear()}`
    : date.toLocaleDateString('en-GB', { year: 'numeric', month: 'long', day: 'numeric' })
}

export default function CertificatePage() {
  const { t, lang } = useI18n()
  const { runtime } = useContent()
  const { progress, setCertName, setCertificate } = useProgress()
  const list = useMissions('guardians')
  const [claim, setClaim] = useState({ busy: false, error: null })
  const missions = progress.guardians.missions
  const certificate = progress.guardians.certificate

  if (list.status === 'loading') return <Loading />
  if (list.status !== 'ready') return <ErrorState error={list.error} onRetry={list.reload} />
  const MISSIONS = list.data.items

  const allDone = MISSIONS.length > 0 && MISSIONS.every((m) => missions[m.id]?.done)
  if (!allDone && !certificate) return <Navigate to="/guardians" replace />

  const totalPoints = MISSIONS.reduce((sum, m) => sum + (missions[m.id]?.best ?? 0), 0)
  const totalMax = MISSIONS.reduce((sum, m) => sum + missionMax(m), 0)
  const issued = certificate ? new Date(certificate.issued_at) : new Date()
  const date = formatCertDate(issued, lang)
  const name = certificate?.display_name || progress.guardians.certName

  const claimCertificate = async () => {
    setClaim({ busy: true, error: null })
    try {
      const data = await apiPost('/certificates', {
        track: 'guardians',
        display_name: progress.guardians.certName,
        completed_missions: missions,
      })
      setCertificate(data)
      setClaim({ busy: false, error: null })
    } catch (err) {
      setClaim({ busy: false, error: err?.message || t('common.errorText') })
    }
  }

  const verifyPath = certificate ? `/certificate/${certificate.public_id}` : null
  const verifyUrl = certificate ? `${window.location.origin}${runtime.siteBase.replace(/\/$/, '')}${certificate.verify_url}` : null

  return (
    <div className="fade-in u-narrow">
      <Link to="/guardians" className="back-btn">
        ← {t('guardians.backToMap')}
      </Link>

      <p className="u-center u-soft u-mb-18">🎉 {t('guardians.certUnlocked')}</p>

      {!certificate && (
        <div className="no-print u-center u-mb-18">
          <label htmlFor="cert-name" className="u-block u-bold u-mb-8">
            {t('guardians.certNameLabel')}
          </label>
          <input
            id="cert-name"
            className="cert-input"
            type="text"
            maxLength={60}
            value={progress.guardians.certName}
            placeholder={t('guardians.certNamePlaceholder')}
            onChange={(e) => setCertName(e.target.value)}
          />
        </div>
      )}

      <div className="cert-sheet">
        <div className="medal" aria-hidden="true">
          🛡️🏆🛡️
        </div>
        <h1>{t('guardians.certTitle')}</h1>
        <div className="c-sub">CyberHero · კიბერგმირი</div>
        <div>{t('guardians.certifies')}</div>
        <div className="c-name">{name || ' '}</div>
        <p className="c-body">{t('guardians.certBody')}</p>
        <div className="c-score">
          ⚡ {t('guardians.points')}: {certificate ? `${certificate.points} / ${certificate.max_points}` : `${totalPoints} / ${totalMax}`}
        </div>
        <div className="c-date">{date}</div>
        {certificate && (
          <div className="c-verify">
            <span>ID: {certificate.public_id}</span>
            <span>{verifyUrl}</span>
          </div>
        )}
      </div>

      <div className="article-actions no-print u-justify-center u-mt-20">
        {!certificate && (
          <button type="button" className="btn-solid" disabled={claim.busy || progress.guardians.certName.trim().length < 2} onClick={claimCertificate}>
            {claim.busy ? '⏳' : '🎖️'} {t('guardians.claimCert')}
          </button>
        )}
        {certificate && (
          <Link to={verifyPath} className="pill-link">
            🔎 {t('verify.title')}
          </Link>
        )}
        <button type="button" className={certificate ? 'btn-solid' : 'btn-ghost'} onClick={() => window.print()}>
          🖨️ {t('guardians.print')}
        </button>
      </div>
      {claim.error && (
        <p className="io-warn no-print" role="alert">
          ⚠️ {claim.error}
        </p>
      )}
      {!certificate && <p className="u-center u-soft no-print u-mt-10">{t('guardians.claimHint')}</p>}
    </div>
  )
}
