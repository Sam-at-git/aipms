import { useEffect, useState } from 'react'
import { Search, RefreshCw, Users, Star, Ban, Shield, Clock, History, Edit, Plus } from 'lucide-react'
import { guestApi } from '../../services/api'
import Modal, { ModalFooter } from '../../components/Modal'
import { useUIStore } from '../../store'
import type { Guest, GuestStayHistory, GuestReservationHistory } from '../../types'

const tierLabels = {
  normal: '普通',
  silver: '银卡',
  gold: '金卡',
  platinum: '白金'
}

const tierColors = {
  normal: 'bg-dark-700 text-dark-400',
  silver: 'bg-slate-500/20 text-slate-400',
  gold: 'bg-amber-500/20 text-amber-400',
  platinum: 'bg-purple-500/20 text-purple-400'
}

export default function Customers() {
  const [guests, setGuests] = useState<Guest[]>([])
  const [loading, setLoading] = useState(true)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [selectedGuest, setSelectedGuest] = useState<Guest | null>(null)
  const [stayHistory, setStayHistory] = useState<GuestStayHistory[]>([])
  const [reservationHistory, setReservationHistory] = useState<GuestReservationHistory[]>([])
  const { openModal, closeModal } = useUIStore()

  // 筛选条件
  const [filters, setFilters] = useState({
    tier: '',
    is_blacklisted: ''
  })

  // 编辑表单
  const [editForm, setEditForm] = useState({
    name: '',
    phone: '',
    email: '',
    id_number: '',
    tier: 'normal',
    notes: '',
    preferences: ''
  })
  const [submitting, setSubmitting] = useState(false)

  // 黑名单操作
  const [blacklistReason, setBlacklistReason] = useState('')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (filters.tier) params.tier = filters.tier
      if (filters.is_blacklisted !== '') params.is_blacklisted = filters.is_blacklisted === 'true'
      if (searchKeyword) params.search = searchKeyword

      const data = await guestApi.getList(params)
      setGuests(data)
    } catch (err) {
      console.error('Failed to load guests:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    loadData()
  }

  const handleFilter = () => {
    loadData()
  }

  const handleReset = () => {
    setFilters({ tier: '', is_blacklisted: '' })
    setSearchKeyword('')
    setTimeout(loadData, 0)
  }

  const handleViewDetail = async (guest: Guest) => {
    setSelectedGuest(guest)
    try {
      const [stays, reservations] = await Promise.all([
        guestApi.getStayHistory(guest.id, 5),
        guestApi.getReservationHistory(guest.id, 5)
      ])
      setStayHistory(stays)
      setReservationHistory(reservations)
    } catch (err) {
      console.error('Failed to load history:', err)
    }
    openModal('guestDetail')
  }

  const handleEdit = (guest: Guest) => {
    setSelectedGuest(guest)
    setEditForm({
      name: guest.name,
      phone: guest.phone || '',
      email: guest.email || '',
      id_number: guest.id_number || '',
      tier: guest.tier,
      notes: guest.notes || '',
      preferences: guest.preferences || ''
    })
    openModal('editGuest')
  }

  const handleSave = async () => {
    if (!selectedGuest) return

    setSubmitting(true)
    try {
      await guestApi.update(selectedGuest.id, {
        name: editForm.name,
        phone: editForm.phone || undefined,
        email: editForm.email || undefined,
        id_number: editForm.id_number || undefined,
        tier: editForm.tier,
        notes: editForm.notes || undefined
      })
      closeModal()
      loadData()
    } catch (err) {
      console.error('Update failed:', err)
      alert('保存失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleBlacklist = async (guest: Guest) => {
    if (guest.is_blacklisted) {
      if (!confirm(`确定要将 ${guest.name} 从黑名单移除吗？`)) return
      try {
        await guestApi.toggleBlacklist(guest.id, false)
        loadData()
      } catch (err) {
        console.error('Failed to remove from blacklist:', err)
      }
    } else {
      setSelectedGuest(guest)
      setBlacklistReason('')
      openModal('addToBlacklist')
    }
  }

  const handleConfirmBlacklist = async () => {
    if (!selectedGuest || !blacklistReason.trim()) {
      alert('请提供黑名单原因')
      return
    }

    try {
      await guestApi.toggleBlacklist(selectedGuest.id, true, blacklistReason)
      closeModal()
      loadData()
    } catch (err) {
      console.error('Failed to add to blacklist:', err)
      alert('操作失败')
    }
  }

  const handleUpdateTier = async (guest: Guest, newTier: string) => {
    if (!confirm(`确定要将 ${guest.name} 的等级从 ${tierLabels[guest.tier]} 更改为 ${tierLabels[newTier]} 吗？`)) return

    try {
      await guestApi.updateTier(guest.id, newTier)
      loadData()
    } catch (err) {
      console.error('Failed to update tier:', err)
      alert('更新失败')
    }
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">客户管理</h1>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      {/* 搜索和筛选 */}
      <div className="bg-dark-900 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Search size={18} className="text-dark-400" />
          <span className="text-sm font-medium">搜索和筛选</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-400" />
            <input
              type="text"
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="搜索姓名、手机号、证件号..."
              className="w-full bg-dark-800 border border-dark-700 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-primary-500"
            />
          </div>
          <select
            value={filters.tier}
            onChange={(e) => setFilters({ ...filters, tier: e.target.value })}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
          >
            <option value="">全部等级</option>
            <option value="normal">普通</option>
            <option value="silver">银卡</option>
            <option value="gold">金卡</option>
            <option value="platinum">白金</option>
          </select>
          <select
            value={filters.is_blacklisted}
            onChange={(e) => setFilters({ ...filters, is_blacklisted: e.target.value })}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
          >
            <option value="">全部状态</option>
            <option value="false">正常</option>
            <option value="true">黑名单</option>
          </select>
          <button
            onClick={handleFilter}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors text-sm"
          >
            筛选
          </button>
          <button
            onClick={handleReset}
            className="px-4 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg transition-colors text-sm"
          >
            重置
          </button>
        </div>
      </div>

      {/* 客户列表 */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </div>
      ) : (
        <div className="bg-dark-900 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-dark-800">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">客户信息</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">联系方式</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">等级</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">入住统计</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">累计消费</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">状态</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">操作</th>
              </tr>
            </thead>
            <tbody>
              {guests.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-dark-500">
                    暂无客户记录
                  </td>
                </tr>
              ) : (
                guests.map(guest => (
                  <tr key={guest.id} className="border-t border-dark-800 hover:bg-dark-800/50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Users size={18} className="text-dark-400" />
                        <span className="font-medium">{guest.name}</span>
                        {guest.is_blacklisted && (
                          <Ban size={16} className="text-red-400" title="黑名单" />
                        )}
                      </div>
                      {guest.id_number && (
                        <p className="text-xs text-dark-500 mt-1">{guest.id_number}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <p>{guest.phone || '-'}</p>
                      {guest.email && <p className="text-xs text-dark-500">{guest.email}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={guest.tier}
                        onChange={(e) => handleUpdateTier(guest, e.target.value)}
                        className={`px-2 py-1 rounded text-xs ${tierColors[guest.tier]} border-0 cursor-pointer`}
                      >
                        <option value="normal">普通</option>
                        <option value="silver">银卡</option>
                        <option value="gold">金卡</option>
                        <option value="platinum">白金</option>
                      </select>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <p>{guest.total_stays} 次</p>
                      {guest.last_stay_date && (
                        <p className="text-xs text-dark-500">
                          上次: {new Date(guest.last_stay_date).toLocaleDateString()}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className="text-primary-400">¥{parseFloat(guest.total_amount).toLocaleString()}</span>
                    </td>
                    <td className="px-4 py-3">
                      {guest.is_blacklisted ? (
                        <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs">
                          黑名单
                        </span>
                      ) : (
                        <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs">
                          正常
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleViewDetail(guest)}
                          className="text-dark-400 hover:text-primary-400"
                          title="查看详情"
                        >
                          <History size={16} />
                        </button>
                        <button
                          onClick={() => handleEdit(guest)}
                          className="text-dark-400 hover:text-primary-400"
                          title="编辑"
                        >
                          <Edit size={16} />
                        </button>
                        <button
                          onClick={() => handleToggleBlacklist(guest)}
                          className={`hover:text-${guest.is_blacklisted ? 'emerald' : 'red'}-400`}
                          title={guest.is_blacklisted ? '移除黑名单' : '加入黑名单'}
                        >
                          <Ban size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 客户详情弹窗 */}
      <Modal name="guestDetail" title="客户详情" size="lg">
        {selectedGuest && (
          <div className="space-y-6">
            {/* 基本信息 */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-sm text-dark-400">姓名</label>
                <p className="font-medium">{selectedGuest.name}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">手机号</label>
                <p className="font-medium">{selectedGuest.phone || '-'}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">邮箱</label>
                <p className="font-medium">{selectedGuest.email || '-'}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">证件号</label>
                <p className="font-medium">{selectedGuest.id_number || '-'}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">客户等级</label>
                <p>
                  <span className={`px-2 py-1 rounded text-xs ${tierColors[selectedGuest.tier]}`}>
                    <Star size={12} className="inline mr-1" />
                    {tierLabels[selectedGuest.tier]}
                  </span>
                </p>
              </div>
              <div>
                <label className="text-sm text-dark-400">状态</label>
                <p>
                  {selectedGuest.is_blacklisted ? (
                    <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs">
                      <Ban size={12} className="inline mr-1" />
                      黑名单
                    </span>
                  ) : (
                    <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs">
                      <Shield size={12} className="inline mr-1" />
                      正常
                    </span>
                  )}
                </p>
              </div>
            </div>

            {/* 统计信息 */}
            <div className="bg-dark-800 rounded-lg p-4">
              <h3 className="font-medium mb-3">统计信息</h3>
              <div className="grid grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-primary-400">{selectedGuest.total_stays}</p>
                  <p className="text-xs text-dark-400">入住次数</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-primary-400">
                    ¥{parseFloat(selectedGuest.total_amount).toLocaleString()}
                  </p>
                  <p className="text-xs text-dark-400">累计消费</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-primary-400">
                    {selectedGuest.reservation_count || 0}
                  </p>
                  <p className="text-xs text-dark-400">预订次数</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-primary-400">
                    {selectedGuest.last_room_type || '-'}
                  </p>
                  <p className="text-xs text-dark-400">上次房型</p>
                </div>
              </div>
            </div>

            {/* 偏好和备注 */}
            {selectedGuest.preferences && (
              <div>
                <label className="text-sm text-dark-400">客户偏好</label>
                <pre className="bg-dark-800 rounded-lg p-3 text-sm text-dark-300 mt-1 overflow-x-auto">
                  {selectedGuest.preferences}
                </pre>
              </div>
            )}

            {selectedGuest.notes && (
              <div>
                <label className="text-sm text-dark-400">备注</label>
                <p className="text-sm bg-dark-800 rounded-lg p-3 mt-1">{selectedGuest.notes}</p>
              </div>
            )}

            {selectedGuest.is_blacklisted && selectedGuest.blacklist_reason && (
              <div className="bg-red-900/20 border border-red-700 rounded-lg p-3">
                <label className="text-sm text-red-400">黑名单原因</label>
                <p className="text-sm text-red-300 mt-1">{selectedGuest.blacklist_reason}</p>
              </div>
            )}

            {/* 入住历史 */}
            {stayHistory.length > 0 && (
              <div>
                <h3 className="font-medium mb-3 flex items-center gap-2">
                  <Clock size={18} />
                  入住历史
                </h3>
                <div className="max-h-40 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-dark-800">
                      <tr>
                        <th className="text-left px-3 py-2">房间</th>
                        <th className="text-left px-3 py-2">房型</th>
                        <th className="text-left px-3 py-2">入住时间</th>
                        <th className="text-left px-3 py-2">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stayHistory.map((stay) => (
                        <tr key={stay.id} className="border-t border-dark-800">
                          <td className="px-3 py-2">{stay.room_number}</td>
                          <td className="px-3 py-2">{stay.room_type}</td>
                          <td className="px-3 py-2">{new Date(stay.check_in_time).toLocaleDateString()}</td>
                          <td className="px-3 py-2">
                            {stay.status === 'checked_out' ? '已退房' : '在住'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="flex justify-end pt-4 border-t border-dark-800">
              <button
                onClick={closeModal}
                className="px-4 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg transition-colors"
              >
                关闭
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* 编辑客户弹窗 */}
      <Modal name="editGuest" title="编辑客户信息">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">姓名</label>
              <input
                type="text"
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">手机号</label>
              <input
                type="text"
                value={editForm.phone}
                onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">证件号</label>
              <input
                type="text"
                value={editForm.id_number}
                onChange={(e) => setEditForm({ ...editForm, id_number: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">邮箱</label>
              <input
                type="email"
                value={editForm.email}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">客户等级</label>
              <select
                value={editForm.tier}
                onChange={(e) => setEditForm({ ...editForm, tier: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              >
                <option value="normal">普通</option>
                <option value="silver">银卡</option>
                <option value="gold">金卡</option>
                <option value="platinum">白金</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">备注</label>
            <textarea
              value={editForm.notes}
              onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
              rows={3}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
            />
          </div>
          <ModalFooter
            onCancel={closeModal}
            onConfirm={handleSave}
            confirmText="保存"
            loading={submitting}
          />
        </div>
      </Modal>

      {/* 加入黑名单弹窗 */}
      <Modal name="addToBlacklist" title="加入黑名单">
        <div className="space-y-4">
          <p className="text-dark-300">
            确定要将 <span className="font-medium text-white">{selectedGuest?.name}</span> 加入黑名单吗？
          </p>
          <div>
            <label className="block text-sm text-dark-400 mb-1">原因 *</label>
            <textarea
              value={blacklistReason}
              onChange={(e) => setBlacklistReason(e.target.value)}
              rows={3}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="请输入加入黑名单的原因..."
            />
          </div>
          <ModalFooter
            onCancel={closeModal}
            onConfirm={handleConfirmBlacklist}
            confirmText="确认加入"
            confirmClass="bg-red-600 hover:bg-red-700"
          />
        </div>
      </Modal>
    </div>
  )
}
