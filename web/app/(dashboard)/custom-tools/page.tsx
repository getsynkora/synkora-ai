'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { Plus, Wrench, Edit, Trash2, TestTube, Eye, ArrowLeft, Search, Tag } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface CustomTool {
  id: string
  name: string
  description: string
  server_url: string
  auth_type: string
  auth_config?: any
  enabled: boolean
  icon?: string
  tags?: string[]
  openapi_schema: any
  created_at: string
  updated_at: string
}

interface Operation {
  operation_id: string
  method: string
  path: string
  summary: string
  description: string
}

export default function CustomToolsPage() {
  const router = useRouter()
  const [tools, setTools] = useState<CustomTool[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingTool, setEditingTool] = useState<CustomTool | null>(null)
  const [viewingOperations, setViewingOperations] = useState<CustomTool | null>(null)
  const [operations, setOperations] = useState<Operation[]>([])
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    fetchTools()
  }, [])

  const fetchTools = async () => {
    try {
      const tools = await apiClient.getCustomTools()
      setTools(tools)
    } catch (error) {
      console.error('Failed to fetch custom tools:', error)
      toast.error('Failed to load custom tools')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (toolId: string) => {
    if (!confirm('Are you sure you want to delete this custom tool? This will also remove it from all agents using it.')) return

    try {
      await apiClient.deleteCustomTool(toolId)
      toast.success('Custom tool deleted successfully')
      fetchTools()
    } catch (error) {
      console.error('Failed to delete tool:', error)
      toast.error('Failed to delete tool')
    }
  }

  const handleTest = async (toolId: string) => {
    try {
      await apiClient.testCustomTool(toolId)
      toast.success('Connection test successful!')
    } catch (error) {
      console.error('Failed to test tool:', error)
      toast.error('Connection test failed')
    }
  }

  const handleViewOperations = async (tool: CustomTool) => {
    setViewingOperations(tool)
    try {
      const data = await apiClient.getCustomToolOperations(tool.id)
      setOperations(data.operations || [])
    } catch (error) {
      console.error('Failed to fetch operations:', error)
      toast.error('Failed to load operations')
    }
  }

  const toggleToolStatus = async (toolId: string, enabled: boolean) => {
    try {
      await apiClient.updateCustomTool(toolId, { enabled })
      toast.success(`Tool ${enabled ? 'enabled' : 'disabled'} successfully`)
      fetchTools()
    } catch (error) {
      console.error('Failed to toggle tool status:', error)
      toast.error('Failed to update tool status')
    }
  }

  const filteredTools = tools.filter(tool =>
    tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    tool.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    tool.tags?.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header - More Compact */}
        <div className="mb-6">
          <button
            onClick={() => router.push('/agents')}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-3 text-sm"
          >
            <ArrowLeft size={18} />
            Back to Agents
          </button>
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Custom Tools</h1>
              <p className="text-gray-600 mt-1 text-sm">
                Import and manage OpenAPI-based tools for your agents
              </p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-2 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white px-5 py-2.5 rounded-lg transition-all shadow-sm hover:shadow-md text-sm font-medium"
            >
              <Plus size={18} />
              Import Tool
            </button>
          </div>
        </div>

        {/* Stats - More Compact */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-gray-600 text-xs font-medium">Total Tools</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">{tools.length}</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-gray-600 text-xs font-medium">Enabled Tools</div>
            <div className="text-2xl font-bold text-emerald-600 mt-1">
              {tools.filter(t => t.enabled).length}
            </div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-gray-600 text-xs font-medium">Total Operations</div>
            <div className="text-2xl font-bold text-red-600 mt-1">
              {tools.reduce((sum, tool) => {
                const paths = tool.openapi_schema?.paths || {}
                return sum + Object.keys(paths).reduce((pathSum, path) => {
                  return pathSum + Object.keys(paths[path]).filter(m => 
                    ['get', 'post', 'put', 'patch', 'delete'].includes(m.toLowerCase())
                  ).length
                }, 0)
              }, 0)}
            </div>
          </div>
        </div>

        {/* Search - More Compact */}
        <div className="mb-5">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
            <input
              type="text"
              placeholder="Search tools by name, description, or tags..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Tools List - More Compact */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-200">
            <h2 className="text-base font-semibold text-gray-900">Imported Tools</h2>
          </div>

          {loading ? (
            <div className="p-12 text-center text-gray-500 text-sm">Loading tools...</div>
          ) : filteredTools.length === 0 ? (
            <div className="p-12 text-center">
              <Wrench className="mx-auto text-gray-400 mb-3" size={40} />
              <p className="text-gray-500 mb-3 text-sm">
                {searchQuery ? 'No tools match your search' : 'No custom tools imported yet'}
              </p>
              {!searchQuery && (
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="text-red-600 hover:text-red-700 font-medium text-sm"
                >
                  Import your first custom tool
                </button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {filteredTools.map((tool) => (
                <div key={tool.id} className="p-4 hover:bg-gray-50 transition-colors">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1.5">
                        {tool.icon ? (
                          <img src={tool.icon} alt="" className="w-6 h-6 rounded" />
                        ) : (
                          <Wrench className="text-red-600" size={18} />
                        )}
                        <h3 className="text-base font-semibold text-gray-900">{tool.name}</h3>
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            tool.enabled
                              ? 'bg-emerald-100 text-emerald-700'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {tool.enabled ? 'Enabled' : 'Disabled'}
                        </span>
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                          {tool.auth_type}
                        </span>
                      </div>
                      <p className="text-gray-600 mb-1.5 text-sm">{tool.description}</p>
                      <div className="flex items-center gap-3 text-xs text-gray-500 mb-1.5">
                        <span className="font-mono">{tool.server_url}</span>
                        <span>•</span>
                        <span>Added {new Date(tool.created_at).toLocaleDateString()}</span>
                      </div>
                      {tool.tags && tool.tags.length > 0 && (
                        <div className="flex items-center gap-2 flex-wrap">
                          {tool.tags.map((tag, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs"
                            >
                              <Tag size={12} />
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 ml-4">
                      <button
                        onClick={() => handleViewOperations(tool)}
                        className="p-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                        title="View Operations"
                      >
                        <Eye size={18} />
                      </button>
                      <button
                        onClick={() => handleTest(tool.id)}
                        className="p-2 text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                        title="Test Connection"
                      >
                        <TestTube size={18} />
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            // Fetch full tool details including openapi_schema
                            const fullTool = await apiClient.getCustomTool(tool.id)
                            setEditingTool(fullTool)
                          } catch (error) {
                            console.error('Failed to fetch tool details:', error)
                            toast.error('Failed to load tool details')
                          }
                        }}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Edit Tool"
                      >
                        <Edit size={18} />
                      </button>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={tool.enabled}
                          onChange={(e) => toggleToolStatus(tool.id, e.target.checked)}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
                      </label>
                      <button
                        onClick={() => handleDelete(tool.id)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Delete Tool"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingTool) && (
        <CustomToolModal
          tool={editingTool}
          onClose={() => {
            setShowCreateModal(false)
            setEditingTool(null)
          }}
          onSuccess={() => {
            setShowCreateModal(false)
            setEditingTool(null)
            fetchTools()
          }}
        />
      )}

      {/* Operations Modal */}
      {viewingOperations && (
        <OperationsModal
          tool={viewingOperations}
          operations={operations}
          onClose={() => {
            setViewingOperations(null)
            setOperations([])
          }}
        />
      )}
    </div>
  )
}

// Custom Tool Modal Component
function CustomToolModal({
  tool,
  onClose,
  onSuccess,
}: {
  tool: CustomTool | null
  onClose: () => void
  onSuccess: () => void
}) {
  const [importMethod, setImportMethod] = useState<'url' | 'paste'>('url')
  const [formData, setFormData] = useState({
    name: tool?.name || '',
    description: tool?.description || '',
    server_url: tool?.server_url || '',
    auth_type: tool?.auth_type || 'none',
    icon: tool?.icon || '',
    tags: tool?.tags?.join(', ') || '',
  })
  const [schemaUrl, setSchemaUrl] = useState('')
  const [schemaJson, setSchemaJson] = useState(
    tool?.openapi_schema ? JSON.stringify(tool.openapi_schema, null, 2) : ''
  )
  const [authConfigJson, setAuthConfigJson] = useState(
    tool?.auth_config ? JSON.stringify(tool.auth_config, null, 2) : '{}'
  )
  const [saving, setSaving] = useState(false)
  const [importing, setImporting] = useState(false)
  const formId = 'custom-tool-modal-form'
  const fieldClass = 'w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500'
  const textareaClass = `${fieldClass} resize-y`
  const codeClass = 'w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 font-mono text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500'
  const labelClass = 'mb-2 block text-sm font-semibold text-gray-700'
  const helpClass = 'mt-2 text-xs leading-relaxed text-gray-500'

  const handleImportFromUrl = async () => {
    if (!schemaUrl) {
      toast.error('Please enter an OpenAPI schema URL')
      return
    }

    setImporting(true)
    try {
      await apiClient.importCustomToolFromUrl(schemaUrl)
      toast.success('Schema imported successfully!')
      onSuccess()
    } catch (error) {
      console.error('Failed to import schema:', error)
      toast.error('Failed to import schema')
    } finally {
      setImporting(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)

    try {
      let openapi_schema = {}
      let auth_config = {}

      try {
        openapi_schema = schemaJson.trim() ? JSON.parse(schemaJson) : {}
      } catch {
        toast.error('Invalid JSON in OpenAPI Schema')
        setSaving(false)
        return
      }

      try {
        auth_config = authConfigJson.trim() ? JSON.parse(authConfigJson) : {}
      } catch {
        toast.error('Invalid JSON in Auth Config')
        setSaving(false)
        return
      }

      const payload = {
        name: formData.name,
        description: formData.description,
        server_url: formData.server_url,
        openapi_schema,
        auth_type: formData.auth_type,
        auth_config,
        icon: formData.icon || null,
        tags: formData.tags ? formData.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
        enabled: true
      }

      if (tool) {
        await apiClient.updateCustomTool(tool.id, payload)
      } else {
        await apiClient.createCustomTool(payload)
      }
      
      toast.success(`Tool ${tool ? 'updated' : 'created'} successfully!`)
      onSuccess()
    } catch (error) {
      console.error('Failed to save tool:', error)
      toast.error('Failed to save tool')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
      <div className="w-full max-w-4xl overflow-hidden rounded-[2rem] border border-black/10 bg-[#fcfaf5] shadow-[0_32px_90px_rgba(0,0,0,0.18)]">
        <div className="border-b border-black/10 bg-white px-8 py-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#6e675d]">
            <Wrench className="h-3.5 w-3.5 text-[#2d8b69]" />
            Custom Tool
          </div>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-gray-900">
            {tool ? 'Edit Custom Tool' : 'Import Custom Tool'}
          </h2>
          <p className="mt-2 text-base text-gray-600">
            Configure your OpenAPI-based tool
          </p>
        </div>

        <form
          id={formId}
          onSubmit={handleSubmit}
          className="max-h-[calc(90vh-210px)] space-y-6 overflow-y-auto px-8 py-7"
        >
          {!tool && (
            <div>
              <label className={labelClass}>
                Import Method
              </label>
              <div className="grid gap-3 md:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setImportMethod('url')}
                  className={`rounded-[1.5rem] border px-5 py-4 text-left transition-all ${
                    importMethod === 'url'
                      ? 'border-black/10 bg-white text-gray-900 shadow-[0_16px_36px_rgba(0,0,0,0.08)]'
                      : 'border-black/10 bg-[#f4efe4] text-[#5b564e] hover:bg-white'
                  }`}
                >
                  <div className="text-sm font-semibold text-current">Import from URL</div>
                  <div className="mt-1 text-sm leading-relaxed text-[#5b564e]">Fetch the OpenAPI schema from a hosted endpoint.</div>
                </button>
                <button
                  type="button"
                  onClick={() => setImportMethod('paste')}
                  className={`rounded-[1.5rem] border px-5 py-4 text-left transition-all ${
                    importMethod === 'paste'
                      ? 'border-black/10 bg-white text-gray-900 shadow-[0_16px_36px_rgba(0,0,0,0.08)]'
                      : 'border-black/10 bg-[#f4efe4] text-[#5b564e] hover:bg-white'
                  }`}
                >
                  <div className="text-sm font-semibold text-current">Paste Schema</div>
                  <div className="mt-1 text-sm leading-relaxed text-[#5b564e]">Manually provide the OpenAPI JSON and configuration.</div>
                </button>
              </div>
            </div>
          )}

          {!tool && importMethod === 'url' && (
            <div className="rounded-[1.6rem] border border-black/10 bg-white p-5 shadow-[0_20px_50px_rgba(0,0,0,0.05)]">
              <label className={labelClass}>
                OpenAPI Schema URL *
              </label>
              <div className="flex flex-col gap-3 md:flex-row">
                <input
                  type="url"
                  value={schemaUrl}
                  onChange={(e) => setSchemaUrl(e.target.value)}
                  className={`flex-1 ${fieldClass}`}
                  placeholder="https://api.example.com/openapi.json"
                />
                <button
                  type="button"
                  onClick={handleImportFromUrl}
                  disabled={importing}
                  className="rounded-[1.2rem] bg-[#171717] px-6 py-4 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {importing ? 'Importing...' : 'Import'}
                </button>
              </div>
              <p className={helpClass}>
                The URL should return a valid OpenAPI 3.0+ specification
              </p>
            </div>
          )}

          {(tool || importMethod === 'paste') && (
            <>
              <div className="grid gap-5 md:grid-cols-2">
                <div>
                  <label className={labelClass}>
                    Tool Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className={fieldClass}
                    placeholder="My API Tool"
                    required
                  />
                </div>

                <div>
                  <label className={labelClass}>
                    Server URL *
                  </label>
                  <input
                    type="url"
                    value={formData.server_url}
                    onChange={(e) => setFormData({ ...formData, server_url: e.target.value })}
                    className={fieldClass}
                    placeholder="https://api.example.com"
                    required
                  />
                </div>
              </div>

              <div>
                <label className={labelClass}>
                  Description *
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className={textareaClass}
                  rows={3}
                  placeholder="Describe what this tool does..."
                  required
                />
              </div>

              <div>
                <label className={labelClass}>
                  OpenAPI Schema (JSON) *
                </label>
                <textarea
                  value={schemaJson}
                  onChange={(e) => setSchemaJson(e.target.value)}
                  className={codeClass}
                  rows={10}
                  placeholder='{"openapi": "3.0.0", ...}'
                  required
                />
              </div>

              <div className="grid gap-5 md:grid-cols-2">
                <div>
                  <label className={labelClass}>
                    Authentication Type
                  </label>
                  <select
                    value={formData.auth_type}
                    onChange={(e) => setFormData({ ...formData, auth_type: e.target.value })}
                    className={fieldClass}
                  >
                    <option value="none">None</option>
                    <option value="bearer">Bearer Token</option>
                    <option value="basic">Basic Auth</option>
                    <option value="custom">Custom Headers</option>
                  </select>
                </div>

                <div>
                  <label className={labelClass}>
                    Icon URL (Optional)
                  </label>
                  <input
                    type="url"
                    value={formData.icon}
                    onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                    className={fieldClass}
                    placeholder="https://example.com/icon.png"
                  />
                </div>
              </div>

              {formData.auth_type !== 'none' && (
                <div>
                  <label className={labelClass}>
                    Auth Config (JSON)
                  </label>
                  <textarea
                    value={authConfigJson}
                    onChange={(e) => setAuthConfigJson(e.target.value)}
                    className={codeClass}
                    rows={4}
                    placeholder={`{\n  "token": "your_token_here"\n}`}
                  />
                  <p className={helpClass}>
                    {formData.auth_type === 'bearer' && 'Example: {"token": "your_bearer_token"}'}
                    {formData.auth_type === 'basic' && 'Example: {"username": "user", "password": "pass"}'}
                    {formData.auth_type === 'custom' && 'Example: {"X-API-Key": "your_key"}'}
                  </p>
                </div>
              )}

              <div>
                <label className={labelClass}>
                  Tags (comma-separated)
                </label>
                <input
                  type="text"
                  value={formData.tags}
                  onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                  className={fieldClass}
                  placeholder="api, rest, external"
                />
              </div>

              <div className="rounded-[1.5rem] border border-black/10 bg-[#f7f2e7] p-4">
                <h4 className="text-sm font-semibold text-gray-900">About Custom Tools</h4>
                <p className="mt-2 text-xs leading-relaxed text-[#5b564e]">
                  Custom tools allow you to import OpenAPI-based APIs and use their operations with your agents.
                  Each tool can have multiple operations that can be individually enabled for different agents.
                </p>
              </div>
            </>
          )}
        </form>

        <div className="flex justify-end gap-3 border-t border-black/10 bg-white px-8 py-5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-[1.2rem] border border-black/10 bg-[#f4efe4] px-5 py-3 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#ebe2cf]"
          >
            Cancel
          </button>
          <button
            type="submit"
            form={formId}
            disabled={saving}
            className="rounded-[1.2rem] bg-[#171717] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? 'Saving...' : tool ? 'Update Tool' : 'Create Tool'}
          </button>
        </div>
      </div>
    </div>
  )
}

// Operations Modal Component
function OperationsModal({
  tool,
  operations,
  onClose,
}: {
  tool: CustomTool
  operations: Operation[]
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-gray-900">
                {tool.name} - Available Operations
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                {operations.length} operations available
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg"
            >
              <span className="text-2xl">&times;</span>
            </button>
          </div>
        </div>

        <div className="p-6 space-y-4">
          {operations.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              No operations found in this tool
            </div>
          ) : (
            operations.map((operation) => (
              <div
                key={operation.operation_id}
                className="border border-gray-200 rounded-lg p-4 hover:border-red-300 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`px-2 py-1 text-xs font-semibold rounded ${
                        operation.method === 'GET' ? 'bg-blue-100 text-blue-700' :
                        operation.method === 'POST' ? 'bg-green-100 text-green-700' :
                        operation.method === 'PUT' ? 'bg-yellow-100 text-yellow-700' :
                        operation.method === 'DELETE' ? 'bg-red-100 text-red-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {operation.method}
                      </span>
                      <code className="text-sm text-gray-600">{operation.path}</code>
                    </div>
                    <h4 className="font-semibold text-gray-900 mb-1">
                      {operation.summary || operation.operation_id}
                    </h4>
                    {operation.description && (
                      <p className="text-sm text-gray-600">{operation.description}</p>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
