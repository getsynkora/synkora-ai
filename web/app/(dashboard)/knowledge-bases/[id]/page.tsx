'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import {
  Database,
  ArrowLeft,
  Edit,
  Trash2,
  FileText,
  Layers,
  Activity,
  Search,
  AlertCircle,
  CheckCircle,
  Upload,
  Type,
  Globe,
  X,
  Loader2,
  Plus,
  Network,
  Sliders
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import FileUpload from '@/components/knowledge-bases/FileUpload'
import DocumentBrowser from '@/components/knowledge-bases/DocumentBrowser'
import {
  type BrainDomain,
  listBrainDomains,
  createBrainDomain,
  updateBrainDomain,
  deleteBrainDomain,
} from '@/lib/api/brain'

interface KnowledgeBase {
  id: number
  name: string
  description: string
  vector_db_provider: string
  embedding_provider: string
  embedding_model: string
  chunk_size: number
  chunk_overlap: number
  document_count: number
  total_chunks: number
  is_active: boolean
  created_at: string
  updated_at: string
}

interface DataSource {
  id: number
  source_type: string
  sync_status: string
  last_sync_at: string | null
  total_documents: number
}

interface SearchResult {
  content: string
  score: number
  metadata: Record<string, any>
}

export default function KnowledgeBaseDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const id = params.id as string

  const [activeTab, setActiveTab] = useState<'overview' | 'sources' | 'documents' | 'search' | 'domains'>('overview')
  const [kb, setKb] = useState<KnowledgeBase | null>(null)
  const [dataSources, setDataSources] = useState<DataSource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // Brain Domain state
  const [domains, setDomains] = useState<BrainDomain[]>([])
  const [domainsLoading, setDomainsLoading] = useState(false)
  const [showDomainForm, setShowDomainForm] = useState(false)
  const [editingDomain, setEditingDomain] = useState<BrainDomain | null>(null)
  const [domainForm, setDomainForm] = useState({ name: '', slug: '', description: '', rerank_weight: 1.0, is_active: true })
  const [savingDomain, setSavingDomain] = useState(false)
  const [deletingDomainId, setDeletingDomainId] = useState<string | null>(null)
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  // Add content modals
  const [showPasteModal, setShowPasteModal] = useState(false)
  const [showWebsiteModal, setShowWebsiteModal] = useState(false)
  const [pasteTitle, setPasteTitle] = useState('')
  const [pasteContent, setPasteContent] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [includeSubpages, setIncludeSubpages] = useState(false)
  const [maxPages, setMaxPages] = useState(20)
  const [addingContent, setAddingContent] = useState(false)
  const fieldClass = 'w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500'
  const compactFieldClass = 'w-full rounded-[1rem] border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500'
  const textareaClass = `${fieldClass} resize-none`
  const compactTextareaClass = `${compactFieldClass} resize-none`
  const labelClass = 'mb-2 block text-sm font-semibold text-gray-700'
  const compactLabelClass = 'mb-1.5 block text-sm font-semibold text-gray-700'
  const helpClass = 'mt-2 text-xs leading-relaxed text-gray-500'

  useEffect(() => {
    fetchKnowledgeBase()
    fetchDataSources()
  }, [id])

  useEffect(() => {
    if (activeTab === 'domains') fetchDomains()
  }, [activeTab])

  const fetchKnowledgeBase = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getKnowledgeBase(id)
      setKb(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      toast.error('Failed to load knowledge base')
    } finally {
      setLoading(false)
    }
  }

  const fetchDataSources = async () => {
    try {
      const data = await apiClient.getDataSources()
      // Filter by knowledge_base_id on client side for now
      setDataSources(Array.isArray(data) ? data.filter((ds: any) => ds.knowledge_base_id === parseInt(id)) : [])
    } catch (err) {
      console.error('Failed to fetch data sources:', err)
    }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return

    try {
      setSearching(true)
      setSearchError(null)
      const data = await apiClient.searchKnowledgeBase(id, searchQuery, 5)
      setSearchResults(data.data?.results || [])
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Search failed')
      toast.error('Search failed')
    } finally {
      setSearching(false)
    }
  }

  const handleDelete = async () => {
    try {
      setDeleting(true)
      await apiClient.deleteKnowledgeBase(id)
      toast.success('Knowledge base deleted successfully')
      router.push('/knowledge-bases')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete knowledge base')
    } finally {
      setDeleting(false)
      setShowDeleteModal(false)
    }
  }

  const getProviderIcon = (provider: string) => {
    const icons: Record<string, string> = {
      QDRANT: '🔍',
      PINECONE: '🌲',
      WEAVIATE: '🔷',
      CHROMA: '🎨',
      MILVUS: '⚡',
    }
    return icons[provider?.toUpperCase()] || '📦'
  }

  const handleAddTextContent = async () => {
    if (!pasteTitle.trim() || !pasteContent.trim()) {
      toast.error('Please provide both title and content')
      return
    }

    setAddingContent(true)
    try {
      await apiClient.addTextContent(id, pasteTitle, pasteContent)
      toast.success('Text content added successfully')
      setShowPasteModal(false)
      setPasteTitle('')
      setPasteContent('')
      fetchKnowledgeBase()
      // Refresh documents tab
      setActiveTab('overview')
      setTimeout(() => setActiveTab('documents'), 0)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add text content')
    } finally {
      setAddingContent(false)
    }
  }

  const handleCrawlWebsite = async () => {
    if (!websiteUrl.trim()) {
      toast.error('Please provide a URL')
      return
    }

    // Basic URL validation
    try {
      new URL(websiteUrl)
    } catch {
      toast.error('Please enter a valid URL (e.g., https://example.com)')
      return
    }

    setAddingContent(true)
    try {
      const result = await apiClient.crawlWebsite(id, websiteUrl, { includeSubpages, maxPages })
      toast.success(result.message || 'Website content added successfully')
      setShowWebsiteModal(false)
      setWebsiteUrl('')
      setIncludeSubpages(false)
      setMaxPages(20)
      fetchKnowledgeBase()
      // Refresh documents tab
      setActiveTab('overview')
      setTimeout(() => setActiveTab('documents'), 0)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to crawl website')
    } finally {
      setAddingContent(false)
    }
  }

  const fetchDomains = async () => {
    setDomainsLoading(true)
    try {
      const all = await listBrainDomains()
      setDomains(all.filter((d) => d.knowledge_base_id === parseInt(id)))
    } catch {
      toast.error('Failed to load domains')
    } finally {
      setDomainsLoading(false)
    }
  }

  const openNewDomain = () => {
    setEditingDomain(null)
    setDomainForm({ name: '', slug: '', description: '', rerank_weight: 1.0, is_active: true })
    setShowDomainForm(true)
  }

  const openEditDomain = (d: BrainDomain) => {
    setEditingDomain(d)
    setDomainForm({ name: d.name, slug: d.slug, description: d.description ?? '', rerank_weight: d.rerank_weight, is_active: d.is_active })
    setShowDomainForm(true)
  }

  const handleSaveDomain = async () => {
    if (!domainForm.name.trim() || !domainForm.slug.trim()) {
      toast.error('Name and slug are required')
      return
    }
    setSavingDomain(true)
    try {
      if (editingDomain) {
        await updateBrainDomain(editingDomain.id, {
          name: domainForm.name,
          description: domainForm.description || undefined,
          rerank_weight: domainForm.rerank_weight,
          is_active: domainForm.is_active,
        })
        toast.success('Domain updated')
      } else {
        await createBrainDomain({
          name: domainForm.name,
          slug: domainForm.slug,
          description: domainForm.description || undefined,
          rerank_weight: domainForm.rerank_weight,
          is_active: domainForm.is_active,
          knowledge_base_id: parseInt(id),
        })
        toast.success('Domain created')
      }
      setShowDomainForm(false)
      fetchDomains()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save domain')
    } finally {
      setSavingDomain(false)
    }
  }

  const handleDeleteDomain = async (domainId: string) => {
    setDeletingDomainId(domainId)
    try {
      await deleteBrainDomain(domainId)
      toast.success('Domain deleted')
      setDomains((prev) => prev.filter((d) => d.id !== domainId))
    } catch {
      toast.error('Failed to delete domain')
    } finally {
      setDeletingDomainId(null)
    }
  }

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 animate-spin rounded-full border-b-2 border-red-600"></div>
          <p className="mt-4 text-sm text-gray-600">Loading knowledge base...</p>
        </div>
      </div>
    )
  }

  if (error || !kb) {
    return (
      <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
        <div className="max-w-5xl mx-auto">
          <div className="rounded-[1.6rem] border border-red-200 bg-red-50/90 p-5">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-600" />
              <div>
                <h3 className="text-base font-semibold text-red-900">Error</h3>
                <p className="text-red-700 mt-1 text-sm">{error || 'Knowledge base not found'}</p>
              </div>
            </div>
          </div>
          <Link
            href="/knowledge-bases"
            className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-gray-600 transition-colors hover:text-[#171717]"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Knowledge Bases
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <Link
            href="/knowledge-bases"
            className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-gray-600 transition-colors hover:text-[#171717]"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Knowledge Bases
          </Link>
          
          <div className="rounded-[2rem] border border-black/10 bg-white/78 p-6 shadow-[0_24px_60px_rgba(0,0,0,0.06)] sm:p-8">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3 flex-1">
                <div className="rounded-[1.15rem] bg-[#f3ecde] p-3 shadow-[0_12px_28px_rgba(0,0,0,0.04)]">
                  <Database className="h-6 w-6 text-[#171717]" />
                </div>
                <div className="flex-1">
                  <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#6e675d]">
                    <Database className="h-3.5 w-3.5 text-[#2d8b69]" />
                    Knowledge Base
                  </div>
                  <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">{kb.name}</h1>
                  {kb.description && (
                    <p className="mt-2 text-sm text-gray-600">{kb.description}</p>
                  )}
                  <div className="mt-4 flex flex-wrap gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f7f2e7] px-2.5 py-1 text-xs font-medium text-[#6e675d]">
                      <span className="text-base">{getProviderIcon(kb.vector_db_provider)}</span>
                      {kb.vector_db_provider}
                    </span>
                    <span className="inline-flex items-center rounded-full bg-[#eef7f1] px-2.5 py-1 text-xs font-medium text-[#2d8b69]">
                      {kb.embedding_model}
                    </span>
                    {kb.is_active ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-[#e8f4ee] px-2.5 py-1 text-xs font-medium text-[#2d8b69]">
                        <CheckCircle className="w-3.5 h-3.5" />
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f1eadc] px-2.5 py-1 text-xs font-medium text-[#6e675d]">
                        <AlertCircle className="w-3.5 h-3.5" />
                        Inactive
                      </span>
                    )}
                  </div>
                </div>
              </div>
              
              <div className="flex gap-2">
                <Link
                  href={`/knowledge-bases/${id}/wiki`}
                  className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-[#f1eadc] px-3 py-2 text-xs font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8]"
                >
                  <FileText className="w-3.5 h-3.5" />
                  Wiki
                </Link>
                <Link
                  href={`/knowledge-bases/${id}/edit`}
                  className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-[#f7f2e7] px-3 py-2 text-xs font-semibold text-[#171717] transition-colors hover:bg-[#f1eadc]"
                >
                  <Edit className="w-3.5 h-3.5" />
                  Edit
                </Link>
                <button
                  onClick={() => setShowDeleteModal(true)}
                  className="inline-flex items-center gap-2 rounded-[1rem] border border-red-200 bg-red-50/90 px-3 py-2 text-xs font-semibold text-red-600 transition-colors hover:bg-red-100"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4">
          <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
            <div className="flex items-center gap-2 mb-2">
              <div className="rounded-[0.95rem] bg-[#f3ecde] p-2">
                <FileText className="w-4 h-4 text-[#171717]" />
              </div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Documents</p>
            </div>
            <p className="text-2xl font-semibold text-gray-900">{kb.document_count}</p>
          </div>
          
          <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
            <div className="flex items-center gap-2 mb-2">
              <div className="rounded-[0.95rem] bg-[#eef7f1] p-2">
                <Layers className="w-4 h-4 text-[#2d8b69]" />
              </div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Chunks</p>
            </div>
            <p className="text-2xl font-semibold text-gray-900">{kb.total_chunks}</p>
          </div>
          
          <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
            <div className="flex items-center gap-2 mb-2">
              <div className="rounded-[0.95rem] bg-[#f4efe4] p-2">
                <Database className="w-4 h-4 text-[#5b564e]" />
              </div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Data Sources</p>
            </div>
            <p className="text-2xl font-semibold text-gray-900">{dataSources.length}</p>
          </div>
          
          <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
            <div className="flex items-center gap-2 mb-2">
              <div className="rounded-[0.95rem] bg-[#f7f2e7] p-2">
                <Activity className="w-4 h-4 text-[#171717]" />
              </div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Status</p>
            </div>
            <p className="text-xl font-semibold text-gray-900">{kb.is_active ? 'Active' : 'Inactive'}</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="mb-6 overflow-hidden rounded-[2rem] border border-black/10 bg-white/78 shadow-[0_24px_60px_rgba(0,0,0,0.06)]">
          <div className="border-b border-black/10 px-5 py-2">
            <nav className="flex flex-wrap gap-2">
              <button
                onClick={() => setActiveTab('overview')}
                className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition-colors ${
                  activeTab === 'overview'
                    ? 'bg-[#171717] text-white'
                    : 'text-gray-500 hover:bg-[#f7f2e7] hover:text-[#171717]'
                }`}
              >
                Overview
              </button>
              <button
                onClick={() => setActiveTab('sources')}
                className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition-colors ${
                  activeTab === 'sources'
                    ? 'bg-[#171717] text-white'
                    : 'text-gray-500 hover:bg-[#f7f2e7] hover:text-[#171717]'
                }`}
              >
                Data Sources ({dataSources.length})
              </button>
              <button
                onClick={() => setActiveTab('documents')}
                className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition-colors ${
                  activeTab === 'documents'
                    ? 'bg-[#171717] text-white'
                    : 'text-gray-500 hover:bg-[#f7f2e7] hover:text-[#171717]'
                }`}
              >
                <span className="flex items-center gap-2">
                  <Upload className="w-3.5 h-3.5" />
                  Documents ({kb.document_count})
                </span>
              </button>
              <button
                onClick={() => setActiveTab('search')}
                className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition-colors ${
                  activeTab === 'search'
                    ? 'bg-[#171717] text-white'
                    : 'text-gray-500 hover:bg-[#f7f2e7] hover:text-[#171717]'
                }`}
              >
                <span className="flex items-center gap-2">
                  <Search className="w-3.5 h-3.5" />
                  Search
                </span>
              </button>
              <button
                onClick={() => setActiveTab('domains')}
                className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition-colors ${
                  activeTab === 'domains'
                    ? 'bg-[#171717] text-white'
                    : 'text-gray-500 hover:bg-[#f7f2e7] hover:text-[#171717]'
                }`}
              >
                <span className="flex items-center gap-2">
                  <Network className="w-3.5 h-3.5" />
                  Brain Domains
                </span>
              </button>
            </nav>
          </div>

          {/* Tab Content */}
          <div className="p-5 sm:p-6">
            {activeTab === 'overview' && (
              <div className="space-y-5">
                <div>
                  <h2 className="mb-3 text-base font-semibold text-gray-900">Configuration</h2>
                  <dl className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="rounded-[1.25rem] border border-black/10 bg-[#f7f2e7] p-4">
                      <dt className="mb-1 text-[11px] font-medium uppercase tracking-[0.14em] text-gray-500">Vector Database</dt>
                      <dd className="text-sm font-semibold text-gray-900">{kb.vector_db_provider}</dd>
                    </div>
                    <div className="rounded-[1.25rem] border border-black/10 bg-[#eef7f1] p-4">
                      <dt className="mb-1 text-[11px] font-medium uppercase tracking-[0.14em] text-gray-500">Embedding Provider</dt>
                      <dd className="text-sm font-semibold text-gray-900">{kb.embedding_provider}</dd>
                    </div>
                    <div className="rounded-[1.25rem] border border-black/10 bg-[#fcfaf5] p-4">
                      <dt className="mb-1 text-[11px] font-medium uppercase tracking-[0.14em] text-gray-500">Embedding Model</dt>
                      <dd className="text-sm font-semibold text-gray-900">{kb.embedding_model}</dd>
                    </div>
                    <div className="rounded-[1.25rem] border border-black/10 bg-[#fcfaf5] p-4">
                      <dt className="mb-1 text-[11px] font-medium uppercase tracking-[0.14em] text-gray-500">Chunk Size</dt>
                      <dd className="text-sm font-semibold text-gray-900">{kb.chunk_size} characters</dd>
                    </div>
                    <div className="rounded-[1.25rem] border border-black/10 bg-[#fcfaf5] p-4">
                      <dt className="mb-1 text-[11px] font-medium uppercase tracking-[0.14em] text-gray-500">Chunk Overlap</dt>
                      <dd className="text-sm font-semibold text-gray-900">{kb.chunk_overlap} characters</dd>
                    </div>
                    <div className="rounded-[1.25rem] border border-black/10 bg-[#f4efe4] p-4">
                      <dt className="mb-1 text-[11px] font-medium uppercase tracking-[0.14em] text-gray-500">Created</dt>
                      <dd className="text-sm font-semibold text-gray-900">
                        {new Date(kb.created_at).toLocaleDateString()}
                      </dd>
                    </div>
                  </dl>
                </div>
              </div>
            )}

            {activeTab === 'sources' && (
              <div>
                {dataSources.length === 0 ? (
                  <div className="rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] py-12 text-center">
                    <Database className="mx-auto mb-4 h-12 w-12 text-[#8a8378]" />
                    <h3 className="text-base font-semibold text-gray-900 mb-2">No data sources connected</h3>
                    <p className="text-gray-600 text-sm mb-5">Connect a data source to start syncing documents to this knowledge base.</p>
                    <Link
                      href={`/data-sources/connect?kb_id=${id}`}
                      className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-xs font-semibold text-white transition-colors hover:bg-black"
                    >
                      <Database className="w-4 h-4" />
                      Connect Data Source
                    </Link>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {dataSources.map((source) => (
                      <Link
                        key={source.id}
                        href={`/data-sources/${source.id}`}
                        className="rounded-[1.5rem] border border-black/10 bg-white/80 p-5 shadow-[0_18px_36px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-[0_22px_44px_rgba(0,0,0,0.08)]"
                      >
                        <div className="flex items-start justify-between mb-3">
                          <span className="inline-flex items-center rounded-full bg-[#f7f2e7] px-2.5 py-1 text-xs font-medium text-[#6e675d]">
                            {source.source_type}
                          </span>
                          <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                            source.sync_status === 'active' ? 'bg-[#e8f4ee] text-[#2d8b69]' :
                            source.sync_status === 'error' ? 'bg-red-50 text-red-700' :
                            'bg-[#f1eadc] text-[#6e675d]'
                          }`}>
                            {source.sync_status}
                          </span>
                        </div>
                        <div className="space-y-2">
                          <div>
                            <p className="text-xs text-gray-500 mb-1">Documents</p>
                            <p className="text-xl font-bold text-gray-900">{source.total_documents}</p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500 mb-1">Last Sync</p>
                            <p className="text-xs text-gray-900">
                              {source.last_sync_at
                                ? new Date(source.last_sync_at).toLocaleString()
                                : 'Never'}
                            </p>
                          </div>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'documents' && (
              <div className="space-y-6">
                {/* Add Content Section */}
                <div>
                  <h3 className="mb-2 text-base font-semibold text-gray-900">Add Content</h3>
                  <p className="text-sm text-gray-600 mb-4">
                    Add information to this knowledge base. Your AI agents will use this content to answer questions.
                  </p>

                  {/* Input Source Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                    {/* Upload Documents Card */}
                    <div className="group cursor-pointer rounded-[1.5rem] border border-black/10 bg-white/80 p-5 shadow-[0_18px_36px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-[0_22px_44px_rgba(0,0,0,0.08)]">
                      <div className="mb-3 w-fit rounded-[1rem] bg-[#f3ecde] p-3 transition-colors group-hover:bg-[#ece2cd]">
                        <Upload className="w-6 h-6 text-[#171717]" />
                      </div>
                      <h4 className="font-semibold text-gray-900 mb-1">Upload Documents</h4>
                      <p className="text-sm text-gray-500">PDF, DOCX, TXT, MD, HTML, CSV (Max 50MB)</p>
                    </div>

                    {/* Paste Text Card */}
                    <button
                      onClick={() => setShowPasteModal(true)}
                      className="group rounded-[1.5rem] border border-black/10 bg-white/80 p-5 text-left shadow-[0_18px_36px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-[0_22px_44px_rgba(0,0,0,0.08)]"
                    >
                      <div className="mb-3 w-fit rounded-[1rem] bg-[#eef7f1] p-3 transition-colors group-hover:bg-[#e2efe7]">
                        <Type className="w-6 h-6 text-[#2d8b69]" />
                      </div>
                      <h4 className="font-semibold text-gray-900 mb-1">Paste Text</h4>
                      <p className="text-sm text-gray-500">Direct manual content entry</p>
                    </button>

                    {/* Add Website Card */}
                    <button
                      onClick={() => setShowWebsiteModal(true)}
                      className="group rounded-[1.5rem] border border-black/10 bg-white/80 p-5 text-left shadow-[0_18px_36px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-[0_22px_44px_rgba(0,0,0,0.08)]"
                    >
                      <div className="mb-3 w-fit rounded-[1rem] bg-[#f4efe4] p-3 transition-colors group-hover:bg-[#ebe2cf]">
                        <Globe className="w-6 h-6 text-[#5b564e]" />
                      </div>
                      <h4 className="font-semibold text-gray-900 mb-1">Add Website</h4>
                      <p className="text-sm text-gray-500">Crawl content from a URL</p>
                    </button>
                  </div>

                  {/* File Upload Area */}
                  <div className="rounded-[1.7rem] border border-black/10 bg-[#fcfaf5] p-4">
                    <FileUpload
                      onUploadComplete={() => {
                        fetchKnowledgeBase()
                        // Trigger document browser refresh by re-mounting
                        setActiveTab('overview')
                        setTimeout(() => setActiveTab('documents'), 0)
                      }}
                      onUpload={async (files, onProgress) => {
                        return await apiClient.uploadDocuments(id, files, onProgress)
                      }}
                    />
                  </div>
                </div>

                {/* Documents List */}
                <div>
                  <h3 className="mb-3 text-base font-semibold text-gray-900">All Documents ({kb.document_count})</h3>
                  <DocumentBrowser
                    kbId={id}
                    onGetDocuments={(params) => apiClient.getKnowledgeBaseDocuments(id, params)}
                    onDeleteDocument={(docId) => apiClient.deleteKnowledgeBaseDocument(id, docId)}
                    onBulkDelete={(docIds) => apiClient.bulkDeleteKnowledgeBaseDocuments(id, docIds)}
                    onDownloadDocument={(docId) => apiClient.downloadKnowledgeBaseDocument(id, docId)}
                  />
                </div>
              </div>
            )}

            {activeTab === 'search' && (
              <div className="space-y-5">
                <form onSubmit={handleSearch} className="flex gap-3">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search knowledge base..."
                    className={`flex-1 ${compactFieldClass}`}
                  />
                  <button
                    type="submit"
                    disabled={searching || !searchQuery.trim()}
                    className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {searching ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Searching...
                      </>
                    ) : (
                      <>
                        <Search className="w-4 h-4" />
                        Search
                      </>
                    )}
                  </button>
                </form>

                {searchError && (
                  <div className="rounded-[1.35rem] border border-red-200 bg-red-50/90 p-3">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-red-600" />
                      <p className="text-red-700 text-sm">{searchError}</p>
                    </div>
                  </div>
                )}

                {searchResults.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-base font-semibold text-gray-900">
                      Results ({searchResults.length})
                    </h3>
                    {searchResults.map((result, index) => (
                      <div
                        key={index}
                        className="rounded-[1.5rem] border border-black/10 bg-white/80 p-5 shadow-[0_18px_36px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-[0_22px_44px_rgba(0,0,0,0.08)]"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <span className="inline-flex items-center rounded-full bg-[#e8f4ee] px-2.5 py-1 text-xs font-medium text-[#2d8b69]">
                            Score: {(result.score * 100).toFixed(1)}%
                          </span>
                          {result.metadata.source && (
                            <span className="text-xs text-gray-500">
                              Source: {result.metadata.source}
                            </span>
                          )}
                        </div>
                        <p className="text-gray-700 text-sm whitespace-pre-wrap leading-relaxed">{result.content}</p>
                        {result.metadata && Object.keys(result.metadata).length > 0 && (
                          <div className="mt-3 border-t border-black/10 pt-3">
                            <p className="text-xs font-medium text-gray-500 mb-2">Metadata:</p>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(result.metadata).map(([key, value]) => (
                                <span
                                  key={key}
                                  className="inline-flex items-center rounded-md bg-[#f7f2e7] px-2 py-1 text-xs text-gray-700"
                                >
                                  <span className="font-medium">{key}:</span>&nbsp;{String(value)}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {searchResults.length === 0 && searchQuery && !searching && !searchError && (
                  <div className="rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] py-12 text-center">
                    <Search className="mx-auto mb-4 h-12 w-12 text-[#8a8378]" />
                    <h3 className="text-base font-semibold text-gray-900 mb-2">No results found</h3>
                    <p className="text-gray-600 text-sm">Try adjusting your search query or check if documents have been synced.</p>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'domains' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-gray-900">Brain Domains</h2>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Semantic routing labels for this knowledge base. Agents use domains to classify and route queries.
                    </p>
                  </div>
                  <button
                    onClick={openNewDomain}
                    className="inline-flex items-center gap-1.5 rounded-[1rem] bg-[#171717] px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-black"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    New Domain
                  </button>
                </div>

                {domainsLoading ? (
                  <div className="flex justify-center py-10">
                    <Loader2 className="h-6 w-6 animate-spin text-[#8a8378]" />
                  </div>
                ) : domains.length === 0 ? (
                  <div className="rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] py-12 text-center">
                    <Network className="mx-auto mb-3 h-10 w-10 text-[#8a8378]" />
                    <h3 className="text-sm font-semibold text-gray-700 mb-1">No domains yet</h3>
                    <p className="text-xs text-gray-500 mb-4">
                      Create a domain to enable semantic routing for this knowledge base.
                    </p>
                    <button
                      onClick={openNewDomain}
                      className="inline-flex items-center gap-1.5 rounded-[1rem] bg-[#171717] px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-black"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Create First Domain
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {domains.map((domain) => (
                      <div
                        key={domain.id}
                        className="rounded-[1.5rem] border border-black/10 bg-white/80 p-4 shadow-[0_18px_36px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-[0_22px_44px_rgba(0,0,0,0.08)]"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-gray-900 text-sm">{domain.name}</span>
                            <span className="rounded-md bg-[#f7f2e7] px-1.5 py-0.5 font-mono text-xs text-[#6e675d]">{domain.slug}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            {domain.is_active ? (
                              <span className="rounded-md bg-[#e8f4ee] px-1.5 py-0.5 text-xs text-[#2d8b69]">Active</span>
                            ) : (
                              <span className="rounded-md bg-[#f1eadc] px-1.5 py-0.5 text-xs text-[#6e675d]">Inactive</span>
                            )}
                          </div>
                        </div>
                        {domain.description && (
                          <p className="text-xs text-gray-500 mb-3 line-clamp-2">{domain.description}</p>
                        )}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1 text-xs text-gray-500">
                            <Sliders className="w-3 h-3" />
                            <span>Weight: {domain.rerank_weight}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => openEditDomain(domain)}
                              className="rounded-md px-2 py-1 text-xs text-gray-600 transition-colors hover:bg-[#f7f2e7] hover:text-[#171717]"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteDomain(domain.id)}
                              disabled={deletingDomainId === domain.id}
                              className="rounded-md px-2 py-1 text-xs text-red-500 transition-colors hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                            >
                              {deletingDomainId === domain.id ? '...' : 'Delete'}
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.18)]">
            <div className="flex items-center gap-3 mb-4">
              <div className="rounded-[1rem] bg-red-50 p-2.5">
                <AlertCircle className="w-5 h-5 text-red-600" />
              </div>
              <h3 className="text-base font-semibold text-gray-900">Delete Knowledge Base</h3>
            </div>
            
            <p className="text-gray-600 text-sm mb-5">
              Are you sure you want to delete <span className="font-semibold">"{kb.name}"</span>? 
              This action cannot be undone and will permanently delete all associated documents and data.
            </p>
            
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteModal(false)}
                disabled={deleting}
                className="rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
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

      {/* Paste Text Modal */}
      {showPasteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-[2rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_32px_90px_rgba(0,0,0,0.18)] sm:p-8">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#eef7f1] p-3">
                  <Type className="w-5 h-5 text-[#2d8b69]" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Paste Text Content</h3>
                  <p className="text-sm text-gray-500">Add text directly to your knowledge base</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setShowPasteModal(false)
                  setPasteTitle('')
                  setPasteContent('')
                }}
                className="rounded-lg p-2 transition-colors hover:bg-[#f1eadc]"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className={labelClass}>
                  Title <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={pasteTitle}
                  onChange={(e) => setPasteTitle(e.target.value)}
                  placeholder="e.g., Company FAQ, Product Guide, Meeting Notes"
                  className={fieldClass}
                />
              </div>

              <div>
                <label className={labelClass}>
                  Content <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={pasteContent}
                  onChange={(e) => setPasteContent(e.target.value)}
                  placeholder="Paste or type your content here..."
                  rows={10}
                  className={textareaClass}
                />
                <p className={helpClass}>
                  {pasteContent.length} characters
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowPasteModal(false)
                  setPasteTitle('')
                  setPasteContent('')
                }}
                disabled={addingContent}
                className="rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAddTextContent}
                disabled={addingContent || !pasteTitle.trim() || !pasteContent.trim()}
                className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
              >
                {addingContent ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Adding...
                  </>
                ) : (
                  'Add Content'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Brain Domain Form Modal */}
      {showDomainForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-[2rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_32px_90px_rgba(0,0,0,0.18)]">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f3ecde] p-3">
                  <Network className="w-5 h-5 text-[#171717]" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{editingDomain ? 'Edit Domain' : 'New Brain Domain'}</h3>
                  <p className="text-sm text-gray-500">Will be linked to <span className="font-medium">{kb?.name}</span></p>
                </div>
              </div>
              <button onClick={() => setShowDomainForm(false)} className="rounded-lg p-2 transition-colors hover:bg-[#f1eadc]">
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={compactLabelClass}>Name <span className="text-red-500">*</span></label>
                  <input
                    type="text"
                    value={domainForm.name}
                    onChange={(e) => setDomainForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="e.g., Engineering"
                    className={compactFieldClass}
                  />
                </div>
                <div>
                  <label className={compactLabelClass}>Slug <span className="text-red-500">*</span></label>
                  <input
                    type="text"
                    value={domainForm.slug}
                    onChange={(e) => setDomainForm((f) => ({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '-') }))}
                    placeholder="e.g., engineering"
                    disabled={!!editingDomain}
                    className={`${compactFieldClass} font-mono disabled:bg-gray-100 disabled:text-gray-400`}
                  />
                </div>
              </div>

              <div>
                <label className={compactLabelClass}>Description</label>
                <textarea
                  value={domainForm.description}
                  onChange={(e) => setDomainForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Describe what topics this domain covers — used by the AI query classifier"
                  rows={3}
                  className={compactTextareaClass}
                />
              </div>

              <div>
                <label className={compactLabelClass}>
                  Rerank Weight <span className="text-gray-400 font-normal">(0.1 – 10.0)</span>
                </label>
                <input
                  type="number"
                  min={0.1}
                  max={10}
                  step={0.1}
                  value={domainForm.rerank_weight}
                  onChange={(e) => setDomainForm((f) => ({ ...f, rerank_weight: parseFloat(e.target.value) || 1.0 }))}
                  className={compactFieldClass}
                />
                <p className={helpClass}>Multiplier applied to result scores. 1.0 = neutral, &gt;1 boosts, &lt;1 demotes.</p>
              </div>

              <div className="flex items-center justify-between border-t border-black/10 py-2">
                <div>
                  <p className="text-sm font-medium text-gray-700">Active</p>
                  <p className="text-xs text-gray-400">Inactive domains are excluded from query routing</p>
                </div>
                <button
                  type="button"
                  onClick={() => setDomainForm((f) => ({ ...f, is_active: !f.is_active }))}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${domainForm.is_active ? 'bg-[#171717]' : 'bg-gray-200'}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${domainForm.is_active ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowDomainForm(false)}
                disabled={savingDomain}
                className="rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveDomain}
                disabled={savingDomain || !domainForm.name.trim() || !domainForm.slug.trim()}
                className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
              >
                {savingDomain ? (
                  <><Loader2 className="w-4 h-4 animate-spin" />Saving...</>
                ) : (
                  editingDomain ? 'Save Changes' : 'Create Domain'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Website Modal */}
      {showWebsiteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-[2rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_32px_90px_rgba(0,0,0,0.18)]">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f4efe4] p-3">
                  <Globe className="w-5 h-5 text-[#5b564e]" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Add Website Content</h3>
                  <p className="text-sm text-gray-500">Crawl and import content from a URL</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setShowWebsiteModal(false)
                  setWebsiteUrl('')
                }}
                className="rounded-lg p-2 transition-colors hover:bg-[#f1eadc]"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className={labelClass}>
                  Website URL <span className="text-red-500">*</span>
                </label>
                <input
                  type="url"
                  value={websiteUrl}
                  onChange={(e) => setWebsiteUrl(e.target.value)}
                  placeholder="https://example.com/docs"
                  className={fieldClass}
                />
                <p className={helpClass}>
                  Supports regular and JavaScript-rendered (SPA) pages.
                </p>
              </div>

              {/* Include subpages toggle */}
              <div className="flex items-center justify-between border-t border-black/10 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-700">Include subpages</p>
                  <p className="text-xs text-gray-500 mt-0.5">Crawl same-domain links found on this page</p>
                </div>
                <button
                  type="button"
                  onClick={() => setIncludeSubpages(v => !v)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${includeSubpages ? 'bg-[#171717]' : 'bg-gray-200'}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${includeSubpages ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
              </div>

              {/* Max pages — only shown when subpages enabled */}
              {includeSubpages && (
                <div>
                  <label className={labelClass}>
                    Max pages <span className="text-gray-400 font-normal">(1–50)</span>
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={maxPages}
                    onChange={(e) => setMaxPages(Math.min(50, Math.max(1, parseInt(e.target.value) || 1)))}
                    className={fieldClass}
                  />
                  <p className={helpClass}>
                    Crawl will follow links from the starting URL up to this limit.
                  </p>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowWebsiteModal(false)
                  setWebsiteUrl('')
                  setIncludeSubpages(false)
                  setMaxPages(20)
                }}
                disabled={addingContent}
                className="rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCrawlWebsite}
                disabled={addingContent || !websiteUrl.trim()}
                className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
              >
                {addingContent ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Crawling...
                  </>
                ) : (
                  'Crawl Website'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
