'use client'

import { memo, useState, useMemo, useRef, useEffect } from 'react'
import Image from 'next/image'
import dynamic from 'next/dynamic'
import { Copy, Check, RefreshCw, Sparkles, FileText, Image as ImageIcon, Download, File, Trash2, ThumbsUp, ThumbsDown, Square } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Message, Attachment, GeneratedImageData, GeneratedVideoData, FormDefinition } from '../types'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import DOMPurify from 'dompurify'
import { SourcesList } from './SourceCard'
import { VoicePlayer } from './VoicePlayer'
import { ToolStatusDisplay } from './ToolStatusDisplay'
import { InteractiveFormCard } from './InteractiveFormCard'
import toast from 'react-hot-toast'
import { useLocale, useTranslations } from 'next-intl'

const ChartRenderer = dynamic(
  () => import('@/components/charts/ChartRenderer').then((mod) => mod.ChartRenderer),
  { ssr: false }
)
const MermaidDiagram = dynamic(
  () => import('@/components/diagrams/MermaidDiagram').then((mod) => mod.MermaidDiagram),
  { ssr: false }
)
const DiagramRenderer = dynamic(
  () => import('@/components/diagrams/DiagramRenderer').then((mod) => mod.DiagramRenderer),
  { ssr: false }
)
const MarkdownViewer = dynamic(
  () => import('./MarkdownViewer').then((mod) => mod.MarkdownViewer),
  { ssr: false }
)
const DocumentViewer = dynamic(
  () => import('./DocumentViewer').then((mod) => mod.DocumentViewer),
  { ssr: false }
)
const CodeBlock = dynamic(
  () => import('./CodeBlock').then((mod) => mod.CodeBlock),
  { ssr: false }
)

interface ToolStatus {
  tool_name: string
  status: 'started' | 'completed' | 'error'
  description: string
  details?: {
    file_path?: string
    path?: string
    command?: string
    repo_url?: string
    url?: string
    branch?: string
  }
  duration_ms?: number
  input_tokens?: number
  output_tokens?: number
}

function sanitizeSvg(svgContent: string): string {
  if (typeof window === 'undefined') return ''
  const clean = DOMPurify.sanitize(svgContent, {
    USE_PROFILES: { svg: true, svgFilters: true },
    ADD_TAGS: ['use'],
    FORBID_ATTR: ['xlink:href'],
  })
  // Keep SVG responsive inside a capped-width chat container.
  return clean
    .replace(/<svg aria-hidden="true"([^>]*)>/, (_match, attrs: string) => {
      const withoutDims = attrs
        .replace(/\s+width="[^"]*"/g, '')
        .replace(/\s+height="[^"]*"/g, '')
        .replace(/\s+style="[^"]*"/g, '')
      return `<svg aria-hidden="true"${withoutDims} width="100%" style="display:block;max-width:100%;height:auto;margin:0 auto">`
    })
}

/**
 * Detect image URLs in message content
 * Looks for URLs ending with common image extensions or containing image indicators
 */
function detectImageUrls(content: string): string[] {
  if (!content) return []

  // Regex to match URLs that look like images
  const imageUrlPatterns = [
    // URLs ending with image extensions
    /https?:\/\/[^\s<>"]+\.(?:png|jpg|jpeg|gif|webp|svg|bmp)(?:\?[^\s<>"]*)?/gi,
    // URLs with image in path or query (common for S3/CDN)
    /https?:\/\/[^\s<>"]+(?:screenshot|image|img|photo)[^\s<>"]*\.(?:png|jpg|jpeg|gif|webp)(?:\?[^\s<>"]*)?/gi,
    // S3/MinIO presigned URLs for images (detect by content type or extension before query)
    /https?:\/\/[^\s<>"]+\/[^\s<>"?]+\.(?:png|jpg|jpeg|gif|webp)\?[^\s<>"]+X-Amz-[^\s<>"]*/gi,
  ]

  const imageUrls: Set<string> = new Set()

  for (const pattern of imageUrlPatterns) {
    const matches = content.match(pattern)
    if (matches) {
      matches.forEach(url => {
        // Clean up any trailing punctuation that might have been captured
        const cleanUrl = url.replace(/[.,;:!?)]+$/, '')
        imageUrls.add(cleanUrl)
      })
    }
  }

  return Array.from(imageUrls)
}

function detectMarkdownUrls(content: string): string[] {
  const urlRegex = /(https?:\/\/[^\s]+\.md[^\s]*)/gi
  const matches = content.match(urlRegex)
  return matches || []
}

function detectDocumentUrls(content: string): Array<{ url: string; type: string }> {
  const documents: Array<{ url: string; type: string }> = []
  const seenFiles = new Set<string>()
  const patterns = [
    {
      regex: /https?:\/\/[^\s)>\]"'*]+\/api\/documents\/stream\/[^\s)>\]"'*]+\.pdf/gi,
      type: 'pdf',
    },
    {
      regex: /https?:\/\/[^\s)>\]"'*]+\.pdf(?:\?[^\s)>\]"'*]*)?/gi,
      type: 'pdf',
    },
    {
      regex: /https?:\/\/[^\s)>\]"'*]+\.pptx?(?:\?[^\s)>\]"'*]*)?/gi,
      type: 'powerpoint',
    },
    {
      regex: /https?:\/\/[^\s)>\]"'*]+\/api\/documents\/stream\/[^\s)>\]"'*]+\.pptx?/gi,
      type: 'powerpoint',
    },
    {
      regex: /https:\/\/docs\.google\.com\/document\/d\/[a-zA-Z0-9_-]+(?:\/[^\s]*)?/gi,
      type: 'google_doc',
    },
    {
      regex: /https:\/\/docs\.google\.com\/spreadsheets\/d\/[a-zA-Z0-9_-]+(?:\/[^\s]*)?/gi,
      type: 'google_sheet',
    },
  ]

  for (const pattern of patterns) {
    const matches = content.match(pattern.regex)
    if (!matches) continue

    for (const url of matches) {
      const cleanUrl = url.replace(/[.,;!?)>\]*_]+$/, '')
      let fileKey = cleanUrl
      if (cleanUrl.includes('/api/documents/stream/')) {
        fileKey = cleanUrl.split('/api/documents/stream/')[1]
      } else if (cleanUrl.includes('?')) {
        fileKey = cleanUrl.split('?')[0].split('/').pop() || cleanUrl
      } else {
        fileKey = cleanUrl.split('/').pop() || cleanUrl
      }

      if (seenFiles.has(fileKey)) continue
      seenFiles.add(fileKey)
      documents.push({ url: cleanUrl, type: pattern.type })
    }
  }

  return documents
}

