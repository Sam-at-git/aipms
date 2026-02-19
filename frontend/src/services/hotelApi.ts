import api from './apiClient'
import type {
  Room, RoomType, Reservation, StayRecord, Task, Employee,
  Bill, RatePlan, DashboardStats,
  Guest, GuestStayHistory, GuestReservationHistory,
} from '../types/hotel'

// ============== 房间 ==============

export const roomApi = {
  getRoomTypes: async (): Promise<RoomType[]> => {
    const res = await api.get('/rooms/types')
    return res.data
  },
  getRooms: async (params?: {
    floor?: number
    room_type_id?: number
    status?: string
  }): Promise<Room[]> => {
    const res = await api.get('/rooms', { params })
    return res.data
  },
  getRoom: async (id: number): Promise<Room> => {
    const res = await api.get(`/rooms/${id}`)
    return res.data
  },
  getStatusSummary: async () => {
    const res = await api.get('/rooms/status-summary')
    return res.data
  },
  getAvailableRooms: async (checkInDate: string, checkOutDate: string, roomTypeId?: number) => {
    const res = await api.get('/rooms/available', {
      params: { check_in_date: checkInDate, check_out_date: checkOutDate, room_type_id: roomTypeId }
    })
    return res.data
  },
  updateStatus: async (id: number, status: string) => {
    const res = await api.patch(`/rooms/${id}/status`, { status })
    return res.data
  }
}

// ============== 预订 ==============

export const reservationApi = {
  getList: async (params?: {
    status?: string
    check_in_date?: string
    guest_name?: string
  }): Promise<Reservation[]> => {
    const res = await api.get('/reservations', { params })
    return res.data
  },
  get: async (id: number): Promise<Reservation> => {
    const res = await api.get(`/reservations/${id}`)
    return res.data
  },
  search: async (keyword: string): Promise<Reservation[]> => {
    const res = await api.get('/reservations/search', { params: { keyword } })
    return res.data
  },
  getTodayArrivals: async (): Promise<Reservation[]> => {
    const res = await api.get('/reservations/today-arrivals')
    return res.data
  },
  create: async (data: {
    guest_name: string
    guest_phone: string
    room_type_id: number
    check_in_date: string
    check_out_date: string
    room_count?: number
    prepaid_amount?: number
    special_requests?: string
  }): Promise<Reservation> => {
    const res = await api.post('/reservations', data)
    return res.data
  },
  cancel: async (id: number, reason: string) => {
    const res = await api.post(`/reservations/${id}/cancel`, { cancel_reason: reason })
    return res.data
  }
}

// ============== 入住 ==============

export const checkinApi = {
  getActiveStays: async (): Promise<StayRecord[]> => {
    const res = await api.get('/checkin/active-stays')
    return res.data
  },
  search: async (keyword: string): Promise<StayRecord[]> => {
    const res = await api.get('/checkin/search', { params: { keyword } })
    return res.data
  },
  getStay: async (id: number): Promise<StayRecord> => {
    const res = await api.get(`/checkin/stay/${id}`)
    return res.data
  },
  fromReservation: async (data: {
    reservation_id: number
    room_id: number
    deposit_amount?: number
    guest_id_number?: string
  }): Promise<StayRecord> => {
    const res = await api.post('/checkin/from-reservation', data)
    return res.data
  },
  walkIn: async (data: {
    guest_name: string
    guest_phone: string
    guest_id_type: string
    guest_id_number: string
    room_id: number
    expected_check_out: string
    deposit_amount?: number
  }): Promise<StayRecord> => {
    const res = await api.post('/checkin/walk-in', data)
    return res.data
  },
  extend: async (id: number, newDate: string) => {
    const res = await api.post(`/checkin/stay/${id}/extend`, { new_check_out_date: newDate })
    return res.data
  },
  changeRoom: async (id: number, newRoomId: number) => {
    const res = await api.post(`/checkin/stay/${id}/change-room`, { new_room_id: newRoomId })
    return res.data
  }
}

