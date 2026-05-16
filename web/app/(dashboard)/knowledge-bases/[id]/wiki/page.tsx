'use client'

import { useParams } from 'next/navigation'
import { useState, useEffect } from 'react'
import Link from 'next/link'
import { ArrowLeft, BookOpen, LayoutGrid, Share2, Zap } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { WikiBrowser } from '@/components/knowledge-autopilot/WikiBrowser'
import { WikiGraph } from '@/components/knowledge-autopilot/WikiGraph'
import { cn } from '@/lib/utils/cn'

export default function WikiPage() {
  const params = useParams()
  const kbId = params.id as string
  const [kbName, setKbName] = useState('')
  const [view, setView] = useState<'list' | 'graph'>('list')

  useEffect(() => {
    apiClient.getKnowledgeBase(kbId).then((data: any) => {
      setKbName(data.name || 'Knowledge Base')
    }).catch(() => {
      setKbName('Knowledge Base')
    })
  }, [kbId])

  return (
    <div
      className={cn(
        'dashboard-resource-page p-4 md:p-6',
        view === 'graph'
          ? 'h-[calc(100vh-32px)] min-h-[calc(100vh-32px)]'
          : 'min-h-[calc(100vh-64px)]'
      )}
    >
      <div
        className={cn(
          'mx-auto max-w-7xl',
          view === 'graph' ? 'flex h-full min-h-0 flex-col' : 'space-y-0'
        )}
      >
        <div className="mb-6">
          <Link
            href={`/knowledge-bases/${kbId}`}
            className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-gray-600 transition-colors hover:text-[#171717]"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Knowledge Base
          </Link>

          <div className="rounded-[2rem] border border-black/10 bg-white/78 p-6 shadow-[0_24px_60px_rgba(0,0,0,0.06)] sm:p-8">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex items-start gap-3">
                <div className="rounded-[1.15rem] bg-[#f3ecde] p-3 shadow-[0_12px_28px_rgba(0,0,0,0.04)]">
                  <BookOpen className="h-6 w-6 text-[#171717]" />
                </div>
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#6e675d]">
                    <Zap className="h-3.5 w-3.5 text-[#2d8b69]" />
                    Knowledge Wiki
                  </div>
                  <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-gray-900 md:text-3xl">
                    {kbName} Wiki
                  </h1>
                  <p className="mt-2 max-w-2xl text-sm text-gray-600">
                    Browse AI-compiled articles, search key topics, and switch to graph view when you want to explore relationships.
                  </p>
                </div>
              </div>

              <div className="flex w-full rounded-[1.25rem] border border-black/10 bg-[#f1eadc] p-1.5 lg:w-auto">
                <button
                  onClick={() => setView('list')}
                  className={cn(
                    'flex flex-1 items-center justify-center gap-2 rounded-[0.95rem] px-4 py-2.5 text-sm font-semibold transition-all lg:flex-none',
                    view === 'list'
                      ? 'bg-[#171717] text-white shadow-[0_12px_24px_rgba(0,0,0,0.16)]'
                      : 'text-[#6e675d] hover:bg-white/70 hover:text-[#171717]'
                  )}
                >
                  <LayoutGrid className="h-4 w-4" />
                  Articles
                </button>
                <button
                  onClick={() => setView('graph')}
                  className={cn(
                    'flex flex-1 items-center justify-center gap-2 rounded-[0.95rem] px-4 py-2.5 text-sm font-semibold transition-all lg:flex-none',
                    view === 'graph'
                      ? 'bg-[#171717] text-white shadow-[0_12px_24px_rgba(0,0,0,0.16)]'
                      : 'text-[#6e675d] hover:bg-white/70 hover:text-[#171717]'
                  )}
                >
                  <Share2 className="h-4 w-4" />
                  Knowledge Graph
                </button>
              </div>
            </div>
          </div>
        </div>

        <div
          className={cn(
            'rounded-[2rem] border border-black/10 bg-white/72 shadow-[0_28px_70px_rgba(0,0,0,0.08)]',
            view === 'graph'
              ? 'min-h-[38rem] flex-1 overflow-hidden'
              : 'overflow-visible'
          )}
        >
          <div className={cn(view === 'graph' ? 'h-full overflow-hidden' : 'overflow-visible')}>
            {view === 'list' ? (
              <WikiBrowser kbId={kbId} kbName={kbName} />
            ) : (
              <WikiGraph kbId={kbId} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
