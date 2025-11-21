/**
 * Utility functions for reading files
 */

/**
 * Reads a text file and returns its content as a string
 * @param file The file to read
 * @returns Promise that resolves with the file content
 */
export function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result)
      } else {
        reject(new Error('Failed to read file as text'))
      }
    }
    reader.onerror = () => reject(new Error('Failed to read file'))
    reader.readAsText(file)
  })
}

/**
 * Handles file drop event and reads the first file
 * @param e Drag event
 * @param onFileRead Callback with file content
 */
export function handleFileDrop(
  e: React.DragEvent<HTMLTextAreaElement>,
  onFileRead: (content: string) => void
): void {
  e.preventDefault()
  const file = e.dataTransfer.files?.[0]
  if (!file) return

  readTextFile(file)
    .then(onFileRead)
    .catch((error) => {
      console.error('Failed to read dropped file:', error)
    })
}

/**
 * Handles file input change event and reads the selected file
 * @param e Change event
 * @param onFileRead Callback with file content
 */
export function handleFileSelect(
  e: React.ChangeEvent<HTMLInputElement>,
  onFileRead: (content: string) => void
): void {
  const file = e.target.files?.[0]
  if (!file) return

  readTextFile(file)
    .then((content) => {
      onFileRead(content)
      // Reset input to allow selecting same file again
      e.target.value = ''
    })
    .catch((error) => {
      console.error('Failed to read selected file:', error)
    })
}

