// Guided (the full tour, for new doctors and the demo) or Clinic (the compact daily view) (DW-32).
// Stored in this browser only; never sent anywhere.
import { useCallback, useEffect, useState } from 'react'

export type ViewMode = 'guided' | 'clinic'
const KEY = 'safesignal-mode'

function saved(): ViewMode {
  try {
    return localStorage.getItem(KEY) === 'clinic' ? 'clinic' : 'guided'
  } catch {
    return 'guided'
  }
}

export function useViewMode() {
  const [mode, setMode] = useState<ViewMode>(saved)
  useEffect(() => {
    document.documentElement.classList.toggle('clinic-mode', mode === 'clinic')
    return () => document.documentElement.classList.remove('clinic-mode')
  }, [mode])
  const choose = useCallback((m: ViewMode) => {
    setMode(m)
    try {
      localStorage.setItem(KEY, m)
    } catch {
      /* not remembered, still applied */
    }
  }, [])
  return { mode, choose }
}
