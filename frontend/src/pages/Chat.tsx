import { Link } from 'react-router-dom'
import { ArrowLeft, MessageSquare } from 'lucide-react'
import ChatPanel from '../components/ChatPanel'

export default function Chat() {
  return (
    <div className="h-screen flex flex-col bg-dark-950">
      {/* 顶栏 */}
      <div className="h-14 flex items-center justify-between px-4 border-b border-dark-800 bg-dark-900 flex-shrink-0">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-1 text-dark-400 hover:text-dark-200 transition-colors"
          >
            <ArrowLeft size={18} />
            <span className="text-sm">返回</span>
          </Link>
          <div className="w-px h-6 bg-dark-700" />
          <MessageSquare size={20} className="text-primary-400" />
          <span className="font-medium">智能助手</span>
        </div>
      </div>

      {/* 聊天区域 */}
      <div className="flex-1 overflow-hidden max-w-3xl w-full mx-auto">
        <ChatPanel />
      </div>
    </div>
  )
}
