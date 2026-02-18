import { useEffect, useState } from 'react'
import { Book, Plus, Pencil, Trash2, ChevronRight, RefreshCw } from 'lucide-react'
import { dictApi, DictType, DictItem } from '../../services/api'

export default function DictManagement() {
  const [types, setTypes] = useState<DictType[]>([])
  const [items, setItems] = useState<DictItem[]>([])
  const [selectedType, setSelectedType] = useState<DictType | null>(null)
  const [loading, setLoading] = useState(true)
  const [itemsLoading, setItemsLoading] = useState(false)

  // Type form
  const [showTypeForm, setShowTypeForm] = useState(false)
  const [editingType, setEditingType] = useState<DictType | null>(null)
  const [typeForm, setTypeForm] = useState({ code: '', name: '', description: '' })

  // Item form
  const [showItemForm, setShowItemForm] = useState(false)
  const [editingItem, setEditingItem] = useState<DictItem | null>(null)
  const [itemForm, setItemForm] = useState({ label: '', value: '', color: '', sort_order: 0 })

  useEffect(() => { loadTypes() }, [])

  const loadTypes = async () => {
    try {
      setLoading(true)
      const data = await dictApi.getTypes()
      setTypes(data)
      if (data.length > 0 && !selectedType) {
        selectType(data[0])
      }
    } catch (err) {
      console.error('Failed to load dict types:', err)
    } finally {
      setLoading(false)
    }
  }

  const selectType = async (type: DictType) => {
    setSelectedType(type)
    setItemsLoading(true)
    try {
      const data = await dictApi.getItems(type.id)
      setItems(data)
    } catch (err) {
      console.error('Failed to load items:', err)
    } finally {
      setItemsLoading(false)
    }
  }

  // ---- Type CRUD ----
  const openTypeCreate = () => {
    setEditingType(null)
    setTypeForm({ code: '', name: '', description: '' })
    setShowTypeForm(true)
  }

  const openTypeEdit = (type: DictType) => {
    setEditingType(type)
    setTypeForm({ code: type.code, name: type.name, description: type.description })
    setShowTypeForm(true)
  }

  const saveType = async () => {
    try {
      if (editingType) {
        await dictApi.updateType(editingType.id, { name: typeForm.name, description: typeForm.description })
      } else {
        await dictApi.createType({ code: typeForm.code, name: typeForm.name, description: typeForm.description })
      }
      setShowTypeForm(false)
      await loadTypes()
    } catch (err: any) {
      alert(err.response?.data?.detail || '操作失败')
    }
  }

  const deleteType = async (type: DictType) => {
    if (type.is_system) {
      alert('系统内置字典不可删除')
      return
    }
    if (!confirm(`确定删除字典类型 "${type.name}"？`)) return
    try {
      await dictApi.deleteType(type.id)
      if (selectedType?.id === type.id) {
        setSelectedType(null)
        setItems([])
      }
      await loadTypes()
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  // ---- Item CRUD ----
  const openItemCreate = () => {
    setEditingItem(null)
    setItemForm({ label: '', value: '', color: '', sort_order: 0 })
    setShowItemForm(true)
  }

  const openItemEdit = (item: DictItem) => {
    setEditingItem(item)
    setItemForm({ label: item.label, value: item.value, color: item.color, sort_order: item.sort_order })
    setShowItemForm(true)
  }

  const saveItem = async () => {
    if (!selectedType) return
    try {
      if (editingItem) {
        await dictApi.updateItem(editingItem.id, itemForm)
      } else {
        await dictApi.createItem(selectedType.id, itemForm)
      }
      setShowItemForm(false)
      await selectType(selectedType)
      await loadTypes()
    } catch (err: any) {
      alert(err.response?.data?.detail || '操作失败')
    }
  }

  const deleteItem = async (item: DictItem) => {
    if (!confirm(`确定删除字典项 "${item.label}"？`)) return
    try {
      await dictApi.deleteItem(item.id)
      if (selectedType) await selectType(selectedType)
      await loadTypes()
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Book size={24} className="text-primary-400" />
          <h1 className="text-2xl font-bold">数据字典</h1>
        </div>
        <button onClick={loadTypes} className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg text-sm">
          <RefreshCw size={16} />
          刷新
        </button>
      </div>

      {/* Main content: left types + right items */}
      <div className="flex gap-6">
        {/* Left: Dict Types */}
        <div className="w-80 flex-shrink-0">
          <div className="bg-dark-900 rounded-xl border border-dark-800">
            <div className="flex items-center justify-between p-4 border-b border-dark-800">
              <span className="font-medium">字典类型</span>
              <button onClick={openTypeCreate} className="p-1.5 bg-primary-600 hover:bg-primary-700 rounded-lg">
                <Plus size={16} />
              </button>
            </div>
            <div className="max-h-[calc(100vh-280px)] overflow-y-auto">
              {types.length === 0 ? (
                <div className="p-4 text-center text-dark-500 text-sm">暂无字典类型</div>
              ) : (
                types.map(type => (
                  <div
                    key={type.id}
                    onClick={() => selectType(type)}
                    className={`flex items-center justify-between px-4 py-3 cursor-pointer border-b border-dark-800/50 transition-colors ${
                      selectedType?.id === type.id ? 'bg-primary-600/10 text-primary-400' : 'hover:bg-dark-800'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm truncate">{type.name}</span>
                        {type.is_system && (
                          <span className="px-1.5 py-0.5 text-xs bg-dark-700 text-dark-400 rounded">内置</span>
                        )}
                      </div>
                      <div className="text-xs text-dark-500 mt-0.5">{type.code} ({type.item_count})</div>
                    </div>
                    <div className="flex items-center gap-1 ml-2">
                      <button
                        onClick={e => { e.stopPropagation(); openTypeEdit(type) }}
                        className="p-1 hover:bg-dark-700 rounded"
                      >
                        <Pencil size={14} className="text-dark-400" />
                      </button>
                      {!type.is_system && (
                        <button
                          onClick={e => { e.stopPropagation(); deleteType(type) }}
                          className="p-1 hover:bg-dark-700 rounded"
                        >
                          <Trash2 size={14} className="text-red-400" />
                        </button>
                      )}
                      <ChevronRight size={14} className="text-dark-500" />
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right: Dict Items */}
        <div className="flex-1">
          <div className="bg-dark-900 rounded-xl border border-dark-800">
            <div className="flex items-center justify-between p-4 border-b border-dark-800">
              <span className="font-medium">
                {selectedType ? `${selectedType.name} — 字典项` : '请选择字典类型'}
              </span>
              {selectedType && (
                <button onClick={openItemCreate} className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-600 hover:bg-primary-700 rounded-lg text-sm">
                  <Plus size={14} />
                  新增
                </button>
              )}
            </div>

            {itemsLoading ? (
              <div className="flex items-center justify-center h-32">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-500" />
              </div>
            ) : !selectedType ? (
              <div className="p-8 text-center text-dark-500">
                <Book size={48} className="mx-auto mb-3 opacity-30" />
                <p>从左侧选择一个字典类型查看其字典项</p>
              </div>
            ) : items.length === 0 ? (
              <div className="p-8 text-center text-dark-500 text-sm">暂无字典项</div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="text-left text-dark-400 text-sm border-b border-dark-800">
                    <th className="px-4 py-3">排序</th>
                    <th className="px-4 py-3">标签</th>
                    <th className="px-4 py-3">值</th>
                    <th className="px-4 py-3">颜色</th>
                    <th className="px-4 py-3">默认</th>
                    <th className="px-4 py-3">状态</th>
                    <th className="px-4 py-3">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(item => (
                    <tr key={item.id} className="border-b border-dark-800/50 hover:bg-dark-800/30">
                      <td className="px-4 py-3 text-sm text-dark-400">{item.sort_order}</td>
                      <td className="px-4 py-3 text-sm font-medium">{item.label}</td>
                      <td className="px-4 py-3 text-sm text-dark-300 font-mono">{item.value}</td>
                      <td className="px-4 py-3">
                        {item.color ? (
                          <div className="flex items-center gap-2">
                            <div className="w-4 h-4 rounded" style={{ backgroundColor: item.color }} />
                            <span className="text-xs text-dark-400">{item.color}</span>
                          </div>
                        ) : (
                          <span className="text-xs text-dark-500">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {item.is_default && <span className="px-1.5 py-0.5 text-xs bg-primary-600/20 text-primary-400 rounded">默认</span>}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-1.5 py-0.5 text-xs rounded ${item.is_active ? 'bg-emerald-500/20 text-emerald-400' : 'bg-dark-700 text-dark-400'}`}>
                          {item.is_active ? '启用' : '禁用'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <button onClick={() => openItemEdit(item)} className="p-1 hover:bg-dark-700 rounded">
                            <Pencil size={14} className="text-dark-400" />
                          </button>
                          <button onClick={() => deleteItem(item)} className="p-1 hover:bg-dark-700 rounded">
                            <Trash2 size={14} className="text-red-400" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Type Form Modal */}
      {showTypeForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-dark-900 rounded-xl border border-dark-800 w-[440px] p-6">
            <h3 className="text-lg font-medium mb-4">{editingType ? '编辑字典类型' : '新增字典类型'}</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">编码</label>
                <input
                  value={typeForm.code}
                  onChange={e => setTypeForm(f => ({ ...f, code: e.target.value }))}
                  disabled={!!editingType}
                  placeholder="如: room_status"
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">名称</label>
                <input
                  value={typeForm.name}
                  onChange={e => setTypeForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="如: 房间状态"
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">描述</label>
                <input
                  value={typeForm.description}
                  onChange={e => setTypeForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="可选"
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowTypeForm(false)} className="px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg text-sm">取消</button>
              <button onClick={saveType} className="px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-sm">保存</button>
            </div>
          </div>
        </div>
      )}

      {/* Item Form Modal */}
      {showItemForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-dark-900 rounded-xl border border-dark-800 w-[440px] p-6">
            <h3 className="text-lg font-medium mb-4">{editingItem ? '编辑字典项' : '新增字典项'}</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">标签</label>
                <input
                  value={itemForm.label}
                  onChange={e => setItemForm(f => ({ ...f, label: e.target.value }))}
                  placeholder="如: 空闲-已清洁"
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">值</label>
                <input
                  value={itemForm.value}
                  onChange={e => setItemForm(f => ({ ...f, value: e.target.value }))}
                  placeholder="如: vacant_clean"
                  className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm text-dark-400 mb-1">颜色</label>
                  <input
                    value={itemForm.color}
                    onChange={e => setItemForm(f => ({ ...f, color: e.target.value }))}
                    placeholder="如: green, #ff0000"
                    className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div className="w-24">
                  <label className="block text-sm text-dark-400 mb-1">排序</label>
                  <input
                    type="number"
                    value={itemForm.sort_order}
                    onChange={e => setItemForm(f => ({ ...f, sort_order: parseInt(e.target.value) || 0 }))}
                    className="w-full bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowItemForm(false)} className="px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg text-sm">取消</button>
              <button onClick={saveItem} className="px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-sm">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
