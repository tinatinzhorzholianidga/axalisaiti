import { Link } from 'react-router-dom'
import { useContent } from '../content/ContentProvider.jsx'
import { useI18n } from '../i18n/I18nContext.jsx'

export default function Footer() {
  const { t } = useI18n()
  const { settings, runtime } = useContent()
  return (
    <footer className="site-footer">
      <p>{t('footer.line')}</p>
      <p>
        {t('footer.emergency')}: <strong>{settings.emergency_phone}</strong>
        {settings.help_line ? ` · ${t('footer.helpLine')}: ${settings.help_line}` : ''}
        {settings.cybercrime_contact ? ` · ${t('footer.cybercrime')}: ${settings.cybercrime_contact}` : ''}
      </p>
      <p className="footer-links">
        <Link to="/emergency">🆘 {t('emergency.title')}</Link>
        <Link to="/certificate">🔎 {t('verify.title')}</Link>
        <a href={runtime.siteBase}>{t('nav.elearning')}</a>
      </p>
    </footer>
  )
}
