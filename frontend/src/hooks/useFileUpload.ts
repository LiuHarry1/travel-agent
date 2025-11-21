import { useState, useRef, type DragEvent, type ChangeEvent } from 'react'

const VALID_EXTENSIONS = ['.txt', '.md', '.json', '.text', '.pdf', '.doc', '.docx']
const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5MB

interface FileUploadError {
  type: 'size' | 'format'
  files: string[]
}

export function useFileUpload() {
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([])
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = (file: File): { valid: boolean; error?: FileUploadError } => {
    const fileExtension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'))
    const isValidType = 
      VALID_EXTENSIONS.includes(fileExtension) || 
      file.type.startsWith('text/') ||
      file.type === 'application/pdf' ||
      file.type === 'application/msword' ||
      file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    const isValidSize = file.size <= MAX_FILE_SIZE

    if (!isValidSize) {
      return { valid: false, error: { type: 'size', files: [file.name] } }
    }
    if (!isValidType) {
      return { valid: false, error: { type: 'format', files: [file.name] } }
    }
    return { valid: true }
  }

  const addFiles = (files: File[]): FileUploadError[] => {
    const errors: FileUploadError[] = []
    const validFiles: File[] = []
    const errorMap = new Map<FileUploadError['type'], string[]>()

    files.forEach((file) => {
      const validation = validateFile(file)
      if (validation.valid) {
        validFiles.push(file)
      } else if (validation.error) {
        const existing = errorMap.get(validation.error.type) || []
        existing.push(...validation.error.files)
        errorMap.set(validation.error.type, existing)
      }
    })

    // Combine errors by type
    errorMap.forEach((fileNames, type) => {
      errors.push({ type, files: fileNames })
    })

    if (validFiles.length > 0) {
      setUploadedFiles((prev) => [...prev, ...validFiles])
    }

    return errors
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)

    const files = Array.from(e.dataTransfer.files)
    return addFiles(files)
  }

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      const fileArray = Array.from(files)
      addFiles(fileArray)
    }
    // Reset input to allow selecting same file again
    if (e.target) {
      e.target.value = ''
    }
  }

  const removeFile = (index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const clearFiles = () => {
    setUploadedFiles([])
  }

  const openFileDialog = () => {
    fileInputRef.current?.click()
  }

  const formatErrorMessages = (errors: FileUploadError[]): string => {
    if (errors.length === 0) return ''

    const sizeErrors = errors.find((e) => e.type === 'size')
    const formatErrors = errors.find((e) => e.type === 'format')

    const messages = [
      sizeErrors && `File too large (>5MB): ${sizeErrors.files.join(', ')}`,
      formatErrors && `Unsupported file format: ${formatErrors.files.join(', ')}`,
    ].filter(Boolean)

    return (
      (messages.length > 0 && (messages as string[]).join('; ')) ||
      'File validation failed: Only text files, PDF, and Word documents are supported (.txt, .md, .json, .pdf, .doc, .docx), each file not exceeding 5MB.'
    )
  }

  return {
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
    addFiles,
    formatErrorMessages,
  }
}

