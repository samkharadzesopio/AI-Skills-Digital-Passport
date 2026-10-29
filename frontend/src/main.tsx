import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { demoHostAllowed } from './demo/mode'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {demoHostAllowed ? <App /> : <main><h1>Demo deployment unavailable</h1><p>This synthetic preview is restricted to its dedicated demo hostname.</p></main>}
  </StrictMode>,
)
