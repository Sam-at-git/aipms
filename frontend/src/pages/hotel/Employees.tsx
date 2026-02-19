import { useEffect, useState } from 'react'
import { Plus, RefreshCw, UserCog, Key } from 'lucide-react'
import { employeeApi } from '../../services/api'
import Modal, { ModalFooter } from '../../components/Modal'
import { useAuthStore, useUIStore } from '../../store'
import type { Employee, EmployeeRole } from '../../types'

const roleLabels: Record<EmployeeRole, string> = {
  sysadmin: '系统管理员',
  manager: '经理',
  receptionist: '前台',
  cleaner: '清洁员'
}

export default function Employees() {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [loading, setLoading] = useState(true)
  const { user: currentUser } = useAuthStore()
  const { openModal, closeModal } = useUIStore()
  const isSysadmin = currentUser?.role === 'sysadmin'

  // 新建员工表单
  const [form, setForm] = useState({
    username: '',
    password: '',
    name: '',
    phone: '',
    role: 'receptionist' as EmployeeRole
  })
  const [submitting, setSubmitting] = useState(false)
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null)
  const [newPassword, setNewPassword] = useState('')

  useEffect(() => {
    loadData()
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

  const handleCreate = async () => {
    if (!form.username || !form.password || !form.name) return

    setSubmitting(true)
    try {
      await employeeApi.create(form)
      closeModal()
      loadData()
      setForm({
        username: '',
        password: '',
        name: '',
        phone: '',
        role: 'receptionist'
      })
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

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">员工管理</h1>
        <div className="flex gap-3">
          <button
            onClick={() => openModal('createEmployee')}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
          >
            <Plus size={18} />
            新增员工
          </button>
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
        </div>
      </div>

      {/* 员工列表 */}
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
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">手机号</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">状态</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">操作</th>
              </tr>
            </thead>
            <tbody>
              {employees.map(emp => (
                <tr key={emp.id} className="border-t border-dark-800 hover:bg-dark-800/50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <UserCog size={18} className="text-dark-400" />
                      <span className="font-medium">{emp.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-sm">{emp.username}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs ${
                      emp.role === 'sysadmin' ? 'bg-red-500/20 text-red-400' :
                      emp.role === 'manager' ? 'bg-purple-500/20 text-purple-400' :
                      emp.role === 'receptionist' ? 'bg-blue-500/20 text-blue-400' :
                      'bg-emerald-500/20 text-emerald-400'
                    }`}>
                      {roleLabels[emp.role]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-dark-400">{emp.phone || '-'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs ${
                      emp.is_active ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {emp.is_active ? '启用' : '停用'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {emp.role === 'sysadmin' && !isSysadmin ? (
                      <span className="text-sm text-dark-500">—</span>
                    ) : (
                      <div className="flex gap-2">
                        <button
                          onClick={() => openResetModal(emp)}
                          className="flex items-center gap-1 text-sm text-dark-400 hover:text-primary-400"
                        >
                          <Key size={14} />
                          重置密码
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
            </tbody>
          </table>
        </div>
      )}

      {/* 新增员工弹窗 */}
      <Modal name="createEmployee" title="新增员工">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">姓名 *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入姓名"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">用户名 *</label>
            <input
              type="text"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入登录用户名"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">初始密码 *</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入初始密码"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">手机号</label>
            <input
              type="tel"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入手机号"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">角色 *</label>
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as EmployeeRole })}
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

      {/* 重置密码弹窗 */}
      <Modal name="resetPassword" title={`重置密码 - ${selectedEmployee?.name || ''}`}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">新密码</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入新密码"
            />
          </div>
          <ModalFooter
            onCancel={() => {
              closeModal()
              setNewPassword('')
              setSelectedEmployee(null)
            }}
            onConfirm={handleResetPassword}
            confirmText="重置"
            loading={submitting}
          />
        </div>
      </Modal>
    </div>
  )
}
