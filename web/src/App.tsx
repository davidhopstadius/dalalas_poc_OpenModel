import { useCallback, useEffect, useState } from 'react'
import { KeyRound, Menu } from 'lucide-react'
import { api, setUnauthorizedHandler } from './api'
import type { ConversationSummary, Settings, User, View } from './types'
import Sidebar from './components/Sidebar'
import ChatView from './components/ChatView'
import DocumentsView from './components/DocumentsView'
import DriftInfoView from './components/DriftInfoView'
import SettingsView from './components/SettingsView'
import UsersView from './components/UsersView'
import Login from './components/Login'

// Vyer som bara admins kommer åt. Icke-admins som råkar hamna här (t.ex. via
// gammal state) skickas tillbaka till chatten.
const ADMIN_VIEWS: View[] = ['documents', 'driftinfo', 'settings', 'users']

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [view, setView] = useState<View>('chat')
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const isAdmin = !!user?.is_admin

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations())
    } catch {
      /* ignorera - backend kanske inte uppe an */
    }
  }, [])

  const refreshSettings = useCallback(async () => {
    try {
      setSettings(await api.getSettings())
    } catch {
      /* icke-admin (403) eller backend nere - lat settings vara null */
    }
  }, [])

  // Kolla befintlig session vid start; nolla user vid 401 (utgangen session).
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true))
  }, [])

  // Ladda data nar vi vet vem som ar inloggad.
  useEffect(() => {
    if (!user) {
      setConversations([])
      setSettings(null)
      setActiveId(null)
      return
    }
    refreshConversations()
    if (user.is_admin) refreshSettings()
  }, [user, refreshConversations, refreshSettings])

  // Skydda admin-vyer i frontend (backend gatar redan, detta ar bara UX).
  useEffect(() => {
    if (!isAdmin && ADMIN_VIEWS.includes(view)) setView('chat')
  }, [isAdmin, view])

  const openConversation = (id: string) => {
    setActiveId(id)
    setView('chat')
    setSidebarOpen(false)
  }

  const newChat = () => {
    setActiveId(null)
    setView('chat')
    setSidebarOpen(false)
  }

  const goTo = (v: View) => {
    setView(v)
    setSidebarOpen(false)
  }

  const logout = async () => {
    try {
      await api.logout()
    } catch {
      /* ignorera */
    }
    setUser(null)
    setView('chat')
  }

  if (!authChecked) {
    return <div className="grid h-full place-items-center text-[14px] text-ink-faint">Laddar…</div>
  }

  if (!user) {
    return <Login onLoggedIn={setUser} />
  }

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar
        view={view}
        user={user}
        conversations={conversations}
        activeId={activeId}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={newChat}
        onOpenConversation={openConversation}
        onGoTo={goTo}
        onConversationsChanged={refreshConversations}
        onActiveCleared={() => setActiveId(null)}
        onLogout={logout}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        {/* Mobil topbar */}
        <header className="flex items-center gap-3 border-b border-line px-4 py-3 md:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="grid h-9 w-9 place-items-center rounded-lg border border-line bg-surface text-ink-soft transition hover:text-ink"
            aria-label="Oppna meny"
          >
            <Menu size={18} />
          </button>
          <span className="flex items-center gap-2 font-display text-[15px] font-semibold tracking-tight">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-white">
              <KeyRound size={15} strokeWidth={2.2} />
            </span>
            Låsmontörens bästa vän
          </span>
        </header>

        {view === 'chat' && (
          <ChatView
            conversationId={activeId}
            settings={settings}
            onConversationCreated={(id) => {
              setActiveId(id)
              refreshConversations()
            }}
            onTitleMaybeChanged={refreshConversations}
            onOpenSettings={() => isAdmin && setView('settings')}
          />
        )}
        {view === 'documents' && isAdmin && <DocumentsView />}
        {view === 'driftinfo' && isAdmin && <DriftInfoView />}
        {view === 'settings' && isAdmin && (
          <SettingsView settings={settings} onSaved={refreshSettings} />
        )}
        {view === 'users' && isAdmin && <UsersView currentUser={user} />}
      </main>
    </div>
  )
}
