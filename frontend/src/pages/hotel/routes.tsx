import { Route } from 'react-router-dom'
import Dashboard from './Dashboard'
import Rooms from './Rooms'
import Reservations from './Reservations'
import Guests from './Guests'
import Customers from './Customers'
import Tasks from './Tasks'
import Billing from './Billing'
import Employees from './Employees'
import Prices from './Prices'
import Reports from './Reports'
import {
  LayoutDashboard, BedDouble, CalendarCheck, Users, ClipboardList,
  DollarSign, UserCog, BarChart3, Tag, UserCircle,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface HotelNavItem {
  path: string
  icon: LucideIcon
  label: string
  roles: string[]
}

export const hotelNavItems: HotelNavItem[] = [
  { path: '/', icon: LayoutDashboard, label: '工作台', roles: ['sysadmin', 'manager', 'receptionist', 'cleaner'] },
  { path: '/rooms', icon: BedDouble, label: '房态管理', roles: ['sysadmin', 'manager', 'receptionist'] },
  { path: '/reservations', icon: CalendarCheck, label: '预订管理', roles: ['sysadmin', 'manager', 'receptionist'] },
  { path: '/guests', icon: Users, label: '在住客人', roles: ['sysadmin', 'manager', 'receptionist'] },
  { path: '/customers', icon: UserCircle, label: '客户管理', roles: ['sysadmin', 'manager', 'receptionist'] },
  { path: '/tasks', icon: ClipboardList, label: '任务管理', roles: ['sysadmin', 'manager', 'receptionist', 'cleaner'] },
  { path: '/billing', icon: DollarSign, label: '账单管理', roles: ['sysadmin', 'manager', 'receptionist'] },
  { path: '/prices', icon: Tag, label: '价格管理', roles: ['sysadmin', 'manager'] },
  { path: '/employees', icon: UserCog, label: '员工管理', roles: ['sysadmin', 'manager'] },
  { path: '/reports', icon: BarChart3, label: '统计报表', roles: ['sysadmin', 'manager'] },
]

export function getHotelRoutes() {
  return (
    <>
      <Route index element={<Dashboard />} />
      <Route path="rooms" element={<Rooms />} />
      <Route path="reservations" element={<Reservations />} />
      <Route path="guests" element={<Guests />} />
      <Route path="customers" element={<Customers />} />
      <Route path="tasks" element={<Tasks />} />
      <Route path="billing" element={<Billing />} />
      <Route path="prices" element={<Prices />} />
      <Route path="employees" element={<Employees />} />
      <Route path="reports" element={<Reports />} />
    </>
  )
}
