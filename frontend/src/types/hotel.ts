// ============== Hotel Domain Types ==============

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
export type EmployeeRole = 'sysadmin' | 'manager' | 'receptionist' | 'cleaner'

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
