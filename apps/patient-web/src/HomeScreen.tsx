// Home: one bold sentence ("Good morning, Walter"), one giant action ("Start today's check-in"), and the other two
// places as big labelled buttons further down. No hidden menus.
import { S } from './strings.ts'
import { AlertIcon, HourglassIcon, ListIcon, MicIcon, PeopleIcon, WelcomeIllustration } from './Icons.tsx'

export interface HomeViewProps {
  /** Shown in the greeting only. */
  name: string
  /** 0-23, local time: picks "morning", "afternoon" or "evening". */
  hour: number
  starting: boolean
  startError: string | null
  onStart: () => void
  onConsent: () => void
  onNetworkLog: () => void
}

export function HomeView({ name, hour, starting, startError, onStart, onConsent, onNetworkLog }: HomeViewProps) {
  const H = S.home
  return (
    <main className="screen screen--home">
      <WelcomeIllustration className="home__picture" />
      <h1 className="title home__greeting">{H.greeting(hour, name)}</h1>
      <p className="lead">{H.lead}</p>

      <p className="status" role="status" aria-live="polite">
        {starting && (
          <>
            <HourglassIcon className="icon" />
            <span>{H.preparing}</span>
          </>
        )}
      </p>
      {startError && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <p>{startError}</p>
        </div>
      )}

      <button
        type="button"
        className="button button--primary button--huge button--start"
        aria-disabled={starting}
        onClick={onStart}
      >
        <MicIcon className="icon icon--large" />
        <span>{startError ? H.tryAgain : H.start}</span>
      </button>
      <p className="home__privacy">{H.privacy}</p>

      <section className="home__more" aria-labelledby="home-more">
        <h2 id="home-more" className="subtitle subtitle--small">
          {H.moreHeading}
        </h2>
        <button type="button" className="button button--secondary button--huge button--row" onClick={onConsent}>
          <PeopleIcon className="icon" />
          <span>{H.consent}</span>
        </button>
        <button type="button" className="button button--secondary button--huge button--row" onClick={onNetworkLog}>
          <ListIcon className="icon" />
          <span>{H.networkLog}</span>
        </button>
      </section>
    </main>
  )
}
