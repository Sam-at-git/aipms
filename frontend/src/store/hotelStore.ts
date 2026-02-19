import { create } from 'zustand'
import type { DashboardStats, Room, StayRecord, Task } from '../types/hotel'

// 仪表盘数据状态
interface DashboardState {
  stats: DashboardStats | null
  rooms: Room[]
  activeStays: StayRecord[]
  pendingTasks: Task[]
  isLoading: boolean
  setStats: (stats: DashboardStats) => void
  setRooms: (rooms: Room[]) => void
  setActiveStays: (stays: StayRecord[]) => void
  setPendingTasks: (tasks: Task[]) => void
  setLoading: (loading: boolean) => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  stats: null,
  rooms: [],
  activeStays: [],
  pendingTasks: [],
  isLoading: false,
  setStats: (stats) => set({ stats }),
  setRooms: (rooms) => set({ rooms }),
  setActiveStays: (stays) => set({ activeStays: stays }),
  setPendingTasks: (tasks) => set({ pendingTasks: tasks }),
  setLoading: (loading) => set({ isLoading: loading })
}))
