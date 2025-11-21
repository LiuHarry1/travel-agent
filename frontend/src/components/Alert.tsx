interface AlertProps {
  type: 'error' | 'success'
  message: string
  className?: string
  onClose?: () => void
}

export function Alert({ type, message, className = '', onClose }: AlertProps) {
  return (
    <div className={`alert-message ${type} ${className}`}>
      {message}
      {onClose && (
        <button
          type="button"
          className="alert-close"
          onClick={onClose}
          aria-label="Close alert"
        >
          ×
        </button>
      )}
    </div>
  )
}

