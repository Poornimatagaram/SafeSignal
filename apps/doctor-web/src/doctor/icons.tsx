// Inline icons for the doctor screens (no icon font, no network).
type P = { size?: number; className?: string }
const base = (size: number) => ({ width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true })

export const ArrowRight = ({ size = 16, className = 'arrow' }: P) => <svg {...base(size)} strokeWidth={2.6} className={className}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
export const ArrowLeft = ({ size = 16 }: P) => <svg {...base(size)} strokeWidth={2.6}><path d="M19 12H5M11 6l-6 6 6 6" /></svg>
export const ArrowDown = ({ size = 26 }: P) => <svg {...base(size)} strokeWidth={2.8}><path d="M12 5v14M6 13l6 6 6-6" /></svg>
export const Chevron = ({ size = 14, className }: P) => <svg {...base(size)} strokeWidth={2.4} className={className}><path d="m6 9 6 6 6-6" /></svg>
export const SyncIcon = ({ size = 16 }: P) => <svg {...base(size)} strokeWidth={2.4}><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /></svg>
export const Check = ({ size = 16 }: P) => <svg {...base(size)} strokeWidth={3}><path d="m5 12 5 5 9-10" /></svg>
export const Warn = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.6}><path d="M12 8v5M12 17h.01" /><path d="M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /></svg>
export const Clock = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.6}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
export const Shield = ({ size = 22 }: P) => <svg {...base(size)} strokeWidth={2.2}><path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z" /><path d="m9 12 2 2 4-4" /></svg>
export const Search = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.2}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
export const Menu = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.4}><path d="M4 7h16M4 12h16M4 17h16" /></svg>
export const Key = ({ size = 16 }: P) => <svg {...base(size)} strokeWidth={2.2}><circle cx="8" cy="15" r="4" /><path d="m11 12 9-9M17 6l3 3" /></svg>
export const Sun = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.2}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
export const Moon = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.2}><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" /></svg>
export const Monitor = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.2}><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></svg>

export function Logo({ size = 38, flat = false }: { size?: number; flat?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <defs>
        <linearGradient id="ss-lg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#f6a07f" />
          <stop offset="1" stopColor="#e2673f" />
        </linearGradient>
      </defs>
      {!flat && <rect x="3" y="5" width="32" height="32" rx="9" fill="#c9583a" transform="rotate(-8 19 21)" />}
      <rect x="4" y="2" width="32" height="32" rx="9" fill={flat ? '#ef8262' : 'url(#ss-lg)'} transform="rotate(-8 20 18)" />
      <path d="M9 19h6l3-7 4 13 3-6h6" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" transform="rotate(-8 20 18)" />
    </svg>
  )
}
