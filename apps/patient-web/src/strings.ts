// Every word the patient sees, in one place, so another language can be added without touching a screen.
//
// To add Spanish: write `const es: Strings = { ... }` with the same keys (TypeScript lists any missing key), add it
// to STRINGS, and pick it with `t('es')`. Components never hold their own text: tests/strings.test.ts checks that.
//
// Rules for the words (NF-08, SE-04): plain and short; a symptom is "for review", never described as caused by
// anything; nothing here ever holds a patient's words (those live only in memory, and only on the screen).

type Hour = number

const en = {
  /** Shown at the top of the home screen. The name is only ever shown on this screen. */
  home: {
    greeting: (hour: Hour, name: string) => {
      const part = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'
      return name.trim() ? `Good ${part}, ${name.trim()}` : `Good ${part}`
    },
    lead: 'I will ask you a few short questions out loud. Answer in your own words.',
    privacy: 'Your voice stays on this computer. Nothing is shared until you say so.',
    preparing: 'Getting your check-in ready…',
    start: "Start today's check-in",
    tryAgain: 'Try again',
    moreHeading: 'Other things you can do',
    consent: 'Who I share with',
    networkLog: 'What this computer sent',
  },

  /** The check-in, shown as a conversation. */
  checkin: {
    progress: (number: number, total: number) => `Question ${number} of ${total}`,
    progressNone: 'Daily check-in',
    conversation: 'Our conversation',
    helperSays: 'I asked:',
    youSaid: 'You said:',
    reask: 'Let me ask that more simply.',
    repeat: 'Saying it again',
    slower: 'Saying it more slowly',
    moveOn: "That's okay, let's move on.",
    hearAgain: 'Repeat',
    slowerButton: 'Slower',
    typeLabel: 'Or type your answer',
    send: 'Send',
    tryAgain: 'Try again',
    startAgain: 'Start again',
    next: 'Next question',
    finish: 'Finish check-in',
    status: {
      micStarting: 'Getting the microphone ready…',
      listening: 'I am listening. Take your time; pauses are fine.',
      sending: 'Thinking about your answer…',
      loading: 'Getting the question…',
      voiceLoading: 'Getting the question ready to play…',
      speaking: 'Reading the question out loud…',
    },
    talk: {
      idle: 'Tap to answer',
      starting: 'Getting ready…',
      listening: "Listening… tap when you're done",
      sending: 'Thinking…',
    },
    noWords: 'I did not catch any words. Tap to answer again, or go on to the next question.',
    notChecked: 'I could not check this answer for symptoms right now.',
    noSymptoms: 'No symptoms noted.',
    notedForReview: 'Noted for review:',
  },

  /** The sound controls at the top of every screen and beside "Repeat". */
  sound: {
    mute: 'Mute',
    unmute: 'Unmute',
    stop: 'Stop',
    offNote: 'Sound is off. Tap Unmute to hear it.',
  },

  /** Every message the patient may see when something goes wrong, in plain words (src/messages.ts picks one). */
  errors: {
    runtimeDown:
      'The check-in helper on this computer is not running. Please ask your helper to start it, then try again.',
    somethingWrong: 'Something went wrong. Please try again.',
    sessionLost: 'This check-in is no longer open on this computer. Please start the check-in again.',
    start: {
      questionsMissing:
        "Today's questions are not on this computer yet. They are downloaded when this computer is online. Please check the internet connection, then tap Start today's check-in again.",
      other: 'I could not start the check-in. Please try again.',
    },
    summary: 'I could not put your summary together. Nothing was shared. Please try again.',
    share: {
      runtimeDown:
        'The check-in helper on this computer is not answering. Please ask your helper to start it, then tap Share this again. It will never be sent twice.',
      needsSeverity: 'Please choose how bad each problem is, then tap Share this again.',
      recordRefused: 'The privacy check on this computer stopped this record, so nothing was sent. Please tell your helper.',
      alreadyShared: 'This check-in was already shared. Nothing more was sent.',
      other: 'Something went wrong. Please tap Share this again. It will never be sent twice.',
    },
    microphone: {
      blocked:
        'The microphone is blocked for this page. Please allow the microphone in the browser, then tap to answer again.',
      notFound: 'No microphone was found. Please check that a microphone is connected, then try again.',
      busy: 'The microphone is being used by another program. Please close that program, then try again.',
      unsupported: 'This browser cannot record your voice. Please use a recent version of Chrome, Edge, Firefox or Safari.',
      failed: 'The recording stopped by itself. Please tap to answer again.',
    },
    answer: {
      speechUnavailable:
        'The speech helper on this computer is not ready yet, so I cannot understand answers. Please ask your helper to set it up.',
      notUnderstood: 'Sorry, I could not make out that answer. Please tap and try again.',
      emptyAudio: 'I did not hear anything. Please tap the button, speak, then tap again when you are done.',
      tooLarge: 'That answer was too long to send. Please tap and give a shorter answer.',
      badFormat:
        'This browser recorded the answer in a format I cannot use. Please try a recent version of Chrome, Edge, Firefox or Safari.',
      forbidden: 'This screen is not allowed to send answers. Please open it on the same computer as the check-in helper.',
      alreadyShared:
        'This check-in has already been shared, so no more answers can be added. Please start a new check-in.',
    },
    typed: {
      empty: 'Please type your answer in the box first, then tap Send.',
      tooLong: 'That answer is too long. Please make it shorter, then tap Send again.',
      unavailable:
        'The check-in helper on this computer cannot read answers right now. Please ask your helper, or try again later.',
    },
    correction: {
      notUnderstood:
        'Sorry, I did not understand the change. Nothing was changed. Please say it again, or tap to change it.',
      used: 'This summary cannot be changed again. You can share it as it is, or tap Not now.',
      notUnderstoodShort: 'Sorry, I did not understand the change. Nothing was changed. Please try again.',
      other: 'Something went wrong. Nothing was changed. Please try again.',
    },
    summaryVoice: {
      tapToHear: 'Tap “Repeat” to hear your summary.',
      other: 'I cannot read your summary out loud right now. Please read it on the screen.',
    },
    question: 'I could not load the question. Please try again.',
    questionVoice: {
      tapToHear: 'Tap “Repeat” to hear the question.',
      other: 'I cannot say the question out loud right now. Please read it on the screen.',
    },
    consentLoad: 'I could not show who you share with. Nothing was changed. Please try again.',
    consentUnavailable: 'This cannot be turned on: nobody is set up for it on this computer yet. Please ask your helper.',
    consentChange: 'I could not change this. Nothing was changed. Please try again.',
    setupRefused: 'Some of your choices could not be saved. Please check them and try again.',
    setupSave: 'I could not save your choices. Nothing was changed. Please try again.',
    networkLog: 'I could not show what this computer sent. Please try again.',
  },

  /** Plain words for the summary, the "what will be shared" box and the receipt (src/summaryText.ts uses them). */
  plain: {
    onset: {
      today: 'today',
      '1_3_days': '1 to 3 days ago',
      '4_7_days': '4 to 7 days ago',
      over_7_days: 'more than a week ago',
    } as Record<string, string>,
    onsetUnknown: 'start not known',
    onsetUnknownSentence: 'Start not known',
    onsetSentence: (words: string) => `Started ${words}`,
    severity: { mild: 'Mild', moderate: 'Moderate', severe: 'Severe' },
    severityUnknown: 'Not known',
    severityQuestion: (name: string) => `How bad is the ${name}?`,
    problem: 'problem',
    symptom: (label: string, severity: string | null) => (severity ? `${label}, ${severity}` : label),
    possibleLink:
      'Marked for review: this started within a week of something new you began. That does not mean one caused the other.',
    nothingToReport: 'You did not report any new problems.',
    sharedParts: {
      symptoms: 'Each problem as a code: what it is, how bad, when it started, and whether it is marked for review',
      unanswered: 'How many questions had no answer',
      status: 'Whether the check-in was finished',
      week: 'The week of this check-in, not the day',
      ref: 'A random code instead of your name',
      program: 'Your study group and medicine version',
      reporter: 'Who answered, and whether by voice or typing',
      consent: 'Who you agreed may see your check-ins',
      schema: 'The version of this record format',
      other: 'Other coded answers (see the exact list)',
    },
    receiptStatus: { sent: 'Shared', queued: 'Saved on this computer.', failed: 'Not accepted' },
    queuedExplanation: 'It will be sent automatically when the connection is back.',
    alert: {
      sent: 'Your care team was told about the severe symptom.',
      queued: 'Your care team will be told about the severe symptom when the connection is back.',
      failed: 'I could not tell your care team about the severe symptom. Please call them, or tell your helper.',
    },
    onsetChoices: {
      today: 'Today',
      '1_3_days': '1 to 3 days ago',
      '4_7_days': '4 to 7 days ago',
      over_7_days: 'More than a week ago',
      unknown: 'Not sure',
    },
    careParts: {
      name: 'Your name',
      age: 'Your age',
      date: 'The date of this check-in',
      medicine: 'Your medicine',
      symptoms: 'Your symptoms: what each one is, how bad, and when it started',
      trend: 'How you are doing compared with before',
      reporter: 'Who answered',
      status: 'Whether the check-in was finished',
      ref: 'A code for your file, and the version of this record format',
      other: 'Other details (see the exact list)',
    },
    careTeamSealed: 'Sent to your care team, sealed: only your doctors can read it.',
    careTeamOff: 'Your doctor gets nothing from this check-in: sharing with your doctor is off.',
    careTeamDestination: 'Your care team (sealed: only your doctors can read it)',
    emergencyDestination: 'Your emergency hospital (sealed: opened only in an emergency, and that is logged)',
    and: 'and',
    emergencyCopy: (list: string) => `Also sealed for ${list}: they can open it only in an emergency, and that is logged.`,
    sealedHeading: { emergency: "Emergency hospital's sealed copy", care: "Your doctor's sealed copy" },
    sealed: {
      nounEmergency: "The emergency hospital's sealed copy",
      nounCare: "Your doctors' sealed copy",
      refusedEmergency: "The service did not accept the emergency hospital's sealed copy. Please tell your helper.",
      refusedCare: "The service did not accept your doctors' sealed copy. Please tell your helper.",
      offline: (noun: string) => `${noun} is saved on this computer. It will be sent when you're back online.`,
      sentEmergency:
        'Your emergency hospital got a sealed copy: they can open it only in an emergency, and that is logged.',
      sentCare: 'Your doctors got a sealed copy: only they can read it.',
      noKey: (noun: string, emergency: boolean) =>
        `${noun} is waiting: ${emergency ? 'that hospital has' : 'their hospital has'} not set up its lock yet. It will be sent later by itself.`,
      waiting: (noun: string) => `${noun} is waiting on this computer. It will be sent later by itself.`,
    },
  },

  /** The summary, approval and the "Change one answer" panel. */
  summary: {
    progress: 'End of check-in',
    loadingTitle: 'Your summary',
    putting: 'Putting your summary together…',
    title: "Here's what you're sharing",
    alreadyShared: 'You have already shared this check-in.',
    hearAgain: 'Repeat',
    slower: 'Slower',
    toldHeading: 'What you told me',
    unanswered: (count: number) =>
      count === 1 ? '1 question had no answer. That is fine.' : `${count} questions had no answer. That is fine.`,
    forReview: 'For review',
    howBad: (severity: string) => `How bad: ${severity}`,
    youChose: (choice: string) => `You chose: ${choice}`,
    notChosen: 'Not chosen yet',
    changeOne: 'Change one answer',
    canChangeOne: 'You can change one thing before sharing.',
    sayChange: 'Say the change',
    tapChange: 'Tap to change',
    sayExample: "For example: “The rash is mild”, or “I don't have a headache”.",
    changing: 'Changing it…',
    tapAndSay: 'Tap and say the change',
    tapInstead: 'Tap to change instead',
    whichOne: 'Which one do you want to change?',
    whenStart: 'When did it start?',
    dontHave: "I don't have this",
    changingSummary: 'Changing your summary…',
    keep: 'Keep it as it is',
    sharing: 'Sharing…',
    chooseHint: 'Choose how bad each problem is, then tap Share this.',
    share: 'Share this',
    notNow: 'Not now',
    tryAgain: 'Try again',
    startAgain: 'Start again',
    box: {
      heading: 'What will be shared',
      whoGetsIt: 'Who gets it:',
      onlyCoded: 'Only coded answers:',
      onlyCodedRest: 'no name, no words you said, no recording.',
      noProblems: 'It tells them you had no new problems.',
      yourDoctor: 'Your doctor',
      insideSealed: 'Inside the sealed copy:',
      showExact: 'Show exactly what is sent',
      hideExact: 'Hide exactly what is sent',
      sentWith: 'Sent with:',
      fieldNames: (count: number) => `Field names (${count})`,
      theRecord: 'The record',
      recordLater:
        'The record is completed with your answers to “How bad” when you tap Share this. The receipt then shows its fingerprint.',
      sealedForCare: 'Sealed copy for your care team',
      lockedFor: 'Locked for:',
      insideSealedCount: (count: number) => `Inside the sealed copy (${count})`,
    },
  },

  /** The egress receipt (PV-05) and "Nothing was shared". */
  receipt: {
    progress: 'Receipt',
    failedLead: "The safety team's service did not accept this record. Please tell your helper.",
    plainHeading: (queued: boolean) => (queued ? 'What will be shared, in plain words' : 'What was shared, in plain words'),
    sentTo: 'Sent to',
    willBeSentTo: 'Will be sent to',
    sentAt: 'Sent at',
    triedAt: 'Tried at',
    notYet: 'Not yet: it is waiting for the internet',
    recordNumber: 'Record number',
    serviceAnswer: 'Answer from the service',
    code: (code: number) => `Code ${code}`,
    whatSent: (queued: boolean) => `${queued ? 'What will be sent' : 'What was sent'}: coded answers only`,
    fingerprint: 'Fingerprint',
    fingerprintNote: (queued: boolean) =>
      `This code is a fingerprint of exactly what ${queued ? 'will be' : 'was'} sent. It matches the entry in this computer's network log.`,
    sealedFingerprintNote:
      "This code is a fingerprint of the sealed copy. It matches the entry in this computer's network log.",
    thanks: "Thank you, that's all for today.",
    home: 'Back to the start',
    nothingShared: 'Nothing was shared.',
    backToSummary: 'Go back to my summary',
  },

  /** "Who I share with" (CN-01, CN-03). */
  consent: {
    title: 'Who I share with',
    lead: 'Tap a switch to turn it on or off. A change counts straight away.',
    loading: 'Getting your choices…',
    tryAgain: 'Try again',
    change: 'Change my choices',
    back: 'Back to my check-in',
    saving: 'Saving…',
    on: 'On',
    off: 'Off',
    switches: {
      share_care_team: {
        label: 'Share with my doctor',
        on: "Your doctor's team gets your check-ins, sealed so only they can read them.",
        off: "Your doctor's team gets nothing new from now on.",
        nobody: 'No doctor is set up on this computer yet, so this cannot be turned on. Please ask your helper.',
      },
      share_caregiver: {
        label: 'Share with my caregiver',
        on: 'Your caregiver is told when you report a severe problem.',
        off: 'Your caregiver gets nothing new from now on.',
        nobody: 'No caregiver is set up on this computer yet, so this cannot be turned on. Please ask your helper.',
      },
    },
    receipt: {
      none: 'Saved on this device.',
      sent: 'Saved and sent.',
      queued: "Saved on this device. It will be sent when you're back online.",
      failed: 'Saved on this device, but the service did not accept it. Please tell your helper.',
    },
  },

  /** "Set up who I share with". */
  setup: {
    title: 'Set up who I share with',
    loading: 'Getting your choices…',
    tryAgain: 'Try again',
    back: 'Back',
    cancel: 'Cancel',
    next: 'Next',
    saved: 'Your choices are saved',
    backToConsent: 'Back to who I share with',
    step: (number: number, total: number) => `Step ${number} of ${total}`,
    stepTitles: { care: 'My care team', caregiver: 'My caregiver', emergency: 'Emergencies', review: 'Check and send' },
    savingStatus: 'Saving and sending…',
    sending: 'Sending…',
    saveAndSend: 'Save and send',
    youChose: (choices: string) => `You chose: ${choices}`,
    notChosen: 'Not chosen yet',
    none: 'None',
    care: {
      lead: 'Your care team is the hospital or clinic that looks after you.',
      question: 'Which hospital or clinic looks after you?',
    },
    caregiver: {
      lead: 'A caregiver is someone who helps look after you, like a family member.',
      question: 'Who is your caregiver?',
      alertsOnly: (detail: string) => `${detail}: your caregiver is told when you report a severe problem.`,
    },
    emergency: {
      question: 'Let an emergency hospital see my history in an emergency?',
      yes: 'Yes',
      no: 'No',
      hint: 'If yes, they can open it only in an emergency, and every time is logged. If no, nothing about emergencies is kept or sent.',
      hospitals: (max: number) => `Which hospitals? Choose up to ${max}.`,
      careNotListed: 'Your care team is not in this list: it already has your check-ins.',
      contactsHeading: 'Who to call in an emergency',
      contactsLead: (max: number) => `Up to ${max}. The first one is called first.`,
      addContact: 'Add a contact',
    },
    contact: {
      title: (number: number) => `Contact ${number}`,
      who: 'Who is it?',
      whichHospital: 'Which hospital? (you can skip this)',
      notListed: 'Not listed',
      phone: 'Phone number',
      phoneHint: 'For example +1 555 010 0199, or 911.',
      label: 'A name for it (you can skip this)',
      labelHint: 'This name stays on this computer. It is never sent.',
      earlier: 'Call earlier',
      later: 'Call later',
      remove: (number: number) => `Remove contact ${number}`,
      types: { emergency_service: 'An emergency number (like 911)', hospital: 'A hospital', person: 'A person' },
    },
    caregiverDetail: { alerts_only: 'Only alerts', summary: 'Alerts and a summary' },
    review: {
      lead: 'Please check your choices. Nothing is sent until you tap Save and send.',
      change: (title: string) => `Change ${title.toLowerCase()}`,
      whatSentHeading: 'What will be sent',
      chosenFallback: 'the one you chose',
      noCare: 'No care team. Your doctor gets nothing.',
      careOn: (name: string) => `${name}: your check-ins go to them sealed, so only they can read them.`,
      sharingOff: (name: string) => `${name}: sharing is off, so they get nothing new.`,
      noCaregiver: 'No caregiver. Nobody else is told anything.',
      caregiverOn: (name: string) => `${name}: only alerts about a severe problem.`,
      emergencyNo: 'No. No emergency hospital or contact is kept or sent.',
      emergencyYes: 'Yes. An emergency hospital may open your history only in an emergency, and that is logged.',
      noHospital: 'No emergency hospital chosen.',
      hospitals: (names: string) => `Hospitals: ${names}.`,
      noContacts: 'No contacts.',
      contactLine: (priority: number, type: string, where: string, phone: string) =>
        `Contact ${priority}: ${type}${where}, ${phone}.`,
      sentLines: {
        gate: 'A coded update goes through the privacy check on this computer to the service.',
        withPhones:
          'It holds the codes of the places and the caregiver you chose, whether each one is on, and the phone numbers of your emergency contacts.',
        noPhones:
          'It holds the codes of the places and the caregiver you chose, and whether each one is on. No phone numbers.',
        noNames: 'No names are sent. The names you typed for your contacts stay on this computer.',
      },
    },
    problems: {
      chooseCare: 'Choose your hospital or clinic, or turn off sharing with your doctor.',
      chooseCaregiver: 'Choose your caregiver, or turn off sharing with your caregiver.',
      careIsEmergency: 'Your care team cannot also be your emergency hospital. Please choose another hospital.',
      tooManyHospitals: (max: number) => `Choose at most ${max} emergency hospitals.`,
      tooManyContacts: (max: number) => `You can have at most ${max} contacts.`,
      contact: (number: number) => `Contact ${number}`,
      noPhone: (which: string) => `${which}: please type a phone number.`,
      badPhone: (which: string) =>
        `${which}: the phone number should start with + and the country code (for example +1 555 010 0199), or be an emergency number like 911.`,
      labelTooLong: (which: string, max: number) => `${which}: the name can be at most ${max} letters.`,
      hospitalAgain: (which: string) => `${which}: please choose the hospital again.`,
    },
  },

  /** "What this computer sent" (PV-06). */
  networkLog: {
    title: 'What this computer sent',
    onlyThese: 'Only these went out. Nothing else leaves this computer: no recordings, no words you said.',
    nothingSent: 'Nothing has been sent yet.',
    loading: 'Getting the list…',
    tryAgain: 'Try again',
    refresh: 'Refresh',
    back: 'Back',
    timeUnknown: 'Time not known',
    showDetails: 'Show details',
    hideDetails: 'Hide details',
    sentWith: 'Sent with',
    answerCode: 'Answer code',
    askedWith: 'Asked with',
    fieldNames: 'Field names',
    none: 'None',
    fingerprint: 'Fingerprint',
    status: {
      accepted: 'Accepted',
      refused: 'Refused',
      retry: 'Service error, will try again',
      unknown: 'Answer not known',
    },
    what: {
      survey: "Today's questions downloaded",
      terms: 'Symptom word list downloaded',
      careTeam: 'your care team',
      emergencyHospital: 'an emergency hospital',
      someOrg: 'a hospital or clinic',
      careOrEmergency: 'your care team or an emergency hospital',
      lock: (who: string, name: string) => `Lock for ${who}${name} fetched`,
      settings: 'Settings downloaded',
      record: 'Check-in sent to the drug company safety team (coded answers only, no name)',
      sealed: (who: string, name: string) => `Sealed copy sent to ${who}${name}`,
      alert: 'Severe-problem alert sent',
      consent: 'Your sharing choices sent',
      otherSend: 'Something sent to the service (see the details)',
      other: 'Something sent or fetched (see the details)',
    },
  },
}

/** The shape every language must fill in. */
export type Strings = typeof en

export const STRINGS = { en } satisfies Record<string, Strings>

export type Locale = keyof typeof STRINGS

export const DEFAULT_LOCALE: Locale = 'en'

/** The words for one language (English for now). */
export function t(locale: Locale = DEFAULT_LOCALE): Strings {
  return STRINGS[locale]
}

/** The words this screen shows. */
export const S: Strings = t()
