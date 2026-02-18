/**
 * DebugPanel Page
 *
 * Main page for the debug panel (sysadmin only).
 * Displays a list of debug sessions and analytics charts.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { debugApi } from '../services/api'
import type { DebugSession, DebugStatistics, TokenTrendResponse, ErrorAggregationResponse } from '../types'
import { useAuthStore } from '../store'
import { Button } from '../components/ui/button'
import { RefreshCw, Calendar, BarChart3, List } from 'lucide-react'

type TabType = 'sessions' | 'analytics'

export default function DebugPanelPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [sessions, setSessions] = useState<DebugSession[]>([])
  const [stats, setStats] = useState<DebugStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabType>('sessions')
  const [filters, setFilters] = useState({
    status: '',
    limit: 20,
    offset: 0
  })

  // Analytics state
  const [tokenTrend, setTokenTrend] = useState<TokenTrendResponse | null>(null)
  const [errorAgg, setErrorAgg] = useState<ErrorAggregationResponse | null>(null)
  const [analyticsDays, setAnalyticsDays] = useState(7)
  const [analyticsLoading, setAnalyticsLoading] = useState(false)

  // Check if user is sysadmin
  useEffect(() => {
    if (user && user.role !== 'sysadmin') {
      navigate('/dashboard')
    }
  }, [user, navigate])

  // Load sessions and stats
  useEffect(() => {
    if (user?.role === 'sysadmin') {
      loadData()
    }
  }, [user, filters])

  // Load analytics when tab or days change
  useEffect(() => {
    if (user?.role === 'sysadmin' && activeTab === 'analytics') {
      loadAnalytics()
    }
  }, [user, activeTab, analyticsDays])

  const loadData = async () => {
    setLoading(true)
    try {
      const [sessionsData, statsData] = await Promise.all([
        debugApi.listSessions(filters),
        debugApi.getStatistics()
      ])
      setSessions(sessionsData.sessions)
      setStats(statsData)
    } catch (error) {
      console.error('Failed to load debug data:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadAnalytics = async () => {
    setAnalyticsLoading(true)
    try {
      const [trend, errors] = await Promise.all([
        debugApi.getTokenTrend(analyticsDays),
        debugApi.getErrorAggregation(analyticsDays),
      ])
      setTokenTrend(trend)
      setErrorAgg(errors)
    } catch (error) {
      console.error('Failed to load analytics:', error)
    } finally {
      setAnalyticsLoading(false)
    }
  }

  const handleRefresh = () => {
    if (activeTab === 'sessions') loadData()
    else loadAnalytics()
  }

  const handleSessionClick = (sessionId: string) => {
    navigate(`/debug/sessions/${sessionId}`)
  }

  const handleCleanup = async () => {
    if (!confirm('Delete sessions older than 30 days?')) return

    try {
      const result = await debugApi.cleanupOldSessions(30)
      alert(result.message)
      loadData()
    } catch (error) {
      console.error('Failed to cleanup:', error)
      alert('Cleanup failed')
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return 'text-green-400'
      case 'error': return 'text-red-400'
      case 'partial': return 'text-yellow-400'
      default: return 'text-gray-400'
    }
  }

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('zh-CN')
  }

  if (!user || user.role !== 'sysadmin') {
    return null
  }

  const isLoading = activeTab === 'sessions' ? loading : analyticsLoading

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Debug Panel</h1>
          <p className="text-gray-400 text-sm mt-1">AI decision trace and replay (sysadmin only)</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isLoading}
            className="border-gray-700 text-gray-300 hover:bg-gray-800"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          {activeTab === 'sessions' && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleCleanup}
              className="border-red-900 text-red-400 hover:bg-red-950"
            >
              <Calendar className="w-4 h-4 mr-2" />
              Cleanup (30 days)
            </Button>
          )}
        </div>
      </div>

      {/* Statistics */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">Total Sessions</div>
            <div className="text-2xl font-bold text-white">{stats.total_sessions}</div>
          </div>
          <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">Total Attempts</div>
            <div className="text-2xl font-bold text-white">{stats.total_attempts}</div>
          </div>
          <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">Success Rate</div>
            <div className="text-2xl font-bold text-white">
              {stats.total_sessions > 0
                ? Math.round((stats.status_counts.success || 0) / stats.total_sessions * 100)
                : 0}%
            </div>
          </div>
          <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">Last 24h</div>
            <div className="text-2xl font-bold text-white">{stats.recent_sessions_24h}</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-dark-800">
        <button
          onClick={() => setActiveTab('sessions')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'sessions'
              ? 'border-primary-400 text-primary-400'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <List size={16} />
          Sessions
        </button>
        <button
          onClick={() => setActiveTab('analytics')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'analytics'
              ? 'border-primary-400 text-primary-400'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <BarChart3 size={16} />
          Analytics
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'sessions' ? (
        <SessionsTab
          sessions={sessions}
          loading={loading}
          filters={filters}
          setFilters={setFilters}
          onSessionClick={handleSessionClick}
          getStatusColor={getStatusColor}
          formatTime={formatTime}
        />
      ) : (
        <AnalyticsTab
          tokenTrend={tokenTrend}
          errorAgg={errorAgg}
          loading={analyticsLoading}
          days={analyticsDays}
          onDaysChange={setAnalyticsDays}
        />
      )}
    </div>
  )
}

