/**
 * SessionDetail Page
 *
 * Shows detailed information about a debug session including
 * input, retrieval, LLM interaction, execution, and results.
 */
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { debugApi } from '../services/api'
import type { SessionDetailResponse, ReplayRequest } from '../types'
import { Button } from '../components/ui/button'
import { ArrowLeft, Play, RefreshCw, Copy, Check } from 'lucide-react'

export default function SessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<SessionDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [replaying, setReplaying] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)

  useEffect(() => {
    if (sessionId) {
      loadData()
    }
  }, [sessionId])

  const loadData = async () => {
    setLoading(true)
    try {
      const result = await debugApi.getSessionDetail(sessionId!)
      setData(result)
    } catch (error) {
      console.error('Failed to load session:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleReplay = async () => {
    if (!data) return

    setReplaying(true)
    try {
      const request: ReplayRequest = {
        session_id: sessionId!,
        dry_run: true
      }
      const result = await debugApi.replaySession(request)
      // Navigate to replay results
      navigate(`/debug/replay/${result.replay.replay_id}`, {
        state: { replayData: result }
      })
    } catch (error: any) {
      console.error('Replay failed:', error)
      const message = error.response?.data?.detail || 'Replay failed'
      alert(message)
    } finally {
      setReplaying(false)
    }
  }

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  const formatJson = (obj: any) => {
    return JSON.stringify(obj, null, 2)
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <div className="text-gray-400">Loading session details...</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="p-6">
        <div className="text-red-400">Session not found</div>
      </div>
    )
  }

  const { session, attempts } = data

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/debug')}
            className="text-gray-400 hover:text-white"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-xl font-bold text-white">Session Detail</h1>
            <p className="text-gray-400 text-sm">{session.session_id}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            className="border-gray-700 text-gray-300 hover:bg-gray-800"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={handleReplay}
            disabled={replaying}
            className="bg-primary-600 hover:bg-primary-700"
          >
            <Play className="w-4 h-4 mr-2" />
            {replaying ? 'Replaying...' : 'Replay (Dry Run)'}
          </Button>
        </div>
      </div>

      {/* Session Overview */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs uppercase">Status</div>
          <div className={`text-lg font-bold ${
            session.status === 'success' ? 'text-green-400' :
            session.status === 'error' ? 'text-red-400' :
            'text-yellow-400'
          }`}>
            {session.status}
          </div>
        </div>
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs uppercase">Execution Time</div>
          <div className="text-lg font-bold text-white">
            {session.execution_time_ms ? `${session.execution_time_ms}ms` : '-'}
          </div>
        </div>
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs uppercase">LLM Tokens</div>
          <div className="text-lg font-bold text-white">
            {session.llm_tokens_used || '-'}
          </div>
        </div>
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs uppercase">Attempts</div>
          <div className="text-lg font-bold text-white">{attempts.length}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Input Section */}
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-white">Input Message</h3>
          </div>
          <div className="bg-dark-950 rounded p-3 text-sm text-gray-300 font-mono whitespace-pre-wrap">
            {session.input_message}
          </div>
        </div>

        {/* Retrieval Section */}
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-white">Retrieval</h3>
          </div>
          <div className="space-y-2">
            <div>
              <div className="text-xs text-gray-400 mb-1">Schema</div>
              <div className="bg-dark-950 rounded p-2 text-xs text-gray-300 font-mono overflow-auto max-h-20">
                {session.retrieved_schema ? formatJson(session.retrieved_schema) : 'None'}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-1">Tools</div>
              <div className="bg-dark-950 rounded p-2 text-xs text-gray-300 font-mono overflow-auto max-h-20">
                {session.retrieved_tools ? formatJson(session.retrieved_tools) : 'None'}
              </div>
            </div>
          </div>
        </div>

        {/* LLM Section */}
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-white">LLM Interaction</h3>
            <span className="text-xs text-gray-400">{session.llm_model || 'Unknown'}</span>
          </div>
          <div className="space-y-2">
            <div>
              <div className="text-xs text-gray-400 mb-1">Prompt</div>
              <div className="bg-dark-950 rounded p-2 text-xs text-gray-300 font-mono overflow-auto max-h-32">
                {session.llm_prompt || 'None'}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-1">Response</div>
              <div className="bg-dark-950 rounded p-2 text-xs text-gray-300 font-mono overflow-auto max-h-32">
                {session.llm_response || 'None'}
              </div>
            </div>
          </div>
        </div>

        {/* Result Section */}
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-white">Final Result</h3>
          </div>
          <div className="bg-dark-950 rounded p-3 text-sm text-gray-300 font-mono overflow-auto max-h-72">
            {session.final_result ? formatJson(session.final_result) : 'None'}
          </div>
        </div>
      </div>

      {/* Attempts Timeline */}
      <div className="mt-6 bg-dark-900 border border-dark-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-white mb-3">Execution Attempts</h3>
        <div className="space-y-3">
          {attempts.map((attempt, index) => (
            <div key={attempt.attempt_id} className="border border-dark-800 rounded p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-dark-800 px-2 py-1 rounded">Attempt {attempt.attempt_number}</span>
                  <span className="text-xs font-mono text-gray-400">{attempt.action_name}</span>
                </div>
                <span className={`text-xs px-2 py-1 rounded ${
                  attempt.success ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
                }`}>
                  {attempt.success ? 'Success' : 'Error'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <div className="text-gray-400">Params</div>
                  <div className="font-mono text-gray-300 bg-dark-950 p-2 rounded mt-1">
                    {formatJson(attempt.params)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Result</div>
                  <div className="font-mono text-gray-300 bg-dark-950 p-2 rounded mt-1 max-h-32 overflow-auto">
                    {attempt.result ? formatJson(attempt.result) : 'None'}
                  </div>
                </div>
              </div>
              {attempt.error && (
                <div className="mt-2">
                  <div className="text-gray-400 text-xs">Error</div>
                  <div className="font-mono text-red-400 bg-dark-950 p-2 rounded mt-1 text-xs">
                    {formatJson(attempt.error)}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