// ============== 退房 ==============

export const checkoutApi = {
  checkout: async (data: {
    stay_record_id: number
    refund_deposit?: number
    allow_unsettled?: boolean
    unsettled_reason?: string
  }) => {
    const res = await api.post('/checkout', data)
    return res.data
  },
  getTodayExpected: async (): Promise<StayRecord[]> => {
    const res = await api.get('/checkout/today-expected')
    return res.data
  },
  getOverdue: async (): Promise<StayRecord[]> => {
    const res = await api.get('/checkout/overdue')
    return res.data
  }
}

// ============== 任务 ==============

export const taskApi = {
  getList: async (params?: {
    task_type?: string
    status?: string
    assignee_id?: number
  }): Promise<Task[]> => {
    const res = await api.get('/tasks', { params })
    return res.data
  },
  getMyTasks: async (): Promise<Task[]> => {
    const res = await api.get('/tasks/my-tasks')
    return res.data
  },
  getPending: async (): Promise<Task[]> => {
    const res = await api.get('/tasks/pending')
    return res.data
  },
  getCleaners: async (): Promise<{ id: number; name: string }[]> => {
    const res = await api.get('/tasks/cleaners')
    return res.data
  },
  getSummary: async () => {
    const res = await api.get('/tasks/summary')
    return res.data
  },
  create: async (data: {
    room_id: number
    task_type: string
    priority?: number
    assignee_id?: number
  }): Promise<Task> => {
    const res = await api.post('/tasks', data)
    return res.data
  },
  assign: async (id: number, assigneeId: number) => {
    const res = await api.post(`/tasks/${id}/assign`, { assignee_id: assigneeId })
    return res.data
  },
  start: async (id: number) => {
    const res = await api.post(`/tasks/${id}/start`)
    return res.data
  },
  complete: async (id: number, notes?: string) => {
    const res = await api.post(`/tasks/${id}/complete`, null, { params: { notes } })
    return res.data
  }
}

// ============== 账单 ==============

export const billingApi = {
  getBill: async (id: number): Promise<Bill> => {
    const res = await api.get(`/billing/bill/${id}`)
    return res.data
  },
  getBillByStay: async (stayId: number): Promise<Bill> => {
    const res = await api.get(`/billing/stay/${stayId}`)
    return res.data
  },
  addPayment: async (data: {
    bill_id: number
    amount: number
    method: 'cash' | 'card'
    remark?: string
  }) => {
    const res = await api.post('/billing/payment', data)
    return res.data
  },
  adjust: async (data: {
    bill_id: number
    adjustment_amount: number
    reason: string
  }) => {
    const res = await api.post('/billing/adjust', data)
    return res.data
  }
}

// ============== 员工 ==============

export const employeeApi = {
  getList: async (params?: { role?: string; is_active?: boolean }): Promise<Employee[]> => {
    const res = await api.get('/employees', { params })
    return res.data
  },
  get: async (id: number): Promise<Employee> => {
    const res = await api.get(`/employees/${id}`)
    return res.data
  },
  create: async (data: {
    username: string
    password: string
    name: string
    phone?: string
    role: string
  }): Promise<Employee> => {
    const res = await api.post('/employees', data)
    return res.data
  },
  update: async (id: number, data: {
    name?: string
    phone?: string
    role?: string
    is_active?: boolean
  }): Promise<Employee> => {
    const res = await api.put(`/employees/${id}`, data)
    return res.data
  },
  resetPassword: async (id: number, newPassword: string) => {
    const res = await api.post(`/employees/${id}/reset-password`, { new_password: newPassword })
    return res.data
  }
}

// ============== 报表 ==============

export const reportApi = {
  getDashboard: async (): Promise<DashboardStats> => {
    const res = await api.get('/reports/dashboard')
    return res.data
  },
  getOccupancy: async (startDate: string, endDate: string) => {
    const res = await api.get('/reports/occupancy', {
      params: { start_date: startDate, end_date: endDate }
    })
    return res.data
  },
  getRevenue: async (startDate: string, endDate: string) => {
    const res = await api.get('/reports/revenue', {
      params: { start_date: startDate, end_date: endDate }
    })
    return res.data
  }
}