function PlainCodeBlock({ language, code }: { language?: string; code: string }) {
  return (
    <div className="not-prose relative group/code my-3 max-w-full overflow-hidden rounded-lg">
      <div className="flex items-center justify-between px-3 py-1.5 bg-ink rounded-t-lg border-b border-ink-soft">
        <span className="text-xs text-ash font-mono">{language || 'code'}</span>
        <button
          onClick={() => navigator.clipboard.writeText(code)}
          className="text-xs text-ash hover:text-white transition-colors flex items-center gap-1"
        >
          <Copy size={12} />
          Copy
        </button>
      </div>
      <pre className="overflow-x-auto bg-ink text-sand !my-0 p-3 text-[13px] leading-relaxed rounded-b-lg">
        <code>{code}</code>
      </pre>
    </div>
  )
}

interface ChatConfig {
  chat_title?: string
  chat_logo_url?: string
  chat_welcome_message?: string
  chat_placeholder?: string
  chat_primary_color?: string
  chat_background_color?: string
  chat_font_family?: string
}

interface ChatMessageProps {
  message: Message
  isStreaming?: boolean
  thinkingStatus?: string
  toolStatus?: ToolStatus | null
  recentTools?: ToolStatus[]
  streamStartTime?: number | null
  onCopy?: (content: string, messageId: string) => void
  onRetry?: (messageId: string) => void
  onDelete?: (messageId: string) => void
  onFeedback?: (messageId: string, rating: 1 | -1) => void
  onActionClick?: (text: string) => void
  className?: string
  chatConfig?: ChatConfig | null
  agentAvatar?: string
  userAvatar?: string
  userName?: string
  agentName?: string
  conversationId?: string
  onFormSubmit?: (form: FormDefinition, answers: Record<string, unknown>, attachments?: Attachment[]) => Promise<void> | void
  formSubmissionDisabled?: boolean
}

function UserInitialAvatar({ name }: { name?: string }) {
  const t = useTranslations('chat.message')
  const seed = encodeURIComponent(name?.trim() || 'User')
  return (
    <img
      src={`https://api.dicebear.com/9.x/adventurer/svg?seed=${seed}&backgroundColor=b6e3f4,c0aede,d1d4f9,ffd5dc,ffdfbf`}
      alt={name || t('user')}
      className="h-full w-full object-cover"
    />
  )
}

/**
 * TableWithExport — wraps a markdown table with CSV and PDF export buttons.
 * Uses a DOM ref to extract cell text, so it works with any react-markdown output.
 */
function TableWithExport({ children, ...props }: any) {
  const t = useTranslations('chat.message')
  const tableRef = useRef<HTMLTableElement>(null)
  const [exporting, setExporting] = useState<'csv' | 'pdf' | null>(null)

  function extractTableData(): { headers: string[]; rows: string[][] } {
    const table = tableRef.current
    if (!table) return { headers: [], rows: [] }
    const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent?.trim() ?? '')
    const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr =>
      Array.from(tr.querySelectorAll('td')).map(td => td.textContent?.trim() ?? '')
    )
    return { headers, rows }
  }

  function exportCSV() {
    setExporting('csv')
    try {
      const { headers, rows } = extractTableData()
      const csvRows = [headers, ...rows].map(row =>
        row.map(cell => `"${cell.replace(/"/g, '""')}"`).join(',')
      )
      const csv = '\uFEFF' + csvRows.join('\r\n') // BOM for Excel UTF-8
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'table-export.csv'
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setTimeout(() => setExporting(null), 800)
    }
  }

  function exportPDF() {
    setExporting('pdf')
    try {
      const { headers, rows } = extractTableData()
      const thStyle = 'text-align:left;padding:8px 12px;border:1px solid #d1d5db;background:#f3f4f6;font-size:12px;font-weight:600;color:#374151;'
      const tdStyle = 'padding:8px 12px;border:1px solid #d1d5db;font-size:12px;color:#374151;'
      const tableHtml = `
        <table style="border-collapse:collapse;width:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
          <thead><tr>${headers.map(h => `<th style="${thStyle}">${h}</th>`).join('')}</tr></thead>
          <tbody>${rows.map((row, i) =>
            `<tr style="${i % 2 !== 0 ? 'background:#f9fafb;' : ''}">${row.map(cell => `<td style="${tdStyle}">${cell}</td>`).join('')}</tr>`
          ).join('')}</tbody>
        </table>`
      const win = window.open('', '_blank')
      if (!win) return
      win.document.write(`<!DOCTYPE html><html><head><title>${t('tableExport')}</title>
        <style>@media print{body{margin:16px}}</style>
        </head><body>${tableHtml}</body></html>`)
      win.document.close()
      win.focus()
      win.print()
    } finally {
      setTimeout(() => setExporting(null), 1200)
    }
  }

  return (
    <div className="my-3 rounded-lg border border-line overflow-hidden w-full max-w-full">
      <div className="flex items-center justify-end gap-3 px-3 py-1.5 bg-cream border-b border-line">
        <button
          onClick={exportCSV}
          disabled={exporting !== null}
          title={t('exportCsv')}
          className="flex items-center gap-1 text-xs text-ink-mute hover:text-ink transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {exporting === 'csv' ? (
            <svg aria-hidden="true" className="motion-safe:animate-spin" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" strokeLinecap="round"/>
            </svg>
          ) : (
            <Download size={12} />
          )}
          CSV
        </button>
        <button
          onClick={exportPDF}
          disabled={exporting !== null}
          title={t('exportPdf')}
          className="flex items-center gap-1 text-xs text-ink-mute hover:text-ink transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {exporting === 'pdf' ? (
            <svg aria-hidden="true" className="motion-safe:animate-spin" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" strokeLinecap="round"/>
            </svg>
          ) : (
            <FileText size={12} />
          )}
          PDF
        </button>
      </div>
      <div className="overflow-x-auto">
        <table ref={tableRef} className="min-w-full divide-y divide-line" {...props}>
          {children}
        </table>
      </div>
    </div>
  )
}

