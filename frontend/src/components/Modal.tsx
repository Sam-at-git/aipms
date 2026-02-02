import { X } from 'lucide-react'
import { useUIStore } from '../store'

interface ModalProps {
  name: string
  title: string
  children: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl'
}

const sizeClasses = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl'
}

export default function Modal({ name, title, children, size = 'md' }: ModalProps) {
  const { activeModal, closeModal } = useUIStore()

  if (activeModal !== name) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 遮罩 */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={closeModal}
      />

      {/* 弹窗内容 */}
      <div className={`relative bg-dark-900 rounded-xl shadow-xl w-full ${sizeClasses[size]} mx-4 max-h-[90vh] overflow-hidden`}>
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-dark-800">
          <h3 className="text-lg font-medium">{title}</h3>
          <button
            onClick={closeModal}
            className="p-1 hover:bg-dark-800 rounded transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* 内容 */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-4rem)]">
          {children}
        </div>
      </div>
    </div>
  )
}

// 表单按钮组
export function ModalFooter({ onCancel, onConfirm, confirmText = '确认', loading = false }: {
  onCancel: () => void
  onConfirm: () => void
  confirmText?: string
  loading?: boolean
}) {
  return (
    <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-dark-800">
      <button
        onClick={onCancel}
        className="px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
      >
        取消
      </button>
      <button
        onClick={onConfirm}
        disabled={loading}
        className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-lg transition-colors"
      >
        {loading ? '处理中...' : confirmText}
      </button>
    </div>
  )
}
