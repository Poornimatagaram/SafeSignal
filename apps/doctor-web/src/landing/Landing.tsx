// Public home page (#/): one message, one example, three steps, one week of what the doctor sees.
import { useState } from 'react'
import { CONTACT_EMAIL, HOME_FAQ, NO_CHECKIN, WAVE, WEEK } from './content'
import { scrollToId, useBigText } from './textSize'
import { Accordion, Footer, Frame, Logo, NavLink, SizeToggle } from './ui'

const BAR_COLORS = ['#91788f', '#df7796', '#d3bfcc']

export function Landing() {
  const [big, toggleBig] = useBigText()
  return (
    <Frame>
      <header className="flex flex-wrap items-center gap-x-5 gap-y-3 px-7 py-5">
        <Logo />
        <nav aria-label="Main" className="flex flex-wrap gap-1">
          <NavLink onClick={() => scrollToId('how')}>How it works</NavLink>
          <NavLink onClick={() => scrollToId('faq')}>Questions</NavLink>
          <NavLink href="#/learn">Learn more</NavLink>
        </nav>
        <SizeToggle big={big} onToggle={toggleBig} />
      </header>

      <main>
        <Hero />
        <HowItWorks />
        <DoctorWeek />
        <WhoSeesWhat />
        <section id="faq" className="px-7 py-10">
          <div className="mx-auto max-w-3xl">
            <h2 className="mb-6 text-center font-display text-[2rem] font-semibold">Questions</h2>
            <Accordion items={HOME_FAQ} />
          </div>
        </section>
        <section className="px-7 pb-10 pt-4">
          <div className="rounded-[1.8rem] bg-plum px-8 py-10 text-center text-cream">
            <h2 className="mb-2 font-display text-[1.8rem] font-semibold text-white">Want to use SafeSignal?</h2>
            <p className="mx-auto max-w-xl text-[1.1rem]">Ask your doctor or nurse at your next visit. It's free for patients.</p>
            <p className="mt-6 text-[0.95rem]">
              Doctor, nurse or drug program?{' '}
              <a href="#/learn" className="font-extrabold text-white">Learn more</a>
              {' '}or{' '}
              <a href={`mailto:${CONTACT_EMAIL}`} className="font-extrabold text-white">contact us</a>
            </p>
          </div>
        </section>
      </main>

      <Footer>
        <span className="font-display font-bold">SafeSignal</span>
        <a href="#/" className="font-bold">Doctor sign-in</a>
        <a href="#/caregiver" className="font-bold">Caregiver alerts</a>
      </Footer>
    </Frame>
  )
}

function Hero() {
  const [playing, setPlaying] = useState(false)
  return (
    <section className="grid gap-5 px-7 pb-10 pt-2 md:grid-cols-2">
      <div className="flex flex-col justify-center gap-5 rounded-[1.8rem] bg-mauve p-9">
        <h1 className="font-display text-[2.6rem] font-bold leading-[1.12] tracking-tight sm:text-[2.9rem]">Tell your doctor how you feel, just by talking.</h1>
        <p className="text-[1.2rem]">Answer a few questions out loud each day. Your words stay on your phone.</p>
        <button type="button" onClick={() => scrollToId('example')} className="soft-focus inline-flex min-h-[54px] items-center gap-2 self-start rounded-full bg-plum px-7 text-[1.05rem] font-extrabold text-white">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 4.5v15l13-7.5z" /></svg>
          See an example
        </button>
      </div>

      <div id="example" className="flex scroll-mt-4 flex-col gap-4 rounded-[1.8rem] bg-white p-8 shadow-soft">
        <p className="text-[1.1rem] font-extrabold">“How is your skin today?”</p>
        <div className="rounded-[1.3rem] bg-cream p-5">
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? 'Pause' : 'Play the answer'}
              className="soft-focus grid h-[52px] w-[52px] flex-none place-items-center rounded-full bg-plum text-white"
            >
              {playing ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 4.5v15l13-7.5z" /></svg>
              )}
            </button>
            <div aria-hidden="true" className="flex h-10 min-w-0 flex-1 items-center gap-[3px] overflow-hidden">
              {WAVE.map((h, i) => (
                <div
                  key={i}
                  className={playing ? 'wave-on' : 'wave-off'}
                  style={{ flex: '1 0 3px', maxWidth: 5, height: h, borderRadius: 3, background: BAR_COLORS[i % 3], animationDelay: `${((i * 0.07) % 0.9).toFixed(2)}s` }}
                />
              ))}
            </div>
          </div>
          <p className="mt-4 text-[1.1rem] italic">“The red bumps on my arms came back, and they itch more than last week.”</p>
          <p className="mt-1 text-[0.9rem] font-bold">This stays on your phone.</p>
        </div>
        <div>
          <p className="mb-2 font-extrabold">Your doctor only gets:</p>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-rose-tint px-4 py-1.5 font-bold">Rash</span>
            <span className="rounded-full bg-butter-tint px-4 py-1.5 font-bold">Getting worse</span>
            <span className="rounded-full bg-mint-tint px-4 py-1.5 font-bold">Started a few days ago</span>
          </div>
        </div>
      </div>
    </section>
  )
}

