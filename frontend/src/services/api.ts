import axios from 'axios'
import type {
  Room, RoomType, Reservation, StayRecord, Task, Employee,
  Bill, RatePlan, DashboardStats, LoginResponse, AuditLog, ActionSummary,
  Guest, GuestStayHistory, GuestReservationHistory,
  MessagesListResponse, SearchResultsResponse, AvailableDatesResponse, AIResponseWithHistory
} from '../types'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：添加 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：处理 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ============== 认证 ==============

export const authApi = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const res = await api.post('/auth/login', { username, password })
    return res.data
  },
  me: async (): Promise<Employee> => {
    const res = await api.get('/auth/me')
    return res.data
  },
  changePassword: async (oldPassword: string, newPassword: string) => {
    const res = await api.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword
    })
    return res.data
  }
}

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

// ============== AI ==============

export const aiApi = {
  chat: async (message: string, topicId?: string, followUpContext?: Record<string, unknown>): Promise<AIResponseWithHistory> => {
    const res = await api.post('/ai/chat', {
      content: message,
      topic_id: topicId,
      follow_up_context: followUpContext
    })
    return res.data
  },
  execute: async (action: object, confirmed: boolean) => {
    const res = await api.post('/ai/execute', { action, confirmed })
    return res.data
  }
}

// ============== 会话历史 ==============

export const conversationApi = {
  getMessages: async (params?: {
    limit?: number
    before?: string
  }): Promise<MessagesListResponse> => {
    const res = await api.get('/conversations/messages', { params })
    return res.data
  },
  getMessagesByDate: async (dateStr: string) => {
    const res = await api.get(`/conversations/messages/date/${dateStr}`)
    return res.data
  },
  search: async (params: {
    keyword: string
    start_date?: string
    end_date?: string
    limit?: number
  }): Promise<SearchResultsResponse> => {
    const res = await api.get('/conversations/search', { params })
    return res.data
  },
  getAvailableDates: async (): Promise<AvailableDatesResponse> => {
    const res = await api.get('/conversations/dates')
    return res.data
  }
}

// ============== 审计日志 ==============

export const auditApi = {
  getLogs: async (params?: {
    action?: string
    entity_type?: string
    operator_id?: number
    start_date?: string
    end_date?: string
    limit?: number
  }): Promise<AuditLog[]> => {
    const res = await api.get('/audit-logs/', { params })
    return res.data
  },
  getLog: async (id: number): Promise<AuditLog> => {
    const res = await api.get(`/audit-logs/${id}`)
    return res.data
  },
  getEntityLogs: async (entityType: string, entityId: number, limit?: number): Promise<AuditLog[]> => {
    const res = await api.get(`/audit-logs/entity/${entityType}/${entityId}`, { params: { limit } })
    return res.data
  },
  getSummary: async (days?: number): Promise<ActionSummary[]> => {
    const res = await api.get('/audit-logs/summary', { params: { days } })
    return res.data
  }
}

// ============== 操作撤销 ==============

export interface OperationSnapshot {
  id: number
  snapshot_uuid: string
  operation_type: string
  operator_id: number
  operation_time: string
  entity_type: string
  entity_id: number
  is_undone: boolean
  expires_at: string
}

export interface SnapshotDetail extends OperationSnapshot {
  operator_name?: string
  before_state: Record<string, any>
  after_state: Record<string, any>
  undone_time?: string
  undone_by?: number
  can_undo: boolean
}

export interface UndoResult {
  success: boolean
  message: string
  details: Record<string, any>
}

export const undoApi = {
  /** 获取可撤销的操作列表 */
  getOperations: async (params?: {
    entity_type?: string
    entity_id?: number
    limit?: number
  }): Promise<OperationSnapshot[]> => {
    const res = await api.get('/undo/operations', { params })
    return res.data
  },
  /** 获取快照详情 */
  getSnapshot: async (snapshotUuid: string): Promise<SnapshotDetail> => {
    const res = await api.get(`/undo/${snapshotUuid}`)
    return res.data
  },
  /** 执行撤销操作 */
  undo: async (snapshotUuid: string): Promise<UndoResult> => {
    const res = await api.post(`/undo/${snapshotUuid}`)
    return res.data
  },
  /** 获取撤销历史（仅管理员） */
  getHistory: async (limit?: number): Promise<OperationSnapshot[]> => {
    const res = await api.get('/undo/history', { params: { limit } })
    return res.data
  }
}

