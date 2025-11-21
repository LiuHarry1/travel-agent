import { useState } from 'react'
import type { ReviewResponse, ChecklistItem, Alert } from '../types'
import { reviewMrt } from '../api'

export function useReview() {
  const [mrtContent, setMrtContent] = useState('')
  const [softwareRequirement, setSoftwareRequirement] = useState('')
  const [result, setResult] = useState<ReviewResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [alert, setAlert] = useState<Alert | null>(null)
  const [customSystemPrompt, setCustomSystemPrompt] = useState<string | undefined>(undefined)
  const [customChecklist, setCustomChecklist] = useState<ChecklistItem[] | undefined>(undefined)

  const submitReview = async () => {
    if (!mrtContent.trim()) {
      setAlert({ type: 'error', message: 'Please enter MRT content' })
      return
    }

    setAlert(null)
    setResult(null)
    setLoading(true)

    try {
      const payload = {
        mrt_content: mrtContent,
        software_requirement: softwareRequirement.trim() || undefined,
        checklist: customChecklist,
        system_prompt: customSystemPrompt,
      }

      const response = await reviewMrt(payload)
      setResult(response)
      setAlert({ type: 'success', message: 'Review completed' })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Review failed'
      setAlert({ type: 'error', message })
    } finally {
      setLoading(false)
    }
  }

  const handleChecklistSave = (systemPromptTemplate: string, checklist: ChecklistItem[]) => {
    setCustomSystemPrompt(systemPromptTemplate)
    setCustomChecklist(checklist)
  }

  return {
    mrtContent,
    setMrtContent,
    softwareRequirement,
    setSoftwareRequirement,
    result,
    loading,
    alert,
    setAlert,
    customSystemPrompt,
    customChecklist,
    submitReview,
    handleChecklistSave,
  }
}

