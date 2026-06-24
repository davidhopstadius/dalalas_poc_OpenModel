import { useState } from 'react'
import { KeyRound } from 'lucide-react'
import { api } from '../api'
import type { User } from '../types'

export default function Login({ onLoggedIn }: { onLoggedIn: (user: User) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const user = await api.login(email.trim(), password)
      onLoggedIn(user)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid h-full place-items-center px-4">
      <div className="w-full max-w-[360px]">
        <div className="mb-7 flex flex-col items-center text-center">
          <div className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-accent text-white shadow-sm">
            <KeyRound size={28} strokeWidth={2} />
          </div>
          <h1 className="font-display text-[22px] font-semibold tracking-tight">
            Låsmontörens bästa vän
          </h1>
          <p className="mt-1.5 text-[13.5px] text-ink-soft">Logga in för att fortsätta</p>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="mb-1 block text-[12.5px] font-medium text-ink-soft">E-post</label>
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              className="w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-[14px] text-ink outline-none transition focus:border-accent/50 focus:ring-2 focus:ring-accent/15"
            />
          </div>
          <div>
            <label className="mb-1 block text-[12.5px] font-medium text-ink-soft">Lösenord</label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-[14px] text-ink outline-none transition focus:border-accent/50 focus:ring-2 focus:ring-accent/15"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-danger/25 bg-danger/5 px-3.5 py-2.5 text-[13px] text-danger">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-accent px-4 py-2.5 text-[14px] font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
          >
            {busy ? 'Loggar in…' : 'Logga in'}
          </button>
        </form>
      </div>
    </div>
  )
}
