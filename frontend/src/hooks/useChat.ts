import { useState, useEffect, useRef } from 'react'
import type { ChatResponse, Suggestion, Alert, ToolCall, StreamEvent } from '../types'
import { sendChatMessageStream } from '../api'
import { useChatSessions } from './useChatSessions'

export function useChat() {
  const { activeSession, updateActiveSession, createSession } = useChatSessions()
  const hasInitialized = useRef(false)

  const [sessionId, setSessionId] = useState<string | undefined>(activeSession?.sessionId)
  const [message, setMessage] = useState('')
  const [history, setHistory] = useState<ChatResponse['history']>(activeSession?.history ?? [])
  const [suggestions, setSuggestions] = useState<Suggestion[] | undefined>(activeSession?.suggestions)
  const [summary] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)
  const [alert, setAlert] = useState<Alert | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Sync local state when active session changes
  useEffect(() => {
    if (!activeSession && !hasInitialized.current) {
      // Use setTimeout to defer state update until after render
      // This prevents the "Cannot update component while rendering" error
      hasInitialized.current = true
      setTimeout(() => {
        createSession()
      }, 0)
      return
    }
    
    if (activeSession) {
      hasInitialized.current = true
      setSessionId(activeSession.sessionId)
      // Only update history if it's actually different to avoid unnecessary re-renders
      setHistory((prev) => {
        // Compare by length and last message to avoid unnecessary updates
        if (prev.length !== activeSession.history.length) {
          return activeSession.history
        }
        // If lengths are same, check if last messages are different
        if (prev.length > 0 && activeSession.history.length > 0) {
          const prevLast = prev[prev.length - 1]
          const activeLast = activeSession.history[activeSession.history.length - 1]
          if (prevLast.content !== activeLast.content || 
              prevLast.toolCalls?.length !== activeLast.toolCalls?.length) {
            return activeSession.history
          }
          // Check if tool call statuses changed
          if (prevLast.toolCalls && activeLast.toolCalls) {
            const prevStatuses = prevLast.toolCalls.map(tc => `${tc.id}:${tc.status}`).join(',')
            const activeStatuses = activeLast.toolCalls.map(tc => `${tc.id}:${tc.status}`).join(',')
            if (prevStatuses !== activeStatuses) {
              return activeSession.history
            }
          }
          return prev // No change, return previous to avoid re-render
        }
        return activeSession.history
      })
      setSuggestions(activeSession.suggestions)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSession])

  const sendMessage = async (text?: string, files?: Array<{ name: string; content: string }>) => {
    const messageText = text || message.trim()

    if (!messageText && (!files || files.length === 0)) {
      setAlert({ type: 'error', message: 'Please enter content to send or upload a file.' })
      return
    }

    // Validate file sizes (already validated in useFileUpload, but double-check)
    if (files && files.length > 0) {
      const oversizedFiles = files.filter((f) => {
        let size = new Blob([f.content]).size
        if (f.content.startsWith('[BINARY_FILE:')) {
          const base64Content = f.content.split(':')[2]?.split(']')[0] || ''
          size = Math.floor(base64Content.length * 0.75)
        }
        return size > 5 * 1024 * 1024
      })
      if (oversizedFiles.length > 0) {
        const fileNames = oversizedFiles.map((f) => f.name).join(', ')
        setAlert({
          type: 'error',
          message: `File too large (over 5MB): ${fileNames}. Please upload smaller files.`,
        })
        return
      }
    }

    setAlert(null)

    const userMessageContent =
      messageText || (files && files.length > 0 ? files.map((f) => `[文件: ${f.name}]`).join(', ') : '')

    const currentHistory: ChatResponse['history'] = userMessageContent
      ? [...history, { role: 'user' as const, content: messageText || userMessageContent }]
      : history

    if (userMessageContent) {
      setHistory(currentHistory)
      // Derive chat title from the first user message if not already set
      if (!activeSession?.title || activeSession.title === 'New chat' || activeSession.title === 'New conversation') {
        const rawTitle = (messageText || userMessageContent).replace(/\s+/g, ' ').trim()
        const newTitle = rawTitle.slice(0, 30) || 'New chat'
        updateActiveSession({ title: newTitle, history: currentHistory })
      } else {
        updateActiveSession({ history: currentHistory })
      }
    }

    setLoading(true)

    let assistantMessageIndex = -1
    if (userMessageContent) {
      const updatedHistory: ChatResponse['history'] = [...currentHistory, { role: 'assistant' as const, content: '', toolCalls: [] }]
      assistantMessageIndex = updatedHistory.length - 1
      setHistory(updatedHistory)
      updateActiveSession({ history: updatedHistory })
    }

    // Use a ref to track assistant message index so it can be updated in event handlers
    const assistantIndexRef = { current: assistantMessageIndex }

    try {
      const payload = {
        session_id: sessionId,
        message: messageText || undefined,
        files,
        messages: currentHistory.map((turn) => ({
          role: turn.role as string,
          content: turn.content,
        })),
      }

      let accumulatedContent = ''
      let currentSessionId = sessionId || undefined
      const currentToolCalls = new Map<string, ToolCall>()

      await sendChatMessageStream(
        payload,
        (chunk: string) => {
          accumulatedContent += chunk
          setHistory((prev) => {
            const updated: ChatResponse['history'] = [...prev]
            let targetIndex = assistantIndexRef.current
            if (targetIndex >= 0 && targetIndex < updated.length) {
              // Update content and preserve tool calls
              const existingTurn = updated[targetIndex]
              updated[targetIndex] = {
                role: 'assistant' as const,
                content: accumulatedContent,
                toolCalls: existingTurn.toolCalls || Array.from(currentToolCalls.values()),
              }
            } else if (targetIndex < 0 && accumulatedContent) {
              updated.push({ 
                role: 'assistant' as const, 
                content: accumulatedContent,
                toolCalls: Array.from(currentToolCalls.values())
              })
              targetIndex = updated.length - 1
              assistantIndexRef.current = targetIndex
            }
            // Update session asynchronously to avoid triggering re-renders during render
            setTimeout(() => {
              updateActiveSession({ history: updated })
            }, 0)
            return updated
          })
        },
        () => {
          setLoading(false)
          if (currentSessionId) {
            setSessionId(currentSessionId)
            updateActiveSession({ sessionId: currentSessionId })
          }
        },
        (error: string) => {
          setLoading(false)
          if (userMessageContent) {
            setHistory(history)
            setMessage(messageText)
          }
          setAlert({ type: 'error', message: error })
        },
        (event: StreamEvent) => {
          // Handle tool call events
          if (event.type === 'tool_call_start' && event.tool) {
            // Use tool_call_id if available, otherwise use tool name as fallback
            const toolCallId = (event as any).tool_call_id || event.tool
            // Check if this tool call already exists
            if (currentToolCalls.has(toolCallId)) {
              return
            }
            const toolCall: ToolCall = {
              id: toolCallId,
              name: event.tool,
              arguments: event.input || {},
              status: 'calling',
            }
            currentToolCalls.set(toolCallId, toolCall)
            
            // Update history with tool call - only show currently calling tools
            setHistory((prev) => {
              const updated: ChatResponse['history'] = [...prev]
              let targetIndex = assistantIndexRef.current
              if (targetIndex < 0 || targetIndex >= updated.length) {
                // Create assistant message if it doesn't exist
                updated.push({ 
                  role: 'assistant' as const, 
                  content: '',
                  toolCalls: Array.from(currentToolCalls.values()).filter(tc => tc.status === 'calling')
                })
                targetIndex = updated.length - 1
                assistantIndexRef.current = targetIndex
              } else {
                // Update existing assistant message - only show calling tools
                const existingTurn = updated[targetIndex]
                updated[targetIndex] = {
                  ...existingTurn,
                  toolCalls: Array.from(currentToolCalls.values()).filter(tc => tc.status === 'calling'),
                }
              }
              // Update session asynchronously to avoid triggering re-renders
              setTimeout(() => {
                updateActiveSession({ history: updated })
              }, 0)
              return updated
            })
          } else if (event.type === 'tool_call_end' && event.tool) {
            const toolCallId = (event as any).tool_call_id || event.tool
            const toolCall = currentToolCalls.get(toolCallId)
            if (toolCall) {
              toolCall.status = 'completed'
              toolCall.result = event.result
              currentToolCalls.set(toolCallId, toolCall)
              
              // Update history - only show currently calling tools
              setHistory((prev) => {
                const updated: ChatResponse['history'] = [...prev]
                let targetIndex = assistantIndexRef.current
                if (targetIndex >= 0 && targetIndex < updated.length) {
                  const existingTurn = updated[targetIndex]
                  updated[targetIndex] = {
                    ...existingTurn,
                    toolCalls: Array.from(currentToolCalls.values()).filter(tc => tc.status === 'calling'),
                  }
                }
                // Update session asynchronously to avoid triggering re-renders during render
                setTimeout(() => {
                  updateActiveSession({ history: updated })
                }, 0)
                return updated
              })
            }
          } else if (event.type === 'tool_call_error' && event.tool) {
            const toolCallId = (event as any).tool_call_id || event.tool
            const toolCall = currentToolCalls.get(toolCallId)
            if (toolCall) {
              toolCall.status = 'error'
              toolCall.error = event.error
              currentToolCalls.set(toolCallId, toolCall)
              
              // Update history - only show currently calling tools
              setHistory((prev) => {
                const updated: ChatResponse['history'] = [...prev]
                let targetIndex = assistantIndexRef.current
                if (targetIndex >= 0 && targetIndex < updated.length) {
                  const existingTurn = updated[targetIndex]
                  updated[targetIndex] = {
                    ...existingTurn,
                    toolCalls: Array.from(currentToolCalls.values()).filter(tc => tc.status === 'calling'),
                  }
                }
                // Update session asynchronously to avoid triggering re-renders during render
                setTimeout(() => {
                  updateActiveSession({ history: updated })
                }, 0)
                return updated
              })
            }
          }
        }
      )

      if (accumulatedContent && assistantMessageIndex >= 0) {
        const finalHistory: ChatResponse['history'] = [...currentHistory, { role: 'assistant' as const, content: accumulatedContent }]
        updateActiveSession({
          history: finalHistory,
          suggestions: undefined,
          summary: undefined,
        })
      }
    } catch (error) {
      setLoading(false)
      if (userMessageContent) {
        setHistory(history)
        setMessage(messageText)
      }
      const errorMessage = error instanceof Error ? error.message : 'Send failed'
      setAlert({ type: 'error', message: errorMessage })
    }
  }

  return {
    sessionId,
    message,
    setMessage,
    history,
    suggestions,
    summary,
    loading,
    alert,
    setAlert,
    messagesEndRef,
    sendMessage,
  }
}

