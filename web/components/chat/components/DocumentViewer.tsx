'use client'

import { useState } from 'react'
import { FileText, Download, ExternalLink, Maximize2, Minimize2, X } from 'lucide-react'

interface DocumentViewerProps {
  url: string
  filename?: string
  type?: 'pdf' | 'powerpoint' | 'google_doc' | 'google_sheet' | 'auto'
  primaryColor?: string
}

/**
 * DocumentViewer - Embedded viewer for PDFs, PowerPoint, Google Docs, and Google Sheets
 * Detects document type from URL and renders appropriate viewer
 */
export function DocumentViewer({ 
  url, 
  filename, 
  type = 'auto',
  primaryColor = '#0d9488'
}: DocumentViewerProps) {
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [viewerError, setViewerError] = useState(false)

  // Auto-detect document type from URL if not specified
  const detectType = (): 'pdf' | 'powerpoint' | 'google_doc' | 'google_sheet' | 'unknown' => {
    if (type !== 'auto') return type

    const urlLower = url.toLowerCase()
    
    // Google Docs
    if (urlLower.includes('docs.google.com/document')) return 'google_doc'
    
    // Google Sheets
    if (urlLower.includes('docs.google.com/spreadsheets')) return 'google_sheet'
    
    // PDF files
    if (urlLower.endsWith('.pdf') || urlLower.includes('.pdf?')) return 'pdf'
    
    // PowerPoint files
    if (urlLower.endsWith('.pptx') || urlLower.endsWith('.ppt') || 
        urlLower.includes('.pptx?') || urlLower.includes('.ppt?')) return 'powerpoint'
    
    return 'unknown'
  }

  const documentType = detectType()

  // Get display name for document type
  const getTypeName = () => {
    switch (documentType) {
      case 'pdf': return 'PDF Document'
      case 'powerpoint': return 'PowerPoint Presentation'
      case 'google_doc': return 'Google Doc'
      case 'google_sheet': return 'Google Sheet'
      default: return 'Document'
    }
  }

  // Get appropriate icon
  const getIcon = () => {
    switch (documentType) {
      case 'pdf':
        return <FileText className="w-5 h-5 text-leaf" />
      case 'powerpoint':
        return <FileText className="w-5 h-5 text-warn" />
      case 'google_doc':
        return <FileText className="w-5 h-5 text-azure" />
      case 'google_sheet':
        return <FileText className="w-5 h-5 text-leaf" />
      default:
        return <FileText className="w-5 h-5 text-ink-mute" />
    }
  }

  // Get embeddable URL
  const getEmbedUrl = (): string => {
    switch (documentType) {
      case 'pdf':
        return url
      
      case 'powerpoint':
        // Use Microsoft Office Online viewer for PowerPoint
        return `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(url)}`
      
      case 'google_doc':
        // Convert Google Docs view URL to embed URL
        if (url.includes('/edit')) {
          return url.replace('/edit', '/preview')
        }
        return url + (url.includes('?') ? '&' : '?') + 'embedded=true'
      
      case 'google_sheet':
        // Convert Google Sheets view URL to embed URL
        if (url.includes('/edit')) {
          return url.replace('/edit', '/preview')
        }
        return url + (url.includes('?') ? '&' : '?') + 'embedded=true'
      
      default:
        return url
    }
  }

  // If type is unknown or error occurred, show download link
  if (documentType === 'unknown' || viewerError) {
    return (
      <div className="my-4 p-4 bg-cream border border-line rounded-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {getIcon()}
            <div>
              <p className="text-sm font-medium text-ink">
                {filename || 'Document'}
              </p>
              <p className="text-xs text-ink-mute">{getTypeName()}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-white border border-taupe text-ink-soft rounded-lg hover:bg-cream transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              Open
            </a>
            <a
              href={url}
              download={filename}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white rounded-lg hover:opacity-90 transition-colors"
              style={{ backgroundColor: primaryColor }}
            >
              <Download className="w-4 h-4" />
              Download
            </a>
          </div>
        </div>
      </div>
    )
  }

  const embedUrl = getEmbedUrl()

  return (
    <>
      <div className="my-4 bg-white border border-line rounded-lg overflow-hidden shadow-sm">
        {/* Document Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-cream border-b border-line">
          <div className="flex items-center gap-3">
            {getIcon()}
            <div>
              <p className="text-sm font-medium text-ink">
                {filename || getTypeName()}
              </p>
              <p className="text-xs text-ink-mute">{getTypeName()}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 text-ink-soft hover:text-ink hover:bg-line rounded transition-colors"
              title="Open in new tab"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
            <a
              href={url}
              download={filename}
              className="p-1.5 text-ink-soft hover:text-ink hover:bg-line rounded transition-colors"
              title="Download"
            >
              <Download className="w-4 h-4" />
            </a>
            <button
              onClick={() => setIsFullscreen(true)}
              className="p-1.5 text-ink-soft hover:text-ink hover:bg-line rounded transition-colors"
              title="Fullscreen"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Document Viewer */}
        <div className="relative bg-sand">
          <iframe
            src={embedUrl}
            className="w-full h-[600px] border-0"
            title={filename || getTypeName()}
            onError={() => setViewerError(true)}
            allowFullScreen
          />
        </div>
      </div>

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-95 flex flex-col">
          {/* Fullscreen Header */}
          <div className="flex items-center justify-between px-6 py-4 bg-ink border-b border-ink-soft">
            <div className="flex items-center gap-3 text-white">
              {getIcon()}
              <div>
                <p className="text-sm font-medium">{filename || getTypeName()}</p>
                <p className="text-xs text-ash">{getTypeName()}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 text-white hover:bg-ink rounded transition-colors"
                title="Open in new tab"
              >
                <ExternalLink className="w-5 h-5" />
              </a>
              <a
                href={url}
                download={filename}
                className="p-2 text-white hover:bg-ink rounded transition-colors"
                title="Download"
              >
                <Download className="w-5 h-5" />
              </a>
              <button
                onClick={() => setIsFullscreen(false)}
                className="p-2 text-white hover:bg-ink rounded transition-colors"
                title="Exit fullscreen"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Fullscreen Viewer */}
          <div className="flex-1 relative">
            <iframe
              src={embedUrl}
              className="w-full h-full border-0"
              title={filename || getTypeName()}
              allowFullScreen
            />
          </div>
        </div>
      )}
    </>
  )
}

