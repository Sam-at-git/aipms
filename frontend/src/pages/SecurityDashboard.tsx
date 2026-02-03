import React, { useEffect, useState, useCallback } from 'react'
import {
  Shield, AlertTriangle, CheckCircle, Clock, RefreshCw,
  Filter, Eye, Check
} from 'lucide-react'
import { securityApi, SecurityEvent, SecurityStatistics, AlertSummary } from '../services/api'

// Severity color mapping
const severityColors: Record<string, { bg: string; text: string; border: string }> = {
  low: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30' },
  medium: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  high: { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/30' },
  critical: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
}

// Event type labels
const eventTypeLabels: Record<string, string> = {
  login_failed: 'Login Failed',
  login_success: 'Login Success',
  multiple_login_failures: 'Multiple Login Failures',
  logout: 'User Logout',
  unauthorized_access: 'Unauthorized Access',
  role_escalation_attempt: 'Role Escalation Attempt',
  sensitive_data_access: 'Sensitive Data Access',
  bulk_data_export: 'Bulk Data Export',
  unusual_time_access: 'Unusual Time Access',
  security_config_changed: 'Security Config Changed',
  password_changed: 'Password Changed',
}

// Severity labels
const severityLabels: Record<string, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
}

interface StatCardProps {
  title: string
  value: number | string
  icon: React.ReactNode
  highlight?: boolean
  color?: string
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, highlight, color }) => (
  <div className={`bg-dark-900 rounded-lg p-4 border ${highlight ? 'border-red-500/50' : 'border-dark-800'}`}>
    <div className="flex items-center justify-between mb-2">
      <span className="text-dark-400 text-sm">{title}</span>
      <span className={color || 'text-dark-500'}>{icon}</span>
    </div>
    <div className={`text-2xl font-bold ${highlight ? 'text-red-400' : 'text-white'}`}>
      {value}
    </div>
  </div>
)

interface EventRowProps {
  event: SecurityEvent
  onAcknowledge: (id: number) => void
  onViewDetails: (event: SecurityEvent) => void
}

const EventRow: React.FC<EventRowProps> = ({ event, onAcknowledge, onViewDetails }) => {
  const colors = severityColors[event.severity] || severityColors.low

  return (
    <tr className="border-b border-dark-800 hover:bg-dark-800/50">
      <td className="py-3 px-4">
        <span className={`px-2 py-0.5 rounded text-xs ${colors.bg} ${colors.text}`}>
          {severityLabels[event.severity] || event.severity}
        </span>
      </td>
      <td className="py-3 px-4">
        <span className="text-dark-300">
          {eventTypeLabels[event.event_type] || event.event_type}
        </span>
      </td>
      <td className="py-3 px-4 max-w-xs truncate text-dark-400" title={event.description}>
        {event.description}
      </td>
      <td className="py-3 px-4 text-dark-400">
        {event.user_name || '-'}
      </td>
      <td className="py-3 px-4 text-dark-500 text-sm">
        {event.source_ip || '-'}
      </td>
      <td className="py-3 px-4 text-dark-500 text-sm">
        {new Date(event.timestamp).toLocaleString()}
      </td>
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onViewDetails(event)}
            className="p-1 hover:bg-dark-700 rounded transition-colors"
            title="View Details"
          >
            <Eye size={16} className="text-dark-400" />
          </button>
          {!event.is_acknowledged && (
            <button
              onClick={() => onAcknowledge(event.id)}
              className="p-1 hover:bg-dark-700 rounded transition-colors"
              title="Acknowledge"
            >
              <Check size={16} className="text-green-400" />
            </button>
          )}
          {event.is_acknowledged && (
            <CheckCircle size={16} className="text-green-500" />
          )}
        </div>
      </td>
    </tr>
  )
}

interface EventDetailModalProps {
  event: SecurityEvent | null
  onClose: () => void
}

