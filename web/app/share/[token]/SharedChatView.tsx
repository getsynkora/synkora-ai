'use client'

import { useMemo, useState } from 'react'
import { ChatMessages } from '@/components/chat/components'
import type { SharedConversationData } from '@/lib/api/conversations'
import type { Message } from '@/components/chat/types'
import { useTranslations } from 'next-intl'
import {
  buildLinkedInShareUrl,
  buildSocialShareText,
  buildXShareUrl,
  extractMindsetShareData,
} from '@/lib/share/mindsetShare'

interface Props {
  data: SharedConversationData
}

function formatExpiry(expiresAt: string, expiredLabel: string): string {
  const diff = new Date(expiresAt).getTime() - Date.now()
  if (diff <= 0) return expiredLabel
  const h = Math.floor(diff / 3_600_000)
  const m = Math.floor((diff % 3_600_000) / 60_000)
  if (h >= 24) return `${Math.floor(h / 24)}d ${h % 24}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export function SharedChatView({ data }: Props) {
  const t = useTranslations('share.view')
  const { conversation, messages: rawMessages, agent, expires_at } = data
  const [copied, setCopied] = useState<'caption' | 'link' | null>(null)

  const messages: Message[] = useMemo(
    () =>
      rawMessages
        .filter((msg: any) => {
          const role = (msg.role as string).toLowerCase()
          return role === 'user' || role === 'assistant'
        })
        .map((msg: any) => ({
          id: msg.id,
          role: (msg.role as string).toLowerCase() as Message['role'],
          content: msg.content,
          timestamp: new Date(msg.created_at),
          sources: msg.metadata?.sources || [],
          metadata: msg.metadata || {},
        })),
    [rawMessages]
  )

  const mindsetShare = useMemo(
    () => extractMindsetShareData(data),
    [data]
  )

  const shareUrl = typeof window !== 'undefined' ? window.location.href : ''
  const shareCopyText = mindsetShare ? buildSocialShareText(mindsetShare, shareUrl) : ''
  const socialShareText = mindsetShare ? buildSocialShareText(mindsetShare) : ''
  const linkedInUrl = shareUrl ? buildLinkedInShareUrl(shareUrl) : '#'
  const xUrl = shareUrl && mindsetShare ? buildXShareUrl(shareUrl, socialShareText) : '#'

  async function handleCopy(value: string, type: 'caption' | 'link') {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(type)
      window.setTimeout(() => setCopied(current => (current === type ? null : current)), 2000)
    } catch {
      setCopied(null)
    }
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-ink text-white">
      <div className="relative isolate">
        <div className="absolute inset-0" />

        <div className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
          {mindsetShare && (
            <section className="overflow-hidden rounded-[32px] border border-white/10 bg-white/[0.06] shadow-soft">
              <div className="grid gap-6 px-5 py-6 sm:px-7 sm:py-7 lg:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.9fr)] lg:gap-8 lg:px-8 lg:py-8">
                <div className="space-y-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-semibold text-white/[0.72]">
                      {t('mindsetSnapshot')}
                    </span>
                    <span className="rounded-full border border-azure/40 bg-azure/16 px-3 py-1 text-xs font-semibold text-blush-wash">
                      {mindsetShare.classification}
                    </span>
                    <span className="rounded-full border border-white/12 bg-black/20 px-3 py-1 text-xs font-medium text-white/[0.70]">
                      {mindsetShare.domain}
                    </span>
                    {mindsetShare.scoreLabel && (
                      <span className="rounded-full border border-steel/35 bg-steel/12 px-3 py-1 text-xs font-medium text-sky-wash">
                        {mindsetShare.scoreLabel}
                      </span>
                    )}
                  </div>

                  <div className="max-w-3xl space-y-3">
                    <h1 className="text-3xl font-semibold tracking-[-0.04em] text-white sm:text-4xl lg:text-[3.25rem] lg:leading-[1.02]">
                      {mindsetShare.headline}
                    </h1>
                    <p className="max-w-2xl text-sm leading-6 text-white/[0.72] sm:text-[15px] sm:leading-7">
                      {mindsetShare.insight}
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                      <p className="text-[11px] font-semibold text-white/[0.45]">
                        {t('strongestSignal')}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-white/[0.84]">
                        {mindsetShare.strengths[0] || t('defaultStrength')}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                      <p className="text-[11px] font-semibold text-white/[0.45]">
                        {t('nextGrowthEdge')}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-white/[0.84]">
                        {mindsetShare.growthEdges[0] || t('defaultGrowthEdge')}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-white/10 flex flex-col justify-between rounded-[28px] border border-white/12 p-5 shadow-soft">
                  <div>
                    <div className="flex items-center justify-between">
                      <p className="text-[11px] font-semibold text-white/[0.45]">
                        {t('shareCaption')}
                      </p>
                      <span className="rounded-full border border-white/10 bg-black/[0.15] px-2.5 py-1 text-[11px] text-white/[0.52]">
                        {t('ogEnabled')}
                      </span>
                    </div>
                    <p className="mt-4 text-base leading-7 text-white/[0.92]">
                      {mindsetShare.shareCaption}
                    </p>
                  </div>

                  <div className="mt-6 flex flex-wrap gap-2">
                    <button
                      onClick={() => handleCopy(shareCopyText, 'caption')}
                      className="rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-ink transition hover:bg-white/90"
                    >
                      {copied === 'caption' ? t('copiedPost') : t('copyPost')}
                    </button>
                    <button
                      onClick={() => handleCopy(shareUrl, 'link')}
                      className="rounded-xl border border-white/15 bg-white/[0.08] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/[0.14]"
                    >
                      {copied === 'link' ? t('copiedLink') : t('copyLink')}
                    </button>
                    <a
                      href={linkedInUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-xl border border-white/15 bg-white/[0.08] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/[0.14]"
                    >
                      {t('shareLinkedIn')}
                    </a>
                    <a
                      href={xUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-xl border border-white/15 bg-white/[0.08] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/[0.14]"
                    >
                      {t('shareX')}
                    </a>
                  </div>
                </div>
              </div>
            </section>
          )}

          <section className="overflow-hidden rounded-[28px] border border-white/10 bg-white/[0.94] shadow-soft">
            <header className="flex flex-wrap items-center gap-3 border-b border-line/80 px-4 py-4 sm:px-5">
              {agent?.avatar ? (
                <img
                  src={agent.avatar}
                  alt={agent.name}
                  className="h-10 w-10 rounded-2xl object-cover shadow-sm"
                />
              ) : (
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl shadow-soft">
                  <span className="text-sm font-bold text-white">
                    {agent?.name?.charAt(0)?.toUpperCase() || 'S'}
                  </span>
                </div>
              )}

              <div className="min-w-0 flex-1">
                <h2 className="truncate text-sm font-semibold text-ink">
                  {conversation?.name || t('sharedConversation')}
                </h2>
                <p className="text-xs text-ink-mute">
                  {agent?.name || t('defaultAgent')}, {t('readOnly')}
                </p>
              </div>

              <span className="rounded-full border border-line bg-cream px-3 py-1 text-xs font-medium text-ink-mute">
                {t('expiresIn', { time: formatExpiry(expires_at, t('expired')) })}
              </span>
            </header>

            <div className="w-full bg-white px-4 py-4 sm:px-5 sm:py-5">
              {messages.length === 0 ? (
                <div className="flex h-64 flex-col items-center justify-center text-ash">
                  <p className="text-sm">No messages in this conversation.</p>
                </div>
              ) : (
                <ChatMessages
                  messages={messages}
                  isStreaming={false}
                  agentName={agent?.name}
                  agentAvatar={agent?.avatar}
                />
              )}
            </div>

            <div className="border-t border-line/80 bg-white px-4 py-3 sm:px-5">
              <p className="text-center text-xs text-ash">
                {t('sharedVia')}
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
