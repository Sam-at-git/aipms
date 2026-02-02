import { useEffect, useState } from 'react'
import { Search, LogOut, RefreshCw, CreditCard } from 'lucide-react'
import { checkinApi, checkoutApi, billingApi } from '../services/api'
import Modal, { ModalFooter } from '../components/Modal'
import { useUIStore } from '../store'
import type { StayRecord, Bill } from '../types'

export default function Guests() {
  const [stays, setStays] = useState<StayRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [selectedStay, setSelectedStay] = useState<StayRecord | null>(null)
  const [bill, setBill] = useState<Bill | null>(null)
  const { openModal, closeModal } = useUIStore()

  // 支付表单
  const [paymentForm, setPaymentForm] = useState({
    amount: 0,
    method: 'cash' as 'cash' | 'card'
  })
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await checkinApi.getActiveStays()
      setStays(data)
    } catch (err) {
      console.error('Failed to load stays:', err)
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
      const results = await checkinApi.search(searchKeyword)
      setStays(results)
    } catch (err) {
      console.error('Search failed:', err)
    }
  }

  const handleViewDetail = async (stay: StayRecord) => {
    setSelectedStay(stay)
    try {
      const billData = await billingApi.getBillByStay(stay.id)
      setBill(billData)
    } catch (err) {
      console.error('Failed to load bill:', err)
    }
    openModal('stayDetail')
  }

  const handleCheckout = async () => {
    if (!selectedStay) return

    if (bill && bill.balance > 0) {
      if (!confirm(`账单尚有余额 ¥${bill.balance}，确定要退房吗？`)) {
        return
      }
    }

    setSubmitting(true)
    try {
      await checkoutApi.checkout({
        stay_record_id: selectedStay.id,
        allow_unsettled: true,
        unsettled_reason: '客人要求'
      })
      closeModal()
      loadData()
    } catch (err) {
      console.error('Checkout failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const handlePayment = async () => {
    if (!bill || paymentForm.amount <= 0) return

    setSubmitting(true)
    try {
      await billingApi.addPayment({
        bill_id: bill.id,
        amount: paymentForm.amount,
        method: paymentForm.method
      })
      // 刷新账单
      const updatedBill = await billingApi.getBillByStay(selectedStay!.id)
      setBill(updatedBill)
      setPaymentForm({ amount: 0, method: 'cash' })
    } catch (err) {
      console.error('Payment failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">在住客人</h1>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
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
            placeholder="搜索房间号、客人姓名..."
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

      {/* 在住列表 */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {stays.map(stay => (
            <div
              key={stay.id}
              onClick={() => handleViewDetail(stay)}
              className="bg-dark-900 rounded-xl p-4 cursor-pointer hover:bg-dark-800 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <span className="text-2xl font-bold text-primary-400">{stay.room_number}</span>
                  <span className="ml-2 text-dark-400">{stay.room_type_name}</span>
                </div>
                <span className={`px-2 py-1 rounded text-xs ${
                  stay.bill_balance > 0 ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'
                }`}>
                  {stay.bill_balance > 0 ? `待收 ¥${stay.bill_balance}` : '已结清'}
                </span>
              </div>
              <div className="space-y-1 text-sm">
                <p><span className="text-dark-400">住客：</span>{stay.guest_name}</p>
                <p><span className="text-dark-400">入住：</span>{new Date(stay.check_in_time).toLocaleDateString()}</p>
                <p><span className="text-dark-400">预离：</span>{stay.expected_check_out}</p>
              </div>
            </div>
          ))}
          {stays.length === 0 && (
            <div className="col-span-2 text-center text-dark-500 py-12">
              当前没有在住客人
            </div>
          )}
        </div>
      )}

      {/* 住宿详情弹窗 */}
      <Modal name="stayDetail" title={`${selectedStay?.room_number || ''}号房 - ${selectedStay?.guest_name || ''}`} size="lg">
        {selectedStay && (
          <div className="space-y-6">
            {/* 基本信息 */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-dark-400">房型</label>
                <p className="font-medium">{selectedStay.room_type_name}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">联系电话</label>
                <p className="font-medium">{selectedStay.guest_phone || '-'}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">入住时间</label>
                <p className="font-medium">{new Date(selectedStay.check_in_time).toLocaleString()}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">预计离店</label>
                <p className="font-medium">{selectedStay.expected_check_out}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">押金</label>
                <p className="font-medium">¥{selectedStay.deposit_amount}</p>
              </div>
            </div>

            {/* 账单信息 */}
            {bill && (
              <div className="bg-dark-800 rounded-lg p-4">
                <h3 className="font-medium mb-3 flex items-center gap-2">
                  <CreditCard size={18} />
                  账单信息
                </h3>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-sm text-dark-400">总金额</p>
                    <p className="text-lg font-bold">¥{bill.total_amount}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-400">已付</p>
                    <p className="text-lg font-bold text-emerald-400">¥{bill.paid_amount}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-400">余额</p>
                    <p className={`text-lg font-bold ${bill.balance > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                      ¥{bill.balance}
                    </p>
                  </div>
                </div>

                {/* 收款 */}
                {bill.balance > 0 && (
                  <div className="mt-4 pt-4 border-t border-dark-700">
                    <div className="flex gap-3">
                      <input
                        type="number"
                        min={0}
                        value={paymentForm.amount || ''}
                        onChange={(e) => setPaymentForm({ ...paymentForm, amount: Number(e.target.value) })}
                        placeholder="收款金额"
                        className="flex-1 bg-dark-700 border border-dark-600 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
                      />
                      <select
                        value={paymentForm.method}
                        onChange={(e) => setPaymentForm({ ...paymentForm, method: e.target.value as 'cash' | 'card' })}
                        className="bg-dark-700 border border-dark-600 rounded-lg px-3 py-2"
                      >
                        <option value="cash">现金</option>
                        <option value="card">刷卡</option>
                      </select>
                      <button
                        onClick={handlePayment}
                        disabled={paymentForm.amount <= 0 || submitting}
                        className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-lg transition-colors"
                      >
                        收款
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 操作按钮 */}
            <div className="flex justify-end gap-3 pt-4 border-t border-dark-800">
              <button
                onClick={closeModal}
                className="px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
              >
                关闭
              </button>
              <button
                onClick={handleCheckout}
                disabled={submitting}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-lg transition-colors"
              >
                <LogOut size={18} />
                {submitting ? '处理中...' : '办理退房'}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
