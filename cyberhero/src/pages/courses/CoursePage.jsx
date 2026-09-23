import { Link, Navigate, useParams } from 'react-router-dom'
import { ErrorState, Loading } from '../../components/State.jsx'
import { useCourse } from '../../content/ContentProvider.jsx'
import { useI18n } from '../../i18n/I18nContext.jsx'
import { useProgress } from '../../store/progress.jsx'

const LESSON_ICON = { reading: '📖', video: '🎬', quiz: '❓', lab: '🧪', assignment: '📝' }

export default function CoursePage() {
  const { slug } = useParams()
  const { t, tx } = useI18n()
  const { progress } = useProgress()
  const { data: course, status, error, reload } = useCourse(slug)

  if (status === 'error' && error?.status === 404) return <Navigate to="/courses" replace />
  if (status === 'loading') return <Loading />
  if (status !== 'ready') return <ErrorState error={error} onRetry={reload} />

  const lessons = course.modules.flatMap((m) => m.lessons)
  const doneCount = lessons.filter((l) => progress.lessons[`${course.slug}/${l.slug}`]?.done).length
  const objectives = tx(course.objectives) || []
  const firstLesson = lessons[0]

  return (
    <div className={`detail fade-in course-page tone-${course.color}`}>
      <Link to="/courses" className="back-btn">
        ← {t('courses.title')}
      </Link>
      <div className="detail-head">
        <span className="emoji" aria-hidden="true">
          📚
        </span>
        <div>
          <div className="tag">
            {t(`courses.level.${course.difficulty}`)}
            {course.estimated_minutes ? ` · ${course.estimated_minutes} ${t('courses.min')}` : ''}
            {course.age_min ? ` · ${course.age_min}${course.age_max ? `-${course.age_max}` : '+'} ${t('courses.years')}` : ''}
          </div>
          <h2 className="tone-text">{tx(course.title)}</h2>
        </div>
      </div>
      <p className="detail-intro">{tx(course.short_description)}</p>
      {/* Lesson HTML is sanitised server-side (nh3 allow-list) before it reaches the API. */}
      {tx(course.description_html) && <div className="article-body course-desc" dangerouslySetInnerHTML={{ __html: tx(course.description_html) }} />}

      {objectives.length > 0 && (
        <>
          <h3 className="topic-list-label">{t('track.learn')}</h3>
          <ul className="topic-list">
            {objectives.map((topic, i) => (
              <li key={i}>
                <span className="n" aria-hidden="true">
                  {i + 1}
                </span>
                <span>{topic}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="g-statbar">
        <span className="g-stat">
          📖 {t('courses.lessons')}:{' '}
          <span className="val">
            {doneCount}/{lessons.length}
          </span>
        </span>
        {firstLesson && (
          <Link to={`/learn/${course.slug}/${firstLesson.slug}`} className="btn-solid">
            {doneCount === 0 ? t('courses.startCourse') : t('courses.continueCourse')} →
          </Link>
        )}
      </div>

      {course.modules.map((module, mi) => (
        <section key={module.slug} className="module-box" aria-labelledby={`module-${mi}`}>
          <h3 id={`module-${mi}`}>
            {mi + 1}. {tx(module.title)}
          </h3>
          {tx(module.description) && <p className="u-soft">{tx(module.description)}</p>}
          <ol className="lesson-list">
            {module.lessons.map((lesson) => {
              const done = progress.lessons[`${course.slug}/${lesson.slug}`]?.done
              return (
                <li key={lesson.slug} className={done ? 'done' : ''}>
                  <Link to={`/learn/${course.slug}/${lesson.slug}`}>
                    <span className="l-ic" aria-hidden="true">
                      {done ? '✅' : LESSON_ICON[lesson.type] || '📖'}
                    </span>
                    <span className="l-title">{tx(lesson.title)}</span>
                    {lesson.minutes ? (
                      <span className="l-min">
                        {lesson.minutes} {t('courses.min')}
                      </span>
                    ) : null}
                  </Link>
                </li>
              )
            })}
          </ol>
        </section>
      ))}

      {course.track === 'parents' && (
        <>
          <div className="hub-cta">
            <span className="emoji" aria-hidden="true">
              📝
            </span>
            <div className="body">
              <h2>{t('parents.agreementCta')}</h2>
              <p>{t('parents.agreementCtaText')}</p>
            </div>
            <Link to="/parents/agreement" className="btn-solid amber">
              {t('parents.openAgreement')}
            </Link>
          </div>
          <div className="hub-cta">
            <span className="emoji" aria-hidden="true">
              🆘
            </span>
            <div className="body">
              <h2>{t('emergency.title')}</h2>
              <p>{t('emergency.intro')}</p>
            </div>
            <Link to="/emergency" className="btn-solid">
              {t('emergency.open')}
            </Link>
          </div>
        </>
      )}

      {course.missions.length > 0 && (
        <section className="module-box" aria-labelledby="course-missions">
          <h3 id="course-missions">🎯 {t('courses.practice')}</h3>
          <div className="mission-grid compact">
            {course.missions.map((mission) => (
              <Link key={mission.id} to={`/guardians/mission/${mission.id}`} className={`mission-card tone-${mission.color}`}>
                <div className="m-top">
                  <span className="m-ic" aria-hidden="true">
                    {mission.emoji}
                  </span>
                  <span className="m-num">
                    {t('guardians.mission')} {String(mission.order).padStart(2, '0')}
                  </span>
                </div>
                <h3>{tx(mission.name)}</h3>
                <p className="m-desc">{tx(mission.desc)}</p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
