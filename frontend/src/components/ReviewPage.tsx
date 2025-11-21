import { useState, useRef, type FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useReview } from '../hooks/useReview'
import { ChecklistEditorModal } from '../ChecklistEditorModal'
import { Alert } from './Alert'
import { handleFileDrop, handleFileSelect } from '../utils/fileReader'

export function ReviewPage() {
  const {
    mrtContent,
    setMrtContent,
    softwareRequirement,
    setSoftwareRequirement,
    result,
    loading,
    alert,
    customSystemPrompt,
    customChecklist,
    submitReview,
    handleChecklistSave,
  } = useReview()

  const [isChecklistModalOpen, setIsChecklistModalOpen] = useState(false)
  const mrtFileInputRef = useRef<HTMLInputElement | null>(null)
  const requirementFileInputRef = useRef<HTMLInputElement | null>(null)

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    await submitReview()
  }

  const handleMrtDrop = (e: React.DragEvent<HTMLTextAreaElement>) => {
    handleFileDrop(e, setMrtContent)
  }

  const handleRequirementDrop = (e: React.DragEvent<HTMLTextAreaElement>) => {
    handleFileDrop(e, setSoftwareRequirement)
  }

  const handleMrtFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFileSelect(e, setMrtContent)
  }

  const handleRequirementFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFileSelect(e, setSoftwareRequirement)
  }

  return (
    <section className="review-container">
      <div className="review-header">
        <div className="review-header-top">
          <div className="review-title-section">
            <h2>Single-Pass Review</h2>
            <p className="review-subtitle">
              Paste your MRT content once and get instant AI-powered review feedback, aligned with your requirements and checklist.
            </p>
          </div>
          <button
            type="button"
            className="edit-checklist-btn"
            onClick={() => setIsChecklistModalOpen(true)}
            title="Edit Checklist and System Prompt"
          >
            <span>Configure</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="review-form">
        <div className="form-group">
          <label className="form-label">
            <span className="label-text">MRT Test Case</span>
            <span className="label-required">*</span>
          </label>
          <div className="review-upload-row">
            <button
              type="button"
              className="review-upload-btn"
              onClick={() => mrtFileInputRef.current?.click()}
            >
              Upload file
            </button>
            <span className="review-upload-hint">Supports .txt, .md, .json (text only)</span>
          </div>
          <input
            ref={mrtFileInputRef}
            type="file"
            accept=".txt,.md,.json,.text"
            style={{ display: 'none' }}
            onChange={handleMrtFileSelect}
          />
          <textarea
            required
            value={mrtContent}
            onChange={(e) => setMrtContent(e.target.value)}
            placeholder="Paste your complete MRT test case content here, or drag a text file to upload..."
            className="form-textarea"
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleMrtDrop}
          />
          <p className="form-hint">
            The AI will review your test case against the configured checklist and software requirement (if provided), and provide improvement suggestions.
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">
            <span className="label-text">Software Requirement</span>
            <span className="label-optional">(Optional)</span>
          </label>
          <div className="review-upload-row">
            <button
              type="button"
              className="review-upload-btn"
              onClick={() => requirementFileInputRef.current?.click()}
            >
              Upload file
            </button>
            <span className="review-upload-hint">Supports .txt, .md, .json (text only)</span>
          </div>
          <input
            ref={requirementFileInputRef}
            type="file"
            accept=".txt,.md,.json,.text"
            style={{ display: 'none' }}
            onChange={handleRequirementFileSelect}
          />
          <textarea
            value={softwareRequirement}
            onChange={(e) => setSoftwareRequirement(e.target.value)}
            placeholder="Paste your software requirement content here, or drag a text file to upload (optional)..."
            className="form-textarea"
            rows={8}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleRequirementDrop}
          />
          <p className="form-hint">
            Software requirement from Codebeamer. The AI will review test cases against requirements to ensure comprehensive coverage.
          </p>
        </div>

        <div className="form-actions">
          <button type="submit" disabled={loading} className="submit-button">
            {loading ? (
              <>
                <div className="loading-spinner small"></div>
                <span>Reviewing...</span>
              </>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 11l3 3L22 4" />
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
                <span>Start Review</span>
              </>
            )}
          </button>
        </div>

        {alert && <Alert type={alert.type} message={alert.message} />}

        {result && (
          <div className="review-results">
            <div className="result-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {result.raw_content || result.summary || 'No content available'}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </form>

      <ChecklistEditorModal
        isOpen={isChecklistModalOpen}
        onClose={() => setIsChecklistModalOpen(false)}
        onSave={handleChecklistSave}
        initialSystemPromptTemplate={customSystemPrompt}
        initialChecklist={customChecklist}
      />
    </section>
  )
}

