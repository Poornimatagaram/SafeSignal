// The name in the home screen's greeting ("Good morning, Walter"). The runtime does not give the patient's name to
// this screen, so it comes from `VITE_PATIENT_DISPLAY_NAME`. It is only ever shown on the screen: never sent, logged
// or stored.
export const DEFAULT_DISPLAY_NAME = 'Walter'

const MAX_NAME = 40

/** The configured name, trimmed and kept short; the default when none is set. */
export function resolveDisplayName(configured: string | undefined | null): string {
  const name = (configured ?? '').trim().slice(0, MAX_NAME)
  return name || DEFAULT_DISPLAY_NAME
}
