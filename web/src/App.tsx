import { useCallback, useEffect, useState } from 'react'
import { Menu } from 'lucide-react'
import { api } from './api'
import type { ConversationSummary, Settings, View } from './types'
import Sidebar from './components/Sidebar'
import ChatView from './components/ChatView'
import DocumentsView from './components/DocumentsView'
import DriftInfoView from './components/DriftInfoView'
import SettingsView from './components/SettingsView'

export default function App() {
  const [view, setView] = useState<View>('chat')
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

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
      /* ignorera */
    }
  }, [])

  useEffect(() => {
    refreshConversations()
    refreshSettings()
  }, [refreshConversations, refreshSettings])

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

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar
        view={view}
        conversations={conversations}
        activeId={activeId}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={newChat}
        onOpenConversation={openConversation}
        onGoTo={goTo}
        onConversationsChanged={refreshConversations}
        onActiveCleared={() => setActiveId(null)}
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
          <span className="font-display text-[15px] font-semibold tracking-tight">
            Grunden<span className="text-accent">.</span>fält
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
            onOpenSettings={() => setView('settings')}
          />
        )}
        {view === 'documents' && <DocumentsView />}
        {view === 'driftinfo' && <DriftInfoView />}
        {view === 'settings' && (
          <SettingsView settings={settings} onSaved={refreshSettings} />
        )}
      </main>
    </div>
  )
}
