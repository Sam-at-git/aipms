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
  query_result?: QueryResultData
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
  query_result?: QueryResultData
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

// 查询结果数据
export interface QueryResultData {
  display_type: 'text' | 'table' | 'chart'
  columns?: string[]
  column_keys?: string[]
  rows?: Record<string, unknown>[]
  data?: Record<string, unknown>
  summary?: Record<string, unknown>
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

// ============== 本体元数据类型 (Ontology Metadata) ==============

// 原有的本体 Schema（兼容性保留）
export interface OntologySchema {
  entities: OntologyEntity[]
  relationships: OntologyRelationship[]
}

export interface OntologyEntity {
  name: string
  description: string
  attributes: OntologyAttributeSimple[]
}

export interface OntologyAttributeSimple {
  name: string
  type: string
  primary?: boolean
  values?: string[]
}

export interface OntologyRelationship {
  from: string
  to: string
  type: string
  label: string
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

// ============== 语义层类型 (Semantic) ==============
export interface OntologySemantic {
  entities: OntologyEntitySemantic[]
}

export interface OntologyEntitySemantic {
  name: string
  description: string
  table_name: string
  is_aggregate_root: boolean
  attributes: OntologyAttribute[]
  relationships: OntologyRelationshipDetail[]
  related_entities: string[]
}

export interface OntologyAttribute {
  name: string
  type: string
  python_type: string
  is_primary_key: boolean
  is_foreign_key: boolean
  is_required: boolean
  is_nullable: boolean
  is_unique: boolean
  default_value: string | null
  max_length: number | null
  enum_values: string[] | null
  description: string
  security_level: 'PUBLIC' | 'INTERNAL' | 'CONFIDENTIAL' | 'RESTRICTED'
  foreign_key_target: string | null
  // Phase 2.5 enhanced fields
  display_name?: string
  searchable?: boolean
  indexed?: boolean
  is_rich_text?: boolean
  pii?: boolean
  phi?: boolean
  mask_strategy?: string
}

export interface OntologyRelationshipDetail {
  name: string
  target: string
  type: 'one_to_many' | 'many_to_one' | 'one_to_one' | 'many_to_many'
  foreign_key: string | null
  label: string
}

// ============== 动力层类型 (Kinetic) ==============
export interface OntologyKinetic {
  entities: OntologyEntityKinetic[]
}

export interface OntologyEntityKinetic {
  name: string
  description: string
  actions: OntologyAction[]
}

export interface OntologyAction {
  action_type: string
  description: string
  params: OntologyActionParam[]
  requires_confirmation: boolean
  allowed_roles: EmployeeRole[]
  writeback: boolean
  undoable: boolean
}

export interface OntologyActionParam {
  name: string
  type: 'string' | 'integer' | 'number' | 'boolean' | 'date' | 'datetime' | 'enum' | 'array' | 'object'
  required: boolean
  description: string
  enum_values?: string[]
  format?: string
}

// ============== 动态层类型 (Dynamic) ==============
export interface OntologyDynamic {
  state_machines: StateMachine[]
  permission_matrix: PermissionMatrix
  business_rules: BusinessRule[]
}

export interface StateMachine {
  entity: string
  description: string
  states: StateDefinition[]
  initial_state: string
  transitions: StateTransition[]
}

export interface StateDefinition {
  value: string
  label: string
  color?: string
}

export interface StateTransition {
  from: string
  to: string
  trigger: string
  trigger_action?: string
  condition?: string | null
  side_effects: string[]
}

export interface PermissionMatrix {
  roles: EmployeeRole[]
  actions: PermissionAction[]
}

export interface PermissionAction {
  action_type: string
  entity: string
  roles: EmployeeRole[]
}

export interface BusinessRule {
  rule_id: string
  entity: string
  rule_name: string
  description: string
  condition: string
  action: string
  severity: 'error' | 'warning' | 'info'
}

// ============== 领域事件类型 (Events) ==============
export interface OntologyEvent {
  name: string
  description: string
  entity: string
  triggered_by: string[]
  payload_fields: string[]
  subscribers: string[]
}

// ============== 接口系统类型 (Interface System - Phase 2.5) ==============

export interface OntologyInterfaceDef {
  description?: string
  required_properties: Record<string, string>
  required_actions: string[]
  implementations: string[]
}

export interface InterfaceImplementation {
  entity: string
  interfaces: string[]
}

// ============== Schema 导出类型 (Schema Export - Phase 2.5) ==============

export interface EntitySchema {
  name?: string
  description: string
  table_name: string
  is_aggregate_root: boolean
  properties: Record<string, any>
  actions: string[]
  interfaces: string[]
  state_machine?: any
  related_entities?: string[]
}

export interface ActionSchema {
  action_type: string
  entity: string
  description: string
  params: any[]
  requires_confirmation: boolean
  allowed_roles: string[]
}

export interface StateMachineSchema {
  entity: string
  states: string[]
  initial_state: string
  transitions: any[]
}

export interface OntologySchemaExport {
  entity_types: Record<string, EntitySchema>
  interfaces: Record<string, OntologyInterfaceDef>
  actions: Record<string, ActionSchema>
  state_machines: Record<string, StateMachineSchema>
}

export type OntologyTabType = 'data' | 'semantic' | 'kinetic' | 'dynamic' | 'interfaces'

// ============== Debug Panel Types (SPEC-19) ==============
export * from './debug'

