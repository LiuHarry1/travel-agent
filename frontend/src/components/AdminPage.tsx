import { useState, useEffect } from 'react'
import { getProviders, getLLMConfig, getAvailableModels, updateLLMConfig, type ProviderInfo } from '../api'
import { Alert } from './Alert'

export function AdminPage() {
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [provider, setProvider] = useState<string>('')
  const [model, setModel] = useState<string>('')
  const [ollamaUrl, setOllamaUrl] = useState<string>('http://localhost:11434')
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingProviders, setLoadingProviders] = useState(false)
  const [loadingModels, setLoadingModels] = useState(false)
  const [alert, setAlert] = useState<{ type: 'error' | 'success'; message: string } | null>(null)

  // Load providers and current configuration
  useEffect(() => {
    loadProviders()
    loadConfig()
  }, [])

  // Load available models when provider changes
  useEffect(() => {
    if (provider) {
      loadModels()
    }
  }, [provider, ollamaUrl])

  const loadProviders = async () => {
    try {
      setLoadingProviders(true)
      const response = await getProviders()
      setProviders(response.providers)
    } catch (error) {
      setAlert({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to load providers',
      })
    } finally {
      setLoadingProviders(false)
    }
  }

  const loadConfig = async () => {
    try {
      setLoading(true)
      const config = await getLLMConfig()
      setProvider(config.provider)
      setModel(config.model)
      
      // Set Ollama URL from config or use default
      if (config.provider === 'ollama') {
        setOllamaUrl(config.ollama_url || 'http://localhost:11434')
      }
    } catch (error) {
      setAlert({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to load configuration',
      })
    } finally {
      setLoading(false)
    }
  }

  const loadModels = async () => {
    if (!provider) return

    try {
      setLoadingModels(true)
      
      // Fetch models from backend API
      const response = await getAvailableModels(provider, provider === 'ollama' ? ollamaUrl : undefined)
      setAvailableModels(response.models || [])
      
      // If current model is not in the list, keep it
      if (model && response.models && !response.models.includes(model)) {
        // Keep current model
      } else if (response.models && response.models.length > 0 && !model) {
        setModel(response.models[0])
      }
    } catch (error) {
      setAlert({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to load available models',
      })
      setAvailableModels([])
    } finally {
      setLoadingModels(false)
    }
  }

  const handleUpdate = async () => {
    if (!provider || !model) {
      setAlert({
        type: 'error',
        message: 'Please select both provider and model',
      })
      return
    }

    try {
      setLoading(true)
      await updateLLMConfig({
        provider,
        model,
        ollama_url: provider === 'ollama' ? ollamaUrl : undefined,
      })
      setAlert({
        type: 'success',
        message: 'Configuration updated successfully! The new model will be used for future requests.',
      })
    } catch (error) {
      setAlert({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to update configuration',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider)
    setModel('') // Reset model when provider changes
  }

  const handleOllamaUrlChange = (newUrl: string) => {
    setOllamaUrl(newUrl)
  }

  return (
    <section className="admin-container">
      <div className="admin-header">
        <h1>Admin Settings</h1>
        <p className="admin-subtitle">Configure default LLM provider and model</p>
      </div>

      {alert && (
        <Alert
          type={alert.type}
          message={alert.message}
          onClose={() => setAlert(null)}
        />
      )}

      <div className="admin-content">
        <div className="admin-form">
          <div className="form-group">
            <label htmlFor="provider">Provider</label>
            <select
              id="provider"
              value={provider}
              onChange={(e) => handleProviderChange(e.target.value)}
              disabled={loading || loadingProviders}
              className="form-select"
            >
              <option value="">Select a provider</option>
              {providers.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          {provider === 'ollama' && (
            <div className="form-group">
              <label htmlFor="ollama-url">Ollama URL</label>
              <input
                id="ollama-url"
                type="text"
                value={ollamaUrl}
                onChange={(e) => handleOllamaUrlChange(e.target.value)}
                placeholder={ollamaUrl || 'http://localhost:11434'}
                disabled={loading}
                className="form-input"
              />
              <small className="form-hint">
                Enter the base URL of your Ollama instance. Click "Refresh Models" to fetch available models.
              </small>
            </div>
          )}

          {provider === 'ollama' && (
            <div className="form-group">
              <button
                type="button"
                onClick={loadModels}
                disabled={loadingModels || !ollamaUrl}
                className="btn btn-secondary"
              >
                {loadingModels ? 'Loading...' : 'Refresh Models'}
              </button>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="model">Model</label>
            {loadingModels && provider === 'ollama' ? (
              <div className="form-loading">Loading models...</div>
            ) : (
              <select
                id="model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={loading || !provider || availableModels.length === 0}
                className="form-select"
              >
                <option value="">Select a model</option>
                {availableModels.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            )}
            {provider && availableModels.length === 0 && !loadingModels && (
              <small className="form-error">
                No models available. {provider === 'ollama' ? 'Please check your Ollama URL and try refreshing.' : 'Please select a provider.'}
              </small>
            )}
          </div>

          <div className="form-actions">
            <button
              type="button"
              onClick={handleUpdate}
              disabled={loading || !provider || !model}
              className="btn btn-primary"
            >
              {loading ? 'Updating...' : 'Update Configuration'}
            </button>
          </div>
        </div>

        <div className="admin-info">
          <h3>Current Configuration</h3>
          <div className="info-card">
            <div className="info-row">
              <span className="info-label">Provider:</span>
              <span className="info-value">{provider || 'Not set'}</span>
            </div>
            <div className="info-row">
              <span className="info-label">Model:</span>
              <span className="info-value">{model || 'Not set'}</span>
            </div>
            {provider === 'ollama' && (
              <div className="info-row">
                <span className="info-label">Ollama URL:</span>
                <span className="info-value">{ollamaUrl || 'Not set'}</span>
              </div>
            )}
          </div>

          <div className="info-note">
            <p>
              <strong>Note:</strong> After updating the configuration, all new chat and review requests will use the selected model.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

