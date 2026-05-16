'use client'

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import {
  AlertTriangle,
  Search,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Bot,
  User,
  MessageSquare,
  Filter,
  Eye,
  X,
  Send
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface Escalation {
  id: string
  project_id: string
  project: { id: string; name: string } | null
  conversation_id: string
  from_agent_id: string
  from_agent: { id: string; agent_name: string } | null
  to_human_id: string
  to_human: { id: string; name: string; email: string } | null
  reason: string
  priority: string
  subject: string
  message: string
  context_summary: string
  status: string
  notification_channels: Record<string, boolean>
  notification_sent_at: string | null
  human_response: string | null
  resolved_at: string | null
  resolution_notes: string | null
  expires_at: string | null
  created_at: string
  updated_at: string
}

const STATUS_OPTIONS = [
  { value: 'all', label: 'All Status' },
  { value: 'pending', label: 'Pending' },
  { value: 'notified', label: 'Notified' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'expired', label: 'Expired' },
]

const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Low', color: 'bg-gray-100 text-gray-700' },
  { value: 'medium', label: 'Medium', color: 'bg-blue-100 text-blue-700' },
  { value: 'high', label: 'High', color: 'bg-amber-100 text-amber-700' },
  { value: 'urgent', label: 'Urgent', color: 'bg-red-100 text-red-700' },
]

const REASON_OPTIONS = [
  { value: 'uncertainty', label: 'Uncertainty' },
  { value: 'approval_needed', label: 'Approval Needed' },
  { value: 'complex_decision', label: 'Complex Decision' },
  { value: 'blocker', label: 'Blocker' },
  { value: 'review_required', label: 'Review Required' },
]

