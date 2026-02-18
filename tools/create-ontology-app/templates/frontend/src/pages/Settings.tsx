import { useState, useEffect } from 'react'
import {
  Settings as SettingsIcon, TestTube, Check, X, Loader2, Key as KeyIcon,
  History, ChevronDown, ChevronRight, RotateCcw, Plus, Pencil, Trash2, RefreshCw
} from 'lucide-react'
import axios from 'axios'

// ========== Types ==========

interface LLMSettings {
  openai_api_key: string | null
  openai_base_url: string
  llm_model: string
  llm_temperature: number
  llm_max_tokens: number
  enable_llm: boolean
  system_prompt: string
  has_env_key: boolean
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

interface HistoryItem {
  id: number
  config_key: string
  version: number
  changed_by: number
  changed_at: string
  change_reason: string | null
  is_current: boolean
}

interface HistoryDetail {
  id: number
  version: number
  old_value: Record<string, any>
  new_value: Record<string, any>
  changed_by: number
  changer_name: string | null
  changed_at: string
  change_reason: string | null
  is_current: boolean
}

interface ConfigItem {
  id: number
  group: string
  key: string
  value: string
  value_type: string
  name: string
  description: string
  is_public: boolean
  is_system: boolean
}

// ========== API helpers ==========

const api = axios.create({ baseURL: '/api', headers: { 'Content-Type': 'application/json' } })
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ========== Tab definitions ==========

const TABS = [
  { key: 'llm', label: 'LLM 配置' },
  { key: 'system', label: '系统基础' },
  { key: 'security', label: '安全策略' },
  { key: 'business', label: '业务参数' },
] as const

type TabKey = typeof TABS[number]['key']

// ========== Main Component ==========

export default function Settings() {
  const [activeTab, setActiveTab] = useState<TabKey>('llm')

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <SettingsIcon size={24} className="text-primary-400" />
        <h1 className="text-2xl font-bold">系统设置</h1>
      </div>

      {/* Tab Selector */}
      <div className="flex gap-2 mb-6">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              activeTab === tab.key
                ? 'bg-primary-600 text-white'
                : 'bg-dark-800 hover:bg-dark-700 text-dark-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'llm' ? (
        <LLMTab />
      ) : (
        <ConfigGroupTab group={activeTab} />
      )}
    </div>
  )
}

// ========== LLM Tab (existing functionality + history) ==========