// ============== 价格 ==============

export const priceApi = {
  getRatePlans: async (params?: { room_type_id?: number; is_active?: boolean }): Promise<RatePlan[]> => {
    const res = await api.get('/prices/rate-plans', { params })
    return res.data
  },
  getRatePlan: async (id: number): Promise<RatePlan> => {
    const res = await api.get(`/prices/rate-plans/${id}`)
    return res.data
  },
  createRatePlan: async (data: {
    name: string
    room_type_id: number
    start_date: string
    end_date: string
    price: number
    priority?: number
    is_weekend?: boolean
  }): Promise<RatePlan> => {
    const res = await api.post('/prices/rate-plans', data)
    return res.data
  },
  updateRatePlan: async (id: number, data: {
    name?: string
    room_type_id?: number
    start_date?: string
    end_date?: string
    price?: number
    priority?: number
    is_weekend?: boolean
    is_active?: boolean
  }): Promise<RatePlan> => {
    const res = await api.put(`/prices/rate-plans/${id}`, data)
    return res.data
  },
  deleteRatePlan: async (id: number) => {
    const res = await api.delete(`/prices/rate-plans/${id}`)
    return res.data
  },
  getPriceCalendar: async (roomTypeId: number, startDate: string, endDate: string) => {
    const res = await api.get('/prices/calendar', {
      params: { room_type_id: roomTypeId, start_date: startDate, end_date: endDate }
    })
    return res.data
  },
  calculate: async (roomTypeId: number, checkInDate: string, checkOutDate: string, roomCount?: number) => {
    const res = await api.get('/prices/calculate', {
      params: { room_type_id: roomTypeId, check_in_date: checkInDate, check_out_date: checkOutDate, room_count: roomCount }
    })
    return res.data
  }
}

// ============== 客人管理 (CRM) ==============

export const guestApi = {
  getList: async (params?: {
    search?: string
    tier?: string
    is_blacklisted?: boolean
    limit?: number
  }): Promise<Guest[]> => {
    const res = await api.get('/guests/', { params })
    return res.data
  },
  get: async (id: number): Promise<Guest> => {
    const res = await api.get(`/guests/${id}`)
    return res.data
  },
  create: async (data: {
    name: string
    phone?: string
    id_type?: string
    id_number?: string
    email?: string
  }): Promise<Guest> => {
    const res = await api.post('/guests/', data)
    return res.data
  },
  update: async (id: number, data: {
    name?: string
    phone?: string
    id_type?: string
    id_number?: string
    email?: string
    preferences?: string
    tier?: string
    notes?: string
  }): Promise<Guest> => {
    const res = await api.put(`/guests/${id}`, data)
    return res.data
  },
  getStayHistory: async (id: number, limit?: number): Promise<GuestStayHistory[]> => {
    const res = await api.get(`/guests/${id}/stay-history`, { params: { limit } })
    return res.data
  },
  getReservationHistory: async (id: number, limit?: number): Promise<GuestReservationHistory[]> => {
    const res = await api.get(`/guests/${id}/reservation-history`, { params: { limit } })
    return res.data
  },
  updateTier: async (id: number, tier: string) => {
    const res = await api.put(`/guests/${id}/tier`, null, { params: { tier } })
    return res.data
  },
  toggleBlacklist: async (id: number, isBlacklisted: boolean, reason?: string) => {
    const res = await api.put(`/guests/${id}/blacklist`, null, {
      params: { is_blacklisted: isBlacklisted, reason }
    })
    return res.data
  },
  updatePreferences: async (id: number, preferences: Record<string, any>) => {
    const res = await api.put(`/guests/${id}/preferences`, preferences)
    return res.data
  }
}
