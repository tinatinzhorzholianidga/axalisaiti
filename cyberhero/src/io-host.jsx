import React from 'react'
import { createRoot } from 'react-dom/client'
import './styles/io-host.css'
import HomeHost from './host/HomeHost.jsx'

/* Second Vite entry: IO as the welcome host on the eLearning home page
   (templates/main/home.html). The template renders `#io-host-root` with
   everything the host needs as data-* attributes - no inline script
   (strict CSP). He floats in the bottom-right corner, like on CyberHero. */
const root = document.getElementById('io-host-root')
if (root) {
  const ds = root.dataset
  const doors = (ds.doors || 'basic,kids').split(',').filter(Boolean)
  createRoot(root).render(
    <React.StrictMode>
      <HomeHost
        lang={ds.locale === 'en' ? 'en' : 'ka'}
        skin={ds.skin === 'metal' ? 'metal' : 'classic'}
        label={ds.label || ''}
        closeLabel={ds.labelClose || ''}
        openLabel={ds.labelOpen || ''}
        doors={doors}
        signedIn={ds.signedIn === '1'}
      />
    </React.StrictMode>,
  )
}
