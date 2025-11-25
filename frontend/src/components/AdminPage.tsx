import { useState, useEffect } from 'react'
import { 
  getProviders, 
  getLLMConfig, 
  getAvailableModels, 
  updateLLMConfig, 
  getDefaultConfig,
  saveConfig,
  getMCPConfig,
  updateMCPConfig,
  type ProviderInfo 
} from '../api'
import { Alert } from './Alert'

type TabType = 'llm' | 'prompt' | 'mcp'

export function AdminPage() {
  const [activeTab, setActiveTab] = useState<TabType>('llm')
  
  // LLM Config state
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [provider, setProvider] = useState<string>('')
  const [model, setModel] = useState<string>('')
  const [ollamaUrl, setOllamaUrl] = useState<string>('http://localhost:11434')
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState<string>('')
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingProviders, setLoadingProviders] = useState(false)
  const [loadingModels, setLoadingModels] = useState(false)
  
  // System Prompt state
  const [systemPrompt, setSystemPrompt] = useState<string>('')
  const [loadingPrompt, setLoadingPrompt] = useState(false)
  const [savingPrompt, setSavingPrompt] = useState(false)
  
  // MCP Config state
  const [mcpConfig, setMcpConfig] = useState<string>('')
  const [mcpServerCount, setMcpServerCount] = useState<number>(0)
  const [mcpToolCount, setMcpToolCount] = useState<number>(0)
  const [loadingMcp, setLoadingMcp] = useState(false)
  const [savingMcp, setSavingMcp] = useState(false)
  
  const [alert, setAlert] = useState<{ type: 'error' | 'success'; message: string } | null>(null)

  // Load providers and current configuration
  useEffect(() => {
    loadProviders()
    loadConfig()
    loadSystemPrompt()
    loadMCPConfig()
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
      
      // Set provider-specific URLs from config or use defaults
      if (config.provider === 'ollama') {
        setOllamaUrl(config.ollama_url || 'http://localhost:11434')
      } else if (config.provider === 'openai') {
        setOpenaiBaseUrl(config.openai_base_url || '')
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
        openai_base_url: provider === 'openai' ? openaiBaseUrl : undefined,
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

  const handleOpenaiBaseUrlChange = (newUrl: string) => {
    setOpenaiBaseUrl(newUrl)
  }

  const loadSystemPrompt = async () => {
    try {
      setLoadingPrompt(true)
      const config = await getDefaultConfig()
      setSystemPrompt(config.system_prompt_template || '')
    } catch (error) {
      setAlert({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to load system prompt',
      })
    } finally {
      setLoadingPrompt(false)
    }
  }

  const handleSaveSystemPrompt = async () => {
    if (!systemPrompt.trim()) {
      setAlert({
        type: 'error',
        message: 'System prompt template cannot be empty',
      })
      return
    }

    try {
      setSavingPrompt(true)
      await saveConfig({
        system_prompt_template: systemPrompt,
      })
      setAlert({
        type: 'success',
        message: 'System prompt template updated successfully! The new template will be used for future conversations.',
      })
    } catch (error) {
      setAlert({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to save system prompt template',
      })
    } finally {
      setSavingPrompt(false)
    }
  }

  const loadMCPConfig = async () => {
    try {
      setLoadingMcp(true)
      const config = await getMCPConfig()
      setMcpConfig(JSON.stringify(config.config, null, 2))
      setMcpServerCount(config.server_count)
      setMcpToolCount(config.tool_count)
    } catch (error) {
      setAlert({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to load MCP configuration',
      })
    } finally {
      setLoadingMcp(false)
    }
  }

  const handleSaveMCPConfig = async () => {
    if (!mcpConfig.trim()) {
      setAlert({
        type: 'error',
        message: 'MCP configuration cannot be empty',
      })
      return
    }

    try {
      // Validate JSON
      const parsed = JSON.parse(mcpConfig)
      if (!parsed.mcpServers || typeof parsed.mcpServers !== 'object') {
        setAlert({
          type: 'error',
          message: 'Invalid MCP configuration: "mcpServers" key is required',
        })
        return
      }

      setSavingMcp(true)
      await updateMCPConfig({
        config: parsed,
      })
      setAlert({
        type: 'success',
        message: 'MCP configuration updated successfully! The new tools will be available for future conversations.',
      })
      // Reload to get updated counts
      await loadMCPConfig()
    } catch (error) {
      if (error instanceof SyntaxError) {
        setAlert({
          type: 'error',
          message: 'Invalid JSON format. Please check your configuration.',
        })
      } else {
        setAlert({
          type: 'error',
          message: error instanceof Error ? error.message : 'Failed to save MCP configuration',
        })
      }
    } finally {
      setSavingMcp(false)
    }
  }

  return (
    <section className="admin-container">
      <div className="admin-header">
        <h1>Admin Settings</h1>
        <p className="admin-subtitle">Configure LLM, system prompt, and MCP tools</p>
      </div>

      {alert && (
        <Alert
          type={alert.type}
          message={alert.message}
          onClose={() => setAlert(null)}
        />
      )}

      {/* Tabs */}
      <div className="admin-tabs">
        <button
          type="button"
          className={`admin-tab ${activeTab === 'llm' ? 'active' : ''}`}
          onClick={() => setActiveTab('llm')}
        >
          LLM Configuration
        </button>
        <button
          type="button"
          className={`admin-tab ${activeTab === 'prompt' ? 'active' : ''}`}
          onClick={() => setActiveTab('prompt')}
        >
          System Prompt
        </button>
        <button
          type="button"
          className={`admin-tab ${activeTab === 'mcp' ? 'active' : ''}`}
          onClick={() => setActiveTab('mcp')}
        >
          MCP Tools
        </button>
      </div>

      <div className="admin-content">
        {/* LLM Configuration Tab */}
        {activeTab === 'llm' && (
          <>
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

              {provider === 'openai' && (
                <div className="form-group">
                  <label htmlFor="openai-base-url">OpenAI Base URL</label>
                  <input
                    id="openai-base-url"
                    type="text"
                    value={openaiBaseUrl}
                    onChange={(e) => handleOpenaiBaseUrlChange(e.target.value)}
                    placeholder="https://api.openai.com/v1 or http://10.150.117.242:33148/v1"
                    disabled={loading}
                    className="form-input"
                  />
                  <small className="form-hint">
                    Enter the base URL for OpenAI API or OpenAI-compatible proxy server. 
                    Defaults to https://api.openai.com/v1 if not specified. 
                    For proxy servers, include /v1 at the end (e.g., http://10.150.117.242:33148/v1).
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
                {provider === 'openai' && (
                  <div className="info-row">
                    <span className="info-label">OpenAI Base URL:</span>
                    <span className="info-value">{openaiBaseUrl || 'https://api.openai.com/v1 (default)'}</span>
                  </div>
                )}
              </div>

              <div className="info-note">
                <p>
                  <strong>Note:</strong> After updating the configuration, all new chat and review requests will use the selected model.
                </p>
              </div>
            </div>
          </>
        )}

        {/* System Prompt Tab */}
        {activeTab === 'prompt' && (
          <>
            <div className="admin-form" style={{ gridColumn: '1 / -1' }}>
              <div className="form-group">
                <label htmlFor="system-prompt">System Prompt Template</label>
                {loadingPrompt ? (
                  <div className="form-loading">Loading system prompt template...</div>
                ) : (
                  <textarea
                    id="system-prompt"
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                    disabled={savingPrompt}
                    className="form-textarea"
                    rows={15}
                    placeholder="You are a helpful travel agent assistant. Your goal is to help users with travel-related questions and planning.&#10;&#10;Available Tools:&#10;{tools}&#10;&#10;Instructions:&#10;- Use tools when you need specific information to answer questions&#10;- Base your answers STRICTLY on tool results&#10;- Do not add information not in tool results"
                  />
                )}
                <small className="form-hint">
                  Enter the system prompt template. Use <code>{'{tools}'}</code> placeholder to insert the available tools list. 
                  If <code>{'{tools}'}</code> is not present, tools will be automatically appended at the end.
                </small>
              </div>

              <div className="form-actions">
                <button
                  type="button"
                  onClick={handleSaveSystemPrompt}
                  disabled={savingPrompt || loadingPrompt || !systemPrompt.trim()}
                  className="btn btn-primary"
                >
                  {savingPrompt ? 'Saving...' : 'Save System Prompt Template'}
                </button>
              </div>
            </div>

            <div className="admin-info" style={{ gridColumn: '1 / -1' }}>
              <h3>Template Info</h3>
              <div className="info-card">
                <div className="info-row">
                  <span className="info-label">Length:</span>
                  <span className="info-value">{systemPrompt.length} characters</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Contains {'{tools}'} placeholder:</span>
                  <span className="info-value">{systemPrompt.includes('{tools}') ? 'Yes' : 'No (tools will be appended)'}</span>
                </div>
              </div>
              <div className="info-note">
                <p>
                  <strong>Note:</strong> The <code>{'{tools}'}</code> placeholder will be replaced with the list of available tools when the system prompt is generated. 
                  If you don't include the placeholder, tools will be automatically added at the end. Changes take effect immediately for new conversations.
                </p>
              </div>
            </div>
          </>
        )}

        {/* MCP Tools Tab */}
        {activeTab === 'mcp' && (
          <>
            <div className="admin-form" style={{ gridColumn: '1 / -1' }}>
              <div className="form-group">
                <label htmlFor="mcp-config">MCP Configuration (JSON)</label>
                {loadingMcp ? (
                  <div className="form-loading">Loading MCP configuration...</div>
                ) : (
                  <textarea
                    id="mcp-config"
                    value={mcpConfig}
                    onChange={(e) => setMcpConfig(e.target.value)}
                    disabled={savingMcp}
                    className="form-textarea"
                    rows={20}
                    placeholder='{"mcpServers": {...}}'
                    style={{ fontFamily: 'monospace', fontSize: '13px' }}
                  />
                )}
                <small className="form-hint">
                  Edit the MCP servers configuration in JSON format. Each server should have "command", "args", and optionally "env" fields.
                </small>
              </div>

              <div className="form-actions">
                <button
                  type="button"
                  onClick={handleSaveMCPConfig}
                  disabled={savingMcp || loadingMcp || !mcpConfig.trim()}
                  className="btn btn-primary"
                >
                  {savingMcp ? 'Saving...' : 'Save MCP Configuration'}
                </button>
              </div>
            </div>

            <div className="admin-info" style={{ gridColumn: '1 / -1' }}>
              <h3>Current MCP Configuration</h3>
              <div className="info-card">
                <div className="info-row">
                  <span className="info-label">Servers:</span>
                  <span className="info-value">{mcpServerCount}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Tools:</span>
                  <span className="info-value">{mcpToolCount}</span>
                </div>
              </div>
              <div className="info-note">
                <p>
                  <strong>Note:</strong> After updating the MCP configuration, the registry will be reloaded and new tools will be available for future conversations.
                </p>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  )
}

