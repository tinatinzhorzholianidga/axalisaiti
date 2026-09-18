import { Link } from 'react-router-dom'
import { ErrorState, Loading } from '../components/State.jsx'
import { useContent, useResources } from '../content/ContentProvider.jsx'
import { useI18n } from '../i18n/I18nContext.jsx'

function ResourceCard({ item, showContact }) {
  const { tx } = useI18n()
  const steps = tx(item.steps) || []
  return (
    <article className={`resource-card tone-${item.color || 'blue'}`}>
      <div className="top">
        <span className="emoji" aria-hidden="true">
          {item.emoji || '📌'}
        </span>
        <h3>{tx(item.title)}</h3>
      </div>
      {item.summary && <p>{tx(item.summary)}</p>}
      {showContact && item.contact_value && item.is_verified && (
        <p className="contact-value">
          <strong>{item.contact_value}</strong>
        </p>
      )}
      {steps.length > 0 && (
        <ol>
          {steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
      )}
    </article>
  )
}

/* Victim-first framing: the page tells a child or a parent what to do
   right now, with the emergency number configured by the administrators. */
export default function EmergencyPage() {
  const { t } = useI18n()
  const { settings } = useContent()
  const contacts = useResources('emergency_contact')
  const playbooks = useResources('playbook')

  return (
    <div className="fade-in emergency-page">
      <Link to="/" className="back-btn">
        ← {t('nav.back')}
      </Link>
      <div className="hub-head">
        <span className="emoji" aria-hidden="true">
          🆘
        </span>
        <h1>{t('emergency.title')}</h1>
        <p>{t('emergency.intro')}</p>
      </div>

      <section className="emergency-banner" aria-labelledby="emergency-call">
        <h2 id="emergency-call">{t('emergency.callTitle')}</h2>
        <a className="emergency-number" href={`tel:${settings.emergency_phone}`}>
          📞 {settings.emergency_phone}
        </a>
        <p>{t('emergency.callText')}</p>
        {settings.help_line && (
          <p>
            {t('footer.helpLine')}: <strong>{settings.help_line}</strong>
          </p>
        )}
        {settings.cybercrime_contact && (
          <p>
            {t('footer.cybercrime')}: <strong>{settings.cybercrime_contact}</strong>
          </p>
        )}
      </section>

      <section className="callout note emergency-steps">
        <div className="co-title">
          <span aria-hidden="true">💛</span>
          {t('emergency.firstTitle')}
        </div>
        <ol>
          {t('emergency.firstSteps').map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
      </section>

      <h2 className="section-label">{t('emergency.contacts')}</h2>
      {contacts.status === 'loading' && <Loading />}
      {contacts.status === 'error' && <ErrorState error={contacts.error} onRetry={contacts.reload} />}
      {contacts.status === 'ready' && (
        <div className="resource-grid">
          {contacts.data.items.map((item) => (
            <ResourceCard key={item.slug} item={item} showContact />
          ))}
          {contacts.data.items.length === 0 && <p className="u-soft">{t('emergency.noContacts')}</p>}
        </div>
      )}

      <h2 className="section-label">{t('emergency.playbooks')}</h2>
      {playbooks.status === 'loading' && <Loading />}
      {playbooks.status === 'error' && <ErrorState error={playbooks.error} onRetry={playbooks.reload} />}
      {playbooks.status === 'ready' && (
        <div className="resource-grid">
          {playbooks.data.items.map((item) => (
            <ResourceCard key={item.slug} item={item} />
          ))}
        </div>
      )}

      <div className="hub-cta">
        <span className="emoji" aria-hidden="true">
          🧭
        </span>
        <div className="body">
          <h2>{t('emergency.parentsCta')}</h2>
          <p>{t('emergency.parentsCtaText')}</p>
        </div>
        <Link to="/parents" className="btn-solid amber">
          {t('track.goParents')}
        </Link>
      </div>
    </div>
  )
}
