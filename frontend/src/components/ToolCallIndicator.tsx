import type { ToolCall } from '../types'

interface ToolCallIndicatorProps {
  toolCall: ToolCall
}

export function ToolCallIndicator({ toolCall }: ToolCallIndicatorProps) {
  const getStatusText = () => {
    switch (toolCall.status) {
      case 'calling':
        return `正在调用工具: ${toolCall.name}...`
      case 'completed':
        return `工具 ${toolCall.name} 调用完成`
      case 'error':
        return `工具 ${toolCall.name} 调用失败`
      default:
        return `调用工具: ${toolCall.name}`
    }
  }

  const status = toolCall.status || 'calling'
  return (
    <div className={`tool-call-indicator ${status}`}>
      <div className="tool-call-status">
        {(status === 'calling' || !toolCall.status) && (
          <div className="tool-call-spinner">
            <span></span>
            <span></span>
            <span></span>
          </div>
        )}
        <span className="tool-call-text">{getStatusText()}</span>
      </div>
      {status === 'error' && toolCall.error && (
        <div className="tool-call-error">{toolCall.error}</div>
      )}
    </div>
  )
}

