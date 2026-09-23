import { Link, Navigate, useParams } from 'react-router-dom'
import { ErrorState, Loading } from '../../components/State.jsx'
import { useLesson } from '../../content/ContentProvider.jsx'
import { useI18n } from '../../i18n/I18nContext.jsx'
import { useProgress } from '../../store/progress.jsx'

export default function LessonPage() {
  const { course, lesson: lessonSlug } = useParams()
  const { t, tx } = useI18n()
  const { progress, markLesson } = useProgress()
  const { data: lesson, status, error, reload } = useLesson(course, lessonSlug)

  if (status === 'error' && error?.status === 404) return <Navigate to={`/course/${course}`} replace />
  if (status === 'loading') return <Loading />
  if (status !== 'ready') return <ErrorState error={error} onRetry={reload} />

  const key = `${course}/${lesson.slug}`
  const done = Boolean(progress.lessons[key]?.done)
  const html = tx(lesson.content)

  return (
    <div className="article-wrap fade-in lesson-page">
      <Link to={`/course/${course}`} className="back-btn">
        ← {t('courses.backToCourse')}
      </Link>
      <article className="article-paper">
        <div className="kicker">
          <span aria-hidden="true">📖</span>
          <span>{tx(lesson.module_title)}</span>
          <span>
            {t('courses.lesson')} {lesson.index} / {lesson.total}
          </span>
          {lesson.minutes ? (
            <span>
              {lesson.minutes} {t('courses.min')}
            </span>
          ) : null}
        </div>
        <h1>{tx(lesson.title)}</h1>
        {tx(lesson.summary) && <p className="lead">{tx(lesson.summary)}</p>}
        {/* Sanitised server-side (nh3 allow-list); the API never returns raw author HTML. */}
        <div className="article-body" dangerouslySetInnerHTML={{ __html: html }} />

        <div className="article-actions lesson-actions">
          <button type="button" className="btn-ghost" onClick={() => window.print()}>
            🖨️ {t('parents.printThis')}
          </button>
          {done ? (
            <span className="feedback ok lesson-done" role="status">
              ✅ {t('courses.done')}
            </span>
          ) : (
            <button type="button" className="btn-solid" onClick={() => markLesson(course, lesson.slug)}>
              ✅ {t('courses.markDone')}
            </button>
          )}
        </div>
        <nav className="lesson-nav" aria-label={t('courses.lessonNav')}>
          {lesson.prev ? (
            <Link className="pill-link" to={`/learn/${course}/${lesson.prev.slug}`}>
              ← {tx(lesson.prev.title)}
            </Link>
          ) : (
            <span />
          )}
          {lesson.next ? (
            <Link className="pill-link" to={`/learn/${course}/${lesson.next.slug}`}>
              {tx(lesson.next.title)} →
            </Link>
          ) : (
            <Link className="pill-link" to={`/course/${course}`}>
              {t('courses.finish')} 🎉
            </Link>
          )}
        </nav>
      </article>
    </div>
  )
}
