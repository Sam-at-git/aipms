import { useEffect, useState } from 'react'
import { Calendar, TrendingUp, DollarSign } from 'lucide-react'
import { reportApi } from '../services/api'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar
} from 'recharts'

export default function Reports() {
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0]
  })
  const [occupancyData, setOccupancyData] = useState<Array<{
    date: string
    occupancy_rate: number
    occupied_rooms: number
  }>>([])
  const [revenueData, setRevenueData] = useState<Array<{
    date: string
    revenue: number
  }>>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [dateRange])

  const loadData = async () => {
    setLoading(true)
    try {
      const [occupancy, revenue] = await Promise.all([
        reportApi.getOccupancy(dateRange.start, dateRange.end),
        reportApi.getRevenue(dateRange.start, dateRange.end)
      ])
      setOccupancyData(occupancy)
      setRevenueData(revenue)
    } catch (err) {
      console.error('Failed to load reports:', err)
    } finally {
      setLoading(false)
    }
  }

  // 计算统计数据
  const avgOccupancy = occupancyData.length > 0
    ? (occupancyData.reduce((sum, d) => sum + d.occupancy_rate, 0) / occupancyData.length).toFixed(1)
    : 0

  const totalRevenue = revenueData.reduce((sum, d) => sum + d.revenue, 0)

  const avgDailyRevenue = revenueData.length > 0
    ? (totalRevenue / revenueData.length).toFixed(0)
    : 0

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">统计报表</h1>
        <div className="flex items-center gap-3">
          <Calendar size={18} className="text-dark-400" />
          <input
            type="date"
            value={dateRange.start}
            onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-1.5 text-sm"
          />
          <span className="text-dark-400">至</span>
          <input
            type="date"
            value={dateRange.end}
            onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-1.5 text-sm"
          />
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-dark-900 rounded-xl p-4">
          <div className="flex items-center gap-2 text-dark-400 mb-2">
            <TrendingUp size={18} />
            <span>平均入住率</span>
          </div>
          <div className="text-3xl font-bold text-primary-400">{avgOccupancy}%</div>
        </div>
        <div className="bg-dark-900 rounded-xl p-4">
          <div className="flex items-center gap-2 text-dark-400 mb-2">
            <DollarSign size={18} />
            <span>总营收</span>
          </div>
          <div className="text-3xl font-bold text-emerald-400">¥{totalRevenue}</div>
        </div>
        <div className="bg-dark-900 rounded-xl p-4">
          <div className="flex items-center gap-2 text-dark-400 mb-2">
            <DollarSign size={18} />
            <span>日均营收</span>
          </div>
          <div className="text-3xl font-bold text-blue-400">¥{avgDailyRevenue}</div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </div>
      ) : (
        <>
          {/* 入住率趋势 */}
          <div className="bg-dark-900 rounded-xl p-6">
            <h2 className="text-lg font-medium mb-4">入住率趋势</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={occupancyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    dataKey="date"
                    stroke="#64748b"
                    tickFormatter={(value) => value.slice(5)}
                  />
                  <YAxis stroke="#64748b" domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px'
                    }}
                    formatter={(value: number) => [`${value}%`, '入住率']}
                  />
                  <Line
                    type="monotone"
                    dataKey="occupancy_rate"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ fill: '#3b82f6' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 营收趋势 */}
          <div className="bg-dark-900 rounded-xl p-6">
            <h2 className="text-lg font-medium mb-4">营收趋势</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={revenueData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    dataKey="date"
                    stroke="#64748b"
                    tickFormatter={(value) => value.slice(5)}
                  />
                  <YAxis stroke="#64748b" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px'
                    }}
                    formatter={(value: number) => [`¥${value}`, '营收']}
                  />
                  <Bar dataKey="revenue" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
