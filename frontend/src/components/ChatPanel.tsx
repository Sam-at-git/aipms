import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, Check, X, Search, ChevronUp, Globe } from 'lucide-react'
import { useChatStore, useOntologyStore } from '../store'
import ActionForm from './ActionForm'
import { aiApi, conversationApi } from '../services/api'
import { getChatText } from '../i18n/chat'
import type { AIAction, ChatMessage, CandidateOption, ConversationMessage, FollowUpInfo, QueryResultData } from '../types'

// 日期分隔组件
function DateSeparator({ date }: { date: string }) {
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const dateObj = new Date(date)
  const dateStr = dateObj.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })

  let displayText = dateStr
  if (dateObj.toDateString() === today.toDateString()) {
    displayText = '今天'
  } else if (dateObj.toDateString() === yesterday.toDateString()) {
    displayText = '昨天'
  }

  return (
    <div className="flex items-center justify-center my-4">
      <div className="bg-dark-700 text-dark-400 text-xs px-3 py-1 rounded-full">
        {displayText}
      </div>
    </div>
  )
}

// 查询结果展示组件
function QueryResultDisplay({ result }: { result: QueryResultData }) {
  if (result.display_type === 'table' && result.rows && result.columns) {
    return (
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-dark-700">
              {result.columns.map((col, i) => (
                <th key={i} className="px-2 py-1 text-left text-dark-300 font-medium border-b border-dark-600">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-dark-700/50">
                {(result.column_keys || result.columns!).map((key, colIdx) => (
                  <td key={colIdx} className="px-2 py-1 text-dark-200 border-b border-dark-800">
                    {String(row[key as string] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-[10px] text-dark-500 mt-1">{result.rows.length} 条记录</p>
      </div>
    )
  }

  if (result.display_type === 'chart' && result.data) {
    // 简单的统计卡片展示（预留图表接口）
    const entries = Object.entries(result.data).filter(([, v]) => typeof v === 'number' || typeof v === 'string')
    return (
      <div className="mt-2 grid grid-cols-2 gap-2">
        {entries.slice(0, 6).map(([key, value]) => (
          <div key={key} className="bg-dark-700 rounded px-2 py-1.5">
            <div className="text-[10px] text-dark-400">{key}</div>
            <div className="text-sm font-medium text-dark-200">{String(value)}</div>
          </div>
        ))}
      </div>
    )
  }

  return null
}

// 将服务端消息转换为本地格式
function convertToLocalMessage(msg: ConversationMessage): ChatMessage {
  return {
    id: msg.id,
    role: msg.role,
    content: msg.content,
    timestamp: new Date(msg.timestamp),
    actions: msg.actions,
    context: msg.context
  }
}

// 按日期分组消息
function groupMessagesByDate(messages: ChatMessage[]): Map<string, ChatMessage[]> {
  const groups = new Map<string, ChatMessage[]>()

  messages.forEach(msg => {
    const dateKey = msg.timestamp.toDateString()
    if (!groups.has(dateKey)) {
      groups.set(dateKey, [])
    }
    groups.get(dateKey)!.push(msg)
  })

  return groups
}

export default function ChatPanel() {
  const [input, setInput] = useState('')
  const [pendingAction, setPendingAction] = useState<AIAction | null>(null)
  const [followUpInfo, setFollowUpInfo] = useState<FollowUpInfo | null>(null)
  const [formValues, setFormValues] = useState<Record<string, string>>({})
  const [showForm, setShowForm] = useState(true)
  const [showSearch, setShowSearch] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [selectedDate, setSelectedDate] = useState('')
  const [availableDates, setAvailableDates] = useState<string[]>([])
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  const {
    messages,
    isLoading,
    hasMore,
    oldestTimestamp,
    currentTopicId,
    searchResults,
    isSearching,
    historyLoaded,
    addMessage,
    prependMessages,
    setMessages,
    setLoading,
    setHasMore,
    setOldestTimestamp,
    setCurrentTopicId,
    setSearchResults,
    setIsSearching,
    setHistoryLoaded,
    clearSearch,
    language,
    setLanguage
  } = useChatStore()

  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollPositionRef = useRef<number>(0)
  const scrollHeightRef = useRef<number>(0)

  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // 保持滚动位置（用于加载更多历史后）
  const maintainScrollPosition = useCallback(() => {
    if (messagesContainerRef.current) {
      const newScrollHeight = messagesContainerRef.current.scrollHeight
      const scrollDiff = newScrollHeight - scrollHeightRef.current
      messagesContainerRef.current.scrollTop = scrollPositionRef.current + scrollDiff
    }
  }, [])

  // 初始化加载历史消息
  useEffect(() => {
    if (historyLoaded) return

    const loadHistory = async () => {
      try {
        const response = await conversationApi.getLastActive()
        const localMessages = response.messages.map(convertToLocalMessage)
        setMessages(localMessages)
        setHasMore(response.has_more)
        setOldestTimestamp(response.oldest_timestamp || null)
        setHistoryLoaded(true)

        // 如果有消息，设置当前 topic_id
        if (localMessages.length > 0) {
          const lastMsg = localMessages[localMessages.length - 1]
          if (lastMsg.context?.topic_id) {
            setCurrentTopicId(lastMsg.context.topic_id)
          }
        }

        // 滚动到底部
        setTimeout(scrollToBottom, 100)
      } catch (error) {
        console.error('Failed to load history:', error)
        setHistoryLoaded(true)
      }
    }

    loadHistory()
  }, [historyLoaded, setMessages, setHasMore, setOldestTimestamp, setHistoryLoaded, setCurrentTopicId, scrollToBottom])

  // 新消息时滚动到底部
  useEffect(() => {
    scrollToBottom()
  }, [messages.length, scrollToBottom])

  // 加载更多历史消息
  const loadMoreMessages = useCallback(async () => {
    if (!hasMore || isLoadingMore || !oldestTimestamp) return

    setIsLoadingMore(true)

    // 保存当前滚动位置
    if (messagesContainerRef.current) {
      scrollPositionRef.current = messagesContainerRef.current.scrollTop
      scrollHeightRef.current = messagesContainerRef.current.scrollHeight
    }

    try {
      const response = await conversationApi.getMessages({
        limit: 30,
        before: oldestTimestamp
      })

      const localMessages = response.messages.map(convertToLocalMessage)
      prependMessages(localMessages)
      setHasMore(response.has_more)
      setOldestTimestamp(response.oldest_timestamp || null)

      // 恢复滚动位置
      setTimeout(maintainScrollPosition, 50)
    } catch (error) {
      console.error('Failed to load more messages:', error)
    } finally {
      setIsLoadingMore(false)
    }
  }, [hasMore, isLoadingMore, oldestTimestamp, prependMessages, setHasMore, setOldestTimestamp, maintainScrollPosition])

  // 监听滚动事件
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const target = e.target as HTMLDivElement
    if (target.scrollTop < 100 && hasMore && !isLoadingMore) {
      loadMoreMessages()
    }
  }, [hasMore, isLoadingMore, loadMoreMessages])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const trimmedInput = input.trim()
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: trimmedInput,
      timestamp: new Date()
    }

    addMessage(userMessage)
    setInput('')
    setLoading(true)

    // 检测追问模式下的确认/取消关键词
    const confirmKeywords = ['确认', '好的', '行', '可以', '是', '对', 'yes', 'ok']
    const cancelKeywords = ['取消', '不', 'no', '否']

    // 如果有待确认的操作，优先处理
    if (pendingAction) {
      const isConfirm = confirmKeywords.some(kw => trimmedInput.toLowerCase().includes(kw.toLowerCase()))
      const isCancel = cancelKeywords.some(kw => trimmedInput.toLowerCase().includes(kw.toLowerCase()))

      if (isCancel) {
        // 取消操作
        addMessage({
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: '操作已取消。',
          timestamp: new Date()
        })
        setPendingAction(null)
        setFollowUpInfo(null)
        setFormValues({})
        setLoading(false)
        return
      }

      if (isConfirm) {
        // 确认操作：执行待确认的操作
        try {
          const result = await aiApi.execute(pendingAction, true)
          addMessage({
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: result.message || '操作已完成',
            timestamp: new Date(),
            query_result: result.query_result
          })
          setPendingAction(null)
          setFollowUpInfo(null)
          setFormValues({})
        } catch {
          addMessage({
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: '操作执行失败，请稍后重试。',
            timestamp: new Date()
          })
        }
        setLoading(false)
        return
      }
    }

    // 如果在追问模式且用户输入了确认/取消关键词
    if (followUpInfo) {
      const isCancel = cancelKeywords.some(kw => trimmedInput.toLowerCase().includes(kw.toLowerCase()))

      if (isCancel) {
        // 取消操作
        addMessage({
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: '操作已取消。',
          timestamp: new Date()
        })
        setFollowUpInfo(null)
        setFormValues({})
        setLoading(false)
        return
      }

      if (confirmKeywords.some(kw => trimmedInput.toLowerCase().includes(kw.toLowerCase()))) {
        // 确认操作：使用表单提交逻辑
        await handleFormSubmit()
        return
      }
    }

    // 构建追问上下文（如果在追问模式）
    let followUpContext: Record<string, unknown> | undefined = undefined
    if (followUpInfo) {
      followUpContext = {
        action_type: followUpInfo.action_type,
        collected_fields: followUpInfo.collected_fields
      }
    }

    try {
      const response = await aiApi.chat(
        trimmedInput,
        currentTopicId || undefined,
        followUpContext,
        language
      )

      console.log('DEBUG chat response:', {
        message: response.message,
        suggested_actions: response.suggested_actions,
        follow_up: response.follow_up,
        has_action_with_confirmation: response.suggested_actions?.[0]?.requires_confirmation,
        action_missing_fields: response.suggested_actions?.[0]?.missing_fields
      })

      const aiMessage: ChatMessage = {
        id: response.message_id || (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
        actions: response.suggested_actions,
        query_result: response.query_result,
        context: {
          topic_id: response.topic_id,
          // 保存追问上下文用于下次请求
          ...(response.follow_up ? {
            follow_up: response.follow_up,
            action_type: response.follow_up.action_type,
            collected_fields: response.follow_up.collected_fields
          } : {})
        }
      }

      // 更新当前 topic_id
      if (response.topic_id) {
        setCurrentTopicId(response.topic_id)
      }

      // 处理需要确认且有候选项的响应
      if (response.requires_confirmation && response.candidates && response.candidates.length > 0) {
        aiMessage.actions = aiMessage.actions?.map(action => ({
          ...action,
          candidates: response.candidates
        }))
      }

      // 处理追问模式
      if (response.follow_up && response.suggested_actions?.[0]?.missing_fields) {
        setFollowUpInfo(response.follow_up)
        setFormValues(response.follow_up.collected_fields as Record<string, string> || {})
        setShowForm(true)
      } else if (response.suggested_actions?.[0]?.requires_confirmation &&
                 (!response.suggested_actions[0].missing_fields || response.suggested_actions[0].missing_fields.length === 0)) {
        // 信息完整的确认操作，设置待确认操作
        setPendingAction(response.suggested_actions[0])
        setFollowUpInfo(null)
        setFormValues({})
      } else {
        // 其他情况清空追问状态
        setFollowUpInfo(null)
        setFormValues({})
      }

      addMessage(aiMessage)
    } catch {
      addMessage({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，处理请求时出现错误，请稍后重试。',
        timestamp: new Date()
      })
    } finally {
      setLoading(false)
    }
  }

  // 处理表单提交
  const handleFormSubmit = async () => {
    if (!followUpInfo) return

    // 合并已收集的字段和新填写的字段
    const allFields = { ...followUpInfo.collected_fields, ...formValues }
    const missingFields = followUpInfo.missing_fields.filter(
      f => !allFields[f.field_name] || !String(allFields[f.field_name]).trim()
    )

    console.log('DEBUG handleFormSubmit:', {
      followUpInfo,
      formValues,
      allFields,
      missingFields: missingFields.length,
      missingFieldNames: missingFields.map(f => f.field_name)
    })

    if (missingFields.length > 0) {
      // 还有未填写的字段，继续追问
      const response = await aiApi.chat(
        JSON.stringify(allFields),
        currentTopicId || undefined,
        {
          action_type: followUpInfo.action_type,
          collected_fields: allFields
        },
        language
      )

      const aiMessage: ChatMessage = {
        id: response.message_id || (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
        actions: response.suggested_actions,
        context: {
          topic_id: response.topic_id,
          ...(response.follow_up ? {
            follow_up: response.follow_up,
            action_type: response.follow_up.action_type,
            collected_fields: response.follow_up.collected_fields
          } : {})
        }
      }

      if (response.topic_id) {
        setCurrentTopicId(response.topic_id)
      }

      // 检查是否还有追问
      if (response.follow_up && response.suggested_actions?.[0]?.missing_fields) {
        setFollowUpInfo(response.follow_up)
        setFormValues(response.follow_up.collected_fields as Record<string, string> || {})
        setShowForm(true)
      } else if (response.suggested_actions?.[0]?.requires_confirmation &&
                 (!response.suggested_actions[0].missing_fields || response.suggested_actions[0].missing_fields.length === 0)) {
        // 信息完整，需要确认（自然语言回复导致）
        setPendingAction(response.suggested_actions[0])
        setFollowUpInfo(null)
        setFormValues({})
      } else {
        setFollowUpInfo(null)
        setFormValues({})
      }

      addMessage(aiMessage)
      setLoading(false)
      return
    }

    // 信息完整，表单提交 → 直接执行操作（无需再确认）
    const action: AIAction = {
      action_type: followUpInfo.action_type,
      entity_type: followUpInfo.action_type === 'create_reservation' ? 'reservation' : 'stay_record',
      params: allFields,
      description: buildActionDescription(followUpInfo.action_type, allFields),
      requires_confirmation: false  // 表单提交无需确认
    }

    setLoading(true)
    try {
      const result = await aiApi.execute(action, true)

      // 检查操作是否成功
      if (result.success === false) {
        addMessage({
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: result.message || '操作执行失败，请稍后重试。',
          timestamp: new Date()
        })
      } else {
        addMessage({
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: result.message || '操作已完成',
          timestamp: new Date(),
          query_result: result.query_result
        })
      }

      // 清空追问状态
      setFollowUpInfo(null)
      setFormValues({})
    } catch (error) {
      addMessage({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `操作失败: ${error instanceof Error ? error.message : '请稍后重试'}`,
        timestamp: new Date()
      })
    } finally {
      setLoading(false)
    }
  }

  // 构建确认消息
  const buildConfirmMessage = (_actionType: string, params: Record<string, unknown>): string => {
    // Build display names from kinetic schema, with fallbacks
    const schema = useOntologyStore.getState().getActionSchema(_actionType)
    const kineticNames = schema
      ? Object.fromEntries(schema.params.map(p => [p.name, p.description || p.name]))
      : {}
    const fieldDisplayNames: Record<string, string> = {
      guest_name: '客人',
      guest_phone: '电话',
      room_number: '房间号',
      room_type: '房型',
      check_in_date: '入住日期',
      check_out_date: '离店日期',
      expected_check_out: '预计退房',
      reservation_id: '预订号',
      stay_record_id: '住宿记录',
      task_type: '任务类型',
      ...kineticNames,
    }

    let message = '信息已完整：\n\n'
    for (const [key, value] of Object.entries(params)) {
      if (value) {
        const name = fieldDisplayNames[key] || key
        message += `- ${name}：${value}\n`
      }
    }
    message += '\n确认办理吗？'

    return message
  }

  // 构建操作描述
  const buildActionDescription = (actionType: string, params: Record<string, unknown>): string => {
    // Try kinetic schema description first
    const schema = useOntologyStore.getState().getActionSchema(actionType)
    if (schema?.description) return schema.description

    const descriptions: Record<string, string> = {
      walkin_checkin: `为 ${params.guest_name} 办理散客入住（${params.room_number}号房）`,
      create_reservation: `创建 ${params.guest_name} 的预订（${params.room_type}）`,
      checkin: `办理预订入住（${params.room_number}号房）`,
      checkout: `办理退房`,
      extend_stay: `为客人续住`,
      change_room: `为客人换房`,
      create_task: `创建清洁任务（${params.room_number}号房）`,
    }
    return descriptions[actionType] || actionType
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleAction = async (action: AIAction, confirmed: boolean, selectedCandidate?: CandidateOption) => {
    // 清空追问状态（操作结束）
    setFollowUpInfo(null)
    setFormValues({})

    if (!confirmed) {
      setPendingAction(null)
      addMessage({
        id: Date.now().toString(),
        role: 'assistant',
        content: '操作已取消。',
        timestamp: new Date()
      })
      return
    }

    // 如果有选择的候选项，将其添加到参数中
    let finalAction = { ...action }
    if (selectedCandidate) {
      if (action.action_type === 'create_reservation') {
        finalAction.params = {
          ...action.params,
          room_type_id: selectedCandidate.id
        }
      } else if (action.action_type === 'walkin_checkin' || action.action_type === 'checkin' || action.action_type === 'create_task' || action.action_type === 'update_room_status') {
        finalAction.params = {
          ...action.params,
          room_id: selectedCandidate.id
        }
      } else if (action.action_type === 'assign_task') {
        finalAction.params = {
          ...action.params,
          assignee_id: selectedCandidate.id
        }
      }
    }

    setLoading(true)
    try {
      const result = await aiApi.execute(finalAction, true)
      // 检查操作是否成功
      if (result.success === false) {
        addMessage({
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: result.message || '操作执行失败，请稍后重试。',
          timestamp: new Date()
        })
      } else {
        addMessage({
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: result.message || '操作已完成。',
          timestamp: new Date(),
          query_result: result.query_result
        })
      }
      setPendingAction(null)
    } catch (error) {
      addMessage({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `操作执行失败: ${error instanceof Error ? error.message : '请稍后重试'}`,
        timestamp: new Date()
      })
      setPendingAction(null)
    } finally {
      setLoading(false)
    }
  }

  // 处理候选项选择
  const handleSelectCandidate = (candidate: CandidateOption) => {
    if (pendingAction) {
      handleAction(pendingAction, true, candidate)
    }
  }

  // 搜索功能
  const handleSearch = async () => {
    if (!searchInput.trim() && !selectedDate) return

    setIsSearching(true)
    try {
      if (searchInput.trim()) {
        // 关键词搜索（可带日期范围）
        const response = await conversationApi.search({
          keyword: searchInput.trim(),
          start_date: selectedDate || undefined,
          end_date: selectedDate || undefined,
          limit: 50
        })
        setSearchResults(response.messages)
      } else if (selectedDate) {
        // 仅按日期加载
        const messages = await conversationApi.getMessagesByDate(selectedDate)
        setSearchResults(messages)
      }
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setIsSearching(false)
    }
  }

  // 加载可用日期列表
  const loadAvailableDates = async () => {
    try {
      const response = await conversationApi.getAvailableDates()
      setAvailableDates(response.dates)
    } catch (error) {
      console.error('Failed to load dates:', error)
    }
  }

  // 展开搜索时加载可用日期
  useEffect(() => {
    if (showSearch) {
      loadAvailableDates()
    }
  }, [showSearch])

  const handleSearchKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  // 按日期分组的消息
  const groupedMessages = groupMessagesByDate(messages)

  return (
    <div className="h-full flex flex-col">
      {/* 搜索栏 */}
      {showSearch && (
        <div className="p-3 border-b border-dark-800 bg-dark-900">
          <div className="flex gap-2">
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyPress={handleSearchKeyPress}
              placeholder="搜索聊天记录..."
              className="flex-1 bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
            />
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="bg-dark-800 border border-dark-700 rounded-lg px-2 py-2 text-sm focus:outline-none focus:border-primary-500"
            />
            <button
              onClick={handleSearch}
              disabled={isSearching || (!searchInput.trim() && !selectedDate)}
              className="px-3 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              {isSearching ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            </button>
            <button
              onClick={() => { setShowSearch(false); clearSearch(); setSelectedDate(''); setAvailableDates([]) }}
              className="px-3 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* 可用日期快捷选择 */}
          {availableDates.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {availableDates.slice(0, 10).map(d => (
                <button
                  key={d}
                  onClick={() => { setSelectedDate(d); }}
                  className={`text-xs px-2 py-1 rounded-full transition-colors ${
                    selectedDate === d
                      ? 'bg-primary-600 text-white'
                      : 'bg-dark-800 text-dark-400 hover:bg-dark-700'
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          )}

          {/* 搜索结果 */}
          {searchResults.length > 0 && (
            <div className="mt-3 max-h-60 overflow-y-auto space-y-2">
              <p className="text-xs text-dark-400">找到 {searchResults.length} 条结果</p>
              {searchResults.map(result => (
                <div key={result.id} className="bg-dark-800 rounded p-2">
                  <div className="text-xs text-dark-500 mb-1">
                    {new Date(result.timestamp).toLocaleString('zh-CN')}
                  </div>
                  <div className="text-sm text-dark-200 line-clamp-2">{result.content}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 消息列表 */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
        onScroll={handleScroll}
      >
        {/* 加载更多指示器 */}
        {isLoadingMore && (
          <div className="flex justify-center py-2">
            <Loader2 size={16} className="animate-spin text-dark-500" />
          </div>
        )}

        {/* 加载更多按钮 */}
        {hasMore && !isLoadingMore && (
          <div className="flex justify-center">
            <button
              onClick={loadMoreMessages}
              className="flex items-center gap-1 text-xs text-dark-500 hover:text-dark-300 transition-colors"
            >
              <ChevronUp size={14} />
              <span>加载更早消息</span>
            </button>
          </div>
        )}

        {messages.length === 0 && !isLoading && (
          <div className="text-center text-dark-500 py-8">
            <p className="text-sm">您好，我是酒店智能助手</p>
            <p className="text-xs mt-2">试试说"查看房态"或"帮王五退房"</p>
          </div>
        )}

        {/* 按日期分组显示消息 */}
        {Array.from(groupedMessages.entries()).map(([dateKey, dateMessages]) => (
          <div key={dateKey}>
            <DateSeparator date={dateKey} />
            {dateMessages.map(msg => {
              const isSystemCmd = msg.role === 'user' && msg.content.trim().startsWith('#') && msg.content.trim().length > 1 && !/^#\d/.test(msg.content.trim())
              const isSystemResponse = msg.role === 'assistant' && (msg.context as any)?.type === 'system_command'
              return (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} mb-4`}>
                <div className={`chat-bubble ${
                  isSystemCmd ? 'bg-indigo-900/40 border border-indigo-700/50 rounded-lg px-3 py-2 max-w-[80%]' :
                  isSystemResponse ? 'bg-indigo-950/30 border border-indigo-800/30 rounded-lg px-3 py-2 max-w-[80%]' :
                  msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai'
                }`}>
                  {isSystemCmd && (
                    <span className="inline-block text-[10px] bg-indigo-700/50 text-indigo-300 px-1.5 py-0.5 rounded mb-1">
                      系统指令
                    </span>
                  )}
                  {isSystemResponse && (
                    <span className="inline-block text-[10px] bg-indigo-800/40 text-indigo-400 px-1.5 py-0.5 rounded mb-1">
                      系统响应
                    </span>
                  )}
                  <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
                  {msg.query_result && <QueryResultDisplay result={msg.query_result} />}

                  {/* 建议动作 */}
                  {msg.actions && msg.actions.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {msg.actions.map((action, idx) => (
                        <div key={idx} className="bg-dark-700 rounded-lg p-2">
                          <p className="text-xs text-dark-300 mb-2">{action.description}</p>

                          {/* 显示缺失字段表单 */}
                          {action.missing_fields && action.missing_fields.length > 0 && (
                            <ActionForm
                              action={action}
                              formValues={formValues}
                              showForm={showForm}
                              onToggleForm={() => setShowForm(!showForm)}
                              onChange={setFormValues}
                              onSubmit={handleFormSubmit}
                            />
                          )}

                          {/* 显示候选项 */}
                          {action.candidates && action.candidates.length > 0 && pendingAction?.action_type === action.action_type ? (
                            <div className="mb-2 p-2 bg-dark-800 rounded">
                              <p className="text-xs text-dark-400 mb-1">请选择：</p>
                              {action.candidates.map((candidate, cIdx) => (
                                <button
                                  key={cIdx}
                                  onClick={() => handleSelectCandidate(candidate)}
                                  className="block w-full text-left px-2 py-1 bg-dark-700 hover:bg-dark-600 rounded text-xs mb-1 last:mb-0"
                                >
                                  {candidate.name}
                                  {candidate.room_number && ` (${candidate.room_number}号)`}
                                  {candidate.price && ` - ¥${candidate.price}`}
                                </button>
                              ))}
                            </div>
                          ) : null}

                          {action.requires_confirmation && (!action.missing_fields || action.missing_fields.length === 0) && (
                            <div className="flex gap-2">
                              <button
                                onClick={() => followUpInfo ? handleFormSubmit() : handleAction(action, true)}
                                className="flex items-center gap-1 px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs"
                              >
                                <Check size={12} /> 提交
                              </button>
                              <button
                                onClick={() => {
                                  setFollowUpInfo(null)
                                  setFormValues({})
                                  handleAction(action, false)
                                }}
                                className="flex items-center gap-1 px-2 py-1 bg-dark-600 hover:bg-dark-500 rounded text-xs"
                              >
                                <X size={12} /> 取消
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 时间戳 */}
                  <div className="text-xs text-dark-500 mt-1">
                    {msg.timestamp.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>
            )})}
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="chat-bubble chat-bubble-ai flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" />
              <span className="text-sm">思考中...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入框 */}
      <div className="p-4 border-t border-dark-800">
        <div className="flex gap-2">
          <button
            onClick={() => setShowSearch(!showSearch)}
            className={`px-3 py-2 rounded-lg transition-colors ${
              showSearch
                ? 'bg-primary-600 hover:bg-primary-700'
                : 'bg-dark-700 hover:bg-dark-600'
            }`}
            title="搜索历史"
          >
            <Search size={18} />
          </button>
          <button
            onClick={() => {
              // 循环: null(自动) → zh → en → null(自动)
              const next = language === null ? 'zh' : language === 'zh' ? 'en' : null
              setLanguage(next)
            }}
            className="px-3 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg transition-colors text-xs font-medium flex items-center gap-1"
            title={`语言: ${language === null ? '自动' : language === 'zh' ? '中文' : 'EN'}`}
          >
            <Globe size={14} />
            <span>{language === null ? getChatText('lang_auto', language) : language === 'zh' ? getChatText('lang_zh', language) : getChatText('lang_en', language)}</span>
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={getChatText('input_placeholder', language)}
            className="flex-1 bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="px-3 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  )
}
