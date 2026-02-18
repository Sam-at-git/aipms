import { create } from 'zustand'
import { ontologyApi } from '../services/api'
import type { OntologyDynamic, OntologyEntityKinetic, OntologyAction, StateMachine, StateDefinition } from '../types'

// Color mapping: backend color string → Tailwind classes
const COLOR_MAP: Record<string, { bg: string; text: string; dot: string }> = {
  green:  { bg: 'bg-emerald-500/20', text: 'text-emerald-400', dot: 'bg-emerald-500' },
  red:    { bg: 'bg-red-500/20',     text: 'text-red-400',     dot: 'bg-red-500' },
  yellow: { bg: 'bg-yellow-500/20',  text: 'text-yellow-400',  dot: 'bg-yellow-500' },
  gray:   { bg: 'bg-gray-500/20',    text: 'text-gray-400',    dot: 'bg-gray-500' },
  blue:   { bg: 'bg-blue-500/20',    text: 'text-blue-400',    dot: 'bg-blue-500' },
  orange: { bg: 'bg-orange-500/20',  text: 'text-orange-400',  dot: 'bg-orange-500' },
  purple: { bg: 'bg-purple-500/20',  text: 'text-purple-400',  dot: 'bg-purple-500' },
}

// Fallback status configs for when dynamic data isn't loaded
const FALLBACK_STATUS_CONFIGS: Record<string, Record<string, { label: string; color: string }>> = {
  Room: {
    vacant_clean:  { label: '空闲已清洁', color: 'green' },
    occupied:      { label: '入住中',     color: 'red' },
    vacant_dirty:  { label: '空闲待清洁', color: 'yellow' },
    out_of_order:  { label: '维修中',     color: 'gray' },
  },
  Reservation: {
    confirmed:   { label: '已确认', color: 'blue' },
    checked_in:  { label: '已入住', color: 'green' },
    completed:   { label: '已完成', color: 'gray' },
    cancelled:   { label: '已取消', color: 'red' },
    no_show:     { label: '未到店', color: 'orange' },
  },
  StayRecord: {
    active:      { label: '在住',   color: 'green' },
    checked_out: { label: '已退房', color: 'gray' },
  },
  Task: {
    pending:     { label: '待分配', color: 'gray' },
    assigned:    { label: '已分配', color: 'blue' },
    in_progress: { label: '进行中', color: 'yellow' },
    completed:   { label: '已完成', color: 'green' },
  },
}

export interface StatusConfig {
  label: string
  color: string
  class: string
  dotColor: string
}

interface OntologyState {
  dynamicData: OntologyDynamic | null
  kineticData: { entities: OntologyEntityKinetic[] } | null
  isReady: boolean
  _initializing: boolean

  initialize: () => Promise<void>
  fetchKinetic: () => Promise<void>
  getStatusConfig: (entity: string, value: string) => StatusConfig
  getStateMachine: (entity: string) => StateMachine | null
  getActionSchema: (actionType: string) => OntologyAction | null
}

const DEFAULT_STATUS: StatusConfig = {
  label: '未知',
  color: 'gray',
  class: 'bg-gray-500/20 text-gray-400',
  dotColor: 'bg-gray-500',
}

function buildStatusConfig(label: string, color: string): StatusConfig {
  const mapped = COLOR_MAP[color] || COLOR_MAP.gray
  return {
    label,
    color,
    class: `${mapped.bg} ${mapped.text}`,
    dotColor: mapped.dot,
  }
}

export const useOntologyStore = create<OntologyState>((set, get) => ({
  dynamicData: null,
  kineticData: null,
  isReady: false,
  _initializing: false,

  initialize: async () => {
    const state = get()
    if (state.isReady || state._initializing) return
    set({ _initializing: true })
    try {
      const dynamicData = await ontologyApi.getDynamic()
      set({ dynamicData, isReady: true, _initializing: false })
    } catch {
      // If backend unavailable, mark ready with null data (fallbacks will be used)
      set({ isReady: true, _initializing: false })
    }
  },

  fetchKinetic: async () => {
    if (get().kineticData) return
    try {
      const kineticData = await ontologyApi.getKinetic()
      set({ kineticData })
    } catch {
      // silently fail - kinetic data is optional
    }
  },

  getStatusConfig: (entity: string, value: string): StatusConfig => {
    const { dynamicData } = get()

    // Try dynamic data first
    if (dynamicData) {
      const sm = dynamicData.state_machines.find(s => s.entity === entity)
      if (sm) {
        const state = sm.states.find((s: StateDefinition) => s.value === value)
        if (state) {
          return buildStatusConfig(state.label, state.color || 'gray')
        }
      }
    }

    // Fallback to static config
    const fallback = FALLBACK_STATUS_CONFIGS[entity]?.[value]
    if (fallback) {
      return buildStatusConfig(fallback.label, fallback.color)
    }

    return DEFAULT_STATUS
  },

  getStateMachine: (entity: string): StateMachine | null => {
    const { dynamicData } = get()
    if (!dynamicData) return null
    return dynamicData.state_machines.find(s => s.entity === entity) || null
  },

  getActionSchema: (actionType: string): OntologyAction | null => {
    const { kineticData } = get()
    if (!kineticData) return null
    for (const entity of kineticData.entities) {
      const action = entity.actions.find(a => a.action_type === actionType)
      if (action) return action
    }
    return null
  },
}))
