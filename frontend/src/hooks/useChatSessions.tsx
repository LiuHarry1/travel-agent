import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { ChatResponse, Suggestion } from '../types'

const CHAT_SESSIONS_STORAGE_KEY = 'mrt-chat-sessions-v2'
const LEGACY_CHAT_STORAGE_KEY = 'mrt-review-chat-session'

export interface StoredChatSession {
  id: string
  title: string
  /** Backend session id */
  sessionId?: string
  history: ChatResponse['history']
  suggestions?: Suggestion[]
  summary?: string
  updatedAt: string
}

interface ChatSessionsState {
  sessions: StoredChatSession[]
  activeSessionId: string | null
}

interface ChatSessionsContextValue {
  sessions: StoredChatSession[]
  activeSessionId: string | null
  activeSession: StoredChatSession | null
  createSession: () => string
  selectSession: (id: string) => void
  deleteSession: (id: string) => void
  renameSession: (id: string, title: string) => void
  updateActiveSession: (
    data: Partial<Pick<StoredChatSession, 'sessionId' | 'history' | 'suggestions' | 'summary' | 'title'>>,
  ) => void
}

const ChatSessionsContext = createContext<ChatSessionsContextValue | undefined>(undefined)

function loadInitialState(): ChatSessionsState {
  if (typeof window === 'undefined') {
    return { sessions: [], activeSessionId: null }
  }

  try {
    const raw = window.localStorage.getItem(CHAT_SESSIONS_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as ChatSessionsState
      return {
        sessions: (parsed.sessions ?? []).slice(0, 10),
        activeSessionId: parsed.activeSessionId ?? (parsed.sessions?.[0]?.id ?? null),
      }
    }
  } catch {
    // ignore and try legacy
  }

  // Fallback: migrate legacy single-session storage if present
  try {
    const legacyRaw = window.localStorage.getItem(LEGACY_CHAT_STORAGE_KEY)
    if (legacyRaw) {
      const legacy = JSON.parse(legacyRaw) as {
        sessionId?: string
        history?: ChatResponse['history']
        suggestions?: Suggestion[]
        summary?: string
      }
      if (legacy.history && legacy.history.length > 0) {
        const now = new Date().toISOString()
        const id = 'session-' + now
        const title =
          legacy.history.find((m) => m.role === 'user')?.content.slice(0, 30).replace(/\s+/g, ' ') ||
          'Previous session'
        const sessions: StoredChatSession[] = [
          {
            id,
            title,
            sessionId: legacy.sessionId,
            history: legacy.history,
            suggestions: legacy.suggestions,
            summary: legacy.summary,
            updatedAt: now,
          },
        ]
        return { sessions, activeSessionId: id }
      }
    }
  } catch {
    // ignore
  }

  return { sessions: [], activeSessionId: null }
}

export function ChatSessionsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ChatSessionsState>(() => loadInitialState())

  // Persist to localStorage whenever state changes
  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(CHAT_SESSIONS_STORAGE_KEY, JSON.stringify(state))
  }, [state])

  const value: ChatSessionsContextValue = useMemo(() => {
    const { sessions, activeSessionId } = state
    const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null

    const createSession = () => {
      const now = new Date().toISOString()
      const id = 'session-' + now
      const newSession: StoredChatSession = {
        id,
        title: 'New chat',
        sessionId: undefined,
        history: [],
        updatedAt: now,
        suggestions: undefined,
        summary: undefined,
      }
      setState((prev) => {
        // Keep only sessions that actually have history;
        // this prevents many empty "New chat" sessions from pushing out old ones.
        const nonEmptySessions = prev.sessions.filter((s) => s.history.length > 0)
        const sessions = [newSession, ...nonEmptySessions]
        return {
          sessions: sessions.slice(0, 10),
          activeSessionId: id,
        }
      })
      return id
    }

    const selectSession = (id: string) => {
      setState((prev) => ({
        ...prev,
        activeSessionId: id,
      }))
    }

    const deleteSession = (id: string) => {
      setState((prev) => {
        const sessions = prev.sessions.filter((s) => s.id !== id)
        let activeSessionId = prev.activeSessionId
        if (prev.activeSessionId === id) {
          activeSessionId = sessions[0]?.id ?? null
        }
        return { sessions, activeSessionId }
      })
    }

    const renameSession = (id: string, title: string) => {
      setState((prev) => ({
        ...prev,
        sessions: prev.sessions.map((s) => (s.id === id ? { ...s, title } : s)),
      }))
    }

    const updateActiveSession: ChatSessionsContextValue['updateActiveSession'] = (data) => {
      if (!activeSessionId) return
      setState((prev) => ({
        ...prev,
        sessions: prev.sessions.map((s) =>
          s.id === activeSessionId
            ? {
                ...s,
                ...data,
                updatedAt: new Date().toISOString(),
              }
            : s,
        ),
      }))
    }

    return {
      sessions,
      activeSessionId,
      activeSession,
      createSession,
      selectSession,
      deleteSession,
      renameSession,
      updateActiveSession,
    }
  }, [state])

  return <ChatSessionsContext.Provider value={value}>{children}</ChatSessionsContext.Provider>
}

export function useChatSessions() {
  const ctx = useContext(ChatSessionsContext)
  if (!ctx) {
    throw new Error('useChatSessions must be used within ChatSessionsProvider')
  }
  return ctx
}


