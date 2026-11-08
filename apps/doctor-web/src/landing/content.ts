// Copy for the public pages. Walter is a synthetic demo patient; his week matches data/doctor/send_demo_history.py.

export const WAVE = [10, 18, 26, 14, 32, 22, 34, 18, 28, 12, 24, 32, 20, 30, 16, 26, 34, 22, 14, 28, 32, 18, 24, 12, 30, 20, 34, 16, 26, 22, 30, 14]

// days ago -> what the doctor sees (null = no check-in that day)
export const WEEK: Record<number, string | null> = {
  6: 'Rash, getting a little better. His daughter answered.',
  5: null,
  4: 'Rash, and new nail soreness.',
  3: 'Rash getting worse. Flagged for the doctor to look at.',
  2: 'Rash, plus something new to review. His daughter answered.',
  1: 'Rash and sore nails, both getting worse.',
  0: 'Today: rash and sore nails, getting worse. His doctor was alerted.',
}
export const NO_CHECKIN = 'No check-in. His care team got a gentle heads-up.'

export interface QA {
  q: string
  a: string
}

export const HOME_FAQ: QA[] = [
  { q: 'Do I need to be good with phones?', a: 'No. The phone talks to you and listens. A family member can help if you like.' },
  { q: 'Who hears what I say?', a: 'Nobody. Your voice and your words stay on your phone. Your doctor only gets a short summary.' },
  { q: 'Can I stop?', a: 'Yes, any time. Just turn sharing off in the app.' },
]

export type TopicId = 'patients' | 'doctors' | 'programs' | 'privacy' | 'questions'

export interface Topic {
  id: TopicId
  label: string
  tint: string // Tailwind background class
  title: string
  intro: string
  items: QA[]
}

export const TOPICS: Topic[] = [
  {
    id: 'patients', label: 'Patients & families', tint: 'bg-rose-tint', title: 'For patients and families',
    intro: 'A gentle daily check-in about how your medicine is treating you, by voice.',
    items: [
      { q: 'What happens in a check-in?', a: 'Your phone reads a few questions out loud, like "How is your skin today?" You answer in your own words. If an answer is unclear, it asks again in simpler words. It takes a few minutes.' },
      { q: 'Can I type instead of talking?', a: 'Yes. You can talk, type, or mix both.' },
      { q: 'Can someone answer for me?', a: 'Yes. A parent or caregiver can answer on your behalf. Your doctor can see who answered each day.' },
      { q: 'What does my family see?', a: 'Only that something happened and when, for example a missed check-in or a severe symptom. Not your symptoms, unless you choose to share more.' },
      { q: 'What if I report something serious?', a: 'Your care team and your caregiver are told right away. SafeSignal does not replace your doctor: in an emergency, call 911.' },
      { q: 'Does it cost anything?', a: 'No. It is free for patients. The drug company pays for the program.' },
    ],
  },
  {
    id: 'doctors', label: 'Doctors & nurses', tint: 'bg-mint-tint', title: 'For doctors and nurses',
    intro: 'A one-screen symptom history for each patient, ready before the visit.',
    items: [
      { q: 'What do I see for each patient?', a: 'Symptoms by day for the last three weeks, how severe, when they started, whether they are getting better or worse, and who answered: the patient or a caregiver.' },
      { q: 'What does "for review" mean?', a: 'It marks a symptom that may be linked to a new exposure. It is a flag for you to look at, never a diagnosis.' },
      { q: 'Is there a summary?', a: 'Yes, a short pre-visit summary written from the structured check-ins with fixed templates. No AI model reads patient data.' },
      { q: 'What happens when a doctor leaves?', a: 'Records belong to the hospital or clinic, not to one doctor. The admin removes the leaving doctor and adds the new one, who sees the full history right away. The old doctor sees nothing.' },
      { q: 'What about emergencies?', a: "A patient can choose an emergency hospital at setup. That hospital can open the history only by stating a reason. Every access is logged, and the patient's caregiver and care team are told." },
    ],
  },
  {
    id: 'programs', label: 'Drug programs', tint: 'bg-butter-tint', title: 'For drug safety teams',
    intro: 'A steady, structured side-effect signal for each version of your drug.',
    items: [
      { q: 'What data do we receive?', a: 'Coded symptom terms, severity, onset, drug version and cohort, plus who answered and whether it was spoken or typed. No names, no recordings, no transcripts.' },
      { q: 'How small can a group be?', a: 'Views never show a group smaller than five patients.' },
      { q: 'Can we change the questions?', a: 'Yes. Your team can publish survey questions for each cohort.' },
      { q: 'How is it priced?', a: 'Per drug program and per enrolled patient: [YOUR PRICE]. Patients and doctors never pay.' },
    ],
  },
  {
    id: 'privacy', label: 'Privacy', tint: 'bg-mauve', title: 'Privacy in detail',
    intro: 'Private by design, not just by promise.',
    items: [
      { q: 'What stays on the phone?', a: 'Your recording, the words you said, your name, your date of birth and your phone number. Always.' },
      { q: 'What leaves the phone?', a: 'A short, fixed list of details, like the symptom, how bad it is and since when. Personal details are removed first, and the screen shows each detail that was sent.' },
      { q: 'Can SafeSignal read my history?', a: "No. The history for your care team is locked on your phone with your hospital's key. Only its doctors can unlock it. SafeSignal only passes the locked copy along." },
      { q: 'Do you use cloud AI or tracking?', a: 'No. Speech is understood on the phone. There is no cloud speech service, no cloud AI on patient data, and no tracking or analytics.' },
      { q: 'Can I change my mind?', a: 'Yes. Turn sharing off any time in the app, and new check-ins stop going to your care team straight away.' },
    ],
  },
  {
    id: 'questions', label: 'All questions', tint: 'bg-blush', title: 'All questions',
    intro: 'Everything people usually ask, in one place.',
    items: [
      { q: 'Do I need to be good with phones?', a: 'No. The phone talks to you and listens. A family member can help.' },
      { q: 'Who hears what I say?', a: 'Nobody. Your voice and your words stay on your phone.' },
      { q: 'What if I miss a day?', a: 'Your caregiver and care team get a gentle heads-up. After three in a row, your emergency contacts are told too.' },
      { q: 'Can I stop?', a: 'Yes, any time, in the app.' },
      { q: 'Does it replace my doctor?', a: 'No. It helps your doctor know how you have been. In an emergency, call 911.' },
      { q: 'How do I get it?', a: 'Ask your doctor or nurse whether it is offered for your treatment.' },
    ],
  },
]

export const CONTACT_EMAIL = '[YOUR EMAIL]'
