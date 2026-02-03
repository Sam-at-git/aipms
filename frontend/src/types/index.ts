// 房间状态
export type RoomStatus = 'vacant_clean' | 'occupied' | 'vacant_dirty' | 'out_of_order'

// 预订状态
export type ReservationStatus = 'confirmed' | 'checked_in' | 'completed' | 'cancelled' | 'no_show'

// 任务状态
export type TaskStatus = 'pending' | 'assigned' | 'in_progress' | 'completed'

// 任务类型
export type TaskType = 'cleaning' | 'maintenance'

// 支付方式
export type PaymentMethod = 'cash' | 'card'

// 员工角色
export type EmployeeRole = 'manager' | 'receptionist' | 'cleaner'

// 房型
export interface RoomType {
  id: number
  name: string
  description?: string
  base_price: number
  max_occupancy: number
  amenities?: string
  room_count: number
  created_at: string
}

// 房间
export interface Room {
  id: number
  room_number: string
  floor: number
  room_type_id: number
  room_type_name?: string
  status: RoomStatus
  features?: string
  is_active: boolean
  current_guest?: string
  created_at: string
}

// 客人
export interface Guest {
  id: number
  name: string
  id_type?: string
  id_number?: string
  phone?: string
  email?: string
  preferences?: string
  tier: 'normal' | 'silver' | 'gold' | 'platinum'
  total_stays: number
  total_amount: number
  is_blacklisted: boolean
  blacklist_reason?: string
  notes?: string
  created_at: string
  updated_at: string
  reservation_count?: number
  last_stay_date?: string
  last_room_type?: string
}

// 客人历史记录
export interface GuestStayHistory {
  id: number
  room_number: string
  room_type: string
  check_in_time: string
  check_out_time?: string
  status: string
}

export interface GuestReservationHistory {
  id: number
  reservation_no: string
  room_type: string
  check_in_date: string
  check_out_date: string
  status: string
  created_at: string
}

// 预订
export interface Reservation {
  id: number
  reservation_no: string
  guest_id: number
  guest_name: string
  guest_phone: string
  room_type_id: number
  room_type_name: string
  check_in_date: string
  check_out_date: string
  room_count: number
  adult_count: number
  child_count: number
  status: ReservationStatus
  total_amount?: number
  prepaid_amount: number
  special_requests?: string
  estimated_arrival?: string
  created_at: string
}

// 住宿记录
export interface StayRecord {
  id: number
  reservation_id?: number
  guest_id: number
  guest_name: string
  guest_phone?: string
  room_id: number
  room_number: string
  room_type_name: string
  check_in_time: string
  check_out_time?: string
  expected_check_out: string
  deposit_amount: number
  status: 'active' | 'checked_out'
  bill_total: number
  bill_paid: number
  bill_balance: number
}

// 账单
export interface Bill {
  id: number
  stay_record_id: number
  total_amount: number
  paid_amount: number
  adjustment_amount: number
  adjustment_reason?: string
  balance: number
  is_settled: boolean
  payments: Payment[]
}

// 支付记录
export interface Payment {
  id: number
  amount: number
  method: PaymentMethod
  payment_time: string
  remark?: string
  operator_name?: string
}

// 任务
export interface Task {
  id: number
  room_id: number
  room_number: string
  task_type: TaskType
  status: TaskStatus
  assignee_id?: number
  assignee_name?: string
  priority: number
  notes?: string
  created_at: string
  started_at?: string
  completed_at?: string
}

// 员工
export interface Employee {
  id: number
  username: string
  name: string
  phone?: string
  role: EmployeeRole
  is_active: boolean
  created_at: string
}

// 价格策略
export interface RatePlan {
  id: number
  name: string
  room_type_id: number
  room_type_name: string
  start_date: string
  end_date: string
  price: number
  priority: number
  is_weekend: boolean
  is_active: boolean
  created_at: string
}

// 仪表盘统计
export interface DashboardStats {
  total_rooms: number
  vacant_clean: number
  occupied: number
  vacant_dirty: number
  out_of_order: number
  today_checkins: number
  today_checkouts: number
  occupancy_rate: number
  today_revenue: number
}

// AI 响应
export interface AIResponse {
  message: string
  suggested_actions: AIAction[]
  context: Record<string, unknown>
  requires_confirmation?: boolean
  action?: string
  candidates?: CandidateOption[]
  follow_up?: FollowUpInfo
  topic_id?: string
}

// 缺失字段定义（用于追问模式）
export interface MissingField {
  field_name: string
  display_name: string
  field_type: 'text' | 'select' | 'date' | 'number'
  options?: FieldOption[]
  placeholder?: string
  required: boolean
}

export interface FieldOption {
  value: string
  label: string
}

// 追问信息
export interface FollowUpInfo {
  action_type: string
  message: string
  missing_fields: MissingField[]
  collected_fields: Record<string, unknown>
  context: Record<string, unknown>
}

export interface AIAction {
  action_type: string
  entity_type: string
  entity_id?: number
  params: Record<string, unknown>
  description: string
  requires_confirmation: boolean
  candidates?: CandidateOption[]
  missing_fields?: MissingField[]
}

export interface CandidateOption {
  id: number
  name: string
  room_number?: string
  username?: string
  role?: string
  price?: number
  description?: string
}

// 聊天消息
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  actions?: AIAction[]
  context?: MessageContext
}

// 消息上下文
export interface MessageContext {
  topic_id?: string
  is_followup?: boolean
  parent_message_id?: string
  follow_up?: FollowUpInfo
  action_type?: string
  collected_fields?: Record<string, unknown>
}

// 会话消息（从服务端返回）
export interface ConversationMessage {
  id: string
  timestamp: string  // ISO 字符串
  role: 'user' | 'assistant'
  content: string
  actions?: AIAction[]
  context?: MessageContext
}

// 消息列表响应
export interface MessagesListResponse {
  messages: ConversationMessage[]
  has_more: boolean
  oldest_timestamp?: string
}

// 搜索结果响应
export interface SearchResultsResponse {
  messages: ConversationMessage[]
  total: number
}

// 可用日期响应
export interface AvailableDatesResponse {
  dates: string[]
}

// 带历史信息的 AI 响应
export interface AIResponseWithHistory extends AIResponse {
  message_id: string
  topic_id?: string
}

// 登录响应
export interface LoginResponse {
  access_token: string
  token_type: string
  employee: Employee
}

// 审计日志
export interface AuditLog {
  id: number
  operator_id: number
  operator_name: string
  action: string
  entity_type: string | null
  entity_id: number | null
  old_value: string | null
  new_value: string | null
  ip_address: string | null
  created_at: string
}

// 操作统计摘要
export interface ActionSummary {
  action: string
  entity_type: string | null
  count: number
}
