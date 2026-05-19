'use client'

import { memo, useState, useMemo, useRef, useEffect } from 'react'
import Image from 'next/image'
import dynamic from 'next/dynamic'
import { Copy, Check, RefreshCw, Sparkles, FileText, Image as ImageIcon, Download, File, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Message, Attachment, GeneratedImageData } from '../types'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import DOMPurify from 'dompurify'
import { SourcesList } from './SourceCard'
import { VoicePlayer } from './VoicePlayer'
import { ToolStatusDisplay } from './ToolStatusDisplay'

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
  return DOMPurify.sanitize(svgContent, {
    USE_PROFILES: { svg: true, svgFilters: true },
    ADD_TAGS: ['use'],
    FORBID_ATTR: ['xlink:href'],
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
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800 rounded-t-lg border-b border-gray-700">
        <span className="text-xs text-gray-400 font-mono">{language || 'code'}</span>
        <button
          onClick={() => navigator.clipboard.writeText(code)}
          className="text-xs text-gray-400 hover:text-white transition-colors flex items-center gap-1"
        >
          <Copy size={12} />
          Copy
        </button>
      </div>
      <pre className="overflow-x-auto bg-gray-950 text-gray-100 !my-0 p-3 text-[13px] leading-relaxed rounded-b-lg">
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
  onActionClick?: (text: string) => void
  className?: string
  chatConfig?: ChatConfig | null
  agentAvatar?: string
  userAvatar?: string
  agentName?: string
}

/**
 * TableWithExport — wraps a markdown table with CSV and PDF export buttons.
 * Uses a DOM ref to extract cell text, so it works with any react-markdown output.
 */
function TableWithExport({ children, ...props }: any) {
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
      const thStyle = 'text-align:left;padding:14px 18px;border:1px solid #e4d7c6;background:#f0e7da;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#5f564d;'
      const tdStyle = 'padding:18px;border:1px solid #e9ddcd;font-size:13px;color:#342f2a;'
      const tableHtml = `
        <table style="border-collapse:collapse;width:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;border-radius:18px;overflow:hidden;">
          <thead><tr>${headers.map(h => `<th style="${thStyle}">${h}</th>`).join('')}</tr></thead>
          <tbody>${rows.map((row, i) =>
            `<tr style="${i % 2 !== 0 ? 'background:#fbf7f1;' : 'background:#ffffff;'}">${row.map(cell => `<td style="${tdStyle}">${cell}</td>`).join('')}</tr>`
          ).join('')}</tbody>
        </table>`
      const win = window.open('', '_blank')
      if (!win) return
      win.document.write(`<!DOCTYPE html><html><head><title>Table Export</title>
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
    <div className="my-5 w-full max-w-full overflow-hidden rounded-[1.7rem] border border-[#ddd1c0] bg-[linear-gradient(180deg,_rgba(255,255,255,0.92),_rgba(248,242,232,0.98))] shadow-[0_24px_58px_-42px_rgba(39,27,16,0.34)]">
      <div className="flex flex-col gap-3 border-b border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(251,246,239,0.98),_rgba(243,235,224,0.94))] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#8a8378]">Structured Summary</div>
          <div className="mt-1 text-sm font-semibold tracking-[-0.02em] text-[#171717]">Review and export this table</div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={exportCSV}
            disabled={exporting !== null}
            title="Export as CSV"
            className="inline-flex items-center gap-1.5 rounded-full border border-[#d8ccbc] bg-white/88 px-3 py-1.5 text-xs font-semibold text-[#4b443c] transition-all duration-200 hover:-translate-y-0.5 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {exporting === 'csv' ? (
              <svg className="animate-spin" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
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
            title="Export as PDF"
            className="inline-flex items-center gap-1.5 rounded-full border border-[#d8ccbc] bg-white/88 px-3 py-1.5 text-xs font-semibold text-[#4b443c] transition-all duration-200 hover:-translate-y-0.5 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {exporting === 'pdf' ? (
              <svg className="animate-spin" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" strokeLinecap="round"/>
              </svg>
            ) : (
              <FileText size={12} />
            )}
            PDF
          </button>
        </div>
      </div>
      <div className="overflow-x-auto px-1 pb-1">
        <table ref={tableRef} className="min-w-full border-separate border-spacing-0" {...props}>
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
  onActionClick,
  className,
  chatConfig,
  agentAvatar,
  userAvatar,
  agentName,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
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

  // User message — right-aligned dark bubble
  if (isUser) {
    return (
      <div className={cn('flex justify-end group', className)}>
        <div className="max-w-[85%] sm:max-w-[72%]">
          <div className="bg-gray-900 rounded-2xl rounded-tr-sm px-4 py-3.5 shadow-sm">
            <p
              className="text-[15px] text-white/95 leading-[1.65] whitespace-pre-wrap tracking-[-0.01em] max-h-48 overflow-y-auto"
              style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.2) transparent' }}
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
                <span className="text-[10px] text-gray-500">Delete this message?</span>
                <button
                  onClick={() => { onDelete(message.id); setConfirmingDelete(false) }}
                  className="text-[10px] font-medium text-red-500 hover:text-red-600 transition-colors"
                >
                  Delete
                </button>
                <button
                  onClick={() => setConfirmingDelete(false)}
                  className="text-[10px] text-gray-400 hover:text-gray-600 transition-colors"
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                {onDelete && (
                  <button
                    onClick={() => setConfirmingDelete(true)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-all"
                    title="Delete message"
                  >
                    <Trash2 size={11} />
                  </button>
                )}
                <button
                  onClick={handleCopy}
                  className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-gray-600 transition-all"
                  title="Copy message"
                >
                  {copied ? <Check size={11} className="text-green-500" /> : <Copy size={11} />}
                </button>
                <span className="text-[10px] text-gray-400">You</span>
                <span className="text-[10px] text-gray-300">·</span>
                <span className="text-[10px] text-gray-400">{formatTimestamp(message.timestamp)}</span>
              </>
            )}
          </div>
        </div>
      </div>
    )
  }

  // Assistant message — left-aligned layout
  return (
    <div className={cn('group', className)}>
      <div className="flex items-center gap-2 mb-3">
        {agentAvatar ? (
          <div className="w-7 h-7 rounded-full overflow-hidden flex items-center justify-center bg-white relative shrink-0 ring-1 ring-slate-200">
            {agentAvatar.startsWith('http://') || agentAvatar.startsWith('https://') ? (
              <Image
                src={agentAvatar}
                alt="Agent"
                width={24}
                height={24}
                className="w-full h-full object-cover"
                unoptimized
              />
            ) : (
              <Image src={agentAvatar} alt="Agent" fill className="object-cover" />
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
        <span className="text-sm font-semibold text-gray-700 tracking-[-0.01em]">{agentName || 'Assistant'}</span>
        {message.metadata?.confidence && (
          <span className="text-[11px] text-gray-400">Confidence: {message.metadata.confidence}</span>
        )}
      </div>

      <div ref={contentRef} className="pl-6 sm:pl-8 min-w-0 w-full overflow-x-hidden" style={{ fontFamily }}>
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

        {/* Tool Status Display - Fixed height todo-list style */}
        {(toolStatus || recentTools.length > 0) && !message.content && (
          <ToolStatusDisplay
            currentTool={toolStatus ?? null}
            recentTools={recentTools}
            primaryColor={primaryColor}
            isStreaming={isStreaming}
            streamStartTime={streamStartTime}
            className="mb-3"
          />
        )}

        {/* Error Message */}
        {message.isError && (
          <div className="flex items-start gap-2 px-3 py-2.5 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 mb-2">
            <svg className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <span>{message.content}</span>
          </div>
        )}

        {/* Message Content */}
        <div
          className={cn(
            'prose prose-sm max-w-none prose-gray',
            isPlatformEngineer && 'rounded-[1.7rem] border border-[#e2d7c8] bg-[linear-gradient(180deg,_rgba(255,255,255,0.9),_rgba(248,243,235,0.98))] px-5 py-4 shadow-[0_24px_58px_-44px_rgba(39,27,16,0.28)]'
          )}
          style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}
        >
          {!message.isError && thinkingStatus && !message.content && !toolStatus && recentTools.length === 0 ? (
            <div className="flex items-center gap-2 py-1">
              <div className="flex gap-1">
                <span
                  className="w-1.5 h-1.5 rounded-full animate-bounce inline-block"
                  style={{ animationDelay: '0ms', backgroundColor: primaryColor }}
                />
                <span
                  className="w-1.5 h-1.5 rounded-full animate-bounce inline-block"
                  style={{ animationDelay: '150ms', backgroundColor: primaryColor }}
                />
                <span
                  className="w-1.5 h-1.5 rounded-full animate-bounce inline-block"
                  style={{ animationDelay: '300ms', backgroundColor: primaryColor }}
                />
              </div>
              <span className="text-sm text-gray-500">{thinkingStatus}</span>
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
                        className="px-1.5 py-0.5 rounded text-[13px] font-mono bg-gray-100 text-gray-800"
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
                  <thead className="bg-[#f1e7da]" {...props}>
                    {children}
                  </thead>
                ),
                tbody: ({ children, ...props }: any) => (
                  <tbody className="[&_tr:nth-child(even)]:bg-[#fbf7f1] [&_tr:nth-child(odd)]:bg-white" {...props}>
                    {children}
                  </tbody>
                ),
                tr: ({ children, ...props }: any) => (
                  <tr className="transition-colors hover:bg-[#f8f2e8] [&>td]:border-b [&>td]:border-[#ede2d3] last:[&>td]:border-b-0" {...props}>{children}</tr>
                ),
                th: ({ children, ...props }: any) => (
                  <th
                    className="px-5 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.2em] text-[#6b635a]"
                    {...props}
                  >
                    {children}
                  </th>
                ),
                td: ({ children, ...props }: any) => (
                  <td className="px-5 py-5 align-top text-[15px] leading-7 text-[#474139] first:font-semibold first:text-[#171717]" {...props}>
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
                  <h1 className="text-xl font-bold text-gray-900 mb-3 mt-4 first:mt-0 flex flex-wrap items-center gap-2 min-w-0" {...props}>
                    {children}
                  </h1>
                ),
                h2: ({ children, ...props }: any) => (
                  <h2 className="text-lg font-bold text-gray-900 mb-2 mt-4 first:mt-0 flex flex-wrap items-center gap-2 min-w-0" {...props}>
                    {children}
                  </h2>
                ),
                h3: ({ children, ...props }: any) => (
                  <h3 className="text-base font-semibold text-gray-900 mb-2 mt-3 first:mt-0" {...props}>
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
                  <li className="text-[15px] leading-[1.65] text-gray-700 relative pl-4 before:content-['•'] before:absolute before:left-0 before:text-gray-400" {...props}>
                    {children}
                  </li>
                ),
                p: ({ children, ...props }: any) => (
                  <p className="mb-3 last:mb-0 text-[15px] leading-[1.7] text-gray-700 tracking-[-0.005em]" {...props}>
                    {children}
                  </p>
                ),
                blockquote: ({ children, ...props }: any) => (
                  <blockquote
                    className="border-l-3 pl-3 py-1 my-3 text-gray-600 bg-gray-50 rounded-r"
                    style={{ borderLeftColor: primaryColor, borderLeftWidth: '3px' }}
                    {...props}
                  >
                    {children}
                  </blockquote>
                ),
                hr: ({ ...props }: any) => (
                  <hr className="my-4 border-gray-200" {...props} />
                ),
                strong: ({ children, ...props }: any) => (
                  <strong className="font-semibold text-gray-900" {...props}>
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
                        alt={alt || 'Image'}
                        className="max-w-full h-auto rounded-lg border border-gray-200"
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

          {isStreaming && (
            <span
              className="inline-block w-0.5 h-4 animate-pulse ml-0.5"
              style={{ backgroundColor: primaryColor }}
            />
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
          <div className="mt-3 space-y-3">
            {message.metadata.infographics.map((infographic: any, index: number) => (
              <div key={infographic.id || index} className="rounded-lg overflow-hidden border border-gray-200 bg-gray-900">
                {infographic.title && (
                  <div className="px-4 py-2 text-xs font-medium text-gray-400 border-b border-gray-700">
                    {infographic.title}
                  </div>
                )}
                {infographic.svg_content ? (
                  <div
                    className="w-full overflow-auto"
                    dangerouslySetInnerHTML={{ __html: sanitizeSvg(infographic.svg_content) }}
                  />
                ) : infographic.png_url ? (
                  <img
                    src={infographic.png_url}
                    alt={infographic.title || 'Infographic'}
                    className="w-full h-auto"
                  />
                ) : infographic.svg_url ? (
                  <img
                    src={infographic.svg_url}
                    alt={infographic.title || 'Infographic'}
                    className="w-full h-auto"
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
                      alt={img.revised_prompt || img.prompt || 'Generated image'}
                      className="w-full h-auto block"
                      style={{ maxHeight: '640px', objectFit: 'contain', background: '#0a0a0a' }}
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
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/15 hover:bg-white/25 backdrop-blur-sm text-white text-xs font-medium rounded-lg transition-colors border border-white/20"
                            onClick={e => e.stopPropagation()}
                          >
                            <Download className="w-3.5 h-3.5" />
                            Download
                          </a>
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="px-4 py-6 text-sm text-zinc-400 bg-zinc-900 text-center rounded-xl">
                    Image unavailable — S3 storage not configured
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Vehicle Maps (Mapbox) */}
        {message.metadata?.vehicle_maps && message.metadata.vehicle_maps.length > 0 && (
          <div className="mt-3 space-y-3">
            {message.metadata.vehicle_maps.map((map: any, index: number) => (
              <div key={map.id || index} className="rounded-lg overflow-hidden border border-gray-200">
                {(map.distance_km || map.duration_min) && (
                  <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 flex items-center gap-3 text-xs text-gray-600">
                    {map.profile && <span className="capitalize font-medium">{map.profile}</span>}
                    {map.distance_km && <span>📍 {map.distance_km} km</span>}
                    {map.duration_min && <span>⏱ {map.duration_min} min</span>}
                    {map.marker_count > 0 && <span>🔵 {map.marker_count} vehicles</span>}
                  </div>
                )}
                <img
                  src={map.map_url}
                  alt="Map"
                  className="w-full h-auto"
                  style={{ maxHeight: '500px', objectFit: 'cover' }}
                />
                {map.embed_url && (
                  <div className="px-3 py-2 bg-gray-50 border-t border-gray-200 text-xs">
                    <a href={map.embed_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                      Open interactive map ↗
                    </a>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Fleet Intelligence Cards */}
        {message.metadata?.fleet_cards && message.metadata.fleet_cards.length > 0 && (
          <div className="mt-4 space-y-6">
            {message.metadata.fleet_cards.map((card: any, index: number) => {
              const { data, tool } = card
              const summary = data?.summary

              const isFleetHealth = tool?.includes('fleet_health')
              const isDemandSupply = tool?.includes('demand_supply')
              const isPredictDemand = tool?.includes('predict_demand')
              const isRebalancing = tool?.includes('rebalancing')
              const isTripPerf = tool?.includes('trip_performance')
              const isEventImpact = tool?.includes('event_impact')
              const isNetworkHealth = tool?.includes('network_health')
              const isParkingCompliance = tool?.includes('parking_compliance')
              const isBatteryDegradation = tool?.includes('battery_degradation')
              const isRangerPerf = tool?.includes('ranger_performance')

              const cardTitle = isFleetHealth ? 'Fleet Health' :
                isDemandSupply ? 'Demand vs Supply' :
                isPredictDemand ? 'Demand Forecast' :
                isRebalancing ? 'Rebalancing Plan' :
                isTripPerf ? 'Trip Performance' :
                isEventImpact ? 'Event Impact' :
                isNetworkHealth ? 'Network Health' :
                isParkingCompliance ? 'Parking Compliance' :
                isBatteryDegradation ? 'Battery Degradation' :
                isRangerPerf ? 'Ranger Performance' : 'Fleet Analytics'

              const fleetStatus = isFleetHealth ? (
                (summary?.operational_rate_pct ?? 0) >= 90 &&
                (summary?.low_battery_count ?? 0) === 0 &&
                (summary?.maintenance_count ?? 0) === 0 &&
                (summary?.idle_count ?? data?.idle?.length ?? 0) === 0
                  ? 'healthy'
                  : (summary?.operational_rate_pct ?? 0) >= 70 ? 'warning' : 'critical'
              ) : null

              const primaryAction = isFleetHealth && data?.low_battery?.length > 0
                ? `Dispatch charging for ${data.low_battery.length} low-battery vehicle(s)`
                : isFleetHealth && data?.idle?.length > 0
                ? `Flag ${data.idle.length} idle vehicle(s) for repositioning`
                : isRebalancing && data?.moves?.length > 0
                ? `Confirm rebalancing — ${data.total_vehicles_to_move} vehicles`
                : isPredictDemand
                ? `Generate deployment plan for ${data?.service_area || 'this area'}`
                : isDemandSupply && data?.deficit_service_areas?.length > 0
                ? `Rebalance ${data.deficit_service_areas.length} deficit area(s)`
                : isNetworkHealth && data?.offline_count > 0
                ? `Dispatch rangers — ${data.offline_count} offline vehicles`
                : isParkingCompliance && data?.non_compliant_trips > 0
                ? `Create ${data.non_compliant_trips} relocation task(s)`
                : isBatteryDegradation && data?.total_flagged > 0
                ? `Schedule maintenance for ${data.total_flagged} vehicle(s)`
                : null

              // Open-flow hero number (no box, pure typography)
              const H = ({ value, label, color = 'text-gray-900' }: { value: any; label: string; color?: string }) => (
                <div className="text-center flex-1">
                  <div className={`text-4xl font-black tracking-tight leading-none ${color}`}>{value ?? '—'}</div>
                  <div className="mt-1.5 text-[10px] text-gray-400 font-medium uppercase tracking-wide">{label}</div>
                </div>
              )

              // Open row — no background, just a thin bottom rule
              const R = ({ left, right, sub, rightColor = 'text-gray-700' }: { left: string; sub?: string; right: any; rightColor?: string }) => (
                <div className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0">
                  <div className="min-w-0 pr-4">
                    <span className="text-sm text-gray-800">{left}</span>
                    {sub && <span className="text-[11px] text-gray-400 ml-2">{sub}</span>}
                  </div>
                  <div className={`text-sm font-semibold tabular-nums shrink-0 ${rightColor}`}>{right}</div>
                </div>
              )

              // Free-flow section: label + rows + optional inline action
              const Section = ({ title, children, action }: { title: string; children: React.ReactNode; action?: string | null }) => (
                <div className="mt-4">
                  <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-2">{title}</div>
                  {children}
                  {action && onActionClick && !isStreaming && (
                    <div className="flex items-center gap-3 pt-3 mt-1">
                      <button
                        onClick={() => onActionClick(action)}
                        className="w-8 h-8 rounded-full bg-gray-200 hover:bg-gray-300 flex items-center justify-center shrink-0 transition-colors"
                      >
                        <svg width="9" height="9" viewBox="0 0 9 9" fill="currentColor" className="ml-0.5 text-gray-700"><path d="M2.5 1.5l5 3-5 3V1.5z"/></svg>
                      </button>
                      <span className="text-sm font-medium text-gray-700 leading-snug">{action}</span>
                    </div>
                  )}
                </div>
              )

              return (
                <div key={card.id || index}>

                  {/* ── Title (open, no box) ── */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span className="text-base font-bold text-gray-900">{cardTitle}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {data?.confidence && (
                        <span className={`text-[11px] font-semibold ${
                          data.confidence === 'high' ? 'text-emerald-500' :
                          data.confidence === 'medium' ? 'text-amber-500' : 'text-gray-400'
                        }`}>
                          {data.confidence} confidence
                        </span>
                      )}
                      {fleetStatus && (
                        <span className={`text-[11px] font-semibold flex items-center gap-1 ${
                          fleetStatus === 'healthy' ? 'text-emerald-500' :
                          fleetStatus === 'warning' ? 'text-amber-500' : 'text-red-500'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${fleetStatus === 'healthy' ? 'bg-emerald-500' : fleetStatus === 'warning' ? 'bg-amber-500' : 'bg-red-500'}`} />
                          {fleetStatus === 'healthy' ? 'Healthy' : fleetStatus === 'warning' ? 'Attention' : 'Critical'}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* ── Fleet Health ── */}
                  {isFleetHealth && summary && (
                    <>
                      <div className="flex gap-6 mb-5">
                        <H value={summary.total_vehicles} label="Total Vehicles" />
                        <H
                          value={`${summary.operational_rate_pct ?? 0}%`}
                          label="Operational"
                          color={summary.operational_rate_pct >= 90 ? 'text-emerald-500' : summary.operational_rate_pct >= 70 ? 'text-amber-500' : 'text-red-500'}
                        />
                        <H
                          value={summary.avg_battery_pct != null ? `${summary.avg_battery_pct}%` : '—'}
                          label="Avg Battery"
                          color={summary.avg_battery_pct != null && summary.avg_battery_pct < 30 ? 'text-red-500' : 'text-gray-900'}
                        />
                      </div>
                      <div className="flex gap-8 mb-6">
                        <H value={summary.low_battery_count} label="Low Battery" color={summary.low_battery_count > 0 ? 'text-red-400' : 'text-gray-200'} />
                        <H value={summary.idle_count} label="Idle" color={summary.idle_count > 0 ? 'text-amber-400' : 'text-gray-200'} />
                        <H value={summary.maintenance_count} label="Maintenance" color={summary.maintenance_count > 0 ? 'text-orange-400' : 'text-gray-200'} />
                      </div>
                      {(data.low_battery?.length > 0 || data.idle?.length > 0) && (
                        <Section title={data.low_battery?.length > 0 ? 'Low Battery Vehicles' : 'Idle Vehicles'} action={primaryAction}>
                          {data.low_battery?.length > 0
                            ? data.low_battery.slice(0, 5).map((v: any, i: number) => (
                                <R key={i} left={v.qr_code || v.vehicle_id} sub={v.service_area}
                                  right={<span className="flex items-center gap-2">
                                    <span className="w-16 h-1 bg-gray-200 rounded-full overflow-hidden inline-block align-middle">
                                      <span className="h-full bg-red-400 rounded-full block" style={{ width: `${v.battery_pct}%` }} />
                                    </span>
                                    {v.battery_pct}%
                                  </span>}
                                  rightColor="text-red-500"
                                />
                              ))
                            : data.idle.slice(0, 5).map((v: any, i: number) => (
                                <R key={i} left={v.qr_code || v.vehicle_id} sub={v.service_area} right={`${v.idle_hours}h idle`} rightColor="text-amber-500" />
                              ))
                          }
                        </Section>
                      )}
                      {!data.low_battery?.length && !data.idle?.length && data?.recommended_actions?.length > 0 && (
                        <div className="text-sm text-gray-500">{data.recommended_actions[0]}</div>
                      )}
                    </>
                  )}

                  {/* ── Trip Performance ── */}
                  {isTripPerf && (
                    <>
                      <div className="flex gap-6 mb-5">
                        <H value={summary?.total_trips ?? data.kpis?.total_trips ?? data.total_trips ?? '—'} label="Total Trips" />
                        <H value={(() => { const r = summary?.completion_rate_pct ?? data.kpis?.completion_rate_pct ?? data.completion_rate_pct; return r != null ? `${r}%` : '—' })()} label="Completion" color="text-emerald-500" />
                        <H value={(() => { const r = summary?.total_revenue ?? data.kpis?.total_revenue ?? data.total_revenue; return r != null ? `$${r}` : '—' })()} label="Revenue" />
                      </div>
                      {(data?.top_service_areas ?? data?.top_zones)?.length > 0 && (
                        <Section title="Top Service Areas" action={null}>
                          {(data.top_service_areas ?? data.top_zones).slice(0, 5).map((z: any, i: number) => (
                            <R key={i} left={z.service_area} right={`${z.trips ?? z.trip_count} trips`} />
                          ))}
                        </Section>
                      )}
                    </>
                  )}

                  {/* ── Demand vs Supply ── */}
                  {isDemandSupply && (
                    <>
                      <div className="flex gap-6 mb-5">
                        <H value={data.total_zones ?? data.zones?.length ?? '—'} label="Service Areas" />
                        <H value={data.deficit_zones ?? data.deficit_service_areas?.length ?? 0} label="Deficit" color="text-red-400" />
                        <H value={data.surplus_zones ?? data.surplus_service_areas?.length ?? 0} label="Surplus" color="text-emerald-400" />
                      </div>
                      {data?.zones?.length > 0 && (
                        <Section title="Service Area Breakdown" action={primaryAction}>
                          {data.zones.slice(0, 6).map((z: any, i: number) => (
                            <R key={i} left={z.service_area} sub={`${z.available_vehicles ?? z.vehicles_available ?? '—'} vehicles`}
                              right={z.status}
                              rightColor={z.status === 'deficit' ? 'text-red-500' : z.status === 'surplus' ? 'text-emerald-500' : 'text-gray-400'}
                            />
                          ))}
                        </Section>
                      )}
                    </>
                  )}

                  {/* ── Rebalancing Plan ── */}
                  {isRebalancing && (
                    <>
                      <div className="flex gap-6 mb-5">
                        <H value={data.total_vehicles_to_move ?? '—'} label="Vehicles to Move" />
                        <H value={data.moves?.length ?? 0} label="Planned Routes" />
                      </div>
                      {data?.moves?.length > 0 && (
                        <Section title="Generated Rebalancing Plan" action={primaryAction}>
                          {data.moves.slice(0, 5).map((m: any, i: number) => (
                            <R key={i}
                              left={`${m.from_service_area} → ${m.to_service_area}`}
                              right={`${m.vehicle_count} vehicles`}
                              rightColor={m.priority === 'high' || m.priority === 'urgent' ? 'text-red-500' : 'text-gray-700'}
                            />
                          ))}
                        </Section>
                      )}
                    </>
                  )}

                  {/* ── Event Impact ── */}
                  {isEventImpact && (
                    <>
                      <div className="flex gap-6 mb-5">
                        <H value={data.event_trips ?? '—'} label="Event Trips" />
                        <H value={data.baseline_trips ?? '—'} label="Baseline" />
                        <H
                          value={data.overall_delta_pct != null ? `${data.overall_delta_pct >= 0 ? '+' : ''}${data.overall_delta_pct}%` : '—'}
                          label="Overall Delta"
                          color={(data.overall_delta_pct ?? 0) >= 0 ? 'text-emerald-500' : 'text-red-500'}
                        />
                      </div>
                      {data?.hotspot_service_areas?.length > 0 && (
                        <Section title="Area Impact" action={null}>
                          {data.hotspot_service_areas.slice(0, 5).map((z: any, i: number) => (
                            <R key={i} left={z.service_area}
                              right={`${z.delta_pct >= 0 ? '+' : ''}${z.delta_pct}%`}
                              rightColor={z.delta_pct >= 0 ? 'text-emerald-500' : 'text-red-500'}
                            />
                          ))}
                        </Section>
                      )}
                    </>
                  )}

                  {/* ── Network Health ── */}
                  {isNetworkHealth && (
                    <>
                      <div className="flex gap-6 mb-5">
                        <H value={data.total_vehicles ?? '—'} label="Total Vehicles" />
                        <H value={data.offline_count ?? 0} label="Offline" color={(data.offline_count ?? 0) > 0 ? 'text-red-400' : 'text-gray-200'} />
                        <H value={data.offline_rate_pct != null ? `${data.offline_rate_pct}%` : '—'} label="Offline Rate" color={(data.offline_rate_pct ?? 0) > 10 ? 'text-red-500' : 'text-gray-900'} />
                      </div>
                      {data?.offline_service_areas?.length > 0 && (
                        <Section title="Dead Spots" action={primaryAction}>
                          {data.offline_service_areas.slice(0, 5).map((z: any, i: number) => (
                            <R key={i} left={z.service_area} right={`${z.offline_rate_pct}% offline`} rightColor="text-red-500" />
                          ))}
                        </Section>
                      )}
                    </>
                  )}

                  {/* ── Parking Compliance ── */}
                  {isParkingCompliance && (
                    <>
                      <div className="flex gap-6 mb-5">
                        <H value={data.total_trips ?? '—'} label="Total Trips" />
                        <H value={data.non_compliant_trips ?? 0} label="Non-Compliant" color={(data.non_compliant_trips ?? 0) > 0 ? 'text-orange-400' : 'text-gray-200'} />
                        <H value={data.estimated_relocation_ranger_hours != null ? `~${data.estimated_relocation_ranger_hours}h` : '—'} label="Ranger Hours" />
                      </div>
                      {data?.worst_service_areas?.length > 0 && (
                        <Section title="Worst Areas" action={primaryAction}>
                          {data.worst_service_areas.slice(0, 5).map((z: any, i: number) => (
                            <R key={i} left={z.service_area} right={`${z.non_compliance_rate_pct}% non-compliant`} rightColor="text-orange-500" />
                          ))}
                        </Section>
                      )}
                    </>
                  )}

                  {/* ── Battery Degradation ── */}
                  {isBatteryDegradation && (
                    <>
                      <div className="flex gap-6 mb-5">
                        <H value={data.total_checked ?? '—'} label="Checked" />
                        <H value={data.total_flagged ?? 0} label="Flagged" color={(data.total_flagged ?? 0) > 0 ? 'text-red-400' : 'text-gray-200'} />
                        <H value={data.avg_drain_pct_per_trip != null ? `${data.avg_drain_pct_per_trip}%` : '—'} label="Avg Drain/Trip" />
                      </div>
                      {data?.flagged_vehicles?.length > 0 && (
                        <Section title="Flagged Vehicles" action={primaryAction}>
                          {data.flagged_vehicles.slice(0, 5).map((v: any, i: number) => (
                            <R key={i} left={v.vehicle_id} sub={`${v.trips_analysed} trips analysed`} right={`${v.avg_drain_pct_per_trip}% / trip`} rightColor="text-red-500" />
                          ))}
                        </Section>
                      )}
                    </>
                  )}

                  {/* ── Ranger Performance ── */}
                  {isRangerPerf && (
                    <>
                      <div className="flex gap-6 mb-5">
                        <H value={data.total_rangers ?? '—'} label="Rangers" />
                        <H value={data.avg_completion_rate_pct != null ? `${data.avg_completion_rate_pct}%` : '—'} label="Avg Completion" color="text-emerald-500" />
                        <H value={data.avg_task_duration_min != null ? `${data.avg_task_duration_min}m` : '—'} label="Avg Task Time" />
                      </div>
                      {data?.rangers?.length > 0 && (
                        <Section title="Ranger Breakdown" action={null}>
                          {data.rangers.slice(0, 5).map((r: any, i: number) => (
                            <R key={i} left={r.ranger_name || r.ranger_id} sub={`${r.tasks_completed}/${r.tasks_total} tasks`}
                              right={`${r.completion_rate_pct}%`}
                              rightColor={r.completion_rate_pct >= 80 ? 'text-emerald-500' : r.completion_rate_pct >= 60 ? 'text-amber-500' : 'text-red-500'}
                            />
                          ))}
                        </Section>
                      )}
                    </>
                  )}

                  {/* ── Demand Forecast ── */}
                  {isPredictDemand && (
                    <>
                      <div className="flex gap-6 mb-5">
                        <H
                          value={data.predicted_demand_index != null ? `${data.predicted_demand_index}x` : '—'}
                          label="Demand Index"
                          color={(data.predicted_demand_index ?? 1) > 1.2 ? 'text-emerald-500' : (data.predicted_demand_index ?? 1) < 0.8 ? 'text-red-500' : 'text-gray-900'}
                        />
                        <H value={data.recommended_vehicle_count != null ? `${data.recommended_vehicle_count}` : '—'} label="Recommended" />
                        <H value={data.hours_ahead != null ? `${data.hours_ahead}h` : '—'} label="Horizon" />
                      </div>
                      {data?.signals && (
                        <Section title="Demand Signals" action={primaryAction}>
                          {Object.entries(data.signals).map(([key, sig]: [string, any]) => (
                            <R key={key}
                              left={key.charAt(0).toUpperCase() + key.slice(1)}
                              sub={`${Math.round(sig.weight * 100)}% weight`}
                              right={`${sig.modifier}x`}
                              rightColor={sig.modifier > 1.1 ? 'text-emerald-500' : sig.modifier < 0.9 ? 'text-red-500' : 'text-gray-700'}
                            />
                          ))}
                        </Section>
                      )}
                      {data?.summary && (
                        <p className="mt-3 text-sm text-gray-500 leading-relaxed">{data.summary}</p>
                      )}
                    </>
                  )}

                </div>
              )
            })}
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
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100 flex-wrap">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-600 bg-white border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? 'Copied' : 'Copy'}
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
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-600 bg-white border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors"
            >
              <Download size={12} />
              Export
            </button>

            <VoicePlayer text={message.content} className="flex-shrink-0" compact />

            {onRetry && (
              <button
                onClick={() => onRetry(message.id)}
                className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                title="Regenerate"
              >
                <RefreshCw size={12} />
              </button>
            )}

            {onDelete && (
              confirmingDelete ? (
                <div className="flex items-center gap-2 ml-1">
                  <span className="text-[11px] text-gray-500">Delete this message?</span>
                  <button
                    onClick={() => { onDelete(message.id); setConfirmingDelete(false) }}
                    className="text-[11px] font-medium text-red-500 hover:text-red-600 transition-colors"
                  >
                    Delete
                  </button>
                  <button
                    onClick={() => setConfirmingDelete(false)}
                    className="text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmingDelete(true)}
                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                  title="Delete message"
                >
                  <Trash2 size={12} />
                </button>
              )
            )}

            <div className="flex items-center gap-2 ml-auto text-[11px] text-gray-400">
              {message.metadata?.timing?.duration && (
                <span>{message.metadata.timing.duration.toFixed(1)}s</span>
              )}
              {message.metadata?.usage?.total_tokens != null && (
                <span>{message.metadata.usage.total_tokens.toLocaleString()} tokens</span>
              )}
              <span>{formatTimestamp(message.timestamp)}</span>
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
  const [imageError, setImageError] = useState(false)
  const [showLightbox, setShowLightbox] = useState(false)

  if (!attachment) return null

  // Get file icon based on type
  const getFileIcon = (fileType: string) => {
    if (fileType.startsWith('image/')) return <ImageIcon size={20} className="text-blue-500" />
    if (fileType === 'application/pdf') return <FileText size={20} className="text-red-500" />
    if (fileType.includes('word') || fileType.includes('document')) return <FileText size={20} className="text-blue-600" />
    return <File size={20} className="text-gray-500" />
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
            className="rounded-lg overflow-hidden border border-gray-200 cursor-pointer hover:opacity-90 transition-opacity max-w-md"
            onClick={() => setShowLightbox(true)}
          >
            <img
              src={attachment.thumbnail_url || attachment.file_url}
              alt={attachment.file_name || 'Image'}
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
                  className="absolute top-4 right-4 text-white hover:text-gray-300 bg-black bg-opacity-50 rounded-full p-2"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
                <img
                  src={attachment.file_url}
                  alt={attachment.file_name || 'Image'}
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
        className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors border border-gray-200"
      >
        <div className="flex-shrink-0">
          {getFileIcon(attachment.file_type || '')}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">
            {attachment.file_name || 'File'}
          </p>
          <p className="text-xs text-gray-500">
            {attachment.file_size ? formatFileSize(attachment.file_size) : 'Unknown size'}
          </p>
        </div>
        <Download size={16} className="text-gray-400 flex-shrink-0" />
      </a>
    )
  }

  // Legacy attachment types (for backward compatibility)
  switch (attachment.type) {
    case 'image':
      return (
        <div className="rounded-lg overflow-hidden border border-gray-200">
          <img
            src={attachment.url}
            alt={attachment.name || 'Attachment'}
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
          className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
        >
          {attachment.thumbnail && (
            <img
              src={attachment.thumbnail}
              alt=""
              className="w-12 h-12 rounded object-cover"
            />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {attachment.name || 'Link'}
            </p>
            <p className="text-xs text-gray-500 truncate">{attachment.url}</p>
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
  const [imageError, setImageError] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [showLightbox, setShowLightbox] = useState(false)

  if (imageError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
        <div className="flex items-center gap-2">
          <ImageIcon size={16} />
          <span>Failed to load image</span>
        </div>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs underline mt-1 inline-block"
          style={{ color: primaryColor }}
        >
          Open URL directly
        </a>
      </div>
    )
  }

  return (
    <>
      <div
        className={cn(
          "relative rounded-lg overflow-hidden border border-gray-200 cursor-pointer",
          "hover:border-gray-300 transition-all max-w-lg",
          isLoading && "min-h-[100px] bg-gray-100"
        )}
        onClick={() => setShowLightbox(true)}
      >
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div
              className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin"
              style={{ borderColor: primaryColor, borderTopColor: 'transparent' }}
            />
          </div>
        )}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={url}
          alt="Screenshot"
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
            Click to expand
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
              className="absolute top-4 right-4 text-white hover:text-gray-300 bg-black bg-opacity-50 rounded-full p-2 z-10"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="absolute top-4 left-4 text-white hover:text-gray-300 bg-black bg-opacity-50 rounded-full p-2 z-10"
              onClick={(e) => e.stopPropagation()}
              title="Open in new tab"
            >
              <Download size={20} />
            </a>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={url}
              alt="Screenshot"
              className="max-w-full max-h-[90vh] object-contain"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </>
  )
}

function formatTimestamp(date: Date): string {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (seconds < 60) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`

  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}
