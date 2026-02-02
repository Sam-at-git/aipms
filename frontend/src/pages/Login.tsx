import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Hotel, Loader2 } from 'lucide-react'
import { useAuthStore } from '../store'
import { authApi } from '../services/api'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const result = await authApi.login(username, password)
      login(result.employee, result.access_token)
      navigate('/')
    } catch (err: unknown) {
      const errorMessage = err instanceof Error
        ? err.message
        : (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '登录失败，请检查用户名和密码'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-dark-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600/20 rounded-full mb-4">
            <Hotel size={32} className="text-primary-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">AIPMS</h1>
          <p className="text-dark-400 mt-2">智能酒店管理系统</p>
        </div>

        {/* 登录表单 */}
        <form onSubmit={handleSubmit} className="bg-dark-900 rounded-xl p-6 space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/50 text-red-400 px-4 py-2 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm text-dark-400 mb-2">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-primary-500"
              placeholder="请输入用户名"
              required
            />
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-2">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-primary-500"
              placeholder="请输入密码"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
          >
            {loading && <Loader2 size={18} className="animate-spin" />}
            {loading ? '登录中...' : '登录'}
          </button>
        </form>

        {/* 提示 */}
        <div className="mt-6 text-center text-sm text-dark-500">
          <p>默认账号：manager / 123456</p>
        </div>
      </div>
    </div>
  )
}
