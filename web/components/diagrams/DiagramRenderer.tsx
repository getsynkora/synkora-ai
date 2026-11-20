'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import DOMPurify from 'dompurify'
import { DiagramToolbar } from './DiagramToolbar'

export interface DiagramData {
  id?: string
  title: string
  description?: string
  diagram_type: string
  style?: number
  svg_url?: string
  svg_content?: string
  png_url?: string
  spec?: object
  created_at?: string
}

interface DiagramRendererProps {
  diagram: DiagramData
}

export function DiagramRenderer({ diagram }: DiagramRendererProps) {
  const [svgContent, setSvgContent] = useState(diagram.svg_content || '')
  const [loading, setLoading] = useState(!diagram.svg_content && !!diagram.svg_url)
  const [error, setError] = useState('')
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState({ x: 0, y: 0 })
  const [isFullscreen, setIsFullscreen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Fetch SVG from URL if no inline content
  useEffect(() => {
    if (diagram.svg_content) {
      setSvgContent(diagram.svg_content)
      return
    }
    if (!diagram.svg_url) return

    let cancelled = false
    setLoading(true)
    fetch(diagram.svg_url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.text()
      })
      .then((text) => {
        if (!cancelled) {
          setSvgContent(text)
          setError('')
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [diagram.svg_url, diagram.svg_content])

  // Zoom handlers
  const handleZoomIn = useCallback(() => setZoom((z) => Math.min(z + 0.25, 4)), [])
  const handleZoomOut = useCallback(() => setZoom((z) => Math.max(z - 0.25, 0.25)), [])
  const handleZoomReset = useCallback(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }, [])

  // Scroll wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? -0.1 : 0.1
    setZoom((z) => Math.max(0.25, Math.min(4, z + delta)))
  }, [])

  // Pan handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    setIsPanning(true)
    setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }, [pan])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return
    setPan({ x: e.clientX - panStart.x, y: e.clientY - panStart.y })
  }, [isPanning, panStart])

  const handleMouseUp = useCallback(() => setIsPanning(false), [])

  // Sanitize SVG with DOMPurify to prevent XSS (scripts, event handlers, javascript: hrefs, etc.)
  const sanitizedSvg = typeof window !== 'undefined'
    ? DOMPurify.sanitize(svgContent, {
        USE_PROFILES: { svg: true, svgFilters: true },
        ADD_TAGS: ['use'],
        FORBID_ATTR: ['xlink:href'],
      })
    : svgContent

  if (loading) {
    return (
      <div className="my-3 rounded-lg border border-line overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-cream border-b border-line">
          <span className="text-xs text-ink-mute font-medium">{diagram.title || 'Diagram'}</span>
        </div>
        <div className="flex items-center justify-center h-48 bg-white">
          <div className="flex items-center gap-2 text-sm text-ink-mute">
            <div className="w-4 h-4 border-2 border-ash border-t-transparent rounded-full motion-safe:animate-spin" />
            Loading diagram...
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="my-3 rounded-lg border border-blush overflow-hidden">
        <div className="px-3 py-2 bg-blush-wash text-sm text-danger">
          Failed to load diagram: {error}
        </div>
        {diagram.svg_url && (
          <div className="px-3 py-2 text-xs">
            <button
              onClick={() => {
                setError('')
                setLoading(true)
                fetch(diagram.svg_url!)
                  .then((r) => r.text())
                  .then(setSvgContent)
                  .catch((e) => setError(e.message))
                  .finally(() => setLoading(false))
              }}
              className="text-azure hover:underline"
            >
              Retry
            </button>
          </div>
        )}
      </div>
    )
  }

  if (!sanitizedSvg) return null

  const diagramContent = (
    <div
      ref={containerRef}
      className="overflow-hidden bg-white cursor-grab active:cursor-grabbing"
      style={{ maxHeight: isFullscreen ? undefined : 500 }}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <div
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: 'center center',
          transition: isPanning ? 'none' : 'transform 0.15s ease',
        }}
        className="p-4"
        dangerouslySetInnerHTML={{ __html: sanitizedSvg }}
      />
    </div>
  )

  return (
    <>
      <div className="my-3 -mx-2 rounded-lg border border-line overflow-hidden">
        {/* Toolbar header */}
        <div className="flex items-center justify-between px-3 py-1.5 bg-cream border-b border-line">
          <span className="text-xs text-ink-mute font-medium truncate max-w-[200px]">
            {diagram.title || 'Diagram'}
          </span>
          <DiagramToolbar
            svgContent={sanitizedSvg}
            svgUrl={diagram.svg_url}
            pngUrl={diagram.png_url}
            zoom={zoom}
            onZoomIn={handleZoomIn}
            onZoomOut={handleZoomOut}
            onZoomReset={handleZoomReset}
            isFullscreen={false}
            onToggleFullscreen={() => setIsFullscreen(true)}
          />
        </div>

        {diagramContent}

        {/* Description */}
        {diagram.description && (
          <div className="px-3 py-1.5 bg-cream border-t border-line text-xs text-ink-mute">
            {diagram.description}
          </div>
        )}
      </div>

      {/* Fullscreen overlay */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-white flex flex-col">
          <div className="flex items-center justify-between px-4 py-2 border-b border-line">
            <span className="text-sm font-medium text-ink-soft">{diagram.title || 'Diagram'}</span>
            <div className="flex items-center gap-2">
              <DiagramToolbar
                svgContent={sanitizedSvg}
                svgUrl={diagram.svg_url}
                pngUrl={diagram.png_url}
                zoom={zoom}
                onZoomIn={handleZoomIn}
                onZoomOut={handleZoomOut}
                onZoomReset={handleZoomReset}
                isFullscreen={true}
                onToggleFullscreen={() => setIsFullscreen(false)}
              />
            </div>
          </div>
          <div
            className="flex-1 overflow-hidden cursor-grab active:cursor-grabbing"
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <div
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                transformOrigin: 'center center',
                transition: isPanning ? 'none' : 'transform 0.15s ease',
              }}
              className="p-8 flex items-center justify-center min-h-full"
              dangerouslySetInnerHTML={{ __html: sanitizedSvg }}
            />
          </div>
        </div>
      )}
    </>
  )
}
