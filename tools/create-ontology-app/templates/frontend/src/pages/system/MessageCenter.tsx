import { useEffect, useState } from 'react'
import { Bell, Mail, MailOpen, CheckCheck, Megaphone } from 'lucide-react'
import { messageApi, SysMessageItem, SysAnnouncementActive } from '../../services/api'

type Tab = 'inbox' | 'announcements'

export default function MessageCenter() {
  const [tab, setTab] = useState<Tab>('inbox')
  const [messages, setMessages] = useState<SysMessageItem[]>([])
  const [announcements, setAnnouncements] = useState<SysAnnouncementActive[]>([])
  const [total, setTotal] = useState(0)
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'unread'>('all')

  useEffect(() => { loadInbox() }, [filter])
  useEffect(() => { if (tab === 'announcements') loadAnnouncements() }, [tab])

  const loadInbox = async () => {
    setLoading(true)
    try {
      const data = await messageApi.getInbox({
        is_read: filter === 'unread' ? false : undefined,
        limit: 100,
      })
      setMessages(data.messages)
      setTotal(data.total)
      setUnread(data.unread_count)
    } catch (err) {
      console.error('Failed to load inbox:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadAnnouncements = async () => {
    try {
      const data = await messageApi.getActiveAnnouncements()
      setAnnouncements(data)
    } catch (err) {
      console.error('Failed to load announcements:', err)
    }
  }

  const markRead = async (id: number) => {
    await messageApi.markRead(id)
    setMessages(prev => prev.map(m => m.id === id ? { ...m, is_read: true } : m))
    setUnread(prev => Math.max(0, prev - 1))
  }

  const markAllRead = async () => {
    await messageApi.markAllRead()
    setMessages(prev => prev.map(m => ({ ...m, is_read: true })))
    setUnread(0)
  }

  const markAnnRead = async (id: number) => {
    await messageApi.markAnnouncementRead(id)
    setAnnouncements(prev => prev.map(a => a.id === id ? { ...a, is_read: true } : a))
  }

  const msgTypeLabel = (t: string) => {
    if (t === 'system') return '系统'
    if (t === 'business') return '业务'
    if (t === 'todo') return '待办'
    return t
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Bell size={24} className="text-primary-400" />
          <h1 className="text-xl font-bold">消息中心</h1>
          {unread > 0 && (
            <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">{unread}</span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4">
        <button
          onClick={() => setTab('inbox')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm ${
            tab === 'inbox' ? 'bg-primary-600 text-white' : 'text-dark-400 hover:bg-dark-800'
          }`}
        >
          <Mail size={14} /> 收件箱
        </button>
        <button
          onClick={() => setTab('announcements')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm ${
            tab === 'announcements' ? 'bg-primary-600 text-white' : 'text-dark-400 hover:bg-dark-800'
          }`}
        >
          <Megaphone size={14} /> 公告
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 bg-dark-900 rounded-lg border border-dark-800 overflow-hidden flex flex-col">
        {tab === 'inbox' && (
          <>
            <div className="p-3 border-b border-dark-800 flex items-center justify-between">
              <div className="flex gap-2">
                <button
                  onClick={() => setFilter('all')}
                  className={`text-xs px-2 py-1 rounded ${filter === 'all' ? 'bg-dark-700 text-white' : 'text-dark-400'}`}
                >
                  全部 ({total})
                </button>
                <button
                  onClick={() => setFilter('unread')}
                  className={`text-xs px-2 py-1 rounded ${filter === 'unread' ? 'bg-dark-700 text-white' : 'text-dark-400'}`}
                >
                  未读 ({unread})
                </button>
              </div>
              {unread > 0 && (
                <button
                  onClick={markAllRead}
                  className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300"
                >
                  <CheckCheck size={12} /> 全部标记已读
                </button>
              )}
            </div>
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <p className="text-sm text-dark-500 text-center py-8">加载中...</p>
              ) : messages.length === 0 ? (
                <p className="text-sm text-dark-500 text-center py-8">暂无消息</p>
              ) : (
                messages.map(msg => (
                  <div
                    key={msg.id}
                    onClick={() => !msg.is_read && markRead(msg.id)}
                    className={`px-4 py-3 border-b border-dark-800/50 cursor-pointer hover:bg-dark-800/30 ${
                      !msg.is_read ? 'bg-dark-800/10' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {msg.is_read
                        ? <MailOpen size={14} className="text-dark-500" />
                        : <Mail size={14} className="text-primary-400" />
                      }
                      <span className={`text-sm font-medium ${!msg.is_read ? 'text-white' : 'text-dark-300'}`}>
                        {msg.title}
                      </span>
                      <span className="text-xs bg-dark-700 text-dark-400 px-1.5 py-0.5 rounded ml-auto">
                        {msgTypeLabel(msg.msg_type)}
                      </span>
                    </div>
                    <p className="text-xs text-dark-500 mt-1 line-clamp-1 pl-6">{msg.content}</p>
                    <p className="text-xs text-dark-600 mt-1 pl-6">
                      {msg.created_at ? new Date(msg.created_at).toLocaleString('zh-CN') : ''}
                    </p>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {tab === 'announcements' && (
          <div className="flex-1 overflow-y-auto">
            {announcements.length === 0 ? (
              <p className="text-sm text-dark-500 text-center py-8">暂无公告</p>
            ) : (
              announcements.map(ann => (
                <div
                  key={ann.id}
                  onClick={() => !ann.is_read && markAnnRead(ann.id)}
                  className={`px-4 py-3 border-b border-dark-800/50 cursor-pointer hover:bg-dark-800/30 ${
                    !ann.is_read ? 'bg-dark-800/10' : ''
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Megaphone size={14} className={ann.is_pinned ? 'text-amber-400' : 'text-dark-400'} />
                    <span className={`text-sm font-medium ${!ann.is_read ? 'text-white' : 'text-dark-300'}`}>
                      {ann.title}
                    </span>
                    {ann.is_pinned && <span className="text-xs text-amber-400">置顶</span>}
                  </div>
                  <p className="text-xs text-dark-400 mt-1 pl-6 whitespace-pre-wrap">{ann.content}</p>
                  <p className="text-xs text-dark-600 mt-1 pl-6">
                    {ann.publish_at ? new Date(ann.publish_at).toLocaleString('zh-CN') : ''}
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
