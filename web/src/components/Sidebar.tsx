import {
  Activity,
  FileText,
  KeyRound,
  LogOut,
  Plus,
  Settings as SettingsIcon,
  Trash2,
  Users as UsersIcon,
  X,
} from 'lucide-react'
import { api } from '../api'
import type { ConversationSummary, User, View } from '../types'

const PROVIDER_LABELS: Record<string, string> = {
  grunden: 'Grunden',
  berget: 'Berget',
  anthropic: 'Anthropic',
}

/** Tooltip-text som visar vilken modell/leverantör samtalet startades med. */
function modelTooltip(c: ConversationSummary): string | undefined {
  if (!c.model) return undefined
  const prov = c.provider ? PROVIDER_LABELS[c.provider] ?? c.provider : null
  return prov ? `Startad med ${prov} · ${c.model}` : `Startad med ${c.model}`
}

interface Props {
  view: View
  user: User
  conversations: ConversationSummary[]
  activeId: string | null
  open: boolean
  onClose: () => void
  onNewChat: () => void
  onOpenConversation: (id: string) => void
  onGoTo: (v: View) => void
  onConversationsChanged: () => void
  onActiveCleared: () => void
  onLogout: () => void
}

export default function Sidebar({
  view,
  user,
  conversations,
  activeId,
  open,
  onClose,
  onNewChat,
  onOpenConversation,
  onGoTo,
  onConversationsChanged,
  onActiveCleared,
  onLogout,
}: Props) {
  const remove = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    await api.deleteConversation(id)
    if (id === activeId) onActiveCleared()
    onConversationsChanged()
  }

  return (
    <>
      {/* Mobil-overlay */}
      {open && (
        <div
          className="fixed inset-0 z-20 bg-ink/20 backdrop-blur-[2px] md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-[272px] flex-col border-r border-line bg-surface
          transition-transform duration-300 ease-out md:relative md:translate-x-0
          ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* Varumarke */}
        <div className="flex items-center justify-between px-5 pb-4 pt-5">
          <div className="flex items-center gap-2.5">
            <div className="grid h-8 w-8 place-items-center rounded-[10px] bg-accent text-white shadow-sm">
              <KeyRound size={17} strokeWidth={2.2} />
            </div>
            <div className="leading-tight">
              <div className="font-display text-[14.5px] font-semibold leading-tight tracking-tight">
                Låsmontörens bästa vän
              </div>
              <div className="text-[11px] text-ink-faint">Låsteknik-assistent</div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-ink-soft transition hover:bg-line-soft md:hidden"
            aria-label="Stäng meny"
          >
            <X size={17} />
          </button>
        </div>

        <div className="px-3">
          <button
            onClick={onNewChat}
            className="flex w-full items-center gap-2 rounded-xl border border-line bg-surface-raised px-3.5 py-2.5 text-[14px] font-medium text-ink shadow-[0_1px_0_rgba(27,28,25,0.03)] transition hover:border-accent/40 hover:text-accent"
          >
            <Plus size={17} strokeWidth={2.2} />
            Nytt samtal
          </button>
        </div>

        {/* Samtalslista */}
        <nav className="mt-5 flex-1 overflow-y-auto px-3">
          <div className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Samtal
          </div>
          {conversations.length === 0 && (
            <p className="px-2 py-2 text-[13px] text-ink-faint">Inga samtal än.</p>
          )}
          <ul className="space-y-0.5">
            {conversations.map((c) => {
              const active = view === 'chat' && c.id === activeId
              return (
                <li key={c.id}>
                  <button
                    onClick={() => onOpenConversation(c.id)}
                    title={modelTooltip(c)}
                    className={`group flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13.5px] transition
                      ${active ? 'bg-accent-soft text-accent-hover' : 'text-ink-soft hover:bg-line-soft hover:text-ink'}`}
                  >
                    <span className="min-w-0 flex-1 truncate">{c.title}</span>
                    <span
                      onClick={(e) => remove(e, c.id)}
                      className="opacity-0 transition group-hover:opacity-100 hover:text-danger"
                      aria-label="Radera samtal"
                    >
                      <Trash2 size={15} />
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* Botten-navigering - admin-verktyg syns bara for admins */}
        {user.is_admin && (
          <div className="space-y-0.5 border-t border-line px-3 py-3">
            <NavItem
              icon={<FileText size={17} />}
              label="Dokument"
              active={view === 'documents'}
              onClick={() => onGoTo('documents')}
            />
            <NavItem
              icon={<Activity size={17} />}
              label="Driftinfo"
              active={view === 'driftinfo'}
              onClick={() => onGoTo('driftinfo')}
            />
            <NavItem
              icon={<UsersIcon size={17} />}
              label="Användare"
              active={view === 'users'}
              onClick={() => onGoTo('users')}
            />
            <NavItem
              icon={<SettingsIcon size={17} />}
              label="Inställningar"
              active={view === 'settings'}
              onClick={() => onGoTo('settings')}
            />
          </div>
        )}

        {/* Inloggad anvandare + utloggning */}
        <div className="flex items-center gap-2 border-t border-line px-3 py-3">
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-medium text-ink" title={user.email}>
              {user.email}
            </div>
            <div className="text-[11px] text-ink-faint">{user.is_admin ? 'Admin' : 'Användare'}</div>
          </div>
          <button
            onClick={onLogout}
            className="grid h-8 w-8 place-items-center rounded-lg text-ink-soft transition hover:bg-line-soft hover:text-ink"
            aria-label="Logga ut"
            title="Logga ut"
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>
    </>
  )
}

function NavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] font-medium transition
        ${active ? 'bg-accent-soft text-accent-hover' : 'text-ink-soft hover:bg-line-soft hover:text-ink'}`}
    >
      {icon}
      {label}
    </button>
  )
}
