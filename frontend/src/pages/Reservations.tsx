import { useEffect, useState } from 'react'
import { Plus, Search, Calendar, Phone, User, RefreshCw } from 'lucide-react'
import { reservationApi, roomApi, priceApi } from '../services/api'
import Modal, { ModalFooter } from '../components/Modal'
import { UndoButton } from '../components/UndoButton'
import { useUIStore } from '../store'
import type { Reservation, RoomType } from '../types'

const statusLabels: Record<string, { label: string; class: string }> = {
  confirmed: { label: '已确认', class: 'bg-primary-500/20 text-primary-400' },
  checked_in: { label: '已入住', class: 'bg-emerald-500/20 text-emerald-400' },
  completed: { label: '已完成', class: 'bg-gray-500/20 text-gray-400' },
  cancelled: { label: '已取消', class: 'bg-red-500/20 text-red-400' },
  no_show: { label: '未到', class: 'bg-yellow-500/20 text-yellow-400' }
}

export default function Reservations() {
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [roomTypes, setRoomTypes] = useState<RoomType[]>([])
  const [loading, setLoading] = useState(true)
  const [searchKeyword, setSearchKeyword] = useState('')
  const { openModal, closeModal } = useUIStore()

  // 新建预订表单
  const [form, setForm] = useState({
    guest_name: '',
    guest_phone: '',
    room_type_id: 0,
    check_in_date: '',
    check_out_date: '',
    room_count: 1,
    prepaid_amount: 0,
    special_requests: ''
  })
  const [calculatedPrice, setCalculatedPrice] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [reservationsData, typesData] = await Promise.all([
        reservationApi.getList(),
        roomApi.getRoomTypes()
      ])
      setReservations(reservationsData)
      setRoomTypes(typesData)
    } catch (err) {
      console.error('Failed to load data:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!searchKeyword.trim()) {
      loadData()
      return
    }
    try {
      const results = await reservationApi.search(searchKeyword)
      setReservations(results)
    } catch (err) {
      console.error('Search failed:', err)
    }
  }

  const calculatePrice = async () => {
    if (!form.room_type_id || !form.check_in_date || !form.check_out_date) return
    try {
      const result = await priceApi.calculate(
        form.room_type_id,
        form.check_in_date,
        form.check_out_date
      )
      setCalculatedPrice(result.total_amount)
    } catch (err) {
      console.error('Price calculation failed:', err)
    }
  }

  useEffect(() => {
    calculatePrice()
  }, [form.room_type_id, form.check_in_date, form.check_out_date])

  const handleCreate = async () => {
    if (!form.guest_name || !form.guest_phone || !form.room_type_id || !form.check_in_date || !form.check_out_date) {
      return
    }

    setSubmitting(true)
    try {
      await reservationApi.create(form)
      closeModal()
      loadData()
      setForm({
        guest_name: '',
        guest_phone: '',
        room_type_id: 0,
        check_in_date: '',
        check_out_date: '',
        room_count: 1,
        prepaid_amount: 0,
        special_requests: ''
      })
    } catch (err) {
      console.error('Create failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancel = async (id: number) => {
    if (!confirm('确定要取消这个预订吗？')) return
    try {
      await reservationApi.cancel(id, '用户取消')
      loadData()
    } catch (err) {
      console.error('Cancel failed:', err)
    }
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">预订管理</h1>
        <div className="flex gap-3">
          <button
            onClick={() => openModal('createReservation')}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
          >
            <Plus size={18} />
            新建预订
          </button>
          <UndoButton onUndoSuccess={loadData} />
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
        </div>
      </div>

      {/* 搜索 */}
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-400" />
          <input
            type="text"
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="搜索预订号、客人姓名、手机号..."
            className="w-full bg-dark-900 border border-dark-800 rounded-lg pl-10 pr-4 py-2.5 focus:outline-none focus:border-primary-500"
          />
        </div>
        <button
          onClick={handleSearch}
          className="px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
        >
          搜索
        </button>
      </div>

      {/* 预订列表 */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </div>
      ) : (
        <div className="bg-dark-900 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-dark-800">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">预订号</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">客人</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">房型</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">入住日期</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">离店日期</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">金额</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">状态</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">操作</th>
              </tr>
            </thead>
            <tbody>
              {reservations.map(r => (
                <tr key={r.id} className="border-t border-dark-800 hover:bg-dark-800/50">
                  <td className="px-4 py-3 font-mono text-sm">{r.reservation_no}</td>
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-medium">{r.guest_name}</p>
                      <p className="text-sm text-dark-400">{r.guest_phone}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">{r.room_type_name}</td>
                  <td className="px-4 py-3">{r.check_in_date}</td>
                  <td className="px-4 py-3">{r.check_out_date}</td>
                  <td className="px-4 py-3">¥{r.total_amount}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs ${statusLabels[r.status]?.class}`}>
                      {statusLabels[r.status]?.label}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {r.status === 'confirmed' && (
                      <button
                        onClick={() => handleCancel(r.id)}
                        className="text-sm text-red-400 hover:text-red-300"
                      >
                        取消
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {reservations.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-dark-500">
                    暂无预订记录
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 新建预订弹窗 */}
      <Modal name="createReservation" title="新建预订" size="lg">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">
                <User size={14} className="inline mr-1" />客人姓名 *
              </label>
              <input
                type="text"
                value={form.guest_name}
                onChange={(e) => setForm({ ...form, guest_name: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
                placeholder="请输入客人姓名"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">
                <Phone size={14} className="inline mr-1" />联系电话 *
              </label>
              <input
                type="tel"
                value={form.guest_phone}
                onChange={(e) => setForm({ ...form, guest_phone: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
                placeholder="请输入手机号"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">房型 *</label>
            <select
              value={form.room_type_id}
              onChange={(e) => setForm({ ...form, room_type_id: Number(e.target.value) })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
            >
              <option value={0}>请选择房型</option>
              {roomTypes.map(rt => (
                <option key={rt.id} value={rt.id}>{rt.name} - ¥{rt.base_price}/晚</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">
                <Calendar size={14} className="inline mr-1" />入住日期 *
              </label>
              <input
                type="date"
                value={form.check_in_date}
                onChange={(e) => setForm({ ...form, check_in_date: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">
                <Calendar size={14} className="inline mr-1" />离店日期 *
              </label>
              <input
                type="date"
                value={form.check_out_date}
                onChange={(e) => setForm({ ...form, check_out_date: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">房间数量</label>
              <input
                type="number"
                min={1}
                value={form.room_count}
                onChange={(e) => setForm({ ...form, room_count: Number(e.target.value) })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">预付金额</label>
              <input
                type="number"
                min={0}
                value={form.prepaid_amount}
                onChange={(e) => setForm({ ...form, prepaid_amount: Number(e.target.value) })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">特殊要求</label>
            <textarea
              value={form.special_requests}
              onChange={(e) => setForm({ ...form, special_requests: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              rows={2}
              placeholder="如需高楼层、加床等"
            />
          </div>

          {calculatedPrice !== null && (
            <div className="bg-dark-800 rounded-lg p-4">
              <div className="flex justify-between items-center">
                <span className="text-dark-400">预估房费</span>
                <span className="text-xl font-bold text-primary-400">¥{calculatedPrice}</span>
              </div>
            </div>
          )}

          <ModalFooter
            onCancel={closeModal}
            onConfirm={handleCreate}
            confirmText="创建预订"
            loading={submitting}
          />
        </div>
      </Modal>
    </div>
  )
}
