/**
 * Web dashboard entry point.
 *
 * Mounts <App /> under React StrictMode and loads the global Tailwind
 * styles from index.css. The hub serves the built bundle from
 * webui/dist when you open http://<hub-ip>:8765/.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