/**
 * ChatMessage - Individual message component with rich formatting
 * Supports markdown, code highlighting, tables, and media attachments
 */
export const ChatMessage = memo(function ChatMessage({
  message,
  isStreaming = false,
  thinkingStatus,
  toolStatus,
  recentTools = [],
  streamStartTime,
  onCopy,
  onRetry,
  onDelete,
  onFeedback,
  onActionClick,
  className,
  chatConfig,
  agentAvatar,
  userAvatar,
  userName,
  agentName,
  conversationId,
  onFormSubmit,
  formSubmissionDisabled = false,
}: ChatMessageProps) {
  const t = useTranslations('chat.message')
  const locale = useLocale()
  const [copied, setCopied] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  // Use the real DB UUID as the stable key for feedback persistence. Falls back
  // to message.id when the message was loaded fresh (where id IS the DB UUID).
  // Use the real DB UUID as the stable key for feedback persistence. Falls back
  // to message.id when the message was loaded fresh (where id IS the DB UUID).
  const feedbackKey = message.role === 'assistant' ? `feedback:${message.dbId || message.id}` : null
  const [feedbackRating, setFeedbackRating] = useState<1 | -1 | null>(() => {
    if (!feedbackKey || typeof window === 'undefined') return null
    const stored = localStorage.getItem(feedbackKey)
    return stored === '1' ? 1 : stored === '-1' ? -1 : null
  })
  // When dbId arrives (ephemeral→real UUID swap), migrate any rating stored under
  // the ephemeral key to the stable DB UUID key.
  useEffect(() => {
    if (!message.dbId || typeof window === 'undefined') return
    const ephemeralStored = localStorage.getItem(`feedback:${message.id}`)
    const stableKey = `feedback:${message.dbId}`
    if (ephemeralStored && !localStorage.getItem(stableKey)) {
      localStorage.setItem(stableKey, ephemeralStored)
      localStorage.removeItem(`feedback:${message.id}`)
    }
    // Also sync in-memory state from the stable key in case it was set elsewhere
    const stableStored = localStorage.getItem(stableKey)
    if (stableStored) {
      setFeedbackRating(stableStored === '1' ? 1 : -1)
    }
   
  }, [message.dbId])
  const [isCollapsed, setIsCollapsed] = useState(true)
  const [isOverflowing, setIsOverflowing] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)
  const isUser = message.role === 'user'
  const isPlatformEngineer = agentName === 'Platform Engineer'

  const COLLAPSE_THRESHOLD = 400 // px

  // After streaming ends, check if content exceeds threshold
  useEffect(() => {
    if (isStreaming) return
    const el = contentRef.current
    if (!el) return
    setIsOverflowing(el.scrollHeight > COLLAPSE_THRESHOLD)
  }, [isStreaming, message.content])

  // Get colors from config
  const primaryColor = chatConfig?.chat_primary_color || '#0d9488'
  const fontFamily = chatConfig?.chat_font_family || 'inherit'

  // Memoize URL detection — three regex passes over message content are
  // expensive; skip entirely while streaming (URLs may be partial/incomplete)
  const imageUrls = useMemo(
    () => (!isStreaming ? detectImageUrls(message.content) : []),
    [message.content, isStreaming]
  )

  const handleCopy = async () => {
    if (onCopy) {
      onCopy(message.content, message.id)
    } else {
      await navigator.clipboard.writeText(message.content)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // User message — right-aligned light bubble
  if (isUser) {
    return (
      <div className={cn('flex justify-end items-start gap-2.5 group', className)}>
        <div className="max-w-[85%] sm:max-w-[72%]">
          <div className="bg-cream border border-black/[0.07] rounded-2xl rounded-tr-sm px-4 py-3.5 shadow-sm">
            <p
              className="text-[15px] font-semibold text-ink leading-[1.65] whitespace-pre-wrap tracking-[-0.01em] max-h-48 overflow-y-auto"
              style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(0,0,0,0.15) transparent' }}
            >{message.content}</p>
            {message.attachments && message.attachments.length > 0 && (
              <div className="mt-2 space-y-1.5">
                {message.attachments.map((attachment, index) => (
                  <AttachmentPreview key={index} attachment={attachment} />
                ))}
              </div>
            )}
          </div>
          <div className="flex items-center justify-end gap-1.5 mt-1 px-1">
            {onDelete && confirmingDelete ? (
              <>
                <span className="text-[10px] text-ink-mute">{t('deleteThis')}</span>
                <button
                  onClick={() => { onDelete(message.id); setConfirmingDelete(false) }}
                  className="text-[10px] font-medium text-leaf hover:text-danger transition-colors"
                >
                  {t('delete')}
                </button>
                <button
                  onClick={() => setConfirmingDelete(false)}
                  className="text-[10px] text-ash hover:text-ink-soft transition-colors"
                >
                  {t('cancel')}
                </button>
              </>
            ) : (
              <>
                {onDelete && (
                  <button
                    onClick={() => setConfirmingDelete(true)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-ash hover:text-leaf transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                    title={t('deleteMessage')}
                  >
                    <Trash2 size={11} />
                  </button>
                )}
                <button
                  onClick={handleCopy}
                  className="opacity-0 group-hover:opacity-100 p-1 text-ash hover:text-ink-soft transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                  title={t('copyMessage')}
                >
                  {copied ? <Check size={11} className="text-leaf" /> : <Copy size={11} />}
                </button>
                <span className="text-[10px] text-ash">{t('you')}</span>
                <span className="text-[10px] text-taupe">·</span>
                <span className="text-[10px] text-ash">{formatTimestamp(message.timestamp, t, locale)}</span>
              </>
            )}
          </div>
        </div>
        {/* User avatar */}
        <div className="flex-shrink-0 h-8 w-8 rounded-full overflow-hidden mt-0.5">
          {userAvatar
            ? <img src={userAvatar} alt="You" className="h-full w-full object-cover" />
            : <UserInitialAvatar name={userName} />
          }
        </div>
      </div>
    )
  }

  // Assistant message — left-aligned layout
  return (
    <div className={cn('group', className)}>
      <div className="flex items-center gap-2 mb-3">
        {agentAvatar ? (
          <div className="w-7 h-7 rounded-full overflow-hidden flex items-center justify-center bg-white relative shrink-0 ring-1 ring-line">
            {agentAvatar.startsWith('http://') || agentAvatar.startsWith('https://') ? (
              <Image
                src={agentAvatar}
                alt={t('agent')}
                width={24}
                height={24}
                className="w-full h-full object-cover"
                unoptimized
              />
            ) : (
              <Image src={agentAvatar} alt={t('agent')} fill className="object-cover" />
            )}
          </div>
        ) : (
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
            style={{ background: primaryColor }}
          >
            <Sparkles size={12} className="text-white" />
          </div>
        )}
        <span className="text-sm font-semibold text-ink-soft tracking-[-0.01em]">{agentName || 'Assistant'}</span>
        {message.metadata?.confidence && (
          <span className="text-[11px] text-ash">Confidence: {message.metadata.confidence}</span>
        )}
      </div>

      <div ref={contentRef} className="pl-6 sm:pl-8 min-w-0 w-full" style={{ fontFamily }}>
        {/* Collapsible content wrapper */}
        <div
          className="relative"
          style={{
            maxHeight: isOverflowing && isCollapsed ? `${COLLAPSE_THRESHOLD}px` : undefined,
            overflow: isOverflowing && isCollapsed ? 'hidden' : undefined,
          }}
        >
          {/* Gradient fade when collapsed */}
          {isOverflowing && isCollapsed && (
            <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-white to-transparent pointer-events-none" />
          )}
        {/* Document Viewers - Render embedded documents (PDFs, PowerPoint, Google Docs/Sheets) */}
        {/* NOTE: Only render after streaming completes to avoid loading partial/incomplete URLs */}
        {!isStreaming && (() => {
          const documents = detectDocumentUrls(message.content)
          if (documents.length > 0) {
            return documents.map((doc, index) => (
              <DocumentViewer
                key={`doc-${index}`}
                url={doc.url}
                type={doc.type as any}
                primaryColor={primaryColor}
              />
            ))
          }
          return null
        })()}

        {/* Markdown URL Viewers - Render before message content */}
        {/* NOTE: Only render after streaming completes to avoid loading partial/incomplete URLs */}
        {!isStreaming && (() => {
          const markdownUrls = detectMarkdownUrls(message.content)
          if (markdownUrls.length > 0) {
            return markdownUrls.map((url, index) => (
              <MarkdownViewer
                key={`md-${index}`}
                url={url}
                primaryColor={primaryColor}
              />
            ))
          }
          return null
        })()}

        {/* Image URL Viewers - Render embedded images from URLs in content */}
        {/* NOTE: Only render after streaming completes to avoid loading partial/incomplete URLs */}
        {imageUrls.length > 0 && (
          <div className="space-y-3 mb-3">
            {imageUrls.map((url, index) => (
              <EmbeddedImage
                key={`img-${index}`}
                url={url}
                primaryColor={primaryColor}
              />
            ))}
          </div>
        )}

        {/* Error Message */}
        {message.isError && (
          <div className="flex items-start gap-2 px-3 py-2.5 bg-blush-wash border border-blush rounded-xl text-sm text-danger mb-2">
            <svg aria-hidden="true" className="w-4 h-4 mt-0.5 flex-shrink-0 text-leaf" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <span>{message.content}</span>
          </div>
        )}

        {/* Message Content */}
        <div className="prose prose-sm max-w-none prose-gray [&_th]:whitespace-nowrap [&_th]:break-normal [&_td]:break-normal" style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
          {!message.isError && thinkingStatus && !message.content && !toolStatus && recentTools.length === 0 ? (
            <div className="flex items-center gap-2.5 py-1">
              <span className="inline-flex items-end gap-[3px]" style={{ height: '18px' }} aria-hidden>
                {[0, 140, 280].map((delay, i) => (
                  <span
                    key={i}
                    className="inline-block w-[3px] rounded-full origin-bottom"
                    style={{
                      height: '100%',
                      backgroundColor: '#ff444f',
                      boxShadow: '0 0 5px #ff444faa',
                      animation: `synkora-bar 0.75s ease-in-out ${delay}ms infinite`,
                    }}
                  />
                ))}
              </span>
              <span className="text-sm font-medium" style={{ color: 'rgb(var(--brand))' }}>Working…</span>
            </div>
          ) : !message.isError ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code: ({ className, children, ...props }: any) => {
                  const match = /language-(\w+)/.exec(className || '')
                  const language = match ? match[1] : ''
                  const codeString = String(children).replace(/\n$/, '')

                  // Mermaid diagram: render as visual diagram instead of code block
                  if (language === 'mermaid') {
                    if (isStreaming) {
                      return <PlainCodeBlock language={language} code={codeString} />
                    }
                    return (
                      <div className="my-4">
                        <MermaidDiagram code={codeString} />
                      </div>
                    )
                  }

                  // In react-markdown v9, block code is wrapped in <pre>.
                  // We detect inline code by: no language class AND no newlines in content.
                  const isInline = !className && !codeString.includes('\n')

                  if (isInline) {
                    return (
                      <code
                        className="px-1.5 py-0.5 rounded text-[13px] font-mono bg-sand text-ink"
                        {...props}
                      >
                        {children}
                      </code>
                    )
                  }

                  if (isStreaming) {
                    return <PlainCodeBlock language={language} code={codeString} />
                  }

                  return <CodeBlock language={language} code={codeString} />
                },
                pre: ({ children, ...props }: any) => (
                  <div {...props}>{children}</div>
                ),
                table: ({ children, ...props }: any) => (
                  <TableWithExport {...props}>{children}</TableWithExport>
                ),
                thead: ({ children, ...props }: any) => (
                  <thead className="bg-cream" {...props}>
                    {children}
                  </thead>
                ),
                tbody: ({ children, ...props }: any) => (
                  <tbody className="bg-white divide-y divide-sand" {...props}>
                    {children}
                  </tbody>
                ),
                tr: ({ children, ...props }: any) => (
                  <tr className="hover:bg-cream transition-colors" {...props}>{children}</tr>
                ),
                th: ({ children, ...props }: any) => (
                  <th
                    className="px-3 py-2 text-left text-xs font-semibold text-ink-soft"
                    {...props}
                  >
                    {children}
                  </th>
                ),
                td: ({ children, ...props }: any) => (
                  <td className="px-3 py-2 text-sm text-ink-soft" {...props}>
                    {children}
                  </td>
                ),
                a: ({ children, ...props }: any) => (
                  <a
                    className="font-medium hover:underline"
                    style={{ color: primaryColor }}
                    target="_blank"
                    rel="noopener noreferrer"
                    {...props}
                  >
                    {children}
                  </a>
                ),
                h1: ({ children, ...props }: any) => (
                  <h1 className="text-xl font-bold text-ink mb-3 mt-4 first:mt-0 flex flex-wrap items-center gap-2 min-w-0" {...props}>
                    {children}
                  </h1>
                ),
                h2: ({ children, ...props }: any) => (
                  <h2 className="text-lg font-bold text-ink mb-2 mt-4 first:mt-0 flex flex-wrap items-center gap-2 min-w-0" {...props}>
                    {children}
                  </h2>
                ),
                h3: ({ children, ...props }: any) => (
                  <h3 className="text-base font-semibold text-ink mb-2 mt-3 first:mt-0" {...props}>
                    {children}
                  </h3>
                ),
                ul: ({ children, ...props }: any) => (
                  <ul className="list-none ml-0 mb-3 space-y-1" {...props}>
                    {children}
                  </ul>
                ),
                ol: ({ children, ...props }: any) => (
                  <ol className="list-decimal ml-4 mb-3 space-y-1" {...props}>
                    {children}
                  </ol>
                ),
                li: ({ children, ...props }: any) => (
                  <li className="text-[15px] leading-[1.65] text-ink-soft relative pl-4 before:content-['•'] before:absolute before:left-0 before:text-ash" {...props}>
                    {children}
                  </li>
                ),
                p: ({ children, ...props }: any) => (
                  <p className="mb-3 last:mb-0 text-[15px] leading-[1.7] text-ink-soft tracking-[-0.005em]" {...props}>
                    {children}
                  </p>
                ),
                blockquote: ({ children, ...props }: any) => (
                  <blockquote
                    className="border-l-3 pl-3 py-1 my-3 text-ink-soft bg-cream rounded-r"
                    style={{ borderLeftColor: primaryColor, borderLeftWidth: '3px' }}
                    {...props}
                  >
                    {children}
                  </blockquote>
                ),
                hr: ({ ...props }: any) => (
                  <hr className="my-4 border-line" {...props} />
                ),
                strong: ({ children, ...props }: any) => (
                  <strong className="font-semibold text-ink" {...props}>
                    {children}
                  </strong>
                ),
                img: ({ src, alt, ...props }: any) => {
                  // Render images inline with the markdown
                  if (!src) return null
                  return (
                    <span className="block my-3">
                      <img
                        src={src}
                        alt={alt || t('image')}
                        className="max-w-full h-auto rounded-lg border border-line"
                        loading="lazy"
                        {...props}
                      />
                    </span>
                  )
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          ) : null}

          {isStreaming && (toolStatus || recentTools.length > 0) && (
            <ToolStatusDisplay
              currentTool={toolStatus ?? null}
              recentTools={recentTools}
              primaryColor={primaryColor}
              isStreaming={isStreaming}
              streamStartTime={streamStartTime}
              className={message.content ? 'mt-3' : ''}
            />
          )}

          {isStreaming && !(!message.content && !toolStatus && recentTools.length === 0 && thinkingStatus) && !(toolStatus || recentTools.length > 0) && (
            <span
              className="inline-flex items-end gap-[3px] ml-1.5 align-middle"
              style={{ height: '18px' }}
              aria-label={t('generating')}
            >
              {([0, 140, 280] as const).map((delay, i) => (
                <span
                  key={i}
                  className="inline-block w-[3px] rounded-full origin-bottom"
                  style={{
                    height: '100%',
                    backgroundColor: '#ff444f',
                    boxShadow: '0 0 5px #ff444faa',
                    animation: `synkora-bar 0.75s ease-in-out ${delay}ms infinite`,
                  }}
                />
              ))}
            </span>
          )}
        </div>

        {/* RAG Sources */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3">
            <SourcesList sources={message.sources} maxVisible={3} />
          </div>
        )}

        {/* Attachments */}
        {message.attachments && message.attachments.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {message.attachments.map((attachment, index) => (
              <AttachmentPreview key={index} attachment={attachment} />
            ))}
          </div>
        )}

        {/* Charts */}
        {message.metadata?.charts && message.metadata.charts.length > 0 && (
          <div className={`mt-3 ${message.metadata.charts.length >= 2 ? 'grid grid-cols-1 sm:grid-cols-2 gap-3' : 'space-y-3'}`}>
            {message.metadata.charts.map((chart: any, index: number) => {
              const chartData = {
                id: `chart-${index}`,
                title: chart.title,
                description: chart.description || '',
                chart_type: (chart.chart_type || chart.type || 'bar') as string,
                library: chart.library || 'chartjs',
                config: chart.config || {},
                data: chart.data,
                table_data: chart.table_data,
                created_at: new Date().toISOString(),
              }
              return <ChartRenderer key={index} chart={chartData} />
            })}
          </div>
        )}

        {/* Diagrams */}
        {message.metadata?.diagrams && message.metadata.diagrams.length > 0 && (
          <div className="mt-3 space-y-3">
            {message.metadata.diagrams.map((diagram: any, index: number) => (
              <DiagramRenderer key={diagram.id || index} diagram={diagram} />
            ))}
          </div>
        )}

        {/* Infographics */}
        {message.metadata?.infographics && message.metadata.infographics.length > 0 && (
          <div className="mt-3 space-y-4">
            {message.metadata.infographics.map((infographic: any, index: number) => (
              <div key={infographic.id || index} className="mx-auto w-full max-w-[860px]">
                {infographic.svg_content ? (
                  <div className="overflow-x-auto" dangerouslySetInnerHTML={{ __html: sanitizeSvg(infographic.svg_content) }} />
                ) : infographic.png_url ? (
                  <img
                    src={infographic.png_url}
                    alt={infographic.title || t('infographic')}
                    className="block h-auto w-full mx-auto"
                    loading="lazy"
                  />
                ) : infographic.svg_url ? (
                  <img
                    src={infographic.svg_url}
                    alt={infographic.title || t('infographic')}
                    className="block h-auto w-full mx-auto"
                    loading="lazy"
                  />
                ) : null}
              </div>
            ))}
          </div>
        )}

        {/* Generated Images */}
        {message.metadata?.generated_images && message.metadata.generated_images.length > 0 && (
          <div className="mt-3 space-y-4">
            {message.metadata.generated_images.map((img: GeneratedImageData, index: number) => (
              <div key={img.id || index} className="group relative rounded-xl overflow-hidden shadow-lg">
                {img.url ? (
                  <>
                    {/* Image */}
                    <img
                      src={img.url}
                      alt={img.revised_prompt || img.prompt || t('generatedImage')}
                      className="w-full h-auto block"
                      style={{ maxHeight: '640px', objectFit: 'contain', background: 'rgb(var(--ink))' }}
                    />

                    {/* Hover overlay with actions */}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex flex-col justify-end pointer-events-none group-hover:pointer-events-auto">
                      <div className="p-4 flex items-end justify-between gap-3">
                        {/* Prompt caption */}
                        {(img.revised_prompt || img.prompt) && (
                          <p className="text-white/90 text-xs leading-relaxed line-clamp-3 flex-1 min-w-0">
                            {img.revised_prompt || img.prompt}
                          </p>
                        )}

                        {/* Action buttons */}
                        <div className="flex items-center gap-2 shrink-0">
                          {img.model && (
                            <span className="text-white/50 text-xs font-mono hidden sm:block">{img.model}</span>
                          )}
                          <a
                            href={img.url}
                            download={`generated-${img.id || index}.png`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/15 hover:bg-white/25 text-white text-xs font-medium rounded-lg transition-colors border border-white/20"
                            onClick={e => e.stopPropagation()}
                          >
                            <Download className="w-3.5 h-3.5" />
                            {t('download')}
                          </a>
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="px-4 py-6 text-sm text-ash bg-ink text-center rounded-xl">
                    Image unavailable, S3 storage not configured
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Generated Videos */}
        {message.metadata?.generated_videos && message.metadata.generated_videos.length > 0 && (
          <div className="mt-3 space-y-4">
            {message.metadata.generated_videos.map((vid: GeneratedVideoData, index: number) => (
              <div key={vid.id || index} className="rounded-xl overflow-hidden shadow-lg bg-ink">
                {vid.url ? (
                  <>
                    <video
                      src={vid.url}
                      controls
                      playsInline
                      preload="metadata"
                      className="w-full h-auto block"
                      style={{ maxHeight: '640px', background: 'rgb(var(--ink))' }}
                    >
                      {t('videoUnsupported')}
                    </video>
                    <div className="flex items-center justify-between gap-3 px-3 py-2">
                      <p className="text-taupe text-xs leading-relaxed line-clamp-2 flex-1 min-w-0">
                        {vid.prompt}
                      </p>
                      <div className="flex items-center gap-2 shrink-0">
                        {(vid.duration || vid.resolution) && (
                          <span className="text-ink-mute text-xs font-mono hidden sm:block">
                            {[vid.duration ? `${vid.duration}s` : null, vid.resolution].filter(Boolean).join(', ')}
                          </span>
                        )}
                        <a
                          href={vid.url}
                          download={`generated-${vid.id || index}.mp4`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs font-medium rounded-lg transition-colors border border-white/20"
                        >
                          <Download className="w-3.5 h-3.5" />
                          {t('download')}
                        </a>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="px-4 py-6 text-sm text-ash text-center">Video unavailable</div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Interactive Forms */}
        {message.metadata?.forms && message.metadata.forms.length > 0 && (
          <div className="space-y-4">
            {message.metadata.forms.map((form, index) => (
              <InteractiveFormCard
                key={form.form_id || index}
                form={form}
                conversationId={conversationId}
                onSubmit={onFormSubmit}
                disabled={formSubmissionDisabled}
                primaryColor={primaryColor}
              />
            ))}
          </div>
        )}

        {/* Vehicle Maps (Mapbox) */}
        {message.metadata?.vehicle_maps && message.metadata.vehicle_maps.length > 0 && (
          <div className="mt-3 space-y-3">
            {message.metadata.vehicle_maps.map((map: any, index: number) => (
              <div key={map.id || index} className="rounded-lg overflow-hidden border border-line">
                {(map.distance_km || map.duration_min) && (
                  <div className="px-3 py-2 bg-cream border-b border-line flex items-center gap-3 text-xs text-ink-soft">
                    {map.profile && <span className="capitalize font-medium">{map.profile}</span>}
                    {map.distance_km && <span>{map.distance_km} km</span>}
                    {map.duration_min && <span>⏱ {map.duration_min} min</span>}
                    {map.marker_count > 0 && <span>{map.marker_count} vehicles</span>}
                  </div>
                )}
                <img
                  src={map.map_url}
                  alt={t('map')}
                  className="w-full h-auto"
                  style={{ maxHeight: '500px', objectFit: 'cover' }}
                />
                {map.embed_url && (
                  <div className="px-3 py-2 bg-cream border-t border-line text-xs">
                    <a href={map.embed_url} target="_blank" rel="noopener noreferrer" className="text-azure hover:underline">
                      Open interactive map ↗
                    </a>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        </div>{/* end collapsible content wrapper */}

        {/* Show more / Show less toggle */}
        {isOverflowing && !isStreaming && (
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="mt-2 text-xs font-medium transition-colors"
            style={{ color: primaryColor }}
          >
            {isCollapsed ? 'Show more ↓' : 'Show less ↑'}
          </button>
        )}

        {/* Message Actions */}
        {!isStreaming && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-sand flex-wrap">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-ink-soft bg-white border border-line hover:border-taupe hover:bg-cream transition-colors"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? t('copied') : t('copy')}
            </button>

            <button
              onClick={() => {
                const blob = new Blob([message.content], { type: 'text/plain' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `response-${message.id.slice(0, 8)}.txt`
                a.click()
                URL.revokeObjectURL(url)
              }}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-ink-soft bg-white border border-line hover:border-taupe hover:bg-cream transition-colors"
            >
              <Download size={12} />
              {t('export')}
            </button>

            <VoicePlayer text={message.content} className="flex-shrink-0" compact />

            {onFeedback && !isStreaming && feedbackKey && (
              <>
                <button
                  onClick={() => {
                    const newRating: 1 | null = feedbackRating === 1 ? null : 1
                    setFeedbackRating(newRating)
                    if (newRating !== null) {
                      localStorage.setItem(feedbackKey, '1')
                      onFeedback(message.dbId || message.id, 1)
                      toast.success(t('thanksFeedback'))
                    } else {
                      localStorage.removeItem(feedbackKey)
                    }
                  }}
                  className={cn(
                    'p-1.5 rounded-lg transition-colors',
                    feedbackRating === 1
                      ? 'text-leaf bg-leaf-wash'
                      : 'text-ash hover:text-leaf hover:bg-leaf-wash',
                  )}
                  title={t('helpful')}
                >
                  <ThumbsUp size={12} />
                </button>
                <button
                  onClick={() => {
                    const newRating: -1 | null = feedbackRating === -1 ? null : -1
                    setFeedbackRating(newRating)
                    if (newRating !== null) {
                      localStorage.setItem(feedbackKey, '-1')
                      onFeedback(message.dbId || message.id, -1)
                      toast.success(t('thanksFeedback'))
                    } else {
                      localStorage.removeItem(feedbackKey)
                    }
                  }}
                  className={cn(
                    'p-1.5 rounded-lg transition-colors',
                    feedbackRating === -1
                      ? 'text-leaf bg-blush-wash'
                      : 'text-ash hover:text-leaf hover:bg-blush-wash',
                  )}
                  title={t('notHelpful')}
                >
                  <ThumbsDown size={12} />
                </button>
              </>
            )}

            {onRetry && (
              <button
                onClick={() => onRetry(message.id)}
                className="p-1.5 text-ash hover:text-ink-soft hover:bg-sand rounded-lg transition-colors"
                title={t('regenerate')}
              >
                <RefreshCw size={12} />
              </button>
            )}

            {onDelete && (
              confirmingDelete ? (
                <div className="flex items-center gap-2 ml-1">
                  <span className="text-[11px] text-ink-mute">Delete this message?</span>
                  <button
                    onClick={() => { onDelete(message.id); setConfirmingDelete(false) }}
                    className="text-[11px] font-medium text-leaf hover:text-danger transition-colors"
                  >
                    {t('delete')}
                  </button>
                  <button
                    onClick={() => setConfirmingDelete(false)}
                    className="text-[11px] text-ash hover:text-ink-soft transition-colors"
                  >
                    {t('cancel')}
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmingDelete(true)}
                  className="p-1.5 text-ash hover:text-leaf hover:bg-blush-wash rounded-lg transition-colors"
                  title={t('deleteMessage')}
                >
                  <Trash2 size={12} />
                </button>
              )
            )}

            <div className="flex items-center gap-2 ml-auto text-[11px] text-ash">
              {message.stopped && (
                <span className="inline-flex items-center gap-1 rounded-full border border-line bg-cream px-2 py-0.5 text-ash">
                  <Square size={8} className="fill-taupe" />
                  stopped
                </span>
              )}
              {message.metadata?.timing?.duration && (
                <span>{message.metadata.timing.duration.toFixed(1)}s</span>
              )}
              {message.metadata?.usage?.total_tokens != null && (
                <span>{message.metadata.usage.total_tokens.toLocaleString()} tokens</span>
              )}
              <span>{formatTimestamp(message.timestamp, t, locale)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
})

interface AttachmentPreviewProps {
  attachment: Attachment
}

function AttachmentPreview({ attachment }: AttachmentPreviewProps) {
  const t = useTranslations('chat.message')
  const [imageError, setImageError] = useState(false)
  const [showLightbox, setShowLightbox] = useState(false)

  if (!attachment) return null

  // Get file icon based on type
  const getFileIcon = (fileType: string) => {
    if (fileType.startsWith('image/')) return <ImageIcon size={20} className="text-azure" />
    if (fileType === 'application/pdf') return <FileText size={20} className="text-leaf" />
    if (fileType.includes('word') || fileType.includes('document')) return <FileText size={20} className="text-azure" />
    return <File size={20} className="text-ink-mute" />
  }

  // Format file size
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // Handle uploaded files from our system
  if (attachment.file_id) {
    const isImage = attachment.file_type?.startsWith('image/')

    // Image preview with lightbox
    if (isImage && attachment.file_url && !imageError) {
      return (
        <>
          <div 
            className="rounded-lg overflow-hidden border border-line cursor-pointer hover:opacity-90 transition-opacity max-w-md"
            onClick={() => setShowLightbox(true)}
          >
            <img
              src={attachment.thumbnail_url || attachment.file_url}
              alt={attachment.file_name || t('image')}
              className="w-full h-auto"
              onError={() => setImageError(true)}
            />
          </div>

          {/* Lightbox */}
          {showLightbox && (
            <div 
              className="fixed inset-0 z-50 bg-black bg-opacity-90 flex items-center justify-center p-4"
              onClick={() => setShowLightbox(false)}
            >
              <div className="relative max-w-7xl max-h-full">
                <button
                  onClick={() => setShowLightbox(false)}
                  className="absolute top-4 right-4 text-white hover:text-taupe bg-black bg-opacity-50 rounded-full p-2"
                >
                  <svg aria-hidden="true" className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
                <img
                  src={attachment.file_url}
                  alt={attachment.file_name || t('image')}
                  className="max-w-full max-h-[90vh] object-contain"
                  onClick={(e) => e.stopPropagation()}
                />
              </div>
            </div>
          )}
        </>
      )
    }

    // Document/file preview
    return (
      <a
        href={attachment.file_url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-3 p-3 bg-cream rounded-lg hover:bg-sand transition-colors border border-line"
      >
        <div className="flex-shrink-0">
          {getFileIcon(attachment.file_type || '')}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-ink truncate">
            {attachment.file_name || t('file')}
          </p>
          <p className="text-xs text-ink-mute">
            {attachment.file_size ? formatFileSize(attachment.file_size) : t('unknownSize')}
          </p>
        </div>
        <Download size={16} className="text-ash flex-shrink-0" />
      </a>
    )
  }

  // Legacy attachment types (for backward compatibility)
  switch (attachment.type) {
    case 'image':
      return (
        <div className="rounded-lg overflow-hidden border border-line">
          <img
            src={attachment.url}
            alt={attachment.name || t('attachment')}
            className="w-full h-auto"
          />
        </div>
      )
    case 'link':
      return (
        <a
          href={attachment.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 p-3 bg-cream rounded-lg hover:bg-sand transition-colors"
        >
          {attachment.thumbnail && (
            <img
              src={attachment.thumbnail}
              alt=""
              className="w-12 h-12 rounded object-cover"
            />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-ink truncate">
              {attachment.name || t('link')}
            </p>
            <p className="text-xs text-ink-mute truncate">{attachment.url}</p>
          </div>
        </a>
      )
    default:
      return null
  }
}

/**
 * EmbeddedImage - Renders an image from URL with lightbox support
 * Used for displaying images detected in message content
 */
interface EmbeddedImageProps {
  url: string
  primaryColor?: string
}

function EmbeddedImage({ url, primaryColor = '#0d9488' }: EmbeddedImageProps) {
  const t = useTranslations('chat.message')
  const [imageError, setImageError] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [showLightbox, setShowLightbox] = useState(false)

  if (imageError) {
    return (
      <div className="rounded-lg border border-blush bg-blush-wash p-3 text-sm text-danger">
        <div className="flex items-center gap-2">
          <ImageIcon size={16} />
          <span>{t('imageFailed')}</span>
        </div>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs underline mt-1 inline-block"
          style={{ color: primaryColor }}
        >
          {t('openUrl')}
        </a>
      </div>
    )
  }

  return (
    <>
      <div
        className={cn(
          "relative rounded-lg overflow-hidden border border-line cursor-pointer",
          "hover:border-taupe transition-[color,background-color,border-color,box-shadow,opacity,transform] max-w-lg",
          isLoading && "min-h-[100px] bg-sand"
        )}
        onClick={() => setShowLightbox(true)}
      >
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div
              className="w-6 h-6 border-2 border-t-transparent rounded-full motion-safe:animate-spin"
              style={{ borderColor: primaryColor, borderTopColor: 'transparent' }}
            />
          </div>
        )}
        { }
        <img
          src={url}
          alt={t('screenshot')}
          loading="lazy"
          className={cn(
            "w-full h-auto transition-opacity",
            isLoading ? "opacity-0" : "opacity-100"
          )}
          onLoad={() => setIsLoading(false)}
          onError={() => {
            setIsLoading(false)
            setImageError(true)
          }}
        />
        {!isLoading && (
          <div className="absolute bottom-2 right-2 bg-black/50 text-white text-xs px-2 py-1 rounded">
            {t('clickToExpand')}
          </div>
        )}
      </div>

      {/* Lightbox */}
      {showLightbox && (
        <div
          className="fixed inset-0 z-50 bg-black bg-opacity-90 flex items-center justify-center p-4"
          onClick={() => setShowLightbox(false)}
        >
          <div className="relative max-w-7xl max-h-full">
            <button
              onClick={() => setShowLightbox(false)}
              className="absolute top-4 right-4 text-white hover:text-taupe bg-black bg-opacity-50 rounded-full p-2 z-10"
            >
              <svg aria-hidden="true" className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="absolute top-4 left-4 text-white hover:text-taupe bg-black bg-opacity-50 rounded-full p-2 z-10"
              onClick={(e) => e.stopPropagation()}
              title={t('openNewTab')}
            >
              <Download size={20} />
            </a>
            { }
            <img
              src={url}
              alt={t('screenshot')}
              className="max-w-full max-h-[90vh] object-contain"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </>
  )
}

function formatTimestamp(
  date: Date,
  t: (key: 'justNow' | 'minutesAgo' | 'hoursAgo', values?: { count: number }) => string,
  locale: string,
): string {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (seconds < 60) return t('justNow')
  if (minutes < 60) return t('minutesAgo', { count: minutes })
  if (hours < 24) return t('hoursAgo', { count: hours })

  return date.toLocaleTimeString(locale, {
    hour: 'numeric',
    minute: '2-digit',
  })
}
