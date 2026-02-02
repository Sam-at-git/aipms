import { BedDouble, User, Wrench, Sparkles } from 'lucide-react'
import type { Room, RoomStatus } from '../types'

interface RoomCardProps {
  room: Room
  onClick?: (room: Room) => void
}

const statusConfig: Record<RoomStatus, { label: string; class: string; icon: typeof BedDouble }> = {
  vacant_clean: { label: '空闲', class: 'room-vacant-clean', icon: Sparkles },
  occupied: { label: '入住', class: 'room-occupied', icon: User },
  vacant_dirty: { label: '待清洁', class: 'room-vacant-dirty', icon: BedDouble },
  out_of_order: { label: '维修', class: 'room-out-of-order', icon: Wrench }
}

export default function RoomCard({ room, onClick }: RoomCardProps) {
  const config = statusConfig[room.status]
  const Icon = config.icon

  return (
    <div
      onClick={() => onClick?.(room)}
      className={`border rounded-lg p-3 cursor-pointer transition-all hover:scale-105 hover:shadow-lg ${config.class}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-bold text-lg">{room.room_number}</span>
        <Icon size={16} />
      </div>
      <div className="text-xs space-y-1">
        <p className="opacity-80">{room.room_type_name}</p>
        <p className="font-medium">{config.label}</p>
        {room.current_guest && (
          <p className="truncate">{room.current_guest}</p>
        )}
      </div>
    </div>
  )
}

// 房态统计卡片
export function RoomStatusSummary({ stats }: {
  stats: { vacant_clean: number; occupied: number; vacant_dirty: number; out_of_order: number; total: number }
}) {
  const items = [
    { label: '空闲', value: stats.vacant_clean, color: 'bg-emerald-500' },
    { label: '入住', value: stats.occupied, color: 'bg-red-500' },
    { label: '待清洁', value: stats.vacant_dirty, color: 'bg-yellow-500' },
    { label: '维修', value: stats.out_of_order, color: 'bg-gray-500' },
  ]

  return (
    <div className="flex gap-4">
      {items.map(item => (
        <div key={item.label} className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${item.color}`} />
          <span className="text-sm text-dark-400">{item.label}</span>
          <span className="font-medium">{item.value}</span>
        </div>
      ))}
    </div>
  )
}
