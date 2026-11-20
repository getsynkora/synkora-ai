'use client'

import { useState } from 'react'
import { ZoomIn, ZoomOut, RotateCcw, Copy, Download, Maximize2, Minimize2, Check } from 'lucide-react'

interface DiagramToolbarProps {
  svgContent: string
  svgUrl?: string
  pngUrl?: string
  zoom: number
  onZoomIn: () => void
  onZoomOut: () => void
  onZoomReset: () => void
  isFullscreen: boolean
  onToggleFullscreen: () => void
}

export function DiagramToolbar({
  svgContent,
  svgUrl,
  pngUrl,
  zoom,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  isFullscreen,
  onToggleFullscreen,
}: DiagramToolbarProps) {
  const [copied, setCopied] = useState(false)

  const handleCopySvg = async () => {
    if (!svgContent) return
    await navigator.clipboard.writeText(svgContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownloadSvg = () => {
    if (svgUrl) {
      const a = document.createElement('a')
      a.href = svgUrl
      a.download = 'diagram.svg'
      a.click()
      return
    }
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
    if (pngUrl) {
      const a = document.createElement('a')
      a.href = pngUrl
      a.download = 'diagram.png'
      a.click()
      return
    }
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

      const pngDataUrl = canvas.toDataURL('image/png')
      const a = document.createElement('a')
      a.href = pngDataUrl
      a.download = 'diagram.png'
      a.click()
    }
    img.src = url
  }

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={onZoomOut}
        className="p-1 text-ash hover:text-ink-soft rounded transition-colors"
        title="Zoom out"
      >
        <ZoomOut size={14} />
      </button>
      <span className="text-[10px] text-ash min-w-[32px] text-center">
        {Math.round(zoom * 100)}%
      </span>
      <button
        onClick={onZoomIn}
        className="p-1 text-ash hover:text-ink-soft rounded transition-colors"
        title="Zoom in"
      >
        <ZoomIn size={14} />
      </button>
      <button
        onClick={onZoomReset}
        className="p-1 text-ash hover:text-ink-soft rounded transition-colors"
        title="Reset zoom"
      >
        <RotateCcw size={14} />
      </button>
      <div className="w-px h-4 bg-line mx-1" />
      <button
        onClick={handleCopySvg}
        className="p-1 text-ash hover:text-ink-soft rounded transition-colors"
        title="Copy SVG"
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>
      <button
        onClick={handleDownloadSvg}
        className="p-1 text-ash hover:text-ink-soft rounded transition-colors"
        title="Download SVG"
      >
        <Download size={14} />
      </button>
      <button
        onClick={handleDownloadPng}
        className="p-1 text-ash hover:text-ink-soft rounded transition-colors"
        title="Download PNG"
      >
        <span className="text-[10px] font-medium">PNG</span>
      </button>
      <button
        onClick={onToggleFullscreen}
        className="p-1 text-ash hover:text-ink-soft rounded transition-colors"
        title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
      >
        {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
      </button>
    </div>
  )
}
