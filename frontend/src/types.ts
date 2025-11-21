export interface ChecklistItem {
  id: string
  description: string
}

export interface Suggestion {
  checklist_id: string
  message: string
}

export interface Alert {
  type: 'error' | 'success'
  message: string
}

export interface ReviewResponse {
  suggestions: Suggestion[]
  summary?: string
  raw_content?: string
}

export type ConversationState = 'awaiting_mrt' | 'awaiting_checklist' | 'ready'

export interface ToolCall {
  id?: string
  name: string
  arguments: Record<string, any>
  status?: 'calling' | 'completed' | 'error'
  result?: any
  error?: string
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCall[]
}

export interface ChatResponse {
  session_id: string
  state: ConversationState
  replies: string[]
  suggestions?: Suggestion[]
  summary?: string
  history: ChatTurn[]
}

export interface ReviewPayload {
  mrt_content: string
  software_requirement?: string
  checklist?: ChecklistItem[]
  system_prompt?: string
}

export interface ChatPayload {
  session_id?: string
  message?: string
  messages?: Array<{ role: string; content: string }>
  mrt_content?: string
  software_requirement?: string
  checklist?: ChecklistItem[]
  files?: Array<{ name: string; content: string }>
}

export type StreamEventType = 
  | 'chunk' 
  | 'tool_call_start' 
  | 'tool_call_end' 
  | 'tool_call_error' 
  | 'done' 
  | 'error'

export interface StreamEvent {
  type: StreamEventType
  content?: string
  tool?: string
  input?: any
  result?: any
  error?: string
}
