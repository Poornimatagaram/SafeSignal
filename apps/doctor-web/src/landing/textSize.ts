// "Bigger text" for the public pages. Scales the root font size (Tailwind sizes are rem), only while a landing
// page is mounted; the doctor and caregiver views keep the default size. The choice is remembered per browser.
import { useEffect, useState } from 'react'

const KEY = 'safesignal.bigText'
const read = () => {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function useBigText(): [boolean, () => void] {
  const [big, setBig] = useState(read)
  useEffect(() => {
    document.documentElement.style.fontSize = big ? '137.5%' : '112.5%' // 22px : 18px
    try {
      localStorage.setItem(KEY, big ? '1' : '0')
    } catch {
      /* storage unavailable: keep the choice for this visit only */
    }
    return () => {
      document.documentElement.style.fontSize = ''
    }
  }, [big])
  return [big, () => setBig((b) => !b)]
}

// Hash routing owns location.hash (#/, #/learn, #/doctor), so in-page jumps scroll instead of changing the hash.
export function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
