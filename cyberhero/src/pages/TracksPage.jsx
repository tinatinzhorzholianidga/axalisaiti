import { Link } from 'react-router-dom'
import { useContent } from '../content/ContentProvider.jsx'
import { useI18n } from '../i18n/I18nContext.jsx'
import { orderTiers, TierCard } from './WelcomePage.jsx'

export default function TracksPage() {
  const { t } = useI18n()
  const { tiers, featuredTracks } = useContent()
  return (
    <div className="fade-in">
      <Link to="/" className="back-btn">
        ← {t('nav.back')}
      </Link>
      <div className="hub-head">
        <span className="emoji" aria-hidden="true">
          🗺️
        </span>
        <h1>{t('tracks.title')}</h1>
        <p>{t('tracks.intro')}</p>
      </div>
      <div className="tier-grid">
        {orderTiers(tiers, featuredTracks).map((tier) => (
          <TierCard key={tier.id} tier={tier} />
        ))}
      </div>
    </div>
  )
}
