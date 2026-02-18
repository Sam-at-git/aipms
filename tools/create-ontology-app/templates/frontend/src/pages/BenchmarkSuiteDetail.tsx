import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft, Plus, Play, Trash2, Save, X, GripVertical, Loader2,
  CheckCircle, XCircle, AlertTriangle, Sparkles, ExternalLink, ChevronDown, ChevronRight,
  Settings
} from 'lucide-react'
import { benchmarkApi } from '../services/api'
import type { BenchmarkSuiteDetail as SuiteDetailType, BenchmarkCase, BenchmarkRunDetail, BenchmarkCaseResult } from '../types'

export default function BenchmarkSuiteDetail() {
  const { suiteId } = useParams<{ suiteId: string }>()
  const navigate = useNavigate()
  const [suite, setSuite] = useState<SuiteDetailType | null>(null)
  const [runDetail, setRunDetail] = useState<BenchmarkRunDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [executing, setExecuting] = useState(false)
  const [editingCase, setEditingCase] = useState<number | null>(null) // case id being edited, -1 for new
  const [editingSuite, setEditingSuite] = useState(false)
  const [expandedResult, setExpandedResult] = useState<number | null>(null) // case_id

  useEffect(() => {
    if (suiteId) loadData()
  }, [suiteId])

  const loadData = async () => {
    setLoading(true)
    try {
      const [suiteData, runData] = await Promise.allSettled([
        benchmarkApi.getSuite(Number(suiteId)),
        benchmarkApi.getRunDetail(Number(suiteId)),
      ])
      if (suiteData.status === 'fulfilled') setSuite(suiteData.value)
      if (runData.status === 'fulfilled') setRunDetail(runData.value)
      else setRunDetail(null)
    } catch (err) {
      console.error('Failed to load suite:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleRun = async () => {
    if (!suite) return
    setExecuting(true)
    try {
      await benchmarkApi.runSuites([suite.id])
      await loadData()
    } catch (err) {
      console.error('Run failed:', err)
    } finally {
      setExecuting(false)
    }
  }

  const handleDeleteCase = async (caseId: number) => {
    if (!confirm('Delete this case?')) return
    try {
      await benchmarkApi.deleteCase(caseId)
      await loadData()
    } catch (err) {
      console.error('Delete case failed:', err)
    }
  }

  const getCaseResult = (caseId: number): BenchmarkCaseResult | undefined => {
    return runDetail?.case_results.find(r => r.case_id === caseId)
  }

  const statusIcon = (status?: string) => {
    if (!status) return null
    if (status === 'passed') return <CheckCircle size={16} className="text-emerald-400" />
    if (status === 'failed') return <XCircle size={16} className="text-red-400" />
    if (status === 'error') return <AlertTriangle size={16} className="text-amber-400" />
    return null
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="text-primary-400 animate-spin" />
      </div>
    )
  }

  if (!suite) {
    return (
      <div className="text-center py-12 text-dark-500">
        Suite not found. <Link to="/benchmark" className="text-primary-400 hover:underline">Back to list</Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/benchmark')} className="p-1 text-dark-400 hover:text-dark-200">
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1 className="text-xl font-bold text-dark-100">{suite.name}</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="px-2 py-0.5 bg-dark-800 rounded text-xs text-dark-400">{suite.category}</span>
              {suite.init_script && <span className="px-2 py-0.5 bg-dark-800 rounded text-xs text-dark-500">init: {suite.init_script}</span>}
              {suite.description && <span className="text-sm text-dark-500">{suite.description}</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setEditingSuite(true)}
            className="p-1.5 text-dark-400 hover:text-dark-200 transition-colors"
            title="Edit Suite Settings"
          >
            <Settings size={18} />
          </button>
          <button
            onClick={handleRun}
            disabled={executing || suite.cases.length === 0}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {executing ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            Run Suite
          </button>
          <button
            onClick={() => setEditingCase(-1)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg text-sm transition-colors"
          >
            <Plus size={16} />
            Add Case
          </button>
        </div>
      </div>

      {/* Cases List */}
      <div className="space-y-2">
        <h2 className="text-sm font-medium text-dark-400 uppercase tracking-wider">
          Cases ({suite.cases.length})
        </h2>

        {suite.cases.length === 0 && editingCase !== -1 ? (
          <div className="text-center py-8 text-dark-500 bg-dark-900 rounded-xl border border-dark-800">
            No cases yet. Click "Add Case" to create one.
          </div>
        ) : (
          suite.cases.map((c) => {
            const result = getCaseResult(c.id)
            const isExpanded = expandedResult === c.id

            return (
              <div key={c.id} className="bg-dark-900 rounded-xl border border-dark-800">
                {/* Case Header */}
                <div className="flex items-center gap-3 p-3">
                  <GripVertical size={16} className="text-dark-600 flex-shrink-0" />
                  <span className="text-dark-500 text-sm w-6 text-center flex-shrink-0">
                    {c.sequence_order}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-dark-200">{c.name}</span>
                      {c.run_as && (
                        <span className="px-1.5 py-0.5 bg-dark-800 rounded text-xs text-dark-400">@{c.run_as}</span>
                      )}
                      {statusIcon(result?.status)}
                    </div>
                    <p className="text-sm text-dark-500 truncate mt-0.5">{c.input}</p>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {result && (
                      <button
                        onClick={() => setExpandedResult(isExpanded ? null : c.id)}
                        className="p-1 text-dark-400 hover:text-dark-200 transition-colors"
                        title="Toggle result details"
                      >
                        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      </button>
                    )}
                    <button
                      onClick={() => setEditingCase(c.id)}
                      className="p-1 text-dark-400 hover:text-primary-400 transition-colors text-xs"
                      title="Edit"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDeleteCase(c.id)}
                      className="p-1 text-dark-400 hover:text-red-400 transition-colors"
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {/* Expanded Result Details */}
                {isExpanded && result && (
                  <CaseResultDetail result={result} />
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Suite Editor Modal */}
      {editingSuite && suite && (
        <SuiteEditorModal
          suite={suite}
          onClose={() => setEditingSuite(false)}
          onSaved={async () => {
            setEditingSuite(false)
            await loadData()
          }}
        />
      )}

      {/* Case Editor Modal */}
      {editingCase !== null && (
        <CaseEditorModal
          suiteId={suite.id}
          caseId={editingCase === -1 ? undefined : editingCase}
          existingCase={editingCase === -1 ? undefined : suite.cases.find(c => c.id === editingCase)}
          onClose={() => setEditingCase(null)}
          onSaved={async () => {
            setEditingCase(null)
            await loadData()
          }}
        />
      )}
    </div>
  )
}

function AssertionResultRow({ item }: { item: any }) {
  return (
    <div className="flex items-start gap-2 text-sm">
      {item.passed
        ? <CheckCircle size={14} className="text-emerald-400 mt-0.5 flex-shrink-0" />
        : <XCircle size={14} className="text-red-400 mt-0.5 flex-shrink-0" />}
      <div className="min-w-0">
        <span className="text-dark-300">{item.description}</span>
        {!item.passed && (
          <div className="text-xs text-dark-500 mt-0.5">
            Expected: {typeof item.expected === 'object' ? JSON.stringify(item.expected) : String(item.expected)}
            {' | '}Actual: {typeof item.actual === 'object' ? JSON.stringify(item.actual) : String(item.actual)}
          </div>
        )}
      </div>
    </div>
  )
}

function AssertionSection({ title, items }: { title: string; items: any[] }) {
  if (!items || items.length === 0) return null
  return (
    <div>
      <h4 className="text-xs font-medium text-dark-400 mb-1 uppercase">{title}</h4>
      <div className="space-y-1">
        {items.map((item: any, i: number) => (
          <AssertionResultRow key={i} item={item} />
        ))}
      </div>
    </div>
  )
}

function CaseResultDetail({ result }: { result: BenchmarkCaseResult }) {
  let assertionDetails: any = null
  try {
    assertionDetails = result.assertion_details ? JSON.parse(result.assertion_details) : null
  } catch {}

  return (
    <div className="border-t border-dark-800 p-4 space-y-3 bg-dark-800/30">
      {/* Response */}
      {result.actual_response && (
        <div>
          <h4 className="text-xs font-medium text-dark-400 mb-1 uppercase">Response</h4>
          <p className="text-sm text-dark-300 bg-dark-800 rounded p-2">{result.actual_response}</p>
        </div>
      )}

      {/* Error */}
      {result.error_message && (
        <div>
          <h4 className="text-xs font-medium text-red-400 mb-1 uppercase">Error</h4>
          <p className="text-sm text-red-300 bg-red-900/20 rounded p-2">{result.error_message}</p>
        </div>
      )}

      {/* L2 Action Assertions */}
      <AssertionSection title="Action Assertions (L2)" items={assertionDetails?.l2_action} />

      {/* L3 DB Assertions */}
      <AssertionSection title="DB Assertions (L3)" items={assertionDetails?.verify_db} />

      {/* L4 Response Assertions */}
      <AssertionSection title="Response Assertions (L4)" items={assertionDetails?.response} />

      {/* Query Result Assertions */}
      <AssertionSection title="Query Result Assertions" items={assertionDetails?.query} />

      {/* Execution Result Assertions */}
      <AssertionSection title="Execution Result Assertions" items={assertionDetails?.exec_result} />

      {/* Legacy format fallback: response_contains (old runner format) */}
      {assertionDetails?.response_contains?.checks && (
        <div>
          <h4 className="text-xs font-medium text-dark-400 mb-1 uppercase">Response Assertions (L4)</h4>
          <div className="flex flex-wrap gap-1">
            {assertionDetails.response_contains.checks.map((c: any, i: number) => (
              <span key={i} className={`px-2 py-0.5 rounded text-xs ${c.found ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                {c.keyword} {c.found ? '✓' : '✗'}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Debug Session Link */}
      {result.debug_session_id && (
        <Link
          to={`/debug/sessions/${result.debug_session_id}`}
          className="inline-flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300"
        >
          <ExternalLink size={12} />
          View Debug Session
        </Link>
      )}
    </div>
  )
}

function SuiteEditorModal({
  suite,
  onClose,
  onSaved,
}: {
  suite: SuiteDetailType
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState(suite.name)
  const [category, setCategory] = useState(suite.category)
  const [description, setDescription] = useState(suite.description || '')
  const [initScript, setInitScript] = useState(suite.init_script || '')
  const [initScripts, setInitScripts] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    benchmarkApi.listInitScripts().then(setInitScripts).catch(() => {})
  }, [])

  const handleSave = async () => {
    if (!name.trim() || !category.trim()) return
    setSaving(true)
    try {
      await benchmarkApi.updateSuite(suite.id, {
        name: name.trim(),
        category: category.trim(),
        description: description.trim() || undefined,
        init_script: initScript || undefined,
      })
      onSaved()
    } catch (err) {
      console.error('Update suite failed:', err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-dark-900 rounded-xl p-6 w-full max-w-md border border-dark-700" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-dark-100">Edit Suite</h2>
          <button onClick={onClose} className="text-dark-400 hover:text-dark-200"><X size={20} /></button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">Name</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Category</label>
            <input
              value={category}
              onChange={e => setCategory(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200 h-20 resize-none"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Init Script
              <span className="text-dark-600 ml-2">DB initialization before running</span>
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
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-dark-400 hover:text-dark-200 text-sm">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim() || !category.trim() || saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary-500 hover:bg-primary-600 disabled:opacity-50 text-white rounded-lg text-sm"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Save
          </button>
        </div>
      </div>
    </div>
  )
}

function CaseEditorModal({
  suiteId,
  caseId,
  existingCase,
  onClose,
  onSaved,
}: {
  suiteId: number
  caseId?: number
  existingCase?: BenchmarkCase
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState(existingCase?.name || '')
  const [input, setInput] = useState(existingCase?.input || '')
  const [runAs, setRunAs] = useState(existingCase?.run_as || '')
  const [assertions, setAssertions] = useState(() => {
    const defaultVal = '{\n  "verify_db": [],\n  "response_contains": [],\n  "response_not_contains": []\n}'
    if (!existingCase?.assertions) return defaultVal
    try {
      return JSON.stringify(JSON.parse(existingCase.assertions), null, 2)
    } catch {
      return existingCase.assertions
    }
  })
  const [followUpFields, setFollowUpFields] = useState(() => {
    if (!existingCase?.follow_up_fields) return ''
    try {
      return JSON.stringify(JSON.parse(existingCase.follow_up_fields), null, 2)
    } catch {
      return existingCase.follow_up_fields
    }
  })
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)

  const handleGenerateAssertions = async () => {
    if (!input.trim()) return
    setGenerating(true)
    try {
      const result = await benchmarkApi.generateAssertions(input)
      setAssertions(JSON.stringify(result.assertions, null, 2))
      if (result.suggested_follow_up_fields && Object.keys(result.suggested_follow_up_fields).length > 0) {
        setFollowUpFields(JSON.stringify(result.suggested_follow_up_fields, null, 2))
      }
    } catch (err) {
      console.error('Generate assertions failed:', err)
      alert('AI assertion generation failed. Is LLM enabled?')
    } finally {
      setGenerating(false)
    }
  }

  const handleSave = async () => {
    if (!name.trim() || !input.trim()) return
    // Validate JSON
    try {
      JSON.parse(assertions)
    } catch {
      alert('Assertions must be valid JSON')
      return
    }
    if (followUpFields.trim()) {
      try {
        JSON.parse(followUpFields)
      } catch {
        alert('Follow-up fields must be valid JSON')
        return
      }
    }

    setSaving(true)
    try {
      const data = {
        name: name.trim(),
        input: input.trim(),
        run_as: runAs.trim() || undefined,
        assertions,
        follow_up_fields: followUpFields.trim() || undefined,
      }

      if (caseId) {
        await benchmarkApi.updateCase(caseId, data)
      } else {
        await benchmarkApi.createCase(suiteId, data)
      }
      onSaved()
    } catch (err) {
      console.error('Save case failed:', err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto p-4" onClick={onClose}>
      <div className="bg-dark-900 rounded-xl w-full max-w-2xl border border-dark-700 my-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-dark-800">
          <h2 className="text-lg font-bold text-dark-100">{caseId ? 'Edit Case' : 'New Case'}</h2>
          <button onClick={onClose} className="text-dark-400 hover:text-dark-200"><X size={20} /></button>
        </div>

        <div className="p-4 space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <label className="block text-sm text-dark-400 mb-1">Name</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200"
              placeholder="e.g. Walk-in check-in for Room 201"
            />
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Input (Natural Language Instruction)
              <span className="text-dark-600 ml-2">Supports $today, $tomorrow, $yesterday</span>
            </label>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200 h-20 resize-none font-mono text-sm"
              placeholder="e.g. 帮张三办理201房间入住，预计住到$tomorrow"
            />
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Run As
              <span className="text-dark-600 ml-2">Which user to execute this case as (default: current user)</span>
            </label>
            <select
              value={runAs}
              onChange={e => setRunAs(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200 text-sm"
            >
              <option value="">(current user)</option>
              <option value="front1">front1 - 李前台 (receptionist)</option>
              <option value="front2">front2 - 王前台 (receptionist)</option>
              <option value="front3">front3 - 赵前台 (receptionist)</option>
              <option value="manager">manager - 张经理 (manager)</option>
              <option value="cleaner1">cleaner1 - 刘阿姨 (cleaner)</option>
              <option value="cleaner2">cleaner2 - 陈阿姨 (cleaner)</option>
              <option value="sysadmin">sysadmin - 系统管理员 (sysadmin)</option>
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-dark-400">Assertions (JSON)</label>
              <button
                onClick={handleGenerateAssertions}
                disabled={generating || !input.trim()}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded transition-colors"
              >
                {generating ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                AI Generate
              </button>
            </div>
            <textarea
              value={assertions}
              onChange={e => setAssertions(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200 h-48 resize-y font-mono text-xs"
            />
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">Follow-up Fields (JSON, optional)</label>
            <textarea
              value={followUpFields}
              onChange={e => setFollowUpFields(e.target.value)}
              className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-dark-200 h-32 resize-y font-mono text-xs"
              placeholder='e.g. {"guest_name": "张三", "room_number": "201"}'
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 p-4 border-t border-dark-800">
          <button onClick={onClose} className="px-4 py-2 text-dark-400 hover:text-dark-200 text-sm">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim() || !input.trim() || saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary-500 hover:bg-primary-600 disabled:opacity-50 text-white rounded-lg text-sm"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {caseId ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}
