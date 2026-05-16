'use client'

import { useState, useEffect } from 'react'
import { X, Download, Loader2, FileText, AlertCircle, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface Segment {
  id: string
  position: number
  content: string
  word_count: number
  tokens: number
  created_at: string
}

interface DocumentDetails {
  id: string
  title: string
  source_type: string
  source_url?: string
  s3_url?: string
  mime_type?: string
  file_size?: number
  chunk_count: number
  has_images: boolean
  image_count: number
  images: any[]
  created_at: string
  updated_at: string
  metadata: Record<string, any>
  data_source?: {
    id: string
    name: string
    type: string
  }
  content?: string
  segments: Segment[]
}

interface DocumentViewerProps {
  kbId: string
  docId: string
  docTitle: string
  onClose: () => void
  onDownload: () => Promise<void>
}

export default function DocumentViewer({
  kbId,
  docId,
  onClose,
  onDownload,
}: DocumentViewerProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [docDetails, setDocDetails] = useState<DocumentDetails | null>(null)
  const [activeTab, setActiveTab] = useState<'preview' | 'chunks'>('preview')
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadDocument()
  }, [docId])

  const loadDocument = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch document details with content and segments
      const details = await apiClient.getKnowledgeBaseDocument(kbId, docId)
      setDocDetails(details)
    } catch (err) {
      console.error('Error loading document:', err)
      setError(err instanceof Error ? err.message : 'Failed to load document')
    } finally {
      setLoading(false)
    }
  }

  const handleViewInNewTab = () => {
    if (docDetails?.s3_url) {
      window.open(docDetails.s3_url, '_blank')
    } else if (docDetails?.source_url) {
      window.open(docDetails.source_url, '_blank')
    }
  }

  const toggleChunk = (chunkId: string) => {
    const newExpanded = new Set(expandedChunks)
    if (newExpanded.has(chunkId)) {
      newExpanded.delete(chunkId)
    } else {
      newExpanded.add(chunkId)
    }
    setExpandedChunks(newExpanded)
  }

  const expandAllChunks = () => {
    if (docDetails) {
      setExpandedChunks(new Set(docDetails.segments.map(s => s.id)))
    }
  }

  const collapseAllChunks = () => {
    setExpandedChunks(new Set())
  }

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return 'N/A'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  const isPDF = (mimeType?: string) => {
    return mimeType === 'application/pdf' || docDetails?.title.toLowerCase().endsWith('.pdf')
  }

  const isOfficeDoc = (mimeType?: string) => {
    const officeTypes = [
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    ]
    return officeTypes.includes(mimeType || '') || 
           docDetails?.title.toLowerCase().match(/\.(doc|docx|xls|xlsx|ppt|pptx)$/)
  }

  const renderPreview = () => {
    if (!docDetails) return null

    const fileUrl = docDetails.s3_url || docDetails.source_url

    // PDF Preview using iframe
    if (isPDF(docDetails.mime_type) && fileUrl) {
      return (
        <div className="flex h-full min-h-0 flex-col">
          <div className="min-h-0 flex-1 overflow-hidden rounded-[1.5rem] border border-black/10 bg-[#f1eadc]">
            <iframe
              src={fileUrl}
              className="w-full h-full border-0"
              title={docDetails.title}
            />
          </div>
          <div className="px-4 py-3 text-center text-sm text-gray-600">
            PDF viewer. For better experience,{' '}
            <button
              onClick={handleViewInNewTab}
              className="font-semibold text-[#2d8b69] transition-colors hover:text-[#20664d]"
            >
              open in a new tab
            </button>
          </div>
        </div>
      )
    }

    // Office Document Preview (DOC, DOCX, XLS, XLSX, PPT, PPTX)
    if (isOfficeDoc(docDetails.mime_type) && fileUrl) {
      // Use Google Docs Viewer for Office documents
      const viewerUrl = `https://docs.google.com/viewer?url=${encodeURIComponent(fileUrl)}&embedded=true`
      
      return (
        <div className="flex h-full min-h-0 flex-col">
          <div className="min-h-0 flex-1 overflow-hidden rounded-[1.5rem] border border-black/10 bg-[#f1eadc]">
            <iframe
              src={viewerUrl}
              className="w-full h-full border-0"
              title={docDetails.title}
            />
          </div>
          <div className="px-4 py-3 text-center text-sm text-gray-600">
            If the document doesn't display, try{' '}
            <button
              onClick={handleViewInNewTab}
              className="font-semibold text-[#2d8b69] transition-colors hover:text-[#20664d]"
            >
              opening it in a new tab
            </button>
          </div>
        </div>
      )
    }

    return (
      <div className="h-full overflow-auto p-6">
        {docDetails.content ? (
          <div className="rounded-[1.5rem] border border-black/10 bg-[#fcfaf5] p-6">
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-[#2b2723]">
              {docDetails.content}
            </pre>
          </div>
        ) : (
          <div className="py-12 text-center">
            <FileText className="mx-auto mb-4 h-12 w-12 text-[#8a8378]" />
            <p className="text-gray-600">No preview available for this document</p>
            <p className="text-sm text-gray-500 mt-2">
              Try downloading the file or viewing it in a new tab
            </p>
            {fileUrl && (
              <button
                onClick={handleViewInNewTab}
                className="mt-4 inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
              >
                <ExternalLink className="w-4 h-4" />
                Open in New Tab
              </button>
            )}
          </div>
        )}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
        <div className="rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] p-8 shadow-[0_30px_80px_rgba(0,0,0,0.18)]">
          <div className="text-center">
            <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-[#2d8b69]" />
            <p className="text-gray-600">Loading document...</p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
        <div className="max-w-md rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] p-8 shadow-[0_30px_80px_rgba(0,0,0,0.18)]">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Failed to Load Document
            </h3>
            <p className="text-gray-600 mb-4">{error}</p>
            <div className="flex gap-2 justify-center">
              <button
                onClick={loadDocument}
                className="rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
              >
                Try Again
              </button>
              <button
                onClick={onClose}
                className="rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8]"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!docDetails) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
      <div className="flex h-[90vh] min-h-0 w-full max-w-6xl flex-col overflow-hidden rounded-[2rem] border border-black/10 bg-[#fcfaf5] shadow-[0_32px_90px_rgba(0,0,0,0.18)]">
        {/* Header */}
        <div className="border-b border-black/10 bg-white px-6 py-5">
          <div className="flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#6e675d]">
              <FileText className="h-3.5 w-3.5 text-[#2d8b69]" />
              Document Viewer
            </div>
            <h2 className="text-lg font-semibold text-gray-900 truncate">
              {docDetails.title}
            </h2>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-gray-500">
              <span className="inline-flex items-center rounded-full bg-[#f7f2e7] px-2.5 py-1 text-xs font-medium text-[#6e675d]">
                {docDetails.source_type}
              </span>
              <span className="inline-flex items-center rounded-full bg-[#eef7f1] px-2.5 py-1 text-xs font-medium text-[#2d8b69]">
                {formatFileSize(docDetails.file_size)}
              </span>
              <span className="inline-flex items-center rounded-full bg-[#f4efe4] px-2.5 py-1 text-xs font-medium text-[#5b564e]">
                {docDetails.chunk_count} chunks
              </span>
              {docDetails.has_images && (
                <span className="inline-flex items-center rounded-full bg-[#f1eadc] px-2.5 py-1 text-xs font-medium text-[#6e675d]">
                  {docDetails.image_count} images
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 ml-4">
            {(docDetails.s3_url || docDetails.source_url) && (
              <button
                onClick={handleViewInNewTab}
                className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-[#f1eadc] px-3 py-2 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8]"
                title="View in new tab"
              >
                <ExternalLink className="w-4 h-4" />
                Open
              </button>
            )}
            <button
              onClick={onDownload}
              className="rounded-full p-2 text-gray-600 transition-colors hover:bg-[#f7f2e7] hover:text-[#171717]"
              title="Download"
            >
              <Download className="w-5 h-5" />
            </button>
            <button
              onClick={onClose}
              className="rounded-full p-2 text-gray-600 transition-colors hover:bg-red-50 hover:text-red-600"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-black/10 px-6 py-3">
          <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActiveTab('preview')}
            className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition-colors ${
              activeTab === 'preview'
                ? 'bg-[#171717] text-white'
                : 'text-gray-500 hover:bg-[#f7f2e7] hover:text-[#171717]'
            }`}
          >
            Preview
          </button>
          <button
            onClick={() => setActiveTab('chunks')}
            className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition-colors ${
              activeTab === 'chunks'
                ? 'bg-[#171717] text-white'
                : 'text-gray-500 hover:bg-[#f7f2e7] hover:text-[#171717]'
            }`}
          >
            Chunks ({docDetails.segments.length})
          </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="min-h-0 flex-1 overflow-hidden bg-[#fcfaf5]">
          {activeTab === 'preview' ? (
            renderPreview()
          ) : (
            <div className="h-full overflow-auto p-6">
              <div className="space-y-4">
                {/* Chunk Controls */}
                <div className="flex items-center justify-between border-b border-black/10 pb-4">
                  <h3 className="text-sm font-medium text-gray-700">
                    {docDetails.segments.length} chunk{docDetails.segments.length !== 1 ? 's' : ''}
                  </h3>
                  <div className="flex gap-2">
                    <button
                      onClick={expandAllChunks}
                      className="text-xs font-semibold text-[#2d8b69] transition-colors hover:text-[#20664d]"
                    >
                      Expand All
                    </button>
                    <span className="text-gray-300">|</span>
                    <button
                      onClick={collapseAllChunks}
                      className="text-xs font-semibold text-[#2d8b69] transition-colors hover:text-[#20664d]"
                    >
                      Collapse All
                    </button>
                  </div>
                </div>

                {/* Chunks List */}
                {docDetails.segments.length === 0 ? (
                  <div className="py-12 text-center">
                    <FileText className="mx-auto mb-4 h-12 w-12 text-[#8a8378]" />
                    <p className="text-gray-600">No chunks available</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {docDetails.segments.map((segment) => {
                      const isExpanded = expandedChunks.has(segment.id)
                      return (
                        <div
                          key={segment.id}
                          className="overflow-hidden rounded-[1.3rem] border border-black/10 bg-white/85 transition-colors hover:bg-white"
                        >
                          <button
                            onClick={() => toggleChunk(segment.id)}
                            className="flex w-full items-center justify-between px-4 py-3 transition-colors hover:bg-[#fcfaf5]"
                          >
                            <div className="flex items-center gap-3 text-left">
                              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#eef7f1] text-xs font-semibold text-[#2d8b69]">
                                {segment.position}
                              </span>
                              <div>
                                <p className="text-sm font-medium text-gray-900">
                                  Chunk {segment.position}
                                </p>
                                <p className="text-xs text-gray-500">
                                  {segment.word_count} words · {segment.tokens} tokens
                                </p>
                              </div>
                            </div>
                            {isExpanded ? (
                              <ChevronUp className="w-5 h-5 text-gray-400" />
                            ) : (
                              <ChevronDown className="w-5 h-5 text-gray-400" />
                            )}
                          </button>
                          
                          {isExpanded && (
                            <div className="border-t border-black/10 bg-[#fcfaf5] px-4 py-3">
                              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-[#2b2723]">
                                {segment.content}
                              </pre>
                              <div className="mt-3 border-t border-black/10 pt-3 text-xs text-gray-500">
                                Created: {formatDate(segment.created_at)}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer with Metadata */}
        <div className="border-t border-black/10 bg-white px-6 py-4">
          <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <div className="rounded-[1rem] border border-black/10 bg-[#fcfaf5] px-3 py-3">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-gray-500">Created</p>
              <p className="mt-1 font-medium text-gray-900">{formatDate(docDetails.created_at)}</p>
            </div>
            <div className="rounded-[1rem] border border-black/10 bg-[#eef7f1] px-3 py-3">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-gray-500">Updated</p>
              <p className="mt-1 font-medium text-gray-900">{formatDate(docDetails.updated_at)}</p>
            </div>
            {docDetails.data_source && (
              <div className="rounded-[1rem] border border-black/10 bg-[#f7f2e7] px-3 py-3">
                <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-gray-500">Data Source</p>
                <p className="mt-1 font-medium text-gray-900">{docDetails.data_source.name}</p>
              </div>
            )}
            {docDetails.mime_type && (
              <div className="rounded-[1rem] border border-black/10 bg-[#f4efe4] px-3 py-3">
                <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-gray-500">Type</p>
                <p className="mt-1 font-medium text-gray-900">{docDetails.mime_type}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
