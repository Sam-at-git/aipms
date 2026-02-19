/**
 * SessionDetail Page
 *
 * Shows detailed information about a debug session including
 * input, retrieval, LLM interaction, and execution results.
 */
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { debugApi } from '../services/api'
import type { SessionDetailResponse, LLMInteraction } from '../types'
import { Button } from '../components/ui/button'
import { ArrowLeft, Play, RefreshCw, Copy, Check, ChevronDown, ChevronRight } from 'lucide-react'
import DualTrackTimeline from '../components/DualTrackTimeline'
import LLMInteractionDetail from '../components/LLMInteractionDetail'
import SchemaSelectionPanel from '../components/SchemaSelectionPanel'

// Lightweight JSON syntax highlighter (no dependencies)
function JsonHighlight({ data }: { data: unknown }) {
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2)
  if (!text) return <span className="text-dark-500">null</span>

  // Try to parse and re-format if it's a JSON string
  let formatted = text
  try {
    const parsed = typeof data === 'string' ? JSON.parse(data) : data
    formatted = JSON.stringify(parsed, null, 2)
  } catch {
    formatted = text
  }

  // Colorize JSON tokens
  const highlighted = formatted.replace(
    /("(?:\\.|[^"\\])*")\s*:/g, // keys
    '<span class="text-sky-400">$1</span>:'
  ).replace(
    /:\s*("(?:\\.|[^"\\])*")/g, // string values
    ': <span class="text-emerald-400">$1</span>'
  ).replace(
    /:\s*(\d+\.?\d*)/g, // number values
    ': <span class="text-amber-400">$1</span>'
  ).replace(
    /:\s*(true|false|null)/g, // boolean/null values
    ': <span class="text-purple-400">$1</span>'
  )

  return (
    <pre
      className="text-xs text-gray-300 font-mono whitespace-pre-wrap break-words"
      dangerouslySetInnerHTML={{ __html: highlighted }}
    />
  )
}

// Collapsible section component
function CollapsibleSection({
  title,
  defaultOpen = false,
  badge,
  children,
  onCopy,
  copyKey,
  copiedKey,
}: {
  title: string
  defaultOpen?: boolean
  badge?: string
  children: React.ReactNode
  onCopy?: () => void
  copyKey?: string
  copiedKey?: string | null
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="border border-dark-800 rounded-lg overflow-hidden">
      <div
        className="flex items-center justify-between px-3 py-2 bg-dark-800/50 cursor-pointer hover:bg-dark-800/80"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown size={14} className="text-dark-400" /> : <ChevronRight size={14} className="text-dark-400" />}
          <span className="text-xs font-medium text-dark-300">{title}</span>
          {badge && <span className="text-xs px-1.5 py-0.5 bg-dark-700 text-dark-400 rounded">{badge}</span>}
        </div>
        {onCopy && (
          <button
            onClick={(e) => { e.stopPropagation(); onCopy() }}
            className="p-1 hover:bg-dark-700 rounded"
            title="Copy to clipboard"
          >
            {copiedKey === copyKey ? <Check size={12} className="text-green-400" /> : <Copy size={12} className="text-dark-400" />}
          </button>
        )}
      </div>
      {open && (
        <div className="p-3 bg-dark-950">
          {children}
        </div>
      )}
    </div>
  )
}

// OODA Phase type
interface OodaPhase {
  duration_ms: number
  output: Record<string, unknown>
}

