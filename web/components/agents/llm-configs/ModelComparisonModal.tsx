'use client'

import { useState, useEffect, useCallback } from 'react'
import { X, Search, ChevronDown, Zap, Clock, DollarSign, Star, Globe } from 'lucide-react'
import {
  getModelComparison,
  ComparisonModelItem,
  ComparisonFilter,
  ComparisonSortBy,
} from '@/lib/api/llm-providers'

interface ModelComparisonModalProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (providerId: string, modelName: string, modelDisplayName: string) => void
}

const PROVIDER_COLORS: Record<string, string> = {
  openai: 'bg-leaf-wash text-forest',
  anthropic: 'bg-sand-deep text-gold',
  gemini: 'bg-sky-wash text-azure',
  google: 'bg-sky-wash text-azure',
  deepseek: 'bg-sky-wash text-azure',
  ollama: 'bg-blush-wash text-wine',
  huggingface: 'bg-sand-deep text-gold',
  together_ai: 'bg-sky-wash text-azure',
  vllm: 'bg-blush-wash text-wine',
  lm_studio: 'bg-blush-wash text-wine',
  litellm: 'bg-leaf-wash text-forest',
  openrouter: 'bg-sand text-ink',
}

const SPEED_CONFIG = {
  fast: { label: 'Fast', class: 'bg-leaf-wash text-forest' },
  medium: { label: 'Medium', class: 'bg-sand-deep text-gold' },
  slow: { label: 'Slow', class: 'bg-blush-wash text-leaf' },
}

const FILTER_TABS: { key: ComparisonFilter; label: string; icon: React.ReactNode }[] = [
  { key: undefined, label: 'All Models', icon: null },
  { key: 'quality', label: 'Best Quality', icon: <Star className="w-3.5 h-3.5" /> },
  { key: 'fast', label: 'Fastest', icon: <Zap className="w-3.5 h-3.5" /> },
  { key: 'cheap', label: 'Cheapest', icon: <DollarSign className="w-3.5 h-3.5" /> },
  { key: 'open_source', label: 'Open Source', icon: <Globe className="w-3.5 h-3.5" /> },
]

const SORT_OPTIONS: { key: ComparisonSortBy; label: string }[] = [
  { key: 'quality', label: 'Quality Score' },
  { key: 'cost', label: 'Lowest Cost' },
  { key: 'speed', label: 'Fastest First' },
]

function QualityBar({ score }: { score: number | null }) {
  if (score === null) {
    return <span className="text-xs text-ash">N/A</span>
  }
  const pct = (score / 10) * 100
  const color = score >= 9 ? 'bg-leaf' : score >= 8 ? 'bg-warn' : 'bg-ash'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-sand rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-ink-soft w-6 text-right">{score.toFixed(1)}</span>
    </div>
  )
}

function CostDisplay({ item }: { item: ComparisonModelItem }) {
  if (item.cost_input_per_1m === null) {
    return <span className="text-xs text-ash">N/A</span>
  }
  if (item.is_open_source && item.cost_input_per_1m === 0) {
    return <span className="text-xs font-medium text-leaf">Free (local)</span>
  }
  return (
    <span className="text-xs text-ink-soft">
      ${item.cost_input_per_1m}/
      <span className="text-ink-mute">${item.cost_output_per_1m}</span>
      <span className="text-ash"> /1M</span>
    </span>
  )
}

function ModelCard({
  item,
  onSelect,
}: {
  item: ComparisonModelItem
  onSelect: (item: ComparisonModelItem) => void
}) {
  const providerColor =
    PROVIDER_COLORS[item.provider_id] || 'bg-sand text-ink-soft'
  const speedCfg = item.speed_tier ? SPEED_CONFIG[item.speed_tier] : null
  const contextK = item.max_input_tokens
    ? `${Math.round(item.max_input_tokens / 1000)}k ctx`
    : null

  return (
    <div className="bg-white border border-line rounded-xl p-4 flex flex-col gap-3 hover:border-taupe hover:shadow-sm transition-[color,background-color,border-color,box-shadow,opacity,transform]">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-ink text-sm leading-snug truncate">
            {item.name}
          </p>
          <p className="text-xs text-ink-mute mt-0.5 line-clamp-2">{item.description}</p>
        </div>
        <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${providerColor}`}>
          {item.provider_name}
        </span>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        {/* Quality */}
        <div>
          <p className="text-ash mb-1">Quality</p>
          <QualityBar score={item.quality_score} />
        </div>

        {/* Speed */}
        <div>
          <p className="text-ash mb-1">Speed</p>
          {speedCfg ? (
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${speedCfg.class}`}>
              {item.speed_tier === 'fast' && <Zap className="w-3 h-3" />}
              {item.speed_tier === 'slow' && <Clock className="w-3 h-3" />}
              {speedCfg.label}
            </span>
          ) : (
            <span className="text-ash">N/A</span>
          )}
        </div>

        {/* Cost */}
        <div>
          <p className="text-ash mb-1">Cost (in/out)</p>
          <CostDisplay item={item} />
        </div>

        {/* Context */}
        <div>
          <p className="text-ash mb-1">Context</p>
          <span className="text-xs text-ink-soft">{contextK || 'N/A'}</span>
        </div>
      </div>

      {/* Tags */}
      {item.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {item.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="px-1.5 py-0.5 bg-sand text-ink-mute text-xs rounded"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Select button */}
      <button
        onClick={() => onSelect(item)}
        className="mt-auto w-full py-2 bg-danger hover:bg-danger text-white text-sm font-medium rounded-lg transition-colors"
      >
        Select
      </button>
    </div>
  )
}

