import { useEffect, useState } from 'react'
import { Clock, Plus, Pencil, Trash2, RefreshCw, Play, Square, Zap, FileText, X } from 'lucide-react'
import axios from 'axios'

const api = axios.create({ baseURL: '/api', headers: { 'Content-Type': 'application/json' } })
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

interface Job {
  id: number
  name: string
  code: string
  group: string
  invoke_target: string
  cron_expression: string
  misfire_policy: string
  is_concurrent: boolean
  is_active: boolean
  description: string | null
  created_at: string | null
  updated_at: string | null
}

interface JobLog {
  id: number
  job_id: number
  status: string
  start_time: string
  end_time: string | null
  duration_ms: number | null
  result: string | null
  created_at: string | null
}

interface JobForm {
  name: string
  code: string
  invoke_target: string
  cron_expression: string
  group: string
  misfire_policy: string
  is_concurrent: boolean
  is_active: boolean
  description: string
}

const emptyForm: JobForm = {
  name: '', code: '', invoke_target: '', cron_expression: '',
  group: 'default', misfire_policy: 'ignore', is_concurrent: false,
  is_active: true, description: '',
}

const schedulerApi = {
  list: async (group?: string, isActive?: boolean): Promise<Job[]> => {
    const params: Record<string, unknown> = {}
    if (group) params.group = group
    if (isActive !== undefined) params.is_active = isActive
    const res = await api.get('/system/schedulers', { params })
    return res.data
  },
  create: async (data: JobForm): Promise<Job> => {
    const res = await api.post('/system/schedulers', data)
    return res.data
  },
  update: async (id: number, data: Partial<JobForm>): Promise<Job> => {
    const res = await api.put(`/system/schedulers/${id}`, data)
    return res.data
  },
  delete: async (id: number): Promise<void> => {
    await api.delete(`/system/schedulers/${id}`)
  },
  start: async (id: number): Promise<Job> => {
    const res = await api.post(`/system/schedulers/${id}/start`)
    return res.data
  },
  stop: async (id: number): Promise<Job> => {
    const res = await api.post(`/system/schedulers/${id}/stop`)
    return res.data
  },
  trigger: async (id: number): Promise<{ success: boolean; status: string; duration_ms: number; result: string }> => {
    const res = await api.post(`/system/schedulers/${id}/trigger`)
    return res.data
  },
  getLogs: async (jobId: number, limit?: number): Promise<JobLog[]> => {
    const res = await api.get(`/system/schedulers/${jobId}/logs`, { params: { limit: limit || 50 } })
    return res.data
  },
}

