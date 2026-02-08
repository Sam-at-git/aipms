import { useState, useEffect } from 'react'
import { Users, Calendar, MessageSquare, Search, Loader2 } from 'lucide-react'
import { conversationApi, employeeApi } from '../services/api'
import type { ConversationMessage, Employee } from '../types'

export default function ConversationAdmin() {
  const [users, setUsers] = useState<{ user_id: number; name?: string }[]>([])
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null)
  const [dates, setDates] = useState<string[]>([])
  const [selectedDate, setSelectedDate] = useState<string>('')
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)
  const [employeeMap, setEmployeeMap] = useState<Record<number, string>>({})

  // 加载有聊天记录的用户列表
  useEffect(() => {
    const load = async () => {
      try {
        const [usersRes, employees] = await Promise.all([
          conversationApi.adminGetUsers(),
          employeeApi.getList()
        ])
        const empMap: Record<number, string> = {}
        employees.forEach((e: Employee) => { empMap[e.id] = e.name })
        setEmployeeMap(empMap)
        setUsers(usersRes.users.map(u => ({
          user_id: u.user_id,
          name: empMap[u.user_id] || `用户 ${u.user_id}`
        })))
      } catch (error) {
        console.error('Failed to load users:', error)
      }
    }
    load()
  }, [])

  // 选择用户后加载日期列表
  useEffect(() => {
    if (!selectedUserId) {
      setDates([])
      setMessages([])
      return
    }
    const loadDates = async () => {
      try {
        const res = await conversationApi.adminGetUserDates(selectedUserId)
        setDates(res.dates)
        setSelectedDate('')
        setMessages([])
      } catch (error) {
        console.error('Failed to load dates:', error)
      }
    }
    loadDates()
  }, [selectedUserId])

  // 加载消息
  const loadMessages = async (dateStr?: string, kw?: string) => {
    if (!selectedUserId) return
    setLoading(true)
    try {
      const res = await conversationApi.adminGetUserMessages(selectedUserId, {
        date_str: dateStr || undefined,
        keyword: kw || undefined
      })
      setMessages(res.messages)
    } catch (error) {
      console.error('Failed to load messages:', error)
    } finally {
      setLoading(false)
    }
  }

  // 选择日期
  const handleDateSelect = (d: string) => {
    setSelectedDate(d)
    loadMessages(d, keyword)
  }

  // 搜索
  const handleSearch = () => {
    loadMessages(selectedDate, keyword)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <MessageSquare size={24} className="text-primary-400" />
        <h1 className="text-xl font-bold">聊天记录管理</h1>
      </div>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* 左栏：用户列表 */}
        <div className="w-48 flex-shrink-0 bg-dark-900 rounded-lg border border-dark-800 flex flex-col">
          <div className="p-3 border-b border-dark-800 flex items-center gap-2">
            <Users size={16} className="text-dark-400" />
            <span className="text-sm font-medium">用户</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {users.map(u => (
              <button
                key={u.user_id}
                onClick={() => setSelectedUserId(u.user_id)}
                className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                  selectedUserId === u.user_id
                    ? 'bg-primary-600/20 text-primary-400'
                    : 'text-dark-300 hover:bg-dark-800'
                }`}
              >
                {u.name}
              </button>
            ))}
            {users.length === 0 && (
              <p className="text-xs text-dark-500 p-3">暂无聊天记录</p>
            )}
          </div>
        </div>

        {/* 中栏：日期选择 + 搜索 */}
        <div className="w-40 flex-shrink-0 bg-dark-900 rounded-lg border border-dark-800 flex flex-col">
          <div className="p-3 border-b border-dark-800 flex items-center gap-2">
            <Calendar size={16} className="text-dark-400" />
            <span className="text-sm font-medium">日期</span>
          </div>
          {selectedUserId && (
            <div className="p-2 border-b border-dark-800">
              <div className="flex gap-1">
                <input
                  type="text"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="搜索..."
                  className="flex-1 bg-dark-800 border border-dark-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-primary-500"
                />
                <button
                  onClick={handleSearch}
                  className="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs"
                >
                  <Search size={12} />
                </button>
              </div>
            </div>
          )}
          <div className="flex-1 overflow-y-auto">
            {dates.map(d => (
              <button
                key={d}
                onClick={() => handleDateSelect(d)}
                className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                  selectedDate === d
                    ? 'bg-primary-600/20 text-primary-400'
                    : 'text-dark-300 hover:bg-dark-800'
                }`}
              >
                {d}
              </button>
            ))}
            {selectedUserId && dates.length === 0 && (
              <p className="text-xs text-dark-500 p-3">无记录</p>
            )}
          </div>
        </div>

        {/* 右栏：消息内容 */}
        <div className="flex-1 bg-dark-900 rounded-lg border border-dark-800 flex flex-col">
          <div className="p-3 border-b border-dark-800 flex items-center gap-2">
            <MessageSquare size={16} className="text-dark-400" />
            <span className="text-sm font-medium">
              {selectedUserId
                ? `${employeeMap[selectedUserId] || `用户 ${selectedUserId}`} 的聊天记录`
                : '请选择用户'}
            </span>
            {selectedDate && (
              <span className="text-xs text-dark-500 ml-2">{selectedDate}</span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {loading && (
              <div className="flex justify-center py-8">
                <Loader2 size={20} className="animate-spin text-dark-500" />
              </div>
            )}
            {!loading && messages.length === 0 && selectedUserId && (
              <p className="text-sm text-dark-500 text-center py-8">
                {selectedDate ? '该日期无聊天记录' : '请选择日期查看记录'}
              </p>
            )}
            {!loading && messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[70%] rounded-lg px-3 py-2 ${
                  msg.role === 'user'
                    ? 'bg-primary-600/20 text-primary-100'
                    : 'bg-dark-800 text-dark-200'
                }`}>
                  <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                  <div className="text-xs text-dark-500 mt-1">
                    {new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
