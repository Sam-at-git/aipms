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
import type {
  OntologyEntitySemantic,
  OntologyEntityKinetic,
  StateMachine,
  PermissionMatrix,
  BusinessRule,
  OntologyAction,
  OntologyInterfaceDef,
  OntologyEvent,
  OntologyTabType,
} from '../types'
import { Database, RefreshCw, Box, Network, GitBranch, Shield, AlertTriangle, Package, Wrench, DollarSign, BarChart3, X, Download, Copy, Check, Zap, Eye, EyeOff } from 'lucide-react'
import StateMachineGraph from '../components/StateMachineGraph'

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

// Security level colors
const securityLevelColors: Record<string, string> = {
  PUBLIC: 'bg-green-500/20 text-green-400',
  INTERNAL: 'bg-blue-500/20 text-blue-400',
  CONFIDENTIAL: 'bg-yellow-500/20 text-yellow-400',
  RESTRICTED: 'bg-red-500/20 text-red-400',
}

// Tab type
type TabType = OntologyTabType

// Interface icon and color mapping
const interfaceIcons: Record<string, React.ReactNode> = {
  BookableResource: <Package size={20} />,
  Maintainable: <Wrench size={20} />,
  Billable: <DollarSign size={20} />,
  Trackable: <BarChart3 size={20} />,
}

const interfaceColors: Record<string, string> = {
  BookableResource: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  Maintainable: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  Billable: 'bg-green-500/20 text-green-400 border-green-500/30',
  Trackable: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
}

const defaultInterfaceColor = 'bg-dark-700/50 text-dark-300 border-dark-600'

// Interface tag color (inline, simpler for node rendering)
const interfaceTagColors: Record<string, { bg: string; text: string }> = {
  BookableResource: { bg: '#3b82f620', text: '#60a5fa' },
  Maintainable: { bg: '#f9731620', text: '#fb923c' },
  Billable: { bg: '#10b98120', text: '#34d399' },
  Trackable: { bg: '#8b5cf620', text: '#a78bfa' },
}

