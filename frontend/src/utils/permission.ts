/**
 * 前端权限工具
 */
import React from 'react'
import { useAuthStore } from '../store'

/** 检查当前用户是否拥有指定权限 */
export function hasPermission(permCode: string): boolean {
  const { permissions, user } = useAuthStore.getState()
  if (user?.role === 'sysadmin') return true
  return permissions.has(permCode)
}

/** 检查当前用户是否拥有任一权限 */
export function hasAnyPermission(...permCodes: string[]): boolean {
  return permCodes.some(hasPermission)
}

/** React Hook: 权限检查 */
export function usePermission(permCode: string): boolean {
  const permissions = useAuthStore(s => s.permissions)
  const user = useAuthStore(s => s.user)
  if (user?.role === 'sysadmin') return true
  return permissions.has(permCode)
}

/** PermissionGuard 组件 — 条件渲染子元素 */
export function PermissionGuard({
  permission,
  permissions: permList,
  fallback = null,
  children,
}: {
  permission?: string
  permissions?: string[]
  fallback?: React.ReactNode
  children: React.ReactNode
}): React.ReactNode {
  const userPermissions = useAuthStore(s => s.permissions)
  const user = useAuthStore(s => s.user)

  if (user?.role === 'sysadmin') return children

  const codes = permList || (permission ? [permission] : [])
  const allowed = codes.some(code => userPermissions.has(code))
  return allowed ? children : fallback
}

/** 权限常量（与后端 permissions.py 对应） */
export const Permissions = {
  ROOM_READ: 'room:read',
  ROOM_WRITE: 'room:write',
  ROOM_STATUS: 'room:status',
  GUEST_READ: 'guest:read',
  GUEST_WRITE: 'guest:write',
  RESERVATION_READ: 'reservation:read',
  RESERVATION_WRITE: 'reservation:write',
  RESERVATION_CANCEL: 'reservation:cancel',
  CHECKIN_EXECUTE: 'checkin:execute',
  CHECKOUT_EXECUTE: 'checkout:execute',
  BILL_READ: 'bill:read',
  BILL_WRITE: 'bill:write',
  BILL_REFUND: 'bill:refund',
  TASK_READ: 'task:read',
  TASK_WRITE: 'task:write',
  TASK_ASSIGN: 'task:assign',
  EMPLOYEE_READ: 'employee:read',
  EMPLOYEE_WRITE: 'employee:write',
  PRICE_READ: 'price:read',
  PRICE_WRITE: 'price:write',
  REPORT_READ: 'report:read',
  SYS_ROLE_MANAGE: 'sys:role:manage',
  SYS_DEPT_MANAGE: 'sys:dept:manage',
  SYS_USER_MANAGE: 'sys:user:manage',
  SYS_MENU_MANAGE: 'sys:menu:manage',
  SYS_DICT_MANAGE: 'sys:dict:manage',
  SYS_CONFIG_MANAGE: 'sys:config:manage',
  SYS_SCHEDULER_MANAGE: 'sys:scheduler:manage',
  SYS_MESSAGE_MANAGE: 'sys:message:manage',
  DEBUG_READ: 'debug:read',
  DEBUG_REPLAY: 'debug:replay',
  SECURITY_READ: 'security:read',
  AI_CHAT: 'ai:chat',
  ONTOLOGY_READ: 'ontology:read',
} as const
