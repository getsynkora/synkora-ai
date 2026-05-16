'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  BookOpen,
  Plus,
  Edit,
  Trash2,
  FileText,
  AlertCircle,
  CheckCircle,
  Search,
  FolderOpen,
  ChevronRight,
  Home,
  MoreHorizontal
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface KnowledgeBase {
  id: number
  name: string
  description: string
  vector_db_provider: string
  embedding_provider: string
  embedding_model: string
  document_count: number
  total_chunks: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export default function KnowledgeBasesPage() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [filteredKBs, setFilteredKBs] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; kb: KnowledgeBase | null }>({
    show: false,
    kb: null,
  })
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchKnowledgeBases()
  }, [])

  useEffect(() => {
    filterKnowledgeBases()
  }, [searchQuery, knowledgeBases])

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest('[data-kb-menu-root="true"]')) return
      setOpenMenuId(null)
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpenMenuId(null)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [])

  const fetchKnowledgeBases = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getKnowledgeBases()
      setKnowledgeBases(Array.isArray(data) ? data : [])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An error occurred'
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  const filterKnowledgeBases = () => {
    let filtered = knowledgeBases

    // Search filter
    if (searchQuery) {
      filtered = filtered.filter(kb =>
        kb.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        kb.description?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    setFilteredKBs(filtered)
  }

  const openDeleteModal = (kb: KnowledgeBase) => {
    setDeleteModal({ show: true, kb })
  }

  const closeDeleteModal = () => {
    setDeleteModal({ show: false, kb: null })
  }

  const confirmDelete = async () => {
    if (!deleteModal.kb) return

    setDeleting(true)
    try {
      await apiClient.deleteKnowledgeBase(deleteModal.kb.id.toString())
      toast.success(`"${deleteModal.kb.name}" has been deleted`)
      closeDeleteModal()
      fetchKnowledgeBases()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete'
      toast.error(errorMessage)
    } finally {
      setDeleting(false)
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading your knowledge bases...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 text-sm mb-4">
          <Link href="/" className="flex items-center gap-1 text-gray-500 transition-colors hover:text-[#171717]">
            <Home className="w-3.5 h-3.5" />
            Home
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-gray-900 font-medium">Knowledge Bases</span>
        </div>

        {/* Header */}
        <div className="mb-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Your Knowledge</h1>
              <p className="mt-1 text-sm text-gray-600 hidden sm:block">
                Store and organize information for your AI agents to use
              </p>
            </div>
            <Link
              href="/knowledge-bases/create"
              className="inline-flex flex-shrink-0 items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
            >
              <Plus className="w-4 h-4 md:w-5 md:h-5" />
              <span className="hidden sm:inline">Add Knowledge Base</span>
              <span className="sm:hidden">Add</span>
            </Link>
          </div>

          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f3ecde] p-2.5">
                  <BookOpen className="h-[18px] w-[18px] text-[#171717]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Knowledge Bases</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">{knowledgeBases.length}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#e8f4ee] p-2.5">
                  <FileText className="h-[18px] w-[18px] text-[#2d8b69]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Total Documents</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {knowledgeBases.reduce((sum, kb) => sum + kb.document_count, 0)}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f1eadc] p-2.5">
                  <CheckCircle className="h-[18px] w-[18px] text-[#5b564e]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Active</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {knowledgeBases.filter(kb => kb.is_active).length}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Search Bar - Simplified */}
          {knowledgeBases.length > 0 && (
            <div className="relative">
              <Search className="absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search your knowledge bases..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-[1.2rem] border border-black/10 bg-white/80 py-3 pl-11 pr-4 text-sm text-gray-900 shadow-[0_12px_28px_rgba(0,0,0,0.04)] focus:border-[#2d8b69] focus:outline-none focus:ring-2 focus:ring-[#2d8b69]/15"
              />
            </div>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 rounded-[1.3rem] border border-red-200 bg-red-50/90 p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-600" />
              <p className="text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Knowledge Bases Grid */}
        {filteredKBs.length === 0 ? (
          <div className="rounded-[2rem] border border-black/10 bg-white/80 p-10 text-center shadow-[0_22px_55px_rgba(0,0,0,0.06)]">
            {/* Illustration */}
            <div className="relative mx-auto mb-6 h-28 w-28">
              <div className="absolute inset-0 rotate-6 rounded-[1.75rem] bg-[#f3ecde]"></div>
              <div className="absolute inset-0 flex items-center justify-center rounded-[1.75rem] border border-black/10 bg-white shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
                <FolderOpen className="w-10 h-10 text-[#2d8b69]" />
              </div>
            </div>

            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {knowledgeBases.length === 0 ? 'Create your first knowledge base' : 'No results found'}
            </h3>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              {knowledgeBases.length === 0
                ? 'Knowledge bases help your AI agents answer questions using your own documents, websites, and content.'
                : 'Try adjusting your search to find what you\'re looking for.'}
            </p>
            {knowledgeBases.length === 0 && (
              <Link
                href="/knowledge-bases/create"
                className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
              >
                <Plus className="w-5 h-5" />
                Add Knowledge Base
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredKBs.map((kb) => (
              <div
                key={kb.id}
                className="group relative flex min-h-[292px] flex-col rounded-[1.7rem] border border-black/10 bg-white/80 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-all hover:-translate-y-0.5 hover:border-black/15 hover:shadow-[0_22px_50px_rgba(0,0,0,0.08)]"
              >
                <div
                  className="absolute right-4 top-4 z-20"
                  data-kb-menu-root="true"
                >
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setOpenMenuId(openMenuId === kb.id ? null : kb.id)
                    }}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-black/10 bg-white/90 text-[#5b564e] shadow-[0_8px_18px_rgba(0,0,0,0.08)] transition-colors hover:bg-white hover:text-[#171717]"
                    aria-label={`Open actions for ${kb.name}`}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </button>

                  {openMenuId === kb.id && (
                    <div className="absolute right-0 top-11 w-40 overflow-hidden rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] py-1.5 shadow-[0_20px_45px_rgba(0,0,0,0.14)]">
                      <Link
                        href={`/knowledge-bases/${kb.id}/edit`}
                        prefetch={false}
                        onClick={() => setOpenMenuId(null)}
                        className="flex items-center gap-2.5 px-4 py-2.5 text-sm font-medium text-[#171717] transition-colors hover:bg-[#f3ecde]"
                      >
                        <Edit className="h-4 w-4" />
                        Edit
                      </Link>
                      <button
                        type="button"
                        onClick={() => {
                          setOpenMenuId(null)
                          openDeleteModal(kb)
                        }}
                        className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </button>
                    </div>
                  )}
                </div>

                <Link
                  href={`/knowledge-bases/${kb.id}`}
                  prefetch={false}
                  className="flex flex-1 flex-col p-5 pr-16 focus:outline-none"
                  aria-label={`Open ${kb.name}`}
                >
                  <div className="mb-4 flex items-start gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <div className="rounded-[1.1rem] bg-[#f3ecde] p-3 transition-colors group-hover:bg-[#ece2cd]">
                        <BookOpen className="w-5 h-5 text-[#171717]" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="truncate text-[1.05rem] font-semibold text-gray-900">
                          {kb.name}
                        </h3>
                        <p className="mt-1 line-clamp-2 text-sm text-gray-500">
                          {kb.description || 'No description added'}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="mb-4 flex flex-wrap gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                        kb.is_active
                          ? 'bg-[#e8f4ee] text-[#2d8b69]'
                          : 'bg-[#f1eadc] text-[#6e675d]'
                      }`}
                    >
                      <span
                        className={`mr-1.5 h-1.5 w-1.5 rounded-full ${
                          kb.is_active ? 'bg-[#2d8b69]' : 'bg-[#8a8378]'
                        }`}
                      />
                      {kb.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <span className="inline-flex items-center rounded-full bg-[#f7f2e7] px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-[#6e675d]">
                      {kb.vector_db_provider}
                    </span>
                    <span className="inline-flex items-center rounded-full bg-[#f7f2e7] px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-[#6e675d]">
                      {kb.embedding_provider}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2.5">
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-3 py-3">
                      <div className="text-[10px] font-medium uppercase leading-snug tracking-[0.1em] text-gray-500 break-words">Documents</div>
                      <div className="mt-1 text-base font-semibold text-gray-900">{kb.document_count}</div>
                    </div>
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#eef7f1] px-3 py-3">
                      <div className="text-[10px] font-medium uppercase leading-snug tracking-[0.1em] text-gray-500 break-words">Chunks</div>
                      <div className="mt-1 text-base font-semibold text-gray-900">{kb.total_chunks}</div>
                    </div>
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#f4efe4] px-3 py-3">
                      <div className="text-[10px] font-medium uppercase leading-snug tracking-[0.1em] text-gray-500 break-words">Updated</div>
                      <div className="mt-1 text-sm font-semibold text-gray-900">{formatDate(kb.updated_at)}</div>
                    </div>
                  </div>
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteModal.show && deleteModal.kb && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.18)]">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-[1rem] bg-red-50 p-2.5">
                <Trash2 className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Delete Knowledge Base</h3>
            </div>

            <p className="mb-6 text-gray-600">
              Are you sure you want to delete <span className="font-semibold text-gray-900">"{deleteModal.kb.name}"</span>?
              All documents and data will be permanently removed.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={closeDeleteModal}
                disabled={deleting}
                className="rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
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
