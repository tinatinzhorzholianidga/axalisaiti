import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Header from './components/Header.jsx'
import Footer from './components/Footer.jsx'
import ScrollToTop from './components/ScrollToTop.jsx'
import { ErrorState, Loading } from './components/State.jsx'
import { useContent } from './content/ContentProvider.jsx'
import { useI18n } from './i18n/I18nContext.jsx'
import { MascotProvider } from './mascot/MascotProvider.jsx'
import Fireworks from './mascot/Fireworks.jsx'
import WelcomePage from './pages/WelcomePage.jsx'
import TracksPage from './pages/TracksPage.jsx'
import TrackPage from './pages/TrackPage.jsx'
import ParentsHubPage from './pages/parents/ParentsHubPage.jsx'
import ArticlePage from './pages/parents/ArticlePage.jsx'
import AgreementPage from './pages/parents/AgreementPage.jsx'
import GuardiansMapPage from './pages/guardians/GuardiansMapPage.jsx'
import MissionPage from './pages/guardians/MissionPage.jsx'
import CertificatePage from './pages/guardians/CertificatePage.jsx'
import CoursesPage from './pages/courses/CoursesPage.jsx'
import CoursePage from './pages/courses/CoursePage.jsx'
import LessonPage from './pages/courses/LessonPage.jsx'
import EmergencyPage from './pages/EmergencyPage.jsx'
import VerifyCertificatePage from './pages/VerifyCertificatePage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'

// IO lives on every page, but three.js loads lazily after first paint so
// the site itself stays light on slow school machines.
const MascotDemoPage = lazy(() => import('./pages/MascotDemoPage.jsx'))
const IoChatPage = lazy(() => import('./pages/IoChatPage.jsx'))
const MascotWidget = lazy(() => import('./mascot/MascotWidget.jsx'))

function DeferredMascot() {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setReady(true), 900)
    return () => clearTimeout(timer)
  }, [])
  if (!ready) return null
  return (
    <Suspense fallback={null}>
      <MascotWidget />
    </Suspense>
  )
}

/* The IO tutor pages exist only when the feature flag is on. */
function Gated({ enabled, children }) {
  if (!enabled) return <NotFoundPage />
  return <Suspense fallback={<Loading />}>{children}</Suspense>
}

export default function App() {
  const { t } = useI18n()
  const { status, error, retry, flags } = useContent()
  const tutorEnabled = Boolean(flags.CYBERHERO_IO_CHAT_ENABLED)

  let body
  if (status === 'loading') body = <Loading />
  else if (status === 'error') body = <ErrorState error={error} onRetry={retry} />
  else
    body = (
      <Routes>
        <Route path="/" element={<WelcomePage />} />
        <Route path="/tracks" element={<TracksPage />} />
        <Route path="/track/:tierId" element={<TrackPage />} />
        <Route path="/parents" element={<ParentsHubPage />} />
        <Route path="/parents/agreement" element={<AgreementPage />} />
        <Route path="/parents/:articleId" element={<ArticlePage />} />
        <Route path="/articles" element={<ParentsHubPage />} />
        <Route path="/articles/:articleId" element={<ArticlePage />} />
        <Route path="/family-agreement" element={<AgreementPage />} />
        <Route path="/guardians" element={<GuardiansMapPage />} />
        <Route path="/guardians/mission/:missionId" element={<MissionPage />} />
        <Route path="/guardians/certificate" element={<CertificatePage />} />
        <Route path="/courses" element={<CoursesPage />} />
        <Route path="/course/:slug" element={<CoursePage />} />
        <Route path="/learn/:course/:lesson" element={<LessonPage />} />
        <Route path="/emergency" element={<EmergencyPage />} />
        <Route path="/certificate" element={<VerifyCertificatePage />} />
        <Route path="/certificate/:publicId" element={<VerifyCertificatePage />} />
        <Route
          path="/io-chat"
          element={
            <Gated enabled={tutorEnabled}>
              <IoChatPage />
            </Gated>
          }
        />
        <Route
          path="/mascot-demo"
          element={
            <Gated enabled={tutorEnabled}>
              <MascotDemoPage />
            </Gated>
          }
        />
        <Route path="/index.html" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    )

  return (
    <MascotProvider>
      <a className="skip-link" href="#content">
        {t('nav.skipToContent')}
      </a>
      <ScrollToTop />
      <Header />
      <div className="app-main" id="content">
        {body}
      </div>
      <Footer />
      {status === 'ready' && <DeferredMascot />}
      <Fireworks />
    </MascotProvider>
  )
}
