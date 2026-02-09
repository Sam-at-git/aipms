import React from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, BedDouble, CalendarCheck, Users, ClipboardList,
  DollarSign, UserCog, BarChart3, LogOut, Menu, MessageSquare, Settings as SettingsIcon
} from 'lucide-react'
import { useAuthStore, useUIStore, useOntologyStore } from '../store'

const navItems = [
  { path: '/', icon: LayoutDashboard, label: '工作台', roles: ['manager', 'receptionist', 'cleaner'] },
  { path: '/rooms', icon: BedDouble, label: '房态管理', roles: ['manager', 'receptionist'] },
  { path: '/reservations', icon: CalendarCheck, label: '预订管理', roles: ['manager', 'receptionist'] },
  { path: '/guests', icon: Users, label: '在住客人', roles: ['manager', 'receptionist'] },
  { path: '/tasks', icon: ClipboardList, label: '任务管理', roles: ['manager', 'receptionist', 'cleaner'] },
  { path: '/billing', icon: DollarSign, label: '账单管理', roles: ['manager', 'receptionist'] },
  { path: '/employees', icon: UserCog, label: '员工管理', roles: ['manager'] },
  { path: '/reports', icon: BarChart3, label: '统计报表', roles: ['manager'] },
  { path: '/settings', icon: SettingsIcon, label: '系统设置', roles: ['manager'] },
]

export default function Layout() {
  const { user, logout } = useAuthStore()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const initialize = useOntologyStore(s => s.initialize)
  const navigate = useNavigate()

  // Initialize ontology store on mount (requires auth)
  React.useEffect(() => { initialize() }, [initialize])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const filteredNavItems = navItems.filter(item =>
    user && item.roles.includes(user.role)
  )

  return (
    <div className="flex h-screen bg-dark-950">
      {/* 侧边栏 */}
      <aside className={`${sidebarCollapsed ? 'w-16' : 'w-56'} bg-dark-900 border-r border-dark-800 flex flex-col transition-all duration-300`}>
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
                {user?.role === 'manager' ? '经理' :
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

      {/* 主内容区 - 分为左侧数字孪生和右侧对话内核 */}
      <main className="flex-1 flex overflow-hidden">
        {/* 左侧：数字孪生（功能页面） */}
        <div className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </div>

        {/* 右侧：对话内核 */}
        <div className="w-80 border-l border-dark-800 bg-dark-900 flex flex-col">
          <div className="h-14 flex items-center gap-2 px-4 border-b border-dark-800">
            <MessageSquare size={20} className="text-primary-400" />
            <span className="font-medium">智能助手</span>
          </div>
          <div className="flex-1 overflow-hidden">
            {/* ChatPanel 将在这里渲染 */}
            <Outlet context={{ isChat: true }} />
          </div>
        </div>
      </main>
    </div>
  )
}
