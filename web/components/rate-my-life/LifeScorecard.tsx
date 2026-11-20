'use client'

import { useMemo, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface LifeAuditScores {
  career: number
  financial: number
  physical: number
  mental: number
  relationships: number
  growth: number
  overall: number
}

interface AgentHighlight {
  agent_name: string
  dimension: string
  quote: string
  score: number
}

interface LifeScorecardProps {
  scores: LifeAuditScores
  highlights: AgentHighlight[]
  verdict: string | null
  shareToken?: string | null
}

const DIMENSIONS: { key: keyof Omit<LifeAuditScores, 'overall'>; label: string; shortLabel: string; icon: string }[] = [
  { key: 'career', label: 'Career & Growth', shortLabel: 'Career', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { key: 'financial', label: 'Financial Health', shortLabel: 'Financial', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  { key: 'physical', label: 'Physical Health', shortLabel: 'Physical', icon: 'M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z' },
  { key: 'mental', label: 'Mental Wellbeing', shortLabel: 'Mental', icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' },
  { key: 'relationships', label: 'Relationships', shortLabel: 'Relations', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z' },
  { key: 'growth', label: 'Personal Growth', shortLabel: 'Growth', icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' },
]

function scoreColor(score: number): string {
  if (score < 4) return '#ef4444'
  if (score <= 6) return '#f59e0b'
  return '#22c55e'
}

function scoreLabel(score: number): string {
  if (score < 4) return 'Needs Work'
  if (score <= 6) return 'Fair'
  if (score <= 8) return 'Good'
  return 'Excellent'
}

/** Strip [SCORES] blocks from verdict text */
function cleanVerdict(text: string): string {
  return text
    .replace(/\[SCORES?\][\s\S]*?(?=\n\n|\n(?=[A-Z#])|\s*$)/gi, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

// ── Radar Chart (pure SVG) ──────────────────────────────────────────────────

function RadarChart({ scores }: { scores: LifeAuditScores }) {
  // Wider viewBox to prevent label clipping
  const viewW = 380
  const viewH = 380
  const cx = viewW / 2
  const cy = viewH / 2
  const maxR = 110

  const dims = DIMENSIONS.map((d) => d.key)
  const angleStep = (2 * Math.PI) / dims.length
  const startAngle = -Math.PI / 2

  const getPoint = (index: number, value: number) => {
    const angle = startAngle + index * angleStep
    const r = (value / 10) * maxR
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) }
  }

  const rings = [2, 4, 6, 8, 10]

  const dataPoints = dims.map((d, i) => getPoint(i, scores[d]))
  const dataPath = dataPoints.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ') + 'Z'

  return (
    <svg aria-hidden="true" viewBox={`0 0 ${viewW} ${viewH}`} className="w-full max-w-[360px] mx-auto">
      <defs>
        <radialGradient id="radar-bg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fef2f2" />
          <stop offset="100%" stopColor="#fff7ed" />
        </radialGradient>
        <linearGradient id="radar-fill" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ff444f" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#e11d48" stopOpacity="0.15" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Background circle */}
      <circle cx={cx} cy={cy} r={maxR + 8} fill="url(#radar-bg)" />

      {/* Grid rings */}
      {rings.map((ring) => {
        const ringPoints = dims.map((_, i) => getPoint(i, ring))
        const ringPath = ringPoints.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ') + 'Z'
        return (
          <path
            key={ring}
            d={ringPath}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={ring === 10 ? 1.5 : 0.75}
            strokeDasharray={ring === 10 ? 'none' : '3 3'}
            opacity={ring === 10 ? 0.6 : 0.4}
          />
        )
      })}

      {/* Axis lines */}
      {dims.map((_, i) => {
        const endPoint = getPoint(i, 10)
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={endPoint.x}
            y2={endPoint.y}
            stroke="#d1d5db"
            strokeWidth={0.75}
            opacity={0.5}
          />
        )
      })}

      {/* Data polygon fill */}
      <path d={dataPath} fill="url(#radar-fill)" stroke="none" />

      {/* Data polygon stroke */}
      <path
        d={dataPath}
        fill="none"
        stroke="#ff444f"
        strokeWidth={2.5}
        strokeLinejoin="round"
        filter="url(#glow)"
        opacity={0.9}
      />

      {/* Data points with score numbers */}
      {dataPoints.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={5} fill="white" stroke="#ff444f" strokeWidth={2.5} />
          <circle cx={p.x} cy={p.y} r={2} fill="#ff444f" />
        </g>
      ))}

      {/* Labels -- positioned with more padding and full names */}
      {dims.map((d, i) => {
        const labelPoint = getPoint(i, 13)
        const isTop = i === 0
        const isBottom = i === 3
        const isLeft = i === 4 || i === 5
        let textAnchor: 'start' | 'middle' | 'end' = 'middle'
        if (!isTop && !isBottom) {
          textAnchor = isLeft ? 'end' : 'start'
        }

        const score = scores[d]
        const color = scoreColor(score)

        return (
          <g key={d}>
            {/* Dimension label */}
            <text
              x={labelPoint.x}
              y={labelPoint.y}
              textAnchor={textAnchor}
              dominantBaseline={isTop ? 'auto' : isBottom ? 'hanging' : 'middle'}
              className="fill-ink-soft"
              style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.01em' }}
            >
              {DIMENSIONS[i].shortLabel}
            </text>
            {/* Score below label */}
            <text
              x={labelPoint.x}
              y={labelPoint.y + (isTop ? -15 : isBottom ? 17 : 15)}
              textAnchor={textAnchor}
              dominantBaseline={isTop ? 'auto' : 'hanging'}
              style={{ fontSize: '12px', fontWeight: 800, fill: color }}
            >
              {score}/10
            </text>
          </g>
        )
      })}
    </svg>
  )
}

// ── Score Bar ────────────────────────────────────────────────────────────────

function ScoreBar({ dim, score }: { dim: (typeof DIMENSIONS)[number]; score: number }) {
  const color = scoreColor(score)
  const pct = (score / 10) * 100

  return (
    <div className="group">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: `${color}12` }}
          >
            <svg aria-hidden="true" className="w-4 h-4" style={{ color }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={dim.icon} />
            </svg>
          </div>
          <span className="text-[15px] font-semibold text-ink">{dim.label}</span>
        </div>
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-semibold" style={{ color }}>
            {scoreLabel(score)}
          </span>
          <span className="text-xl font-extrabold text-ink tabular-nums w-8 text-right">{score}</span>
        </div>
      </div>
      <div className="h-2.5 bg-sand rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-1000 ease-out"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${color}cc, ${color})`,
          }}
        />
      </div>
    </div>
  )
}

// ── Canvas Image Generator ───────────────────────────────────────────────────

function drawScorecardImage(scores: LifeAuditScores): HTMLCanvasElement {
  const W = 1200
  const H = 630
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!

  // Background
  const bgGrad = ctx.createLinearGradient(0, 0, W, H)
  bgGrad.addColorStop(0, '#fff5f5')
  bgGrad.addColorStop(1, '#ffffff')
  ctx.fillStyle = bgGrad
  ctx.fillRect(0, 0, W, H)

  // Subtle border
  ctx.strokeStyle = '#e5e7eb'
  ctx.lineWidth = 2
  ctx.strokeRect(1, 1, W - 2, H - 2)

  const color = (s: number) => s < 4 ? '#ef4444' : s <= 6 ? '#f59e0b' : '#22c55e'
  const label = (s: number) => s < 4 ? 'Needs Work' : s <= 6 ? 'Fair' : s <= 8 ? 'Good' : 'Excellent'

  // ── Left side: Score ──
  ctx.fillStyle = '#9ca3af'
  ctx.font = 'bold 14px system-ui, -apple-system, sans-serif'
  ctx.letterSpacing = '3px'
  ctx.fillText('YOUR LIFE SCORE', 60, 80)
  ctx.letterSpacing = '0px'

  ctx.fillStyle = color(scores.overall)
  ctx.font = 'bold 120px system-ui, -apple-system, sans-serif'
  ctx.fillText(`${scores.overall}`, 60, 210)
  const numW = ctx.measureText(`${scores.overall}`).width
  ctx.fillStyle = '#d1d5db'
  ctx.font = 'bold 40px system-ui, -apple-system, sans-serif'
  ctx.fillText('/10', 60 + numW + 4, 210)

  ctx.fillStyle = color(scores.overall)
  ctx.font = 'bold 20px system-ui, -apple-system, sans-serif'
  ctx.fillText(label(scores.overall), 60, 245)

  ctx.fillStyle = '#6b7280'
  ctx.font = '14px system-ui, -apple-system, sans-serif'
  ctx.fillText('Scored by 5 AI specialists across', 60, 285)
  ctx.fillText('6 life dimensions after a multi-round debate.', 60, 305)

  // ── Dimension bars (left bottom) ──
  const dims: { key: keyof Omit<LifeAuditScores, 'overall'>; label: string }[] = [
    { key: 'career', label: 'Career' },
    { key: 'financial', label: 'Financial' },
    { key: 'physical', label: 'Physical' },
    { key: 'mental', label: 'Mental' },
    { key: 'relationships', label: 'Relations' },
    { key: 'growth', label: 'Growth' },
  ]
  const barX = 60
  const barW = 400
  const barH = 12
  let barY = 350

  for (const dim of dims) {
    const s = scores[dim.key]
    const c = color(s)

    ctx.fillStyle = '#374151'
    ctx.font = 'bold 13px system-ui, -apple-system, sans-serif'
    ctx.fillText(dim.label, barX, barY)

    ctx.fillStyle = c
    ctx.font = 'bold 13px system-ui, -apple-system, sans-serif'
    ctx.textAlign = 'right'
    ctx.fillText(`${s}/10`, barX + barW, barY)
    ctx.textAlign = 'left'

    // Bar bg
    ctx.fillStyle = '#f3f4f6'
    ctx.beginPath()
    ctx.roundRect(barX, barY + 6, barW, barH, 6)
    ctx.fill()

    // Bar fill
    ctx.fillStyle = c
    ctx.beginPath()
    ctx.roundRect(barX, barY + 6, barW * (s / 10), barH, 6)
    ctx.fill()

    barY += 42
  }

  // ── Right side: Radar chart ──
  const cx = 880
  const cy = 310
  const maxR = 200
  const angleStep = (2 * Math.PI) / 6
  const startAngle = -Math.PI / 2

  const getPoint = (i: number, v: number) => ({
    x: cx + ((v / 10) * maxR) * Math.cos(startAngle + i * angleStep),
    y: cy + ((v / 10) * maxR) * Math.sin(startAngle + i * angleStep),
  })

  // Grid rings
  for (const ring of [2, 4, 6, 8, 10]) {
    ctx.beginPath()
    for (let i = 0; i < 6; i++) {
      const p = getPoint(i, ring)
      if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y)
    }
    ctx.closePath()
    ctx.strokeStyle = ring === 10 ? '#d1d5db' : '#e5e7eb'
    ctx.lineWidth = ring === 10 ? 1.5 : 0.75
    ctx.setLineDash(ring === 10 ? [] : [4, 4])
    ctx.stroke()
    ctx.setLineDash([])
  }

  // Axis lines
  for (let i = 0; i < 6; i++) {
    const p = getPoint(i, 10)
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.lineTo(p.x, p.y)
    ctx.strokeStyle = '#e5e7eb'
    ctx.lineWidth = 0.75
    ctx.stroke()
  }

  // Data polygon
  const dimKeys = dims.map(d => d.key)
  ctx.beginPath()
  for (let i = 0; i < 6; i++) {
    const p = getPoint(i, scores[dimKeys[i]])
    if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y)
  }
  ctx.closePath()
  ctx.fillStyle = 'rgba(255, 68, 79, 0.15)'
  ctx.fill()
  ctx.strokeStyle = '#ff444f'
  ctx.lineWidth = 3
  ctx.stroke()

  // Data points
  for (let i = 0; i < 6; i++) {
    const p = getPoint(i, scores[dimKeys[i]])
    ctx.beginPath()
    ctx.arc(p.x, p.y, 6, 0, Math.PI * 2)
    ctx.fillStyle = '#ffffff'
    ctx.fill()
    ctx.strokeStyle = '#ff444f'
    ctx.lineWidth = 3
    ctx.stroke()
  }

  // Labels
  for (let i = 0; i < 6; i++) {
    const lp = getPoint(i, 12.5)
    const isTop = i === 0
    const isBottom = i === 3
    const isLeft = i === 4 || i === 5

    ctx.font = 'bold 13px system-ui, -apple-system, sans-serif'
    ctx.fillStyle = '#374151'
    ctx.textAlign = isTop || isBottom ? 'center' : isLeft ? 'end' : 'start'
    ctx.textBaseline = isTop ? 'bottom' : isBottom ? 'top' : 'middle'
    ctx.fillText(dims[i].label, lp.x, lp.y)

    const s = scores[dimKeys[i]]
    ctx.fillStyle = color(s)
    ctx.font = 'bold 13px system-ui, -apple-system, sans-serif'
    ctx.fillText(`${s}/10`, lp.x, lp.y + (isTop ? -16 : 16))
  }

  // Reset
  ctx.textAlign = 'left'
  ctx.textBaseline = 'alphabetic'

  // Branding
  ctx.fillStyle = '#d1d5db'
  ctx.font = '12px system-ui, -apple-system, sans-serif'
  ctx.fillText('Rate My Life -- AI Life Audit', W - 240, H - 20)

  return canvas
}

// ── Share Actions ────────────────────────────────────────────────────────────

function ShareActions({ scores, shareToken }: { scores: LifeAuditScores; shareToken?: string | null }) {
  const [copied, setCopied] = useState(false)

  const handleCopyLink = useCallback(() => {
    if (!shareToken) return
    const url = `${window.location.origin}/war-room/${shareToken}/live`
    navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }, [shareToken])

  const handleDownload = useCallback(() => {
    const canvas = drawScorecardImage(scores)
    const link = document.createElement('a')
    link.download = `life-score-${scores.overall}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }, [scores])

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={handleDownload}
        className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-bold text-white bg-ink rounded-xl hover:bg-danger transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm"
      >
        <svg aria-hidden="true" className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        Download Image
      </button>
      {shareToken && (
        <button
          onClick={handleCopyLink}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-bold text-ink-soft bg-white border border-taupe rounded-xl hover:bg-cream hover:border-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm"
        >
          {copied ? (
            <>
              <svg aria-hidden="true" className="w-4 h-4 text-leaf" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-leaf">Link copied!</span>
            </>
          ) : (
            <>
              <svg aria-hidden="true" className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
              Copy Link
            </>
          )}
        </button>
      )}
    </div>
  )
}

// ── Verdict Markdown ────────────────────────────────────────────────────────

function VerdictContent({ text }: { text: string }) {
  const cleaned = useMemo(() => cleanVerdict(text), [text])

  return (
    <div className="verdict-markdown text-[15px] leading-[1.85] text-ink-soft">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h2 className="text-xl font-extrabold text-ink mt-7 mb-3 first:mt-0 pb-2 border-b border-line">{children}</h2>
          ),
          h2: ({ children }) => (
            <h3 className="text-lg font-bold text-ink mt-6 mb-2.5 first:mt-0">{children}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="text-base font-bold text-ink mt-5 mb-2 first:mt-0">{children}</h4>
          ),
          p: ({ children }) => (
            <p className="mb-3.5 last:mb-0">{children}</p>
          ),
          strong: ({ children }) => (
            <strong className="font-bold text-ink">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="text-ink-soft">{children}</em>
          ),
          ul: ({ children }) => (
            <ul className="space-y-1.5 mb-3.5 last:mb-0 ml-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="space-y-1.5 mb-3.5 last:mb-0 ml-1 list-decimal list-inside">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="flex gap-2.5 text-[15px]">
              <span className="text-warn mt-1 select-none flex-shrink-0">&#x25CF;</span>
              <span className="flex-1">{children}</span>
            </li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-[3px] border-honey pl-4 my-4 py-2 italic text-ink-soft bg-sand-deep/30 rounded-r-lg">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-6 border-line" />,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gold font-medium underline decoration-honey underline-offset-2 hover:decoration-warn transition-colors"
            >
              {children}
            </a>
          ),
          code: ({ children }: any) => (
            <code className="px-1.5 py-0.5 rounded text-[13px] font-mono bg-sand text-ink font-medium">
              {children}
            </code>
          ),
        }}
      >
        {cleaned}
      </ReactMarkdown>
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────────────────────

