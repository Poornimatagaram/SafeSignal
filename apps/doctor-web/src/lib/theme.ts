// Appearance: light, dark, or follow the device (DW-29). Stored in this browser only; never sent anywhere.
import { useCallback, useState } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'
export const THEME_LABEL: Record<ThemeMode, string> = { light: 'Light', dark: 'Dark', system: 'System' }
const KEY = 'safesignal-theme'

export function savedTheme(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'light' || v === 'dark' || v === 'system') return v
  } catch {
    /* storage blocked: follow the device */
  }
  return 'system'
}

// 'system' removes the attribute, so the prefers-color-scheme rules in theme.css decide.
export function applyTheme(mode: ThemeMode, animate = false) {
  const root = document.documentElement
  if (animate && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    root.classList.add('theme-fade')
    setTimeout(() => root.classList.remove('theme-fade'), 400)
  }
  if (mode === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', mode)
}

export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(savedTheme)
  const choose = useCallback((m: ThemeMode) => {
    setMode(m)
    applyTheme(m, true)
    try {
      localStorage.setItem(KEY, m)
    } catch {
      /* not remembered, still applied */
    }
  }, [])
  return { mode, choose }
}
