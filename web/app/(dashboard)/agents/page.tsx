'use client'

import { useState, useEffect, useRef, useDeferredValue, type CSSProperties, type MouseEvent as ReactMouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import {
  Plus, Trash2, Bot, Users, MoreVertical,
  Settings, Copy, Globe, Lock, Activity, Search, Sparkles, ChevronDown
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
  slug: string
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

const formatNumber = (num: number): string => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

const formatDate = (value: string): string => {
  if (!value) return 'Recently'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value))
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

  const style: CSSProperties = {
    position: 'fixed',
    top: anchorRect.bottom + 4,
    right: window.innerWidth - anchorRect.right,
    width: 176,
    zIndex: 9999,
  }

  return createPortal(
    <div
      ref={menuRef}
      style={style}
      className="rounded-[0.45rem] border border-black/[0.08] bg-[rgba(255,255,255,0.84)] py-1.5 shadow-[0_18px_40px_rgba(0,0,0,0.12)] backdrop-blur-xl"
    >
      <button
        onClick={() => { router.push(`/agents/${agent.slug}/edit`); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-black/5"
      >
        <Settings size={15} className="text-gray-400" />
        Edit
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.slug}/landing-page`); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-black/5"
      >
        <Globe size={15} className="text-[#ff5f8f]" />
        Landing Page
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.slug}/sub-agents`); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-black/5"
      >
        <Users size={15} className="text-gray-400" />
        Sub-Agents
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.slug}/clone`); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-black/5"
      >
        <Copy size={15} className="text-gray-400" />
        Duplicate
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.slug}/lens`); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-black/5"
      >
        <Activity size={15} className="text-indigo-400" />
        Lens
      </button>
      <div className="my-1.5 h-px bg-black/[0.08]" />
      <button
        onClick={() => { onDelete(); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
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
  onDelete: (agent: { id: string; name: string }) => void
}) => {
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null)
  const btnRef = useRef<HTMLButtonElement>(null)
  const hasAvatar = Boolean(agent.avatar)

  const handleMenuToggle = (e: ReactMouseEvent<HTMLButtonElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (!menuOpen && btnRef.current) {
      setAnchorRect(btnRef.current.getBoundingClientRect())
    }
    setMenuOpen(!menuOpen)
  }

  return (
    <div className="flex flex-col overflow-hidden rounded-[0.5rem] border border-black/10 bg-white/60 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_24px_56px_rgba(0,0,0,0.08)]">
      <div className="relative flex min-h-[16rem] items-center justify-center overflow-hidden border-b border-black/10 bg-[linear-gradient(180deg,#efe7d8_0%,#f3ecdf_100%)] md:min-h-[18.5rem]">
        {hasAvatar ? (
          <>
            <img
              src={agent.avatar || undefined}
              alt={agent.agent_name}
              className="absolute inset-0 h-full w-full object-cover object-center"
            />
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_24%,rgba(255,255,255,0.22),transparent_42%)]" />
            <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(243,236,223,0.08),rgba(243,236,223,0.04)_45%,rgba(255,255,255,0.1))]" />
          </>
        ) : (
          <>
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_26%,rgba(255,255,255,0.78),transparent_32%)]" />
            <div className="pointer-events-none absolute inset-0 opacity-60 [background-image:linear-gradient(90deg,rgba(189,164,125,0.08)_0,rgba(189,164,125,0.08)_8%,transparent_8%,transparent_16%)] [background-size:160px_100%]" />
            <div className="relative z-10 flex h-[7.75rem] w-[7.75rem] items-center justify-center rounded-[0.4rem] border border-white/90 bg-[#fcfbf8] shadow-[0_22px_40px_rgba(109,84,55,0.16)] md:h-[9.25rem] md:w-[9.25rem]">
              <Sparkles className="h-10 w-10 text-[#2d8b69] md:h-12 md:w-12" />
            </div>
          </>
        )}

        <div className="absolute right-5 top-5 z-20">
          <button
            ref={btnRef}
            onClick={handleMenuToggle}
            className="flex h-10 w-10 items-center justify-center rounded-[0.35rem] border border-black/10 bg-white/88 shadow-[0_8px_20px_rgba(0,0,0,0.08)] transition-colors hover:bg-white"
          >
            <MoreVertical className="h-4 w-4 text-gray-500" />
          </button>
          {menuOpen && anchorRect && (
            <DropdownMenu
              agent={agent}
              onDelete={() => onDelete({ id: agent.id, name: agent.agent_name })}
              onClose={() => setMenuOpen(false)}
              anchorRect={anchorRect}
            />
          )}
        </div>
      </div>

      <div className="flex flex-1 flex-col p-6">
        <div className="mb-2 flex items-start justify-between gap-3">
          <h3 className="line-clamp-2 text-[1.35rem] font-semibold leading-tight tracking-[-0.04em] text-[#171717]">
            {agent.agent_name}
          </h3>
          <div className="flex shrink-0 items-center gap-1.5 text-[#7a736a]">
            {agent.is_public ? <Globe className="h-4 w-4 text-[#2d8b69]" /> : <Lock className="h-4 w-4" />}
            <span className="text-[11px] font-semibold uppercase tracking-[0.16em]">
              {agent.is_public ? 'Public' : 'Private'}
            </span>
          </div>
        </div>

        <p className="mb-3 text-sm uppercase tracking-[0.16em] text-[#7a736a]">
          {agent.category || agent.agent_type || 'AI Agent'}
        </p>

        <p className="mb-4 line-clamp-2 text-sm leading-relaxed text-[#575149]">
          {agent.description || 'No description provided'}
        </p>

        <p className="text-xs text-[#7a736a]">
          Created {formatDate(agent.created_at)}
        </p>

        <div className="my-4 border-t border-black/10" />

        <div className="mb-5 flex items-center gap-6">
          <div>
            <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Uses</p>
            <p className="text-xl font-semibold text-[#171717]">{formatNumber(agent.execution_count || 0)}</p>
          </div>
          <div>
            <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Success</p>
            <p className="text-xl font-semibold text-[#171717]">{(agent.success_rate || 0).toFixed(0)}%</p>
          </div>
          <div>
            <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Team</p>
            <p className="text-xl font-semibold text-[#171717]">{agent.sub_agents_count || 0}</p>
          </div>
        </div>

        <div className="mt-auto flex items-center gap-3">
          <button
            onClick={() => router.push(`/agents/${agent.slug}/chat`)}
            className="flex-1 rounded-[0.35rem] border border-black/15 bg-white/70 px-5 py-2.5 text-center text-sm font-semibold uppercase tracking-[0.14em] text-[#171717] transition-colors hover:bg-white"
          >
            Start Chat
          </button>
          <button
            onClick={() => router.push(`/agents/${agent.slug}/view`)}
            className="px-4 py-2.5 text-sm font-medium text-[#7a736a] transition-colors hover:text-[#171717]"
          >
            View Details
          </button>
          <a
            href={`/a/${agent.public_slug || slugify(agent.agent_name)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex h-10 w-10 items-center justify-center rounded-[0.35rem] border border-black/10 bg-white/70 text-[#7a736a] transition-colors hover:bg-white hover:text-[#171717]"
            title="View public page"
          >
            <Globe className="h-4 w-4" />
          </a>
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
  const [agentToDelete, setAgentToDelete] = useState<{ id: string; name: string } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<'all' | 'active' | 'workflow' | 'public'>('all')

  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(9)
  const [totalPages, setTotalPages] = useState(1)

  // Debounce the search term so we don't fire a request on every keystroke
  const deferredSearch = useDeferredValue(searchQuery)

  useEffect(() => {
    // Reset to page 1 when search changes
    setCurrentPage(1)
  }, [deferredSearch])

  useEffect(() => {
    fetchAgents(deferredSearch)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage, deferredSearch])

  const fetchAgents = async (search?: string) => {
    try {
      setLoading(true)
      const response = await apiClient.getAgents(currentPage, pageSize, search || undefined)
      const agentsList = response.agents_list || []
      const pagination = response.pagination || {}

      setAgents(agentsList)
      setTotalPages(pagination.total_pages || 1)
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
      await apiClient.deleteAgent(agentToDelete.id)
      toast.success('Agent deleted')
      setShowDeleteModal(false)
      setAgentToDelete(null)
      fetchAgents(deferredSearch)
    } catch (error) {
      console.error('Failed to delete agent:', error)
      toast.error('Failed to delete agent')
    }
  }

  // Filter is now server-side for search. Client-side filter only handles
  // sub-agent exclusion and the type dropdown (active/workflow/public).
  const filteredAgents = agents.filter((agent) => {
    if (agent.is_sub_agent) return false
    const matchesFilter =
      filterType === 'all' ? true :
      filterType === 'active' ? (agent.status === 'ACTIVE' || agent.status === 'idle') :
      filterType === 'workflow' ? agent.workflow_type !== null :
      filterType === 'public' ? agent.is_public : true
    return matchesFilter
  })

  // Only count parent/standalone agents (exclude sub-agents)
  const parentAgents = agents.filter(a => !a.is_sub_agent)
  const activeCount = parentAgents.filter(a => a.status === 'ACTIVE' || a.status === 'idle').length
  const workflowCount = parentAgents.filter(a => a.workflow_type).length
  const publicCount = parentAgents.filter(a => a.is_public).length
  const parentAgentCount = parentAgents.length

  return (
    <div className="min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
      <div className="mx-auto max-w-[90rem]">
        <div className="dashboard-surface mb-6 p-5 md:p-6 xl:p-7">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/70 px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6e675d]">
                <Sparkles className="h-3 w-3 text-[#ff5f8f]" />
                Agent Library
              </div>
              <h1 className="text-[1.8rem] font-semibold tracking-[-0.05em] text-[#171717] md:text-[2.65rem]">
                <span className="editorial-highlight">Agents</span>
              </h1>
              <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-[#5b564e] md:text-[15px]">
                {parentAgentCount} agents, {activeCount} active, and {publicCount} public. Search, filter, and jump directly into the ones doing the work.
              </p>
            </div>
            <button
              onClick={() => router.push('/agents/create')}
              className="inline-flex flex-shrink-0 items-center gap-2 rounded-[0.35rem] bg-[#181818] px-5 py-3 text-[13px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 md:text-[14px]"
            >
              <Plus size={18} />
              <span className="hidden sm:inline">New Agent</span>
              <span className="sm:hidden">New</span>
            </button>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{parentAgentCount} total</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{activeCount} active</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{workflowCount} workflows</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{publicCount} public</div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8a8378]" />
              <input
                type="text"
                placeholder="Search agents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-[0.35rem] border border-black/10 bg-white/[0.72] py-3 pl-11 pr-4 text-[13px] text-[#171717] outline-none transition-all focus:border-[#ff5f8f] focus:ring-2 focus:ring-[#ff5f8f]/20 md:text-[14px]"
              />
            </label>

            <label className="relative block">
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value as any)}
                className="w-full appearance-none rounded-[0.35rem] border border-black/10 bg-white/[0.72] px-4 py-3 pr-12 text-[13px] text-[#171717] outline-none transition-all focus:border-[#ff5f8f] focus:ring-2 focus:ring-[#ff5f8f]/20 md:text-[14px]"
              >
                <option value="all">All</option>
                <option value="active">Active</option>
                <option value="public">Public</option>
                <option value="workflow">Workflows</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#5b564e]" />
            </label>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="animate-pulse overflow-hidden rounded-[0.5rem] border border-black/10 bg-white/60 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
                <div className="flex items-center justify-center border-b border-black/10 bg-[#efe7d8] pt-10 pb-12">
                  <div className="h-24 w-24 rounded-[0.45rem] bg-white shadow-lg" />
                </div>
                <div className="p-6">
                  <div className="mb-2 h-5 w-40 rounded bg-black/10" />
                  <div className="mb-3 h-4 w-28 rounded bg-black/5" />
                  <div className="mb-2 h-4 w-full rounded bg-black/5" />
                  <div className="mb-4 h-4 w-3/4 rounded bg-black/5" />
                  <div className="mb-4 h-3 w-24 rounded bg-black/5" />
                  <div className="mb-5 border-t border-black/10 pt-4">
                    <div className="flex gap-6">
                      <div>
                        <div className="mb-1 h-3 w-10 rounded bg-black/5" />
                        <div className="h-6 w-8 rounded bg-black/10" />
                      </div>
                      <div>
                        <div className="mb-1 h-3 w-12 rounded bg-black/5" />
                        <div className="h-6 w-10 rounded bg-black/10" />
                      </div>
                      <div>
                        <div className="mb-1 h-3 w-12 rounded bg-black/5" />
                        <div className="h-6 w-8 rounded bg-black/10" />
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="h-10 flex-1 rounded-[0.35rem] bg-black/5" />
                    <div className="h-10 w-24 rounded-[0.35rem] bg-black/5" />
                    <div className="h-10 w-10 rounded-[0.35rem] bg-black/5" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filteredAgents.length === 0 ? (
          <div className="dashboard-surface py-20 text-center">
            <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-[0.45rem] bg-[#ffe1ea]">
              <Bot className="h-10 w-10 text-[#171717]" />
            </div>
            <h3 className="mb-2 text-[1.05rem] font-semibold text-[#171717] md:text-[1.35rem]">
              {searchQuery || filterType !== 'all' ? 'No matching agents' : 'No agents yet'}
            </h3>
            <p className="mb-6 text-[13px] text-[#6c655c] md:text-[14px]">
              {searchQuery || filterType !== 'all'
                ? 'Try adjusting your search or filter'
                : 'Create your first AI agent to get started'}
            </p>
            {!searchQuery && filterType === 'all' && (
              <button
                onClick={() => router.push('/agents/create')}
                className="inline-flex items-center gap-2 rounded-[0.35rem] bg-[#181818] px-6 py-3 text-[13px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 md:text-[14px]"
              >
                <Plus size={20} />
                Create Agent
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
              {filteredAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  onDelete={(agentToRemove) => {
                    setAgentToDelete(agentToRemove)
                    setShowDeleteModal(true)
                  }}
                />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="dashboard-surface mt-8 flex items-center justify-center gap-4 px-4 py-3">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="rounded-[0.35rem] px-4 py-2 text-[13px] font-medium text-[#5b564e] transition-colors hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-[13px] text-[#6c655c]">
                  {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="rounded-[0.35rem] px-4 py-2 text-[13px] font-medium text-[#5b564e] transition-colors hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
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
          <div className="dashboard-surface w-full max-w-sm p-6">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-[0.35rem] bg-[#ffe1ea]">
              <Trash2 className="w-6 h-6 text-red-600" />
            </div>
            <h3 className="mb-2 text-center text-[1rem] font-semibold text-[#171717] md:text-[1.1rem]">
              Delete Agent
            </h3>
            <p className="mb-6 text-center text-[13px] text-[#6c655c] md:text-[14px]">
              Delete <strong className="text-[#171717]">{agentToDelete.name}</strong>? This cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => { setShowDeleteModal(false); setAgentToDelete(null) }}
                className="flex-1 rounded-[0.35rem] bg-white/70 px-4 py-2 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAgent}
                className="flex-1 rounded-[0.35rem] bg-[#181818] px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-black"
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