const STEPS = [
  { n: 1, t: 'Talk', d: 'Your phone asks a few questions. You answer in your own words.', bg: 'bg-rose-tint', icon: 'mic' },
  { n: 2, t: 'It stays private', d: 'Your voice and words never leave your phone.', bg: 'bg-mint-tint', icon: 'lock' },
  { n: 3, t: 'Your doctor knows', d: "Your doctor sees how you've been before your next visit.", bg: 'bg-butter-tint', icon: 'heart' },
] as const

function StepIcon({ icon }: { icon: (typeof STEPS)[number]['icon'] }) {
  if (icon === 'mic')
    return <svg width="24" height="24" viewBox="0 0 24 24" fill="#583a56" aria-hidden="true"><rect x="9" y="2.5" width="6" height="12" rx="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0" fill="none" stroke="#583a56" strokeWidth="2" strokeLinecap="round" /><rect x="11" y="17" width="2" height="4" rx="1" /></svg>
  if (icon === 'lock')
    return <svg width="24" height="24" viewBox="0 0 24 24" fill="#583a56" aria-hidden="true"><rect x="4" y="10" width="16" height="11" rx="3" /><path d="M8 10V7a4 4 0 0 1 8 0v3" fill="none" stroke="#583a56" strokeWidth="2" /></svg>
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="#583a56" aria-hidden="true"><path d="M20.8 5.6a5 5 0 0 0-7.1 0L12 7.3l-1.7-1.7a5 5 0 1 0-7.1 7.1L12 21.5l8.8-8.8a5 5 0 0 0 0-7.1z" /></svg>
}

function HowItWorks() {
  return (
    <section id="how" className="scroll-mt-4 px-7 py-10">
      <h2 className="mb-6 text-center font-display text-[2rem] font-semibold">How it works</h2>
      <ol className="grid gap-4 md:grid-cols-3">
        {STEPS.map((s) => (
          <li key={s.n} className={`rounded-[1.6rem] ${s.bg} p-7 text-center`}>
            <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-white"><StepIcon icon={s.icon} /></div>
            <h3 className="mb-1 font-display text-[1.2rem] font-semibold">{s.n}. {s.t}</h3>
            <p>{s.d}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}

function DoctorWeek() {
  const [day, setDay] = useState(0)
  const today = new Date()
  const offsets = [6, 5, 4, 3, 2, 1, 0]
  const text = WEEK[day] ?? NO_CHECKIN
  return (
    <section className="px-7 py-10">
      <div className="rounded-[1.8rem] bg-mauve p-8">
        <h2 className="font-display text-[1.6rem] font-semibold">What your doctor sees</h2>
        <p className="mb-5">Tap a day.</p>
        <div className="grid grid-cols-7 gap-2">
          {offsets.map((off) => {
            const d = new Date(today)
            d.setDate(d.getDate() - off)
            const checked = WEEK[off] !== null
            const sel = day === off
            return (
              <button
                key={off}
                type="button"
                onClick={() => setDay(off)}
                aria-pressed={sel}
                aria-label={d.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' }) + (checked ? '' : ', no check-in')}
                className={`soft-focus flex min-h-16 flex-col items-center justify-center rounded-2xl font-extrabold ${checked ? 'bg-rose-tint' : 'bg-cream'} ${sel ? 'border-[3px] border-plum' : checked ? 'border-[3px] border-transparent' : 'border-2 border-dashed border-muted'}`}
              >
                <span className="text-[0.8rem] font-bold">{off === 0 ? 'Today' : d.toLocaleDateString(undefined, { weekday: 'short' })}</span>
                <span className="text-[1.1rem]">{d.getDate()}</span>
              </button>
            )
          })}
        </div>
        <p role="status" className="mt-5 rounded-2xl bg-cream px-5 py-4 text-[1.1rem] font-bold">{text}</p>
        <p className="mt-3 text-[0.85rem]">Walter is a made-up demo patient.</p>
      </div>
    </section>
  )
}

function WhoSeesWhat() {
  const rows = [
    ['You', 'Everything you said.'],
    ['Your doctor', 'Your symptoms, how bad, and since when.'],
    ['Your family', 'Only that something happened. Not your symptoms.'],
  ]
  return (
    <section className="px-7 py-10">
      <h2 className="mb-6 text-center font-display text-[2rem] font-semibold">Who sees what</h2>
      <ul className="mx-auto flex max-w-3xl flex-col gap-3">
        {rows.map(([who, what]) => (
          <li key={who} className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-[1.3rem] bg-white px-6 py-4 shadow-soft">
            <b className="min-w-28 text-[1.1rem]">{who}</b>
            <span>{what}</span>
          </li>
        ))}
      </ul>
      <p className="mt-6 text-center">
        <a href="#/learn" className="soft-focus inline-flex min-h-12 items-center gap-1.5 rounded-full bg-mauve px-6 font-extrabold text-plum no-underline">
          Want the details? Learn more
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
        </a>
      </p>
    </section>
  )
}
