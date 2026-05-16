'use client'

import { useState, useEffect } from 'react'
import { extractErrorMessage } from '@/lib/api/error'
import { useRouter } from 'next/navigation'
import { cn } from '@/lib/utils/cn'
import type { WikiArticle, AutopilotStatus, LLMConfigOption } from '@/lib/api/knowledge-autopilot'
import { getWikiArticles, searchWiki, getAutopilotStatus, triggerCompilation, getLLMConfigsForCompilation } from '@/lib/api/knowledge-autopilot'

const CATEGORY_CONFIG: Record<string, { label: string; icon: string; color: string; bg: string; border: string }> = {
  projects: { label: 'Projects', icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z', color: 'text-[#6b5f46]', bg: 'bg-[#f3ecde]', border: 'border-[#e6dcc8]' },
  people: { label: 'People', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z', color: 'text-[#8b5a74]', bg: 'bg-[#f6edf1]', border: 'border-[#ead8e1]' },
  decisions: { label: 'Decisions', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z', color: 'text-[#9a6700]', bg: 'bg-[#f8f0dd]', border: 'border-[#ecd9af]' },
  processes: { label: 'Processes', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15', color: 'text-[#2d8b69]', bg: 'bg-[#e8f4ee]', border: 'border-[#cfe6d9]' },
  architecture: { label: 'Architecture', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10', color: 'text-[#486c77]', bg: 'bg-[#edf4f6]', border: 'border-[#d7e6ea]' },
  general: { label: 'General', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', color: 'text-[#6e675d]', bg: 'bg-white', border: 'border-black/10' },
}

interface WikiBrowserProps {
  kbId: string
  kbName: string
}

export function WikiBrowser({ kbId, kbName }: WikiBrowserProps) {
  const router = useRouter()
  const [articles, setArticles] = useState<WikiArticle[]>([])
  const [categories, setCategories] = useState<Record<string, WikiArticle[]>>({})
  const [status, setStatus] = useState<AutopilotStatus | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<WikiArticle[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [compiling, setCompiling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [compileError, setCompileError] = useState<string | null>(null)
  const [compileMessage, setCompileMessage] = useState<string | null>(null)
  const [llmConfigs, setLlmConfigs] = useState<LLMConfigOption[]>([])
  const [selectedLlmConfigId, setSelectedLlmConfigId] = useState<string>('')

  useEffect(() => {
    loadData()
  }, [kbId, selectedCategory])

  useEffect(() => {
    getLLMConfigsForCompilation(kbId)
      .then((data) => setLlmConfigs(data.configs || []))
      .catch(() => {})
  }, [kbId])

  const loadData = async () => {
    try {
      setError(null)
      const [articlesData, statusData] = await Promise.all([
        getWikiArticles(kbId, selectedCategory || undefined),
        getAutopilotStatus(kbId),
      ])
      setArticles(articlesData.articles || [])
      setCategories(articlesData.categories || {})
      setStatus(statusData)
    } catch (err: any) {
      const msg = extractErrorMessage(err, err?.message || 'Failed to load wiki data')
      setError(msg)
      console.error('Failed to load wiki:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null)
      return
    }
    try {
      const data = await searchWiki(kbId, searchQuery)
      setSearchResults(data.results || [])
    } catch (err) {
      console.error('Search failed:', err)
    }
  }

  const handleCompile = async () => {
    setCompiling(true)
    setCompileError(null)
    setCompileMessage(null)
    try {
      const result = await triggerCompilation(kbId, selectedLlmConfigId || undefined)
      if (result?.status === 'failed') {
        setCompileError(result.error || 'Compilation failed')
        setCompiling(false)
        return
      }

      setCompileMessage('Compiling knowledge base... this may take up to a minute.')

      // Poll status until compilation completes
      const startedAt = Date.now()
      const MAX_WAIT_MS = 3 * 60 * 1000 // 3 minutes max
      while (Date.now() - startedAt < MAX_WAIT_MS) {
        await new Promise((r) => setTimeout(r, 4000))
        try {
          const statusData = await getAutopilotStatus(kbId)
          const job = statusData.last_compilation
          if (job?.status === 'completed') {
            setStatus(statusData)
            await loadData()
            setCompileMessage('Compilation complete. Wiki articles have been updated.')
            setTimeout(() => setCompileMessage(null), 8000)
            return
          }
          if (job?.status === 'failed') {
            setCompileError('Compilation failed. Check server logs for details.')
            return
          }
          // still running — update status in sidebar while we wait
          setStatus(statusData)
        } catch {
          // ignore transient fetch errors during polling
        }
      }

      // Timed out — do a final refresh anyway
      await loadData()
      setCompileMessage('Compilation is taking longer than expected. Refresh the page to check results.')
      setTimeout(() => setCompileMessage(null), 10000)
    } catch (err: any) {
      const msg = extractErrorMessage(err, err?.message || 'Compilation failed')
      setCompileError(msg)
      console.error('Compilation failed:', err)
    } finally {
      setCompiling(false)
    }
  }

  const displayArticles = searchResults !== null ? searchResults : articles

  const healthPct = status ? ((1 - status.avg_staleness) * 100).toFixed(0) : '100'
  const healthColor =
    !status || status.avg_staleness < 0.3 ? 'text-emerald-500' :
    status.avg_staleness < 0.6 ? 'text-amber-500' : 'text-red-500'
  const healthBarColor =
    !status || status.avg_staleness < 0.3 ? 'bg-emerald-500' :
    status.avg_staleness < 0.6 ? 'bg-amber-500' : 'bg-red-500'
  const searchFieldClass = 'w-full rounded-[1.15rem] border border-gray-200 bg-white px-11 py-3 text-sm font-medium text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500'
  const selectFieldClass = 'w-full rounded-[1rem] border border-gray-200 bg-gray-50 px-3.5 py-3 text-sm font-medium text-gray-700 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50'

  return (
    <div className="flex h-full bg-[#fcfaf5]">
      <div className="hidden w-72 flex-shrink-0 overflow-hidden border-r border-black/10 bg-[#f7f2e7]/88 md:flex md:flex-col">
        <div className="border-b border-black/10 p-5">
          <div className="rounded-[1.5rem] border border-black/10 bg-white/78 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
            <h3 className="mb-4 text-[11px] font-extrabold uppercase tracking-[0.16em] text-[#8a8378]">Autopilot</h3>

            {status && (
              <>
                <div className="mb-4 rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] p-3.5">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-500">Knowledge Health</span>
                    <span className={cn('text-xs font-extrabold', healthColor)}>{healthPct}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[#ece4d3]">
                    <div
                      className={cn('h-full rounded-full transition-all duration-700', healthBarColor)}
                      style={{ width: `${healthPct}%` }}
                    />
                  </div>
                </div>

                {status.last_compilation && (
                  <div className="mb-4 space-y-2 text-xs text-gray-500">
                    <div className="flex justify-between gap-3">
                      <span className="font-medium">Last compiled</span>
                      <span className="font-semibold text-gray-700">
                        {status.last_compilation.completed_at
                          ? new Date(status.last_compilation.completed_at).toLocaleDateString()
                          : 'In progress'}
                      </span>
                    </div>
                    {(status.last_compilation.articles_created > 0 || status.last_compilation.articles_updated > 0) && (
                      <div className="flex justify-between gap-3">
                        <span className="font-medium">Changes</span>
                        <span className="font-semibold text-gray-700">
                          +{status.last_compilation.articles_created} / ~{status.last_compilation.articles_updated}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            <div className="mb-3">
              <label className="mb-1.5 block text-[11px] font-semibold text-gray-700">
                LLM Config
              </label>
              <select
                value={selectedLlmConfigId}
                onChange={(e) => setSelectedLlmConfigId(e.target.value)}
                disabled={compiling}
                className={selectFieldClass}
              >
                <option value="">Auto (use agent default)</option>
                {llmConfigs.map((cfg) => (
                  <option key={cfg.id} value={cfg.id}>
                    {cfg.name} — {cfg.model_name}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={handleCompile}
              disabled={compiling}
              className="flex w-full items-center justify-center gap-2 rounded-[1.05rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
            >
              {compiling ? (
                <>
                  <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  Compiling...
                </>
              ) : (
                'Compile Now'
              )}
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <div className="rounded-[1.5rem] border border-black/10 bg-white/60 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.04)]">
            <h3 className="mb-4 text-[11px] font-extrabold uppercase tracking-[0.16em] text-[#8a8378]">Categories</h3>
            <div className="space-y-1.5">
              <button
                onClick={() => { setSelectedCategory(null); setSearchResults(null) }}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-[1rem] px-3.5 py-3 text-left text-sm font-semibold transition-all',
                  !selectedCategory
                    ? 'bg-[#171717] text-white shadow-[0_12px_28px_rgba(0,0,0,0.16)]'
                    : 'text-[#5f5a52] hover:bg-white/75 hover:text-[#171717]'
                )}
              >
                <span>All Articles</span>
                <span
                  className={cn(
                    'ml-auto inline-flex min-w-7 items-center justify-center rounded-full px-2 py-0.5 text-[11px] font-semibold',
                    !selectedCategory ? 'bg-white/12 text-white' : 'bg-[#f3ecde] text-[#6e675d]'
                  )}
                >
                  {status?.total_articles || 0}
                </span>
              </button>

              {Object.entries(CATEGORY_CONFIG).map(([key, config]) => {
                const count = status?.category_counts?.[key] || 0
                if (count === 0 && !categories[key]) return null
                return (
                  <button
                    key={key}
                    onClick={() => { setSelectedCategory(key); setSearchResults(null) }}
                    className={cn(
                      'flex w-full items-center gap-2.5 rounded-[1rem] px-3.5 py-3 text-left text-sm font-semibold transition-all',
                      selectedCategory === key
                        ? 'bg-[#171717] text-white shadow-[0_12px_28px_rgba(0,0,0,0.16)]'
                        : 'text-[#5f5a52] hover:bg-white/75 hover:text-[#171717]'
                    )}
                  >
                    <div className={cn(
                      'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[0.85rem] border',
                      selectedCategory === key ? 'border-white/10 bg-white/10' : `${config.bg} ${config.border}`
                    )}>
                      <svg
                        className={cn('h-4 w-4', selectedCategory === key ? 'text-white' : config.color)}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={config.icon} />
                      </svg>
                    </div>
                    <span>{config.label}</span>
                    <span
                      className={cn(
                        'ml-auto inline-flex min-w-7 items-center justify-center rounded-full px-2 py-0.5 text-[11px] font-semibold',
                        selectedCategory === key ? 'bg-white/12 text-white' : 'bg-[#f3ecde] text-[#6e675d]'
                      )}
                    >
                      {count}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-[#fcfaf5]">
        <div className="sticky top-0 z-10 border-b border-black/10 bg-[#fcfaf5]/95 px-4 py-4 backdrop-blur-sm md:px-5">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  if (!e.target.value.trim()) setSearchResults(null)
                }}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search wiki articles..."
                className={searchFieldClass}
              />
              <svg className="absolute left-4 top-3.5 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <button
              onClick={handleCompile}
              disabled={compiling}
              className="rounded-[1.05rem] bg-[#171717] px-4 py-3 text-xs font-semibold text-white transition-colors hover:bg-black disabled:opacity-50 md:hidden"
            >
              {compiling ? 'Compiling...' : 'Compile'}
            </button>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-medium text-[#6e675d]">
            <span className="inline-flex items-center rounded-full bg-[#f1eadc] px-2.5 py-1">
              {displayArticles.length} article{displayArticles.length === 1 ? '' : 's'}
            </span>
            {selectedCategory && (
              <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 shadow-[0_8px_18px_rgba(0,0,0,0.04)]">
                {CATEGORY_CONFIG[selectedCategory]?.label || selectedCategory}
              </span>
            )}
            {searchResults !== null && (
              <span className="inline-flex items-center rounded-full bg-[#e8f4ee] px-2.5 py-1 text-[#2d8b69]">
                Search results
              </span>
            )}
          </div>
        </div>

        {compileMessage && (
          <div className="mx-4 mt-4 md:mx-5">
            <div className="flex items-center gap-2 rounded-[1.15rem] border border-emerald-200 bg-emerald-50/90 px-4 py-3 text-sm font-medium text-emerald-700">
              <svg className="h-4 w-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {compileMessage}
            </div>
          </div>
        )}
        {(error || compileError) && (
          <div className="mx-4 mt-4 md:mx-5">
            <div className="rounded-[1.15rem] border border-red-200 bg-red-50/90 px-4 py-3 text-sm font-medium text-red-700">
              {compileError || error}
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center px-4 py-20">
            <div className="rounded-[1.75rem] border border-black/10 bg-white/85 px-8 py-10 text-center shadow-[0_20px_48px_rgba(0,0,0,0.05)]">
              <div className="mx-auto mb-4 h-8 w-8 rounded-full border-[3px] border-[#ece4d3] border-t-[#171717] animate-spin" />
              <span className="text-sm font-semibold text-gray-700">Loading articles...</span>
            </div>
          </div>
        ) : displayArticles.length === 0 ? (
          <div className="px-4 py-16 md:px-5 md:py-20">
            <div className="mx-auto max-w-xl rounded-[2rem] border border-black/10 bg-white/85 px-6 py-10 text-center shadow-[0_24px_60px_rgba(0,0,0,0.06)]">
              <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-[1.5rem] border border-black/10 bg-[#f3ecde]">
                <svg className="h-10 w-10 text-[#6e675d]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <h3 className="mb-2 text-2xl font-extrabold tracking-tight text-gray-900">No wiki articles yet</h3>
              <p className="mx-auto mb-8 max-w-md text-sm leading-relaxed text-gray-500">
                Compile <span className="font-semibold text-gray-700">{kbName || 'this knowledge base'}</span> to turn your documents into AI-organized wiki articles.
              </p>
              <button
                onClick={handleCompile}
                disabled={compiling}
                className="rounded-[1.1rem] bg-[#171717] px-8 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
              >
                {compiling ? (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    Compiling...
                  </span>
                ) : (
                  'Generate Wiki'
                )}
              </button>
            </div>
          </div>
        ) : (
          <>
            <style>{`
              @keyframes wikiCardIn {
                from { opacity: 0; transform: translateY(10px); }
                to   { opacity: 1; transform: translateY(0); }
              }
            `}</style>
            <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2 md:p-5 xl:grid-cols-3">
              {displayArticles.map((article, index) => {
                const catConfig = CATEGORY_CONFIG[article.category] || CATEGORY_CONFIG.general
                return (
                  <button
                    key={article.id}
                    onClick={() => router.push(`/knowledge-bases/${kbId}/wiki/${article.slug}`)}
                    style={{ animation: 'wikiCardIn 0.35s ease-out both', animationDelay: `${index * 45}ms` }}
                    className="group rounded-[1.6rem] border border-black/10 bg-white/88 p-5 text-left shadow-[0_18px_40px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-0.5 hover:border-black/15 hover:shadow-[0_24px_56px_rgba(0,0,0,0.08)]"
                  >
                    <div className="mb-4 flex items-start gap-2">
                      <div className={cn('flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[0.95rem] border', catConfig.bg, catConfig.border)}>
                        <svg className={cn('h-4 w-4', catConfig.color)} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={catConfig.icon} />
                        </svg>
                      </div>
                      <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold', catConfig.bg, catConfig.color)}>
                        {catConfig.label}
                      </span>
                      {article.staleness_score > 0.5 && (
                        <span className="ml-auto inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-700">
                          Stale
                        </span>
                      )}
                    </div>

                    <h4 className="mb-2 line-clamp-2 text-base font-semibold tracking-tight text-gray-900 transition-colors group-hover:text-[#171717]">
                      {article.title}
                    </h4>

                    {article.summary ? (
                      <p className="line-clamp-3 text-sm leading-relaxed text-gray-500">
                        {article.summary}
                      </p>
                    ) : (
                      <p className="text-sm leading-relaxed text-gray-400">
                        No summary available for this article yet.
                      </p>
                    )}

                    <div className="mt-5 flex items-center gap-3 border-t border-black/10 pt-4 text-xs font-medium text-[#7b756c]">
                      <span className="inline-flex items-center gap-1.5">
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        {article.source_documents?.length || 0} sources
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                        {(article.forward_links?.length || 0) + (article.backlinks?.length || 0)} links
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
