import React, { useMemo, useCallback, useState } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { StateMachine, StateDefinition } from '../types'

// Map backend color names to hex
const colorHex: Record<string, string> = {
  green: '#10b981',
  red: '#ef4444',
  yellow: '#eab308',
  gray: '#6b7280',
  blue: '#3b82f6',
  orange: '#f97316',
  purple: '#8b5cf6',
}

// Custom state node
function StateNode({ data }: { data: { label: string; value: string; color: string; isInitial: boolean; isHighlighted: boolean | null } }) {
  const hex = colorHex[data.color] || colorHex.gray
  const dimmed = data.isHighlighted === false

  return (
    <div
      className="relative transition-opacity duration-200"
      style={{ opacity: dimmed ? 0.3 : 1 }}
    >
      <Handle type="target" position={Position.Left} style={{ background: hex, border: 'none', width: 6, height: 6 }} />
      <div
        className="px-5 py-3 rounded-xl text-center min-w-[100px]"
        style={{
          border: `2px solid ${hex}`,
          borderWidth: data.isInitial ? 3 : 2,
          backgroundColor: `${hex}15`,
          boxShadow: data.isInitial ? `0 0 12px ${hex}40` : 'none',
        }}
      >
        <div className="text-white font-medium text-sm">{data.label}</div>
        <div className="text-[10px] text-gray-400 font-mono mt-0.5">{data.value}</div>
      </div>
      <Handle type="source" position={Position.Right} style={{ background: hex, border: 'none', width: 6, height: 6 }} />
    </div>
  )
}

const nodeTypes = { stateNode: StateNode }

interface StateMachineGraphProps {
  machine: StateMachine
}

export default function StateMachineGraph({ machine }: StateMachineGraphProps) {
  const [highlightedState, setHighlightedState] = useState<string | null>(null)

  // BFS layout from initial state
  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    const states = machine.states
    const transitions = machine.transitions

    // Build adjacency list
    const adj: Record<string, string[]> = {}
    for (const s of states) adj[s.value] = []
    for (const t of transitions) {
      if (adj[t.from]) adj[t.from].push(t.to)
    }

    // BFS for levels
    const levels: Record<string, number> = {}
    const visited = new Set<string>()
    const queue: string[] = [machine.initial_state]
    visited.add(machine.initial_state)
    levels[machine.initial_state] = 0

    while (queue.length > 0) {
      const current = queue.shift()!
      for (const next of (adj[current] || [])) {
        if (!visited.has(next)) {
          visited.add(next)
          levels[next] = (levels[current] || 0) + 1
          queue.push(next)
        }
      }
    }

    // Any unvisited states go to max level + 1
    const maxLevel = Math.max(0, ...Object.values(levels))
    for (const s of states) {
      if (!(s.value in levels)) {
        levels[s.value] = maxLevel + 1
      }
    }

    // Group by level and compute positions
    const byLevel: Record<number, StateDefinition[]> = {}
    for (const s of states) {
      const l = levels[s.value]
      if (!byLevel[l]) byLevel[l] = []
      byLevel[l].push(s)
    }

    const X_GAP = 220
    const Y_GAP = 100

    const nodes: Node[] = []
    for (const [levelStr, statesAtLevel] of Object.entries(byLevel)) {
      const level = Number(levelStr)
      const totalHeight = (statesAtLevel.length - 1) * Y_GAP
      statesAtLevel.forEach((s, idx) => {
        nodes.push({
          id: s.value,
          type: 'stateNode',
          position: { x: level * X_GAP + 50, y: idx * Y_GAP - totalHeight / 2 + 150 },
          data: {
            label: s.label,
            value: s.value,
            color: s.color || 'gray',
            isInitial: s.value === machine.initial_state,
            isHighlighted: null,
          },
        })
      })
    }

    const edges: Edge[] = transitions.map((t, i) => ({
      id: `e-${i}`,
      source: t.from,
      target: t.to,
      label: t.trigger_action || t.trigger,
      animated: false,
      style: { stroke: '#6b7280', strokeWidth: 1.5 },
      labelStyle: { fill: '#9ca3af', fontSize: 11 },
      labelBgStyle: { fill: '#1a1a2e', fillOpacity: 0.9 },
      labelBgPadding: [4, 2] as [number, number],
      markerEnd: { type: MarkerType.ArrowClosed, color: '#6b7280', width: 16, height: 16 },
    }))

    return { nodes, edges }
  }, [machine])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  // Highlight on node click
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    const clickedState = node.id
    const isAlreadyHighlighted = highlightedState === clickedState

    if (isAlreadyHighlighted) {
      // Clear highlighting
      setHighlightedState(null)
      setNodes(nds => nds.map(n => ({ ...n, data: { ...n.data, isHighlighted: null } })))
      setEdges(eds => eds.map(e => ({
        ...e,
        animated: false,
        style: { ...e.style, stroke: '#6b7280', strokeWidth: 1.5, opacity: 1 },
      })))
    } else {
      // Highlight outgoing transitions
      setHighlightedState(clickedState)
      const outgoingTargets = new Set(
        machine.transitions
          .filter(t => t.from === clickedState)
          .map(t => t.to)
      )

      setNodes(nds => nds.map(n => ({
        ...n,
        data: {
          ...n.data,
          isHighlighted: n.id === clickedState || outgoingTargets.has(n.id) ? true : false,
        },
      })))

      setEdges(eds => eds.map(e => {
        const isOutgoing = e.source === clickedState
        const hex = isOutgoing ? '#3b82f6' : '#6b7280'
        return {
          ...e,
          animated: isOutgoing,
          style: {
            ...e.style,
            stroke: hex,
            strokeWidth: isOutgoing ? 2.5 : 1.5,
            opacity: isOutgoing ? 1 : 0.2,
          },
        }
      }))
    }
  }, [highlightedState, machine.transitions, setNodes, setEdges])

  return (
    <div className="w-full h-[400px] bg-dark-950 rounded-lg border border-dark-700">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.5}
        maxZoom={2}
      >
        <Controls className="!bg-dark-800 !border-dark-700 [&>button]:!bg-dark-800 [&>button]:!border-dark-700 [&>button]:!text-dark-300 [&>button:hover]:!bg-dark-700" />
        <Background color="#333" gap={20} />
      </ReactFlow>
    </div>
  )
}
