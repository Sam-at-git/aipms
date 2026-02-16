/**
 * LLMInteractionDetail Component (SPEC-36)
 *
 * Detail panel shown when an LLM interaction node is clicked in the
 * DualTrackTimeline. Shows prompt, response, tokens, and errors.
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight, Copy, Check, X } from 'lucide-react'
import type { LLMInteraction } from '../types'

interface LLMInteractionDetailProps {
  interaction: LLMInteraction
  onClose: () => void
}

const phaseColors: Record<string, { bg: string; text: string; badge: string }> = {
  orient: { bg: 'bg-violet-500/10', text: 'text-violet-400', badge: 'bg-violet-500/20 text-violet-400' },
  decide: { bg: 'bg-amber-500/10', text: 'text-amber-400', badge: 'bg-amber-500/20 text-amber-400' },
  act: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', badge: 'bg-emerald-500/20 text-emerald-400' },
  observe: { bg: 'bg-sky-500/10', text: 'text-sky-400', badge: 'bg-sky-500/20 text-sky-400' },
}

function CollapsibleBlock({
  title,
  defaultOpen = false,
  content,
  badge,
}: {
  title: string
  defaultOpen?: boolean
  content: string | null
  badge?: string
}) {
  const [open, setOpen] = useState(defaultOpen)
  const [copied, setCopied] = useState(false)

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (content) {
      navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  // Try to pretty-print JSON
  let displayContent = content || '(empty)'
  try {
    if (content) {
      const parsed = JSON.parse(content)
      displayContent = JSON.stringify(parsed, null, 2)
    }
  } catch {
    // not JSON, use as-is
  }

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
        {content && (
          <button
            onClick={handleCopy}
            className="p-1 hover:bg-dark-700 rounded"
            title="Copy to clipboard"
          >
            {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} className="text-dark-400" />}
          </button>
        )}
      </div>
      {open && (
        <div className="p-3 bg-dark-950 max-h-96 overflow-auto">
          <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap break-words">
            {displayContent}
          </pre>
        </div>
      )}
    </div>
  )
}

export default function LLMInteractionDetail({ interaction, onClose }: LLMInteractionDetailProps) {
  const colors = phaseColors[interaction.ooda_phase] || phaseColors.decide

  return (
    <div className="bg-dark-900 border border-dark-800 rounded-lg p-4 mt-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className={`text-xs font-medium px-2 py-1 rounded ${colors.badge}`}>
            {interaction.ooda_phase} / {interaction.call_type}
          </span>
          {interaction.model && (
            <span className="text-xs px-2 py-1 bg-dark-800 rounded text-dark-400">
              Model: <span className="text-sky-400">{interaction.model}</span>
            </span>
          )}
          <span className="text-xs px-2 py-1 bg-dark-800 rounded text-dark-400">
            Latency: <span className="text-emerald-400">{interaction.latency_ms}ms</span>
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-dark-800 rounded text-dark-400 hover:text-white"
        >
          <X size={16} />
        </button>
      </div>

      {/* Token breakdown */}
      {(interaction.tokens_input != null || interaction.tokens_output != null) && (
        <div className="flex items-center gap-4 mb-4 text-xs">
          {interaction.tokens_input != null && (
            <span className="text-dark-400">
              Input: <span className="text-amber-400 font-medium">{interaction.tokens_input.toLocaleString()}</span> tokens
            </span>
          )}
          {interaction.tokens_output != null && (
            <span className="text-dark-400">
              Output: <span className="text-amber-400 font-medium">{interaction.tokens_output.toLocaleString()}</span> tokens
            </span>
          )}
          {interaction.tokens_total != null && (
            <span className="text-dark-400">
              Total: <span className="text-white font-medium">{interaction.tokens_total.toLocaleString()}</span> tokens
            </span>
          )}
          {interaction.temperature != null && (
            <span className="text-dark-400">
              Temp: <span className="text-dark-300">{interaction.temperature}</span>
            </span>
          )}
        </div>
      )}

      {/* Error display */}
      {!interaction.success && interaction.error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
          <div className="text-xs font-medium text-red-400 mb-1">Error</div>
          <pre className="text-xs text-red-300 font-mono whitespace-pre-wrap">{interaction.error}</pre>
        </div>
      )}

      {/* Collapsible sections */}
      <div className="space-y-2">
        <CollapsibleBlock
          title="Prompt"
          content={interaction.prompt}
          badge={interaction.prompt ? `${interaction.prompt.length} chars` : undefined}
        />
        <CollapsibleBlock
          title="Response"
          defaultOpen
          content={interaction.response}
          badge={interaction.response ? `${interaction.response.length} chars` : undefined}
        />
        {interaction.response_parsed && (
          <CollapsibleBlock
            title="Parsed Response"
            defaultOpen
            content={interaction.response_parsed}
          />
        )}
      </div>
    </div>
  )
}
