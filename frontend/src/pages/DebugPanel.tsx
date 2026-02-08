/**
 * DebugPanel Page
 *
 * Main page for the debug panel (sysadmin only).
 * Displays a list of debug sessions and allows viewing details.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { debugApi } from '../services/api'
import type { DebugSession, DebugStatistics } from '../types'
import { useAuthStore } from '../store'
import { Button } from '../components/ui/button'
import { RefreshCw, Calendar } from 'lucide-react'

export default function DebugPanelPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [sessions, setSessions] = useState<DebugSession[]>([])
  const [stats, setStats] = useState<DebugStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    status: '',
    limit: 20,
    offset: 0
  })

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

  const handleRefresh = () => {
    loadData()
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
            disabled={loading}
            className="border-gray-700 text-gray-300 hover:bg-gray-800"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCleanup}
            className="border-red-900 text-red-400 hover:bg-red-950"
          >
            <Calendar className="w-4 h-4 mr-2" />
            Cleanup (30 days)
          </Button>
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
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Duration</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Attempts</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-800">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : sessions.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  No sessions found
                </td>
              </tr>
            ) : (
              sessions.map((session) => (
                <tr
                  key={session.session_id}
                  onClick={() => handleSessionClick(session.session_id)}
                  className="hover:bg-dark-800 cursor-pointer"
                >
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {formatTime(session.timestamp)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {session.user_role || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300 max-w-md truncate">
                    {session.input_message}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className={getStatusColor(session.status)}>
                      {session.status}
                    </span>
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
    </div>
  )
}
