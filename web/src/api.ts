import type {
  Citation,
  ConversationSummary,
  DocumentSummary,
  Message,
  Settings,
  UsageSummary,
} from './types'

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* behall statusText */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  listConversations: () =>
    fetch('/api/conversations').then((r) => jsonOrThrow<ConversationSummary[]>(r)),

  getConversation: (id: string) =>
    fetch(`/api/conversations/${id}`).then((r) =>
      jsonOrThrow<{ id: string; messages: Message[] }>(r),
    ),

  renameConversation: (id: string, title: string) =>
    fetch(`/api/conversations/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    }).then((r) => jsonOrThrow(r)),

  deleteConversation: (id: string) =>
    fetch(`/api/conversations/${id}`, { method: 'DELETE' }).then((r) => jsonOrThrow(r)),

  getUsage: () => fetch('/api/usage').then((r) => jsonOrThrow<UsageSummary>(r)),

  getSettings: () => fetch('/api/settings').then((r) => jsonOrThrow<Settings>(r)),

  updateSettings: (
    patch: Partial<Settings> & {
      api_key?: string
      brave_api_key?: string
      berget_api_key?: string
      anthropic_api_key?: string
    },
  ) =>
    fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }).then((r) => jsonOrThrow<Settings>(r)),

  listDocuments: () =>
    fetch('/api/documents').then((r) =>
      jsonOrThrow<{ documents: DocumentSummary[]; doc_search: boolean }>(r),
    ),

  uploadDocument: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return fetch('/api/documents', { method: 'POST', body: form }).then((r) =>
      jsonOrThrow<{ doc: string; chunks: number }>(r),
    )
  },

  deleteDocument: (name: string) =>
    fetch(`/api/documents/${encodeURIComponent(name)}`, { method: 'DELETE' }).then((r) =>
      jsonOrThrow(r),
    ),
}

export interface ChatHandlers {
  onStart?: (conversationId: string) => void
  onToken?: (text: string) => void
  onTool?: (name: string, query: string) => void
  onDone?: (payload: { conversation_id: string; message_id: string; citations: Citation[] }) => void
  onError?: (message: string) => void
}

/** Streama ett chattsvar via SSE (fetch + ReadableStream). */
export async function streamChat(
  body: { message: string; conversation_id: string | null },
  handlers: ChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok || !res.body) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* behall */
    }
    handlers.onError?.(detail)
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const chunk = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const line = chunk.split('\n').find((l) => l.startsWith('data:'))
      if (!line) continue
      const evt = JSON.parse(line.slice(5).trim())
      switch (evt.type) {
        case 'start':
          handlers.onStart?.(evt.conversation_id)
          break
        case 'token':
          handlers.onToken?.(evt.text)
          break
        case 'tool':
          handlers.onTool?.(evt.name, evt.query)
          break
        case 'done':
          handlers.onDone?.(evt)
          break
        case 'error':
          handlers.onError?.(evt.message)
          break
      }
    }
  }
}
