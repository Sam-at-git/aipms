import { useEffect, useState } from 'react'
import { RefreshCw, FileText, Filter, Search, Download, Minus, Plus, Equal } from 'lucide-react'
import { auditApi } from '../services/api'
import type { AuditLog, ActionSummary } from '../types'

// A-2: Trend chart data type
interface TrendPoint {
  day: string
  count: number
}

// A-3: Diff viewer for old_value vs new_value
function ValueDiff({ oldValue, newValue }: { oldValue: string | null; newValue: string | null }) {
  // Try to parse both as JSON for field-level diff
  let oldObj: Record<string, unknown> | null = null
  let newObj: Record<string, unknown> | null = null
  try { if (oldValue) oldObj = JSON.parse(oldValue) } catch {}
  try { if (newValue) newObj = JSON.parse(newValue) } catch {}

  // If both are valid JSON objects, do field-level diff
  if (oldObj && typeof oldObj === 'object' && !Array.isArray(oldObj) &&
      newObj && typeof newObj === 'object' && !Array.isArray(newObj)) {
    const allKeys = [...new Set([...Object.keys(oldObj), ...Object.keys(newObj)])]

    return (
      <div className="space-y-0.5 font-mono text-xs">
        {allKeys.map(key => {
          const ov = oldObj![key]
          const nv = newObj![key]
          const ovStr = JSON.stringify(ov)
          const nvStr = JSON.stringify(nv)

          if (ovStr === nvStr) {
            return (
              <div key={key} className="flex items-start gap-2 text-dark-500 px-1">
                <Equal size={12} className="mt-0.5 flex-shrink-0" />
                <span className="text-sky-400/50">{key}</span>
                <span>: {ovStr}</span>
              </div>
            )
          }

          return (
            <div key={key} className="space-y-0.5">
              {ov !== undefined && (
                <div className="flex items-start gap-2 text-red-400/80 bg-red-500/5 px-1 rounded">
                  <Minus size={12} className="mt-0.5 flex-shrink-0" />
                  <span className="text-sky-400">{key}</span>
                  <span>: {ovStr}</span>
                </div>
              )}
              {nv !== undefined && (
                <div className="flex items-start gap-2 text-green-400/80 bg-green-500/5 px-1 rounded">
                  <Plus size={12} className="mt-0.5 flex-shrink-0" />
                  <span className="text-sky-400">{key}</span>
                  <span>: {nvStr}</span>
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  // Fallback: show old and new as plain text
  return (
    <div className="space-y-3">
      {oldValue && (
        <div>
          <label className="text-xs text-dark-400">旧值</label>
          <pre className="bg-dark-950 rounded-lg p-3 text-xs text-dark-300 overflow-x-auto mt-1">
            {oldValue}
          </pre>
        </div>
      )}
      {newValue && (
        <div>
          <label className="text-xs text-dark-400">新值</label>
          <pre className="bg-dark-950 rounded-lg p-3 text-xs text-dark-300 overflow-x-auto mt-1">
            {newValue}
          </pre>
        </div>
      )}
    </div>
  )
}

// A-2: CSS bar chart for daily trend
function TrendChart({ data }: { data: TrendPoint[] }) {
  if (data.length === 0) return <div className="text-dark-500 text-sm text-center py-4">No data</div>

  const maxCount = Math.max(...data.map(d => d.count), 1)

  return (
    <div>
      <div className="flex items-end gap-0.5" style={{ height: 100 }}>
        {data.map(d => {
          const h = (d.count / maxCount) * 80
          return (
            <div key={d.day} className="flex-1 flex flex-col items-center" title={`${d.day}: ${d.count} operations`}>
              <div
                className="w-full max-w-[16px] bg-primary-500/70 rounded-t"
                style={{ height: Math.max(h, 2) }}
              />
              {/* Show label every few bars to avoid overcrowding */}
            </div>
          )
        })}
      </div>
      <div className="flex justify-between text-[10px] text-dark-500 mt-1">
        <span>{data[0]?.day.slice(5)}</span>
        <span>{data[data.length - 1]?.day.slice(5)}</span>
      </div>
      <div className="text-xs text-dark-400 mt-1">
        Total: <span className="text-white font-medium">{data.reduce((s, d) => s + d.count, 0)}</span> operations
      </div>
    </div>
  )
}

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [summary, setSummary] = useState<ActionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null)
  const [trend, setTrend] = useState<TrendPoint[]>([])

  // 筛选条件
  const [filters, setFilters] = useState({
    action: '',
    entity_type: '',
    start_date: '',
    end_date: ''
  })

  useEffect(() => {
    loadData()
    loadSummary()
    loadTrend()
  }, [])

  const loadData = async (filterParams?: typeof filters) => {
    setLoading(true)
    try {
      const params = filterParams || filters
      // 移除空值
      const cleanParams = Object.fromEntries(
        Object.entries(params).filter(([_, v]) => v !== '')
      )
      const data = await auditApi.getLogs(cleanParams)
      setLogs(data)
    } catch (err) {
      console.error('Failed to load logs:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadSummary = async () => {
    try {
      const data = await auditApi.getSummary(30)
      setSummary(data)
    } catch (err) {
      console.error('Failed to load summary:', err)
    }
  }

  const loadTrend = async () => {
    try {
      const data = await auditApi.getTrend(30)
      setTrend(data.data)
    } catch (err) {
      console.error('Failed to load trend:', err)
    }
  }

  const handleFilter = () => {
    loadData(filters)
  }

  const handleReset = () => {
    const resetFilters = {
      action: '',
      entity_type: '',
      start_date: '',
      end_date: ''
    }
    setFilters(resetFilters)
    loadData(resetFilters)
  }

  // A-1: Export
  const handleExport = async (format: 'json' | 'csv') => {
    try {
      await auditApi.exportLogs({ ...filters, format })
    } catch (err) {
      console.error('Export failed:', err)
    }
  }

  const getActionColor = (action: string) => {
    const actionColors: Record<string, string> = {
      'create': 'text-emerald-400',
      'update': 'text-amber-400',
      'delete': 'text-red-400',
      'login': 'text-blue-400',
      'logout': 'text-dark-400',
      'checkin': 'text-emerald-400',
      'checkout': 'text-purple-400',
      'cancel': 'text-red-400',
      'complete': 'text-green-400'
    }
    return actionColors[action] || 'text-dark-400'
  }

  const getActionLabel = (action: string) => {
    const labels: Record<string, string> = {
      'create': '创建',
      'update': '更新',
      'delete': '删除',
      'login': '登录',
      'logout': '登出',
      'checkin': '入住',
      'checkout': '退房',
      'cancel': '取消',
      'complete': '完成',
      'assign': '分配',
      'start': '开始',
      'payment': '支付',
      'adjust': '调整'
    }
    return labels[action] || action
  }

  const getEntityTypeLabel = (entityType: string | null) => {
    if (!entityType) return '-'
    const labels: Record<string, string> = {
      'Reservation': '预订',
      'StayRecord': '住宿记录',
      'Guest': '客人',
      'Room': '房间',
      'Task': '任务',
      'Bill': '账单',
      'Employee': '员工',
      'RatePlan': '价格策略'
    }
    return labels[entityType] || entityType
  }

  const formatValue = (value: string | null) => {
    if (!value) return '-'
    if (value.length > 50) {
      return value.substring(0, 50) + '...'
    }
    return value
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">审计日志</h1>
        <div className="flex gap-2">
          {/* A-1: Export buttons */}
          <button
            onClick={() => handleExport('json')}
            className="flex items-center gap-1 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors text-sm"
          >
            <Download size={14} />
            JSON
          </button>
          <button
            onClick={() => handleExport('csv')}
            className="flex items-center gap-1 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors text-sm"
          >
            <Download size={14} />
            CSV
          </button>
          <button
            onClick={() => { loadData(); loadSummary(); loadTrend() }}
            className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
        </div>
      </div>

      {/* 统计摘要 + 趋势图 */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 bg-dark-900 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">最近30天操作统计</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {summary.slice(0, 12).map((item, idx) => (
              <div key={idx} className="bg-dark-800 rounded-lg p-3">
                <div className="text-xs text-dark-400 mb-1">
                  {getActionLabel(item.action)} {getEntityTypeLabel(item.entity_type)}
                </div>
                <div className="text-xl font-bold text-primary-400">{item.count}</div>
              </div>
            ))}
          </div>
        </div>

        {/* A-2: Trend chart */}
        <div className="bg-dark-900 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">日操作量趋势</h2>
          <TrendChart data={trend} />
        </div>
      </div>

      {/* 筛选器 */}
      <div className="bg-dark-900 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={18} className="text-dark-400" />
          <span className="text-sm font-medium">筛选条件</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div>
            <select
              value={filters.action}
              onChange={(e) => setFilters({ ...filters, action: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
            >
              <option value="">全部操作</option>
              <option value="create">创建</option>
              <option value="update">更新</option>
              <option value="delete">删除</option>
              <option value="login">登录</option>
              <option value="checkin">入住</option>
              <option value="checkout">退房</option>
              <option value="cancel">取消</option>
            </select>
          </div>
          <div>
            <select
              value={filters.entity_type}
              onChange={(e) => setFilters({ ...filters, entity_type: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
            >
              <option value="">全部实体</option>
              <option value="Reservation">预订</option>
              <option value="StayRecord">住宿记录</option>
              <option value="Guest">客人</option>
              <option value="Room">房间</option>
              <option value="Task">任务</option>
              <option value="Bill">账单</option>
              <option value="Employee">员工</option>
            </select>
          </div>
          <div>
            <input
              type="date"
              value={filters.start_date}
              onChange={(e) => setFilters({ ...filters, start_date: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
            />
          </div>
          <div>
            <input
              type="date"
              value={filters.end_date}
              onChange={(e) => setFilters({ ...filters, end_date: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleFilter}
              className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors text-sm"
            >
              <Search size={16} />
              筛选
            </button>
            <button
              onClick={handleReset}
              className="px-3 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg transition-colors text-sm"
            >
              重置
            </button>
          </div>
        </div>
      </div>

      {/* 日志列表 */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </div>
      ) : (
        <div className="bg-dark-900 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-dark-800">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">时间</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">操作人</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">操作</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">实体类型</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">详情</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">IP地址</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-dark-500">
                    暂无日志记录
                  </td>
                </tr>
              ) : (
                logs.map(log => (
                  <tr
                    key={log.id}
                    className="border-t border-dark-800 hover:bg-dark-800/50 cursor-pointer"
                    onClick={() => setSelectedLog(log)}
                  >
                    <td className="px-4 py-3 text-sm text-dark-400">
                      {new Date(log.created_at).toLocaleString('zh-CN')}
                    </td>
                    <td className="px-4 py-3 text-sm">{log.operator_name || '-'}</td>
                    <td className="px-4 py-3">
                      <span className={`font-medium ${getActionColor(log.action)}`}>
                        {getActionLabel(log.action)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {getEntityTypeLabel(log.entity_type)}
                      {log.entity_id && <span className="text-dark-500 ml-1">#{log.entity_id}</span>}
                    </td>
                    <td className="px-4 py-3 text-sm text-dark-400 max-w-xs truncate">
                      {log.new_value ? formatValue(log.new_value) : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-dark-500 font-mono">
                      {log.ip_address || '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 日志详情弹窗 (A-3: Diff viewer) */}
      {selectedLog && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setSelectedLog(null)}
        >
          <div
            className="bg-dark-900 rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <FileText size={20} className="text-primary-400" />
                日志详情
              </h3>
              <button
                onClick={() => setSelectedLog(null)}
                className="text-dark-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-dark-400">操作时间</label>
                  <p className="text-sm">{new Date(selectedLog.created_at).toLocaleString('zh-CN')}</p>
                </div>
                <div>
                  <label className="text-xs text-dark-400">IP地址</label>
                  <p className="text-sm font-mono">{selectedLog.ip_address || '-'}</p>
                </div>
                <div>
                  <label className="text-xs text-dark-400">操作人</label>
                  <p className="text-sm">{selectedLog.operator_name || '-'} (ID: {selectedLog.operator_id})</p>
                </div>
                <div>
                  <label className="text-xs text-dark-400">操作类型</label>
                  <p className={`text-sm font-medium ${getActionColor(selectedLog.action)}`}>
                    {getActionLabel(selectedLog.action)}
                  </p>
                </div>
                <div>
                  <label className="text-xs text-dark-400">实体类型</label>
                  <p className="text-sm">{getEntityTypeLabel(selectedLog.entity_type)}</p>
                </div>
                <div>
                  <label className="text-xs text-dark-400">实体ID</label>
                  <p className="text-sm">{selectedLog.entity_id || '-'}</p>
                </div>
              </div>

              {/* A-3: Diff viewer */}
              {(selectedLog.old_value || selectedLog.new_value) && (
                <div>
                  <label className="text-xs text-dark-400 mb-2 block">
                    {selectedLog.old_value && selectedLog.new_value ? '变更对比' : selectedLog.old_value ? '旧值' : '新值'}
                  </label>
                  <div className="bg-dark-950 rounded-lg p-3 overflow-x-auto">
                    <ValueDiff oldValue={selectedLog.old_value} newValue={selectedLog.new_value} />
                  </div>
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg transition-colors"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
