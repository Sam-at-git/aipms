import { useEffect, useState } from 'react'
import { RefreshCw, Filter } from 'lucide-react'
import { roomApi } from '../services/api'
import RoomCard, { RoomStatusSummary } from '../components/RoomCard'
import Modal, { ModalFooter } from '../components/Modal'
import { useUIStore } from '../store'
import type { Room, RoomType, RoomStatus } from '../types'

export default function Rooms() {
  const [rooms, setRooms] = useState<Room[]>([])
  const [roomTypes, setRoomTypes] = useState<RoomType[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<{ floor?: number; status?: RoomStatus }>({})
  const [selectedRoom, setSelectedRoom] = useState<Room | null>(null)
  const { openModal, closeModal, modalData } = useUIStore()

  useEffect(() => {
    loadData()
  }, [filter])

  const loadData = async () => {
    setLoading(true)
    try {
      const [roomsData, typesData] = await Promise.all([
        roomApi.getRooms(filter),
        roomApi.getRoomTypes()
      ])
      setRooms(roomsData)
      setRoomTypes(typesData)
    } catch (err) {
      console.error('Failed to load rooms:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleRoomClick = (room: Room) => {
    setSelectedRoom(room)
    openModal('roomDetail', room)
  }

  const handleStatusChange = async (status: RoomStatus) => {
    if (!selectedRoom) return
    try {
      await roomApi.updateStatus(selectedRoom.id, status)
      closeModal()
      loadData()
    } catch (err) {
      console.error('Failed to update room status:', err)
    }
  }

  // 统计
  const stats = {
    total: rooms.length,
    vacant_clean: rooms.filter(r => r.status === 'vacant_clean').length,
    occupied: rooms.filter(r => r.status === 'occupied').length,
    vacant_dirty: rooms.filter(r => r.status === 'vacant_dirty').length,
    out_of_order: rooms.filter(r => r.status === 'out_of_order').length
  }

  // 按楼层分组
  const floors = [...new Set(rooms.map(r => r.floor))].sort()

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">房态管理</h1>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      {/* 统计和筛选 */}
      <div className="flex items-center justify-between bg-dark-900 rounded-xl p-4">
        <RoomStatusSummary stats={stats} />

        <div className="flex items-center gap-3">
          <Filter size={16} className="text-dark-400" />
          <select
            value={filter.status || ''}
            onChange={(e) => setFilter({ ...filter, status: e.target.value as RoomStatus || undefined })}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-1.5 text-sm"
          >
            <option value="">全部状态</option>
            <option value="vacant_clean">空闲</option>
            <option value="occupied">入住</option>
            <option value="vacant_dirty">待清洁</option>
            <option value="out_of_order">维修</option>
          </select>
          <select
            value={filter.floor || ''}
            onChange={(e) => setFilter({ ...filter, floor: e.target.value ? Number(e.target.value) : undefined })}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-1.5 text-sm"
          >
            <option value="">全部楼层</option>
            {floors.map(f => (
              <option key={f} value={f}>{f}楼</option>
            ))}
          </select>
        </div>
      </div>

      {/* 房态图 */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </div>
      ) : (
        <div className="space-y-6">
          {floors.map(floor => {
            const floorRooms = rooms.filter(r => r.floor === floor)
            if (floorRooms.length === 0) return null

            return (
              <div key={floor} className="bg-dark-900 rounded-xl p-4">
                <h3 className="text-sm font-medium text-dark-400 mb-3">{floor}楼</h3>
                <div className="grid grid-cols-5 gap-3">
                  {floorRooms.map(room => (
                    <RoomCard
                      key={room.id}
                      room={room}
                      onClick={handleRoomClick}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 房间详情弹窗 */}
      <Modal name="roomDetail" title={`${(modalData as Room)?.room_number || ''}号房`}>
        {selectedRoom && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-dark-400">房型</label>
                <p className="font-medium">{selectedRoom.room_type_name}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">楼层</label>
                <p className="font-medium">{selectedRoom.floor}楼</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">当前状态</label>
                <p className="font-medium">
                  {selectedRoom.status === 'vacant_clean' && '空闲'}
                  {selectedRoom.status === 'occupied' && '入住中'}
                  {selectedRoom.status === 'vacant_dirty' && '待清洁'}
                  {selectedRoom.status === 'out_of_order' && '维修中'}
                </p>
              </div>
              {selectedRoom.current_guest && (
                <div>
                  <label className="text-sm text-dark-400">当前住客</label>
                  <p className="font-medium">{selectedRoom.current_guest}</p>
                </div>
              )}
            </div>

            {/* 状态修改（非入住状态可改） */}
            {selectedRoom.status !== 'occupied' && (
              <div>
                <label className="text-sm text-dark-400 block mb-2">修改状态</label>
                <div className="flex gap-2">
                  {selectedRoom.status !== 'vacant_clean' && (
                    <button
                      onClick={() => handleStatusChange('vacant_clean')}
                      className="px-3 py-1.5 bg-emerald-500/20 text-emerald-400 rounded-lg text-sm hover:bg-emerald-500/30"
                    >
                      设为空闲
                    </button>
                  )}
                  {selectedRoom.status !== 'vacant_dirty' && (
                    <button
                      onClick={() => handleStatusChange('vacant_dirty')}
                      className="px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-lg text-sm hover:bg-yellow-500/30"
                    >
                      设为待清洁
                    </button>
                  )}
                  {selectedRoom.status !== 'out_of_order' && (
                    <button
                      onClick={() => handleStatusChange('out_of_order')}
                      className="px-3 py-1.5 bg-gray-500/20 text-gray-400 rounded-lg text-sm hover:bg-gray-500/30"
                    >
                      设为维修
                    </button>
                  )}
                </div>
              </div>
            )}

            <ModalFooter onCancel={closeModal} onConfirm={closeModal} confirmText="关闭" />
          </div>
        )}
      </Modal>
    </div>
  )
}
