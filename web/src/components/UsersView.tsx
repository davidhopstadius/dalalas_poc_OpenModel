import { useEffect, useState } from 'react'
import { KeyRound, ShieldCheck, Trash2, UserPlus } from 'lucide-react'
import { api } from '../api'
import type { User, UserSummary } from '../types'

export default function UsersView({ currentUser }: { currentUser: User }) {
  const [users, setUsers] = useState<UserSummary[]>([])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = () => api.listUsers().then(setUsers).catch(() => {})

  useEffect(() => {
    refresh()
  }, [])

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      await api.createUser(email.trim(), password, isAdmin)
      setNotice(`Skapade ${email.trim()}.`)
      setEmail('')
      setPassword('')
      setIsAdmin(false)
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const toggleAdmin = async (u: UserSummary) => {
    setError(null)
    try {
      await api.updateUser(u.id, { is_admin: !u.is_admin })
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const resetPassword = async (u: UserSummary) => {
    const pw = window.prompt(`Nytt lösenord för ${u.email} (minst 6 tecken):`)
    if (pw == null) return
    setError(null)
    setNotice(null)
    try {
      await api.updateUser(u.id, { password: pw })
      setNotice(`Lösenord uppdaterat för ${u.email}.`)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const remove = async (u: UserSummary) => {
    if (!window.confirm(`Ta bort ${u.email}? Användarens samtal raderas också.`)) return
    setError(null)
    try {
      await api.deleteUser(u.id)
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[760px] px-5 py-8 md:px-6">
        <h1 className="font-display text-[22px] font-semibold tracking-tight">Användare</h1>
        <p className="mt-1.5 text-[14px] text-ink-soft">
          Skapa konton för dem som ska testa appen. Varje användare har egen chatthistorik.
          Admins kan dessutom se inställningar, driftinfo och dokument.
        </p>

        {/* Skapa ny */}
        <form
          onSubmit={create}
          className="mt-6 rounded-2xl border border-line bg-surface p-4"
        >
          <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-ink">
            <UserPlus size={16} className="text-accent" />
            Ny användare
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              type="email"
              placeholder="E-post"
              autoComplete="off"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="rounded-xl border border-line bg-surface px-3.5 py-2.5 text-[14px] text-ink outline-none transition focus:border-accent/50 focus:ring-2 focus:ring-accent/15"
            />
            <input
              type="text"
              placeholder="Lösenord (minst 6 tecken)"
              autoComplete="off"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="rounded-xl border border-line bg-surface px-3.5 py-2.5 text-[14px] text-ink outline-none transition focus:border-accent/50 focus:ring-2 focus:ring-accent/15"
            />
          </div>
          <div className="mt-3 flex items-center justify-between">
            <label className="flex cursor-pointer items-center gap-2 text-[13.5px] text-ink-soft">
              <input
                type="checkbox"
                checked={isAdmin}
                onChange={(e) => setIsAdmin(e.target.checked)}
                className="h-4 w-4 accent-accent"
              />
              Admin (ser inställningar &amp; driftinfo)
            </label>
            <button
              type="submit"
              disabled={busy}
              className="rounded-xl bg-accent px-4 py-2 text-[13.5px] font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
            >
              {busy ? 'Skapar…' : 'Skapa konto'}
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-4 rounded-xl border border-danger/25 bg-danger/5 px-4 py-3 text-[13.5px] text-danger">
            {error}
          </div>
        )}
        {notice && (
          <div className="mt-4 rounded-xl border border-accent/25 bg-accent-soft px-4 py-3 text-[13.5px] text-accent-hover">
            {notice}
          </div>
        )}

        {/* Lista */}
        <div className="mt-8">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Konton ({users.length})
          </div>
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
            {users.map((u) => {
              const isSelf = u.id === currentUser.id
              return (
                <li key={u.id} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 truncate text-[14px] text-ink">
                      {u.email}
                      {isSelf && <span className="text-[11.5px] text-ink-faint">(du)</span>}
                    </div>
                    <div className="mono text-[11.5px] text-ink-faint">
                      {u.is_admin ? 'Admin' : 'Användare'}
                    </div>
                  </div>

                  <button
                    onClick={() => toggleAdmin(u)}
                    title={u.is_admin ? 'Ta bort admin' : 'Gör till admin'}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11.5px] font-medium transition
                      ${
                        u.is_admin
                          ? 'border-accent/25 bg-accent-soft text-accent-hover'
                          : 'border-line bg-surface text-ink-faint hover:text-ink'
                      }`}
                  >
                    <ShieldCheck size={13} />
                    Admin
                  </button>

                  <button
                    onClick={() => resetPassword(u)}
                    className="grid h-8 w-8 place-items-center rounded-lg text-ink-faint transition hover:bg-line-soft hover:text-ink"
                    aria-label="Återställ lösenord"
                    title="Återställ lösenord"
                  >
                    <KeyRound size={15} />
                  </button>

                  <button
                    onClick={() => remove(u)}
                    disabled={isSelf}
                    className="grid h-8 w-8 place-items-center rounded-lg text-ink-faint transition hover:bg-line-soft hover:text-danger disabled:opacity-30 disabled:hover:text-ink-faint"
                    aria-label="Ta bort användare"
                    title={isSelf ? 'Du kan inte ta bort ditt eget konto' : 'Ta bort användare'}
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </div>
  )
}
