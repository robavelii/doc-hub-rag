// Shared API response types mirroring FastAPI backend shapes

export type Plan = 'free' | 'starter' | 'pro'
export type UserRole = 'owner' | 'admin' | 'member'
export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface TenantSummary {
  id: string
  name: string
  slug: string
}

export interface UserSummary {
  id: string
  email: string
  role: UserRole
  is_superadmin?: boolean
  display_name?: string | null
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  api_key?: string
  tenant?: TenantSummary
  user?: UserSummary
}

export interface RegisterRequest {
  tenant_name: string
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface DocumentItem {
  id: string
  filename: string
  file_type: string
  size_bytes: number
  chunk_count: number
  status: DocumentStatus
  error_message?: string | null
  metadata?: Record<string, unknown>
  created_at?: string | null
}

export interface DocumentUploadResponse {
  id: string
  status: DocumentStatus
  filename: string
}

export interface QuerySource {
  id: string
  filename?: string | null
  text: string
  doc_id?: string
}

export interface QueryResponse {
  answer: string
  sources: QuerySource[]
  confidence: number
  confidence_tier?: string
  from_cache: boolean
  tokens_total?: number
  latency_ms?: number
  provider?: string | null
  model?: string | null
  query_log_id?: string
  conversation_id?: string
}

export interface QueryResultMetrics {
  confidence: number
  confidence_tier?: string
  sources: QuerySource[]
  tokens_total?: number | null
  latency_ms?: number | null
  from_cache?: boolean
  provider?: string | null
  model?: string | null
  query_log_id?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface StreamChunkEvent {
  type: 'chunk'
  content: string
}

export interface StreamDoneEvent {
  type: 'done'
  sources: QuerySource[]
  confidence: number
  confidence_tier?: string
  tokens_total?: number
  latency_ms?: number
  from_cache?: boolean
  provider?: string | null
  model?: string | null
  query_log_id?: string
  conversation_id?: string
}

export type StreamEvent = StreamChunkEvent | StreamDoneEvent

export interface UsageSummary {
  plan: Plan
  tokens_used: number
  tokens_limit: number
  storage_used_bytes: number
  storage_limit_bytes: number
}

export interface QueryHistoryItem {
  id: string
  question: string
  answer?: string | null
  tokens_total: number
  confidence_score?: number | null
  from_cache: boolean
  created_at?: string | null
}

export interface UsageHistoryResponse {
  items: QueryHistoryItem[]
  page: number
  page_size: number
  total: number
}

export interface UsageTimeseries {
  range: string
  tokens_by_day: { date: string; tokens: number }[]
  queries_by_day: { date: string; queries: number }[]
  confidence_by_day: { date: string; avg_confidence: number }[]
}

export interface WidgetConfig {
  tenant_id: string
  tenant_name: string
  primary_color: string
  welcome_message: string
  allowed_domains: string[]
  position?: string
  icon?: string
}

export interface ConversationSummary {
  id: string
  title: string
  created_at?: string | null
  updated_at?: string | null
}

export interface ConversationMessage {
  id: string
  role: string
  content: string
  sources?: QuerySource[]
  metrics?: QueryResultMetrics
  query_log_id?: string | null
  created_at?: string | null
}

export interface ConversationDetail {
  id: string
  title: string
  messages: ConversationMessage[]
}

export interface TeamMember {
  id: string
  email: string
  role: UserRole
  display_name?: string | null
  created_at?: string | null
}

export interface ApiKeyItem {
  id: string
  name: string
  key_prefix: string
  masked_key: string
  last_used_at?: string | null
  created_at?: string | null
}

export interface BillingSubscription {
  plan: Plan
  status: string
  tokens_used: number
  tokens_limit: number
  storage_used_bytes: number
  storage_limit_bytes: number
  current_period_end?: string | null
}

export interface AdminTenant {
  id: string
  name: string
  slug: string
  plan: Plan
  is_active: boolean
  monthly_tokens_used: number
  monthly_token_limit: number
  storage_used_bytes: number
  created_at?: string | null
  widget_config?: Record<string, unknown>
}

export interface GlobalUsageStats {
  total_tokens_this_month: number
  total_tenants: number
}

export interface WidgetInitOptions {
  apiKey: string
  containerId: string
  primaryColor?: string
  apiBase?: string
}

export interface UploadProgress {
  id: string
  name: string
  status: 'uploading' | 'processing' | 'ready' | 'failed' | 'error'
  docId?: string
  error?: string
}
