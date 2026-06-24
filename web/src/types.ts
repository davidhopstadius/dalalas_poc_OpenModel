export interface Citation {
  doc: string
  page: number
}

export interface Message {
  id?: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
}

export interface ConversationSummary {
  id: string
  title: string
  updated_at: number
  // Leverantör/modell som startade samtalet (visas i tooltip). Kan saknas för
  // samtal skapade innan kolumnerna fanns.
  model?: string | null
  provider?: string | null
}

export interface DocumentSummary {
  doc: string
  chunks: number
  pages: number
}

export type Provider = 'grunden' | 'berget' | 'anthropic'

export interface Settings {
  base_url: string
  model: string
  system_prompt: string
  thinking: boolean
  search: boolean
  doc_search: boolean
  rerank: boolean
  rerank_model: string
  rerank_candidates: number
  embed_model: string
  rag_top_k: number
  request_timeout: number
  has_api_key: boolean
  has_brave_key: boolean
  // Multi-leverantör
  provider: Provider
  active_model: string
  berget_base_url: string
  berget_model: string
  berget_price_in: number
  berget_price_out: number
  anthropic_model: string
  has_berget_key: boolean
  has_anthropic_key: boolean
}

export interface UsageBlock {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  requests: number
  costs: Record<string, number>
  conversation_title?: string | null
}

export interface UsageSummary {
  last_message: UsageBlock
  last_conversation: UsageBlock
  today: UsageBlock
  total: UsageBlock
  provider: string
  model: string
  last_latency_ms: number | null
  rates: { input_per_mtok: number; output_per_mtok: number; currency: string }
}

export type View = 'chat' | 'documents' | 'driftinfo' | 'settings'
