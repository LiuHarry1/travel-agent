import { useEffect, useRef, useState, type FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useChat } from '../hooks/useChat'
import { useFileUpload } from '../hooks/useFileUpload'
import { uploadFile } from '../api'
import { Alert } from './Alert'
import { FileUploadArea } from './FileUploadArea'
import { MessageList } from './MessageList'
import { FileIcon, ErrorIcon, CloseIcon } from './icons'

interface FileWithContent {
  file: File
  content?: string
  loading?: boolean
  error?: string
  progress?: number
}

export function ChatPage() {
  const {
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
  } = useChat()

  const {
    uploadedFiles,
    dragOver,
    fileInputRef,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleFileSelect,
    removeFile,
    clearFiles,
    openFileDialog,
    formatErrorMessages,
  } = useFileUpload()

  const [filesWithContent, setFilesWithContent] = useState<FileWithContent[]>([])

  // Upload files to backend immediately when they're added
  useEffect(() => {
    const uploadFiles = async () => {
      const newFiles = uploadedFiles.filter(
        (file) => !filesWithContent.find((fwc) => fwc.file === file)
      )

      if (newFiles.length === 0) return

      // Immediately add new files with loading state
      setFilesWithContent((prev) => {
        const newFilesWithContent = newFiles.map((file) => ({ 
          file, 
          loading: true, 
          progress: 0 
        }))
        return [...prev, ...newFilesWithContent]
      })

      // Upload each new file immediately
      for (const file of newFiles) {
        try {
          const result = await uploadFile(
            file,
            (progress) => {
              // Update progress in real-time
              setFilesWithContent((prev) =>
                prev.map((fwc) =>
                  fwc.file === file ? { ...fwc, progress } : fwc
                )
              )
            }
          )
          setFilesWithContent((prev) =>
            prev.map((fwc) =>
              fwc.file === file 
                ? { file, content: result.content, loading: false, progress: 100 } 
                : fwc
            )
          )
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Upload failed'
          setFilesWithContent((prev) =>
            prev.map((fwc) =>
              fwc.file === file 
                ? { file, loading: false, error: errorMessage, progress: 0 } 
                : fwc
            )
          )
          setAlert({ type: 'error', message: `Failed to upload ${file.name}: ${errorMessage}` })
        }
      }
    }

    uploadFiles()
    // Remove filesWithContent from dependencies to avoid circular updates
    // We only want to trigger when uploadedFiles changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploadedFiles, setAlert])

  // Sync with uploadedFiles (remove if removed from uploadedFiles)
  useEffect(() => {
    setFilesWithContent((prev) => prev.filter((fwc) => uploadedFiles.includes(fwc.file)))
  }, [uploadedFiles])


  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const messagesWrapperRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    const adjustHeight = () => {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    }

    adjustHeight()
    textarea.addEventListener('input', adjustHeight)
    return () => textarea.removeEventListener('input', adjustHeight)
  }, [message])

  // When starting a new empty chat, scroll to top and focus textarea
  useEffect(() => {
    if (!loading && history.length === 0) {
      if (messagesWrapperRef.current) {
        messagesWrapperRef.current.scrollTop = 0
      }
      if (textareaRef.current) {
        textareaRef.current.focus()
      }
    }
  }, [history.length, loading])

  // During streaming or when new messages arrive, keep scroll at bottom
  // only when user is already near the bottom (autoScroll = true)
  useEffect(() => {
    if (autoScroll && messagesWrapperRef.current) {
      messagesWrapperRef.current.scrollTop = messagesWrapperRef.current.scrollHeight
    }
  }, [history, loading, autoScroll])

  const handleMessagesScroll = () => {
    const container = messagesWrapperRef.current
    if (!container) return
    const threshold = 40 // px
    const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    setAutoScroll(distanceToBottom <= threshold)
  }

  const renderInputArea = () => (
    <FileUploadArea
      uploadedFiles={[]}
      dragOver={dragOver}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDropWithValidation}
      onFileSelect={handleFileSelect}
      onRemoveFile={(index) => removeFile(index)}
      fileInputRef={fileInputRef}
    >
      <form onSubmit={handleSubmit} className="chat-input-form">
        <div className="chat-input-wrapper">
          {/* File preview inside input box (ChatGPT style) */}
          {filesWithContent.length > 0 && (
            <div className="files-preview-inside">
              {filesWithContent.map((fwc, index) => (
                <div
                  key={index}
                  className={`file-preview-chip ${fwc.error ? 'error' : ''} ${fwc.loading ? 'loading' : ''}`}
                >
                  <div className="file-chip-icon">
                    {fwc.loading ? (
                      <div className="loading-spinner small"></div>
                    ) : fwc.error ? (
                      <ErrorIcon />
                    ) : (
                      <FileIcon />
                    )}
                  </div>
                  <span className="file-chip-name">{fwc.file.name}</span>
                  {fwc.error && <span className="file-chip-error">✗</span>}
                  {fwc.loading && fwc.progress !== undefined && (
                    <div className="file-chip-progress">
                      <div className="file-chip-progress-bar">
                        <div
                          className="file-chip-progress-fill"
                          style={{ width: `${fwc.progress}%` }}
                        ></div>
                      </div>
                      <span className="file-chip-progress-text">{fwc.progress}%</span>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      const index = uploadedFiles.indexOf(fwc.file)
                      if (index !== -1) removeFile(index)
                    }}
                    className="file-chip-remove"
                    title="Remove file"
                  >
                    <CloseIcon />
                  </button>
                </div>
              ))}
            </div>
          )}
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={
              dragOver
                ? 'Release to upload file...'
                : 'Enter message or drag and drop file to upload...'
            }
            rows={3}
            className="chat-textarea"
            disabled={loading}
            onDragOver={(e) => {
              // Prevent browser from opening the file when dragged over the textarea
              e.preventDefault()
            }}
            onDrop={(e) => {
              // Prevent default navigation and delegate to our validated drop handler
              e.preventDefault()
              handleDropWithValidation(e as any)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (
                  !loading &&
                  (message.trim() ||
                    filesWithContent.filter((fwc) => fwc.content && !fwc.error).length > 0)
                ) {
                  handleSubmit(e as any)
                }
              }
            }}
          />
          <div className="chat-input-actions">
            <button
              type="button"
              onClick={openFileDialog}
              className="attach-button"
              data-tooltip="Upload file"
              aria-label="Upload file"
              disabled={loading}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M9.035 15.956a1.29 1.29 0 0 0 1.821-.004l6.911-6.911a3.15 3.15 0 0 0 0-4.457l-.034-.034a3.15 3.15 0 0 0-4.456 0l-7.235 7.234a5.031 5.031 0 0 0 7.115 7.115l6.577-6.577a1.035 1.035 0 0 1 1.463 1.464l-6.576 6.577A7.1 7.1 0 0 1 4.579 10.32l7.235-7.234a5.22 5.22 0 0 1 7.382 0l.034.034a5.22 5.22 0 0 1 0 7.383l-6.91 6.91a3.36 3.36 0 0 1-4.741.012l-.006-.005-.012-.011a3.346 3.346 0 0 1 0-4.732L12.76 7.48a1.035 1.035 0 0 1 1.464 1.463l-5.198 5.198a1.277 1.277 0 0 0 0 1.805z"
                />
              </svg>
            </button>
            <button
              type="submit"
              disabled={
                loading ||
                (!message.trim() &&
                  filesWithContent.filter((fwc) => fwc.content && !fwc.error).length === 0)
              }
              className="send-button"
              data-tooltip="Send (Enter)"
              aria-label="Send message"
            >
              {loading ? (
                <div className="loading-spinner"></div>
              ) : (
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              )}
            </button>
          </div>
        </div>
        {alert && <Alert type={alert.type} message={alert.message} className="alert-toast" />}
      </form>
    </FileUploadArea>
  )

  const hasHistory = history.length > 0

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()

    // Handle file upload if files are present
    const readyFiles = filesWithContent.filter((fwc) => fwc.content && !fwc.loading && !fwc.error)
    
    if (readyFiles.length > 0) {
      try {
        // Send message with file contents (filename and content)
        const filesData = readyFiles.map((fwc) => ({
          name: fwc.file.name,
          content: fwc.content!,
        }))

        // Clear input and files immediately before sending
        setMessage('')
        clearFiles()
        setFilesWithContent([])

        // Send message (don't await, let it stream in background)
        sendMessage(message.trim() || undefined, filesData).catch((error) => {
          const errorMessage = error instanceof Error ? error.message : 'Send failed'
          setAlert({ type: 'error', message: errorMessage })
        })
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Send failed'
        setAlert({ type: 'error', message: errorMessage })
      }
      return
    }

    // Check if there are files still loading
    if (filesWithContent.some((fwc) => fwc.loading)) {
      setAlert({ type: 'error', message: 'Please wait for files to finish uploading' })
      return
    }

    // Check if there are files with errors
    const errorFiles = filesWithContent.filter((fwc) => fwc.error)
    if (errorFiles.length > 0) {
      setAlert({ type: 'error', message: 'Some files failed to upload. Please remove them and try again.' })
      return
    }

    // Handle text message only
    if (message.trim()) {
      // Clear input immediately before sending
      const messageToSend = message.trim()
      setMessage('')
      
      // Send message (don't await, let it stream in background)
      sendMessage(messageToSend).catch((error) => {
        const errorMessage = error instanceof Error ? error.message : 'Send failed'
        setAlert({ type: 'error', message: errorMessage })
      })
    }
  }

  const handleDropWithValidation = (e: React.DragEvent<HTMLDivElement>) => {
    const errors = handleDrop(e)
    if (errors.length > 0) {
      const errorMessage = formatErrorMessages(errors)
      setAlert({ type: 'error', message: errorMessage })
    }
  }

  return (
    <section className={`chat-container ${hasHistory ? '' : 'chat-container-initial'}`}>
      {hasHistory ? (
        <>
          {/* Chat Messages Area */}
          <div
            className="chat-messages-wrapper"
            ref={messagesWrapperRef}
            onScroll={handleMessagesScroll}
          >
            <MessageList history={history} loading={loading} messagesEndRef={messagesEndRef} />

            {(summary || (suggestions && suggestions.length > 0)) && history.length > 0 && (
              <div className="chat-results">
                <div className="result-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {`${summary ? `## Review Summary\n\n${summary}\n\n` : ''}${
                      suggestions && suggestions.length > 0
                        ? `## Improvement Suggestions (${suggestions.length})\n\n${suggestions
                            .map((item) => `- **${item.checklist_id}**: ${item.message}`)
                            .join('\n')}\n`
                        : ''
                    }`}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>

          {/* Chat Input Area */}
          <div className="chat-input-container-wrapper">{renderInputArea()}</div>
        </>
      ) : (
        <div className="chat-initial-layout">
          <div className="chat-initial-inner">
            <MessageList history={history} loading={loading} messagesEndRef={messagesEndRef} />
            <div className="chat-input-floating">{renderInputArea()}</div>
          </div>
        </div>
      )}
    </section>
  )
}