export function LifeScorecard({ scores, highlights, verdict, shareToken }: LifeScorecardProps) {
  const overallColor = useMemo(() => scoreColor(scores.overall), [scores.overall])
  const overallLabel = useMemo(() => scoreLabel(scores.overall), [scores.overall])

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Share + Download actions */}
      <div className="flex items-center justify-end">
        <ShareActions scores={scores} shareToken={shareToken} />
      </div>

      {/* Hero: Overall Score + Radar */}
      <div className="bg-white rounded-2xl border border-line shadow-sm overflow-hidden">
        <div className="bg-cream px-6 md:px-10 py-10">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
            {/* Overall Score */}
            <div className="text-center md:text-left">
              <p className="text-sm font-bold text-ash mb-3">
                Your Life Score
              </p>
              <div className="inline-flex items-baseline gap-1.5">
                <span
                  className="text-8xl font-black tabular-nums tracking-tighter leading-none"
                  style={{ color: overallColor }}
                >
                  {scores.overall}
                </span>
                <span className="text-3xl font-bold text-taupe">/10</span>
              </div>
              <p className="mt-3 text-base font-bold" style={{ color: overallColor }}>
                {overallLabel}
              </p>
              <p className="mt-3 text-sm text-ink-mute max-w-xs leading-relaxed">
                Scored by 5 AI specialists across 6 life dimensions after a multi-round debate.
              </p>
            </div>

            {/* Radar Chart */}
            <div className="flex justify-center">
              <RadarChart scores={scores} />
            </div>
          </div>
        </div>
      </div>

      {/* Dimension Breakdown */}
      <div className="bg-white rounded-2xl border border-line shadow-sm p-6 md:p-8">
        <h3 className="text-base font-bold text-ink mb-6">
          Dimension Breakdown
        </h3>
        <div className="space-y-6">
          {DIMENSIONS.map((dim) => (
            <ScoreBar key={dim.key} dim={dim} score={scores[dim.key]} />
          ))}
        </div>
      </div>

      {/* Agent Highlights */}
      {highlights.length > 0 && (
        <div className="bg-white rounded-2xl border border-line shadow-sm p-6 md:p-8">
          <h3 className="text-base font-bold text-ink mb-6">
            What the Specialists Said
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {highlights.map((h, i) => (
              <div
                key={i}
                className="relative p-5 rounded-xl bg-cream border border-sand"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-bold text-ink">{h.agent_name}</span>
                  <span
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold"
                    style={{
                      color: scoreColor(h.score),
                      backgroundColor: `${scoreColor(h.score)}15`,
                    }}
                  >
                    {h.dimension}: {h.score}/10
                  </span>
                </div>
                <p className="text-sm text-ink-soft leading-relaxed line-clamp-3">
                  &ldquo;{h.quote}&rdquo;
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Verdict */}
      {verdict && (
        <div className="bg-white rounded-2xl border border-line shadow-sm overflow-hidden">
          <div className="px-6 md:px-8 py-5 bg-sand-deep border-b border-sand-deep">
            <div className="flex items-center gap-2.5">
              <svg aria-hidden="true" className="w-5 h-5 text-warn" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"
                />
              </svg>
              <h3 className="text-base font-bold text-gold">The Synthesizer&apos;s Verdict</h3>
            </div>
          </div>
          <div className="px-6 md:px-8 py-6">
            <VerdictContent text={verdict} />
          </div>
        </div>
      )}
    </div>
  )
}
