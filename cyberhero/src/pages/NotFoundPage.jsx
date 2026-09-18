import { Link } from 'react-router-dom'
import { useI18n } from '../i18n/I18nContext.jsx'

export default function NotFoundPage() {
  const { t } = useI18n()
  return (
    <div className="fade-in state-box state-404">
      <span className="emoji" aria-hidden="true">
        🤖❓
      </span>
      <h1>{t('notFound.title')}</h1>
      <p>{t('notFound.text')}</p>
      <div className="links">
        <Link to="/" className="btn-solid">
          🏠 {t('nav.home')}
        </Link>
        <Link to="/guardians" className="pill-link">
          🛡️ {t('track.goGuardians')}
        </Link>
        <Link to="/parents" className="pill-link">
          🧭 {t('track.goParents')}
        </Link>
      </div>
    </div>
  )
}
