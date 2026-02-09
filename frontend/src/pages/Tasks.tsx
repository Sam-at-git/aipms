import { useEffect, useState } from 'react'
import { Plus, RefreshCw, Play, CheckCircle, User } from 'lucide-react'
import { taskApi, roomApi } from '../services/api'
import Modal, { ModalFooter } from '../components/Modal'
import { UndoButton } from '../components/UndoButton'
import { useUIStore, useAuthStore, useOntologyStore } from '../store'
import type { Task, Room } from '../types'

const typeLabels: Record<string, string> = {
  cleaning: '清洁',
  maintenance: '维修'
}

export default function Tasks() {
  const { user } = useAuthStore()
  const [tasks, setTasks] = useState<Task[]>([])
  const [cleaners, setCleaners] = useState<{ id: number; name: string }[]>([])
  const [dirtyRooms, setDirtyRooms] = useState<Room[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('')
  const { openModal, closeModal } = useUIStore()
  const { getStatusConfig } = useOntologyStore()

  // 新建任务表单
  const [taskForm, setTaskForm] = useState({
    room_id: 0,
    task_type: 'cleaning',
    assignee_id: 0,
    priority: 1
  })
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadData()
  }, [filter])

  const loadData = async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = {}
      if (filter) params.status = filter

      // 清洁员只看自己的任务
      if (user?.role === 'cleaner') {
        const myTasks = await taskApi.getMyTasks()
        setTasks(myTasks)
      } else {
        const [tasksData, cleanersData, roomsData] = await Promise.all([
          taskApi.getList(params),
          taskApi.getCleaners(),
          roomApi.getRooms({ status: 'vacant_dirty' })
        ])
        setTasks(tasksData)
        setCleaners(cleanersData)
        setDirtyRooms(roomsData)
      }
    } catch (err) {
      console.error('Failed to load tasks:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    if (!taskForm.room_id) return

    setSubmitting(true)
    try {
      await taskApi.create({
        room_id: taskForm.room_id,
        task_type: taskForm.task_type,
        priority: taskForm.priority,
        assignee_id: taskForm.assignee_id || undefined
      })
      closeModal()
      loadData()
      setTaskForm({ room_id: 0, task_type: 'cleaning', assignee_id: 0, priority: 1 })
    } catch (err) {
      console.error('Create task failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleAssign = async (taskId: number, assigneeId: number) => {
    try {
      await taskApi.assign(taskId, assigneeId)
      loadData()
    } catch (err) {
      console.error('Assign failed:', err)
    }
  }

  const handleStart = async (taskId: number) => {
    try {
      await taskApi.start(taskId)
      loadData()
    } catch (err) {
      console.error('Start failed:', err)
    }
  }

  const handleComplete = async (taskId: number) => {
    try {
      await taskApi.complete(taskId)
      loadData()
    } catch (err) {
      console.error('Complete failed:', err)
    }
  }

  const isCleaner = user?.role === 'cleaner'

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{isCleaner ? '我的任务' : '任务管理'}</h1>
        <div className="flex gap-3">
          {!isCleaner && (
            <>
              <button
                onClick={() => openModal('createTask')}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
              >
                <Plus size={18} />
                新建任务
              </button>
              <UndoButton onUndoSuccess={loadData} />
            </>
          )}
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
        </div>
      </div>

      {/* 筛选 */}
      {!isCleaner && (
        <div className="flex gap-2">
          {['', 'pending', 'assigned', 'in_progress', 'completed'].map(status => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                filter === status
                  ? 'bg-primary-600 text-white'
                  : 'bg-dark-800 text-dark-400 hover:bg-dark-700'
              }`}
            >
              {status === '' ? '全部' : getStatusConfig('Task', status).label}
            </button>
          ))}
        </div>
      )}

      {/* 任务列表 */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </div>
      ) : (
        <div className="space-y-3">
          {tasks.map(task => (
            <div key={task.id} className="bg-dark-900 rounded-xl p-4">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-primary-400">{task.room_number}</div>
                    <div className="text-xs text-dark-400">号房</div>
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 rounded text-xs ${getStatusConfig('Task', task.status).class}`}>
                        {getStatusConfig('Task', task.status).label}
                      </span>
                      <span className="text-sm text-dark-400">{typeLabels[task.task_type]}</span>
                      <span className="text-xs text-dark-500">优先级 {task.priority}</span>
                    </div>
                    {task.assignee_name && (
                      <p className="text-sm text-dark-400">
                        <User size={14} className="inline mr-1" />
                        {task.assignee_name}
                      </p>
                    )}
                    {task.notes && (
                      <p className="text-sm text-dark-500 mt-1">{task.notes}</p>
                    )}
                    <p className="text-xs text-dark-500 mt-1">
                      创建于 {new Date(task.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>

                {/* 操作按钮 */}
                <div className="flex gap-2">
                  {/* 待分配：可分配 */}
                  {task.status === 'pending' && !isCleaner && (
                    <select
                      onChange={(e) => handleAssign(task.id, Number(e.target.value))}
                      className="bg-dark-800 border border-dark-700 rounded-lg px-2 py-1 text-sm"
                      defaultValue=""
                    >
                      <option value="" disabled>分配给...</option>
                      {cleaners.map(c => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  )}

                  {/* 已分配：可开始 */}
                  {task.status === 'assigned' && (isCleaner || task.assignee_id === user?.id) && (
                    <button
                      onClick={() => handleStart(task.id)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm transition-colors"
                    >
                      <Play size={14} />
                      开始
                    </button>
                  )}

                  {/* 进行中：可完成 */}
                  {task.status === 'in_progress' && (isCleaner || task.assignee_id === user?.id) && (
                    <button
                      onClick={() => handleComplete(task.id)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-sm transition-colors"
                    >
                      <CheckCircle size={14} />
                      完成
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {tasks.length === 0 && (
            <div className="text-center text-dark-500 py-12">
              暂无任务
            </div>
          )}
        </div>
      )}

      {/* 新建任务弹窗 */}
      <Modal name="createTask" title="新建清洁任务">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">房间 *</label>
            <select
              value={taskForm.room_id}
              onChange={(e) => setTaskForm({ ...taskForm, room_id: Number(e.target.value) })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
            >
              <option value={0}>选择房间</option>
              {dirtyRooms.map(room => (
                <option key={room.id} value={room.id}>{room.room_number}号房 - {room.room_type_name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">任务类型</label>
            <select
              value={taskForm.task_type}
              onChange={(e) => setTaskForm({ ...taskForm, task_type: e.target.value })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
            >
              <option value="cleaning">清洁</option>
              <option value="maintenance">维修</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">分配给</label>
            <select
              value={taskForm.assignee_id}
              onChange={(e) => setTaskForm({ ...taskForm, assignee_id: Number(e.target.value) })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
            >
              <option value={0}>暂不分配</option>
              {cleaners.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">优先级</label>
            <select
              value={taskForm.priority}
              onChange={(e) => setTaskForm({ ...taskForm, priority: Number(e.target.value) })}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
            >
              <option value={1}>普通</option>
              <option value={2}>较高</option>
              <option value={3}>紧急</option>
            </select>
          </div>

          <ModalFooter
            onCancel={closeModal}
            onConfirm={handleCreate}
            confirmText="创建任务"
            loading={submitting}
          />
        </div>
      </Modal>
    </div>
  )
}
