/**
 * ReplayResult Page
 *
 * Shows the results of a replay execution with comparison to the original session.
 * Enhanced with field-level diff visualization (SPEC-38).
 */
import { useEffect, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { debugApi } from '../services/api'
import type { ReplayResponse } from '../types'
import { Button } from '../components/ui/button'
import { ArrowLeft, CheckCircle, XCircle, AlertCircle, Minus, Plus, Equal } from 'lucide-react'

// Field-level diff component for JSON objects
function FieldDiff({ original, replay, label }: {
  original: Record<string, unknown> | null
  replay: Record<string, unknown> | null
  label: string
}) {
  if (!original && !replay) return null

  const origObj = original || {}
  const replayObj = replay || {}
  const allKeys = [...new Set([...Object.keys(origObj), ...Object.keys(replayObj)])]

  if (allKeys.length === 0) return null

  return (
    <div className="bg-dark-950 rounded-lg p-3">
      <div className="text-xs text-gray-400 mb-2 font-medium">{label}</div>
      <div className="space-y-1 font-mono text-xs">
        {allKeys.map(key => {
          const origVal = origObj[key]
          const replayVal = replayObj[key]
          const origStr = origVal !== undefined ? JSON.stringify(origVal) : undefined
          const replayStr = replayVal !== undefined ? JSON.stringify(replayVal) : undefined

          if (origStr === replayStr) {
            // Same
            return (
              <div key={key} className="flex items-start gap-2 text-gray-500">
                <Equal size={12} className="mt-0.5 flex-shrink-0" />
                <span className="text-sky-400/50">{key}</span>
                <span>: {origStr}</span>
              </div>
            )
          }

          // Changed / Added / Removed
          return (
            <div key={key} className="space-y-0.5">
              {origStr !== undefined && (
                <div className="flex items-start gap-2 text-red-400/80 bg-red-500/5 px-1 rounded">
                  <Minus size={12} className="mt-0.5 flex-shrink-0" />
                  <span className="text-sky-400">{key}</span>
                  <span>: {origStr}</span>
                </div>
              )}
              {replayStr !== undefined && (
                <div className="flex items-start gap-2 text-green-400/80 bg-green-500/5 px-1 rounded">
                  <Plus size={12} className="mt-0.5 flex-shrink-0" />
                  <span className="text-sky-400">{key}</span>
                  <span>: {replayStr}</span>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function ReplayResultPage() {
  const { replayId } = useParams<{ replayId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const [data, setData] = useState<ReplayResponse | null>(location.state?.replayData || null)
  const [loading, setLoading] = useState(!data)

  useEffect(() => {
    if (!data && replayId) {
      loadData()
    }
  }, [replayId])

  const loadData = async () => {
    setLoading(true)
    try {
      const result = await debugApi.getReplayResult(replayId!)
      setData(result)
    } catch (error) {
      console.error('Failed to load replay result:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <div className="text-gray-400">Loading replay results...</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="p-6">
        <div className="text-red-400">Replay result not found</div>
      </div>
    )
  }

  const { replay, original_session, comparison } = data

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/debug/sessions/${replay.original_session_id}`)}
            className="text-gray-400 hover:text-white"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-xl font-bold text-white">Replay Result</h1>
            <p className="text-gray-400 text-sm">{replay.replay_id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {replay.dry_run && (
            <span className="text-xs bg-yellow-900 text-yellow-300 px-2 py-1 rounded">
              Dry Run
            </span>
          )}
          {replay.success ? (
            <span className="flex items-center gap-1 text-xs bg-green-900 text-green-300 px-2 py-1 rounded">
              <CheckCircle className="w-3 h-3" /> Success
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs bg-red-900 text-red-300 px-2 py-1 rounded">
              <XCircle className="w-3 h-3" /> Failed
            </span>
          )}
        </div>
      </div>

      {/* Comparison Summary */}
      {comparison && (
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4 mb-6">
          <h3 className="text-sm font-medium text-white mb-3">Comparison Summary</h3>
          <div className="text-sm text-gray-300 whitespace-pre-line">
            {comparison.summary}
          </div>
        </div>
      )}

      {/* Session Comparison */}
      {comparison && (
        <div className="grid grid-cols-2 gap-6 mb-6">
          <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-white mb-3">Original Session</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Status</span>
                <span className={`font-medium ${
                  comparison.session_comparison.original_status === 'success' ? 'text-green-400' :
                  comparison.session_comparison.original_status === 'error' ? 'text-red-400' :
                  'text-yellow-400'
                }`}>
                  {comparison.session_comparison.original_status}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Execution Time</span>
                <span className="text-white">
                  {original_session.execution_time_ms ? `${original_session.execution_time_ms}ms` : '-'}
                </span>
              </div>
            </div>
          </div>
          <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-white mb-3">Replay Session</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Status</span>
                <span className={`font-medium ${
                  comparison.session_comparison.replay_status === 'success' ? 'text-green-400' :
                  comparison.session_comparison.replay_status === 'error' ? 'text-red-400' :
                  'text-yellow-400'
                }`}>
                  {comparison.session_comparison.replay_status}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Execution Time</span>
                <span className="text-white">
                  {replay.execution_time_ms}ms
                  {comparison.performance_diff.execution_time_diff_ms !== null && (
                    <span className={`ml-2 ${
                      comparison.performance_diff.execution_time_diff_ms > 0 ? 'text-red-400' :
                      comparison.performance_diff.execution_time_diff_ms < 0 ? 'text-green-400' :
                      'text-gray-400'
                    }`}>
                      ({comparison.performance_diff.execution_time_diff_ms > 0 ? '+' : ''}
                      {comparison.performance_diff.execution_time_diff_ms}ms)
                    </span>
                  )}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">LLM Model</span>
                <span className="text-white">{replay.llm_model}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Performance Diff */}
      {comparison && comparison.performance_diff.execution_time_diff_ms !== null && (
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4 mb-6">
          <h3 className="text-sm font-medium text-white mb-3">Performance Comparison</h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-gray-400">Time Diff</div>
              <div className={`font-medium ${
                comparison.performance_diff.execution_time_diff_ms > 0 ? 'text-red-400' :
                comparison.performance_diff.execution_time_diff_ms < 0 ? 'text-green-400' :
                'text-gray-300'
              }`}>
                {comparison.performance_diff.execution_time_diff_ms > 0 ? '+' : ''}
                {comparison.performance_diff.execution_time_diff_ms}ms
                {comparison.performance_diff.execution_time_change_pct && (
                  <span className="ml-1 text-gray-400">
                    ({comparison.performance_diff.execution_time_change_pct.toFixed(1)}%)
                  </span>
                )}
              </div>
            </div>
            <div>
              <div className="text-gray-400">Tokens Diff</div>
              <div className={`font-medium ${
                comparison.performance_diff.tokens_diff > 0 ? 'text-red-400' :
                comparison.performance_diff.tokens_diff < 0 ? 'text-green-400' :
                'text-gray-300'
              }`}>
                {comparison.performance_diff.tokens_diff !== null ? (
                  <>
                    {comparison.performance_diff.tokens_diff > 0 ? '+' : ''}
                    {comparison.performance_diff.tokens_diff}
                    {comparison.performance_diff.tokens_change_pct && (
                      <span className="ml-1 text-gray-400">
                        ({comparison.performance_diff.tokens_change_pct.toFixed(1)}%)
                      </span>
                    )}
                  </>
                ) : '-'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Field-Level Diff (from session_comparison) */}
      {comparison && comparison.session_comparison.field_diffs && Object.keys(comparison.session_comparison.field_diffs).length > 0 && (
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4 mb-6">
          <h3 className="text-sm font-medium text-white mb-3">Result Field Diff</h3>
          <div className="space-y-1 font-mono text-xs">
            {Object.entries(comparison.session_comparison.field_diffs).map(([key, diff]) => (
              <div key={key} className="space-y-0.5">
                <div className="flex items-start gap-2 text-red-400/80 bg-red-500/5 px-2 py-0.5 rounded">
                  <Minus size={12} className="mt-0.5 flex-shrink-0" />
                  <span className="text-sky-400">{key}</span>
                  <span>: {JSON.stringify(diff.original)}</span>
                </div>
                <div className="flex items-start gap-2 text-green-400/80 bg-green-500/5 px-2 py-0.5 rounded">
                  <Plus size={12} className="mt-0.5 flex-shrink-0" />
                  <span className="text-sky-400">{key}</span>
                  <span>: {JSON.stringify(diff.replay)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Attempt Comparison */}
      {comparison && comparison.attempt_comparison.length > 0 && (
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-white mb-3">Attempt Comparison</h3>
          <div className="space-y-3">
            {comparison.attempt_comparison.map((diff) => (
              <div key={diff.attempt_number} className="border border-dark-800 rounded p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-white">Attempt {diff.attempt_number}</span>
                  <div className="flex gap-2">
                    {diff.success_changed && (
                      <span className="text-xs bg-yellow-900 text-yellow-300 px-2 py-1 rounded">
                        Status Changed
                      </span>
                    )}
                    {diff.params_changed && (
                      <span className="text-xs bg-sky-900 text-sky-300 px-2 py-1 rounded">
                        Params Changed
                      </span>
                    )}
                    {diff.error_changed && (
                      <span className="text-xs bg-red-900 text-red-300 px-2 py-1 rounded">
                        Error Changed
                      </span>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm mb-3">
                  <div>
                    <div className="text-gray-400 text-xs">Original</div>
                    <div className={`font-medium ${diff.original_success ? 'text-green-400' : 'text-red-400'}`}>
                      {diff.original_success ? 'Success' : 'Failed'}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400 text-xs">Replay</div>
                    <div className={`font-medium ${diff.replay_success ? 'text-green-400' : 'text-red-400'}`}>
                      {diff.replay_success ? 'Success' : 'Failed'}
                    </div>
                  </div>
                </div>
                {/* Param diff */}
                {diff.params_changed && (
                  <FieldDiff
                    original={diff.original_params as Record<string, unknown>}
                    replay={diff.replay_params as Record<string, unknown>}
                    label="Parameters"
                  />
                )}
                {/* Error diff */}
                {diff.error_changed && (
                  <div className="mt-2 space-y-1 text-xs font-mono">
                    {diff.original_error && (
                      <div className="flex items-start gap-2 text-red-400/80 bg-red-500/5 px-2 py-0.5 rounded">
                        <Minus size={12} className="mt-0.5 flex-shrink-0" />
                        <span>error: {diff.original_error}</span>
                      </div>
                    )}
                    {diff.replay_error && (
                      <div className="flex items-start gap-2 text-green-400/80 bg-green-500/5 px-2 py-0.5 rounded">
                        <Plus size={12} className="mt-0.5 flex-shrink-0" />
                        <span>error: {diff.replay_error}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {replay.error && (
        <div className="bg-red-950 border border-red-900 rounded-lg p-4 mt-6">
          <div className="flex items-center gap-2 text-red-400 mb-2">
            <AlertCircle className="w-4 h-4" />
            <span className="font-medium">Replay Error</span>
          </div>
          <div className="text-sm text-red-300 font-mono">{replay.error}</div>
        </div>
      )}
    </div>
  )
}