// OODA Pipeline Visualization (SPEC-26)
function OodaPipeline({ phases }: { phases: Record<string, OodaPhase> }) {
  const phaseConfig = [
    { key: 'observe', label: 'Observe', color: 'sky' },
    { key: 'orient', label: 'Orient', color: 'violet' },
    { key: 'decide', label: 'Decide', color: 'amber' },
    { key: 'act', label: 'Act', color: 'emerald' },
  ]

  const totalMs = phaseConfig.reduce((sum, p) => sum + (phases[p.key]?.duration_ms || 0), 0)

  const colorMap: Record<string, { bg: string; border: string; text: string; bar: string }> = {
    sky: { bg: 'bg-sky-500/10', border: 'border-sky-500/30', text: 'text-sky-400', bar: 'bg-sky-500' },
    violet: { bg: 'bg-violet-500/10', border: 'border-violet-500/30', text: 'text-violet-400', bar: 'bg-violet-500' },
    amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', bar: 'bg-amber-500' },
    emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', bar: 'bg-emerald-500' },
  }

  return (
    <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-white">OODA Pipeline</h3>
        <span className="text-xs text-dark-400">Total: {totalMs}ms</span>
      </div>

      {/* Phase boxes connected by arrows */}
      <div className="flex items-center gap-1 mb-4">
        {phaseConfig.map((phase, idx) => {
          const data = phases[phase.key]
          const c = colorMap[phase.color]
          return (
            <div key={phase.key} className="flex items-center gap-1 flex-1">
              <div className={`flex-1 rounded-lg border ${c.border} ${c.bg} p-3 text-center`}>
                <div className={`text-xs font-medium ${c.text}`}>{phase.label}</div>
                <div className="text-lg font-bold text-white mt-1">
                  {data ? `${data.duration_ms}ms` : '-'}
                </div>
              </div>
              {idx < phaseConfig.length - 1 && (
                <div className="text-dark-600 text-xs">→</div>
              )}
            </div>
          )
        })}
      </div>

      {/* Timing bar */}
      {totalMs > 0 && (
        <div className="h-2 rounded-full overflow-hidden flex bg-dark-800">
          {phaseConfig.map((phase) => {
            const data = phases[phase.key]
            if (!data || data.duration_ms === 0) return null
            const pct = (data.duration_ms / totalMs) * 100
            const c = colorMap[phase.color]
            return (
              <div
                key={phase.key}
                className={`${c.bar} h-full`}
                style={{ width: `${Math.max(pct, 1)}%` }}
                title={`${phase.label}: ${data.duration_ms}ms (${pct.toFixed(0)}%)`}
              />
            )
          })}
        </div>
      )}

      {/* Phase outputs */}
      <div className="grid grid-cols-4 gap-2 mt-3">
        {phaseConfig.map((phase) => {
          const data = phases[phase.key]
          if (!data?.output || Object.keys(data.output).length === 0) return (
            <div key={phase.key} className="text-xs text-dark-600 text-center">-</div>
          )
          const c = colorMap[phase.color]
          return (
            <div key={phase.key} className="text-center">
              {Object.entries(data.output).map(([k, v]) => (
                <div key={k} className="text-xs">
                  <span className="text-dark-500">{k}: </span>
                  <span className={c.text}>{typeof v === 'string' ? (v.length > 30 ? v.slice(0, 30) + '...' : v) : JSON.stringify(v)}</span>
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Replay Options Panel
function ReplayOptionsPanel({
  sessionId,
  attempts,
  onReplayStarted,
}: {
  sessionId: string
  attempts: SessionDetailResponse['attempts']
  onReplayStarted: (replayId: string, data: any) => void
}) {
  const [open, setOpen] = useState(false)
  const [dryRun, setDryRun] = useState(true)
  const [model, setModel] = useState('')
  const [temperature, setTemperature] = useState(0.3)
  const [maxTokens, setMaxTokens] = useState('')
  const [paramOverrides, setParamOverrides] = useState<Record<string, string>>({})
  const [replaying, setReplaying] = useState(false)

  // Build initial params from first attempt
  const firstAttemptParams = attempts.length > 0 ? (attempts[0].params as Record<string, unknown>) : {}

  const handleParamChange = (key: string, value: string) => {
    setParamOverrides(prev => ({ ...prev, [key]: value }))
  }

  const handleReplay = async () => {
    setReplaying(true)
    try {
      const overrides: Record<string, any> = {}
      if (model) overrides.llm_model = model
      if (temperature !== 0.3) overrides.llm_temperature = temperature
      if (maxTokens) overrides.llm_max_tokens = parseInt(maxTokens)

      // Build action_params_override from changed params
      const changedParams: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(paramOverrides)) {
        if (v !== '' && v !== String(firstAttemptParams[k] ?? '')) {
          // Try to parse as number or keep as string
          const num = Number(v)
          changedParams[k] = !isNaN(num) && v.trim() !== '' ? num : v
        }
      }
      if (Object.keys(changedParams).length > 0) {
        overrides.action_params_override = changedParams
      }

      const hasOverrides = Object.keys(overrides).length > 0

      const result = await debugApi.replaySession({
        session_id: sessionId,
        overrides: hasOverrides ? overrides : undefined,
        dry_run: dryRun,
      })
      onReplayStarted(result.replay.replay_id, result)
    } catch (error: any) {
      console.error('Replay failed:', error)
      alert(error.response?.data?.detail || 'Replay failed')
    } finally {
      setReplaying(false)
    }
  }

  if (!open) {
    return (
      <Button
        variant="default"
        size="sm"
        onClick={() => setOpen(true)}
        className="bg-primary-600 hover:bg-primary-700"
      >
        <Play className="w-4 h-4 mr-2" />
        Replay Options
      </Button>
    )
  }

  return (
    <div className="bg-dark-900 border border-primary-500/30 rounded-lg p-4 mt-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-white">Replay Options</h3>
        <button onClick={() => setOpen(false)} className="text-dark-400 hover:text-white text-xs">Close</button>
      </div>

      {/* Mode */}
      <div className="flex items-center gap-4 mb-4">
        <span className="text-xs text-gray-400 w-20">Mode:</span>
        <label className="flex items-center gap-1.5 text-sm cursor-pointer">
          <input type="radio" checked={dryRun} onChange={() => setDryRun(true)} className="accent-primary-500" />
          <span className="text-gray-300">Dry Run</span>
          <span className="text-xs text-gray-500">(no execute)</span>
        </label>
        <label className="flex items-center gap-1.5 text-sm cursor-pointer">
          <input type="radio" checked={!dryRun} onChange={() => setDryRun(false)} className="accent-primary-500" />
          <span className="text-gray-300">Live Replay</span>
          <span className="text-xs text-gray-500">(execute)</span>
        </label>
      </div>

      {/* Overrides */}
      <div className="space-y-3 mb-4">
        <div className="flex items-center gap-4">
          <span className="text-xs text-gray-400 w-20">Model:</span>
          <input
            value={model}
            onChange={e => setModel(e.target.value)}
            placeholder="e.g. deepseek-chat (leave empty = same)"
            className="flex-1 bg-dark-950 border border-dark-800 text-white rounded px-3 py-1.5 text-sm"
          />
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-gray-400 w-20">Temperature:</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={temperature}
            onChange={e => setTemperature(parseFloat(e.target.value))}
            className="flex-1 accent-primary-500"
          />
          <span className="text-sm text-white w-8">{temperature}</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-gray-400 w-20">Max Tokens:</span>
          <input
            value={maxTokens}
            onChange={e => setMaxTokens(e.target.value)}
            placeholder="e.g. 4096 (leave empty = default)"
            className="flex-1 bg-dark-950 border border-dark-800 text-white rounded px-3 py-1.5 text-sm"
          />
        </div>
      </div>

      {/* Param Overrides */}
      {Object.keys(firstAttemptParams).length > 0 && (
        <div className="mb-4">
          <div className="text-xs text-gray-400 mb-2">Parameter Overrides:</div>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {Object.entries(firstAttemptParams).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2">
                <span className="text-xs text-sky-400 font-mono w-32 truncate" title={key}>{key}:</span>
                <span className="text-xs text-gray-500">{String(val ?? '')}</span>
                <span className="text-xs text-gray-600">→</span>
                <input
                  value={paramOverrides[key] ?? ''}
                  onChange={e => handleParamChange(key, e.target.value)}
                  placeholder={String(val ?? '')}
                  className="flex-1 bg-dark-950 border border-dark-800 text-white rounded px-2 py-1 text-xs"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Start Button */}
      <Button
        onClick={handleReplay}
        disabled={replaying}
        className={`w-full ${dryRun ? 'bg-primary-600 hover:bg-primary-700' : 'bg-amber-600 hover:bg-amber-700'}`}
      >
        <Play className="w-4 h-4 mr-2" />
        {replaying ? 'Replaying...' : dryRun ? 'Start Dry Run' : 'Start Live Replay'}
      </Button>
    </div>
  )
}

export default function SessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<SessionDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState<string | null>(null)
  const [selectedInteraction, setSelectedInteraction] = useState<LLMInteraction | null>(null)

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

  const handleReplayStarted = (replayId: string, replayData: any) => {
    navigate(`/debug/replay/${replayId}`, { state: { replayData } })
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

  const { session, attempts, llm_interactions = [] } = data

  // Extract structured prompt parts if available
  const promptParts = session.llm_prompt_parts as Record<string, any> | null
  const responseParsed = session.llm_response_parsed as Record<string, any> | null

  // Determine whether to show dual-track timeline
  const hasOodaPhases = session.metadata && (session.metadata as any).ooda_phases
  const hasLLMInteractions = llm_interactions.length > 0

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
        <Button
          variant="outline"
          size="sm"
          onClick={loadData}
          className="border-gray-700 text-gray-300 hover:bg-gray-800"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Replay Options Panel */}
      {data && (
        <ReplayOptionsPanel
          sessionId={sessionId!}
          attempts={data.attempts}
          onReplayStarted={handleReplayStarted}
        />
      )}

      {/* Session Overview */}
      <div className={`grid ${hasLLMInteractions ? 'grid-cols-6' : 'grid-cols-5'} gap-4 mb-6`}>
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
          <div className="text-gray-400 text-xs uppercase">Total Time</div>
          <div className="text-lg font-bold text-white">
            {session.execution_time_ms ? `${session.execution_time_ms}ms` : '-'}
          </div>
        </div>
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs uppercase">LLM Latency</div>
          <div className="text-lg font-bold text-white">
            {session.llm_latency_ms ? `${session.llm_latency_ms}ms` : '-'}
          </div>
        </div>
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs uppercase">LLM Tokens</div>
          <div className="text-lg font-bold text-white">
            {hasLLMInteractions
              ? llm_interactions.reduce((sum, i) => sum + (i.tokens_total || 0), 0) || session.llm_tokens_used || '-'
              : session.llm_tokens_used || '-'}
          </div>
        </div>
        {hasLLMInteractions && (
          <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
            <div className="text-gray-400 text-xs uppercase">LLM Calls</div>
            <div className="text-lg font-bold text-white">{llm_interactions.length}</div>
          </div>
        )}
        <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs uppercase">Attempts</div>
          <div className="text-lg font-bold text-white">{attempts.length}</div>
        </div>
      </div>

      {/* OODA + LLM Pipeline Visualization */}
      {hasLLMInteractions && hasOodaPhases ? (
        <div className="mb-6">
          <DualTrackTimeline
            oodaPhases={(session.metadata as any).ooda_phases as Record<string, OodaPhase>}
            llmInteractions={llm_interactions}
            onSelectInteraction={(i) => setSelectedInteraction(
              selectedInteraction?.interaction_id === i.interaction_id ? null : i
            )}
            selectedInteractionId={selectedInteraction?.interaction_id || null}
          />
          {selectedInteraction && (
            <LLMInteractionDetail
              interaction={selectedInteraction}
              onClose={() => setSelectedInteraction(null)}
            />
          )}
        </div>
      ) : hasOodaPhases ? (
        <div className="mb-6">
          <OodaPipeline phases={(session.metadata as any).ooda_phases as Record<string, OodaPhase>} />
        </div>
      ) : null}

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
            {session.schema_shaping && (
              <div>
                <div className="text-xs text-gray-400 mb-1">Schema Shaping</div>
                <SchemaSelectionPanel shaping={session.schema_shaping} />
              </div>
            )}
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
      </div>

      {/* Legacy LLM Interaction — only shown for old sessions without per-call tracking */}
      {!hasLLMInteractions && (
      <div className="mt-6 bg-dark-900 border border-dark-800 rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-white">LLM Interaction</h3>
          <div className="flex items-center gap-3 text-xs text-dark-400">
            {session.llm_model && (
              <span className="px-2 py-1 bg-dark-800 rounded">Model: <span className="text-sky-400">{session.llm_model}</span></span>
            )}
            {session.llm_tokens_used && (
              <span className="px-2 py-1 bg-dark-800 rounded">Tokens: <span className="text-amber-400">{session.llm_tokens_used.toLocaleString()}</span></span>
            )}
            {session.llm_latency_ms && (
              <span className="px-2 py-1 bg-dark-800 rounded">Latency: <span className="text-emerald-400">{(session.llm_latency_ms / 1000).toFixed(1)}s</span></span>
            )}
          </div>
        </div>

        <div className="space-y-3">
          {/* Structured Prompt Parts (if available from SPEC-08 backend) */}
          {promptParts ? (
            <>
              {promptParts.system_prompt && (
                <CollapsibleSection
                  title="System Prompt"
                  badge={`${String(promptParts.system_prompt).length} chars`}
                  onCopy={() => copyToClipboard(String(promptParts.system_prompt), 'sys-prompt')}
                  copyKey="sys-prompt"
                  copiedKey={copied}
                >
                  <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap break-words">
                    {String(promptParts.system_prompt)}
                  </pre>
                </CollapsibleSection>
              )}
              {promptParts.entity_context && (
                <CollapsibleSection
                  title="Entity Context"
                  onCopy={() => copyToClipboard(String(promptParts.entity_context), 'entity-ctx')}
                  copyKey="entity-ctx"
                  copiedKey={copied}
                >
                  <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap break-words">
                    {String(promptParts.entity_context)}
                  </pre>
                </CollapsibleSection>
              )}
              {promptParts.date_context && (
                <CollapsibleSection
                  title="Date Context"
                  defaultOpen
                  onCopy={() => copyToClipboard(String(promptParts.date_context), 'date-ctx')}
                  copyKey="date-ctx"
                  copiedKey={copied}
                >
                  <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap break-words">
                    {String(promptParts.date_context)}
                  </pre>
                </CollapsibleSection>
              )}
              {promptParts.conversation_history && (
                <CollapsibleSection
                  title="Conversation History"
                  badge={Array.isArray(promptParts.conversation_history) ? `${promptParts.conversation_history.length} msgs` : undefined}
                  onCopy={() => copyToClipboard(
                    typeof promptParts.conversation_history === 'string'
                      ? promptParts.conversation_history
                      : formatJson(promptParts.conversation_history),
                    'conv-hist'
                  )}
                  copyKey="conv-hist"
                  copiedKey={copied}
                >
                  <JsonHighlight data={promptParts.conversation_history} />
                </CollapsibleSection>
              )}
              {promptParts.user_input && (
                <CollapsibleSection
                  title="User Input"
                  defaultOpen
                  onCopy={() => copyToClipboard(String(promptParts.user_input), 'user-input')}
                  copyKey="user-input"
                  copiedKey={copied}
                >
                  <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap break-words">
                    {String(promptParts.user_input)}
                  </pre>
                </CollapsibleSection>
              )}
            </>
          ) : (
            /* Fallback: show full prompt if structured parts not available */
            <CollapsibleSection
              title="Full Prompt"
              badge={session.llm_prompt ? `${session.llm_prompt.length} chars` : undefined}
              onCopy={session.llm_prompt ? () => copyToClipboard(session.llm_prompt!, 'full-prompt') : undefined}
              copyKey="full-prompt"
              copiedKey={copied}
            >
              <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap break-words">
                {session.llm_prompt || 'None'}
              </pre>
            </CollapsibleSection>
          )}

          {/* LLM Raw Response */}
          <CollapsibleSection
            title="LLM Raw Response"
            defaultOpen
            onCopy={session.llm_response ? () => copyToClipboard(session.llm_response!, 'raw-resp') : undefined}
            copyKey="raw-resp"
            copiedKey={copied}
          >
            <JsonHighlight data={session.llm_response || 'None'} />
          </CollapsibleSection>

          {/* Parsed Decision (from SPEC-08 backend) */}
          {responseParsed && (
            <CollapsibleSection
              title="Parsed Decision"
              defaultOpen
              badge={responseParsed.action_type ? String(responseParsed.action_type) : undefined}
              onCopy={() => copyToClipboard(formatJson(responseParsed), 'parsed-resp')}
              copyKey="parsed-resp"
              copiedKey={copied}
            >
              <div className="space-y-2">
                {responseParsed.action_type && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-dark-400">Action:</span>
                    <span className="px-2 py-0.5 bg-sky-500/20 text-sky-400 rounded font-mono">{String(responseParsed.action_type)}</span>
                  </div>
                )}
                {responseParsed.entity && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-dark-400">Entity:</span>
                    <span className="text-gray-300 font-mono">{String(responseParsed.entity)}</span>
                  </div>
                )}
                {responseParsed.params && (
                  <div className="mt-2">
                    <div className="text-xs text-dark-400 mb-1">Parameters:</div>
                    <JsonHighlight data={responseParsed.params} />
                  </div>
                )}
              </div>
            </CollapsibleSection>
          )}
        </div>
      </div>
      )}

      {/* Result Section */}
      <div className="mt-6 bg-dark-900 border border-dark-800 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-white">Final Result</h3>
          {session.final_result && (
            <button
              onClick={() => copyToClipboard(formatJson(session.final_result), 'final-result')}
              className="p-1 hover:bg-dark-700 rounded"
            >
              {copied === 'final-result' ? <Check size={14} className="text-green-400" /> : <Copy size={14} className="text-dark-400" />}
            </button>
          )}
        </div>
        <div className="bg-dark-950 rounded p-3 overflow-auto max-h-72">
          <JsonHighlight data={session.final_result || 'None'} />
        </div>
      </div>

      {/* Attempts Timeline */}
      <div className="mt-6 bg-dark-900 border border-dark-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-white mb-3">Execution Attempts</h3>
        <div className="space-y-3">
          {attempts.map((attempt) => (
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
                    <JsonHighlight data={attempt.params} />
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Result</div>
                  <div className="font-mono text-gray-300 bg-dark-950 p-2 rounded mt-1 max-h-32 overflow-auto">
                    {attempt.result ? <JsonHighlight data={attempt.result} /> : 'None'}
                  </div>
                </div>
              </div>
              {attempt.error && (
                <div className="mt-2">
                  <div className="text-gray-400 text-xs">Error</div>
                  <div className="font-mono text-red-400 bg-dark-950 p-2 rounded mt-1 text-xs">
                    <JsonHighlight data={attempt.error} />
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
