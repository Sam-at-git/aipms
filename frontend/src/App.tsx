import { useState, useEffect } from 'react'
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
import Chat from './pages/Chat'
import ConversationAdmin from './pages/ConversationAdmin'
import DebugPanel from './pages/DebugPanel'
import SessionDetail from './pages/SessionDetail'
import ReplayResult from './pages/ReplayResult'
import DictManagement from './pages/system/DictManagement'
import ConfigManagement from './pages/system/ConfigManagement'
import RbacManagement from './pages/system/RbacManagement'
import OrgManagement from './pages/system/OrgManagement'
import MessageCenter from './pages/system/MessageCenter'
import SchedulerManagement from './pages/system/SchedulerManagement'

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
      <Route path="/chat" element={<ProtectedRoute><Chat /></ProtectedRoute>} />
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
        <Route path="conversation-admin" element={<ConversationAdmin />} />
        <Route path="debug" element={<DebugPanel />} />
        <Route path="debug/sessions/:sessionId" element={<SessionDetail />} />
        <Route path="debug/replay/:replayId" element={<ReplayResult />} />
        <Route path="system/dicts" element={<DictManagement />} />
        <Route path="system/configs" element={<ConfigManagement />} />
        <Route path="system/rbac" element={<RbacManagement />} />
        <Route path="system/org" element={<OrgManagement />} />
        <Route path="system/messages" element={<MessageCenter />} />
        <Route path="system/schedulers" element={<SchedulerManagement />} />
      </Route>
    </Routes>
  )
}

// 应用布局组件
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, BedDouble, CalendarCheck, Users, ClipboardList,
  DollarSign, UserCog, BarChart3, LogOut, Menu, MessageSquare, Settings as SettingsIcon, Tag, FileText, UserCircle,
  Database, Shield, Bug, BookOpen, ChevronDown, ChevronRight, LucideIcon, Circle, Bell
} from 'lucide-react'
import { useUIStore } from './store'
import { messageApi } from './services/api'

// Icon name → Lucide component mapping
const iconMap: Record<string, LucideIcon> = {
  LayoutDashboard, BedDouble, CalendarCheck, Users, ClipboardList,
  DollarSign, UserCog, BarChart3, MessageSquare, Tag, FileText, UserCircle,
  Database, Shield, Bug, BookOpen, Settings: SettingsIcon,
}

interface DynamicMenuItem {
  path: string
  icon: LucideIcon
  label: string
  children?: DynamicMenuItem[]
}

// Fallback static navItems (used when API fails)
const fallbackNavItems = [
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
  { path: '/settings', icon: SettingsIcon, label: '系统设置', roles: ['sysadmin'] },
  { path: '/chat', icon: MessageSquare, label: '独立聊天', roles: ['sysadmin', 'manager', 'receptionist', 'cleaner'] },
]

function convertMenuTree(tree: any[]): DynamicMenuItem[] {
  return tree.map(node => {
    const IconComp = iconMap[node.icon] || Circle
    const item: DynamicMenuItem = {
      path: node.path || '',
      icon: IconComp,
      label: node.name,
    }
    if (node.children && node.children.length > 0) {
      item.children = convertMenuTree(node.children)
    }
    return item
  })
}

function AppLayout() {
  const { user, logout } = useAuthStore()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const navigate = useNavigate()
  const [dynamicMenus, setDynamicMenus] = useState<DynamicMenuItem[] | null>(null)
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set())
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    if (user) {
      // Fetch user menus from backend
      fetch('/api/system/menus/user', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token') || ''}` }
      })
        .then(res => res.ok ? res.json() : Promise.reject())
        .then(tree => setDynamicMenus(convertMenuTree(tree)))
        .catch(() => setDynamicMenus(null))

      // Fetch unread message count
      messageApi.getUnreadCount().then(setUnreadCount).catch(() => {})
      // Poll every 60 seconds
      const interval = setInterval(() => {
        messageApi.getUnreadCount().then(setUnreadCount).catch(() => {})
      }, 60000)
      return () => clearInterval(interval)
    }
  }, [user])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Use dynamic menus if available, otherwise fallback to role-filtered static items
  const menuItems: DynamicMenuItem[] = dynamicMenus || fallbackNavItems.filter(
    item => user && item.roles.includes(user.role)
  )

  const toggleDir = (label: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }

  return (
    <>
      {/* 侧边栏 */}
      <aside className={`${sidebarCollapsed ? 'w-16' : 'w-56'} bg-dark-900 border-r border-dark-800 flex flex-col transition-all duration-300 flex-shrink-0`}>
        {/* Logo */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-dark-800">
          {!sidebarCollapsed && (
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-primary-400">AIPMS</span>
              <button onClick={() => navigate('/system/messages')} className="relative p-1 hover:bg-dark-800 rounded" title="消息中心">
                <Bell size={16} className="text-dark-400" />
                {unreadCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] min-w-[16px] h-4 flex items-center justify-center rounded-full px-1">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </button>
            </div>
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
          {menuItems.map(item => item.children ? (
            <div key={item.label}>
              <button
                onClick={() => toggleDir(item.label)}
                className="flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg transition-colors text-dark-400 hover:bg-dark-800 hover:text-dark-200 w-full text-left"
              >
                <item.icon size={20} />
                {!sidebarCollapsed && (
                  <>
                    <span className="flex-1">{item.label}</span>
                    {expandedDirs.has(item.label) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </>
                )}
              </button>
              {expandedDirs.has(item.label) && !sidebarCollapsed && item.children.map(child => (
                <NavLink
                  key={child.path}
                  to={child.path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 pl-10 pr-4 py-2 mx-2 rounded-lg transition-colors text-sm ${
                      isActive
                        ? 'bg-primary-600/20 text-primary-400'
                        : 'text-dark-400 hover:bg-dark-800 hover:text-dark-200'
                    }`
                  }
                >
                  <child.icon size={16} />
                  <span>{child.label}</span>
                </NavLink>
              ))}
            </div>
          ) : (
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
