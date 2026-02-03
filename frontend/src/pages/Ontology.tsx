import React, { useEffect, useState, useCallback, useMemo } from 'react'
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
import { ontologyApi, OntologySchema, OntologyStatistics } from '../services/api'
import { Database, RefreshCw } from 'lucide-react'

// Entity color mapping
const entityColors: Record<string, string> = {
  RoomType: '#8b5cf6',  // purple
  Room: '#3b82f6',      // blue
  Guest: '#10b981',     // green
  Reservation: '#f59e0b', // amber
  StayRecord: '#ef4444', // red
  Bill: '#ec4899',      // pink
  Task: '#06b6d4',      // cyan
  Employee: '#6366f1',  // indigo
}

// Custom node component
const EntityNode = ({ data }: { data: any }) => {
  const bgColor = entityColors[data.name] || '#6b7280'

  return (
    <div
      className="px-4 py-3 rounded-lg border-2 shadow-lg min-w-[140px]"
      style={{
        backgroundColor: `${bgColor}20`,
        borderColor: bgColor,
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-dark-400" />
      <div className="text-center">
        <div className="font-semibold text-white mb-1">{data.label}</div>
        <div className="text-xs text-dark-400">{data.name}</div>
        {data.total !== undefined && (
          <div
            className="mt-2 text-2xl font-bold"
            style={{ color: bgColor }}
          >
            {data.total}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-dark-400" />
    </div>
  )
}

const nodeTypes = {
  entityNode: EntityNode,
}

interface EntityDetailPanelProps {
  entity: OntologySchema['entities'][0]
  statistics: OntologyStatistics['entities'][string] | undefined
}

const EntityDetailPanel: React.FC<EntityDetailPanelProps> = ({ entity, statistics }) => {
  const bgColor = entityColors[entity.name] || '#6b7280'

  return (
    <div>
      <h3 className="text-lg font-semibold text-white mb-2" style={{ color: bgColor }}>
        {entity.description}
      </h3>
      <p className="text-dark-400 text-sm mb-4">{entity.name}</p>

      {/* Statistics */}
      {statistics && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-dark-300 mb-2">Statistics</h4>
          <div className="bg-dark-800 rounded p-3">
            <div className="text-2xl font-bold" style={{ color: bgColor }}>
              {statistics.total}
            </div>
            <div className="text-dark-400 text-sm">Total Count</div>

            {/* Status distribution */}
            {statistics.by_status && (
              <div className="mt-3 space-y-1">
                <div className="text-xs text-dark-500 uppercase tracking-wider mb-1">By Status</div>
                {Object.entries(statistics.by_status).map(([status, count]) => (
                  <div key={status} className="flex justify-between text-sm">
                    <span className="text-dark-400">{status}</span>
                    <span className="text-white">{count as number}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Tier distribution */}
            {statistics.by_tier && (
              <div className="mt-3 space-y-1">
                <div className="text-xs text-dark-500 uppercase tracking-wider mb-1">By Tier</div>
                {Object.entries(statistics.by_tier).map(([tier, count]) => (
                  <div key={tier} className="flex justify-between text-sm">
                    <span className="text-dark-400">{tier}</span>
                    <span className="text-white">{count as number}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Role distribution */}
            {statistics.by_role && (
              <div className="mt-3 space-y-1">
                <div className="text-xs text-dark-500 uppercase tracking-wider mb-1">By Role</div>
                {Object.entries(statistics.by_role).map(([role, count]) => (
                  <div key={role} className="flex justify-between text-sm">
                    <span className="text-dark-400">{role}</span>
                    <span className="text-white">{count as number}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Active count */}
            {statistics.active !== undefined && (
              <div className="mt-3 flex justify-between text-sm">
                <span className="text-dark-400">Active</span>
                <span className="text-green-400">{statistics.active}</span>
              </div>
            )}

            {/* Settled/Unsettled */}
            {statistics.settled !== undefined && (
              <div className="mt-3 space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-dark-400">Settled</span>
                  <span className="text-green-400">{statistics.settled}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-dark-400">Unsettled</span>
                  <span className="text-yellow-400">{statistics.unsettled}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Attributes list */}
      <div>
        <h4 className="text-sm font-medium text-dark-300 mb-2">Attributes</h4>
        <div className="space-y-2">
          {entity.attributes.map(attr => (
            <div
              key={attr.name}
              className="bg-dark-800 rounded p-2 text-sm"
            >
              <div className="flex items-center gap-2">
                <span className="text-white">{attr.name}</span>
                {attr.primary && (
                  <span className="text-xs bg-primary-500/20 text-primary-400 px-1 rounded">
                    PK
                  </span>
                )}
              </div>
              <div className="text-dark-400 text-xs mt-1">
                {attr.type}
                {attr.values && ` (${attr.values.slice(0, 3).join(', ')}${attr.values.length > 3 ? '...' : ''})`}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const Ontology: React.FC = () => {
  const [schema, setSchema] = useState<OntologySchema | null>(null)
  const [statistics, setStatistics] = useState<OntologyStatistics | null>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [schemaRes, statsRes] = await Promise.all([
        ontologyApi.getSchema(),
        ontologyApi.getStatistics()
      ])
      setSchema(schemaRes)
      setStatistics(statsRes)
      generateGraph(schemaRes, statsRes)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load ontology data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const generateGraph = useCallback((schema: OntologySchema, stats: OntologyStatistics) => {
    // Entity node layout (circular arrangement)
    const entityNodes: Node[] = schema.entities.map((entity, index) => {
      const angle = (2 * Math.PI * index) / schema.entities.length - Math.PI / 2
      const radius = 280
      const x = 400 + radius * Math.cos(angle)
      const y = 320 + radius * Math.sin(angle)

      const stat = stats.entities[entity.name]

      return {
        id: entity.name,
        type: 'entityNode',
        position: { x, y },
        data: {
          label: entity.description,
          name: entity.name,
          total: stat?.total || 0,
          attributes: entity.attributes
        }
      }
    })

    // Relationship edges
    const relationEdges: Edge[] = schema.relationships.map((rel, index) => ({
      id: `edge-${index}`,
      source: rel.from,
      target: rel.to,
      label: rel.label,
      type: 'smoothstep',
      animated: false,
      style: { stroke: '#6366f1', strokeWidth: 2 },
      labelStyle: { fill: '#9ca3af', fontSize: 11 },
      labelBgStyle: { fill: '#1f2937', fillOpacity: 0.8 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: '#6366f1',
      },
    }))

    setNodes(entityNodes)
    setEdges(relationEdges)
  }, [])

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedEntity(node.id)
  }, [])

  const selectedEntityData = useMemo(() => {
    if (!selectedEntity || !schema) return null
    return schema.entities.find(e => e.name === selectedEntity)
  }, [selectedEntity, schema])

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-primary-400 mx-auto mb-2" />
          <p className="text-dark-400">Loading ontology data...</p>
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
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Database className="w-6 h-6 text-primary-400" />
          <h1 className="text-xl font-semibold">Ontology View</h1>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-3 py-1.5 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors text-sm"
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Left: Graph */}
        <div className="flex-1 bg-dark-900 rounded-lg overflow-hidden">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.3}
            maxZoom={1.5}
          >
            <Controls className="!bg-dark-800 !border-dark-700" />
            <Background color="#374151" gap={20} />
          </ReactFlow>
        </div>

        {/* Right: Entity detail panel */}
        <div className="w-80 bg-dark-900 rounded-lg p-4 overflow-y-auto">
          {selectedEntityData && schema ? (
            <EntityDetailPanel
              entity={selectedEntityData}
              statistics={statistics?.entities[selectedEntity!]}
            />
          ) : (
            <div className="text-dark-400 text-center py-8">
              <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Click an entity to view details</p>
            </div>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-6 text-sm">
        <span className="text-dark-400">Entity Types:</span>
        {Object.entries(entityColors).map(([name, color]) => (
          <div key={name} className="flex items-center gap-1.5">
            <div
              className="w-3 h-3 rounded"
              style={{ backgroundColor: color }}
            />
            <span className="text-dark-300">{name}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default Ontology
