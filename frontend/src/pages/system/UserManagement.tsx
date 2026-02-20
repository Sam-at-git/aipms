/**
 * UserManagement - System-level user management page
 * Features: user CRUD, branch/department display, role assignment, branch filter
 */
import { useEffect, useState } from 'react'
import { Plus, RefreshCw, UserCog, Key, Shield, Search } from 'lucide-react'
import { employeeApi, rbacApi, orgApi, SysRole, UserRoleInfo } from '../../services/api'
import Modal, { ModalFooter } from '../../components/Modal'
import { useAuthStore, useUIStore } from '../../store'
import type { Employee, EmployeeRole } from '../../types'

const roleLabels: Record<string, string> = {
  sysadmin: '系统管理员',
  manager: '经理',
  receptionist: '前台',
  cleaner: '清洁员',
}

const dataScopeLabels: Record<string, string> = {
  ALL: '全部数据',
  DEPT_AND_BELOW: '本部门及下级',
  DEPT: '仅本部门',
  SELF: '仅个人',
}

interface BranchOption {
  id: number
  name: string
  code: string
}

export default function UserManagement() {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [loading, setLoading] = useState(true)
  const [branches, setBranches] = useState<BranchOption[]>([])
  const [allRoles, setAllRoles] = useState<SysRole[]>([])
  const { user: currentUser } = useAuthStore()
  const { openModal, closeModal } = useUIStore()
  const isSysadmin = currentUser?.role === 'sysadmin'

  // Filters
  const [filterBranch, setFilterBranch] = useState<string>('')
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [keyword, setKeyword] = useState('')

  // Create form
  const [form, setForm] = useState({
    username: '',
    password: '',
    name: '',
    phone: '',
    role: 'receptionist' as EmployeeRole,
  })
  const [submitting, setSubmitting] = useState(false)

  // Selected employee for actions
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null)
  const [newPassword, setNewPassword] = useState('')

  // Role assignment
  const [userRoles, setUserRoles] = useState<number[]>([])
  const [roleLoading, setRoleLoading] = useState(false)

  useEffect(() => {
    loadData()
    loadBranches()
    loadRoles()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await employeeApi.getList()
      setEmployees(data)
    } catch (err) {
      console.error('Failed to load employees:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadBranches = async () => {
    try {
      const data = await orgApi.getBranches()
      setBranches(data)
    } catch { /* ignore */ }
  }

  const loadRoles = async () => {
    try {
      const data = await rbacApi.getRoles()
      setAllRoles(data)
    } catch { /* ignore */ }
  }

  const handleCreate = async () => {
    if (!form.username || !form.password || !form.name) return
    setSubmitting(true)
    try {
      await employeeApi.create(form)
      closeModal()
      loadData()
      setForm({ username: '', password: '', name: '', phone: '', role: 'receptionist' })
    } catch (err) {
      console.error('Create failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleActive = async (emp: Employee) => {
    try {
      await employeeApi.update(emp.id, { is_active: !emp.is_active })
      loadData()
    } catch (err) {
      console.error('Update failed:', err)
    }
  }

  const handleResetPassword = async () => {
    if (!selectedEmployee || !newPassword) return
    setSubmitting(true)
    try {
      await employeeApi.resetPassword(selectedEmployee.id, newPassword)
      closeModal()
      setNewPassword('')
      setSelectedEmployee(null)
    } catch (err) {
      console.error('Reset password failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const openResetModal = (emp: Employee) => {
    setSelectedEmployee(emp)
    openModal('resetPassword')
  }

  const openRoleModal = async (emp: Employee) => {
    setSelectedEmployee(emp)
    setRoleLoading(true)
    openModal('assignRoles')
    try {
      const info: UserRoleInfo = await rbacApi.getUserRoles(emp.id)
      setUserRoles(info.roles.map(r => r.id))
    } catch {
      setUserRoles([])
    } finally {
      setRoleLoading(false)
    }
  }

  const handleAssignRoles = async () => {
    if (!selectedEmployee) return
    setSubmitting(true)
    try {
      await rbacApi.assignUserRoles(selectedEmployee.id, userRoles)
      closeModal()
      setSelectedEmployee(null)
      loadData()
    } catch (err) {
      console.error('Assign roles failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const toggleRole = (roleId: number) => {
    setUserRoles(prev =>
      prev.includes(roleId) ? prev.filter(id => id !== roleId) : [...prev, roleId]
    )
  }

  // Filter employees
  const filtered = employees.filter(emp => {
    if (filterBranch && String(emp.branch_id || '') !== filterBranch) return false
    if (filterStatus === 'active' && !emp.is_active) return false
    if (filterStatus === 'inactive' && emp.is_active) return false
    if (keyword) {
      const kw = keyword.toLowerCase()
      if (!emp.name.toLowerCase().includes(kw) && !emp.username.toLowerCase().includes(kw)) return false
    }
    return true
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">用户管理</h1>
        <div className="flex gap-3">
          <button
            onClick={() => openModal('createEmployee')}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
          >
            <Plus size={18} />
            新增用户
          </button>
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 items-center">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-400" />
          <input
            type="text"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="搜索用户名/姓名"
            className="pl-9 pr-3 py-1.5 bg-dark-800 border border-dark-700 rounded-lg text-sm focus:outline-none focus:border-primary-500 w-48"
          />
        </div>
        <select
          value={filterBranch}
          onChange={e => setFilterBranch(e.target.value)}
          className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary-500"
        >
          <option value="">全部分店</option>
          {branches.map(b => (
            <option key={b.id} value={b.id}>{b.name}</option>
          ))}
        </select>
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary-500"
        >
          <option value="">全部状态</option>
          <option value="active">启用</option>
          <option value="inactive">停用</option>
        </select>
        <span className="text-sm text-dark-500">{filtered.length} 条记录</span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </div>
      ) : (
        <div className="bg-dark-900 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-dark-800">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">姓名</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">用户名</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">角色</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">所属分店</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">手机号</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">状态</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(emp => (
                <tr key={emp.id} className="border-t border-dark-800 hover:bg-dark-800/50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <UserCog size={18} className="text-dark-400" />
                      <span className="font-medium">{emp.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-sm">{emp.username}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {emp.role_codes && emp.role_codes.length > 0
                        ? emp.role_codes.map(code => (
                            <span key={code} className={`px-2 py-0.5 rounded text-xs ${
                              code === 'sysadmin' ? 'bg-red-500/20 text-red-400' :
                              code === 'manager' ? 'bg-purple-500/20 text-purple-400' :
                              code === 'receptionist' ? 'bg-blue-500/20 text-blue-400' :
                              'bg-emerald-500/20 text-emerald-400'
                            }`}>
                              {roleLabels[code] || code}
                            </span>
                          ))
                        : (
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            emp.role === 'sysadmin' ? 'bg-red-500/20 text-red-400' :
                            emp.role === 'manager' ? 'bg-purple-500/20 text-purple-400' :
                            emp.role === 'receptionist' ? 'bg-blue-500/20 text-blue-400' :
                            'bg-emerald-500/20 text-emerald-400'
                          }`}>
                            {roleLabels[emp.role] || emp.role}
                          </span>
                        )
                      }
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {emp.branch_name
                      ? <span className="text-dark-300">{emp.branch_name}</span>
                      : <span className="text-dark-500">集团</span>
                    }
                  </td>
                  <td className="px-4 py-3 text-dark-400 text-sm">{emp.phone || '-'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      emp.is_active ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {emp.is_active ? '启用' : '停用'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {emp.role === 'sysadmin' && !isSysadmin ? (
                      <span className="text-sm text-dark-500">-</span>
                    ) : (
                      <div className="flex gap-2">
                        <button
                          onClick={() => openRoleModal(emp)}
                          className="flex items-center gap-1 text-sm text-dark-400 hover:text-primary-400"
                          title="分配角色"
                        >
                          <Shield size={14} />
                        </button>
                        <button
                          onClick={() => openResetModal(emp)}
                          className="flex items-center gap-1 text-sm text-dark-400 hover:text-primary-400"
                          title="重置密码"
                        >
                          <Key size={14} />
                        </button>
                        <button
                          onClick={() => handleToggleActive(emp)}
                          className={`text-sm ${
                            emp.is_active ? 'text-red-400 hover:text-red-300' : 'text-emerald-400 hover:text-emerald-300'
                          }`}
                        >
                          {emp.is_active ? '停用' : '启用'}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-dark-500">
                    暂无数据
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Employee Modal */}
      <Modal name="createEmployee" title="新增用户">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">姓名 *</label>
            <input
              type="text"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入姓名"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">用户名 *</label>
            <input
              type="text"
              value={form.username}
              onChange={e => setForm({ ...form, username: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入登录用户名"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">初始密码 *</label>
            <input
              type="password"
              value={form.password}
              onChange={e => setForm({ ...form, password: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入初始密码"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">手机号</label>
            <input
              type="tel"
              value={form.phone}
              onChange={e => setForm({ ...form, phone: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入手机号"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">角色 *</label>
            <select
              value={form.role}
              onChange={e => setForm({ ...form, role: e.target.value as EmployeeRole })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
            >
              <option value="receptionist">前台</option>
              <option value="cleaner">清洁员</option>
              <option value="manager">经理</option>
            </select>
          </div>
          <ModalFooter
            onCancel={closeModal}
            onConfirm={handleCreate}
            confirmText="创建"
            loading={submitting}
          />
        </div>
      </Modal>

      {/* Reset Password Modal */}
      <Modal name="resetPassword" title={`重置密码 - ${selectedEmployee?.name || ''}`}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">新密码</label>
            <input
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入新密码"
            />
          </div>
          <ModalFooter
            onCancel={() => { closeModal(); setNewPassword(''); setSelectedEmployee(null) }}
            onConfirm={handleResetPassword}
            confirmText="重置"
            loading={submitting}
          />
        </div>
      </Modal>

      {/* Assign Roles Modal */}
      <Modal name="assignRoles" title={`分配角色 - ${selectedEmployee?.name || ''}`}>
        <div className="space-y-4">
          {roleLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-500" />
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-dark-400 mb-3">选择要分配的角色：</p>
              {allRoles.map(role => (
                <label
                  key={role.id}
                  className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                    userRoles.includes(role.id) ? 'bg-primary-600/10 border border-primary-600/30' : 'bg-dark-800 border border-dark-700'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={userRoles.includes(role.id)}
                    onChange={() => toggleRole(role.id)}
                    className="rounded"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{role.name}</span>
                      <span className="text-xs text-dark-500">({role.code})</span>
                    </div>
                    {role.data_scope && (
                      <span className="text-xs text-dark-400">
                        数据范围: {dataScopeLabels[role.data_scope] || role.data_scope}
                      </span>
                    )}
                  </div>
                  {role.is_system && (
                    <span className="text-xs px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded">系统</span>
                  )}
                </label>
              ))}
            </div>
          )}
          <ModalFooter
            onCancel={() => { closeModal(); setSelectedEmployee(null) }}
            onConfirm={handleAssignRoles}
            confirmText="保存"
            loading={submitting}
          />
        </div>
      </Modal>
    </div>
  )
}
