// Routes. Doctor app: #/ home · #/patient/<ref> · #/patient/<ref>/record · #/guide · #/admin (DW-29).
// Also: #/caregiver (Anna's alerts) and the public pages #/about and #/learn (DW-23).
import { useEffect, useState } from 'react'
import { CaregiverView } from './components/CaregiverView'
import { DoctorApp } from './doctor/DoctorApp'
import { isDoctorHash } from './doctor/routes'
import { Landing } from './landing/Landing'
import { LearnMore } from './landing/LearnMore'

type Page = 'doctor' | 'caregiver' | 'about' | 'learn'
const pageFromHash = (h: string): Page =>
  h === '#/caregiver' ? 'caregiver' : h === '#/about' ? 'about' : h === '#/learn' ? 'learn' : isDoctorHash(h) ? 'doctor' : 'doctor'

const TITLES: Record<Page, string> = { doctor: 'Doctor view · SafeSignal', caregiver: 'Caregiver alerts · SafeSignal', about: 'SafeSignal', learn: 'Learn more · SafeSignal' }

export default function App() {
  const [page, setPage] = useState<Page>(() => pageFromHash(location.hash))
  useEffect(() => {
    // The doctor app decides its own scrolling (a patient link opens their page further down the home).
    const on = () => {
      const next = pageFromHash(location.hash)
      setPage(next)
      if (next !== 'doctor') window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  useEffect(() => {
    document.title = TITLES[page]
  }, [page])

  if (page === 'about') return <Landing />
  if (page === 'learn') return <LearnMore />
  if (page === 'caregiver')
    return (
      <div className="min-h-screen bg-cream p-3 font-soft text-plum sm:p-4">
        <div className="mx-auto max-w-3xl rounded-[1.8rem] bg-white p-5 shadow-frame sm:p-6">
          <CaregiverView />
        </div>
      </div>
    )
  return <DoctorApp />
}
