// Inline icons (no icon font, no network). Decorative: the button text always says the same thing.
interface IconProps {
  className?: string
}

const common = {
  'aria-hidden': true,
  focusable: false,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

export function MicIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10v1a7 7 0 0 0 14 0v-1" />
      <path d="M12 18v4M8 22h8" />
    </svg>
  )
}

export function StopIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <rect x="6" y="6" width="12" height="12" rx="1.5" fill="currentColor" />
    </svg>
  )
}

export function HourglassIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M6 2h12M6 22h12" />
      <path d="M7 2v4a5 5 0 0 0 10 0V2M7 22v-4a5 5 0 0 1 10 0v4" />
    </svg>
  )
}

export function SpeakerIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M4 9v6h4l5 4V5L8 9H4z" />
      <path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" />
    </svg>
  )
}

export function SlowIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <circle cx="12" cy="13" r="8" />
      <path d="M12 9v4l-2.5 2.5M10 2h4" />
    </svg>
  )
}

export function ArrowIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M4 12h15M13 6l6 6-6 6" />
    </svg>
  )
}

export function AlertIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M12 3 2 21h20L12 3z" />
      <path d="M12 10v5M12 18h.01" />
    </svg>
  )
}

export function CheckIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <circle cx="12" cy="12" r="10" />
      <path d="m7.5 12.5 3 3 6-6.5" />
    </svg>
  )
}

export function PeopleIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
      <circle cx="17" cy="9" r="2.5" />
      <path d="M16 14.2a5 5 0 0 1 6 4.8" />
    </svg>
  )
}

export function ListIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <rect x="4" y="3" width="16" height="18" rx="2.5" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </svg>
  )
}

export function BackIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M20 12H5M11 6l-6 6 6 6" />
    </svg>
  )
}

export function RefreshIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M20 11a8 8 0 1 0-2.3 5.7" />
      <path d="M20 4v7h-7" />
    </svg>
  )
}

export function ShareIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M4 12 20 4l-4 16-4-6-8-2z" />
      <path d="m12 14 8-10" />
    </svg>
  )
}

/** The app's own mark: a speech bubble holding a heart. Drawn here; public/icon.svg is the same drawing. */
export function HelperAvatar({ className }: IconProps) {
  return (
    <svg aria-hidden={true} focusable={false} viewBox="0 0 48 48" className={className}>
      <circle cx="24" cy="24" r="24" fill="#a6360f" />
      <path d="M12 15a5 5 0 0 1 5-5h14a5 5 0 0 1 5 5v11a5 5 0 0 1-5 5h-8l-7 6v-6a5 5 0 0 1-4-5z" fill="#fff8f0" />
      <path
        d="M24 27.5s-6.5-3.8-6.5-8.1a3.4 3.4 0 0 1 6.5-1.6 3.4 3.4 0 0 1 6.5 1.6c0 4.3-6.5 8.1-6.5 8.1z"
        fill="#a6360f"
      />
    </svg>
  )
}

/** The home screen's picture: a morning sun over a chat bubble and a cup of tea. Decorative only. */
export function WelcomeIllustration({ className }: IconProps) {
  return (
    <svg aria-hidden={true} focusable={false} viewBox="0 0 240 150" className={className}>
      <circle cx="170" cy="62" r="34" fill="#f6b33c" />
      <g stroke="#f6b33c" strokeWidth="6" strokeLinecap="round">
        <path d="M170 12v-8M212 30l6-6M224 62h8M128 30l-6-6" />
      </g>
      <path d="M0 118c40-22 90-30 140-20s80 6 100-4v56H0z" fill="#f3d9c0" />
      <path
        d="M24 34a14 14 0 0 1 14-14h70a14 14 0 0 1 14 14v34a14 14 0 0 1-14 14H64l-22 18V82h-4a14 14 0 0 1-14-14z"
        fill="#ffffff"
        stroke="#1c1917"
        strokeWidth="4"
        strokeLinejoin="round"
      />
      <g fill="#a6360f">
        <circle cx="52" cy="51" r="6" />
        <circle cx="73" cy="51" r="6" />
        <circle cx="94" cy="51" r="6" />
      </g>
      <path d="M150 100h44v18a18 18 0 0 1-18 18h-8a18 18 0 0 1-18-18z" fill="#134e4a" />
      <path d="M194 106h6a8 8 0 0 1 0 16h-7" fill="none" stroke="#134e4a" strokeWidth="5" />
      <path
        d="M163 92c-4-6 4-8 0-14M178 92c-4-6 4-8 0-14"
        fill="none"
        stroke="#7c6f64"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  )
}