const EventDetailModal: React.FC<EventDetailModalProps> = ({ event, onClose }) => {
  if (!event) return null

  const colors = severityColors[event.severity] || severityColors.low

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-dark-900 rounded-lg p-6 max-w-lg w-full mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Event Details</h3>
          <button onClick={onClose} className="text-dark-400 hover:text-white">&times;</button>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-1 rounded text-sm ${colors.bg} ${colors.text}`}>
              {severityLabels[event.severity]}
            </span>
            <span className="text-dark-400">
              {eventTypeLabels[event.event_type] || event.event_type}
            </span>
          </div>

          <div>
            <label className="text-dark-500 text-sm">Description</label>
            <p className="text-white">{event.description}</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-dark-500 text-sm">User</label>
              <p className="text-white">{event.user_name || '-'}</p>
            </div>
            <div>
              <label className="text-dark-500 text-sm">Source IP</label>
              <p className="text-white">{event.source_ip || '-'}</p>
            </div>
            <div>
              <label className="text-dark-500 text-sm">Timestamp</label>
              <p className="text-white">{new Date(event.timestamp).toLocaleString()}</p>
            </div>
            <div>
              <label className="text-dark-500 text-sm">Status</label>
              <p className={event.is_acknowledged ? 'text-green-400' : 'text-yellow-400'}>
                {event.is_acknowledged ? 'Acknowledged' : 'Pending'}
              </p>
            </div>
          </div>

          {Object.keys(event.details).length > 0 && (
            <div>
              <label className="text-dark-500 text-sm">Additional Details</label>
              <pre className="bg-dark-800 rounded p-3 text-sm text-dark-300 overflow-x-auto">
                {JSON.stringify(event.details, null, 2)}
              </pre>
            </div>
          )}

          {event.is_acknowledged && event.acknowledged_at && (
            <div className="text-dark-500 text-sm">
              Acknowledged at {new Date(event.acknowledged_at).toLocaleString()}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const SecurityDashboard: React.FC = () => {
  const [statistics, setStatistics] = useState<SecurityStatistics | null>(null)
  const [alertSummary, setAlertSummary] = useState<AlertSummary | null>(null)
  const [events, setEvents] = useState<SecurityEvent[]>([])
  const [alerts, setAlerts] = useState<SecurityEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null)

  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>('')
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('')
  const [showUnacknowledgedOnly, setShowUnacknowledgedOnly] = useState(false)
  const [timeRange, setTimeRange] = useState(24)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsRes, alertSummaryRes, eventsRes, alertsRes] = await Promise.all([
        securityApi.getStatistics(timeRange),
        securityApi.getAlertSummary(),
        securityApi.getEvents({
          hours: timeRange,
          severity: severityFilter || undefined,
          event_type: eventTypeFilter || undefined,
          unacknowledged_only: showUnacknowledgedOnly,
          limit: 100
        }),
        securityApi.getAlerts()
      ])
      setStatistics(statsRes)
      setAlertSummary(alertSummaryRes)
      setEvents(eventsRes)
      setAlerts(alertsRes)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load security data')
    } finally {
      setLoading(false)
    }
  }, [timeRange, severityFilter, eventTypeFilter, showUnacknowledgedOnly])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleAcknowledge = async (eventId: number) => {
    try {
      await securityApi.acknowledgeEvent(eventId)
      loadData()
    } catch (err: any) {
      console.error('Failed to acknowledge event:', err)
    }
  }

  const handleBulkAcknowledge = async () => {
    const unacknowledgedIds = events
      .filter(e => !e.is_acknowledged)
      .map(e => e.id)

    if (unacknowledgedIds.length === 0) return

    try {
      await securityApi.bulkAcknowledge(unacknowledgedIds)
      loadData()
    } catch (err: any) {
      console.error('Failed to bulk acknowledge:', err)
    }
  }

  if (loading && !statistics) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-primary-400 mx-auto mb-2" />
          <p className="text-dark-400">Loading security data...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={loadData}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-primary-400" />
          <h1 className="text-xl font-semibold">Security Dashboard</h1>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-3 py-1.5 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors text-sm"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Active alerts banner */}
      {alerts.length > 0 && (
        <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-5 h-5" />
              <span className="font-semibold">
                {alerts.length} active alert{alerts.length > 1 ? 's' : ''} require attention
              </span>
            </div>
            <button
              onClick={handleBulkAcknowledge}
              className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm transition-colors"
            >
              Acknowledge All
            </button>
          </div>
        </div>
      )}

      {/* Statistics cards */}
      <div className="grid grid-cols-4 gap-4 mb-4">
        <StatCard
          title="Total Events"
          value={statistics?.total || 0}
          icon={<Shield size={20} />}
          color="text-primary-400"
        />
        <StatCard
          title="Unacknowledged"
          value={statistics?.unacknowledged || 0}
          icon={<Clock size={20} />}
          highlight={(statistics?.unacknowledged || 0) > 0}
        />
        <StatCard
          title="High Severity"
          value={alertSummary?.high || 0}
          icon={<AlertTriangle size={20} />}
          color="text-orange-400"
          highlight={(alertSummary?.high || 0) > 0}
        />
        <StatCard
          title="Critical"
          value={alertSummary?.critical || 0}
          icon={<AlertTriangle size={20} />}
          color="text-red-400"
          highlight={(alertSummary?.critical || 0) > 0}
        />
      </div>

      {/* Severity breakdown */}
      {statistics?.by_severity && Object.keys(statistics.by_severity).length > 0 && (
        <div className="grid grid-cols-4 gap-4 mb-4">
          {Object.entries(statistics.by_severity).map(([severity, count]) => {
            const colors = severityColors[severity] || severityColors.low
            return (
              <div key={severity} className={`${colors.bg} border ${colors.border} rounded-lg p-3`}>
                <div className="flex items-center justify-between">
                  <span className={`${colors.text} text-sm`}>{severityLabels[severity] || severity}</span>
                  <span className={`${colors.text} font-bold text-lg`}>{count}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-dark-400" />
          <span className="text-dark-400 text-sm">Filters:</span>
        </div>

        <select
          value={timeRange}
          onChange={e => setTimeRange(Number(e.target.value))}
          className="bg-dark-800 border border-dark-700 rounded px-3 py-1.5 text-sm"
        >
          <option value={1}>Last 1 hour</option>
          <option value={6}>Last 6 hours</option>
          <option value={24}>Last 24 hours</option>
          <option value={72}>Last 3 days</option>
          <option value={168}>Last 7 days</option>
        </select>

        <select
          value={severityFilter}
          onChange={e => setSeverityFilter(e.target.value)}
          className="bg-dark-800 border border-dark-700 rounded px-3 py-1.5 text-sm"
        >
          <option value="">All Severities</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </select>

        <select
          value={eventTypeFilter}
          onChange={e => setEventTypeFilter(e.target.value)}
          className="bg-dark-800 border border-dark-700 rounded px-3 py-1.5 text-sm"
        >
          <option value="">All Event Types</option>
          {Object.entries(eventTypeLabels).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>

        <label className="flex items-center gap-2 text-sm text-dark-400 cursor-pointer">
          <input
            type="checkbox"
            checked={showUnacknowledgedOnly}
            onChange={e => setShowUnacknowledgedOnly(e.target.checked)}
            className="rounded bg-dark-800 border-dark-700"
          />
          Unacknowledged only
        </label>
      </div>

      {/* Events table */}
      <div className="flex-1 bg-dark-900 rounded-lg overflow-hidden">
        <div className="overflow-x-auto h-full">
          <table className="w-full">
            <thead className="bg-dark-800 sticky top-0">
              <tr>
                <th className="text-left py-3 px-4 text-dark-400 text-sm font-medium">Severity</th>
                <th className="text-left py-3 px-4 text-dark-400 text-sm font-medium">Event Type</th>
                <th className="text-left py-3 px-4 text-dark-400 text-sm font-medium">Description</th>
                <th className="text-left py-3 px-4 text-dark-400 text-sm font-medium">User</th>
                <th className="text-left py-3 px-4 text-dark-400 text-sm font-medium">Source IP</th>
                <th className="text-left py-3 px-4 text-dark-400 text-sm font-medium">Time</th>
                <th className="text-left py-3 px-4 text-dark-400 text-sm font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {events.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-dark-500">
                    No security events found
                  </td>
                </tr>
              ) : (
                events.map(event => (
                  <EventRow
                    key={event.id}
                    event={event}
                    onAcknowledge={handleAcknowledge}
                    onViewDetails={setSelectedEvent}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Event detail modal */}
      <EventDetailModal
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
      />
    </div>
  )
}

export default SecurityDashboard