export default function ModelComparisonModal({
  isOpen,
  onClose,
  onSelect,
}: ModelComparisonModalProps) {
  const [activeFilter, setActiveFilter] = useState<ComparisonFilter>(undefined)
  const [sortBy, setSortBy] = useState<ComparisonSortBy>('quality')
  const [search, setSearch] = useState('')
  const [models, setModels] = useState<ComparisonModelItem[]>([])
  const [loading, setLoading] = useState(false)
  const [sortOpen, setSortOpen] = useState(false)

  const loadModels = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getModelComparison(activeFilter, sortBy)
      setModels(data)
    } catch (err) {
      console.error('Failed to load model comparison data', err)
    } finally {
      setLoading(false)
    }
  }, [activeFilter, sortBy])

  useEffect(() => {
    if (isOpen) {
      loadModels()
    }
  }, [isOpen, loadModels])

  // Reset search when filter changes
  useEffect(() => {
    setSearch('')
  }, [activeFilter])

  const filtered = search.trim()
    ? models.filter(
        (m) =>
          m.name.toLowerCase().includes(search.toLowerCase()) ||
          m.model_name.toLowerCase().includes(search.toLowerCase()) ||
          m.provider_name.toLowerCase().includes(search.toLowerCase())
      )
    : models

  const handleSelect = (item: ComparisonModelItem) => {
    onSelect(item.provider_id, item.model_name, item.name)
    onClose()
  }

  const activeSortLabel = SORT_OPTIONS.find((o) => o.key === sortBy)?.label ?? 'Quality Score'

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-cream rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-line">
          <div>
            <h2 className="text-lg font-semibold text-ink">Choose a Model</h2>
            <p className="text-xs text-ink-mute mt-0.5">
              Compare models by quality, speed, cost, and open-source availability
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-ash hover:text-ink-soft hover:bg-sand rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Controls */}
        <div className="px-6 py-3 bg-white border-b border-line flex flex-wrap items-center gap-3">
          {/* Filter tabs */}
          <div className="flex items-center gap-1 flex-wrap">
            {FILTER_TABS.map((tab) => (
              <button
                key={String(tab.key)}
                onClick={() => setActiveFilter(tab.key)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  activeFilter === tab.key
                    ? 'bg-danger text-white'
                    : 'bg-sand text-ink-soft hover:bg-line'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ash" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search models…"
              className="pl-9 pr-4 py-1.5 border border-taupe rounded-lg text-sm focus:ring-2 focus:ring-ink focus:border-transparent w-48"
            />
          </div>

          {/* Sort dropdown */}
          <div className="relative">
            <button
              onClick={() => setSortOpen((v) => !v)}
              className="inline-flex items-center gap-2 px-3 py-1.5 border border-taupe rounded-lg text-sm text-ink-soft hover:bg-cream transition-colors"
            >
              {activeSortLabel}
              <ChevronDown className="w-4 h-4 text-ash" />
            </button>
            {sortOpen && (
              <div className="absolute right-0 top-full mt-1 w-44 bg-white border border-line rounded-lg shadow-lg z-10 overflow-hidden">
                {SORT_OPTIONS.map((opt) => (
                  <button
                    key={opt.key}
                    onClick={() => {
                      setSortBy(opt.key)
                      setSortOpen(false)
                    }}
                    className={`w-full text-left px-4 py-2 text-sm transition-colors ${
                      sortBy === opt.key
                        ? 'bg-blush-wash text-leaf font-medium'
                        : 'text-ink-soft hover:bg-cream'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Results count */}
        <div className="px-6 py-2 bg-cream border-b border-sand">
          <p className="text-xs text-ink-mute">
            {loading ? 'Loading…' : `${filtered.length} model${filtered.length !== 1 ? 's' : ''} found`}
          </p>
        </div>

        {/* Model grid */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <div className="motion-safe:animate-spin rounded-full h-8 w-8 border-b-2 border-danger mx-auto mb-3" />
                <p className="text-sm text-ink-mute">Loading models…</p>
              </div>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <p className="text-sm font-medium text-ink-soft">No models found</p>
                <p className="text-xs text-ash mt-1">Try a different filter or search term</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {filtered.map((item) => (
                <ModelCard
                  key={`${item.provider_id}/${item.model_name}`}
                  item={item}
                  onSelect={handleSelect}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
