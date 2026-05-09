'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  Folder,
  Plus,
  Edit,
  Trash2,
  Search,
  Bot,
  AlertCircle,
  X,
  CheckCircle,
  Clock,
  Archive,
  Pause,
  ExternalLink
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface Project {
  id: string
  name: string
  description: string
  status: string
  knowledge_base_id: string | null
  external_project_ref: Record<string, string>
  shared_context: Record<string, any>
  project_settings: Record<string, any>
  agents: Array<{ id: string; agent_name: string }>
  created_at: string
  updated_at: string
}

interface Agent {
  id: string
  agent_name: string
  description: string
  status: string
}

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active', icon: CheckCircle, color: 'bg-emerald-100 text-emerald-700' },
  { value: 'on_hold', label: 'On Hold', icon: Pause, color: 'bg-amber-100 text-amber-700' },
  { value: 'completed', label: 'Completed', icon: CheckCircle, color: 'bg-blue-100 text-blue-700' },
  { value: 'archived', label: 'Archived', icon: Archive, color: 'bg-gray-100 text-gray-600' },
]

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [filteredProjects, setFilteredProjects] = useState<Project[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState<Project | null>(null)
  const [showAgentModal, setShowAgentModal] = useState<Project | null>(null)
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; project: Project | null }>({
    show: false,
    project: null,
  })
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    status: 'active',
    project_management: '',
  })

  useEffect(() => {
    fetchProjects()
    fetchAgents()
  }, [])

  useEffect(() => {
    filterProjects()
  }, [searchQuery, projects])

  const fetchProjects = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getProjects()
      setProjects(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      toast.error('Failed to load projects')
    } finally {
      setLoading(false)
    }
  }

  const fetchAgents = async () => {
    try {
      const data = await apiClient.getAgents()
      setAgents(data.agents_list)
    } catch (err) {
      console.error('Failed to load agents:', err)
    }
  }

  const filterProjects = () => {
    let filtered = projects
    if (searchQuery) {
      filtered = filtered.filter(project =>
        project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        project.description?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    setFilteredProjects(filtered)
  }

  const openCreateModal = () => {
    setFormData({
      name: '',
      description: '',
      status: 'active',
      project_management: '',
    })
    setShowCreateModal(true)
  }

  const openEditModal = (project: Project) => {
    // Determine which project management tool is set
    const pmTool = project.external_project_ref?.jira ? 'jira'
      : project.external_project_ref?.clickup ? 'clickup'
      : project.external_project_ref?.github ? 'github'
      : ''
    setFormData({
      name: project.name,
      description: project.description || '',
      status: project.status,
      project_management: pmTool,
    })
    setShowEditModal(project)
  }

  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast.error('Project name is required')
      return
    }

    setSaving(true)
    try {
      // Convert project_management to external_project_ref format
      const external_project_ref = formData.project_management
        ? { [formData.project_management]: 'true' }
        : {}

      const payload = {
        name: formData.name,
        description: formData.description,
        status: formData.status,
        external_project_ref,
      }

      if (showEditModal) {
        await apiClient.updateProject(showEditModal.id, payload)
        toast.success('Project updated successfully')
        setShowEditModal(null)
      } else {
        await apiClient.createProject(payload)
        toast.success('Project created successfully')
        setShowCreateModal(false)
      }
      fetchProjects()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save project')
    } finally {
      setSaving(false)
    }
  }

  const openDeleteModal = (project: Project) => {
    setDeleteModal({ show: true, project })
  }

  const closeDeleteModal = () => {
    setDeleteModal({ show: false, project: null })
  }

  const confirmDelete = async () => {
    if (!deleteModal.project) return

    setDeleting(true)
    try {
      await apiClient.deleteProject(deleteModal.project.id)
      toast.success(`"${deleteModal.project.name}" has been deleted`)
      closeDeleteModal()
      fetchProjects()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete')
    } finally {
      setDeleting(false)
    }
  }

  const addAgentToProject = async (agentId: string) => {
    if (!showAgentModal) return

    try {
      await apiClient.addAgentToProject(showAgentModal.id, agentId)
      toast.success('Agent added to project')
      fetchProjects()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add agent')
    }
  }

  const removeAgentFromProject = async (projectId: string, agentId: string) => {
    try {
      await apiClient.removeAgentFromProject(projectId, agentId)
      toast.success('Agent removed from project')
      fetchProjects()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove agent')
    }
  }

  const getStatusStyle = (status: string) => {
    const option = STATUS_OPTIONS.find(o => o.value === status)
    return option?.color || 'bg-gray-100 text-gray-600'
  }

  const getStatusIcon = (status: string) => {
    const option = STATUS_OPTIONS.find(o => o.value === status)
    const Icon = option?.icon || Clock
    return <Icon className="w-3.5 h-3.5" />
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-red-50/60 via-white to-rose-50/40">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading projects...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50/60 via-white to-rose-50/40 p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Projects</h1>
              <p className="text-gray-600 mt-1">
                Organize agents around projects with shared context
              </p>
            </div>
            <button
              onClick={openCreateModal}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white rounded-xl transition-all shadow-sm hover:shadow-md font-medium"
            >
              <Plus className="w-5 h-5" />
              <span className="hidden sm:inline">Create Project</span>
              <span className="sm:hidden">Create</span>
            </button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-red-100 rounded-xl">
                  <Folder className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Total Projects</p>
                  <p className="text-2xl font-bold text-gray-900">{projects.length}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-emerald-100 rounded-xl">
                  <CheckCircle className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Active</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {projects.filter(p => p.status === 'active').length}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-blue-100 rounded-xl">
                  <Bot className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Agents Assigned</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {projects.reduce((sum, p) => sum + (p.agents?.length || 0), 0)}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-amber-100 rounded-xl">
                  <Pause className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">On Hold</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {projects.filter(p => p.status === 'on_hold').length}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Search */}
          {projects.length > 0 && (
            <div className="relative">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search projects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-4 py-3 bg-white border border-gray-200 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-transparent shadow-sm"
              />
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-600" />
              <p className="text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Projects Grid */}
        {filteredProjects.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-12 text-center">
            <div className="w-32 h-32 mx-auto mb-6 relative">
              <div className="absolute inset-0 bg-gradient-to-br from-red-100 to-red-50 rounded-2xl transform rotate-6"></div>
              <div className="absolute inset-0 bg-white rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center">
                <Folder className="w-12 h-12 text-red-500" />
              </div>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {projects.length === 0 ? 'No projects yet' : 'No results found'}
            </h3>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              {projects.length === 0
                ? 'Create projects to organize your agents and share context between them.'
                : 'Try adjusting your search.'}
            </p>
            {projects.length === 0 && (
              <button
                onClick={openCreateModal}
                className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white rounded-xl transition-all shadow-sm hover:shadow-md font-medium"
              >
                <Plus className="w-5 h-5" />
                Create Project
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredProjects.map((project) => (
              <div
                key={project.id}
                className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-all hover:border-red-200 group"
              >
                <div className="p-5">
                  <div className="flex items-start gap-3 mb-4">
                    <div className="p-2.5 bg-red-100 rounded-xl group-hover:bg-red-200 transition-colors">
                      <Folder className="w-5 h-5 text-red-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-gray-900 truncate">
                        {project.name}
                      </h3>
                      <p className="text-sm text-gray-500 line-clamp-2 mt-1">
                        {project.description || 'No description'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 mb-4 flex-wrap">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${getStatusStyle(project.status)}`}>
                      {getStatusIcon(project.status)}
                      {STATUS_OPTIONS.find(o => o.value === project.status)?.label || project.status}
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                      <Bot className="w-3.5 h-3.5" />
                      {project.agents?.length || 0} agents
                    </span>
                  </div>

                  {/* External Links */}
                  {Object.keys(project.external_project_ref || {}).length > 0 && (
                    <div className="flex items-center gap-2 mb-4 flex-wrap">
                      {project.external_project_ref?.jira && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">
                          <ExternalLink className="w-3 h-3" />
                          Jira
                        </span>
                      )}
                      {project.external_project_ref?.github && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                          <ExternalLink className="w-3 h-3" />
                          GitHub
                        </span>
                      )}
                      {project.external_project_ref?.clickup && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-50 text-purple-600 rounded text-xs">
                          <ExternalLink className="w-3 h-3" />
                          ClickUp
                        </span>
                      )}
                    </div>
                  )}

                  <div className="flex items-center gap-2 text-xs text-gray-500 mb-4">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Updated {formatDate(project.updated_at)}</span>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => setShowAgentModal(project)}
                      className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
                    >
                      <Bot className="w-4 h-4" />
                      Agents
                    </button>
                    <button
                      onClick={() => openEditModal(project)}
                      className="inline-flex items-center justify-center px-3 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => openDeleteModal(project)}
                      className="inline-flex items-center justify-center px-3 py-2.5 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || showEditModal) && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                {showEditModal ? 'Edit Project' : 'Create Project'}
              </h3>
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setShowEditModal(null)
                }}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Project Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Mobile App Redesign"
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe the project..."
                  rows={3}
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                >
                  {STATUS_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Project Management Tool</label>
                <select
                  value={formData.project_management}
                  onChange={(e) => setFormData({ ...formData, project_management: e.target.value })}
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                >
                  <option value="">None</option>
                  <option value="jira">Jira</option>
                  <option value="clickup">ClickUp</option>
                  <option value="github">GitHub</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">Select the project management tool used for this project</p>
              </div>
            </div>

            <div className="sticky bottom-0 bg-white border-t border-gray-100 px-6 py-4 flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setShowEditModal(null)
                }}
                disabled={saving}
                className="px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {saving ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Saving...
                  </>
                ) : (
                  showEditModal ? 'Update Project' : 'Create Project'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Agent Management Modal */}
      {showAgentModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                Manage Agents - {showAgentModal.name}
              </h3>
              <button
                onClick={() => setShowAgentModal(null)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="p-6">
              <div className="mb-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Assigned Agents</h4>
                {showAgentModal.agents?.length > 0 ? (
                  <div className="space-y-2">
                    {showAgentModal.agents.map((agent) => (
                      <div key={agent.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-3">
                          <Bot className="w-5 h-5 text-gray-400" />
                          <span className="text-sm font-medium text-gray-900">{agent.agent_name}</span>
                        </div>
                        <button
                          onClick={() => removeAgentFromProject(showAgentModal.id, agent.id)}
                          className="text-red-600 hover:text-red-700 text-sm"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 text-center py-4">No agents assigned yet</p>
                )}
              </div>

              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-3">Add Agent</h4>
                <p className="text-xs text-gray-500 mb-3">
                  Select an agent to add to this project
                </p>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {agents
                    .filter(a => !showAgentModal.agents?.find(pa => pa.agent_name === a.agent_name))
                    .map((agent) => (
                      <button
                        key={agent.id || agent.agent_name}
                        onClick={() => addAgentToProject(agent.id)}
                        disabled={!agent.id}
                        className="w-full flex items-center gap-3 p-3 text-left bg-white border border-gray-200 rounded-lg hover:border-red-300 hover:bg-red-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <Bot className="w-5 h-5 text-gray-400" />
                        <span className="text-sm font-medium text-gray-900">{agent.agent_name}</span>
                      </button>
                    ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {deleteModal.show && deleteModal.project && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 bg-red-100 rounded-xl">
                <Trash2 className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Delete Project</h3>
            </div>

            <p className="text-gray-600 mb-6">
              Are you sure you want to delete <span className="font-semibold text-gray-900">"{deleteModal.project.name}"</span>?
              This will remove all agent associations and shared context.
            </p>

            <div className="flex gap-3 justify-end">
              <button
                onClick={closeDeleteModal}
                disabled={deleting}
                className="px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {deleting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
