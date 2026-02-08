import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, TestTube, Check, X, Loader2, Key as KeyIcon } from 'lucide-react'

interface LLMSettings {
  openai_api_key: string | null
  openai_base_url: string
  llm_model: string
  llm_temperature: number
  llm_max_tokens: number
  enable_llm: boolean
  system_prompt: string
  has_env_key: boolean
  // Embedding settings
  embedding_enabled: boolean
  embedding_base_url: string
  embedding_model: string
}

interface LLMProvider {
  name: string
  base_url: string
  models: string[]
  default_model: string
}

export default function Settings() {
  const [settings, setSettings] = useState<LLMSettings>({
    openai_api_key: null,
    openai_base_url: 'https://api.deepseek.com',
    llm_model: 'deepseek-chat',
    llm_temperature: 0.7,
    llm_max_tokens: 1000,
    enable_llm: true,
    system_prompt: '',
    has_env_key: false,
    embedding_enabled: true,
    embedding_base_url: 'http://localhost:11434/v1',
    embedding_model: 'nomic-embed-text'
  })
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testingEmbedding, setTestingEmbedding] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; response?: string } | null>(null)
  const [embeddingTestResult, setEmbeddingTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // 获取设置
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const token = localStorage.getItem('token')
        const [settingsRes, providersRes] = await Promise.all([
          fetch('/api/settings/llm', {
            headers: { Authorization: `Bearer ${token}` }
          }),
          fetch('/api/settings/llm/providers', {
            headers: { Authorization: `Bearer ${token}` }
          })
        ])

        if (settingsRes.ok) {
          const data = await settingsRes.json()
          setSettings(data)
        }

        if (providersRes.ok) {
          const data = await providersRes.json()
          setProviders(data.providers)
        }
      } catch (error) {
        console.error('Failed to fetch settings:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchSettings()
  }, [])

  // 保存设置
  const handleSave = async () => {
    setSaving(true)
    setSaveSuccess(false)

    try {
      const token = localStorage.getItem('token')
      const res = await fetch('/api/settings/llm', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(settings)
      })

      if (res.ok) {
        setSaveSuccess(true)
        setTimeout(() => setSaveSuccess(false), 3000)
      } else {
        alert('保存失败')
      }
    } catch (error) {
      alert('保存失败: ' + error)
    } finally {
      setSaving(false)
    }
  }

  // 测试连接
  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)

    try {
      const token = localStorage.getItem('token')
      const requestBody: {
        api_key?: string
        base_url: string
        model: string
      } = {
        base_url: settings.openai_base_url,
        model: settings.llm_model
      }

      // 只有当用户输入了 API Key 时才发送（留空则使用环境变量）
      if (settings.openai_api_key && settings.openai_api_key.trim()) {
        requestBody.api_key = settings.openai_api_key
      }

      const res = await fetch('/api/settings/llm/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(requestBody)
      })

      const data = await res.json()
      setTestResult(data)
    } catch (error) {
      setTestResult({ success: false, message: '测试失败: ' + error })
    } finally {
      setTesting(false)
    }
  }

  // 测试 Embedding
  const handleTestEmbedding = async () => {
    setTestingEmbedding(true)
    setEmbeddingTestResult(null)

    try {
      const token = localStorage.getItem('token')
      const res = await fetch('/api/settings/embedding/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          base_url: settings.embedding_base_url,
          model: settings.embedding_model
        })
      })

      const data = await res.json()
      setEmbeddingTestResult(data)
    } catch (error) {
      setEmbeddingTestResult({ success: false, message: '测试失败: ' + error })
    } finally {
      setTestingEmbedding(false)
    }
  }

  // 选择预设服务商
  const selectProvider = (provider: LLMProvider) => {
    setSettings({
      ...settings,
      openai_base_url: provider.base_url,
      llm_model: provider.default_model
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 animate-spin text-primary-400" />
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <SettingsIcon className="text-primary-400" />
          系统设置
        </h1>
        <div className="flex items-center gap-3">
          <button
            onClick={handleTest}
            disabled={testing}
            className="px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg flex items-center gap-2 disabled:opacity-50 transition-colors"
          >
            {testing ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <TestTube size={18} />
            )}
            测试连接
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg flex items-center gap-2 disabled:opacity-50 transition-colors"
          >
            {saving ? (
              <Loader2 size={18} className="animate-spin" />
            ) : saveSuccess ? (
              <Check size={18} />
            ) : (
              <span>保存</span>
            )}
            {saving ? '保存中...' : saveSuccess ? '已保存' : '保存设置'}
          </button>
        </div>
      </div>

      {/* 测试结果 */}
      {testResult && (
        <div className={`mb-6 p-4 rounded-lg flex items-start gap-3 ${
          testResult.success ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'
        }`}>
          {testResult.success ? (
            <Check className="text-green-400 mt-0.5" size={20} />
          ) : (
            <X className="text-red-400 mt-0.5" size={20} />
          )}
          <div>
            <p className={testResult.success ? 'text-green-300' : 'text-red-300'}>
              {testResult.message}
            </p>
            {testResult.response && (
              <p className="text-dark-400 mt-2 text-sm">AI 回复: {testResult.response}</p>
            )}
          </div>
        </div>
      )}

      {/* Embedding 测试结果 */}
      {embeddingTestResult && (
        <div className={`mb-6 p-4 rounded-lg flex items-start gap-3 ${
          embeddingTestResult.success ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'
        }`}>
          {embeddingTestResult.success ? (
            <Check className="text-green-400 mt-0.5" size={20} />
          ) : (
            <X className="text-red-400 mt-0.5" size={20} />
          )}
          <div>
            <p className={embeddingTestResult.success ? 'text-green-300' : 'text-red-300'}>
              {embeddingTestResult.message}
            </p>
          </div>
        </div>
      )}

      <div className="space-y-6">
        {/* LLM 开关 */}
        <div className="bg-dark-900 rounded-lg p-6 border border-dark-800">
          <h2 className="text-lg font-semibold mb-4">LLM 功能</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-dark-300">启用 AI 智能助手</p>
              <p className="text-sm text-dark-500 mt-1">关闭后将使用规则匹配模式</p>
            </div>
            <button
              onClick={() => setSettings({ ...settings, enable_llm: !settings.enable_llm })}
              className={`relative w-14 h-7 rounded-full transition-colors ${
                settings.enable_llm ? 'bg-primary-600' : 'bg-dark-700'
              }`}
            >
              <span className={`absolute top-1 w-5 h-5 bg-white rounded-full transition-transform ${
                settings.enable_llm ? 'translate-x-7' : 'translate-x-1'
              }`} />
            </button>
          </div>
        </div>

        {/* 快速选择服务商 */}
        <div className="bg-dark-900 rounded-lg p-6 border border-dark-800">
          <h2 className="text-lg font-semibold mb-4">快速配置</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {providers.map((provider) => (
              <button
                key={provider.name}
                onClick={() => selectProvider(provider)}
                className={`p-3 rounded-lg border transition-colors text-left ${
                  settings.openai_base_url === provider.base_url
                    ? 'border-primary-500 bg-primary-900/20'
                    : 'border-dark-700 hover:border-dark-600'
                }`}
              >
                <p className="font-medium">{provider.name}</p>
                <p className="text-xs text-dark-500 mt-1 truncate">{provider.base_url}</p>
              </button>
            ))}
          </div>
        </div>

        {/* API 配置 */}
        <div className="bg-dark-900 rounded-lg p-6 border border-dark-800">
          <h2 className="text-lg font-semibold mb-4">API 配置</h2>
          <div className="space-y-4">
            {/* API Key */}
            <div>
              <label className="block text-sm text-dark-400 mb-2">API Key</label>
              <div className="relative">
                <input
                  type="password"
                  value={settings.openai_api_key || ''}
                  onChange={(e) => setSettings({ ...settings, openai_api_key: e.target.value })}
                  placeholder="留空使用环境变量 OPENAI_API_KEY"
                  className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-2.5 pr-10 focus:outline-none focus:border-primary-500"
                />
                {settings.has_env_key && !settings.openai_api_key && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2" title="已配置环境变量">
                    <KeyIcon size={16} className="text-green-400" />
                  </div>
                )}
              </div>
              <p className="text-xs text-dark-500 mt-1">
                {settings.has_env_key
                  ? "已从环境变量读取 API Key，可在此处输入覆盖"
                  : "密钥将保存在服务器端，或设置环境变量 OPENAI_API_KEY"}
              </p>
            </div>

            {/* Base URL */}
            <div>
              <label className="block text-sm text-dark-400 mb-2">API Base URL</label>
              <input
                type="text"
                value={settings.openai_base_url}
                onChange={(e) => setSettings({ ...settings, openai_base_url: e.target.value })}
                className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-primary-500"
              />
            </div>

            {/* 模型 */}
            <div>
              <label className="block text-sm text-dark-400 mb-2">模型名称</label>
              <input
                type="text"
                value={settings.llm_model}
                onChange={(e) => setSettings({ ...settings, llm_model: e.target.value })}
                list="models-suggest"
                className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-primary-500"
              />
              <datalist id="models-suggest">
                {providers.flatMap(p => p.models).map((model) => (
                  <option key={model} value={model} />
                ))}
              </datalist>
            </div>

            {/* 温度和 Tokens */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-dark-400 mb-2">Temperature (0-1)</label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={settings.llm_temperature}
                  onChange={(e) => setSettings({ ...settings, llm_temperature: parseFloat(e.target.value) })}
                  className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-primary-500"
                />
                <p className="text-xs text-dark-500 mt-1">越低越确定，越高越随机</p>
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-2">Max Tokens</label>
                <input
                  type="number"
                  min="100"
                  max="8000"
                  value={settings.llm_max_tokens}
                  onChange={(e) => setSettings({ ...settings, llm_max_tokens: parseInt(e.target.value) })}
                  className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-primary-500"
                />
                <p className="text-xs text-dark-500 mt-1">最大回复长度</p>
              </div>
            </div>
          </div>
        </div>

        {/* 系统提示词 */}
        <div className="bg-dark-900 rounded-lg p-6 border border-dark-800">
          <h2 className="text-lg font-semibold mb-4">系统提示词</h2>
          <textarea
            value={settings.system_prompt}
            onChange={(e) => setSettings({ ...settings, system_prompt: e.target.value })}
            rows={10}
            className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-3 focus:outline-none focus:border-primary-500 font-mono text-sm"
            placeholder="输入系统提示词..."
          />
          <p className="text-xs text-dark-500 mt-2">修改提示词可以调整 AI 的行为和回复风格</p>
        </div>

        {/* Embedding 配置 */}
        <div className="bg-dark-900 rounded-lg p-6 border border-dark-800">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">语义搜索配置 (Embedding)</h2>
            <button
              onClick={handleTestEmbedding}
              disabled={testingEmbedding || !settings.embedding_enabled}
              className="px-3 py-1.5 bg-dark-800 hover:bg-dark-700 rounded-lg flex items-center gap-2 disabled:opacity-50 transition-colors text-sm"
            >
              {testingEmbedding ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <TestTube size={14} />
              )}
              测试
            </button>
          </div>

          <div className="flex items-center justify-between mb-4 pb-4 border-b border-dark-800">
            <div>
              <p className="text-dark-300">启用语义搜索</p>
              <p className="text-sm text-dark-500 mt-1">用于智能匹配和语义理解</p>
            </div>
            <button
              onClick={() => setSettings({ ...settings, embedding_enabled: !settings.embedding_enabled })}
              className={`relative w-14 h-7 rounded-full transition-colors ${
                settings.embedding_enabled ? 'bg-primary-600' : 'bg-dark-700'
              }`}
            >
              <span className={`absolute top-1 w-5 h-5 bg-white rounded-full transition-transform ${
                settings.embedding_enabled ? 'translate-x-7' : 'translate-x-1'
              }`} />
            </button>
          </div>

          <div className="space-y-4">
            {/* Base URL */}
            <div>
              <label className="block text-sm text-dark-400 mb-2">Embedding API 地址</label>
              <input
                type="text"
                value={settings.embedding_base_url}
                onChange={(e) => setSettings({ ...settings, embedding_base_url: e.target.value })}
                className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-primary-500"
                placeholder="http://localhost:11434/v1"
              />
              <p className="text-xs text-dark-500 mt-1">本地 Ollama: http://localhost:11434/v1</p>
            </div>

            {/* 模型 */}
            <div>
              <label className="block text-sm text-dark-400 mb-2">Embedding 模型</label>
              <input
                type="text"
                value={settings.embedding_model}
                onChange={(e) => setSettings({ ...settings, embedding_model: e.target.value })}
                list="embedding-models-suggest"
                className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-primary-500"
                placeholder="nomic-embed-text"
              />
              <datalist id="embedding-models-suggest">
                <option value="nomic-embed-text" />
                <option value="nomic-embed-text:latest" />
                <option value="mxbai-embed-large" />
                <option value="mxbai-embed-large:latest" />
                <option value="text-embedding-3-small" />
                <option value="text-embedding-ada-002" />
              </datalist>
              <p className="text-xs text-dark-500 mt-1">推荐使用 nomic-embed-text (本地 Ollama)</p>
            </div>
          </div>
        </div>

        {/* 系统提示词 */}
        <div className="bg-dark-900 rounded-lg p-6 border border-dark-800">
          <h2 className="text-lg font-semibold mb-4">系统提示词</h2>
          <textarea
            value={settings.system_prompt}
            onChange={(e) => setSettings({ ...settings, system_prompt: e.target.value })}
            rows={10}
            className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-3 focus:outline-none focus:border-primary-500 font-mono text-sm"
            placeholder="输入系统提示词..."
          />
          <p className="text-xs text-dark-500 mt-2">修改提示词可以调整 AI 的行为和回复风格</p>
        </div>
      </div>
    </div>
  )
}
