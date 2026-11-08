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
