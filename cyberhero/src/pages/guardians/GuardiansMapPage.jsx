import { Link } from 'react-router-dom'
import { ErrorState, Loading } from '../../components/State.jsx'
import { missionMax, useMissions } from '../../content/ContentProvider.jsx'
import { useI18n } from '../../i18n/I18nContext.jsx'
import { useProgress } from '../../store/progress.jsx'

export default function GuardiansMapPage() {
  const { t, tx } = useI18n()
  const { progress, resetGuardians, syncState, signedIn } = useProgress()
  const list = useMissions('guardians')
  const missions = progress.guardians.missions

  if (list.status === 'loading') return <Loading />
  if (list.status !== 'ready') return <ErrorState error={list.error} onRetry={list.reload} />
  const MISSIONS = list.data.items

  const doneCount = MISSIONS.filter((m) => missions[m.id]?.done).length
  const totalPoints = MISSIONS.reduce((sum, m) => sum + (missions[m.id]?.best ?? 0), 0)
  const coreDone = MISSIONS.filter((m) => !m.final).every((m) => missions[m.id]?.done)
  const allDone = MISSIONS.length > 0 && doneCount === MISSIONS.length

  const handleReset = () => {
    if (window.confirm(t('guardians.resetConfirm'))) resetGuardians()
  }

  return (
    <div className="fade-in">
      <Link to="/" className="back-btn">
        ← {t('nav.back')}
      </Link>
      <div className="g-head">
        <span className="emoji" aria-hidden="true">
          🛡️
        </span>
        <h1>{t('guardians.title')}</h1>
        <div className="g-tag">{t('guardians.tag')}</div>
        <p className="g-intro">{t('guardians.intro')}</p>
      </div>

      <div className="g-statbar">
        <span className="g-stat">
          ⚡ {t('guardians.points')}: <span className="val">{totalPoints}</span>
        </span>
        <span className="g-stat">
          🎯 {t('guardians.missions')}:{' '}
          <span className="val">
            {doneCount}/{MISSIONS.length}
          </span>
        </span>
        {signedIn && (
          <span className="g-stat g-sync" data-state={syncState}>
            {syncState === 'error' ? '⚠️ ' + t('guardians.syncError') : '☁️ ' + t('guardians.synced')}
          </span>
        )}
      </div>

      <div className="mission-grid">
        {MISSIONS.map((mission) => {
          const state = missions[mission.id]
          const locked = mission.final && !coreDone
          const classes = ['mission-card', `tone-${mission.color}`, state?.done ? 'done' : '', locked ? 'locked' : '']
            .filter(Boolean)
            .join(' ')
          const inner = (
            <>
              <span className="corner tl" aria-hidden="true" />
              <span className="corner tr" aria-hidden="true" />
              <span className="corner bl" aria-hidden="true" />
              <span className="corner br" aria-hidden="true" />
              <div className="m-top">
                <span className="m-ic" aria-hidden="true">
                  {locked ? '🔒' : mission.emoji}
                </span>
                <span className="m-num">
                  {t('guardians.mission')} {String(mission.order).padStart(2, '0')}
                </span>
              </div>
              <h3>{tx(mission.name)}</h3>
              <p className="m-desc">{locked ? t('guardians.locked') : tx(mission.desc)}</p>
              <div className="m-state">
                <span>{locked ? t('guardians.lockedShort') : state?.done ? `↻ ${t('guardians.replay')}` : `${t('guardians.start')} →`}</span>
                {state?.done && (
                  <span className="m-score">
                    ✓ {state.best}/{missionMax(mission)}
                  </span>
                )}
              </div>
            </>
          )
          if (locked) {
            return (
              <div key={mission.id} className={classes} aria-disabled="true">
                {inner}
              </div>
            )
          }
          return (
            <Link key={mission.id} to={`/guardians/mission/${mission.id}`} className={classes}>
              {inner}
            </Link>
          )
        })}
      </div>

      <div className="g-statbar u-mt-30">
        {allDone ? (
          <Link to="/guardians/certificate" className="btn-solid">
            🏆 {t('guardians.getCert')}
          </Link>
        ) : (
          <span className="g-stat">🏆 {t('guardians.certProgress')}</span>
        )}
      </div>

      {(doneCount > 0 || totalPoints > 0) && (
        <p className="u-center u-mt-18">
          <button type="button" className="pill-link as-btn" onClick={handleReset}>
            {t('guardians.resetProgress')}
          </button>
        </p>
      )}
    </div>
  )
}
