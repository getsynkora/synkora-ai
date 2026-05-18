'use client'

import { useEffect, useState, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import dynamic from 'next/dynamic'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

const SyntaxHighlighter = dynamic(
  () => import('react-syntax-highlighter').then((m) => ({ default: m.Prism })),
  { ssr: false, loading: () => <pre className="bg-gray-900 text-gray-100 p-3 text-[12px] font-mono overflow-x-auto" /> }
)
import { FileText, Loader2, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react'
import DOMPurify from 'dompurify'

interface MarkdownViewerProps {
  url: string
  primaryColor?: string
  onError?: (error: string) => void
}

function sanitizeSvg(svg: string): string {
  return DOMPurify.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_ATTR: ['xlink:href'],
  })
}

/**
 * MarkdownViewer - Fetches and renders markdown content from a URL
 * Supports mermaid diagrams, code highlighting, and GitHub Flavored Markdown
 */
export function MarkdownViewer({ url, primaryColor = '#0d9488', onError }: MarkdownViewerProps) {
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>('')
  const [isCollapsed, setIsCollapsed] = useState(false)
  const mermaidRef = useRef<any>(null)

  // Dynamically import Mermaid (client-only)
  useEffect(() => {
    if (!mermaidRef.current && typeof window !== 'undefined') {
      import('mermaid')
        .then((mod) => {
          const mermaid = mod.default ?? mod
          mermaidRef.current = mermaid
          mermaid.initialize({
            startOnLoad: false,
            theme: 'default',
            securityLevel: 'strict',
            fontFamily: 'inherit',
          })
        })
        .catch((err) => console.error('Failed to load mermaid:', err))
    }
  }, [])

  // Fetch markdown content
  useEffect(() => {
    const fetchMarkdown = async () => {
      try {
        setLoading(true)
        setError('')
        const response = await fetch(url)
        if (!response.ok) throw new Error(`Failed to fetch markdown: ${response.statusText}`)
        const text = await response.text()
        setContent(text)
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to load markdown'
        setError(errorMsg)
        onError?.(errorMsg)
      } finally {
        setLoading(false)
      }
    }
    fetchMarkdown()
  }, [url, onError])

  // Render Mermaid diagrams after content updates.
  // Return a cleanup function so the timer is cancelled if the component unmounts
  // before the timeout fires (avoids writing to detached DOM nodes).
  useEffect(() => {
    if (!content || loading || !mermaidRef.current) return

    const timer = setTimeout(() => {
      const diagrams = document.querySelectorAll<HTMLElement>('.mermaid-diagram')
      diagrams.forEach((el, index) => {
        const code = el.innerText
        const id = `mermaid-${index}`
        el.id = id
        el.innerHTML = ''
        try {
          mermaidRef.current.render(id, code, (svgCode: string) => {
            el.innerHTML = sanitizeSvg(svgCode)
          })
        } catch (err) {
          console.error('Mermaid rendering error:', err)
        }
      })
    }, 100)

    return () => clearTimeout(timer)
  }, [content, loading])

  if (loading) {
    return (
      <div className="flex items-center gap-3 p-6 bg-gradient-to-br from-gray-50 to-white border border-gray-200 rounded-xl">
        <Loader2 className="animate-spin" size={20} style={{ color: primaryColor }} />
        <span className="text-sm text-gray-600">Loading tutorial...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-xl">
        <div className="flex items-start gap-3">
          <FileText className="text-red-500 mt-0.5" size={20} />
          <div>
            <p className="text-sm font-medium text-red-800">Failed to load markdown</p>
            <p className="text-xs text-red-600 mt-1">{error}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="my-4 border border-gray-200 rounded-xl overflow-hidden bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between p-4 bg-gradient-to-r from-gray-50 to-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg" style={{ background: `${primaryColor}15` }}>
            <FileText size={18} style={{ color: primaryColor }} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Tutorial Document</h3>
            <p className="text-xs text-gray-500">Generated markdown content</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="Open in new tab"
          >
            <ExternalLink size={16} className="text-gray-600" />
          </a>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title={isCollapsed ? 'Expand' : 'Collapse'}
          >
            {isCollapsed ? <ChevronDown size={16} className="text-gray-600" /> : <ChevronUp size={16} className="text-gray-600" />}
          </button>
        </div>
      </div>

      {/* Content */}
      {!isCollapsed && (
        <div className="p-6 prose prose-sm max-w-none overflow-x-auto">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code: ({ className, children, ...props }: any) => {
                const match = /language-(\w+)/.exec(className || '')
                const language = match ? match[1] : ''
                const codeString = String(children).replace(/\n$/, '')

                // In react-markdown v9, detect inline code by: no language class AND no newlines
                const isInline = !className && !codeString.includes('\n')

                if (language === 'mermaid') {
                  return (
                    <div className="my-6 flex justify-center">
                      <div className="mermaid-diagram bg-white p-4 rounded-lg border border-gray-200 inline-block">
                        {codeString}
                      </div>
                    </div>
                  )
                }

                if (isInline) {
                  return (
                    <code
                      className="px-2 py-0.5 rounded text-sm font-mono"
                      style={{ backgroundColor: `${primaryColor}10`, color: primaryColor }}
                      {...props}
                    >
                      {children}
                    </code>
                  )
                }

                return (
                  <div className="relative group/code my-4 max-w-full">
                    <div className="absolute right-2 top-2 opacity-0 group-hover/code:opacity-100 transition-opacity z-10">
                      <button
                        onClick={() => navigator.clipboard.writeText(codeString)}
                        className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded"
                      >
                        Copy
                      </button>
                    </div>
                    <div className="overflow-x-auto">
                      <SyntaxHighlighter
                        style={vscDarkPlus}
                        language={language || 'text'}
                        PreTag="div"
                        className="rounded-xl !my-0"
                        {...props}
                      >
                        {codeString}
                      </SyntaxHighlighter>
                    </div>
                  </div>
                )
              },
            }}
          >
            {content}
          </ReactMarkdown>
        </div>
      )}
    </div>
  )
}

/**
 * Detect if a message contains markdown URLs
 * Looks for S3 presigned URLs ending in .md
 */
export function detectMarkdownUrls(content: string): string[] {
  const urlRegex = /(https?:\/\/[^\s]+\.md[^\s]*)/gi
  const matches = content.match(urlRegex)
  return matches || []
}
