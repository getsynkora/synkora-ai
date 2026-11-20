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
  { value: 'active', label: 'Active', icon: CheckCircle, color: 'bg-leaf-wash text-forest' },
  { value: 'on_hold', label: 'On Hold', icon: Pause, color: 'bg-sand-deep text-gold' },
  { value: 'completed', label: 'Completed', icon: CheckCircle, color: 'bg-sky-wash text-azure' },
  { value: 'archived', label: 'Archived', icon: Archive, color: 'bg-sand text-ink-soft' },
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
    return option?.color || 'bg-sand text-ink-soft'
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
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-danger mx-auto mb-4"></div>
          <p className="text-ink-soft">Loading projects…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Projects</h1>
              <p className="text-ink-soft mt-1">
                Organize agents around projects with shared context
              </p>
            </div>
            <button
              onClick={openCreateModal}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-ink hover:bg-ink/85 text-white rounded-xl transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm hover:shadow-md font-medium"
            >
              <Plus className="w-5 h-5" />
              <span className="hidden sm:inline">Create Project</span>
              <span className="sm:hidden">Create</span>
            </button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-xl shadow-sm border border-sand p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-sand-deep rounded-xl">
                  <Folder className="w-5 h-5 text-leaf" />
                </div>
                <div>
                  <p className="text-sm text-ink-soft">Total Projects</p>
                  <p className="text-2xl font-bold text-ink">{projects.length}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-sand p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-leaf-wash rounded-xl">
                  <CheckCircle className="w-5 h-5 text-leaf" />
                </div>
                <div>
                  <p className="text-sm text-ink-soft">Active</p>
                  <p className="text-2xl font-bold text-ink">
                    {projects.filter(p => p.status === 'active').length}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-sand p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-sky-wash rounded-xl">
                  <Bot className="w-5 h-5 text-azure" />
                </div>
                <div>
                  <p className="text-sm text-ink-soft">Agents Assigned</p>
                  <p className="text-2xl font-bold text-ink">
                    {projects.reduce((sum, p) => sum + (p.agents?.length || 0), 0)}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-sand p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-sand-deep rounded-xl">
                  <Pause className="w-5 h-5 text-warn" />
                </div>
                <div>
                  <p className="text-sm text-ink-soft">On Hold</p>
                  <p className="text-2xl font-bold text-ink">
                    {projects.filter(p => p.status === 'on_hold').length}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Search */}
          {projects.length > 0 && (
            <div className="relative">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-ash" />
              <input
                type="text"
                placeholder="Search projects…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-4 py-3 bg-white border border-line rounded-xl focus:ring-2 focus:ring-ink focus:border-transparent shadow-sm"
              />
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 bg-blush-wash border border-blush rounded-xl p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-danger" />
              <p className="text-danger">{error}</p>
            </div>
          </div>
        )}

        {/* Projects Grid */}
        {filteredProjects.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-sm border border-sand p-12 text-center">
            <div className="w-32 h-32 mx-auto mb-6 relative">
              <div className="absolute inset-0 bg-blush-wash rounded-2xl transform rotate-6"></div>
              <div className="absolute inset-0 bg-white rounded-2xl shadow-sm border border-sand flex items-center justify-center">
                <Folder className="w-12 h-12 text-leaf" />
              </div>
            </div>
            <h3 className="text-xl font-semibold text-ink mb-2">
              {projects.length === 0 ? 'No projects yet' : 'No results found'}
            </h3>
            <p className="text-ink-soft mb-6 max-w-md mx-auto">
              {projects.length === 0
                ? 'Create projects to organize your agents and share context between them.'
                : 'Try adjusting your search.'}
            </p>
            {projects.length === 0 && (
              <button
                onClick={openCreateModal}
                className="inline-flex items-center gap-2 px-6 py-3 bg-ink hover:bg-ink/85 text-white rounded-xl transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm hover:shadow-md font-medium"
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
                className="bg-white rounded-xl shadow-sm border border-sand hover:shadow-md transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:border-blush group"
              >
                <div className="p-5">
                  <div className="flex items-start gap-3 mb-4">
                    <div className="p-2.5 bg-sand-deep rounded-xl group-hover:bg-blush transition-colors">
                      <Folder className="w-5 h-5 text-leaf" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-ink truncate">
                        {project.name}
                      </h3>
                      <p className="text-sm text-ink-mute line-clamp-2 mt-1">
                        {project.description || 'No description'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 mb-4 flex-wrap">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${getStatusStyle(project.status)}`}>
                      {getStatusIcon(project.status)}
                      {STATUS_OPTIONS.find(o => o.value === project.status)?.label || project.status}
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-sky-wash text-azure">
                      <Bot className="w-3.5 h-3.5" />
                      {project.agents?.length || 0} agents
                    </span>
                  </div>

                  {/* External Links */}
                  {Object.keys(project.external_project_ref || {}).length > 0 && (
                    <div className="flex items-center gap-2 mb-4 flex-wrap">
                      {project.external_project_ref?.jira && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-sky-wash text-azure rounded text-xs">
                          <ExternalLink className="w-3 h-3" />
                          Jira
                        </span>
                      )}
                      {project.external_project_ref?.github && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-sand text-ink-soft rounded text-xs">
                          <ExternalLink className="w-3 h-3" />
                          GitHub
                        </span>
                      )}
                      {project.external_project_ref?.clickup && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-sand-deep text-ink-soft rounded text-xs">
                          <ExternalLink className="w-3 h-3" />
                          ClickUp
                        </span>
                      )}
                    </div>
                  )}

                  <div className="flex items-center gap-2 text-xs text-ink-mute mb-4">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Updated {formatDate(project.updated_at)}</span>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => setShowAgentModal(project)}
                      className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-danger rounded-lg hover:bg-danger transition-colors"
                    >
                      <Bot className="w-4 h-4" />
                      Agents
                    </button>
                    <button
                      onClick={() => openEditModal(project)}
                      className="inline-flex items-center justify-center px-3 py-2.5 text-sm font-medium text-ink-soft bg-sand rounded-lg hover:bg-line transition-colors"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => openDeleteModal(project)}
                      className="inline-flex items-center justify-center px-3 py-2.5 text-sm font-medium text-danger bg-blush-wash rounded-lg hover:bg-blush-wash transition-colors"
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
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-[1.9rem] border border-line bg-white shadow-soft">
            <div className="sticky top-0 flex items-center justify-between border-b border-sand-deep bg-cream/95 px-6 py-4">
              <h3 className="text-lg font-semibold text-ink">
                {showEditModal ? 'Edit Project' : 'Create Project'}
              </h3>
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setShowEditModal(null)
                }}
                className="rounded-[0.9rem] p-2 transition-colors hover:bg-sand"
              >
                <X className="w-5 h-5 text-ink-mute" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-ink-soft mb-1">Project Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Mobile App Redesign"
                  className="w-full rounded-[1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink placeholder-ash focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-ink-soft mb-1">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe the project…"
                  rows={3}
                  className="w-full rounded-[1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink placeholder-ash focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-ink-soft mb-1">Status</label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="w-full rounded-[1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint"
                >
                  {STATUS_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-ink-soft mb-1">Project Management Tool</label>
                <select
                  value={formData.project_management}
                  onChange={(e) => setFormData({ ...formData, project_management: e.target.value })}
                  className="w-full rounded-[1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint"
                >
                  <option value="">None</option>
                  <option value="jira">Jira</option>
                  <option value="clickup">ClickUp</option>
                  <option value="github">GitHub</option>
                </select>
                <p className="mt-1 text-xs text-ink-mute">Select the project management tool used for this project</p>
              </div>
            </div>

            <div className="sticky bottom-0 flex justify-end gap-3 border-t border-sand-deep bg-cream/95 px-6 py-4">
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setShowEditModal(null)
                }}
                disabled={saving}
                className="rounded-[0.95rem] bg-sand-deep px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-line disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 rounded-[0.95rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full motion-safe:animate-spin" />
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
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-[1.9rem] border border-line bg-white shadow-soft">
            <div className="sticky top-0 flex items-center justify-between border-b border-sand-deep bg-cream/95 px-6 py-4">
              <h3 className="text-lg font-semibold text-ink">
                Manage Agents - {showAgentModal.name}
              </h3>
              <button
                onClick={() => setShowAgentModal(null)}
                className="rounded-[0.9rem] p-2 transition-colors hover:bg-sand"
              >
                <X className="w-5 h-5 text-ink-mute" />
              </button>
            </div>

            <div className="p-6">
              <div className="mb-6">
                <h4 className="text-sm font-medium text-ink-soft mb-3">Assigned Agents</h4>
                {showAgentModal.agents?.length > 0 ? (
                  <div className="space-y-2">
                    {showAgentModal.agents.map((agent) => (
                      <div key={agent.id} className="flex items-center justify-between rounded-[1rem] border border-black/5 bg-cream p-3">
                        <div className="flex items-center gap-3">
                          <Bot className="w-5 h-5 text-ash" />
                          <span className="text-sm font-medium text-ink">{agent.agent_name}</span>
                        </div>
                        <button
                          onClick={() => removeAgentFromProject(showAgentModal.id, agent.id)}
                        className="text-sm font-semibold text-wine hover:text-wine"
                      >
                        Remove
                      </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-ink-mute text-center py-4">No agents assigned yet</p>
                )}
              </div>

              <div>
                <h4 className="text-sm font-medium text-ink-soft mb-3">Add Agent</h4>
                <p className="text-xs text-ink-mute mb-3">
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
                        className="w-full rounded-[1rem] border border-black/10 bg-white/85 p-3 text-left transition-colors hover:bg-paper disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Bot className="w-5 h-5 text-ash" />
                        <span className="text-sm font-medium text-ink">{agent.agent_name}</span>
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
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-md rounded-[1.9rem] border border-line bg-white p-6 shadow-soft">
            <div className="flex items-center gap-3 mb-4">
              <div className="rounded-xl bg-cream p-2.5">
                <Trash2 className="w-6 h-6 text-wine" />
              </div>
              <h3 className="text-lg font-semibold text-ink">Delete Project</h3>
            </div>

            <p className="text-ink-soft mb-6">
              Are you sure you want to delete <span className="font-semibold text-ink">"{deleteModal.project.name}"</span>?
              This will remove all agent associations and shared context.
            </p>

            <div className="flex gap-3 justify-end">
              <button
                onClick={closeDeleteModal}
                disabled={deleting}
                className="rounded-[0.95rem] bg-sand-deep px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-line disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="flex items-center gap-2 rounded-[0.95rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
              >
                {deleting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full motion-safe:animate-spin" />
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
