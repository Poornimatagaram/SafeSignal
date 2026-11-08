import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './theme.css'
import App from './App.tsx'
import { applyTheme, savedTheme } from './lib/theme'

applyTheme(savedTheme()) // before the first render, so a dark choice never flashes light

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
