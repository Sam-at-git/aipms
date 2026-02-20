/**
 * BranchSwitcher - branch selector component
 *
 * - sysadmin: show all branches + "All" option
 * - branch staff: show their branch name (read-only)
 * - system management routes: hidden
 */
import { useEffect } from 'react'
import { Building2 } from 'lucide-react'
import { useAuthStore } from '../store'
import { orgApi } from '../services/api'

export function BranchSwitcher() {
  const user = useAuthStore(s => s.user)
  const currentBranchId = useAuthStore(s => s.currentBranchId)
  const availableBranches = useAuthStore(s => s.availableBranches)
  const switchBranch = useAuthStore(s => s.switchBranch)
  const setBranches = useAuthStore(s => s.setBranches)

  // Load available branches on mount
  useEffect(() => {
    if (!user) return
    orgApi.getBranches()
      .then(branches => setBranches(branches))
      .catch(() => {})
  }, [user, setBranches])

  if (!user || availableBranches.length === 0) return null

  // Single branch: show as static label
  if (availableBranches.length === 1 && user.role !== 'sysadmin') {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-dark-400">
        <Building2 size={14} />
        <span>{availableBranches[0].name}</span>
      </div>
    )
  }

  // Multi-branch: dropdown selector (sysadmin or group roles)
  return (
    <div className="px-3 py-1.5">
      <div className="flex items-center gap-1.5 text-xs text-dark-400 mb-1">
        <Building2 size={14} />
        <span>当前分店</span>
      </div>
      <select
        value={currentBranchId ?? ''}
        onChange={(e) => switchBranch(e.target.value ? Number(e.target.value) : null)}
        className="w-full bg-dark-800 border border-dark-700 rounded px-2 py-1 text-sm text-dark-200 focus:outline-none focus:border-primary-500"
      >
        <option value="">全部分店</option>
        {availableBranches.map(b => (
          <option key={b.id} value={b.id}>{b.name}</option>
        ))}
      </select>
    </div>
  )
}
