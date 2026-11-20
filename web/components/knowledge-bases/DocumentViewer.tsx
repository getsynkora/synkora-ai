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
          <div className="min-h-0 flex-1 overflow-hidden rounded-[1.5rem] border border-black/10 bg-sand-deep">
            <iframe
              src={fileUrl}
              className="w-full h-full border-0"
              title={docDetails.title}
            />
          </div>
          <div className="px-4 py-3 text-center text-sm text-ink-soft">
            PDF viewer. For better experience,{' '}
            <button
              onClick={handleViewInNewTab}
              className="font-semibold text-leaf transition-colors hover:text-forest"
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
          <div className="min-h-0 flex-1 overflow-hidden rounded-[1.5rem] border border-black/10 bg-sand-deep">
            <iframe
              src={viewerUrl}
              className="w-full h-full border-0"
              title={docDetails.title}
            />
          </div>
          <div className="px-4 py-3 text-center text-sm text-ink-soft">
            If the document doesn't display, try{' '}
            <button
              onClick={handleViewInNewTab}
              className="font-semibold text-leaf transition-colors hover:text-forest"
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
          <div className="rounded-[1.5rem] border border-black/10 bg-cream p-6">
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-night">
              {docDetails.content}
            </pre>
          </div>
        ) : (
          <div className="py-12 text-center">
            <FileText className="mx-auto mb-4 h-12 w-12 text-ash" />
            <p className="text-ink-soft">No preview available for this document</p>
            <p className="text-sm text-ink-mute mt-2">
              Try downloading the file or viewing it in a new tab
            </p>
            {fileUrl && (
              <button
                onClick={handleViewInNewTab}
                className="mt-4 inline-flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
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
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
        <div className="rounded-[1.8rem] border border-black/10 bg-cream p-8 shadow-soft">
          <div className="text-center">
            <Loader2 className="mx-auto mb-4 h-12 w-12 motion-safe:animate-spin text-leaf" />
            <p className="text-ink-soft">Loading document…</p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
        <div className="max-w-md rounded-[1.8rem] border border-black/10 bg-cream p-8 shadow-soft">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 text-leaf mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-ink mb-2">
              Failed to Load Document
            </h3>
            <p className="text-ink-soft mb-4">{error}</p>
            <div className="flex gap-2 justify-center">
              <button
                onClick={loadDocument}
                className="rounded-[1rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
              >
                Try Again
              </button>
              <button
                onClick={onClose}
                className="rounded-[1rem] border border-black/10 bg-sand-deep px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-line"
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="flex h-[90vh] min-h-0 w-full max-w-6xl flex-col overflow-hidden rounded-[2rem] border border-black/10 bg-cream shadow-soft">
        {/* Header */}
        <div className="border-b border-black/10 bg-white px-6 py-5">
          <div className="flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold text-ink truncate">
              {docDetails.title}
            </h2>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-ink-mute">
              <span className="inline-flex items-center rounded-full bg-paper px-2.5 py-1 text-xs font-medium text-ink-mute">
                {docDetails.source_type}
              </span>
              <span className="inline-flex items-center rounded-full bg-leaf-wash px-2.5 py-1 text-xs font-medium text-leaf">
                {formatFileSize(docDetails.file_size)}
              </span>
              <span className="inline-flex items-center rounded-full bg-paper px-2.5 py-1 text-xs font-medium text-ink-soft">
                {docDetails.chunk_count} chunks
              </span>
              {docDetails.has_images && (
                <span className="inline-flex items-center rounded-full bg-sand-deep px-2.5 py-1 text-xs font-medium text-ink-mute">
                  {docDetails.image_count} images
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 ml-4">
            {(docDetails.s3_url || docDetails.source_url) && (
              <button
                onClick={handleViewInNewTab}
                className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-sand-deep px-3 py-2 text-sm font-semibold text-ink transition-colors hover:bg-line"
                title="View in new tab"
              >
                <ExternalLink className="w-4 h-4" />
                Open
              </button>
            )}
            <button
              onClick={onDownload}
              className="rounded-full p-2 text-ink-soft transition-colors hover:bg-paper hover:text-ink"
              title="Download"
            >
              <Download className="w-5 h-5" />
            </button>
            <button
              onClick={onClose}
              className="rounded-full p-2 text-ink-soft transition-colors hover:bg-blush-wash hover:text-leaf"
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
            className={`rounded-full px-4 py-2 text-xs font-semibold transition-colors ${
              activeTab === 'preview'
                ? 'bg-ink text-white'
                : 'text-ink-mute hover:bg-paper hover:text-ink'
            }`}
          >
            Preview
          </button>
          <button
            onClick={() => setActiveTab('chunks')}
            className={`rounded-full px-4 py-2 text-xs font-semibold transition-colors ${
              activeTab === 'chunks'
                ? 'bg-ink text-white'
                : 'text-ink-mute hover:bg-paper hover:text-ink'
            }`}
          >
            Chunks ({docDetails.segments.length})
          </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="min-h-0 flex-1 overflow-hidden bg-cream">
          {activeTab === 'preview' ? (
            renderPreview()
          ) : (
            <div className="h-full overflow-auto p-6">
              <div className="space-y-4">
                {/* Chunk Controls */}
                <div className="flex items-center justify-between border-b border-black/10 pb-4">
                  <h3 className="text-sm font-medium text-ink-soft">
                    {docDetails.segments.length} chunk{docDetails.segments.length !== 1 ? 's' : ''}
                  </h3>
                  <div className="flex gap-2">
                    <button
                      onClick={expandAllChunks}
                      className="text-xs font-semibold text-leaf transition-colors hover:text-forest"
                    >
                      Expand All
                    </button>
                    <span className="text-taupe">|</span>
                    <button
                      onClick={collapseAllChunks}
                      className="text-xs font-semibold text-leaf transition-colors hover:text-forest"
                    >
                      Collapse All
                    </button>
                  </div>
                </div>

                {/* Chunks List */}
                {docDetails.segments.length === 0 ? (
                  <div className="py-12 text-center">
                    <FileText className="mx-auto mb-4 h-12 w-12 text-ash" />
                    <p className="text-ink-soft">No chunks available</p>
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
                            className="flex w-full items-center justify-between px-4 py-3 transition-colors hover:bg-cream"
                          >
                            <div className="flex items-center gap-3 text-left">
                              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-leaf-wash text-xs font-semibold text-leaf">
                                {segment.position}
                              </span>
                              <div>
                                <p className="text-sm font-medium text-ink">
                                  Chunk {segment.position}
                                </p>
                                <p className="text-xs text-ink-mute">
                                  {segment.word_count} words, {segment.tokens} tokens
                                </p>
                              </div>
                            </div>
                            {isExpanded ? (
                              <ChevronUp className="w-5 h-5 text-ash" />
                            ) : (
                              <ChevronDown className="w-5 h-5 text-ash" />
                            )}
                          </button>
                          
                          {isExpanded && (
                            <div className="border-t border-black/10 bg-cream px-4 py-3">
                              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-night">
                                {segment.content}
                              </pre>
                              <div className="mt-3 border-t border-black/10 pt-3 text-xs text-ink-mute">
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
            <div className="rounded-[1rem] border border-black/10 bg-cream px-3 py-3">
              <p className="text-[11px] font-medium text-ink-mute">Created</p>
              <p className="mt-1 font-medium text-ink">{formatDate(docDetails.created_at)}</p>
            </div>
            <div className="rounded-[1rem] border border-black/10 bg-leaf-wash px-3 py-3">
              <p className="text-[11px] font-medium text-ink-mute">Updated</p>
              <p className="mt-1 font-medium text-ink">{formatDate(docDetails.updated_at)}</p>
            </div>
            {docDetails.data_source && (
              <div className="rounded-[1rem] border border-black/10 bg-paper px-3 py-3">
                <p className="text-[11px] font-medium text-ink-mute">Data Source</p>
                <p className="mt-1 font-medium text-ink">{docDetails.data_source.name}</p>
              </div>
            )}
            {docDetails.mime_type && (
              <div className="rounded-[1rem] border border-black/10 bg-paper px-3 py-3">
                <p className="text-[11px] font-medium text-ink-mute">Type</p>
                <p className="mt-1 font-medium text-ink">{docDetails.mime_type}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
