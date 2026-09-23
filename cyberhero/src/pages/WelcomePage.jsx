import { useRef } from 'react'
import { Link } from 'react-router-dom'
import Arrow from '../components/Arrow.jsx'
import { useContent } from '../content/ContentProvider.jsx'
import { useI18n } from '../i18n/I18nContext.jsx'
import { trackHint } from '../mascot/mascotContext.js'
import { useMascot } from '../mascot/MascotProvider.jsx'

// One uniform grid: every card the same size. The active sections
// (Cyber Guardians, Teachers & Parents) come first so they are seen.
// Hovering or focusing a card makes IO (the corner widget) say a hint about
// that track - the "track.<id>" reactions from the admin panel.
export function TierCard({ tier }) {
  const { t, tx } = useI18n()
  const { mascot } = useContent()
  const { peek, unpeek } = useMascot()
  const visits = useRef(0) // repeated hovers walk through the track's hints
  const to = tier.active ? tier.route || `/track/${tier.id}` : `/track/${tier.id}`
  const classes = ['tier-card', `tone-${tier.color}`, tier.active ? '' : 'is-soon'].filter(Boolean).join(' ')
  // admin-created tracks may leave the tag blank: skip the hollow pill
  // (the description span stays, it keeps the card heights aligned)
  const tag = tx(tier.tag)
  const desc = tx(tier.desc)

  const look = () => {
    const hint = trackHint(mascot, tier, visits.current)
    visits.current += 1
    if (hint) peek(hint, tier.active ? 'excited' : 'thinking')
  }

  return (
    <Link to={to} className={classes} onMouseEnter={look} onMouseLeave={unpeek} onFocus={look} onBlur={unpeek}>
      {tier.active && <span className="live-chip">{t('welcome.activeBadge')}</span>}
      <span className="emoji" aria-hidden="true">
        {tier.emoji}
      </span>
      {tag && <span className="tag">{tag}</span>}
      <h3>{tx(tier.name)}</h3>
      <span className="desc">{desc}</span>
      {tier.active ? (
        <span className="go">
          {t('welcome.start')} <Arrow />
        </span>
      ) : (
        <span className="soon-chip">🚧 {t('welcome.comingSoon')}</span>
      )}
    </Link>
  )
}

/** Active / featured tracks first, then the rest in their configured order. */
export function orderTiers(tiers, featured = []) {
  const rank = (tier) => {
    const idx = featured.indexOf(tier.id)
    if (idx >= 0) return idx
    return tier.active ? featured.length : featured.length + 1
  }
  return [...tiers].sort((a, b) => rank(a) - rank(b))
}

export default function WelcomePage() {
  const { t } = useI18n()
  const { tiers, featuredTracks } = useContent()
  const ordered = orderTiers(tiers, featuredTracks)
  return (
    <div className="fade-in">
      <section className="hero">
        <span className="sticker s1" aria-hidden="true">
          🛡️
        </span>
        <span className="sticker s2" aria-hidden="true">
          🔒
        </span>
        <span className="sticker s3" aria-hidden="true">
          ⭐
        </span>
        <span className="sticker s4" aria-hidden="true">
          📱
        </span>
        <span className="badge">✦ {t('welcome.badge')}</span>
        <h1>
          {t('welcome.title1')}
          <br />
          <span className="grad">{t('welcome.title2')}</span>
        </h1>
        <p>{t('welcome.sub')}</p>
      </section>

      <h2 className="section-label">{t('welcome.pick')}</h2>
      <div className="tier-grid">
        {ordered.map((tier) => (
          <TierCard key={tier.id} tier={tier} />
        ))}
      </div>

      <div className="home-links">
        <Link to="/courses" className="pill-link">
          📚 {t('courses.title')}
        </Link>
        <Link to="/emergency" className="pill-link">
          🆘 {t('emergency.title')}
        </Link>
      </div>
    </div>
  )
}