// Custom node component
const EntityNode = ({ data }: { data: any }) => {
  const bgColor = entityColors[data.name] || '#6b7280'
  const interfaces: string[] = data.interfaces || []

  // 使用简短的显示名称映射
  const displayNames: Record<string, string> = {
    'RoomType': '房型',
    'Room': '房间',
    'Guest': '客人',
    'Reservation': '预订',
    'StayRecord': '入住',
    'Bill': '账单',
    'Task': '任务',
    'Employee': '员工',
  }

  const shortLabel = displayNames[data.name] || data.name

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
        <div className="font-semibold text-white mb-1">{shortLabel}</div>
        {data.total !== undefined && (
          <div
            className="mt-2 text-2xl font-bold"
            style={{ color: bgColor }}
          >
            {data.total}
          </div>
        )}
        {interfaces.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1 justify-center">
            {interfaces.map(iface => {
              const colors = interfaceTagColors[iface] || { bg: '#6b728020', text: '#9ca3af' }
              const shortName = iface.replace('Resource', '').replace('able', '')
              return (
                <span
                  key={iface}
                  className="text-[10px] px-1.5 py-0.5 rounded"
                  style={{ backgroundColor: colors.bg, color: colors.text }}
                  title={iface}
                >
                  {shortName}
                </span>
              )
            })}
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

// ============== Data Tab Components ==============

interface DataTabProps {
  schema: OntologySchema | null
  statistics: OntologyStatistics | null
  nodes: Node[]
  edges: Edge[]
  onNodesChange: any
  onEdgesChange: any
  onNodeClick: any
  selectedEntity: string | null
}

const DataTab: React.FC<DataTabProps> = ({
  schema,
  statistics,
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onNodeClick,
  selectedEntity,
}) => {
  const [showSystemEntities, setShowSystemEntities] = useState(false)

  const selectedEntityData = useMemo(() => {
    if (!selectedEntity || !schema) return null
    return schema.entities.find(e => e.name === selectedEntity)
  }, [selectedEntity, schema])

  const filteredNodes = useMemo(() => {
    if (showSystemEntities) return nodes
    return nodes.filter(n => n.data?.category !== 'system')
  }, [nodes, showSystemEntities])

  const filteredEdges = useMemo(() => {
    if (showSystemEntities) return edges
    const visibleIds = new Set(filteredNodes.map(n => n.id))
    return edges.filter(e => visibleIds.has(e.source) && visibleIds.has(e.target))
  }, [edges, filteredNodes, showSystemEntities])

  return (
    <div className="flex-1 flex gap-4 min-h-0" style={{ minHeight: '600px' }}>
      {/* Left: Graph */}
      <div className="flex-1 bg-dark-900 rounded-lg overflow-hidden relative" style={{ minHeight: '600px' }}>
        {/* System entity toggle */}
        <div className="absolute top-3 right-3 z-10">
          <button
            onClick={() => setShowSystemEntities(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              showSystemEntities
                ? 'bg-primary-500/20 text-primary-300 border border-primary-500/30'
                : 'bg-dark-800/90 text-dark-400 border border-dark-700 hover:text-dark-300'
            }`}
            title={showSystemEntities ? 'Hide system entities' : 'Show system entities'}
          >
            {showSystemEntities ? <Eye size={14} /> : <EyeOff size={14} />}
            System Entities
          </button>
        </div>
        <ReactFlow
          nodes={filteredNodes}
          edges={filteredEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15, minZoom: 0.5, maxZoom: 1 }}
          minZoom={0.1}
          maxZoom={2}
          defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
          style={{ width: '100%', height: '100%' }}
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
  )
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

            {statistics.active !== undefined && (
              <div className="mt-3 flex justify-between text-sm">
                <span className="text-dark-400">Active</span>
                <span className="text-green-400">{statistics.active}</span>
              </div>
            )}

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

// ============== Semantic Tab Components ==============

interface SemanticTabProps {
  semanticData: { entities: OntologyEntitySemantic[] } | null
  loading: boolean
}

const SemanticTab: React.FC<SemanticTabProps> = ({ semanticData, loading }) => {
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null)
  const [entitySearch, setEntitySearch] = useState('')

  const selectedEntityData = useMemo(() => {
    if (!selectedEntity || !semanticData) return null
    return semanticData.entities.find(e => e.name === selectedEntity)
  }, [selectedEntity, semanticData])

  const groupedEntities = useMemo(() => {
    if (!semanticData) return { business: [], system: [] }
    const filtered = entitySearch
      ? semanticData.entities.filter(e =>
          e.name.toLowerCase().includes(entitySearch.toLowerCase()) ||
          e.description.toLowerCase().includes(entitySearch.toLowerCase()))
      : semanticData.entities
    return {
      business: filtered.filter(e => e.category !== 'system'),
      system: filtered.filter(e => e.category === 'system'),
    }
  }, [semanticData, entitySearch])

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-dark-400">Loading semantic metadata...</div>
      </div>
    )
  }

  if (!semanticData) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-dark-400">No data available</div>
      </div>
    )
  }

  const renderEntityButton = (entity: typeof semanticData.entities[0]) => (
    <button
      key={entity.name}
      onClick={() => setSelectedEntity(entity.name)}
      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
        selectedEntity === entity.name
          ? 'bg-primary-500/20 text-primary-400'
          : 'bg-dark-800 text-dark-300 hover:bg-dark-700'
      }`}
    >
      <div className="font-medium">{entity.name}</div>
      <div className="text-xs text-dark-500">{entity.description}</div>
    </button>
  )

  return (
    <div className="flex-1 flex gap-4 min-h-0">
      {/* Left: Entity list with search + category groups */}
      <div className="w-64 bg-dark-900 rounded-lg p-4 overflow-y-auto">
        <input
          value={entitySearch}
          onChange={e => setEntitySearch(e.target.value)}
          className="w-full px-3 py-1.5 bg-dark-800 border border-dark-700 rounded text-sm mb-3"
          placeholder="搜索实体..."
        />
        {groupedEntities.business.length > 0 && (
          <>
            <h3 className="text-xs font-medium text-dark-500 mb-2 uppercase tracking-wider">业务实体</h3>
            <div className="space-y-1 mb-4">
              {groupedEntities.business.map(renderEntityButton)}
            </div>
          </>
        )}
        {groupedEntities.system.length > 0 && (
          <>
            <h3 className="text-xs font-medium text-dark-500 mb-2 uppercase tracking-wider">系统实体</h3>
            <div className="space-y-1">
              {groupedEntities.system.map(renderEntityButton)}
            </div>
          </>
        )}
      </div>

      {/* Right: Entity detail */}
      <div className="flex-1 bg-dark-900 rounded-lg p-4 overflow-y-auto">
        {selectedEntityData ? (
          <SemanticEntityDetail entity={selectedEntityData} />
        ) : (
          <div className="h-full flex items-center justify-center text-dark-400">
            <div className="text-center">
              <Box className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Select an entity to view semantic details</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

interface SemanticEntityDetailProps {
  entity: OntologyEntitySemantic
}

const SemanticEntityDetail: React.FC<SemanticEntityDetailProps> = ({ entity }) => {
  const bgColor = entityColors[entity.name] || '#6b7280'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 pb-4 border-b border-dark-700">
        <div
          className="w-12 h-12 rounded-lg flex items-center justify-center text-2xl"
          style={{ backgroundColor: `${bgColor}20` }}
        >
          {entity.name[0]}
        </div>
        <div>
          <h2 className="text-xl font-semibold text-white">{entity.name}</h2>
          <p className="text-dark-400 text-sm">{entity.description}</p>
        </div>
        {entity.is_aggregate_root && (
          <span className="ml-auto px-2 py-1 bg-purple-500/20 text-purple-400 text-xs rounded">
            Aggregate Root
          </span>
        )}
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-dark-800 rounded p-3">
          <div className="text-xs text-dark-500 uppercase tracking-wider mb-1">Table Name</div>
          <div className="text-white font-mono text-sm">{entity.table_name}</div>
        </div>
        <div className="bg-dark-800 rounded p-3">
          <div className="text-xs text-dark-500 uppercase tracking-wider mb-1">Related Entities</div>
          <div className="text-white text-sm">
            {entity.related_entities.length > 0
              ? entity.related_entities.join(', ')
              : 'None'}
          </div>
        </div>
      </div>

      {/* Attributes */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-3">Attributes</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-dark-400 border-b border-dark-700">
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Type</th>
                <th className="pb-2 font-medium">Python Type</th>
                <th className="pb-2 font-medium">Constraints</th>
                <th className="pb-2 font-medium">Security</th>
                <th className="pb-2 font-medium">Sensitivity</th>
                <th className="pb-2 font-medium">Flags</th>
                <th className="pb-2 font-medium">Description</th>
              </tr>
            </thead>
            <tbody>
              {entity.attributes.map(attr => (
                <tr key={attr.name} className="border-b border-dark-800">
                  <td className="py-2 text-white">
                    <div className="flex items-center gap-2">
                      {attr.display_name || attr.name}
                      {attr.is_primary_key && (
                        <span className="text-xs bg-primary-500/20 text-primary-400 px-1 rounded">
                          PK
                        </span>
                      )}
                      {attr.is_foreign_key && (
                        <span className="text-xs bg-blue-500/20 text-blue-400 px-1 rounded">
                          FK
                        </span>
                      )}
                    </div>
                    {attr.display_name && attr.display_name !== attr.name && (
                      <div className="text-xs text-dark-500 font-mono">{attr.name}</div>
                    )}
                    {attr.foreign_key_target && (
                      <div className="text-xs text-dark-500">→ {attr.foreign_key_target}</div>
                    )}
                  </td>
                  <td className="py-2 text-dark-300 font-mono text-xs">{attr.type}</td>
                  <td className="py-2 text-dark-300 font-mono text-xs">{attr.python_type}</td>
                  <td className="py-2 text-dark-400 text-xs">
                    {attr.is_required && <span className="text-red-400">required </span>}
                    {attr.is_unique && <span className="text-yellow-400">unique </span>}
                    {attr.is_unique && <span className="text-blue-400">nullable</span>}
                    {attr.max_length && <span className="text-dark-500">max:{attr.max_length}</span>}
                  </td>
                  <td className="py-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${securityLevelColors[attr.security_level]}`}>
                      {attr.security_level}
                    </span>
                  </td>
                  <td className="py-2">
                    <div className="flex items-center gap-1">
                      {attr.pii && (
                        <span className="text-xs bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded" title="Personal Identifiable Information">
                          PII
                        </span>
                      )}
                      {attr.phi && (
                        <span className="text-xs bg-orange-500/20 text-orange-400 px-1.5 py-0.5 rounded" title="Protected Health Information">
                          PHI
                        </span>
                      )}
                      {!attr.pii && !attr.phi && (
                        <span className="text-dark-600 text-xs">-</span>
                      )}
                    </div>
                  </td>
                  <td className="py-2">
                    <div className="flex items-center gap-1">
                      {attr.searchable && (
                        <span className="text-xs text-primary-400" title="Searchable">S</span>
                      )}
                      {attr.indexed && (
                        <span className="text-xs text-cyan-400" title="Indexed">I</span>
                      )}
                      {attr.is_rich_text && (
                        <span className="text-xs text-yellow-400" title="Rich Text">R</span>
                      )}
                      {!attr.searchable && !attr.indexed && !attr.is_rich_text && (
                        <span className="text-dark-600 text-xs">-</span>
                      )}
                    </div>
                  </td>
                  <td className="py-2 text-dark-400 text-xs">{attr.description || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Relationships */}
      {entity.relationships.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-3">Relationships</h3>
          <div className="space-y-2">
            {entity.relationships.map(rel => (
              <div key={rel.name} className="bg-dark-800 rounded p-3 flex items-center justify-between">
                <div>
                  <div className="text-white font-medium">{rel.name}</div>
                  <div className="text-dark-500 text-sm">{rel.label}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-dark-700 text-dark-300 px-2 py-1 rounded">
                    {rel.type}
                  </span>
                  <span className="text-dark-400">→</span>
                  <span className="text-white">{rel.target}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ============== Kinetic Tab Components ==============

interface KineticTabProps {
  kineticData: { entities: OntologyEntityKinetic[] } | null
  loading: boolean
}

const KineticTab: React.FC<KineticTabProps> = ({ kineticData, loading }) => {
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null)
  const [selectedAction, setSelectedAction] = useState<string | null>(null)
  const [entitySearch, setEntitySearch] = useState('')

  const selectedEntityData = useMemo(() => {
    if (!selectedEntity || !kineticData) return null
    return kineticData.entities.find(e => e.name === selectedEntity)
  }, [selectedEntity, kineticData])

  const selectedActionData = useMemo(() => {
    if (!selectedAction || !selectedEntityData) return null
    return selectedEntityData.actions.find(a => a.action_type === selectedAction)
  }, [selectedAction, selectedEntityData])

  const groupedEntities = useMemo(() => {
    if (!kineticData) return { business: [], system: [] }
    const filtered = entitySearch
      ? kineticData.entities.filter(e =>
          e.name.toLowerCase().includes(entitySearch.toLowerCase()) ||
          e.description.toLowerCase().includes(entitySearch.toLowerCase()))
      : kineticData.entities
    return {
      business: filtered.filter(e => e.category !== 'system'),
      system: filtered.filter(e => e.category === 'system'),
    }
  }, [kineticData, entitySearch])

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-dark-400">Loading kinetic metadata...</div>
      </div>
    )
  }

  if (!kineticData) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-dark-400">No data available</div>
      </div>
    )
  }

  const renderEntityButton = (entity: typeof kineticData.entities[0]) => (
    <button
      key={entity.name}
      onClick={() => {
        setSelectedEntity(entity.name)
        setSelectedAction(null)
      }}
      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
        selectedEntity === entity.name
          ? 'bg-primary-500/20 text-primary-400'
          : 'bg-dark-800 text-dark-300 hover:bg-dark-700'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="font-medium">{entity.name}</span>
        <span className="text-xs text-dark-500">{entity.actions.length}</span>
      </div>
    </button>
  )

  return (
    <div className="flex-1 flex gap-4 min-h-0">
      {/* Left: Entity list with search + category groups */}
      <div className="w-56 bg-dark-900 rounded-lg p-4 overflow-y-auto">
        <input
          value={entitySearch}
          onChange={e => setEntitySearch(e.target.value)}
          className="w-full px-3 py-1.5 bg-dark-800 border border-dark-700 rounded text-sm mb-3"
          placeholder="搜索实体..."
        />
        {groupedEntities.business.length > 0 && (
          <>
            <h3 className="text-xs font-medium text-dark-500 mb-2 uppercase tracking-wider">业务实体</h3>
            <div className="space-y-1 mb-4">
              {groupedEntities.business.map(renderEntityButton)}
            </div>
          </>
        )}
        {groupedEntities.system.length > 0 && (
          <>
            <h3 className="text-xs font-medium text-dark-500 mb-2 uppercase tracking-wider">系统实体</h3>
            <div className="space-y-1">
              {groupedEntities.system.map(renderEntityButton)}
            </div>
          </>
        )}
      </div>

      {/* Middle: Action list */}
      {selectedEntityData && (
        <div className="w-72 bg-dark-900 rounded-lg p-4 overflow-y-auto">
          <h3 className="text-sm font-medium text-dark-300 mb-1">Actions</h3>
          <p className="text-xs text-dark-500 mb-3">{selectedEntityData.description}</p>
          <div className="space-y-1">
            {selectedEntityData.actions.map(action => (
              <button
                key={action.action_type}
                onClick={() => setSelectedAction(action.action_type)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                  selectedAction === action.action_type
                    ? 'bg-primary-500/20 text-primary-400'
                    : 'bg-dark-800 text-dark-300 hover:bg-dark-700'
                }`}
              >
                <div className="font-medium">{action.action_type}</div>
                <div className="text-xs text-dark-500 truncate">{action.description}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Right: Action detail */}
      <div className="flex-1 bg-dark-900 rounded-lg p-4 overflow-y-auto">
        {selectedActionData ? (
          <ActionDetail action={selectedActionData} entityName={selectedEntity!} />
        ) : (
          <div className="h-full flex items-center justify-center text-dark-400">
            <div className="text-center">
              <Network className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Select an action to view details</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

interface ActionDetailProps {
  action: OntologyAction
  entityName: string
}

const ActionDetail: React.FC<ActionDetailProps> = ({ action, entityName }) => {
  const bgColor = entityColors[entityName] || '#6b7280'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 pb-4 border-b border-dark-700">
        <div
          className="w-12 h-12 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: `${bgColor}20` }}
        >
          <Network className="w-6 h-6" style={{ color: bgColor }} />
        </div>
        <div className="flex-1">
          <h2 className="text-xl font-semibold text-white">{action.action_type}</h2>
          <p className="text-dark-400 text-sm">{action.description}</p>
        </div>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-2">
        {action.requires_confirmation && (
          <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded">
            Requires Confirmation
          </span>
        )}
        {action.undoable && (
          <span className="px-2 py-1 bg-blue-500/20 text-blue-400 text-xs rounded">
            Undoable
          </span>
        )}
        {action.writeback ? (
          <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded">
            Writeback
          </span>
        ) : (
          <span className="px-2 py-1 bg-dark-700 text-dark-400 text-xs rounded">
            Read-only
          </span>
        )}
      </div>

      {/* Allowed roles */}
      <div>
        <h3 className="text-sm font-medium text-dark-300 mb-2">Allowed Roles</h3>
        <div className="flex flex-wrap gap-2">
          {action.allowed_roles.map(role => (
            <span
              key={role}
              className="px-3 py-1 bg-dark-800 text-dark-300 text-sm rounded capitalize"
            >
              {role}
            </span>
          ))}
        </div>
      </div>

      {/* Parameters */}
      <div>
        <h3 className="text-sm font-medium text-dark-300 mb-3">Parameters</h3>
        <div className="space-y-2">
          {action.params.map(param => (
            <div key={param.name} className="bg-dark-800 rounded p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-white font-medium">{param.name}</span>
                {param.required && (
                  <span className="text-xs bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded">
                    required
                  </span>
                )}
                <span className="ml-auto text-xs text-dark-500 font-mono">{param.type}</span>
              </div>
              <p className="text-dark-400 text-sm">{param.description}</p>
              {param.enum_values && (
                <div className="mt-2 text-xs text-dark-500">
                  Options: {param.enum_values.join(', ')}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ============== Dynamic Tab Components ==============

interface DynamicTabProps {
  dynamicData: {
    state_machines: StateMachine[]
    permission_matrix: PermissionMatrix
    business_rules: BusinessRule[]
  } | null
  loading: boolean
}

const DynamicTab: React.FC<DynamicTabProps> = ({ dynamicData, loading }) => {
  const [view, setView] = useState<'state-machines' | 'permissions' | 'rules' | 'events'>('state-machines')
  const [selectedStateMachine, setSelectedStateMachine] = useState<string | null>(null)

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-dark-400">Loading dynamic metadata...</div>
      </div>
    )
  }

  if (!dynamicData) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-dark-400">No data available</div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex gap-4 min-h-0">
      {/* Left: Navigation */}
      <div className="w-48 bg-dark-900 rounded-lg p-4">
        <h3 className="text-sm font-medium text-dark-300 mb-3">Dynamic Aspects</h3>
        <div className="space-y-1">
          <button
            onClick={() => setView('state-machines')}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center gap-2 ${
              view === 'state-machines'
                ? 'bg-primary-500/20 text-primary-400'
                : 'bg-dark-800 text-dark-300 hover:bg-dark-700'
            }`}
          >
            <GitBranch size={16} />
            State Machines
          </button>
          <button
            onClick={() => setView('permissions')}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center gap-2 ${
              view === 'permissions'
                ? 'bg-primary-500/20 text-primary-400'
                : 'bg-dark-800 text-dark-300 hover:bg-dark-700'
            }`}
          >
            <Shield size={16} />
            Permission Matrix
          </button>
          <button
            onClick={() => setView('rules')}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center gap-2 ${
              view === 'rules'
                ? 'bg-primary-500/20 text-primary-400'
                : 'bg-dark-800 text-dark-300 hover:bg-dark-700'
            }`}
          >
            <AlertTriangle size={16} />
            Business Rules
          </button>
          <button
            onClick={() => setView('events')}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center gap-2 ${
              view === 'events'
                ? 'bg-primary-500/20 text-primary-400'
                : 'bg-dark-800 text-dark-300 hover:bg-dark-700'
            }`}
          >
            <Zap size={16} />
            Domain Events
          </button>
        </div>

        {view === 'state-machines' && (
          <div className="mt-4 pt-4 border-t border-dark-700">
            <h4 className="text-xs text-dark-500 uppercase tracking-wider mb-2">Entities</h4>
            <div className="space-y-1">
              {dynamicData.state_machines.map(sm => (
                <button
                  key={sm.entity}
                  onClick={() => setSelectedStateMachine(sm.entity)}
                  className={`w-full text-left px-3 py-1.5 rounded text-sm transition-colors ${
                    selectedStateMachine === sm.entity
                      ? 'bg-dark-700 text-white'
                      : 'text-dark-400 hover:text-dark-300'
                  }`}
                >
                  {sm.entity}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right: Content */}
      <div className="flex-1 bg-dark-900 rounded-lg p-4 overflow-y-auto">
        {view === 'state-machines' && (
          <StateMachineView
            stateMachines={dynamicData.state_machines}
            selectedEntity={selectedStateMachine}
          />
        )}
        {view === 'permissions' && (
          <PermissionMatrixView permissionMatrix={dynamicData.permission_matrix} />
        )}
        {view === 'rules' && (
          <BusinessRulesView businessRules={dynamicData.business_rules} />
        )}
        {view === 'events' && <EventsView />}
      </div>
    </div>
  )
}

interface StateMachineViewProps {
  stateMachines: StateMachine[]
  selectedEntity: string | null
}

const StateMachineView: React.FC<StateMachineViewProps> = ({
  stateMachines,
  selectedEntity,
}) => {
  const machine = useMemo(() => {
    if (!selectedEntity) return stateMachines[0] || null
    return stateMachines.find(sm => sm.entity === selectedEntity) || null
  }, [stateMachines, selectedEntity])

  if (!machine) {
    return (
      <div className="h-full flex items-center justify-center text-dark-400">
        No state machine available
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-dark-700">
        <h2 className="text-xl font-semibold text-white">{machine.entity} State Machine</h2>
        <p className="text-dark-400 text-sm">{machine.description}</p>
        <div className="mt-2 text-xs text-dark-500">
          Initial State: <span className="text-primary-400">{machine.initial_state}</span>
        </div>
      </div>

      {/* Flow Graph */}
      <StateMachineGraph machine={machine} />

      {/* Transitions table */}
      <div>
        <h3 className="text-sm font-medium text-dark-300 mb-3">Transitions</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-dark-400 border-b border-dark-700">
              <th className="pb-2 font-medium">From</th>
              <th className="pb-2 font-medium">To</th>
              <th className="pb-2 font-medium">Trigger</th>
              <th className="pb-2 font-medium">Condition</th>
              <th className="pb-2 font-medium">Side Effects</th>
            </tr>
          </thead>
          <tbody>
            {machine.transitions.map((transition, index) => (
              <tr key={index} className="border-b border-dark-800">
                <td className="py-2 text-white">{transition.from}</td>
                <td className="py-2 text-white">{transition.to}</td>
                <td className="py-2">
                  <span className="text-primary-400">{transition.trigger}</span>
                  {transition.trigger_action && (
                    <div className="text-xs text-dark-500">{transition.trigger_action}</div>
                  )}
                </td>
                <td className="py-2 text-dark-400 text-xs font-mono">
                  {transition.condition || '-'}
                </td>
                <td className="py-2">
                  {transition.side_effects.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {transition.side_effects.map((effect, i) => (
                        <span
                          key={i}
                          className="text-xs bg-dark-700 text-dark-300 px-2 py-0.5 rounded"
                        >
                          {effect}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-dark-500">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

interface PermissionMatrixViewProps {
  permissionMatrix: PermissionMatrix
}

const PermissionMatrixView: React.FC<PermissionMatrixViewProps> = ({ permissionMatrix }) => {
  // Group actions by entity
  const actionsByEntity = useMemo(() => {
    const grouped: Record<string, typeof permissionMatrix.actions> = {}
    permissionMatrix.actions.forEach(action => {
      if (!grouped[action.entity]) {
        grouped[action.entity] = []
      }
      grouped[action.entity].push(action)
    })
    return grouped
  }, [permissionMatrix.actions])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-dark-700">
        <h2 className="text-xl font-semibold text-white">Permission Matrix</h2>
        <p className="text-dark-400 text-sm">Define which roles can perform which actions</p>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-dark-400">Legend:</span>
        <span className="flex items-center gap-1">
          <div className="w-4 h-4 rounded bg-green-500"></div>
          <span className="text-dark-300">Allowed</span>
        </span>
        <span className="flex items-center gap-1">
          <div className="w-4 h-4 rounded bg-dark-700"></div>
          <span className="text-dark-300">Not Allowed</span>
        </span>
      </div>

      {/* Matrix by entity */}
      <div className="space-y-6">
        {Object.entries(actionsByEntity).map(([entity, actions]) => (
          <div key={entity}>
            <h3 className="text-lg font-semibold text-white mb-3">{entity}</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-dark-400 border-b border-dark-700">
                    <th className="pb-2 pr-4 font-medium">Action</th>
                    {permissionMatrix.roles.map(role => (
                      <th key={role} className="pb-2 px-2 text-center font-medium capitalize">
                        {role}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {actions.map(action => (
                    <tr key={action.action_type} className="border-b border-dark-800">
                      <td className="py-2 pr-4 text-white font-mono text-xs">
                        {action.action_type}
                      </td>
                      {permissionMatrix.roles.map(role => (
                        <td key={role} className="py-2 px-2 text-center">
                          <div
                            className={`w-6 h-6 mx-auto rounded ${
                              action.roles.includes(role as any)
                                ? 'bg-green-500'
                                : 'bg-dark-700'
                            }`}
                            title={
                              action.roles.includes(role as any)
                                ? `${role} can perform ${action.action_type}`
                                : `${role} cannot perform ${action.action_type}`
                            }
                          ></div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

interface BusinessRulesViewProps {
  businessRules: BusinessRule[]
}

const BusinessRulesView: React.FC<BusinessRulesViewProps> = ({ businessRules }) => {
  const [filterSeverity, setFilterSeverity] = useState<string>('all')
  const [filterEntity, setFilterEntity] = useState<string>('all')

  const filteredRules = useMemo(() => {
    return businessRules.filter(rule => {
      if (filterSeverity !== 'all' && rule.severity !== filterSeverity) return false
      if (filterEntity !== 'all' && rule.entity !== filterEntity) return false
      return true
    })
  }, [businessRules, filterSeverity, filterEntity])

  const entities = useMemo(() => {
    return Array.from(new Set(businessRules.map(r => r.entity))).sort()
  }, [businessRules])

  const severityColors: Record<string, string> = {
    error: 'bg-red-500/20 text-red-400',
    warning: 'bg-yellow-500/20 text-yellow-400',
    info: 'bg-blue-500/20 text-blue-400',
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-dark-700">
        <h2 className="text-xl font-semibold text-white">Business Rules</h2>
        <p className="text-dark-400 text-sm">Define behavior logic and constraints</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm text-dark-400">Entity:</label>
          <select
            value={filterEntity}
            onChange={(e) => setFilterEntity(e.target.value)}
            className="bg-dark-800 border border-dark-700 rounded px-3 py-1.5 text-sm text-white"
          >
            <option value="all">All Entities</option>
            {entities.map(entity => (
              <option key={entity} value={entity}>
                {entity}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-dark-400">Severity:</label>
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="bg-dark-800 border border-dark-700 rounded px-3 py-1.5 text-sm text-white"
          >
            <option value="all">All Severities</option>
            <option value="error">Error</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
        </div>
        <div className="ml-auto text-sm text-dark-400">
          Showing {filteredRules.length} of {businessRules.length} rules
        </div>
      </div>

      {/* Rules list */}
      <div className="space-y-3">
        {filteredRules.map(rule => (
          <div key={rule.rule_id} className="bg-dark-800 rounded-lg p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded ${severityColors[rule.severity]}`}>
                  {rule.severity}
                </span>
                <span className="text-xs text-dark-500">{rule.entity}</span>
              </div>
              <span className="text-xs text-dark-500 font-mono">{rule.rule_id}</span>
            </div>
            <h4 className="text-white font-medium mb-1">{rule.rule_name}</h4>
            <p className="text-dark-400 text-sm mb-3">{rule.description}</p>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-dark-500">Condition:</span>
                <code className="ml-2 text-primary-400">{rule.condition}</code>
              </div>
              <div>
                <span className="text-dark-500">Action:</span>
                <code className="ml-2 text-yellow-400">{rule.action}</code>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============== Events View ==============

const EventsView: React.FC = () => {
  const [events, setEvents] = useState<OntologyEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    ontologyApi.getEvents().then(data => {
      setEvents(data.events)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="text-dark-400 text-center py-8">Loading events...</div>
  }

  if (events.length === 0) {
    return <div className="text-dark-400 text-center py-8">No events registered</div>
  }

  // Group by entity
  const byEntity: Record<string, OntologyEvent[]> = {}
  for (const e of events) {
    const key = e.entity || 'Other'
    if (!byEntity[key]) byEntity[key] = []
    byEntity[key].push(e)
  }

  return (
    <div className="space-y-6">
      <div className="pb-4 border-b border-dark-700">
        <h2 className="text-xl font-semibold text-white">Domain Events</h2>
        <p className="text-dark-400 text-sm">{events.length} events registered</p>
      </div>

      {Object.entries(byEntity).map(([entity, entityEvents]) => (
        <div key={entity}>
          <h3 className="text-sm font-medium text-dark-300 mb-3">{entity}</h3>
          <div className="grid gap-3">
            {entityEvents.map(event => (
              <div key={event.name} className="bg-dark-800 rounded-lg p-4">
                <div className="flex items-start justify-between mb-2">
                  <code className="text-sm font-mono text-primary-400">{event.name}</code>
                </div>
                {event.description && (
                  <p className="text-sm text-dark-300 mb-3">{event.description}</p>
                )}
                <div className="flex flex-wrap gap-4 text-xs">
                  {event.triggered_by.length > 0 && (
                    <div>
                      <span className="text-dark-500 mr-1">Triggered by:</span>
                      {event.triggered_by.map(t => (
                        <span key={t} className="inline-block bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded mr-1">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                  {event.payload_fields.length > 0 && (
                    <div>
                      <span className="text-dark-500 mr-1">Payload:</span>
                      {event.payload_fields.map(f => (
                        <span key={f} className="inline-block bg-dark-700 text-dark-300 px-2 py-0.5 rounded mr-1 font-mono">
                          {f}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ============== Interfaces Tab Components ==============

interface InterfacesTabProps {
  interfacesData: Record<string, OntologyInterfaceDef> | null
  loading: boolean
}

const InterfacesTab: React.FC<InterfacesTabProps> = ({ interfacesData, loading }) => {
  const [selectedInterface, setSelectedInterface] = useState<string | null>(null)

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-dark-400">Loading interfaces...</div>
      </div>
    )
  }

  if (!interfacesData || Object.keys(interfacesData).length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-dark-400">
          <Package className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No interfaces registered</p>
        </div>
      </div>
    )
  }

  const selectedData = selectedInterface ? interfacesData[selectedInterface] : null

  return (
    <div className="flex-1 flex gap-4 min-h-0">
      {/* Cards grid */}
      <div className="flex-1 overflow-y-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(interfacesData).map(([name, iface]) => {
            const colorClass = interfaceColors[name] || defaultInterfaceColor
            const icon = interfaceIcons[name] || <Package size={20} />
            return (
              <button
                key={name}
                onClick={() => setSelectedInterface(name)}
                className={`text-left p-4 rounded-lg border transition-all hover:scale-[1.02] ${
                  selectedInterface === name
                    ? 'ring-2 ring-primary-500 ' + colorClass
                    : 'bg-dark-800 border-dark-700 hover:border-dark-600'
                }`}
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className={`p-2 rounded-lg ${colorClass.split(' ').slice(0, 1).join(' ')}`}>
                    {icon}
                  </div>
                  <div>
                    <h3 className="font-semibold text-white">{name}</h3>
                    {iface.description && (
                      <p className="text-xs text-dark-400">{iface.description}</p>
                    )}
                  </div>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-dark-400">Properties</span>
                    <span className="text-dark-300">{Object.keys(iface.required_properties).length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-dark-400">Actions</span>
                    <span className="text-dark-300">{iface.required_actions.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-dark-400">Implementations</span>
                    <span className={iface.implementations.length > 0 ? 'text-green-400' : 'text-dark-500'}>
                      {iface.implementations.length}
                    </span>
                  </div>
                </div>

                {iface.implementations.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {iface.implementations.map(impl => (
                      <span
                        key={impl}
                        className="text-xs bg-dark-700 text-dark-300 px-2 py-0.5 rounded"
                      >
                        {impl}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Detail drawer */}
      {selectedData && selectedInterface && (
        <div className="w-96 bg-dark-900 rounded-lg p-4 overflow-y-auto border border-dark-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">{selectedInterface}</h3>
            <button
              onClick={() => setSelectedInterface(null)}
              className="p-1 hover:bg-dark-700 rounded"
            >
              <X size={16} className="text-dark-400" />
            </button>
          </div>

          {selectedData.description && (
            <p className="text-dark-400 text-sm mb-4">{selectedData.description}</p>
          )}

          {/* Required Properties */}
          <div className="mb-4">
            <h4 className="text-sm font-medium text-dark-300 mb-2">Required Properties</h4>
            {Object.keys(selectedData.required_properties).length > 0 ? (
              <div className="space-y-1">
                {Object.entries(selectedData.required_properties).map(([prop, type]) => (
                  <div key={prop} className="flex items-center justify-between bg-dark-800 rounded px-3 py-2 text-sm">
                    <span className="text-white">{prop}</span>
                    <span className="text-dark-400 font-mono text-xs">{type}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-dark-500 text-sm">None</p>
            )}
          </div>

          {/* Required Actions */}
          <div className="mb-4">
            <h4 className="text-sm font-medium text-dark-300 mb-2">Required Actions</h4>
            {selectedData.required_actions.length > 0 ? (
              <div className="space-y-1">
                {selectedData.required_actions.map(action => (
                  <div key={action} className="bg-dark-800 rounded px-3 py-2 text-sm text-white">
                    {action}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-dark-500 text-sm">None</p>
            )}
          </div>

          {/* Implementations */}
          <div>
            <h4 className="text-sm font-medium text-dark-300 mb-2">Implementations</h4>
            {selectedData.implementations.length > 0 ? (
              <div className="space-y-1">
                {selectedData.implementations.map(impl => (
                  <div
                    key={impl}
                    className="bg-dark-800 rounded px-3 py-2 text-sm text-primary-400 flex items-center gap-2"
                  >
                    <div
                      className="w-3 h-3 rounded"
                      style={{ backgroundColor: entityColors[impl] || '#6b7280' }}
                    />
                    {impl}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-dark-500 text-sm italic">No implementations yet</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ============== Schema Export Button ==============

const SchemaExportButton: React.FC = () => {
  const [showMenu, setShowMenu] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleExportJSON = async () => {
    try {
      const schema = await ontologyApi.exportSchema()
      const blob = new Blob([JSON.stringify(schema, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const now = new Date()
      const ts = now.toISOString().replace(/[-:T]/g, '').slice(0, 15)
      a.href = url
      a.download = `ontology-schema-${ts}.json`
      a.click()
      URL.revokeObjectURL(url)
      setShowMenu(false)
    } catch (err) {
      console.error('Failed to export schema:', err)
    }
  }

  const handleCopyToClipboard = async () => {
    try {
      const schema = await ontologyApi.exportSchema()
      await navigator.clipboard.writeText(JSON.stringify(schema, null, 2))
      setCopied(true)
      setTimeout(() => {
        setCopied(false)
        setShowMenu(false)
      }, 1500)
    } catch (err) {
      console.error('Failed to copy schema:', err)
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setShowMenu(!showMenu)}
        className="flex items-center gap-2 px-3 py-1.5 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors text-sm"
      >
        <Download size={16} />
        Export Schema
      </button>
      {showMenu && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
          <div className="absolute right-0 top-full mt-1 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-xl z-20 overflow-hidden">
            <button
              onClick={handleExportJSON}
              className="w-full text-left px-4 py-2.5 text-sm text-dark-300 hover:bg-dark-700 flex items-center gap-2"
            >
              <Download size={14} />
              Export as JSON
            </button>
            <button
              onClick={handleCopyToClipboard}
              className="w-full text-left px-4 py-2.5 text-sm text-dark-300 hover:bg-dark-700 flex items-center gap-2"
            >
              {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
              {copied ? 'Copied!' : 'Copy to Clipboard'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

// ============== Main Ontology Component ==============

const Ontology: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('data')
  const [schema, setSchema] = useState<OntologySchema | null>(null)
  const [statistics, setStatistics] = useState<OntologyStatistics | null>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Extended metadata states
  const [semanticData, setSemanticData] = useState<{ entities: OntologyEntitySemantic[] } | null>(null)
  const [kineticData, setKineticData] = useState<{ entities: OntologyEntityKinetic[] } | null>(null)
  const [dynamicData, setDynamicData] = useState<{
    state_machines: StateMachine[]
    permission_matrix: PermissionMatrix
    business_rules: BusinessRule[]
  } | null>(null)
  const [interfacesData, setInterfacesData] = useState<Record<string, OntologyInterfaceDef> | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // Load schema, statistics and interfaces for data tab
      const [schemaRes, statsRes, ifacesRes] = await Promise.all([
        ontologyApi.getSchema(),
        ontologyApi.getStatistics(),
        ontologyApi.getInterfaces().catch(() => ({} as Record<string, OntologyInterfaceDef>)),
      ])
      setSchema(schemaRes)
      setStatistics(statsRes)
      setInterfacesData(ifacesRes)
      generateGraph(schemaRes, statsRes, ifacesRes)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load ontology data')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadTabData = useCallback(async (tab: TabType) => {
    try {
      if (tab === 'semantic' && !semanticData) {
        const data = await ontologyApi.getSemantic()
        setSemanticData(data)
      } else if (tab === 'kinetic' && !kineticData) {
        const data = await ontologyApi.getKinetic()
        setKineticData(data)
      } else if (tab === 'dynamic' && !dynamicData) {
        const data = await ontologyApi.getDynamic()
        setDynamicData(data)
      } else if (tab === 'interfaces' && !interfacesData) {
        const data = await ontologyApi.getInterfaces()
        setInterfacesData(data)
      }
    } catch (err: any) {
      console.error(`Failed to load ${tab} data:`, err)
    }
  }, [semanticData, kineticData, dynamicData, interfacesData])

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    loadTabData(activeTab)
  }, [activeTab, loadTabData])

  const generateGraph = useCallback((schema: OntologySchema, stats: OntologyStatistics, ifaceData?: Record<string, OntologyInterfaceDef> | null) => {
    // Build reverse map: entity -> [interface names]
    const entityInterfaces: Record<string, string[]> = {}
    if (ifaceData) {
      Object.entries(ifaceData).forEach(([ifaceName, iface]) => {
        iface.implementations.forEach(impl => {
          // Match both "RoomEntity" and "Room" style names
          const shortName = impl.replace('Entity', '')
          if (!entityInterfaces[impl]) entityInterfaces[impl] = []
          if (!entityInterfaces[shortName]) entityInterfaces[shortName] = []
          entityInterfaces[impl].push(ifaceName)
          entityInterfaces[shortName].push(ifaceName)
        })
      })
    }

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
          name: entity.name,
          category: entity.category || 'business',
          total: stat?.total || 0,
          attributes: entity.attributes,
          interfaces: entityInterfaces[entity.name] || [],
        }
      }
    })

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

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'data', label: 'Data', icon: <Database size={16} /> },
    { id: 'semantic', label: 'Semantic', icon: <Box size={16} /> },
    { id: 'kinetic', label: 'Kinetic', icon: <Network size={16} /> },
    { id: 'dynamic', label: 'Dynamic', icon: <GitBranch size={16} /> },
    { id: 'interfaces', label: 'Interfaces', icon: <Package size={16} /> },
  ]

  if (loading && activeTab === 'data') {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-primary-400 mx-auto mb-2" />
          <p className="text-dark-400">Loading ontology data...</p>
        </div>
      </div>
    )
  }

  if (error && activeTab === 'data') {
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
        <div className="flex items-center gap-2">
          <SchemaExportButton />
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-3 py-1.5 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors text-sm"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-4 bg-dark-800 rounded-lg p-1">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
              activeTab === tab.id
                ? 'bg-primary-500 text-white'
                : 'text-dark-400 hover:text-dark-300'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0">
        {activeTab === 'data' && (
          <DataTab
            schema={schema}
            statistics={statistics}
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            selectedEntity={selectedEntity}
          />
        )}
        {activeTab === 'semantic' && (
          <SemanticTab semanticData={semanticData} loading={loading && !semanticData} />
        )}
        {activeTab === 'kinetic' && (
          <KineticTab kineticData={kineticData} loading={loading && !kineticData} />
        )}
        {activeTab === 'dynamic' && (
          <DynamicTab dynamicData={dynamicData} loading={loading && !dynamicData} />
        )}
        {activeTab === 'interfaces' && (
          <InterfacesTab interfacesData={interfacesData} loading={loading && !interfacesData} />
        )}
      </div>

      {/* Legend (only for data tab) */}
      {activeTab === 'data' && (
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
      )}
    </div>
  )
}

export default Ontology
