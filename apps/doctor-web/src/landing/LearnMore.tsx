// Learn more (#/learn): details by topic, one topic at a time, each answer opens on tap.
import { useState } from 'react'
import { CONTACT_EMAIL, TOPICS, type TopicId } from './content'
import { useBigText } from './textSize'
import { Accordion, Footer, Frame, SizeToggle } from './ui'

export function LearnMore() {
  const [big, toggleBig] = useBigText()
  const [topic, setTopic] = useState<TopicId>('patients')
  const cur = TOPICS.find((t) => t.id === topic) ?? TOPICS[0]
  return (
    <Frame>
      <header className="flex flex-wrap items-center gap-x-5 gap-y-3 px-7 py-5">
        <BackHome />
        <span className="mr-auto font-display text-xl font-bold">SafeSignal</span>
        <SizeToggle big={big} onToggle={toggleBig} />
      </header>

      <main>
        <section className="px-7 pb-6 pt-2">
          <h1 className="mb-1 font-display text-[2.4rem] font-bold leading-tight">Learn more</h1>
          <p className="text-[1.1rem]">Pick a topic. Open only what you want to read.</p>
        </section>

        <nav aria-label="Topics" className="flex flex-wrap gap-2 px-7">
          {TOPICS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTopic(t.id)}
              aria-pressed={topic === t.id}
              className={`soft-focus min-h-12 rounded-full px-5 font-extrabold ${topic === t.id ? 'bg-plum text-white shadow-soft' : 'bg-mauve text-plum'}`}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <section aria-live="polite" className="px-7 pb-10 pt-6">
          <div className={`mb-5 rounded-[1.8rem] ${cur.tint} p-8`}>
            <h2 className="mb-1 font-display text-[1.7rem] font-semibold">{cur.title}</h2>
            <p className="text-[1.1rem]">{cur.intro}</p>
          </div>
          {/* key resets open answers when the topic changes */}
          <Accordion key={cur.id} items={cur.items} tone="bg-white shadow-soft" />

          {cur.id === 'doctors' && (
            <div className="mt-5 rounded-[1.6rem] bg-white p-6 shadow-soft">
              <h3 className="mb-3 font-display text-[1.15rem] font-semibold">When check-ins are missed</h3>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-[1.2rem] bg-butter-tint p-4"><b>1 missed</b><br />The patient gets a reminder. Their caregiver and care team get a heads-up.</div>
                <div className="rounded-[1.2rem] bg-rose-tint p-4"><b>2 in a row</b><br />The same people are told again, marked urgent.</div>
                <div className="rounded-[1.2rem] bg-mauve p-4"><b>3 in a row</b><br />The emergency contacts the patient chose are told as well.</div>
              </div>
              <a href="#/" className="soft-focus mt-5 inline-flex min-h-12 items-center rounded-full bg-plum px-6 font-extrabold text-white no-underline">Open the doctor view</a>
            </div>
          )}

          {cur.id === 'programs' && (
            <div className="mt-5 flex flex-wrap items-center gap-4 rounded-[1.6rem] bg-plum p-7 text-cream">
              <div className="min-w-0 flex-[1_1_18rem]">
                <h3 className="mb-1 font-display text-[1.25rem] font-semibold text-white">Start a pilot</h3>
                <p>One drug program, the daily check-in and the care-team view. Priced per program and per enrolled patient: [YOUR PRICE].</p>
              </div>
              <a href={`mailto:${CONTACT_EMAIL}`} className="soft-focus inline-flex min-h-12 items-center rounded-full bg-cream px-6 font-extrabold text-plum no-underline">Contact us</a>
            </div>
          )}
        </section>
      </main>

      <Footer>
        <a href="#/about" className="font-extrabold">Back to home</a>
      </Footer>
    </Frame>
  )
}

function BackHome() {
  return (
    <a href="#/about" className="soft-focus inline-flex min-h-11 items-center gap-1.5 rounded-full bg-mauve px-4 font-extrabold text-plum no-underline">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true"><path d="M15 6l-6 6 6 6" /></svg>
      Back to home
    </a>
  )
}