// ==================== Sessions Tab ====================

function SessionsTab({
  sessions, loading, filters, setFilters, onSessionClick, getStatusColor, formatTime
}: {
  sessions: DebugSession[]
  loading: boolean
  filters: { status: string; limit: number; offset: number }
  setFilters: (f: { status: string; limit: number; offset: number }) => void
  onSessionClick: (id: string) => void
  getStatusColor: (status: string) => string
  formatTime: (ts: string) => string
}) {
  return (
    <>
      {/* Filters */}
      <div className="flex gap-4 mb-4">
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value, offset: 0 })}
          className="bg-dark-900 border border-dark-800 text-white rounded px-3 py-2 text-sm"
        >
          <option value="">All Status</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
          <option value="partial">Partial</option>
          <option value="pending">Pending</option>
        </select>
      </div>

      {/* Sessions Table */}
      <div className="bg-dark-900 border border-dark-800 rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-dark-950">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Time</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">User</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Input</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Action</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Model</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Tokens</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Duration</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Attempts</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-800">
            {loading ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : sessions.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-gray-400">
                  No sessions found
                </td>
              </tr>
            ) : (
              sessions.map((session) => (
                <tr
                  key={session.session_id}
                  onClick={() => onSessionClick(session.session_id)}
                  className="hover:bg-dark-800 cursor-pointer"
                >
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {formatTime(session.timestamp)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {session.user_role || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300 max-w-xs truncate">
                    {session.input_message}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {session.action_type ? (
                      <span className="px-1.5 py-0.5 bg-sky-500/10 text-sky-400 rounded text-xs font-mono">
                        {session.action_type}
                      </span>
                    ) : <span className="text-gray-500">-</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-400 text-xs">
                    {session.llm_model || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className={getStatusColor(session.status)}>
                      {session.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {session.llm_tokens_used || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {session.execution_time_ms ? `${session.execution_time_ms}ms` : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {session.attempt_count ?? 0}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ==================== Analytics Tab ====================

function AnalyticsTab({
  tokenTrend, errorAgg, loading, days, onDaysChange
}: {
  tokenTrend: TokenTrendResponse | null
  errorAgg: ErrorAggregationResponse | null
  loading: boolean
  days: number
  onDaysChange: (d: number) => void
}) {
  if (loading) {
    return <div className="text-center text-gray-400 py-12">Loading analytics...</div>
  }

  return (
    <div className="space-y-6">
      {/* Days selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-400">Time range:</span>
        {[7, 14, 30, 90].map(d => (
          <button
            key={d}
            onClick={() => onDaysChange(d)}
            className={`px-3 py-1 text-sm rounded ${
              days === d
                ? 'bg-primary-600/20 text-primary-400 border border-primary-500/30'
                : 'bg-dark-900 text-gray-400 border border-dark-800 hover:text-gray-200'
            }`}
          >
            {d}d
          </button>
        ))}
      </div>

      {/* Token Trend Chart */}
      <div className="bg-dark-900 border border-dark-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Token Usage Trend</h3>
        {tokenTrend && tokenTrend.data.length > 0 ? (
          <TokenTrendChart data={tokenTrend.data} />
        ) : (
          <div className="text-gray-500 text-sm py-8 text-center">No data for selected period</div>
        )}
      </div>

      {/* Error Aggregation */}
      <div className="grid grid-cols-2 gap-6">
        {/* Error Rate Summary */}
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Error Summary</h3>
          {errorAgg ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="text-gray-400 text-xs uppercase">Total</div>
                  <div className="text-xl font-bold text-white">{errorAgg.totals.total_sessions}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-xs uppercase">Success</div>
                  <div className="text-xl font-bold text-green-400">{errorAgg.totals.success_sessions}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-xs uppercase">Errors</div>
                  <div className="text-xl font-bold text-red-400">{errorAgg.totals.error_sessions}</div>
                </div>
              </div>
              {errorAgg.totals.total_sessions > 0 && (
                <div>
                  <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                    <span>Error Rate</span>
                    <span>{Math.round((errorAgg.totals.error_sessions / errorAgg.totals.total_sessions) * 100)}%</span>
                  </div>
                  <div className="h-2 bg-dark-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-red-500 rounded-full"
                      style={{ width: `${(errorAgg.totals.error_sessions / errorAgg.totals.total_sessions) * 100}%` }}
                    />
                  </div>
                </div>
              )}
              {/* Error trend by day */}
              {errorAgg.by_day.length > 0 && (
                <div className="mt-4">
                  <div className="text-sm text-gray-400 mb-2">Errors by Day</div>
                  <ErrorDayChart data={errorAgg.by_day} />
                </div>
              )}
            </div>
          ) : (
            <div className="text-gray-500 text-sm py-4 text-center">No data</div>
          )}
        </div>

        {/* Top Errors */}
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Top Errors</h3>
          {errorAgg && errorAgg.top_errors.length > 0 ? (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {errorAgg.top_errors.map((err, i) => (
                <div key={i} className="flex items-start gap-3 p-2 rounded bg-dark-950">
                  <span className="flex-shrink-0 w-8 h-6 flex items-center justify-center bg-red-500/10 text-red-400 rounded text-xs font-bold">
                    {err.count}
                  </span>
                  <span className="text-sm text-gray-300 break-all line-clamp-2">
                    {err.error_msg}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-500 text-sm py-4 text-center">No errors in this period</div>
          )}
        </div>
      </div>
    </div>
  )
}

// ==================== Chart Components (CSS-based) ====================

function TokenTrendChart({ data }: { data: TokenTrendResponse['data'] }) {
  const maxTokens = Math.max(...data.map(d => d.total_tokens), 1)
  const maxLatency = Math.max(...data.map(d => d.avg_latency_ms), 1)

  return (
    <div className="space-y-4">
      {/* Token bars */}
      <div>
        <div className="text-xs text-gray-400 mb-2">Total Tokens (blue) / Avg Latency ms (amber)</div>
        <div className="flex items-end gap-1" style={{ height: 160 }}>
          {data.map(d => {
            const tokenH = (d.total_tokens / maxTokens) * 140
            const latencyH = (d.avg_latency_ms / maxLatency) * 140
            const dayLabel = d.day.slice(5) // MM-DD
            return (
              <div key={d.day} className="flex-1 flex flex-col items-center gap-0.5" title={
                `${d.day}\nSessions: ${d.session_count}\nTokens: ${d.total_tokens}\nAvg: ${Math.round(d.avg_tokens)}\nLatency: ${Math.round(d.avg_latency_ms)}ms`
              }>
                <div className="w-full flex items-end justify-center gap-0.5" style={{ height: 140 }}>
                  <div
                    className="flex-1 max-w-[20px] bg-sky-500/70 rounded-t"
                    style={{ height: Math.max(tokenH, 2) }}
                  />
                  <div
                    className="flex-1 max-w-[20px] bg-amber-500/70 rounded-t"
                    style={{ height: Math.max(latencyH, 2) }}
                  />
                </div>
                <span className="text-[10px] text-gray-500 mt-1">{dayLabel}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Summary row */}
      <div className="flex gap-6 text-xs text-gray-400 border-t border-dark-800 pt-3">
        <span>Total: <span className="text-white font-medium">{data.reduce((s, d) => s + d.total_tokens, 0).toLocaleString()}</span> tokens</span>
        <span>Sessions: <span className="text-white font-medium">{data.reduce((s, d) => s + d.session_count, 0)}</span></span>
        <span>Avg latency: <span className="text-white font-medium">{Math.round(data.reduce((s, d) => s + d.avg_latency_ms, 0) / data.length)}ms</span></span>
      </div>
    </div>
  )
}

function ErrorDayChart({ data }: { data: { day: string; error_count: number }[] }) {
  const maxCount = Math.max(...data.map(d => d.error_count), 1)

  return (
    <div className="flex items-end gap-1" style={{ height: 80 }}>
      {data.map(d => {
        const h = (d.error_count / maxCount) * 60
        return (
          <div key={d.day} className="flex-1 flex flex-col items-center" title={`${d.day}: ${d.error_count} errors`}>
            <div
              className="w-full max-w-[24px] bg-red-500/70 rounded-t"
              style={{ height: Math.max(h, 2) }}
            />
            <span className="text-[10px] text-gray-500 mt-1">{d.day.slice(5)}</span>
          </div>
        )
      })}
    </div>
  )
}
