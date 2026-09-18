import { Link } from 'react-router-dom'
import { useContent } from '../content/ContentProvider.jsx'
import { useI18n } from '../i18n/I18nContext.jsx'

export default function Header() {
  const { t, lang, setLang } = useI18n()
  const { runtime, user } = useContent()
  return (
    <header className="site-header">
      <Link to="/" className="brand">
        <span className="brand-logo" aria-hidden="true">
          🛡️
        </span>
        <span>
          {t('brand.name')}
          <small>{t('brand.tag')}</small>
        </span>
      </Link>
      <nav className="host-links" aria-label={t('nav.platformLabel')}>
        <a className="host-link" href={runtime.siteBase}>
          ← {t('nav.elearning')}
        </a>
        {user ? (
          <span className="host-user" title={user.display_name}>
            👤 {user.display_name}
          </span>
        ) : (
          <a className="host-link" href={runtime.loginUrl}>
            {t('nav.signIn')}
          </a>
        )}
      </nav>
      <div className="lang-toggle" role="group" aria-label={t('nav.languageLabel')}>
        <button type="button" className={lang === 'en' ? 'active' : ''} aria-pressed={lang === 'en'} onClick={() => setLang('en')}>
          EN
        </button>
        <button type="button" className={lang === 'ka' ? 'active' : ''} aria-pressed={lang === 'ka'} onClick={() => setLang('ka')}>
          ქარ
        </button>
      </div>
    </header>
  )
}
