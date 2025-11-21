import { useEffect, useState } from 'react'
import type { ChecklistItem } from './types'
import { getDefaultConfig, saveConfig } from './api'

interface ChecklistEditorModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (systemPromptTemplate: string, checklist: ChecklistItem[]) => void
  initialSystemPromptTemplate?: string
  initialChecklist?: ChecklistItem[]
}

export function ChecklistEditorModal({
  isOpen,
  onClose,
  onSave,
  initialSystemPromptTemplate,
  initialChecklist,
}: ChecklistEditorModalProps) {
  const [systemPromptTemplate, setSystemPromptTemplate] = useState('')
  const [checklist, setChecklist] = useState<ChecklistItem[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Load config when modal opens
  useEffect(() => {
    if (isOpen) {
      if (initialSystemPromptTemplate !== undefined && initialChecklist !== undefined) {
        // Use provided initial values
        setSystemPromptTemplate(initialSystemPromptTemplate)
        setChecklist(initialChecklist)
        setLoading(false)
      } else {
        // Load default config from API
        setLoading(true)
        getDefaultConfig()
          .then((config) => {
            setSystemPromptTemplate(config.system_prompt_template)
            setChecklist(config.checklist)
          })
          .catch((error) => {
            console.error('Failed to load default config:', error)
            setSystemPromptTemplate('')
            setChecklist([])
          })
          .finally(() => {
            setLoading(false)
          })
      }
    } else {
      // Reset state when modal closes
      setSystemPromptTemplate('')
      setChecklist([])
      setLoading(false)
    }
  }, [isOpen, initialSystemPromptTemplate, initialChecklist])

  const handleAddItem = () => {
    setChecklist([...checklist, { id: '', description: '' }])
  }

  const handleUpdateItem = (index: number, field: 'id' | 'description', value: string) => {
    const updated = [...checklist]
    updated[index] = { ...updated[index], [field]: value }
    setChecklist(updated)
  }

  const handleDeleteItem = (index: number) => {
    setChecklist(checklist.filter((_, i) => i !== index))
  }

  const handleSave = async () => {
    // Validate checklist items
    const validChecklist = checklist.filter((item) => item.id.trim() && item.description.trim())
    
    if (!systemPromptTemplate.trim()) {
      setSaveError('System Prompt Template cannot be empty')
      return
    }
    
    if (validChecklist.length === 0) {
      setSaveError('At least one Checklist item is required')
      return
    }

    setSaving(true)
    setSaveError(null)

    try {
      await saveConfig({
        system_prompt_template: systemPromptTemplate,
        checklist: validChecklist,
      })
      onSave(systemPromptTemplate, validChecklist)
      onClose()
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Save failed'
      setSaveError(message)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={handleCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Edit Checklist and System Prompt Template</h2>
          <button type="button" className="modal-close-btn" onClick={handleCancel}>
            ×
          </button>
        </div>

        <div className="modal-body">
          {loading ? (
            <div className="modal-loading">Loading...</div>
          ) : (
            <>
              {/* System Prompt Template Section */}
              <div className="modal-section">
                <label className="modal-section-label">
                  <span>System Prompt Template</span>
                </label>
                <textarea
                  value={systemPromptTemplate}
                  onChange={(e) => setSystemPromptTemplate(e.target.value)}
                  placeholder="Please enter system prompt template (supports {checklist_section} and {requirement_section} variables)..."
                  className="modal-textarea"
                  rows={12}
                />
                <p className="form-hint" style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                  This template supports variables: {'{'}checklist_section{'}'} and {'{'}requirement_section{'}'} which will be automatically replaced.
                </p>
              </div>

              {/* Checklist Section */}
              <div className="modal-section">
                <div className="modal-section-header">
                  <label className="modal-section-label">
                    <span>Checklist Items</span>
                  </label>
                  <button
                    type="button"
                    className="modal-add-btn"
                    onClick={handleAddItem}
                    title="Add new item"
                  >
                    + Add
                  </button>
                </div>

                <div className="checklist-items">
                  {checklist.length === 0 ? (
                    <div className="checklist-empty">No checklist items. Click "Add" button to add new items</div>
                  ) : (
                    checklist.map((item, index) => (
                      <div key={index} className="checklist-item">
                        <div className="checklist-item-inputs">
                          <input
                            type="text"
                            value={item.id}
                            onChange={(e) => handleUpdateItem(index, 'id', e.target.value)}
                            placeholder="ID (e.g.: CHK-001)"
                            className="checklist-item-id"
                          />
                          <input
                            type="text"
                            value={item.description}
                            onChange={(e) => handleUpdateItem(index, 'description', e.target.value)}
                            placeholder="Description"
                            className="checklist-item-description"
                          />
                        </div>
                        <button
                          type="button"
                          className="checklist-item-delete"
                          onClick={() => handleDeleteItem(index)}
                          title="Delete"
                        >
                          ×
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="modal-footer">
          {saveError && (
            <div className="modal-error-message">{saveError}</div>
          )}
          <div className="modal-footer-buttons">
            <button type="button" className="modal-btn modal-btn-cancel" onClick={handleCancel} disabled={saving}>
              Cancel
            </button>
            <button type="button" className="modal-btn modal-btn-save" onClick={handleSave} disabled={saving}>
              {saving ? (
                <>
                  <div className="loading-spinner small"></div>
                  <span>Saving...</span>
                </>
              ) : (
                <span>Save</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

