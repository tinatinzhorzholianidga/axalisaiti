import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/global.css'
import './styles/platform.css'
import './styles/meter.css'
import { getRuntime } from './lib/runtime.js'
import { ContentProvider } from './content/ContentProvider.jsx'
import { I18nProvider } from './i18n/I18nContext.jsx'
import { ProgressProvider } from './store/progress.jsx'
import App from './App.jsx'

const root = document.getElementById('cyberhero-root')
if (root) {
  const runtime = getRuntime()
  createRoot(root).render(
    <React.StrictMode>
      <BrowserRouter basename={runtime.basename}>
        <ContentProvider runtime={runtime}>
          <I18nProvider runtime={runtime}>
            <ProgressProvider>
              <App />
            </ProgressProvider>
          </I18nProvider>
        </ContentProvider>
      </BrowserRouter>
    </React.StrictMode>,
  )
}
