import { useState, useEffect } from 'react'
import { Users, Calendar, MessageSquare, Search, Loader2, ChevronDown, ChevronRight, Download, BarChart3 } from 'lucide-react'
import { conversationApi, employeeApi } from '../services/api'
import type { ConversationMessage, Employee, ConversationStatistics } from '../types'

// Collapsible inline section for structured data
function InlineCollapsible({ title, badge, children }: { title: string; badge?: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-2 border border-dark-700 rounded text-xs">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1 px-2 py-1 hover:bg-dark-700/50"
      >
        {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        <span className="text-dark-400">{title}</span>
        {badge && <span className="ml-auto text-dark-500">{badge}</span>}
      </button>
      {open && <div className="px-2 py-1 border-t border-dark-700 bg-dark-950">{children}</div>}
    </div>
  )
}

// C-3: Highlight keyword in text
function HighlightText({ text, keyword }: { text: string; keyword: string }) {
  if (!keyword || !keyword.trim()) {
    return <>{text}</>
  }
  const parts = text.split(new RegExp(`(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'))
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === keyword.toLowerCase()
          ? <mark key={i} className="bg-amber-500/30 text-amber-200 rounded px-0.5">{part}</mark>
          : part
      )}
    </>
  )
}

// C-6: Time gap separator
function TimeGapSeparator({ minutes }: { minutes: number }) {
  let label: string
  if (minutes >= 1440) {
    label = `${Math.floor(minutes / 1440)} 天`
  } else if (minutes >= 60) {
    label = `${Math.floor(minutes / 60)} 小时`
  } else {
    label = `${minutes} 分钟`
  }
  return (
    <div className="flex items-center gap-2 my-3 px-4">
      <div className="flex-1 border-t border-dashed border-dark-700" />
      <span className="text-[10px] text-dark-500">间隔 {label}</span>
      <div className="flex-1 border-t border-dashed border-dark-700" />
    </div>
  )
}

// C-6: Date separator
function DateSeparator({ date }: { date: string }) {
  return (
    <div className="flex items-center gap-2 my-3 px-4">
      <div className="flex-1 border-t border-dark-600" />
      <span className="text-xs text-dark-400 bg-dark-900 px-2">{date}</span>
      <div className="flex-1 border-t border-dark-600" />
    </div>
  )
}

export default function ConversationAdmin() {
  const [users, setUsers] = useState<{ user_id: number; name?: string }[]>([])
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null)
  const [dates, setDates] = useState<string[]>([])
  const [selectedDate, setSelectedDate] = useState<string>('')
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [keyword, setKeyword] = useState('')
  const [activeKeyword, setActiveKeyword] = useState('') // The keyword being applied to highlights
  const [loading, setLoading] = useState(false)
  const [employeeMap, setEmployeeMap] = useState<Record<number, string>>({})
  const [stats, setStats] = useState<ConversationStatistics | null>(null)
  const [showStats, setShowStats] = useState(true)

  // 加载有聊天记录的用户列表 + 统计
  useEffect(() => {
    const load = async () => {
      try {
        const [usersRes, employees, statsData] = await Promise.all([
          conversationApi.adminGetUsers(),
          employeeApi.getList(),
          conversationApi.adminGetStatistics(),
        ])
        const empMap: Record<number, string> = {}
        employees.forEach((e: Employee) => { empMap[e.id] = e.name })
        setEmployeeMap(empMap)
        setUsers(usersRes.users.map(u => ({
          user_id: u.user_id,
          name: empMap[u.user_id] || `用户 ${u.user_id}`
        })))
        setStats(statsData)
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
      setActiveKeyword(kw || '')
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

  // C-5: Export
  const handleExport = async (format: 'json' | 'csv') => {
    if (!selectedUserId) return
    try {
      if (format === 'csv') {
        await conversationApi.adminExport(selectedUserId, {
          start_date: selectedDate || undefined,
          end_date: selectedDate || undefined,
          format: 'csv',
        })
      } else {
        const data = await conversationApi.adminExport(selectedUserId, {
          start_date: selectedDate || undefined,
          end_date: selectedDate || undefined,
          format: 'json',
        })
        // Download JSON
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `chat_user_${selectedUserId}.json`
        a.click()
        window.URL.revokeObjectURL(url)
      }
    } catch (error) {
      console.error('Export failed:', error)
    }
  }

  // C-6: Calculate time gap in minutes between two timestamps
  const getGapMinutes = (ts1: string, ts2: string): number => {
    const d1 = new Date(ts1)
    const d2 = new Date(ts2)
    return Math.floor((d2.getTime() - d1.getTime()) / 60000)
  }

  const getDateStr = (ts: string): string => {
    return new Date(ts).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <MessageSquare size={24} className="text-primary-400" />
        <h1 className="text-xl font-bold">聊天记录管理</h1>
        <button
          onClick={() => setShowStats(!showStats)}
          className="ml-auto p-1.5 rounded hover:bg-dark-800 text-dark-400"
          title="Toggle statistics"
        >
          <BarChart3 size={16} />
        </button>
      </div>

      {/* C-4: Statistics panel */}
      {showStats && stats && (
        <div className="flex items-center gap-6 mb-4 px-4 py-2.5 bg-dark-900 border border-dark-800 rounded-lg text-sm">
          <span className="text-dark-400">总消息: <span className="text-white font-medium">{stats.total_messages.toLocaleString()}</span></span>
          <span className="text-dark-400">今日: <span className="text-primary-400 font-medium">{stats.today_messages}</span></span>
          <span className="text-dark-400">用户: <span className="text-white font-medium">{stats.user_count}</span></span>
          {stats.action_distribution.length > 0 && (
            <span className="text-dark-400">
              热门操作:{' '}
              {stats.action_distribution.slice(0, 3).map((a, i) => (
                <span key={a.action_type}>
                  {i > 0 && ', '}
                  <span className="text-sky-400 font-mono text-xs">{a.action_type}</span>
                  <span className="text-dark-500">({a.count})</span>
                </span>
              ))}
            </span>
          )}
        </div>
      )}

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
            {/* C-5: Export buttons */}
            {selectedUserId && messages.length > 0 && (
              <div className="ml-auto flex gap-1">
                <button
                  onClick={() => handleExport('json')}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-dark-400 hover:text-white hover:bg-dark-800 rounded"
                  title="导出 JSON"
                >
                  <Download size={12} />
                  JSON
                </button>
                <button
                  onClick={() => handleExport('csv')}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-dark-400 hover:text-white hover:bg-dark-800 rounded"
                  title="导出 CSV"
                >
                  <Download size={12} />
                  CSV
                </button>
              </div>
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
            {!loading && messages.map((msg, idx) => {
              // Topic grouping (C-2): detect topic boundary
              const prevMsg = idx > 0 ? messages[idx - 1] : null
              const currentTopic = msg.context?.topic_id
              const prevTopic = prevMsg?.context?.topic_id
              const isNewTopic = currentTopic && prevTopic && currentTopic !== prevTopic
              const isFollowup = msg.context?.is_followup

              // C-6: Time gap and date separators
              let timeGap: number | null = null
              let showDateSep = false
              if (prevMsg) {
                timeGap = getGapMinutes(prevMsg.timestamp, msg.timestamp)
                const prevDate = getDateStr(prevMsg.timestamp)
                const currDate = getDateStr(msg.timestamp)
                if (prevDate !== currDate) {
                  showDateSep = true
                }
              }

              return (
                <div key={msg.id}>
                  {/* C-6: Date separator (cross-day) */}
                  {showDateSep && (
                    <DateSeparator date={getDateStr(msg.timestamp)} />
                  )}

                  {/* C-6: Time gap separator (>30 min) */}
                  {!showDateSep && timeGap !== null && timeGap >= 30 && (
                    <TimeGapSeparator minutes={timeGap} />
                  )}

                  {/* Topic boundary separator */}
                  {isNewTopic && (
                    <div className="flex items-center gap-2 my-3">
                      <div className="flex-1 border-t border-dark-700" />
                      <span className="text-xs text-dark-500">新话题</span>
                      <div className="flex-1 border-t border-dark-700" />
                    </div>
                  )}

                  <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {/* Topic continuity indicator */}
                    {currentTopic && !isNewTopic && msg.role === 'assistant' && (
                      <div className="w-0.5 bg-dark-700 mr-2 rounded-full" />
                    )}

                    <div className={`max-w-[75%] rounded-lg px-3 py-2 ${
                      msg.role === 'user'
                        ? 'bg-primary-600/20 text-primary-100'
                        : 'bg-dark-800 text-dark-200'
                    }`}>
                      {/* Followup badge */}
                      {isFollowup && (
                        <span className="inline-block text-xs bg-dark-700 text-dark-400 px-1.5 py-0.5 rounded mb-1">续上轮</span>
                      )}

                      {/* C-3: Search highlight */}
                      <div className="text-sm whitespace-pre-wrap">
                        <HighlightText text={msg.content} keyword={activeKeyword} />
                      </div>

                      {/* Structured data: actions (C-1) */}
                      {msg.actions && msg.actions.length > 0 && (
                        <InlineCollapsible
                          title="Actions"
                          badge={`${msg.actions.length} action(s)`}
                        >
                          {msg.actions.map((action: any, i: number) => (
                            <div key={i} className="flex items-center gap-2 py-0.5">
                              <span className="text-sky-400 font-mono">{action.action_type}</span>
                              {action.entity_type && <span className="text-dark-500">({action.entity_type})</span>}
                              {action.requires_confirmation && <span className="text-amber-400">需确认</span>}
                            </div>
                          ))}
                        </InlineCollapsible>
                      )}

                      {/* Structured data: query result (C-1) */}
                      {!!msg.result_data?.query_result && (
                        <InlineCollapsible
                          title="Query Result"
                          badge={(msg.result_data.query_result as any)?.total != null
                            ? `${(msg.result_data.query_result as any).total} rows`
                            : undefined}
                        >
                          <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap max-h-32 overflow-auto">
                            {JSON.stringify(msg.result_data.query_result, null, 2)}
                          </pre>
                        </InlineCollapsible>
                      )}

                      <div className="text-xs text-dark-500 mt-1">
                        {new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
