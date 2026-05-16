'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { getWikiGraph } from '@/lib/api/knowledge-autopilot'
import type { WikiGraphData } from '@/lib/api/knowledge-autopilot'

const CATEGORY_COLORS: Record<string, { fill: string; glow: string }> = {
  projects:     { fill: '#3b82f6', glow: 'rgba(59, 130, 246, 0.5)' },
  people:       { fill: '#a855f7', glow: 'rgba(168, 85, 247, 0.5)' },
  decisions:    { fill: '#f59e0b', glow: 'rgba(245, 158, 11, 0.5)' },
  processes:    { fill: '#10b981', glow: 'rgba(16, 185, 129, 0.5)' },
  architecture: { fill: '#06b6d4', glow: 'rgba(6, 182, 212, 0.5)' },
  general:      { fill: '#6b7280', glow: 'rgba(107, 114, 128, 0.4)' },
}

interface WikiGraphProps {
  kbId: string
}

interface NodePosition {
  id: string
  title: string
  slug: string
  category: string
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  connections: number
  opacity: number   // entrance fade-in [0..1]
  phase: number     // idle float phase offset (random per node)
  floatAmpX: number
  floatAmpY: number
}

interface Transform {
  x: number
  y: number
  scale: number
}

export function WikiGraph({ kbId }: WikiGraphProps) {
  const router = useRouter()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [graphData, setGraphData] = useState<WikiGraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const nodesRef = useRef<NodePosition[]>([])
  const animRef = useRef<number>(0)
  const timeRef = useRef(0)
  const hoveredRef = useRef<string | null>(null)

  // Zoom / pan
  const transformRef = useRef<Transform>({ x: 0, y: 0, scale: 1 })
  const isDraggingRef = useRef(false)
  const hasDraggedRef = useRef(false)
  const dragStartRef = useRef({ x: 0, y: 0, tx: 0, ty: 0 })

  useEffect(() => { hoveredRef.current = hoveredNode }, [hoveredNode])

  useEffect(() => {
    getWikiGraph(kbId)
      .then((data) => setGraphData(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [kbId])

  const initSimulation = useCallback(() => {
    if (!graphData || !canvasRef.current || !containerRef.current) return

    const canvas = canvasRef.current
    const container = containerRef.current
    const width = container.clientWidth
    const height = container.clientHeight
    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`

    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.scale(dpr, dpr)

    const centerX = width / 2
    const centerY = height / 2

    // Count connections for node sizing
    const connectionCount = new Map<string, number>()
    for (const link of graphData.links) {
      connectionCount.set(link.source, (connectionCount.get(link.source) || 0) + 1)
      connectionCount.set(link.target, (connectionCount.get(link.target) || 0) + 1)
    }

    // Spawn nodes clustered at center — they explode outward via physics
    nodesRef.current = graphData.nodes.map((node) => {
      const connections = connectionCount.get(node.id) || 0
      const angle = Math.random() * 2 * Math.PI
      const dist = Math.random() * 60
      return {
        ...node,
        x: centerX + dist * Math.cos(angle),
        y: centerY + dist * Math.sin(angle),
        vx: (Math.random() - 0.5) * 4,
        vy: (Math.random() - 0.5) * 4,
        radius: Math.max(4, Math.min(14, 4 + connections * 2)),
        connections,
        opacity: 0,
        phase: Math.random() * Math.PI * 2,
        floatAmpX: 0.25 + Math.random() * 0.35,
        floatAmpY: 0.25 + Math.random() * 0.35,
      }
    })

    const nodeMap = new Map(nodesRef.current.map((n) => [n.id, n]))

    // Per-link ambient particle state
    const particleT = graphData.links.map(() => Math.random())
    const particleSpeed = graphData.links.map(() => 0.003 + Math.random() * 0.004)

    let iteration = 0

    const tick = () => {
      iteration++
      timeRef.current = iteration
      const alpha = Math.max(0.002, 1 - iteration / 500)
      const isSettled = iteration > 500
      const nodes = nodesRef.current
      const hovered = hoveredRef.current
      const transform = transformRef.current

      // --- Entrance fade-in (first ~60 frames) ---
      for (const node of nodes) {
        if (node.opacity < 1) node.opacity = Math.min(1, node.opacity + 0.025)
      }

      // --- Physics (only while settling) ---
      if (!isSettled) {
        // Repulsion
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const dx = nodes[j].x - nodes[i].x
            const dy = nodes[j].y - nodes[i].y
            const dist = Math.sqrt(dx * dx + dy * dy) || 1
            const minDist = nodes[i].radius + nodes[j].radius + 40
            const force = ((minDist * 3) * alpha) / (dist * dist)
            const fx = (dx / dist) * force
            const fy = (dy / dist) * force
            nodes[i].vx -= fx; nodes[i].vy -= fy
            nodes[j].vx += fx; nodes[j].vy += fy
          }
        }

        // Link spring attraction
        for (const link of graphData.links) {
          const src = nodeMap.get(link.source)
          const tgt = nodeMap.get(link.target)
          if (!src || !tgt) continue
          const dx = tgt.x - src.x
          const dy = tgt.y - src.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = (dist - 120) * 0.008 * alpha
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          src.vx += fx; src.vy += fy
          tgt.vx -= fx; tgt.vy -= fy
        }

        // Center gravity + damping
        for (const node of nodes) {
          node.vx += (centerX - node.x) * 0.003 * alpha
          node.vy += (centerY - node.y) * 0.003 * alpha
          node.vx *= 0.85
          node.vy *= 0.85
          node.x += node.vx
          node.y += node.vy
          node.x = Math.max(40, Math.min(width - 40, node.x))
          node.y = Math.max(40, Math.min(height - 40, node.y))
        }
      } else {
        // Idle float — continuous gentle sinusoidal drift so graph never goes static
        for (const node of nodes) {
          node.x += Math.sin(iteration * 0.008 + node.phase) * node.floatAmpX
          node.y += Math.cos(iteration * 0.006 + node.phase * 1.3) * node.floatAmpY
        }
      }

      // Advance ambient particles
      for (let i = 0; i < particleT.length; i++) {
        particleT[i] += particleSpeed[i]
        if (particleT[i] > 1) particleT[i] -= 1
      }

      // --- RENDER ---
      ctx.save()

      // Background gradient
      const bgGrad = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, Math.max(width, height) * 0.7)
      bgGrad.addColorStop(0, '#111827')
      bgGrad.addColorStop(1, '#0a0e1a')
      ctx.fillStyle = bgGrad
      ctx.fillRect(0, 0, width, height)

      // Dot grid
      ctx.fillStyle = 'rgba(255,255,255,0.03)'
      for (let gx = 0; gx < width; gx += 30)
        for (let gy = 0; gy < height; gy += 30)
          ctx.fillRect(gx, gy, 1, 1)

      // Apply zoom/pan
      ctx.translate(transform.x, transform.y)
      ctx.scale(transform.scale, transform.scale)

      // Determine hover-highlighted sets
      const highlightLinks = new Set<string>()
      const highlightNodes = new Set<string>()
      if (hovered) {
        highlightNodes.add(hovered)
        for (const link of graphData.links) {
          if (link.source === hovered || link.target === hovered) {
            highlightLinks.add(`${link.source}-${link.target}`)
            highlightNodes.add(link.source)
            highlightNodes.add(link.target)
          }
        }
      }

      // --- Links + particles ---
      for (let li = 0; li < graphData.links.length; li++) {
        const link = graphData.links[li]
        const src = nodeMap.get(link.source)
        const tgt = nodeMap.get(link.target)
        if (!src || !tgt) continue

        const linkKey = `${link.source}-${link.target}`
        const isHighlighted = highlightLinks.has(linkKey)
        const isDimmed = hovered !== null && !isHighlighted
        const entryOpacity = Math.min(src.opacity, tgt.opacity)

        // Curve control point
        const mx = (src.x + tgt.x) / 2
        const my = (src.y + tgt.y) / 2
        const dx = tgt.x - src.x
        const dy = tgt.y - src.y
        const len = Math.sqrt(dx * dx + dy * dy) || 1
        const offset = Math.min(20, len * 0.08)
        const cx = mx - dy * offset / len
        const cy = my + dx * offset / len

        // Link line
        ctx.beginPath()
        ctx.moveTo(src.x, src.y)
        ctx.quadraticCurveTo(cx, cy, tgt.x, tgt.y)

        if (isHighlighted) {
          const col = CATEGORY_COLORS[src.category] || CATEGORY_COLORS.general
          ctx.strokeStyle = col.fill + 'a0'
          ctx.lineWidth = 1.5
        } else {
          const a = (isDimmed ? 0.02 : 0.08) * entryOpacity
          ctx.strokeStyle = `rgba(255,255,255,${a})`
          ctx.lineWidth = 0.5
        }
        ctx.stroke()

        // Ambient particle travelling the link
        if (!isDimmed) {
          const col = CATEGORY_COLORS[src.category] || CATEGORY_COLORS.general

          if (isHighlighted) {
            // Fast bright particle on hover-highlighted link
            const tH = ((iteration * 0.015) % 1)
            const px = (1 - tH) * (1 - tH) * src.x + 2 * (1 - tH) * tH * cx + tH * tH * tgt.x
            const py = (1 - tH) * (1 - tH) * src.y + 2 * (1 - tH) * tH * cy + tH * tH * tgt.y
            ctx.beginPath()
            ctx.arc(px, py, 2.5, 0, 2 * Math.PI)
            ctx.fillStyle = col.fill
            ctx.fill()
          } else {
            // Slow dim ambient particle on every link
            const t = particleT[li]
            const px = (1 - t) * (1 - t) * src.x + 2 * (1 - t) * t * cx + t * t * tgt.x
            const py = (1 - t) * (1 - t) * src.y + 2 * (1 - t) * t * cy + t * t * tgt.y
            const ambientAlpha = Math.round(entryOpacity * 55).toString(16).padStart(2, '0')
            ctx.beginPath()
            ctx.arc(px, py, 1.2, 0, 2 * Math.PI)
            ctx.fillStyle = col.fill + ambientAlpha
            ctx.fill()
          }
        }
      }

      // --- Nodes ---
      for (const node of nodes) {
        const col = CATEGORY_COLORS[node.category] || CATEGORY_COLORS.general
        const isHovered = hovered === node.id
        const isConnected = highlightNodes.has(node.id)
        const isDimmed = hovered !== null && !isConnected
        const r = isHovered ? node.radius * 1.4 : node.radius

        ctx.globalAlpha = node.opacity * (isDimmed ? 0.2 : 1)

        // Outer glow
        if (isHovered || isConnected) {
          const glowR = r + (isHovered ? 22 : 10)
          const glow = ctx.createRadialGradient(node.x, node.y, r, node.x, node.y, glowR)
          glow.addColorStop(0, col.glow)
          glow.addColorStop(1, 'rgba(0,0,0,0)')
          ctx.beginPath()
          ctx.arc(node.x, node.y, glowR, 0, 2 * Math.PI)
          ctx.fillStyle = glow
          ctx.fill()
        }

        // Dual concentric pulse rings on hover
        if (isHovered) {
          for (let ring = 0; ring < 2; ring++) {
            const phase = ((iteration * 0.05) + ring * 0.5) % 1
            const pulseR = r + 8 + phase * 20
            const pulseAlpha = Math.round((1 - phase) * (ring === 0 ? 180 : 100))
              .toString(16).padStart(2, '0')
            ctx.beginPath()
            ctx.arc(node.x, node.y, pulseR, 0, 2 * Math.PI)
            ctx.strokeStyle = col.fill + pulseAlpha
            ctx.lineWidth = ring === 0 ? 1.5 : 1
            ctx.stroke()
          }
        }

        // Node fill with radial gradient
        const nodeGrad = ctx.createRadialGradient(node.x - r * 0.3, node.y - r * 0.3, 0, node.x, node.y, r)
        nodeGrad.addColorStop(0, col.fill)
        nodeGrad.addColorStop(1, col.fill + 'cc')
        ctx.beginPath()
        ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
        ctx.fillStyle = isDimmed ? 'rgba(75,85,99,0.3)' : nodeGrad
        ctx.fill()

        // Glass inner highlight
        if (!isDimmed) {
          ctx.beginPath()
          ctx.arc(node.x - r * 0.2, node.y - r * 0.2, r * 0.5, 0, 2 * Math.PI)
          ctx.fillStyle = 'rgba(255,255,255,0.15)'
          ctx.fill()
        }

        ctx.globalAlpha = 1

        // Labels
        if (isHovered || isConnected || nodes.length < 25) {
          const label = node.title.length > 25 ? node.title.slice(0, 25) + '…' : node.title
          const labelAlpha = node.opacity * (isDimmed ? 0.2 : isHovered ? 1 : 0.8)
          ctx.globalAlpha = labelAlpha
          ctx.font = isHovered ? 'bold 12px Inter, system-ui, sans-serif' : '10px Inter, system-ui, sans-serif'
          ctx.textAlign = 'center'

          ctx.fillStyle = 'rgba(0,0,0,0.6)'
          ctx.fillText(label, node.x + 1, node.y + r + 15)
          ctx.fillStyle = isDimmed ? 'rgba(156,163,175,0.3)' : isHovered ? '#ffffff' : 'rgba(209,213,219,0.8)'
          ctx.fillText(label, node.x, node.y + r + 14)

          if (isHovered && node.connections > 0) {
            ctx.font = '9px Inter, system-ui, sans-serif'
            ctx.fillStyle = 'rgba(156,163,175,0.6)'
            ctx.fillText(`${node.connections} connections`, node.x, node.y + r + 27)
          }
          ctx.globalAlpha = 1
        }
      }

      ctx.restore()
      animRef.current = requestAnimationFrame(tick)
    }

    animRef.current = requestAnimationFrame(tick)
  }, [graphData])

  useEffect(() => {
    initSimulation()
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [initSimulation])

  useEffect(() => {
    const handleResize = () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
      initSimulation()
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [initSimulation])

  // Zoom via scroll wheel
  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    const transform = transformRef.current
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const factor = e.deltaY < 0 ? 1.1 : 0.9
    const newScale = Math.max(0.25, Math.min(5, transform.scale * factor))
    const ratio = newScale / transform.scale
    transformRef.current = {
      x: mx - ratio * (mx - transform.x),
      y: my - ratio * (my - transform.y),
      scale: newScale,
    }
  }, [])

  // Pan via drag
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = true
    hasDraggedRef.current = false
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      tx: transformRef.current.x,
      ty: transformRef.current.y,
    }
  }, [])

  const handleMouseUp = useCallback(() => {
    isDraggingRef.current = false
  }, [])

  // Translate mouse position into graph-space coordinates (accounting for zoom/pan)
  const toGraphCoords = useCallback((clientX: number, clientY: number) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const rect = canvas.getBoundingClientRect()
    const t = transformRef.current
    return {
      x: (clientX - rect.left - t.x) / t.scale,
      y: (clientY - rect.top - t.y) / t.scale,
    }
  }, [])

  const handleCanvasClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (hasDraggedRef.current) return
      const { x, y } = toGraphCoords(e.clientX, e.clientY)
      for (const node of nodesRef.current) {
        const dx = node.x - x
        const dy = node.y - y
        if (dx * dx + dy * dy < (node.radius + 5) * (node.radius + 5)) {
          router.push(`/knowledge-bases/${kbId}/wiki/${node.slug}`)
          return
        }
      }
    },
    [kbId, router, toGraphCoords],
  )

  const handleCanvasMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (isDraggingRef.current) {
        const dx = e.clientX - dragStartRef.current.x
        const dy = e.clientY - dragStartRef.current.y
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasDraggedRef.current = true
        transformRef.current = {
          ...transformRef.current,
          x: dragStartRef.current.tx + dx,
          y: dragStartRef.current.ty + dy,
        }
        return
      }

      const { x, y } = toGraphCoords(e.clientX, e.clientY)
      let found: string | null = null
      for (const node of nodesRef.current) {
        const dx = node.x - x
        const dy = node.y - y
        if (dx * dx + dy * dy < (node.radius + 8) * (node.radius + 8)) {
          found = node.id
          break
        }
      }
      if (found !== hoveredNode) setHoveredNode(found)
    },
    [hoveredNode, toGraphCoords],
  )

  if (loading) {
    return (
      <div className="flex h-full min-h-[32rem] items-center justify-center bg-gray-900">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-[3px] border-gray-700 border-b-primary-500 rounded-full animate-spin" />
          <span className="text-xs font-bold text-gray-500">Loading graph...</span>
        </div>
      </div>
    )
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex h-full min-h-[32rem] flex-col items-center justify-center gap-3 bg-gray-900">
        <div className="w-16 h-16 rounded-2xl bg-gray-800 flex items-center justify-center border border-gray-700">
          <svg className="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
        </div>
        <p className="text-sm font-bold text-gray-500">No articles to visualize yet</p>
        <p className="text-xs text-gray-600">Compile your knowledge base first</p>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative h-full min-h-[32rem] w-full select-none">
      <canvas
        ref={canvasRef}
        onClick={handleCanvasClick}
        onMouseMove={handleCanvasMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        className={hoveredNode ? 'h-full w-full cursor-pointer' : 'h-full w-full cursor-grab active:cursor-grabbing'}
      />

      {/* Zoom/pan hint — fades out after a moment */}
      <div className="absolute top-4 left-4 text-[10px] font-semibold text-gray-600 bg-gray-900/80 px-3 py-1.5 rounded-lg border border-gray-800 pointer-events-none">
        Scroll to zoom · Drag to pan
      </div>

      {/* Category legend */}
      <div className="absolute bottom-4 left-4 flex flex-wrap gap-3 bg-gray-900/90 backdrop-blur-md rounded-xl px-5 py-3 border border-gray-700/50">
        {Object.entries(CATEGORY_COLORS).map(([cat, colors]) => (
          <div key={cat} className="flex items-center gap-1.5">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: colors.fill, boxShadow: `0 0 6px ${colors.glow}` }}
            />
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">{cat}</span>
          </div>
        ))}
      </div>

      {/* Stats */}
      <div className="absolute top-4 right-4 bg-gray-900/90 backdrop-blur-md rounded-xl px-5 py-3 border border-gray-700/50">
        <div className="flex items-center gap-5 text-xs text-gray-400">
          <span><span className="text-white font-extrabold">{graphData.nodes.length}</span> <span className="font-semibold">articles</span></span>
          <span><span className="text-white font-extrabold">{graphData.links.length}</span> <span className="font-semibold">connections</span></span>
        </div>
      </div>
    </div>
  )
}
