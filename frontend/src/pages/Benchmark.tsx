import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FlaskConical, Plus, Play, Download, Upload, Trash2, RefreshCw,
  CheckCircle, XCircle, AlertTriangle, Loader2, Filter
} from 'lucide-react'
import { benchmarkApi } from '../services/api'
import type { BenchmarkSuite, BenchmarkRun } from '../types'

export default function Benchmark() {
  const navigate = useNavigate()
  const [suites, setSuites] = useState<BenchmarkSuite[]>([])
  const [runs, setRuns] = useState<Map<number, BenchmarkRun>>(new Map())
  const [loading, setLoading] = useState(true)
  const [executing, setExecuting] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [categories, setCategories] = useState<string[]>([])
  const [showCreateModal, setShowCreateModal] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [suitesData, runsData] = await Promise.all([
        benchmarkApi.listSuites(),
        benchmarkApi.listRuns(),
      ])
      setSuites(suitesData)
      const runsMap = new Map<number, BenchmarkRun>()
      runsData.forEach(r => runsMap.set(r.suite_id, r))
      setRuns(runsMap)

      const cats = [...new Set(suitesData.map(s => s.category))].sort()
      setCategories(cats)
    } catch (err) {
      console.error('Failed to load benchmark data:', err)
    } finally {
      setLoading(false)
    }
  }

  const filteredSuites = categoryFilter
    ? suites.filter(s => s.category === categoryFilter)
    : suites

  const toggleSelect = (id: number) => {
    const next = new Set(selectedIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelectedIds(next)
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredSuites.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredSuites.map(s => s.id)))
    }
  }

  const handleRun = async () => {
    if (selectedIds.size === 0) return
    setExecuting(true)
    try {
      await benchmarkApi.runSuites([...selectedIds])
      await loadData()
    } catch (err) {
      console.error('Benchmark run failed:', err)
    } finally {
      setExecuting(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除此 Suite？')) return
    try {
      await benchmarkApi.deleteSuite(id)
      await loadData()
    } catch (err) {
      console.error('Delete failed:', err)
    }
  }

  const handleExportAll = async () => {
    try {
      const yaml = await benchmarkApi.exportAll()
      const blob = new Blob([yaml], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'benchmark_suites.yaml'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed:', err)
    }
  }

  const handleImport = async () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.yaml,.yml'
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return
      const text = await file.text()
      try {
        const result = await benchmarkApi.importYaml(text)
        alert(`导入完成：${result.created_suites} 个 Suite，${result.created_cases} 个 Case，跳过 ${result.skipped_suites} 个`)
        await loadData()
      } catch (err) {
        console.error('Import failed:', err)
        alert('导入失败')
      }
    }
    input.click()
  }

  const statusIcon = (run?: BenchmarkRun) => {
    if (!run) return <span className="text-dark-500 text-sm">未执行</span>
    if (run.status === 'running') return <Loader2 size={16} className="text-primary-400 animate-spin" />
    if (run.status === 'passed') return <CheckCircle size={16} className="text-emerald-400" />
    if (run.status === 'failed') return <XCircle size={16} className="text-red-400" />
    return <AlertTriangle size={16} className="text-amber-400" />
  }

  const statusBadge = (run?: BenchmarkRun) => {
    if (!run) return null
    const total = run.total_cases
    const passed = run.passed
    const bgColor = run.status === 'passed' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${bgColor}`}>
        {passed}/{total} passed
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="text-primary-400 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FlaskConical size={24} className="text-primary-400" />
          <h1 className="text-2xl font-bold text-dark-100">Benchmark</h1>
          <span className="text-dark-500 text-sm">{suites.length} suites</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg text-sm transition-colors"
          >
            <Plus size={16} />
            New Suite
          </button>
          <button
            onClick={handleImport}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-dark-800 hover:bg-dark-700 text-dark-200 rounded-lg text-sm border border-dark-700 transition-colors"
          >
            <Upload size={16} />
            Import
          </button>
          <button
            onClick={handleExportAll}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-dark-800 hover:bg-dark-700 text-dark-200 rounded-lg text-sm border border-dark-700 transition-colors"
          >
            <Download size={16} />
            Export
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between bg-dark-900 rounded-xl p-4 border border-dark-800">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-dark-400" />
            <select
              value={categoryFilter}
              onChange={e => setCategoryFilter(e.target.value)}
              className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-1.5 text-sm text-dark-200"
            >
              <option value="">All Categories</option>
              {categories.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-dark-400 cursor-pointer">
            <input
              type="checkbox"
              checked={selectedIds.size === filteredSuites.length && filteredSuites.length > 0}
              onChange={toggleSelectAll}
              className="rounded border-dark-600"
            />
            Select All
          </label>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRun}
            disabled={selectedIds.size === 0 || executing}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
          >
            {executing ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            Run Selected ({selectedIds.size})
          </button>
          <button
            onClick={loadData}
            className="p-1.5 text-dark-400 hover:text-dark-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Suite Cards */}
      <div className="grid gap-3">
        {filteredSuites.length === 0 ? (
          <div className="text-center py-12 text-dark-500">
            No suites found. Create one or import from YAML.
          </div>
        ) : (
          filteredSuites.map(suite => {
            const run = runs.get(suite.id)
            return (
              <div
                key={suite.id}
                className="bg-dark-900 rounded-xl p-4 border border-dark-800 hover:border-dark-700 transition-colors"
              >
                <div className="flex items-center gap-4">
                  {/* Checkbox */}
                  <input
                    type="checkbox"
                    checked={selectedIds.has(suite.id)}
                    onChange={() => toggleSelect(suite.id)}
                    className="rounded border-dark-600 flex-shrink-0"
                  />

                  {/* Suite Info */}
                  <div
                    className="flex-1 min-w-0 cursor-pointer"
                    onClick={() => navigate(`/benchmark/suites/${suite.id}`)}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-dark-100">{suite.name}</span>
                      <span className="px-2 py-0.5 bg-dark-800 rounded text-xs text-dark-400">
                        {suite.category}
                      </span>
                      <span className="text-dark-500 text-xs">{suite.case_count} cases</span>
                    </div>
                    {suite.description && (
                      <p className="text-sm text-dark-500 truncate">{suite.description}</p>
                    )}
                    {suite.init_script && (
                      <span className="text-xs text-dark-500">init: {suite.init_script}</span>
                    )}
                  </div>

                  {/* Status */}
                  <div className="flex items-center gap-3 flex-shrink-0">
                    {statusIcon(run)}
                    {statusBadge(run)}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={async () => {
                        setExecuting(true)
                        try {
                          await benchmarkApi.runSuites([suite.id])
                          await loadData()
                        } catch (err) {
                          console.error('Run failed:', err)
                        } finally {
                          setExecuting(false)
                        }
                      }}
                      disabled={executing}
                      className="p-1.5 text-dark-400 hover:text-emerald-400 transition-colors"
                      title="Run"
                    >
                      <Play size={16} />
                    </button>
                    <button
                      onClick={() => handleDelete(suite.id)}
                      className="p-1.5 text-dark-400 hover:text-red-400 transition-colors"
                      title="Delete"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Results Summary */}
      {runs.size > 0 && (
        <div className="bg-dark-900 rounded-xl border border-dark-800 overflow-hidden">
          <div className="px-4 py-3 border-b border-dark-800">
            <h3 className="font-medium text-dark-200">Latest Results</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-dark-400 border-b border-dark-800">
                <th className="text-left px-4 py-2 font-medium">Suite</th>
                <th className="text-center px-4 py-2 font-medium">Total</th>
                <th className="text-center px-4 py-2 font-medium">Passed</th>
                <th className="text-center px-4 py-2 font-medium">Failed</th>
                <th className="text-center px-4 py-2 font-medium">Error</th>
                <th className="text-center px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {suites.filter(s => runs.has(s.id)).map(suite => {
                const run = runs.get(suite.id)!
                return (
                  <tr key={suite.id} className="border-b border-dark-800/50 hover:bg-dark-800/30 cursor-pointer" onClick={() => navigate(`/benchmark/suites/${suite.id}`)}>
                    <td className="px-4 py-2 text-dark-200 hover:text-primary-400">{suite.name}</td>
                    <td className="text-center px-4 py-2 text-dark-300">{run.total_cases}</td>
                    <td className="text-center px-4 py-2 text-emerald-400">{run.passed}</td>
                    <td className="text-center px-4 py-2 text-red-400">{run.failed}</td>
                    <td className="text-center px-4 py-2 text-amber-400">{run.error_count}</td>
                    <td className="text-center px-4 py-2">
                      {statusIcon(run)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Suite Modal */}
      {showCreateModal && (
        <CreateSuiteModal
          onClose={() => setShowCreateModal(false)}
          onCreated={async () => {
            setShowCreateModal(false)
            await loadData()
          }}
        />
      )}
    </div>
  )
}

function CreateSuiteModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [description, setDescription] = useState('')
  const [initScript, setInitScript] = useState('')
  const [initScripts, setInitScripts] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    benchmarkApi.listInitScripts().then(setInitScripts).catch(() => {})
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !category.trim()) return
    setSaving(true)
    try {
      await benchmarkApi.createSuite({
        name: name.trim(),
        category: category.trim(),
        description: description.trim() || undefined,
        init_script: initScript || undefined,
      })
      onCreated()
    } catch (err) {
      console.error('Create suite failed:', err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-dark-900 rounded-xl p-6 w-full max-w-md border border-dark-700" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-dark-100 mb-4">New Suite</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">Name</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200"
              placeholder="e.g. Walk-in Check-in Flow"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Category</label>
            <input
              value={category}
              onChange={e => setCategory(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200"
              placeholder="e.g. Check-in, Query, Reservation"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200 h-20 resize-none"
              placeholder="Optional description"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Init Script
              <span className="text-dark-600 ml-2">DB initialization before running suite</span>
            </label>
            <select
              value={initScript}
              onChange={e => setInitScript(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200 text-sm"
            >
              <option value="">(default - reset business data)</option>
              <option value="none">No initialization</option>
              {initScripts.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-dark-400 hover:text-dark-200 text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || !category.trim() || saving}
              className="px-4 py-2 bg-primary-500 hover:bg-primary-600 disabled:opacity-50 text-white rounded-lg text-sm"
            >
              {saving ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
