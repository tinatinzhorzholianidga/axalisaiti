import { Navigate, useParams } from 'react-router-dom'
import { useContent } from '../../content/ContentProvider.jsx'

/** Where the Teachers & Parents track lives now (its route is admin data, e.g. `/course/teachers-parents`). */
export function parentsCourseSlug(tiersById) {
  const route = tiersById?.parents?.route || ''
  const match = route.match(/^\/course\/([^/]+)/)
  return match ? match[1] : null
}

/** Legacy `/parents`, `/parents/<article>` and `/articles/...` links: the
 *  article ids became lesson slugs of the parents course. */
export function ParentsCourseRedirect() {
  const { articleId } = useParams()
  const { tiersById } = useContent()
  const slug = parentsCourseSlug(tiersById)
  if (!slug) return <Navigate to="/courses" replace />
  return <Navigate to={articleId ? `/learn/${slug}/${articleId}` : `/course/${slug}`} replace />
}
