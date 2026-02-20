import { useEffect, useState } from 'react'
import { Shield, Plus, Pencil, Trash2, RefreshCw, Check, ChevronRight, ChevronDown, Users } from 'lucide-react'
import { rbacApi, SysRole, SysRoleDetail, SysPermission, PermissionTreeNode } from '../../services/api'

type TabKey = 'roles' | 'permissions'

export default function RbacManagement() {
  const [tab, setTab] = useState<TabKey>('roles')

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-6 h-6 text-primary-400" />
          <h1 className="text-xl font-bold text-white">权限管理</h1>
        </div>
        <div className="flex gap-1 bg-dark-800 rounded-lg p-1">
          {([['roles', '角色管理'], ['permissions', '权限管理']] as [TabKey, string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-1.5 rounded-md text-sm transition-colors ${
                tab === key ? 'bg-primary-500/20 text-primary-400' : 'text-dark-300 hover:text-white'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'roles' ? <RolesTab /> : <PermissionsTab />}
    </div>
  )
}

// ========== Roles Tab ==========

function RolesTab() {
  const [roles, setRoles] = useState<SysRole[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedRole, setSelectedRole] = useState<SysRoleDetail | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingRole, setEditingRole] = useState<SysRole | null>(null)
  const [formData, setFormData] = useState({ code: '', name: '', description: '', data_scope: 'ALL', sort_order: 0 })
  const [allPermissions, setAllPermissions] = useState<SysPermission[]>([])
  const [assignedPermIds, setAssignedPermIds] = useState<Set<number>>(new Set())
  const [saving, setSaving] = useState(false)

  useEffect(() => { loadRoles() }, [])

  const loadRoles = async () => {
    try {
      setLoading(true)
      const [r, p] = await Promise.all([rbacApi.getRoles(true), rbacApi.getPermissions()])
      setRoles(r)
      setAllPermissions(p)
    } catch (err) {
      console.error('Failed to load roles:', err)
    } finally {
      setLoading(false)
    }
  }

  const selectRole = async (role: SysRole) => {
    try {
      const detail = await rbacApi.getRole(role.id)
      setSelectedRole(detail)
      setAssignedPermIds(new Set(detail.permissions.map(p => p.id)))
    } catch (err) {
      console.error('Failed to load role detail:', err)
    }
  }

  const openCreateForm = () => {
    setEditingRole(null)
    setFormData({ code: '', name: '', description: '', data_scope: 'ALL', sort_order: 0 })
    setShowForm(true)
  }

  const openEditForm = (role: SysRole) => {
    setEditingRole(role)
    setFormData({ code: role.code, name: role.name, description: role.description, data_scope: role.data_scope, sort_order: role.sort_order })
    setShowForm(true)
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      if (editingRole) {
        await rbacApi.updateRole(editingRole.id, { name: formData.name, description: formData.description, data_scope: formData.data_scope, sort_order: formData.sort_order })
      } else {
        await rbacApi.createRole(formData)
      }
      setShowForm(false)
      loadRoles()
    } catch (err: any) {
      alert(err.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (role: SysRole) => {
    if (!confirm(`确认删除角色「${role.name}」？`)) return
    try {
      await rbacApi.deleteRole(role.id)
      if (selectedRole?.id === role.id) setSelectedRole(null)
      loadRoles()
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  const togglePermission = (permId: number) => {
    setAssignedPermIds(prev => {
      const next = new Set(prev)
      if (next.has(permId)) next.delete(permId)
      else next.add(permId)
      return next
    })
  }

  const savePermissions = async () => {
    if (!selectedRole) return
    try {
      setSaving(true)
      await rbacApi.assignPermissions(selectedRole.id, Array.from(assignedPermIds))
      await selectRole(selectedRole)
      loadRoles()
    } catch (err: any) {
      alert(err.response?.data?.detail || '保存权限失败')
    } finally {
      setSaving(false)
    }
  }

  // Group permissions by resource
  const permsByResource: Record<string, SysPermission[]> = {}
  allPermissions.forEach(p => {
    const key = p.resource || '其他'
    if (!permsByResource[key]) permsByResource[key] = []
    permsByResource[key].push(p)
  })

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* Left: Role List */}
      <div className="col-span-4 bg-dark-900 rounded-lg border border-dark-800">
        <div className="flex items-center justify-between p-3 border-b border-dark-800">
          <span className="text-sm font-medium text-dark-200">角色列表</span>
          <div className="flex gap-1">
            <button onClick={loadRoles} className="p-1 hover:bg-dark-700 rounded" title="刷新"><RefreshCw className="w-4 h-4 text-dark-400" /></button>
            <button onClick={openCreateForm} className="p-1 hover:bg-dark-700 rounded" title="新增"><Plus className="w-4 h-4 text-primary-400" /></button>
          </div>
        </div>
        {loading ? (
          <div className="p-4 text-center text-dark-400 text-sm">加载中...</div>
        ) : roles.length === 0 ? (
          <div className="p-4 text-center text-dark-400 text-sm">暂无角色</div>
        ) : (
          <div className="divide-y divide-dark-800">
            {roles.map(role => (
              <div
                key={role.id}
                onClick={() => selectRole(role)}
                className={`p-3 cursor-pointer hover:bg-dark-800/50 flex items-center justify-between ${
                  selectedRole?.id === role.id ? 'bg-dark-800' : ''
                }`}
              >
                <div>
                  <div className="text-sm text-white flex items-center gap-2">
                    {role.name}
                    {role.is_system && <span className="text-xs bg-primary-500/20 text-primary-400 px-1.5 py-0.5 rounded">系统</span>}
                    {!role.is_active && <span className="text-xs bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded">停用</span>}
                  </div>
                  <div className="text-xs text-dark-400 mt-0.5 flex items-center gap-1.5">
                    <span>{role.code}</span>
                    <span>·</span>
                    <span>{role.permission_count} 权限</span>
                    <span>·</span>
                    <span className={`px-1.5 py-0.5 rounded ${
                      role.data_scope === 'ALL' ? 'bg-blue-500/20 text-blue-400' :
                      role.data_scope === 'SELF' ? 'bg-amber-500/20 text-amber-400' :
                      'bg-green-500/20 text-green-400'
                    }`}>
                      {role.data_scope === 'ALL' ? '全部数据' :
                       role.data_scope === 'DEPT' ? '本部门' :
                       role.data_scope === 'DEPT_AND_BELOW' ? '本部门及下级' :
                       role.data_scope === 'SELF' ? '仅本人' : role.data_scope}
                    </span>
                  </div>
                </div>
                <div className="flex gap-1">
                  <button onClick={(e) => { e.stopPropagation(); openEditForm(role) }} className="p-1 hover:bg-dark-700 rounded"><Pencil className="w-3.5 h-3.5 text-dark-400" /></button>
                  {!role.is_system && (
                    <button onClick={(e) => { e.stopPropagation(); handleDelete(role) }} className="p-1 hover:bg-dark-700 rounded"><Trash2 className="w-3.5 h-3.5 text-red-400" /></button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right: Permission Assignment */}
      <div className="col-span-8 bg-dark-900 rounded-lg border border-dark-800">
        {selectedRole ? (
          <>
            <div className="flex items-center justify-between p-3 border-b border-dark-800">
              <span className="text-sm font-medium text-dark-200">
                权限配置 — {selectedRole.name}
              </span>
              <button
                onClick={savePermissions}
                disabled={saving}
                className="px-3 py-1 bg-primary-500 hover:bg-primary-600 text-white text-sm rounded disabled:opacity-50"
              >
                {saving ? '保存中...' : '保存权限'}
              </button>
            </div>
            <div className="p-3 max-h-[600px] overflow-y-auto space-y-3">
              {Object.entries(permsByResource).map(([resource, perms]) => (
                <div key={resource} className="border border-dark-700 rounded-lg p-2">
                  <div className="text-xs font-medium text-dark-300 mb-2 uppercase">{resource}</div>
                  <div className="flex flex-wrap gap-2">
                    {perms.map(p => (
                      <label
                        key={p.id}
                        className={`flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer text-sm border transition-colors ${
                          assignedPermIds.has(p.id)
                            ? 'border-primary-500/50 bg-primary-500/10 text-primary-300'
                            : 'border-dark-700 text-dark-400 hover:border-dark-500'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={assignedPermIds.has(p.id)}
                          onChange={() => togglePermission(p.id)}
                          className="hidden"
                        />
                        {assignedPermIds.has(p.id) && <Check className="w-3 h-3" />}
                        {p.name}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-64 text-dark-400 text-sm">
            <div className="text-center">
              <Users className="w-10 h-10 mx-auto mb-2 opacity-30" />
              请选择左侧角色查看权限配置
            </div>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-dark-900 rounded-lg border border-dark-700 p-6 w-[420px]">
            <h3 className="text-lg font-medium text-white mb-4">
              {editingRole ? '编辑角色' : '新增角色'}
            </h3>
            <div className="space-y-3">
              {!editingRole && (
                <div>
                  <label className="text-sm text-dark-300">角色编码</label>
                  <input
                    value={formData.code}
                    onChange={e => setFormData(f => ({ ...f, code: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                    placeholder="如: auditor"
                  />
                </div>
              )}
              <div>
                <label className="text-sm text-dark-300">角色名称</label>
                <input
                  value={formData.name}
                  onChange={e => setFormData(f => ({ ...f, name: e.target.value }))}
                  className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                  placeholder="如: 审计员"
                />
              </div>
              <div>
                <label className="text-sm text-dark-300">描述</label>
                <input
                  value={formData.description}
                  onChange={e => setFormData(f => ({ ...f, description: e.target.value }))}
                  className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                />
              </div>
              <div>
                <label className="text-sm text-dark-300">数据范围</label>
                <select
                  value={formData.data_scope}
                  onChange={e => setFormData(f => ({ ...f, data_scope: e.target.value }))}
                  className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                >
                  <option value="ALL">全部数据（集团管理员）</option>
                  <option value="DEPT_AND_BELOW">本分店及下级部门</option>
                  <option value="DEPT">仅本部门</option>
                  <option value="SELF">仅本人数据</option>
                </select>
                <p className="text-xs text-dark-500 mt-1">
                  {formData.data_scope === 'ALL' ? '可查看和操作所有分店的数据' :
                   formData.data_scope === 'DEPT_AND_BELOW' ? '可查看所属分店及其下属部门的数据' :
                   formData.data_scope === 'DEPT' ? '只能查看所属部门的数据' :
                   '只能查看和操作自己创建的数据'}
                </p>
              </div>
              <div>
                <label className="text-sm text-dark-300">排序</label>
                <input
                  type="number"
                  value={formData.sort_order}
                  onChange={e => setFormData(f => ({ ...f, sort_order: parseInt(e.target.value) || 0 }))}
                  className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-dark-300 hover:text-white">取消</button>
              <button onClick={handleSave} disabled={saving} className="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white text-sm rounded disabled:opacity-50">
                {saving ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ========== Permissions Tab ==========

function PermissionsTab() {
  const [permissions, setPermissions] = useState<SysPermission[]>([])
  const [tree, setTree] = useState<PermissionTreeNode[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<'list' | 'tree'>('list')
  const [showForm, setShowForm] = useState(false)
  const [editingPerm, setEditingPerm] = useState<SysPermission | null>(null)
  const [formData, setFormData] = useState({ code: '', name: '', type: 'api', resource: '', action: '', parent_id: null as number | null, sort_order: 0 })
  const [saving, setSaving] = useState(false)

  useEffect(() => { loadPermissions() }, [])

  const loadPermissions = async () => {
    try {
      setLoading(true)
      const [p, t] = await Promise.all([rbacApi.getPermissions(), rbacApi.getPermissionTree()])
      setPermissions(p)
      setTree(t)
    } catch (err) {
      console.error('Failed to load permissions:', err)
    } finally {
      setLoading(false)
    }
  }

  const openCreateForm = () => {
    setEditingPerm(null)
    setFormData({ code: '', name: '', type: 'api', resource: '', action: '', parent_id: null, sort_order: 0 })
    setShowForm(true)
  }

  const openEditForm = (perm: SysPermission) => {
    setEditingPerm(perm)
    setFormData({ code: perm.code, name: perm.name, type: perm.type, resource: perm.resource, action: perm.action, parent_id: perm.parent_id, sort_order: perm.sort_order })
    setShowForm(true)
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      if (editingPerm) {
        await rbacApi.updatePermission(editingPerm.id, { name: formData.name, type: formData.type, resource: formData.resource, action: formData.action, sort_order: formData.sort_order })
      } else {
        await rbacApi.createPermission(formData)
      }
      setShowForm(false)
      loadPermissions()
    } catch (err: any) {
      alert(err.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (perm: SysPermission) => {
    if (!confirm(`确认删除权限「${perm.name}」？`)) return
    try {
      await rbacApi.deletePermission(perm.id)
      loadPermissions()
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  const typeColors: Record<string, string> = {
    api: 'text-blue-400 bg-blue-500/10',
    menu: 'text-green-400 bg-green-500/10',
    button: 'text-yellow-400 bg-yellow-500/10',
    data: 'text-purple-400 bg-purple-500/10',
  }

  return (
    <div className="bg-dark-900 rounded-lg border border-dark-800">
      <div className="flex items-center justify-between p-3 border-b border-dark-800">
        <span className="text-sm font-medium text-dark-200">权限列表 ({permissions.length})</span>
        <div className="flex gap-2">
          <div className="flex gap-1 bg-dark-800 rounded p-0.5">
            <button onClick={() => setViewMode('list')} className={`px-2 py-0.5 rounded text-xs ${viewMode === 'list' ? 'bg-dark-700 text-white' : 'text-dark-400'}`}>列表</button>
            <button onClick={() => setViewMode('tree')} className={`px-2 py-0.5 rounded text-xs ${viewMode === 'tree' ? 'bg-dark-700 text-white' : 'text-dark-400'}`}>树形</button>
          </div>
          <button onClick={loadPermissions} className="p-1 hover:bg-dark-700 rounded"><RefreshCw className="w-4 h-4 text-dark-400" /></button>
          <button onClick={openCreateForm} className="p-1 hover:bg-dark-700 rounded"><Plus className="w-4 h-4 text-primary-400" /></button>
        </div>
      </div>

      {loading ? (
        <div className="p-4 text-center text-dark-400 text-sm">加载中...</div>
      ) : viewMode === 'list' ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-dark-400 text-xs border-b border-dark-800">
              <th className="text-left p-3">编码</th>
              <th className="text-left p-3">名称</th>
              <th className="text-left p-3">类型</th>
              <th className="text-left p-3">资源</th>
              <th className="text-left p-3">操作</th>
              <th className="text-right p-3">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-800">
            {permissions.map(p => (
              <tr key={p.id} className="hover:bg-dark-800/50">
                <td className="p-3 text-dark-200 font-mono text-xs">{p.code}</td>
                <td className="p-3 text-white">{p.name}</td>
                <td className="p-3"><span className={`text-xs px-1.5 py-0.5 rounded ${typeColors[p.type] || 'text-dark-400'}`}>{p.type}</span></td>
                <td className="p-3 text-dark-300">{p.resource}</td>
                <td className="p-3 text-dark-300">{p.action}</td>
                <td className="p-3 text-right">
                  <div className="flex justify-end gap-1">
                    <button onClick={() => openEditForm(p)} className="p-1 hover:bg-dark-700 rounded"><Pencil className="w-3.5 h-3.5 text-dark-400" /></button>
                    <button onClick={() => handleDelete(p)} className="p-1 hover:bg-dark-700 rounded"><Trash2 className="w-3.5 h-3.5 text-red-400" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="p-3 space-y-1">
          {tree.map(node => <TreeNode key={node.id} node={node} onEdit={openEditForm} onDelete={handleDelete} typeColors={typeColors} />)}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-dark-900 rounded-lg border border-dark-700 p-6 w-[420px]">
            <h3 className="text-lg font-medium text-white mb-4">
              {editingPerm ? '编辑权限' : '新增权限'}
            </h3>
            <div className="space-y-3">
              {!editingPerm && (
                <div>
                  <label className="text-sm text-dark-300">权限编码</label>
                  <input
                    value={formData.code}
                    onChange={e => setFormData(f => ({ ...f, code: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                    placeholder="如: room:view"
                  />
                </div>
              )}
              <div>
                <label className="text-sm text-dark-300">权限名称</label>
                <input
                  value={formData.name}
                  onChange={e => setFormData(f => ({ ...f, name: e.target.value }))}
                  className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-sm text-dark-300">类型</label>
                  <select
                    value={formData.type}
                    onChange={e => setFormData(f => ({ ...f, type: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                  >
                    <option value="api">api</option>
                    <option value="menu">menu</option>
                    <option value="button">button</option>
                    <option value="data">data</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm text-dark-300">资源</label>
                  <input
                    value={formData.resource}
                    onChange={e => setFormData(f => ({ ...f, resource: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                    placeholder="room"
                  />
                </div>
                <div>
                  <label className="text-sm text-dark-300">操作</label>
                  <input
                    value={formData.action}
                    onChange={e => setFormData(f => ({ ...f, action: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                    placeholder="view"
                  />
                </div>
              </div>
              <div>
                <label className="text-sm text-dark-300">排序</label>
                <input
                  type="number"
                  value={formData.sort_order}
                  onChange={e => setFormData(f => ({ ...f, sort_order: parseInt(e.target.value) || 0 }))}
                  className="w-full mt-1 px-3 py-2 bg-dark-800 border border-dark-700 rounded text-white text-sm"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-dark-300 hover:text-white">取消</button>
              <button onClick={handleSave} disabled={saving} className="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white text-sm rounded disabled:opacity-50">
                {saving ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ========== Tree Node Component ==========

function TreeNode({
  node, onEdit, onDelete, typeColors, depth = 0,
}: {
  node: PermissionTreeNode
  onEdit: (p: SysPermission) => void
  onDelete: (p: SysPermission) => void
  typeColors: Record<string, string>
  depth?: number
}) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = node.children && node.children.length > 0

  return (
    <div>
      <div
        className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-dark-800/50 group"
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
      >
        <div className="flex items-center gap-2">
          {hasChildren ? (
            <button onClick={() => setExpanded(!expanded)} className="p-0.5">
              {expanded ? <ChevronDown className="w-3.5 h-3.5 text-dark-400" /> : <ChevronRight className="w-3.5 h-3.5 text-dark-400" />}
            </button>
          ) : (
            <span className="w-4.5" />
          )}
          <span className={`text-xs px-1.5 py-0.5 rounded ${typeColors[node.type] || 'text-dark-400'}`}>{node.type}</span>
          <span className="text-sm text-white">{node.name}</span>
          <span className="text-xs text-dark-500 font-mono">{node.code}</span>
        </div>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={() => onEdit(node)} className="p-1 hover:bg-dark-700 rounded"><Pencil className="w-3 h-3 text-dark-400" /></button>
          <button onClick={() => onDelete(node)} className="p-1 hover:bg-dark-700 rounded"><Trash2 className="w-3 h-3 text-red-400" /></button>
        </div>
      </div>
      {expanded && hasChildren && node.children.map(child => (
        <TreeNode key={child.id} node={child} onEdit={onEdit} onDelete={onDelete} typeColors={typeColors} depth={depth + 1} />
      ))}
    </div>
  )
}
