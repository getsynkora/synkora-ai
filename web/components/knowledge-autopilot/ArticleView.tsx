'use client'

import Link from 'next/link'
import { cn } from '@/lib/utils/cn'
import type { WikiArticle } from '@/lib/api/knowledge-autopilot'

const CATEGORY_CONFIG: Record<string, { label: string; icon: string; color: string; bg: string }> = {
  projects: { label: 'Projects', icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z', color: 'text-azure', bg: 'bg-sky-wash' },
  people: { label: 'People', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z', color: 'text-plum', bg: 'bg-blush-wash' },
  decisions: { label: 'Decisions', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z', color: 'text-warn', bg: 'bg-sand-deep' },
  processes: { label: 'Processes', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15', color: 'text-leaf', bg: 'bg-leaf-wash' },
  architecture: { label: 'Architecture', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10', color: 'text-azure', bg: 'bg-sky-wash' },
  general: { label: 'General', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', color: 'text-ink-mute', bg: 'bg-cream' },
}

interface ArticleViewProps {
  article: WikiArticle
  kbId: string
}

export function ArticleView({ article, kbId }: ArticleViewProps) {
  const catConfig = CATEGORY_CONFIG[article.category] || CATEGORY_CONFIG.general

  return (
    <div className="max-w-5xl mx-auto flex gap-8 p-6 md:p-8">
      {/* Main content */}
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-2.5 mb-4">
            <div className={cn('w-7 h-7 rounded-lg flex items-center justify-center', catConfig.bg)}>
              <svg aria-hidden="true" className={cn('w-4 h-4', catConfig.color)} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={catConfig.icon} />
              </svg>
            </div>
            <span className="text-[10px] font-extrabold text-ash">{catConfig.label}</span>
            {article.staleness_score > 0.5 && (
              <span className="text-[10px] font-bold text-gold bg-sand-deep border border-honey px-2 py-0.5 rounded-full">Stale</span>
            )}
            {article.auto_generated && (
              <span className="text-[10px] font-bold text-ash bg-sand px-2 py-0.5 rounded-full">Auto-generated</span>
            )}
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-ink mb-3">{article.title}</h1>
          {article.summary && (
            <p className="text-base text-ink-mute leading-relaxed font-medium">{article.summary}</p>
          )}
        </div>

        {/* Article content */}
        <div className="prose prose-sm max-w-none
          prose-headings:text-ink prose-headings:font-extrabold prose-headings:tracking-tight
          prose-h2:text-xl prose-h2:mt-10 prose-h2:mb-4
          prose-h3:text-base prose-h3:mt-7 prose-h3:mb-3
          prose-p:text-ink-soft prose-p:leading-[1.75] prose-p:font-normal
          prose-a:text-primary-500 prose-a:font-semibold prose-a:no-underline hover:prose-a:underline
          prose-strong:text-ink prose-strong:font-bold
          prose-code:text-primary-700 prose-code:bg-primary-50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:text-xs prose-code:font-semibold
          prose-pre:bg-ink prose-pre:border-0 prose-pre:rounded-xl
          prose-ul:text-ink-soft prose-ol:text-ink-soft
          prose-li:marker:text-primary-400 prose-li:font-normal
        ">
          {article.content?.split('\n').map((line, i) => {
            if (line.startsWith('### ')) return <h3 key={i}>{line.slice(4)}</h3>
            if (line.startsWith('## ')) return <h2 key={i}>{line.slice(3)}</h2>
            if (line.startsWith('# ')) return <h2 key={i}>{line.slice(2)}</h2>
            if (line.startsWith('- ')) return <li key={i} className="ml-4 list-disc">{line.slice(2)}</li>
            if (line.startsWith('* ')) return <li key={i} className="ml-4 list-disc">{line.slice(2)}</li>
            if (line.trim() === '') return <br key={i} />
            return <p key={i}>{line}</p>
          })}
        </div>

        {/* Source documents */}
        {article.source_documents && article.source_documents.length > 0 && (
          <div className="mt-12 pt-6 border-t border-line">
            <h3 className="text-[10px] font-extrabold text-ash mb-4">Sources</h3>
            <div className="flex flex-wrap gap-2">
              {article.source_documents.map((src, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-cream border border-line rounded-lg text-xs font-semibold text-ink-soft"
                >
                  <svg aria-hidden="true" className="w-3 h-3 text-ash" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  {src.doc_title}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right sidebar */}
      <div className="w-64 flex-shrink-0 hidden lg:block">
        <div className="sticky top-6 space-y-5">
          {/* Metadata */}
          <div className="bg-white border border-line shadow-sm rounded-xl p-5">
            <h3 className="text-[10px] font-extrabold text-ash mb-4">Details</h3>
            <dl className="space-y-3 text-xs">
              <div className="flex justify-between">
                <dt className="font-medium text-ash">Status</dt>
                <dd className="font-bold text-ink capitalize">{article.status}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="font-medium text-ash">Category</dt>
                <dd className={cn('font-bold', catConfig.color)}>{catConfig.label}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="font-medium text-ash">Freshness</dt>
                <dd className={cn('font-bold', article.staleness_score > 0.5 ? 'text-warn' : 'text-leaf')}>
                  {((1 - article.staleness_score) * 100).toFixed(0)}% fresh
                </dd>
              </div>
              {article.last_compiled_at && (
                <div className="flex justify-between">
                  <dt className="font-medium text-ash">Compiled</dt>
                  <dd className="font-semibold text-ink-soft">{new Date(article.last_compiled_at).toLocaleDateString()}</dd>
                </div>
              )}
              {article.created_at && (
                <div className="flex justify-between">
                  <dt className="font-medium text-ash">Created</dt>
                  <dd className="font-semibold text-ink-soft">{new Date(article.created_at).toLocaleDateString()}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Linked articles */}
          {article.linked_articles && article.linked_articles.length > 0 && (
            <div className="bg-white border border-line shadow-sm rounded-xl p-5">
              <h3 className="text-[10px] font-extrabold text-ash mb-4">Related Articles</h3>
              <div className="space-y-1">
                {article.linked_articles.map((linked) => {
                  const linkedCat = CATEGORY_CONFIG[linked.category] || CATEGORY_CONFIG.general
                  return (
                    <Link
                      key={linked.id}
                      href={`/knowledge-bases/${kbId}/wiki/${linked.slug}`}
                      className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-semibold text-ink-soft hover:bg-primary-50 hover:text-primary-600 transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                    >
                      <div className={cn('w-5 h-5 rounded flex items-center justify-center flex-shrink-0', linkedCat.bg)}>
                        <svg aria-hidden="true" className={cn('w-3 h-3', linkedCat.color)} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={linkedCat.icon} />
                        </svg>
                      </div>
                      <span className="truncate">{linked.title}</span>
                    </Link>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
