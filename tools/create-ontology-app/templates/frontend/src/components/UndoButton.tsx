/**
 * 撤销按钮组件
 * 显示可撤销的操作列表，支持执行撤销
 */
import React, { useState, useEffect, useRef } from 'react'
import { Undo2, Clock, AlertCircle, Check, ChevronDown } from 'lucide-react'
import { undoApi, OperationSnapshot } from '../services/api'

// 操作类型的中文映射
const operationTypeLabels: Record<string, string> = {
  check_in: '入住',
  check_out: '退房',
  extend_stay: '续住',
  change_room: '换房',
  complete_task: '完成任务',
  add_payment: '添加支付',
  create_reservation: '创建预订',
  cancel_reservation: '取消预订',
  assign_task: '分配任务'
}

// 实体类型的中文映射
const entityTypeLabels: Record<string, string> = {
  stay_record: '住宿记录',
  reservation: '预订',
  task: '任务',
  payment: '支付',
  room: '房间'
}

interface UndoButtonProps {
  /** 筛选特定实体类型 */
  entityType?: string
  /** 筛选特定实体ID */
  entityId?: number
  /** 撤销成功后的回调 */
  onUndoSuccess?: () => void
  /** 按钮样式变体 */
  variant?: 'default' | 'compact'
}

export const UndoButton: React.FC<UndoButtonProps> = ({
  entityType,
  entityId,
  onUndoSuccess,
  variant = 'default'
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [operations, setOperations] = useState<OperationSnapshot[]>([])
  const [loading, setLoading] = useState(false)
  const [undoing, setUndoing] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // 加载可撤销的操作
  const loadOperations = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await undoApi.getOperations({
        entity_type: entityType,
        entity_id: entityId,
        limit: 10
      })
      setOperations(data)
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  // 执行撤销
  const handleUndo = async (snapshotUuid: string) => {
    setUndoing(snapshotUuid)
    setError(null)
    try {
      const result = await undoApi.undo(snapshotUuid)
      if (result.success) {
        setSuccess(result.message)
        setTimeout(() => setSuccess(null), 2000)
        // 重新加载列表
        await loadOperations()
        // 触发回调
        onUndoSuccess?.()
      } else {
        setError(result.message)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '撤销失败')
    } finally {
      setUndoing(null)
    }
  }

  // 点击外部关闭下拉菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // 打开时加载数据
  useEffect(() => {
    if (isOpen) {
      loadOperations()
    }
  }, [isOpen, entityType, entityId])

  // 格式化时间
  const formatTime = (isoString: string) => {
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return '刚刚'
    if (diffMins < 60) return `${diffMins}分钟前`

    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}小时前`

    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // 检查是否过期
  const isExpired = (expiresAt: string) => {
    return new Date(expiresAt) < new Date()
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* 触发按钮 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          flex items-center gap-1.5 rounded-lg transition-colors
          ${variant === 'compact'
            ? 'px-2 py-1 text-sm bg-dark-800 hover:bg-dark-700 text-dark-300 hover:text-white'
            : 'px-3 py-2 bg-dark-800 hover:bg-dark-700 text-dark-300 hover:text-white border border-dark-700'
          }
        `}
        title="撤销操作"
      >
        <Undo2 className="w-4 h-4" />
        {variant === 'default' && (
          <>
            <span>撤销</span>
            <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
          </>
        )}
      </button>

      {/* 下拉菜单 */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-dark-900 border border-dark-700 rounded-lg shadow-xl z-50">
          {/* 标题 */}
          <div className="px-4 py-3 border-b border-dark-700">
            <h3 className="text-sm font-medium text-white">可撤销的操作</h3>
            <p className="text-xs text-dark-400 mt-0.5">24小时内的操作可撤销</p>
          </div>

          {/* 内容 */}
          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <div className="px-4 py-6 text-center text-dark-400">
                <div className="animate-spin w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full mx-auto" />
                <p className="mt-2 text-sm">加载中...</p>
              </div>
            ) : error && operations.length === 0 ? (
              <div className="px-4 py-6 text-center">
                <AlertCircle className="w-8 h-8 text-red-400 mx-auto" />
                <p className="mt-2 text-sm text-red-400">{error}</p>
              </div>
            ) : operations.length === 0 ? (
              <div className="px-4 py-6 text-center text-dark-400">
                <Clock className="w-8 h-8 mx-auto opacity-50" />
                <p className="mt-2 text-sm">暂无可撤销的操作</p>
              </div>
            ) : (
              <ul className="py-1">
                {operations.map((op) => {
                  const expired = isExpired(op.expires_at)
                  const isUndoing = undoing === op.snapshot_uuid

                  return (
                    <li
                      key={op.snapshot_uuid}
                      className={`px-4 py-3 hover:bg-dark-800 border-b border-dark-800 last:border-0 ${
                        expired ? 'opacity-50' : ''
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white font-medium">
                            {operationTypeLabels[op.operation_type] || op.operation_type}
                          </p>
                          <p className="text-xs text-dark-400 mt-0.5">
                            {entityTypeLabels[op.entity_type] || op.entity_type} #{op.entity_id}
                          </p>
                          <p className="text-xs text-dark-500 mt-1">
                            {formatTime(op.operation_time)}
                          </p>
                        </div>
                        <button
                          onClick={() => handleUndo(op.snapshot_uuid)}
                          disabled={expired || isUndoing}
                          className={`
                            px-3 py-1.5 rounded text-xs font-medium transition-colors
                            ${expired
                              ? 'bg-dark-700 text-dark-500 cursor-not-allowed'
                              : isUndoing
                                ? 'bg-primary-500/20 text-primary-400'
                                : 'bg-primary-500/20 text-primary-400 hover:bg-primary-500/30'
                            }
                          `}
                        >
                          {isUndoing ? (
                            <span className="flex items-center gap-1">
                              <div className="animate-spin w-3 h-3 border border-primary-400 border-t-transparent rounded-full" />
                              撤销中
                            </span>
                          ) : expired ? (
                            '已过期'
                          ) : (
                            '撤销'
                          )}
                        </button>
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          {/* 成功/错误提示 */}
          {success && (
            <div className="px-4 py-2 bg-green-500/20 border-t border-dark-700">
              <p className="text-xs text-green-400 flex items-center gap-1">
                <Check className="w-3 h-3" />
                {success}
              </p>
            </div>
          )}
          {error && operations.length > 0 && (
            <div className="px-4 py-2 bg-red-500/20 border-t border-dark-700">
              <p className="text-xs text-red-400 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                {error}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default UndoButton