export default function EscalationsPage() {
  const [escalations, setEscalations] = useState<Escalation[]>([])
  const [filteredEscalations, setFilteredEscalations] = useState<Escalation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [showDetailModal, setShowDetailModal] = useState<Escalation | null>(null)
  const [showResolveModal, setShowResolveModal] = useState<Escalation | null>(null)
  const [resolving, setResolving] = useState(false)
  const [responseText, setResponseText] = useState('')

  useEffect(() => {
    fetchEscalations()
  }, [statusFilter])

  useEffect(() => {
    filterEscalations()
  }, [searchQuery, escalations])

  const fetchEscalations = async () => {
    try {
      setLoading(true)
      const params: Record<string, string> = {}
      if (statusFilter !== 'all') {
        params.status = statusFilter
      }
      const data = await apiClient.getEscalations(params)
      setEscalations(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      toast.error('Failed to load escalations')
    } finally {
      setLoading(false)
    }
  }

  const filterEscalations = () => {
    let filtered = escalations
    if (searchQuery) {
      filtered = filtered.filter(esc =>
        esc.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
        esc.message?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        esc.from_agent?.agent_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        esc.to_human?.name?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    setFilteredEscalations(filtered)
  }

  const handleResolve = async () => {
    if (!showResolveModal || !responseText.trim()) {
      toast.error('Please provide a response')
      return
    }

    setResolving(true)
    try {
      await apiClient.resolveEscalation(showResolveModal.id, responseText)
      toast.success('Escalation resolved')
      setShowResolveModal(null)
      setResponseText('')
      fetchEscalations()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to resolve escalation')
    } finally {
      setResolving(false)
    }
  }

  const getStatusStyle = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-amber-100 text-amber-700',
      notified: 'bg-blue-100 text-blue-700',
      in_progress: 'bg-purple-100 text-purple-700',
      resolved: 'bg-emerald-100 text-emerald-700',
      expired: 'bg-gray-100 text-gray-600',
    }
    return styles[status] || 'bg-gray-100 text-gray-600'
  }

  const getStatusIcon = (status: string) => {
    const icons: Record<string, any> = {
      pending: Clock,
      notified: AlertTriangle,
      in_progress: Clock,
      resolved: CheckCircle,
      expired: XCircle,
    }
    const Icon = icons[status] || Clock
    return <Icon className="w-3.5 h-3.5" />
  }

  const getPriorityStyle = (priority: string) => {
    const option = PRIORITY_OPTIONS.find(o => o.value === priority)
    return option?.color || 'bg-gray-100 text-gray-700'
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const pendingCount = escalations.filter(e => e.status === 'pending' || e.status === 'notified').length
  const resolvedCount = escalations.filter(e => e.status === 'resolved').length
  const urgentCount = escalations.filter(e => e.priority === 'urgent' && e.status !== 'resolved').length

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading escalations...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Escalations</h1>
              <p className="text-gray-600 mt-1">
                Review and respond to agent escalation requests
              </p>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-red-100 rounded-xl">
                  <AlertTriangle className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Total</p>
                  <p className="text-2xl font-bold text-gray-900">{escalations.length}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-amber-100 rounded-xl">
                  <Clock className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Pending</p>
                  <p className="text-2xl font-bold text-gray-900">{pendingCount}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-red-100 rounded-xl">
                  <AlertCircle className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Urgent</p>
                  <p className="text-2xl font-bold text-gray-900">{urgentCount}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-emerald-100 rounded-xl">
                  <CheckCircle className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Resolved</p>
                  <p className="text-2xl font-bold text-gray-900">{resolvedCount}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className="flex gap-4 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search escalations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-4 py-3 bg-white border border-gray-200 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-transparent shadow-sm"
              />
            </div>
            <div className="relative">
              <Filter className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="pl-12 pr-8 py-3 bg-white border border-gray-200 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-transparent shadow-sm appearance-none cursor-pointer"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
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

        {/* Escalations List */}
        {filteredEscalations.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-12 text-center">
            <div className="w-32 h-32 mx-auto mb-6 relative">
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-100 to-emerald-50 rounded-2xl transform rotate-6"></div>
              <div className="absolute inset-0 bg-white rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center">
                <CheckCircle className="w-12 h-12 text-emerald-500" />
              </div>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {escalations.length === 0 ? 'No escalations' : 'No results found'}
            </h3>
            <p className="text-gray-600 max-w-md mx-auto">
              {escalations.length === 0
                ? 'All clear! No escalations require your attention right now.'
                : 'Try adjusting your search or filter.'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredEscalations.map((escalation) => (
              <div
                key={escalation.id}
                className={`bg-white rounded-xl shadow-sm border transition-all hover:shadow-md ${
                  escalation.priority === 'urgent' && escalation.status !== 'resolved'
                    ? 'border-red-200 hover:border-red-300'
                    : 'border-gray-100 hover:border-red-200'
                }`}
              >
                <div className="p-5">
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${getStatusStyle(escalation.status)}`}>
                          {getStatusIcon(escalation.status)}
                          {escalation.status.replace('_', ' ')}
                        </span>
                        <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${getPriorityStyle(escalation.priority)}`}>
                          {escalation.priority}
                        </span>
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                          {REASON_OPTIONS.find(r => r.value === escalation.reason)?.label || escalation.reason}
                        </span>
                      </div>
                      <h3 className="text-lg font-semibold text-gray-900 truncate">
                        {escalation.subject}
                      </h3>
                    </div>
                    <span className="text-xs text-gray-500 whitespace-nowrap">
                      {formatDate(escalation.created_at)}
                    </span>
                  </div>

                  <p className="text-sm text-gray-600 line-clamp-2 mb-4">
                    {escalation.message}
                  </p>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <div className="flex items-center gap-1.5">
                        <Bot className="w-4 h-4" />
                        <span>{escalation.from_agent?.agent_name || 'Unknown agent'}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <User className="w-4 h-4" />
                        <span>{escalation.to_human?.name || 'Unknown contact'}</span>
                      </div>
                      {escalation.project && (
                        <div className="flex items-center gap-1.5">
                          <span className="text-gray-400">|</span>
                          <span>{escalation.project.name}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={() => setShowDetailModal(escalation)}
                        className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                      >
                        <Eye className="w-4 h-4" />
                        View
                      </button>
                      {escalation.status !== 'resolved' && (
                        <button
                          onClick={() => {
                            setShowResolveModal(escalation)
                            setResponseText('')
                          }}
                          className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
                        >
                          <MessageSquare className="w-4 h-4" />
                          Respond
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {showDetailModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Escalation Details</h3>
              <button
                onClick={() => setShowDetailModal(null)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${getStatusStyle(showDetailModal.status)}`}>
                  {getStatusIcon(showDetailModal.status)}
                  {showDetailModal.status.replace('_', ' ')}
                </span>
                <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${getPriorityStyle(showDetailModal.priority)}`}>
                  {showDetailModal.priority}
                </span>
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                  {REASON_OPTIONS.find(r => r.value === showDetailModal.reason)?.label || showDetailModal.reason}
                </span>
              </div>

              <div>
                <h4 className="text-xl font-semibold text-gray-900 mb-2">{showDetailModal.subject}</h4>
                <p className="text-gray-600">{showDetailModal.message}</p>
              </div>

              {showDetailModal.context_summary && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h5 className="text-sm font-medium text-gray-700 mb-2">Context Summary</h5>
                  <p className="text-sm text-gray-600">{showDetailModal.context_summary}</p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">From Agent:</span>
                  <p className="font-medium text-gray-900">{showDetailModal.from_agent?.agent_name || 'Unknown'}</p>
                </div>
                <div>
                  <span className="text-gray-500">To Human:</span>
                  <p className="font-medium text-gray-900">{showDetailModal.to_human?.name || 'Unknown'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Project:</span>
                  <p className="font-medium text-gray-900">{showDetailModal.project?.name || 'None'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Created:</span>
                  <p className="font-medium text-gray-900">{new Date(showDetailModal.created_at).toLocaleString()}</p>
                </div>
              </div>

              {showDetailModal.human_response && (
                <div className="bg-emerald-50 rounded-lg p-4">
                  <h5 className="text-sm font-medium text-emerald-700 mb-2">Human Response</h5>
                  <p className="text-sm text-emerald-900">{showDetailModal.human_response}</p>
                  {showDetailModal.resolved_at && (
                    <p className="text-xs text-emerald-600 mt-2">
                      Resolved at {new Date(showDetailModal.resolved_at).toLocaleString()}
                    </p>
                  )}
                </div>
              )}

              {showDetailModal.status !== 'resolved' && (
                <button
                  onClick={() => {
                    setShowDetailModal(null)
                    setShowResolveModal(showDetailModal)
                    setResponseText('')
                  }}
                  className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
                >
                  <MessageSquare className="w-4 h-4" />
                  Respond to Escalation
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Resolve Modal */}
      {showResolveModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full">
            <div className="border-b border-gray-100 px-6 py-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Respond to Escalation</h3>
              <button
                onClick={() => setShowResolveModal(null)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="p-6">
              <div className="mb-4 p-4 bg-gray-50 rounded-lg">
                <p className="text-sm font-medium text-gray-900 mb-1">{showResolveModal.subject}</p>
                <p className="text-sm text-gray-600 line-clamp-2">{showResolveModal.message}</p>
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Your Response *</label>
                <textarea
                  value={responseText}
                  onChange={(e) => setResponseText(e.target.value)}
                  placeholder="Provide guidance or answer the agent's question..."
                  rows={5}
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent resize-none"
                />
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowResolveModal(null)}
                  disabled={resolving}
                  className="px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleResolve}
                  disabled={resolving || !responseText.trim()}
                  className="px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {resolving ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      Send Response
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
