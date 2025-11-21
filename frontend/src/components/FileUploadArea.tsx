interface FileUploadAreaProps {
  uploadedFiles: globalThis.File[]
  dragOver: boolean
  onDragOver: (e: React.DragEvent<HTMLDivElement>) => void
  onDragLeave: (e: React.DragEvent<HTMLDivElement>) => void
  onDrop: (e: React.DragEvent<HTMLDivElement>) => void
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void
  onRemoveFile: (index: number) => void
  fileInputRef: React.RefObject<HTMLInputElement | null>
  children?: React.ReactNode
}

export function FileUploadArea({
  uploadedFiles: _uploadedFiles,
  dragOver,
  onDragOver,
  onDragLeave,
  onDrop,
  onFileSelect,
  onRemoveFile: _onRemoveFile,
  fileInputRef,
  children,
}: FileUploadAreaProps) {
  return (
    <div
      className={`chat-input-container ${dragOver ? 'drag-over' : ''}`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <input
        ref={fileInputRef}
        type="file"
        onChange={onFileSelect}
        style={{ display: 'none' }}
        accept=".txt,.md,.json,.text,.pdf,.doc,.docx"
        multiple
      />

      {children}

      {dragOver && (
        <div className="drag-overlay">
          <div className="drag-overlay-inner">
            <p className="drag-text">Release to upload file</p>
            <p className="drag-hint">Processed as MRT file by default</p>
          </div>
        </div>
      )}
    </div>
  )
}

