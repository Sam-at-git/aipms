/**
 * DualTrackTimeline Component (SPEC-35)
 *
 * Dual-track visualization:
 * - Upper track: OODA phases (Observe -> Orient -> Decide -> Act)
 * - Lower track: LLM calls, connected to their parent OODA phase
 */
import type { LLMInteraction } from '../types'

interface OodaPhase {
  duration_ms: number
  output: Record<string, unknown>
}

interface DualTrackTimelineProps {
  oodaPhases: Record<string, OodaPhase>
  llmInteractions: LLMInteraction[]
  onSelectInteraction: (interaction: LLMInteraction) => void
  selectedInteractionId: string | null
}

const phaseConfig = [
  { key: 'observe', label: 'Observe', color: 'sky' },
  { key: 'orient', label: 'Orient', color: 'violet' },
  { key: 'decide', label: 'Decide', color: 'amber' },
  { key: 'act', label: 'Act', color: 'emerald' },
] as const

const colorMap: Record<string, {
  bg: string; border: string; text: string; bar: string;
  dotBorder: string; dotBg: string; selectedBorder: string;
}> = {
  sky: {
    bg: 'bg-sky-500/10', border: 'border-sky-500/30', text: 'text-sky-400',
    bar: 'bg-sky-500', dotBorder: 'border-sky-500/50', dotBg: 'bg-sky-500/20',
    selectedBorder: 'border-sky-400',
  },
  violet: {
    bg: 'bg-violet-500/10', border: 'border-violet-500/30', text: 'text-violet-400',
    bar: 'bg-violet-500', dotBorder: 'border-violet-500/50', dotBg: 'bg-violet-500/20',
    selectedBorder: 'border-violet-400',
  },
  amber: {
    bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400',
    bar: 'bg-amber-500', dotBorder: 'border-amber-500/50', dotBg: 'bg-amber-500/20',
    selectedBorder: 'border-amber-400',
  },
  emerald: {
    bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400',
    bar: 'bg-emerald-500', dotBorder: 'border-emerald-500/50', dotBg: 'bg-emerald-500/20',
    selectedBorder: 'border-emerald-400',
  },
}

const callTypeLabels: Record<string, string> = {
  topic_relevance: 'Topic',
  chat: 'Chat',
  extract_params: 'Extract',
  parse_followup: 'Parse',
  format_result: 'Format',
  tool_round_0: 'Tool #1',
  tool_round_1: 'Tool #2',
  tool_round_2: 'Tool #3',
}

function formatTokens(n: number | null): string {
  if (n == null) return '-'
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export default function DualTrackTimeline({
  oodaPhases,
  llmInteractions,
  onSelectInteraction,
  selectedInteractionId,
}: DualTrackTimelineProps) {
  const totalMs = phaseConfig.reduce(
    (sum, p) => sum + (oodaPhases[p.key]?.duration_ms || 0), 0
  )

  // Group interactions by OODA phase
  const interactionsByPhase: Record<string, LLMInteraction[]> = {}
  for (const interaction of llmInteractions) {
    const phase = interaction.ooda_phase
    if (!interactionsByPhase[phase]) interactionsByPhase[phase] = []
    interactionsByPhase[phase].push(interaction)
  }

  // Calculate total tokens from interactions
  const totalTokens = llmInteractions.reduce(
    (sum, i) => sum + (i.tokens_total || 0), 0
  )

  return (
    <div className="bg-dark-900 border border-dark-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-white">OODA + LLM Pipeline</h3>
        <div className="flex items-center gap-3 text-xs text-dark-400">
          <span>Total: <span className="text-white font-medium">{totalMs}ms</span></span>
          <span>LLM Calls: <span className="text-white font-medium">{llmInteractions.length}</span></span>
          {totalTokens > 0 && (
            <span>Tokens: <span className="text-white font-medium">{formatTokens(totalTokens)}</span></span>
          )}
        </div>
      </div>

      {/* Upper track: OODA phases */}
      <div className="flex items-center gap-1 mb-2">
        {phaseConfig.map((phase, idx) => {
          const data = oodaPhases[phase.key]
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
                <div className="text-dark-600 text-xs">{'\u2192'}</div>
              )}
            </div>
          )
        })}
      </div>

      {/* Connection lines (dashed) */}
      <div className="flex items-stretch gap-1 h-6">
        {phaseConfig.map((phase) => {
          const interactions = interactionsByPhase[phase.key] || []
          const c = colorMap[phase.color]
          return (
            <div key={phase.key} className="flex-1 flex justify-center">
              {interactions.length > 0 && (
                <div
                  className={`border-l-2 border-dashed ${c.dotBorder} h-full`}
                  style={{ marginLeft: '50%' }}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* Lower track: LLM calls */}
      <div className="flex items-start gap-1">
        {phaseConfig.map((phase) => {
          const interactions = interactionsByPhase[phase.key] || []
          const color = phase.color
          const c = colorMap[color]

          if (interactions.length === 0) {
            return <div key={phase.key} className="flex-1" />
          }

          return (
            <div key={phase.key} className="flex-1 flex flex-col gap-1.5">
              {interactions.map((interaction) => {
                const isSelected = selectedInteractionId === interaction.interaction_id
                return (
                  <button
                    key={interaction.interaction_id}
                    onClick={() => onSelectInteraction(interaction)}
                    className={`w-full rounded-lg border p-2 text-left transition-all cursor-pointer
                      ${isSelected
                        ? `${c.selectedBorder} ${c.bg} ring-1 ring-${color}-400/30`
                        : `${c.dotBorder} ${c.dotBg} hover:${c.border}`
                      }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-xs font-medium ${c.text}`}>
                        #{interaction.sequence_number} {callTypeLabels[interaction.call_type] || interaction.call_type}
                      </span>
                      {!interaction.success && (
                        <span className="text-xs text-red-400 font-medium">ERR</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-dark-400">
                      <span>{interaction.latency_ms}ms</span>
                      {interaction.tokens_total != null && (
                        <span>{formatTokens(interaction.tokens_total)} tok</span>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          )
        })}
      </div>

      {/* Timing bar */}
      {totalMs > 0 && (
        <div className="h-2 rounded-full overflow-hidden flex bg-dark-800 mt-4">
          {phaseConfig.map((phase) => {
            const data = oodaPhases[phase.key]
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
    </div>
  )
}
