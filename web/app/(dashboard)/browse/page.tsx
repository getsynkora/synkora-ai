'use client'

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import {
  Search,
  Sparkles,
  Zap,
  Brain,
  TrendingUp,
  MessageSquare,
  Eye,
  Star,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  LayoutGrid,
  List,
  SlidersHorizontal,
  CheckCircle,
  Award,
} from 'lucide-react'
import toast from 'react-hot-toast'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface AgentPricing {
  model: string
  is_free: boolean
  credits_per_use?: number | null
  session_credits?: number | null
  daily_credits?: number | null
  weekly_credits?: number | null
  monthly_credits?: number | null
  trial_messages: number
}

interface PublicAgent {
  id: string
  agent_name: string
  description: string
  avatar?: string
  category: string
  tags: string[]
  likes_count: number
  dislikes_count: number
  usage_count: number
  model_name: string
  created_at: string
  user_rating?: 'like' | 'dislike' | null
  system_prompt?: string
  tools?: any[]
  provider?: string
  pricing?: AgentPricing | null
}

interface Category {
  category: string
  count: number
}

// Get icon based on category
const getCategoryIcon = (category: string, size: number = 32) => {
  const icons: Record<string, any> = {
    Productivity: Zap,
    Research: Search,
    Development: Brain,
    Writing: Eye,
    'Data Analysis': TrendingUp,
    'Customer Support': MessageSquare,
    Education: Star,
    Entertainment: Sparkles,
    Other: Sparkles,
  }
  const Icon = icons[category] || Sparkles
  return <Icon size={size} />
}

// Get rating from likes/dislikes
const getRating = (agent: PublicAgent) => {
  const total = agent.likes_count + agent.dislikes_count
  if (total === 0) return 4.5
  const ratio = agent.likes_count / total
  return Math.round((3 + ratio * 2) * 10) / 10
}

// Get badge type based on agent properties
const getBadge = (agent: PublicAgent) => {
  const rating = getRating(agent)
  if (rating >= 4.9) return { type: 'top_rated', label: 'TOP RATED' }
  if (agent.usage_count > 100) return { type: 'verified', label: 'VERIFIED' }
  return null
}

// Format pricing for display
const formatPricing = (pricing?: AgentPricing | null): { label: string; sub: string } => {
  if (!pricing || pricing.is_free || pricing.model === 'FREE') {
    return { label: 'Free', sub: '' }
  }
  switch (pricing.model) {
    case 'PER_USE':
      return { label: `${pricing.credits_per_use ?? '?'} cr`, sub: '/use' }
    case 'SESSION':
      return { label: `${pricing.session_credits ?? '?'} cr`, sub: '/session' }
    case 'DAILY':
      return { label: `${pricing.daily_credits ?? '?'} cr`, sub: '/day' }
    case 'WEEKLY':
      return { label: `${pricing.weekly_credits ?? '?'} cr`, sub: '/week' }
    case 'SUBSCRIPTION':
    case 'MONTHLY':
      return { label: `${pricing.monthly_credits ?? '?'} cr`, sub: '/mo' }
    default:
      return { label: 'Free', sub: '' }
  }
}

// Main categories from agent creation
const mainCategories = [
  'Productivity',
  'Research',
  'Development',
  'Writing',
  'Data Analysis',
  'Customer Support',
  'Education',
  'Entertainment',
  'Other',
]

