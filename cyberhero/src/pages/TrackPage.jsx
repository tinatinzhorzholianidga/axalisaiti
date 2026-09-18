import { Link, Navigate, useParams } from 'react-router-dom'
import { useContent } from '../content/ContentProvider.jsx'
import { useI18n } from '../i18n/I18nContext.jsx'

export default function TrackPage() {
  const { tierId } = useParams()
  const { t, tx } = useI18n()
  const { tiersById } = useContent()
  const tier = tiersById[tierId]

  if (!tier) return <Navigate to="/" replace />
  if (tier.active && tier.route) return <Navigate to={tier.route} replace />

  return (
    <div className={`detail fade-in tone-${tier.color}`}>
      <Link to="/" className="back-btn">
        ← {t('nav.back')}
      </Link>
      <div className="detail-head">
        <span className="emoji" aria-hidden="true">
          {tier.emoji}
        </span>
        <div>
          <div className="tag">{tx(tier.tag)}</div>
          <h2 className="tone-text">{tx(tier.name)}</h2>
        </div>
      </div>
      <p className="detail-intro">{tx(tier.intro)}</p>
      <h3 className="topic-list-label">{t('track.learn')}</h3>
      <ul className="topic-list">
        {(tx(tier.topics) || []).map((topic, i) => (
          <li key={i}>
            <span className="n" aria-hidden="true">
              {i + 1}
            </span>
            <span>{topic}</span>
          </li>
        ))}
      </ul>
      <div className="soon-banner">
        <p>🚧 {t('track.soon')}</p>
        <div className="links">
          <Link className="pill-link" to="/guardians">
            🛡️ {t('track.goGuardians')}
          </Link>
          <Link className="pill-link" to="/parents">
            🧭 {t('track.goParents')}
          </Link>
        </div>
      </div>
    </div>
  )
}
