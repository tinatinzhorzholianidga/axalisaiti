import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, Loading } from '../../components/State.jsx'
import { useCourses } from '../../content/ContentProvider.jsx'
import { useI18n } from '../../i18n/I18nContext.jsx'
import { useProgress } from '../../store/progress.jsx'

export function CourseCard({ course }) {
  const { t, tx } = useI18n()
  const { progress } = useProgress()
  const done = Object.keys(progress.lessons).filter((key) => key.startsWith(`${course.slug}/`) && progress.lessons[key]?.done).length
  return (
    <Link to={`/course/${course.slug}`} className={`article-card course-card tone-${course.color}`}>
      <span className="top">
        <span className="emoji" aria-hidden="true">
          {course.emoji_char || '📚'}
        </span>
        <span className="meta">
          {course.lesson_count} {t('courses.lessons')}
          {course.mission_count ? ` · ${course.mission_count} ${t('courses.missions')}` : ''}
          {course.estimated_minutes ? ` · ${course.estimated_minutes} ${t('courses.min')}` : ''}
        </span>
        {course.is_featured && <span className="priority-chip">{t('courses.featured')}</span>}
      </span>
      <h3>{tx(course.title)}</h3>
      <span className="teaser">{tx(course.short_description)}</span>
      {course.lesson_count > 0 && (
        <span className="meter course-meter" role="progressbar" aria-valuenow={done} aria-valuemin={0} aria-valuemax={course.lesson_count}>
          <span className="fill" data-value={Math.round((done / course.lesson_count) * 20) * 5} />
        </span>
      )}
    </Link>
  )
}

export default function CoursesPage() {
  const { t } = useI18n()
  const courses = useCourses()
  return (
    <div className="fade-in">
      <Link to="/" className="back-btn">
        ← {t('nav.back')}
      </Link>
      <div className="hub-head">
        <span className="emoji" aria-hidden="true">
          📚
        </span>
        <h1>{t('courses.title')}</h1>
        <p>{t('courses.intro')}</p>
      </div>
      {courses.status === 'loading' && <Loading />}
      {courses.status === 'error' && <ErrorState error={courses.error} onRetry={courses.reload} />}
      {courses.status === 'ready' && courses.data.items.length === 0 && <EmptyState emoji="📚">{t('courses.empty')}</EmptyState>}
      {courses.status === 'ready' && courses.data.items.length > 0 && (
        <div className="article-grid">
          {courses.data.items.map((course) => (
            <CourseCard key={course.slug} course={course} />
          ))}
        </div>
      )}
    </div>
  )
}
