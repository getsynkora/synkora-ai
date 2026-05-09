'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import {
  Plus, Trash2, MessageSquare, Bot, Users, MoreVertical,
  Eye, Star, ArrowRight, GitBranch, RotateCw, Settings, Copy,
  Globe, Lock
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface SubAgent {
  id: string
  sub_agent_id: string
  sub_agent_name: string
  sub_agent_type: string
  execution_order: number
  is_active: boolean
}

interface Agent {
  id: string
  agent_name: string
  public_slug?: string
  agent_type: string
  description: string | null
  avatar: string | null
  status: string
  workflow_type: string | null
  execution_count: number
  success_rate: number
  created_at: string
  sub_agents_count: number
  sub_agents: SubAgent[]
  is_public: boolean
  category: string | null
  tags: string[]
  is_sub_agent: boolean
}

const slugify = (text: string): string =>
  text.toLowerCase().trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '')

const getInitials = (name: string): string => {
  return name
    .split(/[-_\s]+/)
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

const formatNumber = (num: number): string => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

// Dropdown Menu — rendered via portal so it escapes card overflow/stacking
const DropdownMenu = ({
  agent,
  onDelete,
  onClose,
  anchorRect,
}: {
  agent: Agent
  onDelete: () => void
  onClose: () => void
  anchorRect: DOMRect
}) => {
  const router = useRouter()
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  const style: React.CSSProperties = {
    position: 'fixed',
    top: anchorRect.bottom + 4,
    right: window.innerWidth - anchorRect.right,
    width: 176,
    zIndex: 9999,
  }

  return createPortal(
    <div ref={menuRef} style={style} className="bg-white rounded-xl shadow-lg border border-gray-200 py-1.5">
      <button
        onClick={() => { router.push(`/agents/${agent.agent_name}/edit`); onClose() }}
        className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
      >
        <Settings size={15} className="text-gray-400" />
        Edit
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.agent_name}/landing-page`); onClose() }}
        className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
      >
        <Globe size={15} className="text-primary-500" />
        Landing Page
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.agent_name}/sub-agents`); onClose() }}
        className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
      >
        <Users size={15} className="text-gray-400" />
        Sub-Agents
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.agent_name}/clone`); onClose() }}
        className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
      >
        <Copy size={15} className="text-gray-400" />
        Duplicate
      </button>
      <div className="h-px bg-gray-100 my-1.5" />
      <button
        onClick={() => { onDelete(); onClose() }}
        className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
      >
        <Trash2 size={15} />
        Delete
      </button>
    </div>,
    document.body
  )
}

// Agent Card
const AgentCard = ({
  agent,
  onDelete
}: {
  agent: Agent
  onDelete: (name: string) => void
}) => {
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null)
  const btnRef = useRef<HTMLButtonElement>(null)

  const handleMenuToggle = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!menuOpen && btnRef.current) {
      setAnchorRect(btnRef.current.getBoundingClientRect())
    }
    setMenuOpen(!menuOpen)
  }

  return (
    <div className="bg-white rounded-3xl overflow-hidden shadow-sm hover:shadow-lg transition-shadow duration-300 flex flex-col">
      {/* Card Header */}
      <div className="relative h-44 overflow-hidden rounded-t-3xl flex items-center justify-center bg-gradient-to-br from-red-100 via-pink-50 to-orange-50">
        {agent.avatar ? (
          <>
            {/* Blurred background that matches the image colors */}
            <img
              src={agent.avatar}
              alt=""
              aria-hidden="true"
              className="absolute inset-0 w-full h-full object-cover scale-110 blur-2xl opacity-80"
            />
            {/* Main image */}
            <img
              src={agent.avatar}
              alt={agent.agent_name}
              className="relative z-10 h-full w-full object-contain object-bottom"
            />
          </>
        ) : (
          <div className="w-24 h-24 rounded-2xl bg-white shadow-lg flex items-center justify-center">
            <Bot className="w-12 h-12 text-primary-500" />
          </div>
        )}

        {/* Menu Button - Top Right */}
        <div className="absolute top-3 right-3 z-10">
          <button
            ref={btnRef}
            onClick={handleMenuToggle}
            className="w-8 h-8 rounded-full bg-white/60 hover:bg-white flex items-center justify-center transition-colors"
          >
            <MoreVertical className="w-4 h-4 text-gray-500" />
          </button>
          {menuOpen && anchorRect && (
            <DropdownMenu
              agent={agent}
              onDelete={() => onDelete(agent.agent_name)}
              onClose={() => setMenuOpen(false)}
              anchorRect={anchorRect}
            />
          )}
        </div>
      </div>

      {/* Content */}
      <div className="p-6 flex-1 flex flex-col">
        {/* Name and Rating */}
        <div className="flex items-start justify-between gap-3 mb-1">
          <h3 className="text-lg font-bold text-gray-900 line-clamp-1">
            {agent.agent_name}
          </h3>
          {agent.success_rate > 0 && (
            <div className="flex items-center gap-1 text-amber-500 flex-shrink-0">
              <Star className="w-4 h-4 fill-current" />
              <span className="font-semibold text-sm">{agent.success_rate.toFixed(1)}</span>
            </div>
          )}
        </div>

        {/* Category */}
        <p className="text-sm text-gray-400 mb-3">
          {agent.category || agent.agent_type || 'AI Agent'}
        </p>

        {/* Description */}
        <p className="text-sm text-gray-600 leading-relaxed line-clamp-2 mb-4">
          {agent.description || 'No description provided'}
        </p>

        {/* Divider */}
        <div className="border-t border-gray-100 my-4" />

        {/* Stats Row */}
        <div className="flex items-center gap-6 mb-5">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Chats</p>
            <p className="text-xl font-bold text-gray-900">{formatNumber(agent.execution_count || 0)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Success</p>
            <p className="text-xl font-bold text-gray-900">{(agent.success_rate || 0).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Sub-Agents</p>
            <p className="text-xl font-bold text-gray-900">{agent.sub_agents_count || 0}</p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 mt-auto">
          <button
            onClick={() => router.push(`/agents/${agent.agent_name}/chat`)}
            className="flex-1 px-5 py-2.5 border border-primary-300 text-primary-500 text-sm font-semibold rounded-xl hover:bg-primary-50 hover:border-primary-400 transition-colors"
          >
            Start Chat
          </button>
          <a
            href={`/a/${agent.public_slug || slugify(agent.agent_name)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2.5 text-gray-400 text-sm font-medium hover:text-primary-600 transition-colors"
            title="View public page"
          >
            <Globe className="w-4 h-4" />
          </a>
          <button
            onClick={() => router.push(`/agents/${agent.agent_name}/view`)}
            className="px-4 py-2.5 text-gray-400 text-sm font-medium hover:text-gray-600 transition-colors"
          >
            View Details
          </button>
        </div>
      </div>
    </div>
  )
}

