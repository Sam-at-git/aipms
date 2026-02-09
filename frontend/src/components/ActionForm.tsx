import { ChevronUp, ChevronDown, Undo2, ShieldCheck, Lock } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useOntologyStore } from '../store'
import type { AIAction, OntologyAction } from '../types'

interface ActionFormProps {
  action: AIAction
  formValues: Record<string, string>
  showForm: boolean
  onToggleForm: () => void
  onChange: (values: Record<string, string>) => void
  onSubmit: () => void
}

export default function ActionForm({ action, formValues, showForm, onToggleForm, onChange, onSubmit }: ActionFormProps) {
  const { fetchKinetic, getActionSchema } = useOntologyStore()
  const [schema, setSchema] = useState<OntologyAction | null>(null)

  useEffect(() => {
    // Lazy-load kinetic data on first action form render
    fetchKinetic().then(() => {
      setSchema(getActionSchema(action.action_type))
    })
  }, [action.action_type, fetchKinetic, getActionSchema])

  if (!action.missing_fields || action.missing_fields.length === 0) return null

  // Build param lookup from kinetic schema
  const paramLookup = schema
    ? Object.fromEntries(schema.params.map(p => [p.name, p]))
    : {}

  return (
    <div className="mb-2 p-2 bg-dark-800 rounded">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <p className="text-xs text-dark-400">请补充信息：</p>
          {/* Action badges */}
          {schema && (
            <div className="flex gap-1">
              {schema.undoable && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 flex items-center gap-0.5">
                  <Undo2 size={9} /> 可撤销
                </span>
              )}
              {schema.requires_confirmation && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 flex items-center gap-0.5">
                  <ShieldCheck size={9} /> 需确认
                </span>
              )}
              {schema.allowed_roles && schema.allowed_roles.length > 0 && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-400 flex items-center gap-0.5">
                  <Lock size={9} /> {schema.allowed_roles.join(', ')}
                </span>
              )}
            </div>
          )}
        </div>
        <button onClick={onToggleForm} className="text-dark-500 hover:text-dark-300">
          {showForm ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>
      {showForm && (
        <div className="space-y-2">
          {action.missing_fields.map((field, fIdx) => {
            const kineticParam = paramLookup[field.field_name]
            // Upgrade to select if kinetic says there are enum values
            const effectiveType = kineticParam?.enum_values?.length
              ? 'select'
              : field.field_type
            const placeholder = field.placeholder || kineticParam?.description || ''

            return (
              <div key={fIdx}>
                <label className="text-xs text-dark-400 block mb-1">
                  {field.display_name}
                  {field.required && <span className="text-red-500 ml-1">*</span>}
                </label>
                {effectiveType === 'select' ? (
                  <select
                    value={formValues[field.field_name] || ''}
                    onChange={(e) => onChange({ ...formValues, [field.field_name]: e.target.value })}
                    className="w-full bg-dark-700 border border-dark-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-primary-500"
                  >
                    <option value="">{placeholder || '请选择'}</option>
                    {/* Prefer backend options, fall back to kinetic enum_values */}
                    {field.options?.length
                      ? field.options.map((opt, oIdx) => (
                          <option key={oIdx} value={opt.value}>{opt.label}</option>
                        ))
                      : kineticParam?.enum_values?.map((v, oIdx) => (
                          <option key={oIdx} value={v}>{v}</option>
                        ))
                    }
                  </select>
                ) : effectiveType === 'date' ? (
                  <input
                    type="text"
                    value={formValues[field.field_name] || ''}
                    onChange={(e) => onChange({ ...formValues, [field.field_name]: e.target.value })}
                    placeholder={placeholder || '如：明天、2025-02-05'}
                    className="w-full bg-dark-700 border border-dark-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-primary-500"
                  />
                ) : (
                  <input
                    type={effectiveType === 'number' ? 'number' : 'text'}
                    value={formValues[field.field_name] || ''}
                    onChange={(e) => onChange({ ...formValues, [field.field_name]: e.target.value })}
                    placeholder={placeholder}
                    className="w-full bg-dark-700 border border-dark-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-primary-500"
                  />
                )}
              </div>
            )
          })}
          <button
            onClick={onSubmit}
            className="w-full mt-2 px-3 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs"
          >
            提交
          </button>
        </div>
      )}
    </div>
  )
}
