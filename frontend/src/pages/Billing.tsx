import { useEffect, useState } from 'react'
import { Search, CreditCard, Receipt } from 'lucide-react'
import { checkinApi, billingApi } from '../services/api'
import type { StayRecord, Bill } from '../types'

export default function Billing() {
  const [stays, setStays] = useState<StayRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [selectedBill, setSelectedBill] = useState<Bill | null>(null)

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

  const handleViewBill = async (stay: StayRecord) => {
    try {
      const bill = await billingApi.getBillByStay(stay.id)
      setSelectedBill(bill)
    } catch (err) {
      console.error('Failed to load bill:', err)
    }
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">账单管理</h1>
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

      <div className="grid grid-cols-2 gap-6">
        {/* 在住账单列表 */}
        <div className="bg-dark-900 rounded-xl p-4">
          <h2 className="text-lg font-medium mb-4 flex items-center gap-2">
            <Receipt size={20} />
            在住账单
          </h2>
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-500" />
            </div>
          ) : (
            <div className="space-y-2 max-h-[60vh] overflow-y-auto">
              {stays.map(stay => (
                <div
                  key={stay.id}
                  onClick={() => handleViewBill(stay)}
                  className={`p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedBill?.stay_record_id === stay.id
                      ? 'bg-primary-600/20 border border-primary-500'
                      : 'bg-dark-800 hover:bg-dark-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-bold text-primary-400">{stay.room_number}</span>
                      <span className="ml-2 text-dark-400">{stay.guest_name}</span>
                    </div>
                    <span className={`text-sm font-medium ${
                      stay.bill_balance > 0 ? 'text-red-400' : 'text-emerald-400'
                    }`}>
                      {stay.bill_balance > 0 ? `¥${stay.bill_balance}` : '已结清'}
                    </span>
                  </div>
                </div>
              ))}
              {stays.length === 0 && (
                <p className="text-center text-dark-500 py-4">暂无在住账单</p>
              )}
            </div>
          )}
        </div>

        {/* 账单详情 */}
        <div className="bg-dark-900 rounded-xl p-4">
          <h2 className="text-lg font-medium mb-4 flex items-center gap-2">
            <CreditCard size={20} />
            账单详情
          </h2>
          {selectedBill ? (
            <div className="space-y-4">
              {/* 金额汇总 */}
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="bg-dark-800 rounded-lg p-3">
                  <p className="text-sm text-dark-400">总金额</p>
                  <p className="text-xl font-bold">¥{selectedBill.total_amount}</p>
                </div>
                <div className="bg-dark-800 rounded-lg p-3">
                  <p className="text-sm text-dark-400">已付</p>
                  <p className="text-xl font-bold text-emerald-400">¥{selectedBill.paid_amount}</p>
                </div>
                <div className="bg-dark-800 rounded-lg p-3">
                  <p className="text-sm text-dark-400">余额</p>
                  <p className={`text-xl font-bold ${
                    selectedBill.balance > 0 ? 'text-red-400' : 'text-emerald-400'
                  }`}>
                    ¥{selectedBill.balance}
                  </p>
                </div>
              </div>

              {/* 调整信息 */}
              {selectedBill.adjustment_amount !== 0 && (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                  <p className="text-sm text-yellow-400">
                    账单调整：{selectedBill.adjustment_amount > 0 ? '+' : ''}¥{selectedBill.adjustment_amount}
                  </p>
                  {selectedBill.adjustment_reason && (
                    <p className="text-xs text-dark-400 mt-1">原因：{selectedBill.adjustment_reason}</p>
                  )}
                </div>
              )}

              {/* 支付记录 */}
              <div>
                <h3 className="text-sm font-medium text-dark-400 mb-2">支付记录</h3>
                {selectedBill.payments.length > 0 ? (
                  <div className="space-y-2">
                    {selectedBill.payments.map(payment => (
                      <div key={payment.id} className="flex items-center justify-between bg-dark-800 rounded-lg p-3">
                        <div>
                          <p className="font-medium">¥{payment.amount}</p>
                          <p className="text-xs text-dark-400">
                            {payment.method === 'cash' ? '现金' : '刷卡'} · {payment.operator_name || '系统'}
                          </p>
                        </div>
                        <p className="text-sm text-dark-400">
                          {new Date(payment.payment_time).toLocaleString()}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-center text-dark-500 py-4">暂无支付记录</p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-dark-500">
              请选择一个账单查看详情
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
