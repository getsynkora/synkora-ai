'use client'

import { useEffect, useRef, useState, useId } from 'react'
import { Copy, Download, Maximize2, Minimize2, Check } from 'lucide-react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import DOMPurify from 'dompurify'

interface MermaidDiagramProps {
  code: string
}

function sanitizeSvg(svg: string): string {
  return DOMPurify.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_ATTR: ['xlink:href'],
  })
}

export function MermaidDiagram({ code }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svgContent, setSvgContent] = useState<string>('')
  const [error, setError] = useState<string>('')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [copied, setCopied] = useState(false)
  const uniqueId = useId().replace(/:/g, '_')

  useEffect(() => {
    let cancelled = false

    async function renderDiagram() {
      try {
        const mod = await import('mermaid')
        const mermaid = mod.default ?? mod
        mermaid.initialize({
          startOnLoad: false,
          theme: 'default',
          securityLevel: 'strict',
          fontFamily: 'system-ui, -apple-system, sans-serif',
        })

        const id = `mermaid${uniqueId}`
        const { svg } = await mermaid.render(id, code.trim())
        if (!cancelled) {
          setSvgContent(sanitizeSvg(svg))
          setError('')
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Mermaid render error:', err)
          setError(err instanceof Error ? err.message : 'Failed to render diagram')
        }
      }
    }

    renderDiagram()
    return () => { cancelled = true }
  }, [code, uniqueId])

  const handleCopySvg = async () => {
    if (!svgContent) return
    await navigator.clipboard.writeText(svgContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownloadSvg = () => {
    if (!svgContent) return
    const blob = new Blob([svgContent], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'diagram.svg'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDownloadPng = () => {
    if (!svgContent) return
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const img = new Image()
    const svgBlob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(svgBlob)

    img.onload = () => {
      const scale = 2
      canvas.width = img.width * scale
      canvas.height = img.height * scale
      ctx.scale(scale, scale)
      ctx.drawImage(img, 0, 0)
      URL.revokeObjectURL(url)

      const pngUrl = canvas.toDataURL('image/png')
      const a = document.createElement('a')
      a.href = pngUrl
      a.download = 'diagram.png'
      a.click()
    }
    img.src = url
  }

  // Fallback: show raw code on error
  if (error) {
    return (
      <div className="my-3 -mx-2">
        <div className="text-xs text-amber-600 bg-amber-50 px-3 py-1.5 rounded-t-lg border border-amber-200">
          Diagram rendering failed: {error}
        </div>
        <SyntaxHighlighter
          style={vscDarkPlus}
          language="text"
          PreTag="div"
          className="!rounded-t-none !rounded-b-lg !my-0 !text-[13px]"
          customStyle={{ margin: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    )
  }

  if (!svgContent) {
    return (
      <div className="my-3 flex items-center justify-center h-32 bg-gray-50 rounded-lg border border-gray-200">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
          Rendering diagram...
        </div>
      </div>
    )
  }

  const diagramView = (
    <div
      ref={containerRef}
      className="overflow-auto bg-white rounded-lg p-4"
      dangerouslySetInnerHTML={{ __html: svgContent }}
    />
  )

  return (
    <>
      <div className="my-3 -mx-2 rounded-lg border border-gray-200 overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-3 py-1.5 bg-gray-50 border-b border-gray-200">
          <span className="text-xs text-gray-500 font-medium">Mermaid Diagram</span>
          <div className="flex items-center gap-1">
            <button
              onClick={handleCopySvg}
              className="p-1 text-gray-400 hover:text-gray-600 rounded transition-colors"
              title="Copy SVG"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
            <button
              onClick={handleDownloadSvg}
              className="p-1 text-gray-400 hover:text-gray-600 rounded transition-colors"
              title="Download SVG"
            >
              <Download size={14} />
            </button>
            <button
              onClick={handleDownloadPng}
              className="p-1 text-gray-400 hover:text-gray-600 rounded transition-colors"
              title="Download PNG"
            >
              <span className="text-[10px] font-medium">PNG</span>
            </button>
            <button
              onClick={() => setIsFullscreen(true)}
              className="p-1 text-gray-400 hover:text-gray-600 rounded transition-colors"
              title="Fullscreen"
            >
              <Maximize2 size={14} />
            </button>
          </div>
        </div>

        {/* Diagram */}
        {diagramView}
      </div>

      {/* Fullscreen overlay */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-white flex flex-col">
          <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200">
            <span className="text-sm font-medium text-gray-700">Mermaid Diagram</span>
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopySvg}
                className="p-1.5 text-gray-500 hover:text-gray-700 rounded transition-colors"
                title="Copy SVG"
              >
                <Copy size={16} />
              </button>
              <button
                onClick={handleDownloadSvg}
                className="p-1.5 text-gray-500 hover:text-gray-700 rounded transition-colors"
                title="Download SVG"
              >
                <Download size={16} />
              </button>
              <button
                onClick={() => setIsFullscreen(false)}
                className="p-1.5 text-gray-500 hover:text-gray-700 rounded transition-colors"
                title="Exit fullscreen"
              >
                <Minimize2 size={16} />
              </button>
            </div>
          </div>
          <div
            className="flex-1 overflow-auto p-8 flex items-center justify-center"
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        </div>
      )}
    </>
  )
}