function LLMTab() {
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
  const [showHistory, setShowHistory] = useState(false)

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const [settingsRes, providersRes] = await Promise.all([
          api.get('/settings/llm'),
          api.get('/settings/llm/providers')
        ])
        setSettings(settingsRes.data)
        setProviders(providersRes.data.providers)
      } catch (error) {
        console.error('Failed to fetch settings:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchSettings()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setSaveSuccess(false)
    try {
      const res = await api.post('/settings/llm', settings)
      if (res.status === 200) {
        setSaveSuccess(true)
        setTimeout(() => setSaveSuccess(false), 3000)
      }
    } catch (error) {
      alert('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const requestBody: { api_key?: string; base_url: string; model: string } = {
        base_url: settings.openai_base_url,
        model: settings.llm_model
      }
      if (settings.openai_api_key && settings.openai_api_key.trim()) {
        requestBody.api_key = settings.openai_api_key
      }
      const res = await api.post('/settings/llm/test', requestBody)
      setTestResult(res.data)
    } catch (error) {
      setTestResult({ success: false, message: '测试失败: ' + error })
    } finally {
      setTesting(false)
    }
  }

  const handleTestEmbedding = async () => {
    setTestingEmbedding(true)
    setEmbeddingTestResult(null)
    try {
      const res = await api.post('/settings/embedding/test', {
        base_url: settings.embedding_base_url,
        model: settings.embedding_model
      })
      setEmbeddingTestResult(res.data)
    } catch (error) {
      setEmbeddingTestResult({ success: false, message: '测试失败: ' + error })
    } finally {
      setTestingEmbedding(false)
    }
  }

  const selectProvider = (provider: LLMProvider) => {
    setSettings({
      ...settings,
      openai_base_url: provider.base_url,
      llm_model: provider.default_model
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary-400" />
      </div>
    )
  }

  return (
    <div className="flex gap-6">
      {/* Main LLM Config */}
      <div className="flex-1 space-y-6">
        {/* Actions Bar */}
        <div className="flex items-center justify-end gap-3">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`px-3 py-2 rounded-lg flex items-center gap-2 text-sm transition-colors ${
              showHistory ? 'bg-primary-600/20 text-primary-400' : 'bg-dark-800 hover:bg-dark-700'
            }`}
          >
            <History size={16} />
            变更历史
          </button>
          <button
            onClick={handleTest}
            disabled={testing}
            className="px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg flex items-center gap-2 disabled:opacity-50 transition-colors text-sm"
          >
            {testing ? <Loader2 size={16} className="animate-spin" /> : <TestTube size={16} />}
            测试连接
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg flex items-center gap-2 disabled:opacity-50 transition-colors text-sm"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : saveSuccess ? <Check size={16} /> : null}
            {saving ? '保存中...' : saveSuccess ? '已保存' : '保存设置'}
          </button>
        </div>

        {/* Test Results */}
        {testResult && (
          <div className={`p-4 rounded-lg flex items-start gap-3 ${
            testResult.success ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'
          }`}>
            {testResult.success ? <Check className="text-green-400 mt-0.5" size={20} /> : <X className="text-red-400 mt-0.5" size={20} />}
            <div>
              <p className={testResult.success ? 'text-green-300' : 'text-red-300'}>{testResult.message}</p>
              {testResult.response && <p className="text-dark-400 mt-2 text-sm">AI 回复: {testResult.response}</p>}
            </div>
          </div>
        )}
        {embeddingTestResult && (
          <div className={`p-4 rounded-lg flex items-start gap-3 ${
            embeddingTestResult.success ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'
          }`}>
            {embeddingTestResult.success ? <Check className="text-green-400 mt-0.5" size={20} /> : <X className="text-red-400 mt-0.5" size={20} />}
            <p className={embeddingTestResult.success ? 'text-green-300' : 'text-red-300'}>{embeddingTestResult.message}</p>
          </div>
        )}

        {/* LLM Toggle */}
        <div className="bg-dark-900 rounded-lg p-6 border border-dark-800">
          <h2 className="text-lg font-semibold mb-4">LLM 功能</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-dark-300">启用 AI 智能助手</p>
              <p className="text-sm text-dark-500 mt-1">关闭后将使用规则匹配模式</p>
            </div>
            <button
              onClick={() => setSettings({ ...settings, enable_llm: !settings.enable_llm })}
              className={`relative w-14 h-7 rounded-full transition-colors ${settings.enable_llm ? 'bg-primary-600' : 'bg-dark-700'}`}
            >
              <span className={`absolute top-1 w-5 h-5 bg-white rounded-full transition-transform ${settings.enable_llm ? 'translate-x-7' : 'translate-x-1'}`} />
            </button>
          </div>
        </div>

        {/* Provider Quick Select */}
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

        {/* API Config */}
        <div className="bg-dark-900 rounded-lg p-6 border border-dark-800">
          <h2 className="text-lg font-semibold mb-4">API 配置</h2>
          <div className="space-y-4">
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
                {settings.has_env_key ? "已从环境变量读取 API Key，可在此处输入覆盖" : "密钥将保存在服务器端，或设置环境变量 OPENAI_API_KEY"}
              </p>
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-2">API Base URL</label>
              <input
                type="text"
                value={settings.openai_base_url}
                onChange={(e) => setSettings({ ...settings, openai_base_url: e.target.value })}
                className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-primary-500"
              />
            </div>
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

        {/* System Prompt */}
        <div className="bg-dark-900 rounded-lg p-6 border border-dark-800">
          <h2 className="text-lg font-semibold mb-4">系统提示词</h2>
          <textarea
            value={settings.system_prompt}
            onChange={(e) => setSettings({ ...settings, system_prompt: e.target.value })}
            rows={8}
            className="w-full bg-dark-950 border border-dark-700 rounded-lg px-4 py-3 focus:outline-none focus:border-primary-500 font-mono text-sm"
            placeholder="输入系统提示词..."
          />
          <p className="text-xs text-dark-500 mt-2">修改提示词可以调整 AI 的行为和回复风格</p>
        </div>

        {/* Embedding Config */}
        <div className="bg-dark-900 rounded-lg p-6 border border-dark-800">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">语义搜索配置 (Embedding)</h2>
            <button
              onClick={handleTestEmbedding}
              disabled={testingEmbedding || !settings.embedding_enabled}
              className="px-3 py-1.5 bg-dark-800 hover:bg-dark-700 rounded-lg flex items-center gap-2 disabled:opacity-50 transition-colors text-sm"
            >
              {testingEmbedding ? <Loader2 size={14} className="animate-spin" /> : <TestTube size={14} />}
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
              className={`relative w-14 h-7 rounded-full transition-colors ${settings.embedding_enabled ? 'bg-primary-600' : 'bg-dark-700'}`}
            >
              <span className={`absolute top-1 w-5 h-5 bg-white rounded-full transition-transform ${settings.embedding_enabled ? 'translate-x-7' : 'translate-x-1'}`} />
            </button>
          </div>
          <div className="space-y-4">
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
                <option value="text-embedding-3-small" />
                <option value="text-embedding-ada-002" />
              </datalist>
              <p className="text-xs text-dark-500 mt-1">推荐使用 nomic-embed-text (本地 Ollama)</p>
            </div>
          </div>
        </div>
      </div>

      {/* History Sidebar */}
      {showHistory && <HistorySidebar />}
    </div>
  )
}

