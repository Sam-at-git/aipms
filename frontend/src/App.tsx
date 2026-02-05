import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from './store'
import Layout from './components/Layout'
import ChatPanel from './components/ChatPanel'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Rooms from './pages/Rooms'
import Reservations from './pages/Reservations'
import Guests from './pages/Guests'
import Tasks from './pages/Tasks'
import Billing from './pages/Billing'
import Employees from './pages/Employees'
import Reports from './pages/Reports'
import Settings from './pages/Settings'
import Prices from './pages/Prices'
import AuditLogs from './pages/AuditLogs'
import Customers from './pages/Customers'
import Ontology from './pages/Ontology'
import SecurityDashboard from './pages/SecurityDashboard'

// 受保护路由
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// 带聊天面板的布局
function LayoutWithChat() {
  return (
    <div className="flex h-screen bg-dark-950">
      {/* 左侧：导航和内容 */}
      <div className="flex-1 flex overflow-hidden">
        <Layout />
      </div>
    </div>
  )
}

// 主页面包装器（包含ChatPanel）
function MainWrapper() {
  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-6">
        <Outlet />
      </div>
      <div className="w-80 border-l border-dark-800 bg-dark-900">
        <ChatPanel />
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <div className="flex h-screen bg-dark-950">
              {/* 侧边栏和主内容 */}
              <AppLayout />
            </div>
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="rooms" element={<Rooms />} />
        <Route path="reservations" element={<Reservations />} />
        <Route path="guests" element={<Guests />} />
        <Route path="customers" element={<Customers />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="billing" element={<Billing />} />
        <Route path="prices" element={<Prices />} />
        <Route path="audit-logs" element={<AuditLogs />} />
        <Route path="employees" element={<Employees />} />
        <Route path="reports" element={<Reports />} />
        <Route path="settings" element={<Settings />} />
        <Route path="ontology" element={<Ontology />} />
        <Route path="security" element={<SecurityDashboard />} />
      </Route>
    </Routes>
  )
}

// 应用布局组件
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, BedDouble, CalendarCheck, Users, ClipboardList,
  DollarSign, UserCog, BarChart3, LogOut, Menu, MessageSquare, Settings as SettingsIcon, Tag, FileText, UserCircle,
  Database, Shield
} from 'lucide-react'
import { useUIStore } from './store'

const navItems = [
  { path: '/', icon: LayoutDashboard, label: '工作台', roles: ['sysadmin', 'manager', 'receptionist', 'cleaner'] },
  { path: '/rooms', icon: BedDouble, label: '房态管理', roles: ['sysadmin', 'manager', 'receptionist'] },
  { path: '/reservations', icon: CalendarCheck, label: '预订管理', roles: ['sysadmin', 'manager', 'receptionist'] },
  { path: '/guests', icon: Users, label: '在住客人', roles: ['sysadmin', 'manager', 'receptionist'] },
  { path: '/customers', icon: UserCircle, label: '客户管理', roles: ['sysadmin', 'manager', 'receptionist'] },
  { path: '/tasks', icon: ClipboardList, label: '任务管理', roles: ['sysadmin', 'manager', 'receptionist', 'cleaner'] },
  { path: '/billing', icon: DollarSign, label: '账单管理', roles: ['sysadmin', 'manager', 'receptionist'] },
  { path: '/prices', icon: Tag, label: '价格管理', roles: ['sysadmin', 'manager'] },
  { path: '/audit-logs', icon: FileText, label: '审计日志', roles: ['sysadmin'] },
  { path: '/ontology', icon: Database, label: '本体视图', roles: ['sysadmin'] },
  { path: '/security', icon: Shield, label: '安全管理', roles: ['sysadmin'] },
  { path: '/employees', icon: UserCog, label: '员工管理', roles: ['sysadmin', 'manager'] },
  { path: '/reports', icon: BarChart3, label: '统计报表', roles: ['sysadmin', 'manager'] },
  { path: '/settings', icon: SettingsIcon, label: '系统设置', roles: ['sysadmin'] },
]

function AppLayout() {
  const { user, logout } = useAuthStore()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const filteredNavItems = navItems.filter(item =>
    user && item.roles.includes(user.role)
  )

  return (
    <>
      {/* 侧边栏 */}
      <aside className={`${sidebarCollapsed ? 'w-16' : 'w-56'} bg-dark-900 border-r border-dark-800 flex flex-col transition-all duration-300 flex-shrink-0`}>
        {/* Logo */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-dark-800">
          {!sidebarCollapsed && (
            <span className="text-lg font-bold text-primary-400">AIPMS</span>
          )}
          <button
            onClick={toggleSidebar}
            className="p-1 hover:bg-dark-800 rounded"
          >
            <Menu size={20} />
          </button>
        </div>

        {/* 导航 */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {filteredNavItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-primary-600/20 text-primary-400'
                    : 'text-dark-400 hover:bg-dark-800 hover:text-dark-200'
                }`
              }
            >
              <item.icon size={20} />
              {!sidebarCollapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* 用户信息 */}
        <div className="p-4 border-t border-dark-800">
          {!sidebarCollapsed && (
            <div className="mb-3">
              <p className="text-sm font-medium">{user?.name}</p>
              <p className="text-xs text-dark-500">
                {user?.role === 'sysadmin' ? '系统管理员' :
                 user?.role === 'manager' ? '经理' :
                 user?.role === 'receptionist' ? '前台' : '清洁员'}
              </p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-dark-400 hover:text-red-400 transition-colors"
          >
            <LogOut size={18} />
            {!sidebarCollapsed && <span className="text-sm">退出登录</span>}
          </button>
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="flex-1 flex overflow-hidden">
        {/* 左侧：数字孪生（功能页面） */}
        <div className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </div>

        {/* 右侧：对话内核 */}
        <div className="w-80 border-l border-dark-800 bg-dark-900 flex flex-col flex-shrink-0">
          <div className="h-14 flex items-center gap-2 px-4 border-b border-dark-800">
            <MessageSquare size={20} className="text-primary-400" />
            <span className="font-medium">智能助手</span>
          </div>
          <div className="flex-1 overflow-hidden">
            <ChatPanel />
          </div>
        </div>
      </main>
    </>
  )
}
