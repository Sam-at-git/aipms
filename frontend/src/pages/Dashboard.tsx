import { useEffect, useState } from 'react'
import {
  BedDouble, Users, CalendarCheck, DollarSign,
  TrendingUp, ArrowUpRight, ArrowDownRight, Clock
} from 'lucide-react'
import { reportApi, reservationApi, checkoutApi } from '../services/api'
import { useOntologyStore, useAuthStore } from '../store'
import type { DashboardStats, Reservation, StayRecord } from '../types'

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [arrivals, setArrivals] = useState<Reservation[]>([])
  const [departures, setDepartures] = useState<StayRecord[]>([])
  const [loading, setLoading] = useState(true)
  const currentBranchId = useAuthStore(s => s.currentBranchId)

  useEffect(() => {
    loadData()
  }, [currentBranchId])

  const loadData = async () => {
    try {
      const [statsData, arrivalsData, departuresData] = await Promise.all([
        reportApi.getDashboard(),
        reservationApi.getTodayArrivals(),
        checkoutApi.getTodayExpected()
      ])
      setStats(statsData)
      setArrivals(arrivalsData)
      setDepartures(departuresData)
    } catch (err) {
      console.error('Failed to load dashboard data:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">工作台</h1>

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="入住率"
          value={`${stats?.occupancy_rate || 0}%`}
          icon={TrendingUp}
          color="primary"
          trend={stats?.occupancy_rate || 0 > 70 ? 'up' : 'down'}
        />
        <StatCard
          title="今日营收"
          value={`¥${stats?.today_revenue || 0}`}
          icon={DollarSign}
          color="green"
        />
        <StatCard
          title="今日入住"
          value={stats?.today_checkins || 0}
          icon={ArrowUpRight}
          color="blue"
        />
        <StatCard
          title="今日退房"
          value={stats?.today_checkouts || 0}
          icon={ArrowDownRight}
          color="orange"
        />
      </div>

      {/* 房态概览 */}
      <RoomStatusOverview stats={stats} />

      {/* 今日预抵和预离 */}
      <div className="grid grid-cols-2 gap-6">
        {/* 今日预抵 */}
        <div className="bg-dark-900 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <CalendarCheck size={20} className="text-primary-400" />
            <h2 className="text-lg font-medium">今日预抵</h2>
            <span className="text-sm text-dark-400">({arrivals.length})</span>
          </div>
          {arrivals.length > 0 ? (
            <div className="space-y-3">
              {arrivals.slice(0, 5).map(r => (
                <div key={r.id} className="flex items-center justify-between py-2 border-b border-dark-800 last:border-0">
                  <div>
                    <p className="font-medium">{r.guest_name}</p>
                    <p className="text-sm text-dark-400">{r.room_type_name} · {r.reservation_no}</p>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-dark-400">
                    <Clock size={14} />
                    {r.estimated_arrival || '未指定'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-dark-500 text-center py-4">暂无预抵</p>
          )}
        </div>

        {/* 今日预离 */}
        <div className="bg-dark-900 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Users size={20} className="text-orange-400" />
            <h2 className="text-lg font-medium">今日预离</h2>
            <span className="text-sm text-dark-400">({departures.length})</span>
          </div>
          {departures.length > 0 ? (
            <div className="space-y-3">
              {departures.slice(0, 5).map(s => (
                <div key={s.id} className="flex items-center justify-between py-2 border-b border-dark-800 last:border-0">
                  <div>
                    <p className="font-medium">{s.guest_name}</p>
                    <p className="text-sm text-dark-400">{s.room_number}号房 · {s.room_type_name}</p>
                  </div>
                  <div className="text-sm">
                    <span className={s.bill_balance > 0 ? 'text-red-400' : 'text-emerald-400'}>
                      {s.bill_balance > 0 ? `待收 ¥${s.bill_balance}` : '已结清'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-dark-500 text-center py-4">暂无预离</p>
          )}
        </div>
      </div>
    </div>
  )
}

// 统计卡片组件
function StatCard({ title, value, icon: Icon, color, trend }: {
  title: string
  value: string | number
  icon: typeof BedDouble
  color: 'primary' | 'green' | 'blue' | 'orange'
  trend?: 'up' | 'down'
}) {
  const colorClasses = {
    primary: 'bg-primary-500/10 text-primary-400',
    green: 'bg-emerald-500/10 text-emerald-400',
    blue: 'bg-blue-500/10 text-blue-400',
    orange: 'bg-orange-500/10 text-orange-400'
  }

  return (
    <div className="bg-dark-900 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-dark-400">{title}</span>
        <div className={`p-2 rounded-lg ${colorClasses[color]}`}>
          <Icon size={18} />
        </div>
      </div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-bold">{value}</span>
        {trend && (
          <span className={trend === 'up' ? 'text-emerald-400' : 'text-red-400'}>
            {trend === 'up' ? '↑' : '↓'}
          </span>
        )}
      </div>
    </div>
  )
}

// 房态概览 (registry-driven)
function RoomStatusOverview({ stats }: { stats: DashboardStats | null }) {
  const { getStatusConfig } = useOntologyStore()
  const keys: { key: keyof DashboardStats; status: string }[] = [
    { key: 'vacant_clean', status: 'vacant_clean' },
    { key: 'occupied', status: 'occupied' },
    { key: 'vacant_dirty', status: 'vacant_dirty' },
    { key: 'out_of_order', status: 'out_of_order' },
  ]
  const total = stats?.total_rooms || 0

  return (
    <div className="bg-dark-900 rounded-xl p-6">
      <h2 className="text-lg font-medium mb-4">房态概览</h2>
      <div className="grid grid-cols-4 gap-4">
        {keys.map(({ key, status }) => {
          const sc = getStatusConfig('Room', status)
          const value = (stats?.[key] as number) || 0
          const percentage = total > 0 ? (value / total) * 100 : 0
          return (
            <div key={status} className="bg-dark-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-dark-400">{sc.label}</span>
                <span className="text-lg font-bold">{value}</span>
              </div>
              <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                <div
                  className={`h-full ${sc.dotColor} transition-all duration-300`}
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