// ========== History Sidebar ==========

function HistorySidebar() {
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedVersion, setExpandedVersion] = useState<number | null>(null)
  const [detail, setDetail] = useState<HistoryDetail | null>(null)
  const [rolling, setRolling] = useState(false)

  useEffect(() => { loadHistory() }, [])

  const loadHistory = async () => {
    setLoading(true)
    try {
      const res = await api.get('/settings/llm/history')
      setHistory(res.data)
    } catch (err) {
      console.error('Failed to load history:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadDetail = async (version: number) => {
    if (expandedVersion === version) {
      setExpandedVersion(null)
      setDetail(null)
      return
    }
    try {
      const res = await api.get(`/settings/llm/history/${version}`)
      setDetail(res.data)
      setExpandedVersion(version)
    } catch (err) {
      console.error('Failed to load version detail:', err)
    }
  }

  const rollback = async (version: number) => {
    if (!confirm(`确定回滚到版本 ${version}？当前配置将被覆盖。`)) return
    setRolling(true)
    try {
      await api.post(`/settings/llm/rollback/${version}`)
      alert(`已回滚到版本 ${version}，刷新页面查看最新配置`)
      window.location.reload()
    } catch (err: any) {
      alert(err.response?.data?.detail || '回滚失败')
    } finally {
      setRolling(false)
    }
  }

  const formatDiff = (oldVal: any, newVal: any) => {
    const changes: { key: string; from: string; to: string }[] = []
    const allKeys = new Set([...Object.keys(oldVal || {}), ...Object.keys(newVal || {})])
    for (const key of allKeys) {
      const o = JSON.stringify(oldVal?.[key])
      const n = JSON.stringify(newVal?.[key])
      if (o !== n) {
        changes.push({ key, from: String(oldVal?.[key] ?? ''), to: String(newVal?.[key] ?? '') })
      }
    }
    return changes
  }

  return (
    <div className="w-80 flex-shrink-0">
      <div className="bg-dark-900 border border-dark-800 rounded-lg p-4 sticky top-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium flex items-center gap-2">
            <History size={16} className="text-primary-400" />
            变更历史
          </h3>
          <button onClick={loadHistory} className="p-1 hover:bg-dark-700 rounded">
            <RefreshCw size={14} className="text-dark-400" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-20">
            <Loader2 size={16} className="animate-spin text-dark-400" />
          </div>
        ) : history.length === 0 ? (
          <p className="text-sm text-dark-500 text-center py-4">暂无变更记录</p>
        ) : (
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {history.map(item => (
              <div key={item.id} className="border border-dark-800 rounded-lg overflow-hidden">
                <div
                  className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-dark-800/50"
                  onClick={() => loadDetail(item.version)}
                >
                  <div className="flex items-center gap-2">
                    {expandedVersion === item.version
                      ? <ChevronDown size={12} className="text-dark-400" />
                      : <ChevronRight size={12} className="text-dark-400" />
                    }
                    <span className="text-xs font-mono">v{item.version}</span>
                    {item.is_current && <span className="text-xs px-1 py-0.5 bg-emerald-500/20 text-emerald-400 rounded">当前</span>}
                  </div>
                  <span className="text-xs text-dark-500">
                    {new Date(item.changed_at).toLocaleDateString('zh-CN')}
                  </span>
                </div>

                {expandedVersion === item.version && detail && (
                  <div className="px-3 pb-3 border-t border-dark-800">
                    <div className="text-xs text-dark-500 mt-2 mb-2">
                      {detail.changer_name || `用户#${detail.changed_by}`} · {new Date(detail.changed_at).toLocaleString('zh-CN')}
                    </div>
                    {detail.change_reason && (
                      <div className="text-xs text-dark-400 mb-2">原因: {detail.change_reason}</div>
                    )}

                    {/* Diff */}
                    <div className="space-y-1">
                      {formatDiff(detail.old_value, detail.new_value).map(change => (
                        <div key={change.key} className="text-xs">
                          <span className="text-dark-400">{change.key}:</span>
                          <div className="ml-2">
                            <div className="text-red-400/70 line-through truncate">{change.from}</div>
                            <div className="text-emerald-400 truncate">{change.to}</div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {!item.is_current && (
                      <button
                        onClick={() => rollback(item.version)}
                        disabled={rolling}
                        className="mt-2 w-full px-2 py-1 text-xs bg-dark-800 hover:bg-dark-700 rounded flex items-center justify-center gap-1 disabled:opacity-50"
                      >
                        <RotateCcw size={12} />
                        回滚到此版本
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ========== Config Group Tab (sys_config CRUD) ==========

function ConfigGroupTab({ group }: { group: string }) {
  const [configs, setConfigs] = useState<ConfigItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<ConfigItem | null>(null)
  const [form, setForm] = useState({ key: '', value: '', value_type: 'string', name: '', description: '', is_public: false })

  useEffect(() => { loadConfigs() }, [group])

  const loadConfigs = async () => {
    setLoading(true)
    try {
      const res = await api.get('/system/configs', { params: { group } })
      setConfigs(res.data)
    } catch (err) {
      console.error('Failed to load configs:', err)
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    setEditing(null)
    setForm({ key: '', value: '', value_type: 'string', name: '', description: '', is_public: false })
    setShowForm(true)
  }

  const openEdit = (item: ConfigItem) => {
    setEditing(item)
    setForm({ key: item.key, value: item.value, value_type: item.value_type, name: item.name, description: item.description, is_public: item.is_public })
    setShowForm(true)
  }

  const save = async () => {
    try {
      if (editing) {
        await api.put(`/system/configs/${editing.id}`, { value: form.value, name: form.name, description: form.description, is_public: form.is_public })
      } else {
        await api.post('/system/configs', { ...form, group })
      }
      setShowForm(false)
      await loadConfigs()
    } catch (err: any) {
      alert(err.response?.data?.detail || '操作失败')
    }
  }

  const deleteConfig = async (item: ConfigItem) => {
    if (item.is_system) { alert('系统内置配置不可删除'); return }
    if (!confirm(`确定删除配置 "${item.name}"？`)) return
    try {
      await api.delete(`/system/configs/${item.id}`)
      await loadConfigs()
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  const GROUP_DESC: Record<string, string> = {
    system: '系统基础参数，如应用名称、版本号等',
    security: '安全相关策略配置，如密码规则、登录锁定等',
    business: '业务逻辑参数，如默认退房时间、价格规则等',
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-dark-400">{GROUP_DESC[group] || ''}</p>
        <div className="flex gap-3">
          <button onClick={loadConfigs} className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg text-sm">
            <RefreshCw size={16} /> 刷新
          </button>
          <button onClick={openCreate} className="flex items-center gap-2 px-3 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-sm">
            <Plus size={16} /> 新增配置
          </button>
        </div>
      </div>

      <div className="bg-dark-900 rounded-xl border border-dark-800">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 size={20} className="animate-spin text-dark-400" />
          </div>
        ) : configs.length === 0 ? (
          <div className="p-8 text-center text-dark-500 text-sm">该分组暂无配置项，点击"新增配置"添加</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-left text-dark-400 text-sm border-b border-dark-800">
                <th className="px-4 py-3">名称</th>
                <th className="px-4 py-3">键</th>
                <th className="px-4 py-3">值</th>
                <th className="px-4 py-3">类型</th>
                <th className="px-4 py-3">标记</th>
                <th className="px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {configs.map(item => (
                <tr key={item.id} className="border-b border-dark-800/50 hover:bg-dark-800/30">
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium">{item.name}</div>
                    {item.description && <div className="text-xs text-dark-500 mt-0.5">{item.description}</div>}
                  </td>
                  <td className="px-4 py-3 text-sm font-mono text-dark-300">{item.key}</td>
                  <td className="px-4 py-3 text-sm font-mono">{item.value}</td>
                  <td className="px-4 py-3 text-sm text-dark-400">{item.value_type}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      {item.is_system && <span className="px-1.5 py-0.5 text-xs bg-dark-700 text-dark-400 rounded">内置</span>}
                      {item.is_public && <span className="px-1.5 py-0.5 text-xs bg-emerald-500/20 text-emerald-400 rounded">公开</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <button onClick={() => openEdit(item)} className="p-1 hover:bg-dark-700 rounded">
                        <Pencil size={14} className="text-dark-400" />
                      </button>
                      {!item.is_system && (
                        <button onClick={() => deleteConfig(item)} className="p-1 hover:bg-dark-700 rounded">
                          <Trash2 size={14} className="text-red-400" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-dark-900 rounded-xl border border-dark-800 w-[500px] p-6">
            <h3 className="text-lg font-medium mb-4">{editing ? '编辑配置' : '新增配置'}</h3>
            <div className="space-y-4">
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm text-dark-400 mb-1">键</label>
                  <input
                    value={form.key}
                    onChange={e => setForm(f => ({ ...f, key: e.target.value }))}
                    disabled={!!editing}
                    placeholder={`如: ${group}.example_key`}
                    className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm disabled:opacity-50"
                  />
                </div>
                <div className="flex-1">
                  <label className="block text-sm text-dark-400 mb-1">值类型</label>
                  <select
                    value={form.value_type}
                    onChange={e => setForm(f => ({ ...f, value_type: e.target.value }))}
                    className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="string">字符串</option>
                    <option value="number">数字</option>
                    <option value="boolean">布尔</option>
                    <option value="json">JSON</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">名称</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="配置项显示名称"
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">值</label>
                <input
                  value={form.value}
                  onChange={e => setForm(f => ({ ...f, value: e.target.value }))}
                  placeholder="配置值"
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">描述</label>
                <input
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="可选"
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.is_public}
                  onChange={e => setForm(f => ({ ...f, is_public: e.target.checked }))}
                  className="rounded"
                />
                公开配置（无需登录即可获取）
              </label>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg text-sm">取消</button>
              <button onClick={save} className="px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-sm">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
