import { useEffect, useState } from 'react'
import { Settings, Plus, Pencil, Trash2, RefreshCw, Eye, EyeOff } from 'lucide-react'

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
  created_at: string | null
  updated_at: string | null
  updated_by: number | null
}

import axios from 'axios'

const api = axios.create({ baseURL: '/api', headers: { 'Content-Type': 'application/json' } })
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

const configApi = {
  getAll: async (group?: string): Promise<ConfigItem[]> => {
    const res = await api.get('/system/configs', { params: group ? { group } : {} })
    return res.data
  },
  getGroups: async (): Promise<string[]> => {
    const res = await api.get('/system/configs/groups')
    return res.data
  },
  create: async (data: Partial<ConfigItem>): Promise<ConfigItem> => {
    const res = await api.post('/system/configs', data)
    return res.data
  },
  update: async (id: number, data: Partial<ConfigItem>): Promise<ConfigItem> => {
    const res = await api.put(`/system/configs/${id}`, data)
    return res.data
  },
  delete: async (id: number): Promise<void> => {
    await api.delete(`/system/configs/${id}`)
  },
}

const GROUP_LABELS: Record<string, string> = {
  system: '系统基础',
  llm: 'LLM 配置',
  security: '安全策略',
  business: '业务参数',
}

export default function ConfigManagement() {
  const [configs, setConfigs] = useState<ConfigItem[]>([])
  const [groups, setGroups] = useState<string[]>([])
  const [activeGroup, setActiveGroup] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<ConfigItem | null>(null)
  const [form, setForm] = useState({ group: 'system', key: '', value: '', value_type: 'string', name: '', description: '', is_public: false })
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set())

  useEffect(() => { loadData() }, [])
  useEffect(() => { loadConfigs() }, [activeGroup])

  const loadData = async () => {
    try {
      const g = await configApi.getGroups()
      setGroups(g)
      if (g.length > 0) setActiveGroup(g[0])
    } catch (err) {
      console.error('Failed to load groups:', err)
    }
  }

  const loadConfigs = async () => {
    if (!activeGroup) return
    try {
      setLoading(true)
      const data = await configApi.getAll(activeGroup)
      setConfigs(data)
    } catch (err) {
      console.error('Failed to load configs:', err)
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    setEditing(null)
    setForm({ group: activeGroup || 'system', key: '', value: '', value_type: 'string', name: '', description: '', is_public: false })
    setShowForm(true)
  }

  const openEdit = (item: ConfigItem) => {
    setEditing(item)
    setForm({ group: item.group, key: item.key, value: item.value, value_type: item.value_type, name: item.name, description: item.description, is_public: item.is_public })
    setShowForm(true)
  }

  const save = async () => {
    try {
      if (editing) {
        await configApi.update(editing.id, { value: form.value, name: form.name, description: form.description, is_public: form.is_public })
      } else {
        await configApi.create(form)
      }
      setShowForm(false)
      await loadConfigs()
      await loadData()
    } catch (err: any) {
      alert(err.response?.data?.detail || '操作失败')
    }
  }

  const deleteConfig = async (item: ConfigItem) => {
    if (item.is_system) { alert('系统内置配置不可删除'); return }
    if (!confirm(`确定删除配置 "${item.name}"？`)) return
    try {
      await configApi.delete(item.id)
      await loadConfigs()
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  const isSensitive = (key: string) => /api_key|secret|password|token|credential/i.test(key)

  const toggleReveal = (key: string) => {
    setRevealedKeys(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings size={24} className="text-primary-400" />
          <h1 className="text-2xl font-bold">系统配置</h1>
        </div>
        <div className="flex gap-3">
          <button onClick={loadConfigs} className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg text-sm">
            <RefreshCw size={16} /> 刷新
          </button>
          <button onClick={openCreate} className="flex items-center gap-2 px-3 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-sm">
            <Plus size={16} /> 新增配置
          </button>
        </div>
      </div>

      {/* Group tabs */}
      <div className="flex gap-2">
        {groups.map(g => (
          <button
            key={g}
            onClick={() => setActiveGroup(g)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              activeGroup === g ? 'bg-primary-600 text-white' : 'bg-dark-800 hover:bg-dark-700 text-dark-300'
            }`}
          >
            {GROUP_LABELS[g] || g}
          </button>
        ))}
      </div>

      {/* Config table */}
      <div className="bg-dark-900 rounded-xl border border-dark-800">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-500" />
          </div>
        ) : configs.length === 0 ? (
          <div className="p-8 text-center text-dark-500 text-sm">该分组暂无配置项</div>
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
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono">
                        {isSensitive(item.key) && !revealedKeys.has(item.key)
                          ? item.value
                          : item.value}
                      </span>
                      {isSensitive(item.key) && (
                        <button onClick={() => toggleReveal(item.key)} className="p-0.5 hover:bg-dark-700 rounded">
                          {revealedKeys.has(item.key) ? <EyeOff size={14} className="text-dark-400" /> : <Eye size={14} className="text-dark-400" />}
                        </button>
                      )}
                    </div>
                  </td>
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
                  <label className="block text-sm text-dark-400 mb-1">分组</label>
                  <select
                    value={form.group}
                    onChange={e => setForm(f => ({ ...f, group: e.target.value }))}
                    disabled={!!editing}
                    className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm disabled:opacity-50"
                  >
                    <option value="system">系统基础</option>
                    <option value="llm">LLM 配置</option>
                    <option value="security">安全策略</option>
                    <option value="business">业务参数</option>
                  </select>
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
                <label className="block text-sm text-dark-400 mb-1">键</label>
                <input
                  value={form.key}
                  onChange={e => setForm(f => ({ ...f, key: e.target.value }))}
                  disabled={!!editing}
                  placeholder="如: llm.api_key"
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">名称</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="如: LLM API Key"
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
