import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App'
import { applyTheme, savedTheme } from './lib/theme'

applyTheme(savedTheme()) // before the first render, so a dark choice never flashes light

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
