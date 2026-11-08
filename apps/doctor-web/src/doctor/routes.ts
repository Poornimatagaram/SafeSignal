// Doctor routes inside the hash:
// #/ home · #/patient/<ref> (home with that patient open) · #/patient/<ref>/record · #/guide · #/admin
export type DoctorRoute =
  | { view: 'list' }
  | { view: 'patient'; ref: string }
  | { view: 'record'; ref: string }
  | { view: 'guide' }
  | { view: 'admin' }

export function parseDoctorRoute(hash: string): DoctorRoute {
  if (hash === '#/guide') return { view: 'guide' }
  if (hash === '#/admin') return { view: 'admin' }
  const m = /^#\/patient\/(pt_[0-9a-f]{8})(\/record)?$/.exec(hash)
  if (!m) return { view: 'list' }
  return m[2] ? { view: 'record', ref: m[1] } : { view: 'patient', ref: m[1] }
}
export const isDoctorHash = (hash: string) =>
  hash === '' || hash === '#' || hash === '#/' || hash === '#/guide' || hash === '#/admin' || hash.startsWith('#/patient/')
export const patientHref = (ref: string) => `#/patient/${ref}`
export const recordHref = (ref: string) => `#/patient/${ref}/record`

const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches

// Sections of the home page. Hash routing owns the URL, so sections are reached by scrolling, not by anchors.
export function goSection(id: string) {
  const scroll = () => document.getElementById(id)?.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'start' })
  const v = parseDoctorRoute(location.hash).view
  if (v === 'record' || v === 'guide' || v === 'admin') {
    location.hash = '#/'
    setTimeout(scroll, 120)
  } else scroll()
}
