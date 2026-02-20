import { BedDouble, User, Wrench, Sparkles } from 'lucide-react'
import type { Room, RoomStatus } from '../types'
import { useOntologyStore } from '../store'

interface RoomCardProps {
  room: Room
  onClick?: (room: Room) => void
  showBranch?: boolean
}

const statusIcons: Record<RoomStatus, typeof BedDouble> = {
  vacant_clean: Sparkles,
  occupied: User,
  vacant_dirty: BedDouble,
  out_of_order: Wrench,
}

const statusCssClass: Record<RoomStatus, string> = {
  vacant_clean: 'room-vacant-clean',
  occupied: 'room-occupied',
  vacant_dirty: 'room-vacant-dirty',
  out_of_order: 'room-out-of-order',
}

export default function RoomCard({ room, onClick, showBranch }: RoomCardProps) {
  const { getStatusConfig } = useOntologyStore()
  const sc = getStatusConfig('Room', room.status)
  const Icon = statusIcons[room.status] || BedDouble

  return (
    <div
      onClick={() => onClick?.(room)}
      className={`border rounded-lg p-3 cursor-pointer transition-all hover:scale-105 hover:shadow-lg ${statusCssClass[room.status] || ''}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-bold text-lg">{room.room_number}</span>
        <Icon size={16} />
      </div>
      <div className="text-xs space-y-1">
        <p className="opacity-80">{room.room_type_name}</p>
        <p className="font-medium">{sc.label}</p>
        {room.current_guest && (
          <p className="truncate">{room.current_guest}</p>
        )}
        {showBranch && room.branch_name && (
          <p className="text-dark-500 truncate">{room.branch_name}</p>
        )}
      </div>
    </div>
  )
}

// 房态统计卡片
export function RoomStatusSummary({ stats }: {
  stats: { vacant_clean: number; occupied: number; vacant_dirty: number; out_of_order: number; total: number }
}) {
  const { getStatusConfig } = useOntologyStore()
  const keys: (keyof typeof stats)[] = ['vacant_clean', 'occupied', 'vacant_dirty', 'out_of_order']
  const items = keys.map(k => {
    const sc = getStatusConfig('Room', k)
    return { label: sc.label, value: stats[k], color: sc.dotColor }
  })

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
