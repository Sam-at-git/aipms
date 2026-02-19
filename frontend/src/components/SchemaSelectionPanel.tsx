/**
 * SchemaSelectionPanel Component (SPEC-P07)
 *
 * Visualizes schema shaping strategy and metadata in the Debug panel.
 * Shows: strategy badge, entity/action counts, query schema inclusion.
 */
import type { SchemaShaping } from '../types'

interface SchemaSelectionPanelProps {
  shaping: SchemaShaping
}

const strategyConfig: Record<string, { label: string; color: string; bg: string; border: string }> = {
  discovery: { label: 'Discovery', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' },
  inference: { label: 'Inference', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' },
  role_filter: { label: 'Role Filter', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30' },
  full: { label: 'Full', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30' },
}

export default function SchemaSelectionPanel({ shaping }: SchemaSelectionPanelProps) {
  const config = strategyConfig[shaping.strategy] || strategyConfig.full

  const fallbackChain = (shaping.metadata?.fallback_chain as string[]) || []
  const indexedActions = shaping.metadata?.indexed_actions as number | undefined

  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} p-3 space-y-2`}>
      {/* Strategy badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${config.bg} ${config.color} border ${config.border}`}>
            {config.label}
          </span>
          {shaping.include_query_schema && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/30">
              +Query Schema
            </span>
          )}
        </div>
      </div>

      {/* Counts */}
      <div className="flex gap-4 text-xs">
        <div>
          <span className="text-dark-400">Actions: </span>
          <span className="text-white font-medium">
            {shaping.actions_injected != null ? shaping.actions_injected : 'all'}
          </span>
        </div>
        <div>
          <span className="text-dark-400">Entities: </span>
          <span className="text-white font-medium">
            {shaping.entities_injected != null ? shaping.entities_injected : 'all'}
          </span>
        </div>
        {indexedActions != null && (
          <div>
            <span className="text-dark-400">Indexed: </span>
            <span className="text-white font-medium">{indexedActions}</span>
          </div>
        )}
      </div>

      {/* Fallback chain */}
      {fallbackChain.length > 0 && (
        <div className="text-xs text-dark-400">
          Fallbacks: {fallbackChain.map((step, i) => (
            <span key={i}>
              {i > 0 && ' \u2192 '}
              <span className="text-dark-300">{step}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
