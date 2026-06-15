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
}

export interface DocumentSummary {
  doc: string
  chunks: number
  pages: number
}

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
}

export interface UsageBlock {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  requests: number
  cost: number
  conversation_title?: string | null
}

export interface UsageSummary {
  last_message: UsageBlock
  last_conversation: UsageBlock
  today: UsageBlock
  total: UsageBlock
  model: string
  currency: string
  rates: { input_per_mtok: number; output_per_mtok: number }
}

export type View = 'chat' | 'documents' | 'driftinfo' | 'settings'
