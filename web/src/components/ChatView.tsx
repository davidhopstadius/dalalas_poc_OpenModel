import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { BookText, KeyRound, Search, Sparkles } from 'lucide-react'
import { api, streamChat } from '../api'
import type { Citation, Message as Msg, Settings } from '../types'
import Message from './Message'
import Composer from './Composer'

interface Props {
  conversationId: string | null
  settings: Settings | null
  onConversationCreated: (id: string) => void
  onTitleMaybeChanged: () => void
  onOpenSettings: () => void
}

const EXAMPLES = [
  'Vad händer vid strömavbrott med dörröppnaren?',
  'Vilken standard måste låset uppfylla vid omvänd installation?',
  'Vad är artikelnumret för Transmissionsenhet SW300?',
  'Vad betyder tre korta blink på statuslysdioden?',
]

export default function ChatView({
  conversationId,
  settings,
  onConversationCreated,
  onTitleMaybeChanged,
  onOpenSettings,
}: Props) {
  const [messages, setMessages] = useState<Msg[]>([])
  const [streaming, setStreaming] = useState(false)
  const [streamContent, setStreamContent] = useState('')
  const [tool, setTool] = useState<{ name: string; query: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  // Id pa ett samtal vi nyss skapat sjalva (under streaming) - ska inte laddas
  // om fran servern, da skulle det live-streamade svaret skrivas over.
  const selfCreatedRef = useRef<string | null>(null)

  useEffect(() => {
    if (!conversationId) {
      setMessages([])
      return
    }
    if (conversationId === selfCreatedRef.current) return
    api
      .getConversation(conversationId)
      .then((c) => setMessages(c.messages))
      .catch(() => setMessages([]))
  }, [conversationId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, streamContent, tool, streaming])

  const send = async (text: string) => {
    setError(null)
    setMessages((m) => [...m, { role: 'user', content: text }])
    setStreaming(true)
    setStreamContent('')
    setTool(null)

    const ctrl = new AbortController()
    abortRef.current = ctrl
    let acc = ''
    let citations: Citation[] = []
    let convId = conversationId
    let interrupted = false

    try {
      await streamChat(
        { message: text, conversation_id: conversationId },
        {
          onStart: (id) => {
            convId = id
            if (!conversationId) {
              selfCreatedRef.current = id
              onConversationCreated(id)
            }
          },
          onTool: (name, query) => setTool({ name, query }),
          onToken: (t) => {
            acc += t
            setStreamContent(acc)
            setTool(null)
          },
          onDone: (payload) => {
            citations = payload.citations
            convId = payload.conversation_id
          },
          onError: (msg) => {
            interrupted = true
            setError(msg)
          },
        },
        ctrl.signal,
      )
    } catch (e) {
      interrupted = true
      if ((e as Error).name !== 'AbortError') setError((e as Error).message)
    }

    if (acc) {
      setMessages((m) => [...m, { role: 'assistant', content: acc, citations }])
    } else if (!interrupted && convId) {
      // Inga tokens mottogs men ingen felsignal heller - servern kan anda ha
      // sparat svaret (t.ex. en transient stromnings-hicka). Hamta sanningen
      // fran servern sa anvandaren inte blir utan svar.
      try {
        const c = await api.getConversation(convId)
        setMessages(c.messages)
      } catch {
        /* lat tomt-laget sta */
      }
    }
    setStreamContent('')
    setStreaming(false)
    setTool(null)
    abortRef.current = null
    // Streamen ar klar och svaret ar sparat i servern. Slapp guarden sa att
    // samtalet laddas om normalt nasta gang man klickar in pa det igen (annars
    // kunde man aldrig oppna den nyss skapade - oversta - traden pa nytt).
    selfCreatedRef.current = null
    onTitleMaybeChanged()
  }

  const stop = () => abortRef.current?.abort()

  const noKey = settings != null && !settings.has_api_key
  const isEmpty = messages.length === 0 && !streaming

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ChatHeader settings={settings} />

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[760px] px-4 py-6 md:px-6">
          {isEmpty ? (
            <EmptyState onPick={send} disabled={noKey} onOpenSettings={onOpenSettings} noKey={noKey} />
          ) : (
            <div className="space-y-7">
              {messages.map((m, i) => (
                <Message key={m.id ?? i} role={m.role} content={m.content} citations={m.citations} />
              ))}

              {streaming && (
                <div className="rise">
                  {!streamContent && (
                    <div className="flex items-center gap-2.5 text-[13.5px] text-ink-soft">
                      {tool ? (
                        <>
                          <Search size={15} className="text-accent" />
                          <span>
                            {tool.name === 'doc_search' ? 'Söker i dokumentationen' : 'Söker på webben'}
                            {tool.query ? (
                              <span className="text-ink-faint"> · "{tool.query}"</span>
                            ) : null}
                          </span>
                        </>
                      ) : (
                        <>
                          <span className="dot-pulse flex">
                            <span /> <span /> <span />
                          </span>
                          <span>Tänker…</span>
                        </>
                      )}
                    </div>
                  )}
                  {streamContent && (
                    <div className="prose-grunden max-w-none text-[15px] text-ink">
                      <Markdown remarkPlugins={[remarkGfm]}>{streamContent}</Markdown>
                    </div>
                  )}
                </div>
              )}

              {error && (
                <div className="rounded-xl border border-danger/25 bg-danger/5 px-4 py-3 text-[13.5px] text-danger">
                  {error}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <Composer onSend={send} onStop={stop} busy={streaming} disabled={noKey} />
    </div>
  )
}

function ChatHeader({ settings }: { settings: Settings | null }) {
  if (!settings) return <div className="h-px border-b border-line" />
  return (
    <div className="hidden items-center justify-between border-b border-line px-6 py-3 md:flex">
      <div className="flex items-center gap-2 text-[13px] text-ink-soft">
        <Sparkles size={15} className="text-accent" />
        <span className="mono text-ink">{settings.active_model || settings.model}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <Toggle label="Thinking" on={settings.thinking} />
        <Toggle label="Rerank" on={settings.rerank} />
        <Toggle label="Dok.sök" on={settings.doc_search} icon={<BookText size={12} />} />
        <Toggle label="Webb" on={settings.search} />
      </div>
    </div>
  )
}

function Toggle({ label, on, icon }: { label: string; on: boolean; icon?: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11.5px] font-medium transition
        ${on ? 'border-accent/25 bg-accent-soft text-accent-hover' : 'border-line bg-surface text-ink-faint'}`}
      title={`${label}: ${on ? 'på' : 'av'}`}
    >
      {icon}
      {label}
      <span className={`ml-0.5 h-1.5 w-1.5 rounded-full ${on ? 'bg-accent' : 'bg-ink-faint/40'}`} />
    </span>
  )
}

function EmptyState({
  onPick,
  disabled,
  noKey,
  onOpenSettings,
}: {
  onPick: (t: string) => void
  disabled: boolean
  noKey: boolean
  onOpenSettings: () => void
}) {
  return (
    <div className="flex flex-col items-center pt-[12vh] text-center">
      <div className="mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-accent text-white shadow-sm">
        <KeyRound size={28} strokeWidth={2} />
      </div>
      <h1 className="font-display text-[26px] font-semibold tracking-tight">
        Hej — vad behöver du veta?
      </h1>
      <p className="mt-2 max-w-md text-[14.5px] text-ink-soft">
        Ställ en fråga om systemen i din dokumentation. Jag söker i manualerna och svarar med
        sidhänvisning.
      </p>

      {noKey ? (
        <button
          onClick={onOpenSettings}
          className="mt-7 rounded-xl bg-accent px-4 py-2.5 text-[14px] font-medium text-white transition hover:bg-accent-hover"
        >
          Lägg in API-nyckel för att börja →
        </button>
      ) : (
        <div className="mt-8 grid w-full max-w-[620px] gap-2.5 sm:grid-cols-2">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              onClick={() => onPick(q)}
              disabled={disabled}
              className="rounded-xl border border-line bg-surface px-4 py-3 text-left text-[13.5px] leading-snug text-ink-soft transition hover:border-accent/40 hover:bg-surface-raised hover:text-ink disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