export default function AgentsPage() {
  const router = useRouter()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [agentToDelete, setAgentToDelete] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<'all' | 'active' | 'workflow' | 'public'>('all')

  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(9)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)

  useEffect(() => {
    fetchAgents()
  }, [currentPage])

  const fetchAgents = async () => {
    try {
      setLoading(true)
      const response = await apiClient.getAgents(currentPage, pageSize)
      const agentsList = response.agents_list || []
      const pagination = response.pagination || {}

      setAgents(agentsList)
      setTotalPages(pagination.total_pages || 1)
      setTotalCount(pagination.total || 0)
    } catch (error) {
      console.error('Failed to fetch agents:', error)
      toast.error('Failed to load agents')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteAgent = async () => {
    if (!agentToDelete) return
    try {
      await apiClient.deleteAgent(agentToDelete)
      toast.success('Agent deleted')
      setShowDeleteModal(false)
      setAgentToDelete(null)
      fetchAgents()
    } catch (error) {
      console.error('Failed to delete agent:', error)
      toast.error('Failed to delete agent')
    }
  }

  // Filter out sub-agents (they are only accessible from parent agent)
  // and apply search/filter
  const filteredAgents = agents.filter((agent) => {
    // Skip sub-agents - they shouldn't appear as standalone cards
    if (agent.is_sub_agent) return false

    const matchesSearch = agent.agent_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (agent.description?.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (agent.tags?.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase())))
    const matchesFilter =
      filterType === 'all' ? true :
      filterType === 'active' ? (agent.status === 'ACTIVE' || agent.status === 'idle') :
      filterType === 'workflow' ? agent.workflow_type !== null :
      filterType === 'public' ? agent.is_public : true
    return matchesSearch && matchesFilter
  })

  // Only count parent/standalone agents (exclude sub-agents)
  const parentAgents = agents.filter(a => !a.is_sub_agent)
  const activeCount = parentAgents.filter(a => a.status === 'ACTIVE' || a.status === 'idle').length
  const workflowCount = parentAgents.filter(a => a.workflow_type).length
  const publicCount = parentAgents.filter(a => a.is_public).length
  const parentAgentCount = parentAgents.length

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50/60 via-white to-rose-50/40">
      <div className="max-w-7xl mx-auto px-4 md:px-6 py-6 md:py-8">
        {/* Header */}
        <div className="flex flex-col gap-4 mb-6 md:mb-8">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Agents</h1>
              <p className="text-gray-500 mt-0.5 text-sm">
                {parentAgentCount} agents · {activeCount} active · {publicCount} public
              </p>
            </div>
            <button
              onClick={() => router.push('/agents/create')}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors flex-shrink-0"
            >
              <Plus size={18} />
              <span className="hidden sm:inline">New Agent</span>
              <span className="sm:hidden">New</span>
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              placeholder="Search agents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 min-w-[140px] px-4 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />

            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value as any)}
              className="px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="all">All</option>
              <option value="active">Active</option>
              <option value="public">Public</option>
              <option value="workflow">Workflows</option>
            </select>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-white rounded-3xl overflow-hidden shadow-sm animate-pulse">
                {/* Header placeholder */}
                <div className="h-44 bg-gradient-to-br from-red-50 via-pink-50 to-orange-50" />
                {/* Content */}
                <div className="p-6">
                  <div className="h-5 bg-gray-200 rounded w-32 mb-2" />
                  <div className="h-4 bg-gray-100 rounded w-24 mb-4" />
                  <div className="h-4 bg-gray-100 rounded w-full mb-2" />
                  <div className="h-4 bg-gray-100 rounded w-3/4 mb-4" />
                  <div className="border-t border-gray-100 pt-4 mb-4">
                    <div className="flex gap-6">
                      <div>
                        <div className="h-3 bg-gray-100 rounded w-10 mb-1" />
                        <div className="h-6 bg-gray-200 rounded w-8" />
                      </div>
                      <div>
                        <div className="h-3 bg-gray-100 rounded w-12 mb-1" />
                        <div className="h-6 bg-gray-200 rounded w-10" />
                      </div>
                      <div>
                        <div className="h-3 bg-gray-100 rounded w-16 mb-1" />
                        <div className="h-6 bg-gray-200 rounded w-6" />
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-10 bg-gray-100 rounded-xl" />
                    <div className="h-10 bg-gray-50 rounded w-24" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filteredAgents.length === 0 ? (
          <div className="text-center py-20">
            <div className="w-20 h-20 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Bot className="w-10 h-10 text-primary-600" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {searchQuery || filterType !== 'all' ? 'No matching agents' : 'No agents yet'}
            </h3>
            <p className="text-gray-500 mb-6">
              {searchQuery || filterType !== 'all'
                ? 'Try adjusting your search or filter'
                : 'Create your first AI agent to get started'}
            </p>
            {!searchQuery && filterType === 'all' && (
              <button
                onClick={() => router.push('/agents/create')}
                className="inline-flex items-center gap-2 px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 transition-colors"
              >
                <Plus size={20} />
                Create Agent
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  onDelete={(name) => {
                    setAgentToDelete(name)
                    setShowDeleteModal(true)
                  }}
                />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-10">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-500">
                  {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Delete Modal */}
      {showDeleteModal && agentToDelete && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl">
            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Trash2 className="w-6 h-6 text-red-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 text-center mb-2">
              Delete Agent
            </h3>
            <p className="text-gray-500 text-center text-sm mb-6">
              Delete <strong className="text-gray-900">{agentToDelete}</strong>? This cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => { setShowDeleteModal(false); setAgentToDelete(null) }}
                className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAgent}
                className="flex-1 px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
