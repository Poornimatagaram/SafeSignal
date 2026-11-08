/** @type {import('tailwindcss').Config} */
// Colours point at the theme tokens in src/theme.css (DW-29), so Tailwind screens (admin, caregiver, public pages)
// follow light, dark and system modes. Names are kept from the earlier palette so existing classes still work.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        white: 'var(--surface)',
        plum: { DEFAULT: 'var(--ink)', ink: 'var(--ink-2)', dark: 'var(--ink)' },
        muted: 'var(--muted)',
        mauve: 'var(--sand)',
        cream: 'var(--bg)',
        lav: 'var(--line-2)',
        blush: 'var(--butter)',
        rose: { DEFAULT: 'var(--moderate)', tint: 'var(--coral-tint)' },
        mint: { DEFAULT: 'var(--good)', tint: 'var(--good-tint)' },
        butter: { DEFAULT: 'var(--mild)', tint: 'var(--warn-tint)' },
        coral: { DEFAULT: 'var(--coral)', ink: 'var(--coral-ink)', on: 'var(--on-coral)' },
        // Admin and emergency forms use slate and violet; map them onto the tokens too.
        slate: { 50: 'var(--sand)', 100: 'var(--line)', 200: 'var(--line)', 300: 'var(--line-2)', 400: 'var(--muted)', 500: 'var(--muted)', 600: 'var(--ink-2)', 700: 'var(--ink-2)', 800: 'var(--ink)', 900: 'var(--ink)' },
        violet: { 100: 'var(--review-tint)', 200: 'var(--review-tint)', 700: 'var(--review)', 900: 'var(--review)' },
      },
      fontFamily: {
        soft: ['"DM Sans"', 'system-ui', 'sans-serif'],
        display: ['Fredoka', 'system-ui', 'sans-serif'],
        mono: ['"DM Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: { soft: 'var(--shadow-sm)', frame: 'var(--shadow)' },
    },
  },
  plugins: [],
}