// ============== 本体视图 ==============

export interface OntologyEntity {
  name: string
  description: string
  attributes: {
    name: string
    type: string
    primary?: boolean
    values?: string[]
  }[]
}

export interface OntologyRelationship {
  from: string
  to: string
  type: string
  label: string
}

export interface OntologySchema {
  entities: OntologyEntity[]
  relationships: OntologyRelationship[]
}

export interface OntologyStatistics {
  entities: Record<string, {
    total: number
    by_status?: Record<string, number>
    by_tier?: Record<string, number>
    by_role?: Record<string, number>
    active?: number
    settled?: number
    unsettled?: number
  }>
}

export interface GraphNode {
  id: string
  type: string
  label: string
  data: Record<string, any>
  position?: { x: number; y: number }
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label: string
}

export interface InstanceGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export const ontologyApi = {
  getSchema: async (): Promise<OntologySchema> => {
    const res = await api.get('/ontology/schema')
    return res.data
  },
  getStatistics: async (): Promise<OntologyStatistics> => {
    const res = await api.get('/ontology/statistics')
    return res.data
  },
  getInstanceGraph: async (params?: {
    center_entity?: string
    center_id?: number
    depth?: number
  }): Promise<InstanceGraph> => {
    const res = await api.get('/ontology/instance-graph', { params })
    return res.data
  }
}

// ============== 安全管理 ==============

export interface SecurityEvent {
  id: number
  event_type: string
  severity: string
  timestamp: string
  source_ip?: string
  user_id?: number
  user_name?: string
  description: string
  details: Record<string, any>
  is_acknowledged: boolean
  acknowledged_by?: number
  acknowledged_at?: string
}

export interface SecurityStatistics {
  total: number
  unacknowledged: number
  by_type: Record<string, number>
  by_severity: Record<string, number>
  time_range_hours: number
}

export interface AlertSummary {
  total_alerts: number
  critical: number
  high: number
  unacknowledged: number
  time_range_hours: number
}

export const securityApi = {
  getEvents: async (params?: {
    event_type?: string
    severity?: string
    user_id?: number
    hours?: number
    unacknowledged_only?: boolean
    limit?: number
    offset?: number
  }): Promise<SecurityEvent[]> => {
    const res = await api.get('/security/events', { params })
    return res.data
  },
  getEvent: async (id: number): Promise<SecurityEvent> => {
    const res = await api.get(`/security/events/${id}`)
    return res.data
  },
  getStatistics: async (hours?: number): Promise<SecurityStatistics> => {
    const res = await api.get('/security/statistics', { params: { hours } })
    return res.data
  },
  getAlerts: async (): Promise<SecurityEvent[]> => {
    const res = await api.get('/security/alerts')
    return res.data
  },
  getAlertSummary: async (): Promise<AlertSummary> => {
    const res = await api.get('/security/alerts/summary')
    return res.data
  },
  acknowledgeEvent: async (eventId: number): Promise<SecurityEvent> => {
    const res = await api.post(`/security/events/${eventId}/acknowledge`)
    return res.data
  },
  bulkAcknowledge: async (eventIds: number[]): Promise<{ acknowledged_count: number }> => {
    const res = await api.post('/security/events/bulk-acknowledge', eventIds)
    return res.data
  },
  getHighSeverityEvents: async (hours?: number, limit?: number): Promise<SecurityEvent[]> => {
    const res = await api.get('/security/high-severity', { params: { hours, limit } })
    return res.data
  },
  getUserHistory: async (userId: number, days?: number, limit?: number): Promise<SecurityEvent[]> => {
    const res = await api.get(`/security/user/${userId}/history`, { params: { days, limit } })
    return res.data
  },
  getEventTypes: async (): Promise<{ value: string; label: string }[]> => {
    const res = await api.get('/security/event-types')
    return res.data
  },
  getSeverityLevels: async (): Promise<{ value: string; label: string }[]> => {
    const res = await api.get('/security/severity-levels')
    return res.data
  }
}

export default api
