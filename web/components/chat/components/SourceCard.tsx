'use client'

import React, { useState } from 'react'
import { ExternalLink, FileText, Mail, MessageSquare, ChevronDown, ChevronRight, File, Download } from 'lucide-react'
import { RAGSource } from '../types'

interface SourceCardProps {
  source: RAGSource
  compact?: boolean
  className?: string
}

/**
 * Get document title from source
 */
function getDocumentTitle(source: RAGSource): string {
  // Try multiple sources for the title
  if (source.title) return source.title
  if (source.display?.title) return source.display.title
  if (source.metadata?.title) return source.metadata.title
  if (source.metadata?.external_id) {
    // Clean up filename - remove extension and path
    const filename = source.metadata.external_id.split('/').pop() || source.metadata.external_id
    return filename.replace(/\.[^/.]+$/, '').replace(/_/g, ' ')
  }
  return 'Document'
}

/**
 * Get source type icon
 */
function getSourceIcon(type: string, size: number = 14) {
  switch (type.toLowerCase()) {
    case 'slack message':
    case 'slack':
      return <MessageSquare size={size} />
    case 'email':
    case 'gmail':
      return <Mail size={size} />
    case 'pdf':
      return <FileText size={size} />
    default:
      return <File size={size} />
  }
}

/**
 * CompactSourceCard - Minimal inline source display
 */
