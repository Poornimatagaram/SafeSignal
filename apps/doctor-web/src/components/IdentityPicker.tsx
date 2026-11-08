// First launch (DW-19): this browser holds one doctor. Creates the personal key pair here; only the public key is sent.
import { useState } from 'react'
import { DEMO_DOCTORS } from '../lib/config'

export function IdentityPicker({ onPick }: { onPick: (doctorId: string) => Promise<void> }) {
  const [busy, setBusy] = useState(false)
  return (
    <div className="mx-auto mt-16 max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h1 className="text-lg font-semibold">Who is using this browser?</h1>
      <p className="mt-1 text-sm text-slate-500">
        A personal key pair is created here. The private key never leaves this browser. Use another browser profile or
        origin for a second doctor.
      </p>
      <div className="mt-4 grid gap-2">
        {DEMO_DOCTORS.map((d) => (
          <button
            key={d.doctor_id}
            disabled={busy}
            onClick={async () => {
              setBusy(true)
              await onPick(d.doctor_id)
            }}
            className="rounded border border-slate-300 px-3 py-2 text-left hover:bg-slate-50 disabled:opacity-50"
          >
            <span className="font-medium">{d.display_name}</span>
            <span className="ml-2 font-mono text-xs text-slate-400">{d.doctor_id}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