export default function BrowsePage() {
  const router = useRouter()
  const [agents, setAgents] = useState<PublicAgent[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [sortBy, setSortBy] = useState<string>('popular')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 9

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await fetch(`${API_URL}/api/v1/agents/categories`)
        const data = await response.json()
        if (data.success) {
          const normalized = (data.data.categories || []).map((c: any) => ({
            category: c.category || c.name,
            count: c.count ?? 0,
          }))
          setCategories(normalized)
        }
      } catch (error) {
        console.error('Failed to fetch categories:', error)
      }
    }

    const fetchAgents = async () => {
      setLoading(true)
      try {
        const params = new URLSearchParams()
        if (selectedCategory) params.append('category', selectedCategory)
        if (searchQuery) params.append('search', searchQuery)
        if (sortBy) params.append('sort_by', sortBy)
        params.append('limit', '50')

        const response = await fetch(`${API_URL}/api/v1/agents/public?${params}`)
        const data = await response.json()
        if (data.success) {
          setAgents(data.data.agents)
        }
      } catch (error) {
        console.error('Failed to fetch agents:', error)
        toast.error('Failed to load agents')
      } finally {
        setLoading(false)
      }
    }

    void fetchCategories()
    void fetchAgents()
  }, [selectedCategory, sortBy, searchQuery])

  useEffect(() => {
    setCurrentPage(1)
  }, [selectedCategory, sortBy, searchQuery, selectedTags])

  const clearAllFilters = () => {
    setSelectedCategory('')
    setSelectedTags([])
    setSearchQuery('')
    setCurrentPage(1)
  }

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    )
  }

  // Extract all unique tags from agents
  const availableTags = useMemo(() => {
    const tagSet = new Set<string>()
    agents.forEach((agent) => {
      agent.tags?.forEach((tag) => tagSet.add(tag))
    })
    return Array.from(tagSet).slice(0, 10) // Limit to 10 tags
  }, [agents])

  // Filtered and paginated agents
  const filteredAgents = useMemo(() => {
    let result = [...agents]
    if (selectedTags.length > 0) {
      result = result.filter((a) =>
        selectedTags.some((tag) => a.tags?.includes(tag))
      )
    }
    return result
  }, [agents, selectedTags])

  const totalPages = Math.ceil(filteredAgents.length / itemsPerPage)
  const paginatedAgents = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage
    return filteredAgents.slice(start, start + itemsPerPage)
  }, [filteredAgents, currentPage])

  // Use main categories for the sidebar
  const displayCategories = mainCategories
  const categoryCountMap = useMemo(
    () => new Map(categories.map((item) => [item.category, item.count])),
    [categories]
  )
  const hasActiveFilters = Boolean(searchQuery || selectedCategory || selectedTags.length)

  return (
    <div className="dashboard-app min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
      <div className="mx-auto max-w-[90rem]">
        <div className="dashboard-surface mb-4 px-5 py-3">
          <nav className="flex items-center gap-2 text-sm text-[#7a736a]">
            <button onClick={() => router.push('/')} className="transition-colors hover:text-[#171717]">
              Home
            </button>
            <ChevronRight size={14} className="text-[#9a9388]" />
            <button onClick={() => router.push('/browse')} className="transition-colors hover:text-[#171717]">
              Marketplace
            </button>
            {selectedCategory && (
              <>
                <ChevronRight size={14} className="text-[#9a9388]" />
                <span className="font-medium text-[#171717]">{selectedCategory}</span>
              </>
            )}
          </nav>
        </div>

        <div className="dashboard-surface mb-6 p-5 md:p-6 xl:p-7">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/70 px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6e675d]">
                <Sparkles className="h-3 w-3 text-[#2d8b69]" />
                Marketplace Access
              </div>
              <h1 className="text-[1.8rem] font-semibold tracking-[-0.05em] text-[#171717] md:text-[2.65rem]">
                {selectedCategory ? (
                  <>
                    <span className="highlight-mint">{selectedCategory}</span> agents
                  </>
                ) : (
                  <>
                    Browse <span className="highlight-mint">AI agents</span>
                  </>
                )}
              </h1>
              <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-[#5b564e] md:text-[15px]">
                Discover marketplace agents with clearer pricing, stronger trust signals, and cleaner category navigation. Deploy the right specialist without digging through clutter.
              </p>
            </div>

            <button
              onClick={clearAllFilters}
              className="inline-flex flex-shrink-0 items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/[0.78] px-5 py-3 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white md:text-[14px]"
            >
              <SlidersHorizontal size={16} />
              Clear Filters
            </button>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{filteredAgents.length} visible</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{displayCategories.length} categories</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{availableTags.length} tags</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{viewMode === 'grid' ? 'Grid view' : 'List view'}</div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-[minmax(0,1fr)_220px_auto]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8a8378]" />
              <input
                type="text"
                placeholder="Search agents, tools, or use cases..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-[0.35rem] border border-black/10 bg-white/[0.78] py-3 pl-11 pr-4 text-[13px] text-[#171717] outline-none transition-all focus:border-[#ff5f8f] focus:ring-2 focus:ring-[#ff5f8f]/20 md:text-[14px]"
              />
            </label>

            <label className="relative block">
              <select
                aria-label="Sort by"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full appearance-none rounded-[0.35rem] border border-black/10 bg-white/[0.78] px-4 py-3 pr-12 text-[13px] text-[#171717] outline-none transition-all focus:border-[#ff5f8f] focus:ring-2 focus:ring-[#ff5f8f]/20 md:text-[14px]"
              >
                <option value="popular">Most Popular</option>
                <option value="recent">Recently Added</option>
                <option value="rating">Highest Rated</option>
                <option value="name">Name (A-Z)</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#5b564e]" />
            </label>

            <div className="flex items-center rounded-[0.35rem] border border-black/10 bg-white/[0.78] p-1">
              <button
                onClick={() => setViewMode('grid')}
                className={`flex h-10 w-10 items-center justify-center rounded-[0.35rem] transition-colors ${
                  viewMode === 'grid' ? 'bg-[#181818] text-[#f7f2e7]' : 'text-[#6f685e] hover:bg-black/5'
                }`}
                aria-label="Grid view"
              >
                <LayoutGrid size={18} />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`flex h-10 w-10 items-center justify-center rounded-[0.35rem] transition-colors ${
                  viewMode === 'list' ? 'bg-[#181818] text-[#f7f2e7]' : 'text-[#6f685e] hover:bg-black/5'
                }`}
                aria-label="List view"
              >
                <List size={18} />
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[248px_minmax(0,1fr)]">
          <aside className="dashboard-surface p-3 md:p-4 xl:sticky xl:top-24 xl:h-fit">
            <div className="mb-4">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#8a8378]">Categories</p>
              <div className="space-y-1">
                {displayCategories.map((cat) => {
                  const isActive = selectedCategory === cat
                  return (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(isActive ? '' : cat)}
                      className={`relative flex w-full items-center gap-2 overflow-hidden rounded-[0.35rem] px-2 py-2 text-left transition-all ${
                        isActive
                          ? 'border border-black/10 bg-white/[0.82] text-[#171717] shadow-sm'
                          : 'text-[#5b564e] hover:bg-white/[0.62] hover:text-[#171717]'
                      }`}
                    >
                      {isActive && (
                        <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-[0.35rem] bg-[#63dfbe]" aria-hidden="true" />
                      )}
                      <span className={`flex h-7 w-7 items-center justify-center rounded-[0.35rem] ${isActive ? 'bg-[#181818] text-[#f7f2e7]' : 'bg-white/80 text-[#8a8378]'}`}>
                        {getCategoryIcon(cat, 14)}
                      </span>
                      <span className="flex-1 text-[13px] font-medium leading-none">{cat}</span>
                      <span className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[#8a8378]">
                        {categoryCountMap.get(cat) ?? 0}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>

            {availableTags.length > 0 && (
              <>
                <div className="mb-3 border-t border-black/[0.08]" />
                <div>
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#8a8378]">Tags</p>
                  <div className="flex flex-wrap gap-1.5">
                    {availableTags.map((tag) => {
                      const isSelected = selectedTags.includes(tag)
                      return (
                        <button
                          key={tag}
                          onClick={() => toggleTag(tag)}
                          className={`rounded-[0.35rem] px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                            isSelected
                              ? 'bg-[#181818] text-[#f7f2e7]'
                              : 'border border-black/10 bg-white/70 text-[#5b564e] hover:bg-white'
                          }`}
                        >
                          {tag}
                        </button>
                      )
                    })}
                  </div>
                </div>
              </>
            )}
          </aside>

          <section className="min-w-0">
            <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-[13px] uppercase tracking-[0.18em] text-[#8a8378]">Results</p>
                <p className="mt-1 text-[15px] text-[#5b564e]">
                  Showing <span className="font-semibold text-[#171717]">{filteredAgents.length}</span> marketplace agents
                  {selectedCategory && <> in <span className="font-semibold text-[#171717]">{selectedCategory}</span></>}
                </p>
              </div>

              {hasActiveFilters && (
                <div className="flex flex-wrap gap-2">
                  {selectedCategory && (
                    <span className="rounded-[0.35rem] border border-black/10 bg-white/70 px-3 py-2 text-xs font-medium text-[#171717]">
                      {selectedCategory}
                    </span>
                  )}
                  {selectedTags.map((tag) => (
                    <span key={tag} className="rounded-[0.35rem] border border-black/10 bg-white/70 px-3 py-2 text-xs font-medium text-[#171717]">
                      {tag}
                    </span>
                  ))}
                  {searchQuery && (
                    <span className="rounded-[0.35rem] border border-black/10 bg-white/70 px-3 py-2 text-xs font-medium text-[#171717]">
                      {searchQuery}
                    </span>
                  )}
                </div>
              )}
            </div>

            {loading ? (
              <div className={viewMode === 'grid' ? 'grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3' : 'space-y-4'}>
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="dashboard-panel animate-pulse overflow-hidden">
                    <div className="border-b border-black/10 bg-[#efe7d8] pt-10 pb-12">
                      <div className="mx-auto h-24 w-24 rounded-[0.45rem] bg-white shadow-lg" />
                    </div>
                    <div className="p-5">
                      <div className="mb-2 h-5 w-40 rounded bg-black/10" />
                      <div className="mb-3 h-4 w-24 rounded bg-black/5" />
                      <div className="mb-2 h-4 w-full rounded bg-black/5" />
                      <div className="mb-4 h-4 w-3/4 rounded bg-black/5" />
                      <div className="mb-4 border-t border-black/10 pt-4">
                        <div className="flex gap-6">
                          <div className="h-8 w-12 rounded bg-black/10" />
                          <div className="h-8 w-12 rounded bg-black/10" />
                        </div>
                      </div>
                      <div className="h-10 w-32 rounded-[0.35rem] bg-black/5" />
                    </div>
                  </div>
                ))}
              </div>
            ) : paginatedAgents.length === 0 ? (
              <div className="dashboard-surface py-20 text-center">
                <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-[0.45rem] bg-[#f1eadc] text-[#171717]">
                  <Search className="h-8 w-8" />
                </div>
                <h3 className="mb-2 text-[1.05rem] font-semibold text-[#171717] md:text-[1.35rem]">No matching agents</h3>
                <p className="mb-6 text-[13px] text-[#6c655c] md:text-[14px]">
                  Try clearing filters or broadening your search terms.
                </p>
                <button
                  onClick={clearAllFilters}
                  className="inline-flex items-center gap-2 rounded-[0.35rem] bg-[#181818] px-6 py-3 text-[13px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 md:text-[14px]"
                >
                  Reset Filters
                </button>
              </div>
            ) : (
              <div className={viewMode === 'grid' ? 'grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3' : 'space-y-4'}>
                {paginatedAgents.map((agent) => {
                  const badge = getBadge(agent)
                  const rating = getRating(agent)
                  const price = formatPricing(agent.pricing)

                  if (viewMode === 'list') {
                    return (
                      <div
                        key={agent.id}
                        onClick={() => router.push(`/browse/${agent.id}`)}
                        className="dashboard-panel flex cursor-pointer flex-col gap-5 p-5 transition-all duration-300 hover:-translate-y-1 md:flex-row md:items-center"
                      >
                        <div className="relative flex h-40 items-center justify-center overflow-hidden rounded-[0.45rem] border border-black/10 bg-[linear-gradient(180deg,#efe7d8_0%,#f3ecdf_100%)] md:h-48 md:w-56">
                          {agent.avatar ? (
                            <>
                              <img
                                src={agent.avatar}
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
                              <div className="relative z-10 flex h-24 w-24 items-center justify-center rounded-[0.4rem] border border-white/90 bg-[#fcfbf8] shadow-[0_22px_40px_rgba(109,84,55,0.16)]">
                                {getCategoryIcon(agent.category, 36)}
                              </div>
                            </>
                          )}
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            {badge && (
                              <span className={`inline-flex items-center gap-1 rounded-[0.35rem] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                                badge.type === 'top_rated'
                                  ? 'bg-[#fff0d9] text-[#171717]'
                                  : 'bg-[rgba(99,223,190,0.18)] text-[#171717]'
                              }`}>
                                {badge.type === 'verified' && <CheckCircle size={12} />}
                                {badge.type === 'top_rated' && <Award size={12} />}
                                {badge.label}
                              </span>
                            )}
                            <span className="rounded-[0.35rem] border border-black/10 bg-white/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#5b564e]">
                              {agent.category || 'General'}
                            </span>
                          </div>

                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0">
                              <h3 className="line-clamp-1 text-[1.35rem] font-semibold tracking-[-0.04em] text-[#171717]">
                                {agent.agent_name}
                              </h3>
                              <p className="mt-2 line-clamp-2 text-[14px] leading-relaxed text-[#5b564e]">
                                {agent.description || 'AI agent for your business needs.'}
                              </p>
                            </div>

                            <div className="flex items-center gap-5 lg:ml-6 lg:flex-col lg:items-end lg:text-right">
                              <div className="flex items-center gap-1 text-[#b7832f]">
                                <Star size={16} fill="currentColor" />
                                <span className="text-sm font-semibold text-[#171717]">{rating.toFixed(1)}</span>
                              </div>
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#8a8378]">
                                  {price.label === 'Free' ? 'Access' : 'Starting at'}
                                </p>
                                <p className="text-lg font-semibold text-[#171717]">
                                  {price.label}
                                  {price.sub && <span className="ml-1 text-sm font-medium text-[#7a736a]">{price.sub}</span>}
                                </p>
                              </div>
                            </div>
                          </div>

                          <div className="mt-5 flex items-center justify-between gap-4 border-t border-black/10 pt-4">
                            <div className="flex items-center gap-6">
                              <div>
                                <p className="text-xs uppercase tracking-[0.16em] text-[#8a8378]">Uses</p>
                                <p className="text-lg font-semibold text-[#171717]">{agent.usage_count}</p>
                              </div>
                              <div>
                                <p className="text-xs uppercase tracking-[0.16em] text-[#8a8378]">Likes</p>
                                <p className="text-lg font-semibold text-[#171717]">{agent.likes_count}</p>
                              </div>
                            </div>

                            <button className="rounded-[0.35rem] bg-[#181818] px-5 py-2.5 text-sm font-semibold uppercase tracking-[0.14em] text-[#f7f2e7] transition-transform hover:-translate-y-0.5">
                              View Details
                            </button>
                          </div>
                        </div>
                      </div>
                    )
                  }

                  return (
                    <div
                      key={agent.id}
                      onClick={() => router.push(`/browse/${agent.id}`)}
                      className="dashboard-panel group flex cursor-pointer flex-col overflow-hidden transition-all duration-300 hover:-translate-y-1"
                    >
                      <div className="relative flex min-h-[16rem] items-center justify-center overflow-hidden border-b border-black/10 bg-[linear-gradient(180deg,#efe7d8_0%,#f3ecdf_100%)] md:min-h-[18.5rem]">
                        {badge && (
                          <span className={`absolute left-4 top-4 inline-flex items-center gap-1 rounded-[0.35rem] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                            badge.type === 'top_rated'
                              ? 'bg-[#fff0d9] text-[#171717]'
                              : 'bg-[rgba(99,223,190,0.18)] text-[#171717]'
                          }`}>
                            {badge.type === 'verified' && <CheckCircle size={12} />}
                            {badge.type === 'top_rated' && <Award size={12} />}
                            {badge.label}
                          </span>
                        )}

                        <div className="absolute right-4 top-4 rounded-[0.35rem] border border-black/10 bg-white/78 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#171717]">
                          {price.label}
                          {price.sub && <span className="ml-1 font-medium text-[#7a736a]">{price.sub}</span>}
                        </div>

                        {agent.avatar ? (
                          <>
                            <img
                              src={agent.avatar}
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
                              {getCategoryIcon(agent.category, 34)}
                            </div>
                          </>
                        )}
                      </div>

                      <div className="flex flex-1 flex-col p-5">
                        <div className="mb-2 flex items-start justify-between gap-3">
                          <div>
                            <h3 className="line-clamp-2 text-[1.3rem] font-semibold leading-tight tracking-[-0.04em] text-[#171717]">
                              {agent.agent_name}
                            </h3>
                            <p className="mt-2 text-[12px] uppercase tracking-[0.16em] text-[#7a736a]">
                              {agent.category || 'General'}
                            </p>
                          </div>

                          <div className="flex items-center gap-1 text-[#b7832f]">
                            <Star size={15} fill="currentColor" />
                            <span className="text-sm font-semibold text-[#171717]">{rating.toFixed(1)}</span>
                          </div>
                        </div>

                        <p className="mb-4 line-clamp-2 text-[14px] leading-relaxed text-[#5b564e]">
                          {agent.description || 'AI agent for your business needs.'}
                        </p>

                        {agent.tags?.length > 0 && (
                          <div className="mb-4 flex flex-wrap gap-2">
                            {agent.tags.slice(0, 2).map((tag) => (
                              <span key={tag} className="rounded-[0.35rem] border border-black/10 bg-white/70 px-3 py-1 text-[11px] font-medium text-[#5b564e]">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}

                        <div className="mb-5 border-t border-black/10 pt-4">
                          <div className="flex items-center gap-6">
                            <div>
                              <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#8a8378]">Uses</p>
                              <p className="text-xl font-semibold text-[#171717]">{agent.usage_count}</p>
                            </div>
                            <div>
                              <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#8a8378]">Likes</p>
                              <p className="text-xl font-semibold text-[#171717]">{agent.likes_count}</p>
                            </div>
                          </div>
                        </div>

                        <button className="mt-auto rounded-[0.35rem] border border-black/15 bg-white/70 px-5 py-2.5 text-center text-sm font-semibold uppercase tracking-[0.14em] text-[#171717] transition-colors hover:bg-white">
                          View Details
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {totalPages > 1 && (
              <div className="dashboard-surface mt-8 flex items-center justify-center gap-3 px-4 py-3">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="flex h-10 w-10 items-center justify-center rounded-[0.35rem] text-[#5b564e] transition-colors hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="Previous page"
                >
                  <ChevronLeft size={18} />
                </button>

                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pageNum: number
                  if (totalPages <= 5) {
                    pageNum = i + 1
                  } else if (currentPage <= 3) {
                    pageNum = i + 1
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i
                  } else {
                    pageNum = currentPage - 2 + i
                  }

                  return (
                    <button
                      key={pageNum}
                      onClick={() => setCurrentPage(pageNum)}
                      className={`flex h-10 w-10 items-center justify-center rounded-[0.35rem] text-sm font-semibold transition-colors ${
                        currentPage === pageNum
                          ? 'bg-[#181818] text-[#f7f2e7]'
                          : 'text-[#5b564e] hover:bg-black/5'
                      }`}
                    >
                      {pageNum}
                    </button>
                  )
                })}

                {totalPages > 5 && currentPage < totalPages - 2 && (
                  <>
                    <span className="text-[#8a8378]">...</span>
                    <button
                      onClick={() => setCurrentPage(totalPages)}
                      className="flex h-10 w-10 items-center justify-center rounded-[0.35rem] text-sm font-semibold text-[#5b564e] transition-colors hover:bg-black/5"
                    >
                      {totalPages}
                    </button>
                  </>
                )}

                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="flex h-10 w-10 items-center justify-center rounded-[0.35rem] text-[#5b564e] transition-colors hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="Next page"
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
