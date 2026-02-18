import { useEffect, useState } from 'react'
import { Building2, Plus, Pencil, Trash2, ChevronRight, ChevronDown, Briefcase } from 'lucide-react'
import { orgApi, SysDepartment, SysDepartmentTree, SysPosition } from '../../services/api'

export default function OrgManagement() {
  const [departments, setDepartments] = useState<SysDepartment[]>([])
  const [tree, setTree] = useState<SysDepartmentTree[]>([])
  const [positions, setPositions] = useState<SysPosition[]>([])
  const [selectedDept, setSelectedDept] = useState<SysDepartment | null>(null)
  const [loading, setLoading] = useState(true)
  const [posLoading, setPosLoading] = useState(false)

  // Department form
  const [showDeptForm, setShowDeptForm] = useState(false)
  const [editingDept, setEditingDept] = useState<SysDepartment | null>(null)
  const [deptForm, setDeptForm] = useState({ code: '', name: '', parent_id: null as number | null, sort_order: 0 })

  // Position form
  const [showPosForm, setShowPosForm] = useState(false)
  const [editingPos, setEditingPos] = useState<SysPosition | null>(null)
  const [posForm, setPosForm] = useState({ code: '', name: '', sort_order: 0 })

  useEffect(() => { loadDepartments() }, [])

  const loadDepartments = async () => {
    try {
      setLoading(true)
      const [depts, treeData] = await Promise.all([
        orgApi.getDepartments(),
        orgApi.getDepartmentTree(),
      ])
      setDepartments(depts)
      setTree(treeData)
    } catch (err) {
      console.error('Failed to load departments:', err)
    } finally {
      setLoading(false)
    }
  }

  const selectDept = async (dept: SysDepartment) => {
    setSelectedDept(dept)
    setPosLoading(true)
    try {
      const data = await orgApi.getPositions(dept.id)
      setPositions(data)
    } catch (err) {
      console.error('Failed to load positions:', err)
    } finally {
      setPosLoading(false)
    }
  }

  // ---- Department CRUD ----
  const openDeptCreate = (parentId: number | null = null) => {
    setEditingDept(null)
    setDeptForm({ code: '', name: '', parent_id: parentId, sort_order: 0 })
    setShowDeptForm(true)
  }

  const openDeptEdit = (dept: SysDepartment) => {
    setEditingDept(dept)
    setDeptForm({ code: dept.code, name: dept.name, parent_id: dept.parent_id, sort_order: dept.sort_order })
    setShowDeptForm(true)
  }

  const saveDept = async () => {
    try {
      if (editingDept) {
        await orgApi.updateDepartment(editingDept.id, {
          name: deptForm.name, parent_id: deptForm.parent_id, sort_order: deptForm.sort_order,
        })
      } else {
        await orgApi.createDepartment({
          code: deptForm.code, name: deptForm.name, parent_id: deptForm.parent_id, sort_order: deptForm.sort_order,
        })
      }
      setShowDeptForm(false)
      await loadDepartments()
    } catch (err: any) {
      alert(err.response?.data?.detail || '操作失败')
    }
  }

  const deleteDept = async (id: number) => {
    if (!confirm('确认删除该部门？')) return
    try {
      await orgApi.deleteDepartment(id)
      if (selectedDept?.id === id) {
        setSelectedDept(null)
        setPositions([])
      }
      await loadDepartments()
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  // ---- Position CRUD ----
  const openPosCreate = () => {
    setEditingPos(null)
    setPosForm({ code: '', name: '', sort_order: 0 })
    setShowPosForm(true)
  }

  const openPosEdit = (pos: SysPosition) => {
    setEditingPos(pos)
    setPosForm({ code: pos.code, name: pos.name, sort_order: pos.sort_order })
    setShowPosForm(true)
  }

  const savePos = async () => {
    if (!selectedDept) return
    try {
      if (editingPos) {
        await orgApi.updatePosition(editingPos.id, {
          name: posForm.name, sort_order: posForm.sort_order,
        })
      } else {
        await orgApi.createPosition({
          code: posForm.code, name: posForm.name, department_id: selectedDept.id, sort_order: posForm.sort_order,
        })
      }
      setShowPosForm(false)
      await selectDept(selectedDept)
    } catch (err: any) {
      alert(err.response?.data?.detail || '操作失败')
    }
  }

  const deletePos = async (id: number) => {
    if (!confirm('确认删除该岗位？')) return
    try {
      await orgApi.deletePosition(id)
      if (selectedDept) await selectDept(selectedDept)
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Building2 size={24} className="text-primary-400" />
          <h1 className="text-xl font-bold">组织机构管理</h1>
        </div>
      </div>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* Left: Department tree */}
        <div className="w-72 flex-shrink-0 bg-dark-900 rounded-lg border border-dark-800 flex flex-col">
          <div className="p-3 border-b border-dark-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Building2 size={16} className="text-dark-400" />
              <span className="text-sm font-medium">部门</span>
            </div>
            <button
              onClick={() => openDeptCreate(null)}
              className="p-1 hover:bg-dark-700 rounded"
              title="新增根部门"
            >
              <Plus size={14} className="text-primary-400" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {loading ? (
              <p className="text-xs text-dark-500 p-2">加载中...</p>
            ) : tree.length === 0 ? (
              <p className="text-xs text-dark-500 p-2">暂无部门</p>
            ) : (
              tree.map(node => (
                <DeptTreeNode
                  key={node.id}
                  node={node}
                  selectedId={selectedDept?.id ?? null}
                  onSelect={selectDept}
                  onEdit={openDeptEdit}
                  onDelete={deleteDept}
                  onAddChild={openDeptCreate}
                  level={0}
                />
              ))
            )}
          </div>
        </div>

        {/* Right: Position list for selected department */}
        <div className="flex-1 bg-dark-900 rounded-lg border border-dark-800 flex flex-col">
          <div className="p-3 border-b border-dark-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Briefcase size={16} className="text-dark-400" />
              <span className="text-sm font-medium">
                {selectedDept ? `${selectedDept.name} — 岗位` : '请选择部门'}
              </span>
            </div>
            {selectedDept && (
              <button
                onClick={openPosCreate}
                className="flex items-center gap-1 px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs"
              >
                <Plus size={12} /> 新增岗位
              </button>
            )}
          </div>
          <div className="flex-1 overflow-y-auto">
            {!selectedDept ? (
              <p className="text-sm text-dark-500 text-center py-8">请选择左侧部门查看岗位</p>
            ) : posLoading ? (
              <p className="text-sm text-dark-500 text-center py-8">加载中...</p>
            ) : positions.length === 0 ? (
              <p className="text-sm text-dark-500 text-center py-8">该部门暂无岗位</p>
            ) : (
              <table className="w-full">
                <thead className="border-b border-dark-800">
                  <tr className="text-left text-dark-400 text-xs">
                    <th className="px-4 py-2">编码</th>
                    <th className="px-4 py-2">名称</th>
                    <th className="px-4 py-2">排序</th>
                    <th className="px-4 py-2">状态</th>
                    <th className="px-4 py-2 text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map(pos => (
                    <tr key={pos.id} className="border-b border-dark-800/50 hover:bg-dark-800/30">
                      <td className="px-4 py-2 text-sm font-mono text-dark-300">{pos.code}</td>
                      <td className="px-4 py-2 text-sm">{pos.name}</td>
                      <td className="px-4 py-2 text-sm text-dark-400">{pos.sort_order}</td>
                      <td className="px-4 py-2">
                        <span className={`text-xs px-1.5 py-0.5 rounded ${pos.is_active ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                          {pos.is_active ? '启用' : '停用'}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right">
                        <button onClick={() => openPosEdit(pos)} className="p-1 hover:bg-dark-700 rounded mr-1" title="编辑">
                          <Pencil size={14} className="text-dark-400" />
                        </button>
                        <button onClick={() => deletePos(pos.id)} className="p-1 hover:bg-dark-700 rounded" title="删除">
                          <Trash2 size={14} className="text-red-400" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Department Form Modal */}
      {showDeptForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-dark-900 rounded-xl border border-dark-800 w-[400px] p-6">
            <h3 className="text-lg font-semibold mb-4">{editingDept ? '编辑部门' : '新增部门'}</h3>
            <div className="space-y-3">
              {!editingDept && (
                <div>
                  <label className="block text-sm text-dark-400 mb-1">部门编码</label>
                  <input
                    type="text"
                    value={deptForm.code}
                    onChange={e => setDeptForm({ ...deptForm, code: e.target.value })}
                    className="w-full bg-dark-800 border border-dark-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
                    placeholder="如 tech、hr"
                  />
                </div>
              )}
              <div>
                <label className="block text-sm text-dark-400 mb-1">部门名称</label>
                <input
                  type="text"
                  value={deptForm.name}
                  onChange={e => setDeptForm({ ...deptForm, name: e.target.value })}
                  className="w-full bg-dark-800 border border-dark-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
                  placeholder="如 技术部"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">上级部门</label>
                <select
                  value={deptForm.parent_id ?? ''}
                  onChange={e => setDeptForm({ ...deptForm, parent_id: e.target.value ? Number(e.target.value) : null })}
                  className="w-full bg-dark-800 border border-dark-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
                >
                  <option value="">无（顶级部门）</option>
                  {departments.filter(d => d.id !== editingDept?.id).map(d => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">排序</label>
                <input
                  type="number"
                  value={deptForm.sort_order}
                  onChange={e => setDeptForm({ ...deptForm, sort_order: Number(e.target.value) })}
                  className="w-full bg-dark-800 border border-dark-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setShowDeptForm(false)} className="px-3 py-1.5 text-sm text-dark-400 hover:text-white">取消</button>
              <button onClick={saveDept} className="px-3 py-1.5 text-sm bg-primary-600 hover:bg-primary-700 rounded">保存</button>
            </div>
          </div>
        </div>
      )}

      {/* Position Form Modal */}
      {showPosForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-dark-900 rounded-xl border border-dark-800 w-[400px] p-6">
            <h3 className="text-lg font-semibold mb-4">{editingPos ? '编辑岗位' : '新增岗位'}</h3>
            <div className="space-y-3">
              {!editingPos && (
                <div>
                  <label className="block text-sm text-dark-400 mb-1">岗位编码</label>
                  <input
                    type="text"
                    value={posForm.code}
                    onChange={e => setPosForm({ ...posForm, code: e.target.value })}
                    className="w-full bg-dark-800 border border-dark-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
                    placeholder="如 dev、pm"
                  />
                </div>
              )}
              <div>
                <label className="block text-sm text-dark-400 mb-1">岗位名称</label>
                <input
                  type="text"
                  value={posForm.name}
                  onChange={e => setPosForm({ ...posForm, name: e.target.value })}
                  className="w-full bg-dark-800 border border-dark-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
                  placeholder="如 开发工程师"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">排序</label>
                <input
                  type="number"
                  value={posForm.sort_order}
                  onChange={e => setPosForm({ ...posForm, sort_order: Number(e.target.value) })}
                  className="w-full bg-dark-800 border border-dark-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setShowPosForm(false)} className="px-3 py-1.5 text-sm text-dark-400 hover:text-white">取消</button>
              <button onClick={savePos} className="px-3 py-1.5 text-sm bg-primary-600 hover:bg-primary-700 rounded">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---- Department Tree Node Component ----
function DeptTreeNode({
  node, selectedId, onSelect, onEdit, onDelete, onAddChild, level,
}: {
  node: SysDepartmentTree
  selectedId: number | null
  onSelect: (dept: SysDepartment) => void
  onEdit: (dept: SysDepartment) => void
  onDelete: (id: number) => void
  onAddChild: (parentId: number) => void
  level: number
}) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = node.children && node.children.length > 0
  const isSelected = selectedId === node.id

  return (
    <div>
      <div
        className={`flex items-center gap-1 px-2 py-1.5 rounded text-sm cursor-pointer group ${
          isSelected ? 'bg-primary-600/20 text-primary-400' : 'text-dark-300 hover:bg-dark-800'
        }`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
      >
        <button
          onClick={() => hasChildren && setExpanded(!expanded)}
          className="w-4 h-4 flex items-center justify-center"
        >
          {hasChildren ? (
            expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />
          ) : (
            <span className="w-3" />
          )}
        </button>
        <span className="flex-1 truncate" onClick={() => onSelect(node)}>
          {node.name}
        </span>
        <div className="hidden group-hover:flex items-center gap-0.5">
          <button onClick={() => onAddChild(node.id)} className="p-0.5 hover:bg-dark-700 rounded" title="添加子部门">
            <Plus size={12} className="text-primary-400" />
          </button>
          <button onClick={() => onEdit(node)} className="p-0.5 hover:bg-dark-700 rounded" title="编辑">
            <Pencil size={12} className="text-dark-400" />
          </button>
          <button onClick={() => onDelete(node.id)} className="p-0.5 hover:bg-dark-700 rounded" title="删除">
            <Trash2 size={12} className="text-red-400" />
          </button>
        </div>
      </div>
      {hasChildren && expanded && (
        <div>
          {node.children.map(child => (
            <DeptTreeNode
              key={child.id}
              node={child}
              selectedId={selectedId}
              onSelect={onSelect}
              onEdit={onEdit}
              onDelete={onDelete}
              onAddChild={onAddChild}
              level={level + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}
