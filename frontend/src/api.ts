import type { ChatPayload, ChecklistItem, ReviewPayload, ReviewResponse, StreamEvent } from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

export async function reviewMrt(payload: ReviewPayload): Promise<ReviewResponse> {
  const response = await fetch(`${API_BASE_URL}/review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<ReviewResponse>(response)
}

export async function sendChatMessageStream(
  payload: ChatPayload,
  onChunk: (chunk: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
  onEvent?: (event: StreamEvent) => void
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/agent/message/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed with status ${response.status}`)
  }

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  if (!reader) {
    throw new Error('Failed to get response reader')
  }

  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6) // Remove 'data: ' prefix
          try {
            const parsed = JSON.parse(data) as StreamEvent
            if (parsed.type === 'chunk') {
              onChunk(parsed.content || '')
            } else if (parsed.type === 'done') {
              onDone()
              return
            } else if (parsed.type === 'error') {
              onError(parsed.content || parsed.error || 'Unknown error')
              return
            } else if (parsed.type === 'tool_call_start' || parsed.type === 'tool_call_end' || parsed.type === 'tool_call_error') {
              // Handle tool call events
              if (onEvent) {
                onEvent(parsed)
              }
            } else if (onEvent) {
              // Handle other events
              onEvent(parsed)
            }
          } catch (e) {
            // Skip invalid JSON lines
            console.warn('Failed to parse SSE data:', data, e)
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export interface ConfigResponse {
  system_prompt_template: string
  checklist: ChecklistItem[]
}

export async function getDefaultConfig(): Promise<ConfigResponse> {
  const response = await fetch(`${API_BASE_URL}/config`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })
  return handleResponse<ConfigResponse>(response)
}

export interface SaveConfigPayload {
  system_prompt_template: string
  checklist: ChecklistItem[]
}

export interface SaveConfigResponse {
  status: string
  message: string
}

export async function saveConfig(payload: SaveConfigPayload): Promise<SaveConfigResponse> {
  const response = await fetch(`${API_BASE_URL}/config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<SaveConfigResponse>(response)
}

export interface FileUploadResponse {
  filename: string
  content: string
  size: number
}

export async function uploadFile(
  file: File,
  onProgress?: (progress: number) => void
): Promise<FileUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    // Track upload progress
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        const progress = Math.round((e.loaded / e.total) * 100)
        onProgress(progress)
      }
    })

    // Handle completion
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText) as FileUploadResponse
          resolve(response)
        } catch (e) {
          reject(new Error('Failed to parse response'))
        }
      } else {
        const detail = xhr.responseText || `Upload failed with status ${xhr.status}`
        reject(new Error(detail))
      }
    })

    // Handle errors
    xhr.addEventListener('error', () => {
      reject(new Error('Network error occurred'))
    })

    xhr.addEventListener('abort', () => {
      reject(new Error('Upload was aborted'))
    })

    // Start the request
    xhr.open('POST', `${API_BASE_URL}/upload/file`)
    xhr.send(formData)
  })
}

// Admin API
export interface ProviderInfo {
  value: string
  label: string
}

export interface ProvidersResponse {
  providers: ProviderInfo[]
}

export interface LLMConfigResponse {
  provider: string
  model: string
  ollama_url?: string
}

export interface OllamaModelInfo {
  name: string
  size?: number
  modified_at?: string
}

export interface ModelsResponse {
  provider: string
  models: string[]
  ollama_models?: OllamaModelInfo[]
}

export interface UpdateLLMConfigRequest {
  provider: string
  model: string
  ollama_url?: string
}

export interface UpdateLLMConfigResponse {
  status: string
  message: string
  provider: string
  model: string
}

export async function getProviders(): Promise<ProvidersResponse> {
  const response = await fetch(`${API_BASE_URL}/api/admin/providers`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })
  return handleResponse<ProvidersResponse>(response)
}

export async function getLLMConfig(): Promise<LLMConfigResponse> {
  const response = await fetch(`${API_BASE_URL}/api/admin/config`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })
  return handleResponse<LLMConfigResponse>(response)
}

export async function getAvailableModels(
  provider?: string,
  ollamaUrl?: string
): Promise<ModelsResponse> {
  const params = new URLSearchParams()
  if (provider) params.append('provider', provider)
  if (ollamaUrl) params.append('ollama_url', ollamaUrl)
  
  const url = `${API_BASE_URL}/api/admin/models${params.toString() ? `?${params.toString()}` : ''}`
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })
  return handleResponse<ModelsResponse>(response)
}

export async function updateLLMConfig(
  payload: UpdateLLMConfigRequest
): Promise<UpdateLLMConfigResponse> {
  const response = await fetch(`${API_BASE_URL}/api/admin/config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<UpdateLLMConfigResponse>(response)
}

