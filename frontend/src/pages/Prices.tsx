import { useEffect, useState } from 'react'
import { Plus, RefreshCw, DollarSign, Calendar, Trash2, Edit, Calculator } from 'lucide-react'
import { priceApi, roomApi } from '../services/api'
import Modal, { ModalFooter } from '../components/Modal'
import { useUIStore } from '../store'
import type { RatePlan, RoomType } from '../types'

interface PriceCalendarDay {
  date: string
  price: number
  is_weekend: boolean
}

export default function Prices() {
  const [ratePlans, setRatePlans] = useState<RatePlan[]>([])
  const [roomTypes, setRoomTypes] = useState<RoomType[]>([])
  const [loading, setLoading] = useState(true)
  const { openModal, closeModal } = useUIStore()
  const [selectedPlan, setSelectedPlan] = useState<RatePlan | null>(null)

  // 价格策略表单
  const [form, setForm] = useState({
    name: '',
    room_type_id: 0,
    start_date: '',
    end_date: '',
    price: '',
    priority: 1,
    is_weekend: false,
    is_active: true
  })
  const [submitting, setSubmitting] = useState(false)
  const [isEditMode, setIsEditMode] = useState(false)

  // 价格日历
  const [calendarData, setCalendarData] = useState<PriceCalendarDay[]>([])
  const [calendarRoomTypeId, setCalendarRoomTypeId] = useState<number>(0)
  const [calendarStartDate, setCalendarStartDate] = useState('')
  const [calendarEndDate, setCalendarEndDate] = useState('')

  // 价格计算器
  const [calcForm, setCalcForm] = useState({
    room_type_id: 0,
    check_in_date: '',
    check_out_date: '',
    room_count: 1
  })
  const [calcResult, setCalcResult] = useState<any>(null)

  useEffect(() => {
    loadData()
    loadRoomTypes()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await priceApi.getRatePlans()
      setRatePlans(data)
    } catch (err) {
      console.error('Failed to load rate plans:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadRoomTypes = async () => {
    try {
      const data = await roomApi.getRoomTypes()
      setRoomTypes(data)
      if (data.length > 0) {
        setForm(prev => ({ ...prev, room_type_id: data[0].id }))
        setCalendarRoomTypeId(data[0].id)
        setCalcForm(prev => ({ ...prev, room_type_id: data[0].id }))
      }
    } catch (err) {
      console.error('Failed to load room types:', err)
    }
  }

  const handleCreate = () => {
    setIsEditMode(false)
    setForm({
      name: '',
      room_type_id: roomTypes[0]?.id || 0,
      start_date: new Date().toISOString().split('T')[0],
      end_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      price: '',
      priority: 1,
      is_weekend: false,
      is_active: true
    })
    openModal('ratePlanForm')
  }

  const handleEdit = (plan: RatePlan) => {
    setIsEditMode(true)
    setSelectedPlan(plan)
    setForm({
      name: plan.name,
      room_type_id: plan.room_type_id,
      start_date: plan.start_date,
      end_date: plan.end_date,
      price: plan.price.toString(),
      priority: plan.priority,
      is_weekend: plan.is_weekend,
      is_active: plan.is_active
    })
    openModal('ratePlanForm')
  }

  const handleSubmit = async () => {
    if (!form.name || !form.room_type_id || !form.start_date || !form.end_date || !form.price) return

    setSubmitting(true)
    try {
      const data = {
        name: form.name,
        room_type_id: form.room_type_id,
        start_date: form.start_date,
        end_date: form.end_date,
        price: parseFloat(form.price),
        priority: form.priority,
        is_weekend: form.is_weekend,
        is_active: form.is_active
      }

      if (isEditMode && selectedPlan) {
        await priceApi.updateRatePlan(selectedPlan.id, data)
      } else {
        await priceApi.createRatePlan(data)
      }

      closeModal()
      loadData()
    } catch (err) {
      console.error('Save failed:', err)
      alert('保存失败: ' + (err as any).response?.data?.detail || (err as any).message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (plan: RatePlan) => {
    if (!confirm(`确定要删除价格策略 "${plan.name}" 吗？`)) return

    try {
      await priceApi.deleteRatePlan(plan.id)
      loadData()
    } catch (err) {
      console.error('Delete failed:', err)
      alert('删除失败')
    }
  }

  const handleToggleActive = async (plan: RatePlan) => {
    try {
      await priceApi.updateRatePlan(plan.id, { is_active: !plan.is_active })
      loadData()
    } catch (err) {
      console.error('Update failed:', err)
    }
  }

  // 加载价格日历
  const loadCalendar = async () => {
    if (!calendarRoomTypeId || !calendarStartDate || !calendarEndDate) return

    try {
      const data = await priceApi.getPriceCalendar(calendarRoomTypeId, calendarStartDate, calendarEndDate)
      setCalendarData(data)
    } catch (err) {
      console.error('Failed to load calendar:', err)
    }
  }

  // 价格计算
  const handleCalculate = async () => {
    if (!calcForm.room_type_id || !calcForm.check_in_date || !calcForm.check_out_date) return

    try {
      const data = await priceApi.calculate(
        calcForm.room_type_id,
        calcForm.check_in_date,
        calcForm.check_out_date,
        calcForm.room_count
      )
      setCalcResult(data)
    } catch (err) {
      console.error('Calculate failed:', err)
      alert('计算失败: ' + (err as any).response?.data?.detail || (err as any).message)
    }
  }

  const getRoomTypeName = (roomTypeId: number) => {
    const rt = roomTypes.find(r => r.id === roomTypeId)
    return rt?.name || '-'
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">价格管理</h1>
        <div className="flex gap-3">
          <button
            onClick={() => openModal('priceCalculator')}
            className="flex items-center gap-2 px-4 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg transition-colors"
          >
            <Calculator size={18} />
            价格计算器
          </button>
          <button
            onClick={() => openModal('priceCalendar')}
            className="flex items-center gap-2 px-4 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg transition-colors"
          >
            <Calendar size={18} />
            价格日历
          </button>
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
          <button
            onClick={handleCreate}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
          >
            <Plus size={18} />
            新增策略
          </button>
        </div>
      </div>

      {/* 价格策略列表 */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </div>
      ) : (
        <div className="bg-dark-900 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-dark-800">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">策略名称</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">房型</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">价格</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">有效期</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">优先级</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">周末</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">状态</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-dark-400">操作</th>
              </tr>
            </thead>
            <tbody>
              {ratePlans.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-dark-500">
                    暂无价格策略
                  </td>
                </tr>
              ) : (
                ratePlans.map(plan => (
                  <tr key={plan.id} className="border-t border-dark-800 hover:bg-dark-800/50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <DollarSign size={18} className="text-primary-400" />
                        <span className="font-medium">{plan.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">{plan.room_type_name}</td>
                    <td className="px-4 py-3 font-mono">¥{parseFloat(plan.price).toFixed(2)}</td>
                    <td className="px-4 py-3 text-sm text-dark-400">
                      {plan.start_date} ~ {plan.end_date}
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 bg-dark-700 rounded text-xs">{plan.priority}</span>
                    </td>
                    <td className="px-4 py-3">
                      {plan.is_weekend ? (
                        <span className="px-2 py-1 bg-amber-500/20 text-amber-400 rounded text-xs">周末</span>
                      ) : (
                        <span className="px-2 py-1 bg-dark-700 text-dark-400 rounded text-xs">通用</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-xs cursor-pointer ${
                        plan.is_active ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                      }`} onClick={() => handleToggleActive(plan)}>
                        {plan.is_active ? '启用' : '停用'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleEdit(plan)}
                          className="text-dark-400 hover:text-primary-400"
                        >
                          <Edit size={16} />
                        </button>
                        <button
                          onClick={() => handleDelete(plan)}
                          className="text-dark-400 hover:text-red-400"
                        >
                          <Trash2 size={16} />
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

      {/* 价格策略表单弹窗 */}
      <Modal name="ratePlanForm" title={isEditMode ? '编辑价格策略' : '新增价格策略'}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">策略名称 *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              placeholder="如：春节特惠、周末促销"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">适用房型 *</label>
            <select
              value={form.room_type_id}
              onChange={(e) => setForm({ ...form, room_type_id: parseInt(e.target.value) })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
            >
              {roomTypes.map(rt => (
                <option key={rt.id} value={rt.id}>{rt.name} (基础价 ¥{rt.base_price})</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">开始日期 *</label>
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">结束日期 *</label>
              <input
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">策略价格 *</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">优先级</label>
              <input
                type="number"
                min="1"
                max="10"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
              <p className="text-xs text-dark-500 mt-1">数字越大优先级越高</p>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_weekend}
                onChange={(e) => setForm({ ...form, is_weekend: e.target.checked })}
                className="w-4 h-4 rounded border-dark-700 bg-dark-800 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm">仅周末有效</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                className="w-4 h-4 rounded border-dark-700 bg-dark-800 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm">启用</span>
            </label>
          </div>
          <ModalFooter
            onCancel={closeModal}
            onConfirm={handleSubmit}
            confirmText={isEditMode ? '保存' : '创建'}
            loading={submitting}
          />
        </div>
      </Modal>

      {/* 价格日历弹窗 */}
      <Modal name="priceCalendar" title="价格日历">
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">房型</label>
              <select
                value={calendarRoomTypeId}
                onChange={(e) => setCalendarRoomTypeId(parseInt(e.target.value))}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              >
                {roomTypes.map(rt => (
                  <option key={rt.id} value={rt.id}>{rt.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">开始日期</label>
              <input
                type="date"
                value={calendarStartDate}
                onChange={(e) => setCalendarStartDate(e.target.value)}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">结束日期</label>
              <input
                type="date"
                value={calendarEndDate}
                onChange={(e) => setCalendarEndDate(e.target.value)}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
          </div>
          <button
            onClick={loadCalendar}
            className="w-full py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
          >
            查询价格
          </button>

          {calendarData.length > 0 && (
            <div className="max-h-64 overflow-y-auto">
              <table className="w-full">
                <thead className="bg-dark-800 sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-2 text-sm font-medium text-dark-400">日期</th>
                    <th className="text-left px-3 py-2 text-sm font-medium text-dark-400">星期</th>
                    <th className="text-left px-3 py-2 text-sm font-medium text-dark-400">价格</th>
                  </tr>
                </thead>
                <tbody>
                  {calendarData.map((day, idx) => (
                    <tr key={idx} className={`border-t border-dark-800 ${day.is_weekend ? 'bg-amber-900/10' : ''}`}>
                      <td className="px-3 py-2 text-sm">{day.date}</td>
                      <td className="px-3 py-2 text-sm">
                        {day.is_weekend && <span className="text-amber-400">周末</span>}
                      </td>
                      <td className="px-3 py-2 font-mono text-primary-400">¥{parseFloat(day.price).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Modal>

      {/* 价格计算器弹窗 */}
      <Modal name="priceCalculator" title="价格计算器">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">房型</label>
            <select
              value={calcForm.room_type_id}
              onChange={(e) => setCalcForm({ ...calcForm, room_type_id: parseInt(e.target.value) })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
            >
              {roomTypes.map(rt => (
                <option key={rt.id} value={rt.id}>{rt.name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">入住日期 *</label>
              <input
                type="date"
                value={calcForm.check_in_date}
                onChange={(e) => setCalcForm({ ...calcForm, check_in_date: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">离店日期 *</label>
              <input
                type="date"
                value={calcForm.check_out_date}
                onChange={(e) => setCalcForm({ ...calcForm, check_out_date: e.target.value })}
                className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">房间数量</label>
            <input
              type="number"
              min="1"
              value={calcForm.room_count}
              onChange={(e) => setCalcForm({ ...calcForm, room_count: parseInt(e.target.value) || 1 })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
            />
          </div>
          <button
            onClick={handleCalculate}
            className="w-full py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
          >
            计算价格
          </button>

          {calcResult && (
            <div className="bg-dark-800 rounded-lg p-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-dark-400">入住天数</span>
                <span className="font-medium">{calcResult.nights} 晚</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dark-400">房间数量</span>
                <span className="font-medium">{calcResult.room_count} 间</span>
              </div>
              <div className="border-t border-dark-700 pt-2 flex justify-between">
                <span className="text-dark-400">总价</span>
                <span className="text-xl font-bold text-primary-400">¥{parseFloat(calcResult.total_amount).toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}
