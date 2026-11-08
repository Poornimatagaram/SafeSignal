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

export function SpeakerOffIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M4 9v6h4l5 4V5L8 9H4z" />
      <path d="M17 9l5 6M22 9l-5 6" />
    </svg>
  )
}

export function SendIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M3 11.5L21 3l-6.5 18-3-7.5L3 11.5z" />
      <path d="M11.5 13.5L21 3" />
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

/** The app's own mark: a speech bubble holding a heart, in the app's coral. (public/icon.svg is the same drawing.) */
export function HelperAvatar({ className }: IconProps) {
  return (
    <svg aria-hidden={true} focusable={false} viewBox="0 0 48 48" className={className}>
      <circle cx="24" cy="24" r="24" fill="#f2846b" />
      <path d="M12 15a5 5 0 0 1 5-5h14a5 5 0 0 1 5 5v11a5 5 0 0 1-5 5h-8l-7 6v-6a5 5 0 0 1-4-5z" fill="#fff8f1" />
      <path
        d="M24 27.5s-6.5-3.8-6.5-8.1a3.4 3.4 0 0 1 6.5-1.6 3.4 3.4 0 0 1 6.5 1.6c0 4.3-6.5 8.1-6.5 8.1z"
        fill="#d9603f"
      />
    </svg>
  )
}

/** The sun's soft rays: short rounded strokes around the upper half of the sun. */
const SUN = { x: 160, y: 122, r: 46 }
const RAYS = [200, 225, 250, 270, 290, 315, 340].map((deg) => {
  const a = (deg * Math.PI) / 180
  const at = (r: number) => `${(SUN.x + r * Math.cos(a)).toFixed(1)} ${(SUN.y + r * Math.sin(a)).toFixed(1)}`
  return `M${at(SUN.r + 12)}L${at(SUN.r + 24)}`
})

/** The home screen's picture: a gentle sunrise with a heart, over soft rolling hills. Decorative only. */
export function WelcomeIllustration({ className }: IconProps) {
  return (
    <svg aria-hidden={true} focusable={false} viewBox="0 0 320 172" className={className}>
      <defs>
        <clipPath id="welcome-card">
          <rect x="0" y="0" width="320" height="172" rx="32" />
        </clipPath>
      </defs>
      <g clipPath="url(#welcome-card)">
        <rect x="0" y="0" width="320" height="172" fill="#fde4d6" />
        <circle cx={SUN.x} cy={SUN.y} r="104" fill="#fcd9c8" />
        <circle cx={SUN.x} cy={SUN.y} r="78" fill="#fbcdb9" />
        <g stroke="#f6a48f" strokeWidth="6" strokeLinecap="round">
          {RAYS.map((d) => (
            <path key={d} d={d} />
          ))}
        </g>
        <circle cx={SUN.x} cy={SUN.y} r={SUN.r} fill="#f2846b" />
        <path
          d="M160 120s-15-8.8-15-18.6a7.8 7.8 0 0 1 15-3.4 7.8 7.8 0 0 1 15 3.4c0 9.8-15 18.6-15 18.6z"
          fill="#fff8f1"
        />
        <rect x="30" y="34" width="62" height="18" rx="9" fill="#fff8f1" opacity="0.9" />
        <rect x="48" y="24" width="30" height="18" rx="9" fill="#fff8f1" opacity="0.9" />
        <rect x="236" y="44" width="54" height="16" rx="8" fill="#fff8f1" opacity="0.9" />
        <path d="M0 134c52-30 104-30 160-8s110 18 160-6v52H0z" fill="#c9dcbf" />
        <path d="M0 150c64-20 128-16 184 2s96 8 136-6v26H0z" fill="#a9c79c" />
        <path d="M0 164c80-12 200-12 320 0v8H0z" fill="#f8d2bd" />
        <circle cx="62" cy="128" r="5" fill="#fff8f1" />
        <circle cx="262" cy="138" r="5" fill="#fff8f1" />
        <circle cx="244" cy="148" r="4" fill="#f2846b" />
      </g>
    </svg>
  )
}