/**
 * Detect document URLs in message content
 * Returns array of detected document URLs
 * Prioritizes embed URLs (/api/documents/stream/) over presigned URLs
 */
export function detectDocumentUrls(content: string): Array<{ url: string; type: string }> {
  const documents: Array<{ url: string; type: string }> = []
  const seenFiles = new Set<string>() // Track files by their key to avoid duplicates
  
  // Regex patterns for different document types
  // Order matters: 
  // - PDFs: Prefer stream URLs (avoid presigned URL issues)
  // - PowerPoint: Prefer presigned URLs (Microsoft needs direct access)
  const patterns = [
    {
      // Embed URLs for PDFs (via /api/documents/stream/) - PRIORITY for PDFs
      regex: /https?:\/\/[^\s)>\]"'*]+\/api\/documents\/stream\/[^\s)>\]"'*]+\.pdf/gi,
      type: 'pdf',
      priority: 1
    },
    {
      // Regular PDF files (presigned URLs, etc.) - Lower priority
      regex: /https?:\/\/[^\s)>\]"'*]+\.pdf(?:\?[^\s)>\]"'*]*)?/gi,
      type: 'pdf',
      priority: 2
    },
    {
      // PowerPoint presigned URLs (S3/MinIO) - PRIORITY for PowerPoint
      regex: /https?:\/\/[^\s)>\]"'*]+\.pptx?(?:\?[^\s)>\]"'*]*)?/gi,
      type: 'powerpoint',
      priority: 1
    },
    {
      // PowerPoint stream URLs - Lower priority
      regex: /https?:\/\/[^\s)>\]"'*]+\/api\/documents\/stream\/[^\s)>\]"'*]+\.pptx?/gi,
      type: 'powerpoint',
      priority: 2
    },
    {
      // Google Docs
      regex: /https:\/\/docs\.google\.com\/document\/d\/[a-zA-Z0-9_-]+(?:\/[^\s]*)?/gi,
      type: 'google_doc',
      priority: 1
    },
    {
      // Google Sheets
      regex: /https:\/\/docs\.google\.com\/spreadsheets\/d\/[a-zA-Z0-9_-]+(?:\/[^\s]*)?/gi,
      type: 'google_sheet',
      priority: 1
    }
  ]

  for (const pattern of patterns) {
    const matches = content.match(pattern.regex)
    if (matches) {
      for (const url of matches) {
        // Remove trailing markdown/punctuation that the LLM wraps around URLs
        // e.g. )** from **[text](url)** or ]( from markdown links
        const cleanUrl = url.replace(/[.,;!?)>\]*_]+$/, '')
        
        // Extract file key/identifier to detect duplicates
        // For stream URLs: documents/tenant/date/filename.pdf
        // For presigned URLs: same path before query params
        let fileKey = cleanUrl
        if (cleanUrl.includes('/api/documents/stream/')) {
          fileKey = cleanUrl.split('/api/documents/stream/')[1]
        } else if (cleanUrl.includes('?')) {
          fileKey = cleanUrl.split('?')[0].split('/').pop() || cleanUrl
        } else {
          fileKey = cleanUrl.split('/').pop() || cleanUrl
        }
        
        // Skip if we've already added a URL for this file
        if (seenFiles.has(fileKey)) {
          continue
        }
        
        seenFiles.add(fileKey)
        documents.push({ url: cleanUrl, type: pattern.type })
      }
    }
  }

  return documents
}