export function SourceCard({ source, compact = false, className = '' }: SourceCardProps) {
  const display = source.display || { type: source.source_type || 'Document' }
  const displayType = display.type || source.source_type || source.metadata?.file_type || 'Document'
  const title = getDocumentTitle(source)
  const score = ((source.score || 0) * 100).toFixed(0)

  if (compact) {
    return (
      <div className={`flex items-center gap-2 px-2 py-1.5 bg-cream rounded-lg text-xs ${className}`}>
        <span className="text-ash">{getSourceIcon(displayType, 12)}</span>
        <span className="text-ink-soft truncate flex-1">{title}</span>
        <span className="text-leaf font-medium">{score}%</span>
      </div>
    )
  }

  return (
    <div className={`bg-cream rounded-lg p-3 text-xs border border-sand hover:border-line transition-[color,background-color,border-color,box-shadow,opacity,transform] ${className}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-ash flex-shrink-0">{getSourceIcon(displayType)}</span>
          <span className="font-medium text-ink truncate">{title}</span>
        </div>
        <span className="text-leaf font-bold flex-shrink-0">{score}%</span>
      </div>

      {source.text_preview && (
        <p className="mt-2 text-ink-soft line-clamp-2 leading-relaxed pl-5">
          {source.text_preview}
        </p>
      )}

      {(source.external_url || source.presigned_url) && (
        <div className="mt-2 pl-5">
          <a
            href={source.external_url || source.presigned_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-leaf hover:text-forest hover:underline"
          >
            {source.presigned_url ? <Download size={12} /> : <ExternalLink size={12} />}
            <span>{source.presigned_url ? 'Download' : 'View'}</span>
          </a>
        </div>
      )}
    </div>
  )
}

/**
 * Group sources by document
 */
interface GroupedDocument {
  documentId: string
  title: string
  type: string
  url?: string
  presignedUrl?: string
  chunks: RAGSource[]
  topScore: number
}

function groupSourcesByDocument(sources: RAGSource[]): GroupedDocument[] {
  const groups: Record<string, GroupedDocument> = {}

  sources.forEach((source) => {
    const docId = source.document_id || source.metadata?.document_id || source.metadata?.external_id || `doc-${Math.random()}`

    if (!groups[docId]) {
      const title = getDocumentTitle(source)
      const display = source.display || { type: source.source_type || 'Document' }
      const type = display.type || source.source_type || source.metadata?.file_type || 'Document'

      groups[docId] = {
        documentId: docId,
        title,
        type,
        url: source.external_url,
        presignedUrl: source.presigned_url,
        chunks: [],
        topScore: 0,
      }
    }

    groups[docId].chunks.push(source)
    const score = source.score || 0
    if (score > groups[docId].topScore) {
      groups[docId].topScore = score
    }
  })

  // Sort by top score
  return Object.values(groups).sort((a, b) => b.topScore - a.topScore)
}

/**
 * DocumentGroup - Expandable document with chunks
 */
interface DocumentGroupProps {
  group: GroupedDocument
  defaultExpanded?: boolean
}

function DocumentGroup({ group, defaultExpanded = false }: DocumentGroupProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const hasMultipleChunks = group.chunks.length > 1

  return (
    <div className="border border-line rounded-lg overflow-hidden bg-white">
      {/* Document Header */}
      <div
        className={`flex items-center gap-2 px-3 py-2 bg-cream ${hasMultipleChunks ? 'cursor-pointer hover:bg-sand' : ''}`}
        onClick={() => hasMultipleChunks && setExpanded(!expanded)}
      >
        {hasMultipleChunks && (
          <span className="text-ash flex-shrink-0">
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
        )}
        <span className="text-ink-mute flex-shrink-0">{getSourceIcon(group.type, 14)}</span>
        <span className="font-semibold text-ink truncate flex-1 text-sm">{group.title}</span>
        <div className="flex items-center gap-2 flex-shrink-0">
          {hasMultipleChunks && (
            <span className="text-xs text-ink-mute bg-line px-1.5 py-0.5 rounded">
              {group.chunks.length} chunks
            </span>
          )}
          <span className="text-leaf font-bold text-sm">
            {(group.topScore * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Document Actions */}
      {(group.url || group.presignedUrl) && (
        <div className="px-3 py-1.5 border-t border-sand bg-white">
          <a
            href={group.url || group.presignedUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-leaf hover:text-forest hover:underline"
          >
            {group.presignedUrl ? <Download size={12} /> : <ExternalLink size={12} />}
            <span>{group.presignedUrl ? 'Download Document' : 'View Document'}</span>
          </a>
        </div>
      )}

      {/* Chunks - Show if expanded or single chunk */}
      {(expanded || !hasMultipleChunks) && (
        <div className="border-t border-sand">
          {group.chunks.map((chunk, idx) => (
            <div
              key={chunk.segment_id || `chunk-${idx}`}
              className={`px-3 py-2 text-xs ${idx > 0 ? 'border-t border-cream' : ''}`}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-ash">
                  {hasMultipleChunks ? `Chunk ${(chunk.metadata?.chunk_index ?? idx) + 1}` : 'Content'}
                </span>
                <span className="text-leaf font-medium">
                  {((chunk.score || 0) * 100).toFixed(0)}%
                </span>
              </div>
              {chunk.text_preview && (
                <p className="text-ink-soft line-clamp-2 leading-relaxed">
                  {chunk.text_preview}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * SourcesList - Display grouped sources with expand/collapse
 */
interface SourcesListProps {
  sources: RAGSource[]
  maxVisible?: number
  className?: string
}

export function SourcesList({
  sources,
  maxVisible = 3,
  className = '',
}: SourcesListProps) {
  const [showAll, setShowAll] = useState(false)

  if (!sources || sources.length === 0) return null

  const groupedDocs = groupSourcesByDocument(sources)
  const visibleDocs = showAll ? groupedDocs : groupedDocs.slice(0, maxVisible)
  const hasMore = groupedDocs.length > maxVisible

  return (
    <div className={`mt-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-bold text-ink-mute">
          Sources ({sources.length} chunks from {groupedDocs.length} {groupedDocs.length === 1 ? 'document' : 'documents'})
        </h4>
        {hasMore && (
          <button
            onClick={() => setShowAll(!showAll)}
            className="text-xs text-leaf hover:text-forest font-medium"
          >
            {showAll ? 'Show less' : `+${groupedDocs.length - maxVisible} more`}
          </button>
        )}
      </div>

      {/* Document Groups */}
      <div className="space-y-2">
        {visibleDocs.map((group, idx) => (
          <DocumentGroup
            key={group.documentId}
            group={group}
            defaultExpanded={idx === 0}
          />
        ))}
      </div>
    </div>
  )
}
