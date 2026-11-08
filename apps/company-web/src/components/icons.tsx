// Inline icons (no icon font, no network). Shapes match the doctor view so the portals read as one product.
type P = { size?: number; className?: string }
const base = (size: number) => ({ width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true })

export const Chevron = ({ size = 14, className }: P) => <svg {...base(size)} strokeWidth={2.4} className={className}><path d="m6 9 6 6 6-6" /></svg>
export const ChevronRight = ({ size = 14, className }: P) => <svg {...base(size)} strokeWidth={2.4} className={className}><path d="m9 6 6 6-6 6" /></svg>
export const Lock = ({ size = 22 }: P) => <svg {...base(size)} strokeWidth={2}><rect x="5" y="10" width="14" height="11" rx="2.5" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
export const NoText = ({ size = 22 }: P) => <svg {...base(size)} strokeWidth={2}><path d="M4 6h16M4 12h10M4 18h7" /><path d="m15 15 6 6M21 15l-6 6" /></svg>
export const NoMic = ({ size = 22 }: P) => <svg {...base(size)} strokeWidth={2}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 11.5 5.3M19 11a7 7 0 0 1-.4 2.3M12 18v3M3 3l18 18" /></svg>
export const Group = ({ size = 22 }: P) => <svg {...base(size)} strokeWidth={2}><circle cx="9" cy="8" r="3.2" /><path d="M3 20a6 6 0 0 1 12 0" /><circle cx="17" cy="9" r="2.6" /><path d="M16 14.2A5 5 0 0 1 21 19" /></svg>
export const SyncIcon = ({ size = 16 }: P) => <svg {...base(size)} strokeWidth={2.4}><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /></svg>
export const Check = ({ size = 16 }: P) => <svg {...base(size)} strokeWidth={3}><path d="m5 12 5 5 9-10" /></svg>
export const Shield = ({ size = 22 }: P) => <svg {...base(size)} strokeWidth={2.2}><path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z" /><path d="m9 12 2 2 4-4" /></svg>
export const Sun = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.2}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
export const Moon = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.2}><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" /></svg>
export const Monitor = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.2}><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></svg>
export const Pulse = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.4}><path d="M3 12h4l3-7 4 14 3-7h4" /></svg>
export const ClipboardCheck = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.2}><rect x="5" y="4" width="14" height="17" rx="2" /><path d="M9 4V3h6v1M9 13l2 2 4-4" /></svg>
export const Label = ({ size = 18 }: P) => <svg {...base(size)} strokeWidth={2.2}><path d="M3 12V4h8l10 10-8 8z" /><circle cx="7.5" cy="8.5" r="1.2" /></svg>

export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect x="2" y="2" width="36" height="36" rx="11" fill="var(--ink)" />
      <path d="M9 21h6l3-7 4 13 3-6h6" fill="none" stroke="var(--page)" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
