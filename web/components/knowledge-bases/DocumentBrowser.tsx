'use client'

import { useState, useEffect } from 'react'
import {
  FileText,
  Search,
  Download,
  Trash2,
  Image as ImageIcon,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Eye,
  RefreshCw,
  XCircle
} from 'lucide-react'
import toast from 'react-hot-toast'
import DocumentViewer from './DocumentViewer'

interface Document {
  id: number
  title: string
  source_type: string
  source_url?: string
  file_size?: number
  chunk_count: number
  has_images: boolean
  image_count: number
  status: string
  created_at: string
  updated_at: string
  metadata: Record<string, any>
}

interface DocumentBrowserProps {
  kbId: string
  onGetDocuments: (params: any) => Promise<any>
  onDeleteDocument: (docId: string) => Promise<void>
  onBulkDelete: (docIds: number[]) => Promise<void>
  onDownloadDocument: (docId: string) => Promise<Blob>
  onReprocessDocument?: (docId: string) => Promise<void>
  onCancelDocument?: (docId: string) => Promise<void>
}

export default function DocumentBrowser({
  kbId,
  onGetDocuments,
  onDeleteDocument,
  onBulkDelete,
  onDownloadDocument,
  onReprocessDocument,
  onCancelDocument,
}: DocumentBrowserProps) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedDocs, setSelectedDocs] = useState<Set<number>>(new Set())
  const [viewingDoc, setViewingDoc] = useState<Document | null>(null)
  
  // Pagination
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  
  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [sourceTypeFilter, setSourceTypeFilter] = useState('')
  const [hasImagesFilter, setHasImagesFilter] = useState<boolean | undefined>()
  const [sortBy] = useState('created_at')
  const [sortOrder] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    fetchDocuments()
  }, [page, searchQuery, sourceTypeFilter, hasImagesFilter, sortBy, sortOrder])

  // Poll while any document is still processing so status updates without manual refresh
  useEffect(() => {
    const hasPending = documents.some(
      (doc) => doc.status === 'PENDING' || doc.status === 'PROCESSING'
    )
    if (!hasPending) return
    const timer = setInterval(fetchDocuments, 5000)
    return () => clearInterval(timer)
  }, [documents])

  const fetchDocuments = async () => {
    try {
      setLoading(true)
      const params: any = {
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
      }
      
      if (searchQuery) params.search = searchQuery
      if (sourceTypeFilter) params.source_type = sourceTypeFilter
      if (hasImagesFilter !== undefined) params.has_images = hasImagesFilter

      const data = await onGetDocuments(params)
      setDocuments(data.documents || [])
      setTotal(data.total || 0)
      setTotalPages(data.total_pages || 0)
    } catch (error) {
      toast.error('Failed to load documents')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (docId: number) => {
    if (!confirm('Are you sure you want to delete this document?')) return

    try {
      await onDeleteDocument(docId.toString())
      toast.success('Document deleted successfully')
      fetchDocuments()
    } catch {
      toast.error('Failed to delete document')
    }
  }

  const handleBulkDelete = async () => {
    if (selectedDocs.size === 0) return
    if (!confirm(`Are you sure you want to delete ${selectedDocs.size} document(s)?`)) return

    try {
      await onBulkDelete(Array.from(selectedDocs))
      toast.success(`Deleted ${selectedDocs.size} document(s)`)
      setSelectedDocs(new Set())
      fetchDocuments()
    } catch {
      toast.error('Failed to delete documents')
    }
  }

  const handleReprocess = async (docId: number) => {
    if (!onReprocessDocument) return
    try {
      await onReprocessDocument(docId.toString())
      toast.success('Document queued for reprocessing')
      fetchDocuments()
    } catch {
      toast.error('Failed to reprocess document')
    }
  }

  const handleCancel = async (docId: number) => {
    if (!onCancelDocument) return
    try {
      await onCancelDocument(docId.toString())
      toast.success('Document processing cancelled')
      fetchDocuments()
    } catch {
      toast.error('Failed to cancel document processing')
    }
  }

  const handleDownload = async (doc: Document) => {
    try {
      const blob = await onDownloadDocument(doc.id.toString())
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = doc.title
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      toast.success('Download started')
    } catch {
      toast.error('Failed to download document')
    }
  }

  const toggleSelectDoc = (docId: number) => {
    const newSelected = new Set(selectedDocs)
    if (newSelected.has(docId)) {
      newSelected.delete(docId)
    } else {
      newSelected.add(docId)
    }
    setSelectedDocs(newSelected)
  }

  const toggleSelectAll = () => {
    if (selectedDocs.size === documents.length) {
      setSelectedDocs(new Set())
    } else {
      setSelectedDocs(new Set(documents.map(d => d.id)))
    }
  }

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return 'N/A'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  if (loading && documents.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 motion-safe:animate-spin text-leaf" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-ash" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              setPage(1)
            }}
            placeholder="Search documents…"
            className="w-full rounded-[1rem] border border-black/10 bg-white px-4 py-3 pl-10 text-sm text-ink focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
          />
        </div>
        
        <select
          value={sourceTypeFilter}
          onChange={(e) => {
            setSourceTypeFilter(e.target.value)
            setPage(1)
          }}
          className="rounded-[1rem] border border-black/10 bg-white px-4 py-3 text-sm text-ink focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
        >
          <option value="">All Sources</option>
          <option value="manual">Manual Upload</option>
          <option value="SLACK">Slack</option>
          <option value="GMAIL">Gmail</option>
          <option value="github">GitHub</option>
        </select>

        <select
          value={hasImagesFilter === undefined ? '' : hasImagesFilter.toString()}
          onChange={(e) => {
            setHasImagesFilter(e.target.value === '' ? undefined : e.target.value === 'true')
            setPage(1)
          }}
          className="rounded-[1rem] border border-black/10 bg-white px-4 py-3 text-sm text-ink focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
        >
          <option value="">All Documents</option>
          <option value="true">With Images</option>
          <option value="false">Without Images</option>
        </select>
      </div>

      {/* Bulk Actions */}
      {selectedDocs.size > 0 && (
        <div className="flex items-center justify-between rounded-[1.25rem] border border-black/10 bg-paper p-4">
          <span className="text-sm font-medium text-ink">
            {selectedDocs.size} document(s) selected
          </span>
          <button
            onClick={handleBulkDelete}
            className="flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-black"
          >
            <Trash2 className="w-4 h-4" />
            Delete Selected
          </button>
        </div>
      )}

      {/* Documents Table */}
      {documents.length === 0 ? (
        <div className="rounded-[1.6rem] border border-black/10 bg-cream py-12 text-center">
          <FileText className="mx-auto mb-4 h-16 w-16 text-ash" />
          <h3 className="text-lg font-semibold text-ink mb-2">No documents found</h3>
          <p className="text-ink-soft">Upload documents to get started</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-[1.6rem] border border-black/10 bg-white/80">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-black/10 bg-cream">
                <tr>
                  <th className="px-4 py-3 text-left">
                    <input
                      type="checkbox"
                      checked={selectedDocs.size === documents.length}
                      onChange={toggleSelectAll}
                      className="rounded border-taupe"
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">
                    Document
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">
                    Source
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">
                    Size
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">
                    Chunks
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">
                    Created
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/10">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-cream">
                    <td className="px-4 py-4">
                      <input
                        type="checkbox"
                        checked={selectedDocs.has(doc.id)}
                        onChange={() => toggleSelectDoc(doc.id)}
                        className="rounded border-taupe"
                      />
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <FileText className="h-5 w-5 flex-shrink-0 text-leaf" />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-ink truncate">
                            {doc.title}
                          </p>
                          {doc.has_images && (
                            <div className="flex items-center gap-1 text-xs text-ink-mute mt-1">
                              <ImageIcon className="w-3 h-3" />
                              {doc.image_count} image{doc.image_count !== 1 ? 's' : ''}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className="inline-flex items-center rounded-full bg-paper px-2.5 py-1 text-xs font-medium text-ink-mute">
                        {doc.source_type}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm text-ink-mute">
                      {formatFileSize(doc.file_size)}
                    </td>
                    <td className="px-4 py-4 text-sm text-ink-mute">
                      {doc.status === 'PENDING' || doc.status === 'PROCESSING' ? (
                        <span className="inline-flex items-center gap-1 text-warn">
                          <Loader2 className="w-3 h-3 motion-safe:animate-spin" />
                          Processing
                        </span>
                      ) : doc.status === 'ERROR' ? (
                        <span className="text-leaf" title={doc.metadata?.error || 'Processing failed'}>Error</span>
                      ) : (
                        doc.chunk_count
                      )}
                    </td>
                    <td className="px-4 py-4 text-sm text-ink-mute">
                      {formatDate(doc.created_at)}
                    </td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {doc.status === 'PROCESSING' && onCancelDocument && (
                          <button
                            onClick={() => handleCancel(doc.id)}
                            className="rounded-full p-2 text-ash transition-colors hover:bg-sand-deep hover:text-warn"
                            title="Cancel processing"
                          >
                            <XCircle className="w-4 h-4" />
                          </button>
                        )}
                        {(doc.status === 'PENDING' || doc.status === 'ERROR') && onReprocessDocument && (
                          <button
                            onClick={() => handleReprocess(doc.id)}
                            className="rounded-full p-2 text-ash transition-colors hover:bg-leaf-wash hover:text-leaf"
                            title="Reprocess document"
                          >
                            <RefreshCw className="w-4 h-4" />
                          </button>
                        )}
                        {doc.status === 'COMPLETED' && (
                          <button
                            onClick={() => setViewingDoc(doc)}
                            className="rounded-full p-2 text-ash transition-colors hover:bg-leaf-wash hover:text-leaf"
                            title="View"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDownload(doc)}
                          className="rounded-full p-2 text-ash transition-colors hover:bg-paper hover:text-ink"
                          title="Download"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="rounded-full p-2 text-ash transition-colors hover:bg-blush-wash hover:text-danger"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-black/10 px-4 py-3">
              <div className="text-sm text-ink-soft">
                Showing <span className="font-medium">{(page - 1) * pageSize + 1}</span> to{' '}
                <span className="font-medium">{Math.min(page * pageSize, total)}</span> of{' '}
                <span className="font-medium">{total}</span> documents
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="rounded-[0.9rem] border border-black/10 bg-white p-2 transition-colors hover:bg-paper disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <span className="text-sm text-ink-soft">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="rounded-[0.9rem] border border-black/10 bg-white p-2 transition-colors hover:bg-paper disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Document Viewer */}
      {viewingDoc && (
        <DocumentViewer
          kbId={kbId}
          docId={viewingDoc.id.toString()}
          docTitle={viewingDoc.title}
          onClose={() => setViewingDoc(null)}
          onDownload={async () => {
            await handleDownload(viewingDoc)
          }}
        />
      )}
    </div>
  )
}
