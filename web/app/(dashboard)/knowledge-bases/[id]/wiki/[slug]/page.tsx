'use client'

import { useParams } from 'next/navigation'
import { useState, useEffect } from 'react'
import Link from 'next/link'
import { ArrowLeft, Zap } from 'lucide-react'
import { getWikiArticle } from '@/lib/api/knowledge-autopilot'
import type { WikiArticle } from '@/lib/api/knowledge-autopilot'
import { ArticleView } from '@/components/knowledge-autopilot/ArticleView'

export default function WikiArticlePage() {
  const params = useParams()
  const kbId = params.id as string
  const slug = params.slug as string
  const [article, setArticle] = useState<WikiArticle | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getWikiArticle(kbId, slug)
      .then((data) => setArticle(data))
      .catch((err) => setError(err.message || 'Failed to load article'))
      .finally(() => setLoading(false))
  }, [kbId, slug])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="w-10 h-10 border-[3px] border-line border-b-primary-500 rounded-full motion-safe:animate-spin mx-auto mb-4" />
          <p className="text-sm text-ash font-bold">Loading article…</p>
        </div>
      </div>
    )
  }

  if (error || !article) {
    return (
      <div className="flex flex-col items-center justify-center h-screen px-4">
        <div className="w-20 h-20 mb-6 rounded-2xl bg-ink hover:bg-ink/85/50 flex items-center justify-center border border-primary-200/50">
          <svg aria-hidden="true" className="w-10 h-10 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <h3 className="text-xl font-extrabold tracking-tight text-ink mb-2">{error || 'Article not found'}</h3>
        <Link
          href={`/knowledge-bases/${kbId}/wiki`}
          className="mt-4 text-sm text-primary-500 hover:text-primary-600 font-bold transition-colors"
        >
          Back to Wiki
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      <div className="border-b border-line bg-white px-4 md:px-6 py-4">
        <div className="flex items-center gap-3">
          <Link
            href={`/knowledge-bases/${kbId}/wiki`}
            className="flex items-center gap-2 text-ink-mute hover:text-ink transition-colors"
          >
            <ArrowLeft size={18} />
            <span className="text-sm font-medium">Wiki</span>
          </Link>
          <div className="w-px h-6 bg-line" />
          <div className="w-7 h-7 bg-ink hover:bg-ink/85 rounded-lg flex items-center justify-center shadow-sm shadow-primary-500/20">
            <Zap size={13} className="text-white" />
          </div>
          <h1 className="text-base font-extrabold tracking-tight text-ink truncate">{article.title}</h1>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto bg-cream/50">
        <ArticleView article={article} kbId={kbId} />
      </div>
    </div>
  )
}