export default function SchedulerManagement() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Job | null>(null)
  const [form, setForm] = useState<JobForm>(emptyForm)
  const [logs, setLogs] = useState<JobLog[]>([])
  const [logJob, setLogJob] = useState<Job | null>(null)
  const [triggering, setTriggering] = useState<number | null>(null)

  const loadJobs = async () => {
    setLoading(true)
    try {
      const data = await schedulerApi.list()
      setJobs(data)
    } catch (err) {
      console.error('Failed to load jobs:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadJobs() }, [])

  const handleCreate = () => {
    setEditing(null)
    setForm(emptyForm)
    setShowForm(true)
  }

  const handleEdit = (job: Job) => {
    setEditing(job)
    setForm({
      name: job.name,
      code: job.code,
      invoke_target: job.invoke_target,
      cron_expression: job.cron_expression,
      group: job.group,
      misfire_policy: job.misfire_policy,
      is_concurrent: job.is_concurrent,
      is_active: job.is_active,
      description: job.description || '',
    })
    setShowForm(true)
  }

  const handleSave = async () => {
    try {
      if (editing) {
        const { code, ...updateData } = form
        await schedulerApi.update(editing.id, updateData)
      } else {
        await schedulerApi.create(form)
      }
      setShowForm(false)
      await loadJobs()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '操作失败'
      alert(msg)
    }
  }

  const handleDelete = async (job: Job) => {
    if (!confirm(`确定删除任务 "${job.name}"？`)) return
    try {
      await schedulerApi.delete(job.id)
      await loadJobs()
    } catch (err) {
      console.error('Delete failed:', err)
    }
  }

  const handleToggle = async (job: Job) => {
    try {
      if (job.is_active) {
        await schedulerApi.stop(job.id)
      } else {
        await schedulerApi.start(job.id)
      }
      await loadJobs()
    } catch (err) {
      console.error('Toggle failed:', err)
    }
  }

  const handleTrigger = async (job: Job) => {
    setTriggering(job.id)
    try {
      const result = await schedulerApi.trigger(job.id)
      alert(result.success ? `执行成功 (${result.duration_ms}ms)` : `执行失败: ${result.result}`)
      await loadJobs()
    } catch (err) {
      console.error('Trigger failed:', err)
    } finally {
      setTriggering(null)
    }
  }

  const handleViewLogs = async (job: Job) => {
    setLogJob(job)
    try {
      const data = await schedulerApi.getLogs(job.id)
      setLogs(data)
    } catch (err) {
      console.error('Failed to load logs:', err)
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Clock size={24} className="text-primary-400" />
          <h1 className="text-2xl font-bold">定时任务</h1>
          <span className="text-sm text-dark-500">{jobs.length} 个任务</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={loadJobs} className="p-2 hover:bg-dark-800 rounded" title="刷新">
            <RefreshCw size={16} className={loading ? 'animate-spin text-primary-400' : 'text-dark-400'} />
          </button>
          <button onClick={handleCreate} className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-500 hover:bg-primary-600 text-white rounded text-sm">
            <Plus size={14} /> 新建任务
          </button>
        </div>
      </div>

      {/* Job List */}
      <div className="border border-dark-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-dark-900/50">
            <tr>
              <th className="text-left px-4 py-3 text-dark-400 font-medium">任务名称</th>
              <th className="text-left px-4 py-3 text-dark-400 font-medium">编码</th>
              <th className="text-left px-4 py-3 text-dark-400 font-medium">Cron</th>
              <th className="text-left px-4 py-3 text-dark-400 font-medium">分组</th>
              <th className="text-center px-4 py-3 text-dark-400 font-medium">状态</th>
              <th className="text-right px-4 py-3 text-dark-400 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map(job => (
              <tr key={job.id} className="border-t border-dark-800 hover:bg-dark-900/30">
                <td className="px-4 py-3">
                  <div>
                    <span className="text-dark-100">{job.name}</span>
                    {job.description && (
                      <p className="text-xs text-dark-500 mt-0.5">{job.description}</p>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-dark-400">{job.code}</td>
                <td className="px-4 py-3 font-mono text-xs text-amber-400">{job.cron_expression}</td>
                <td className="px-4 py-3 text-dark-400">{job.group}</td>
                <td className="px-4 py-3 text-center">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    job.is_active
                      ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                      : 'bg-dark-800 text-dark-500 border border-dark-700'
                  }`}>
                    {job.is_active ? '运行中' : '已停止'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => handleToggle(job)}
                      className="p-1.5 hover:bg-dark-800 rounded"
                      title={job.is_active ? '停止' : '启动'}
                    >
                      {job.is_active
                        ? <Square size={14} className="text-red-400" />
                        : <Play size={14} className="text-green-400" />}
                    </button>
                    <button
                      onClick={() => handleTrigger(job)}
                      className="p-1.5 hover:bg-dark-800 rounded"
                      title="立即执行"
                      disabled={triggering === job.id}
                    >
                      <Zap size={14} className={triggering === job.id ? 'text-amber-400 animate-pulse' : 'text-amber-400'} />
                    </button>
                    <button
                      onClick={() => handleViewLogs(job)}
                      className="p-1.5 hover:bg-dark-800 rounded"
                      title="执行日志"
                    >
                      <FileText size={14} className="text-dark-400" />
                    </button>
                    <button
                      onClick={() => handleEdit(job)}
                      className="p-1.5 hover:bg-dark-800 rounded"
                      title="编辑"
                    >
                      <Pencil size={14} className="text-dark-400" />
                    </button>
                    <button
                      onClick={() => handleDelete(job)}
                      className="p-1.5 hover:bg-dark-800 rounded"
                      title="删除"
                    >
                      <Trash2 size={14} className="text-red-400" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-dark-500">
                  暂无定时任务
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create/Edit Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-dark-900 border border-dark-700 rounded-lg w-full max-w-lg p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold">{editing ? '编辑任务' : '新建任务'}</h2>
              <button onClick={() => setShowForm(false)} className="p-1 hover:bg-dark-800 rounded">
                <X size={16} className="text-dark-400" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-dark-400 mb-1">任务名称 *</label>
                  <input
                    value={form.name}
                    onChange={e => setForm({ ...form, name: e.target.value })}
                    className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-sm"
                    placeholder="清理过期消息"
                  />
                </div>
                <div>
                  <label className="block text-xs text-dark-400 mb-1">编码 *{editing && ' (不可修改)'}</label>
                  <input
                    value={form.code}
                    onChange={e => setForm({ ...form, code: e.target.value })}
                    className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-sm"
                    placeholder="sys_clean_messages"
                    disabled={!!editing}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs text-dark-400 mb-1">执行目标 *</label>
                <input
                  value={form.invoke_target}
                  onChange={e => setForm({ ...form, invoke_target: e.target.value })}
                  className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-sm font-mono"
                  placeholder="app.system.tasks:clean_expired_messages"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-dark-400 mb-1">Cron 表达式 *</label>
                  <input
                    value={form.cron_expression}
                    onChange={e => setForm({ ...form, cron_expression: e.target.value })}
                    className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-sm font-mono"
                    placeholder="0 2 * * *"
                  />
                </div>
                <div>
                  <label className="block text-xs text-dark-400 mb-1">分组</label>
                  <input
                    value={form.group}
                    onChange={e => setForm({ ...form, group: e.target.value })}
                    className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-sm"
                    placeholder="default"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-dark-400 mb-1">Misfire 策略</label>
                  <select
                    value={form.misfire_policy}
                    onChange={e => setForm({ ...form, misfire_policy: e.target.value })}
                    className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-sm"
                  >
                    <option value="ignore">忽略</option>
                    <option value="fire_once">补偿执行一次</option>
                  </select>
                </div>
                <div className="flex items-end gap-4 pb-2">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.is_concurrent}
                      onChange={e => setForm({ ...form, is_concurrent: e.target.checked })}
                      className="rounded"
                    />
                    允许并发
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.is_active}
                      onChange={e => setForm({ ...form, is_active: e.target.checked })}
                      className="rounded"
                    />
                    启用
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-xs text-dark-400 mb-1">描述</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm({ ...form, description: e.target.value })}
                  className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-sm"
                  rows={2}
                  placeholder="任务说明..."
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-dark-400 hover:text-dark-200">
                取消
              </button>
              <button onClick={handleSave} className="px-4 py-2 text-sm bg-primary-500 hover:bg-primary-600 text-white rounded">
                {editing ? '保存' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Logs Modal */}
      {logJob && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-dark-900 border border-dark-700 rounded-lg w-full max-w-2xl p-6 space-y-4 max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold">执行日志 — {logJob.name}</h2>
              <button onClick={() => setLogJob(null)} className="p-1 hover:bg-dark-800 rounded">
                <X size={16} className="text-dark-400" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-dark-900/50 sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-2 text-dark-400 font-medium">状态</th>
                    <th className="text-left px-3 py-2 text-dark-400 font-medium">开始时间</th>
                    <th className="text-right px-3 py-2 text-dark-400 font-medium">耗时</th>
                    <th className="text-left px-3 py-2 text-dark-400 font-medium">结果</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <tr key={log.id} className="border-t border-dark-800">
                      <td className="px-3 py-2">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          log.status === 'success'
                            ? 'bg-green-500/10 text-green-400'
                            : 'bg-red-500/10 text-red-400'
                        }`}>
                          {log.status === 'success' ? '成功' : '失败'}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-dark-400 text-xs">
                        {log.start_time ? new Date(log.start_time).toLocaleString() : '-'}
                      </td>
                      <td className="px-3 py-2 text-right text-dark-400">
                        {log.duration_ms != null ? `${log.duration_ms}ms` : '-'}
                      </td>
                      <td className="px-3 py-2 text-dark-400 text-xs max-w-xs truncate" title={log.result || ''}>
                        {log.result || '-'}
                      </td>
                    </tr>
                  ))}
                  {logs.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-3 py-8 text-center text-dark-500">
                        暂无执行记录
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
