'use client'

import { useMemo, useState } from 'react'
import { X, Download, Sparkles, Check } from 'lucide-react'
import { createConversationShare, revokeConversationShare } from '@/lib/api/conversations'
import type { Message } from '@/components/chat/types'
import type { ShareLink } from '@/lib/api/conversations'
import { extractMindsetShareData } from '@/lib/share/mindsetShare'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface ShareModalProps {
  conversationId: string
  messages?: Message[]
  conversationName?: string
  agentName?: string
  onClose: () => void
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
}

export function ShareModal({ conversationId, messages = [], conversationName, agentName, onClose }: ShareModalProps) {
  const [generatedShare, setGeneratedShare] = useState<ShareLink | null>(null)
  const [generatedImageUrl, setGeneratedImageUrl] = useState<string | null>(null)
  const [downloaded, setDownloaded] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleGenerate() {
    setError(null)
    setIsCreating(true)

    try {
      if (generatedShare) {
        await revokeConversationShare(generatedShare.id, conversationId).catch(() => undefined)
      }

      const share = await createConversationShare(conversationId, 86400)
      const token = share.token || share.share_url?.split('/').pop()
      if (!token) throw new Error('missing_share_token')

      setGeneratedShare(share)
      setGeneratedImageUrl(`${API_URL}/api/v1/public/share/${encodeURIComponent(token)}/image`)
      setDownloaded(false)
    } catch {
      setError('Failed to generate share image. Please try again.')
    } finally {
      setIsCreating(false)
    }
  }

  async function cleanupGeneratedShare() {
    if (!generatedShare) return

    try {
      await revokeConversationShare(generatedShare.id, conversationId)
    } catch {
      // Best effort cleanup only.
    }
  }

  async function handleDownload() {
    if (!generatedImageUrl) return

    try {
      setIsDownloading(true)
      const response = await fetch(generatedImageUrl, { cache: 'no-store' })
      if (!response.ok) throw new Error('download_failed')

      const blob = await response.blob()
      const blobUrl = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      const baseName = slugify(agentName || conversationName || 'synkora-share-image')
      anchor.href = blobUrl
      anchor.download = `${baseName}.png`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(blobUrl)
      setDownloaded(true)
    } catch {
      setError('Failed to download the share image.')
    } finally {
      setIsDownloading(false)
    }
  }

  async function handleClose() {
    await cleanupGeneratedShare()
    onClose()
  }

  const sharePreview = useMemo(
    () =>
      extractMindsetShareData({
        conversation: { name: conversationName },
        agent: { name: agentName },
        messages: messages.map(message => ({
          role: message.role,
          content: message.content,
          metadata: message.metadata,
        })),
      }),
    [agentName, conversationName, messages]
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-md" onClick={handleClose}>
      <div
        className="mx-4 w-full max-w-5xl overflow-hidden rounded-[30px] border border-white/15 bg-[#09101f] text-white shadow-[0_36px_120px_rgba(3,7,18,0.65)]"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-5">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-white/40">
              Social Export
            </p>
            <h2 className="mt-1 text-lg font-semibold text-white">Download Share Image</h2>
          </div>
          <button
            onClick={handleClose}
            className="rounded-xl p-2 text-white/[0.55] transition hover:bg-white/10 hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        <div className="grid gap-6 px-6 py-6 lg:grid-cols-[minmax(0,1.2fr)_340px]">
          <div className="space-y-4">
            <div className="overflow-hidden rounded-[28px] border border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(124,58,237,0.38),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(6,182,212,0.2),_transparent_26%),linear-gradient(145deg,_#0a1124_0%,_#10152d_52%,_#16173b_100%)] p-4">
              {generatedImageUrl ? (
                <img
                  src={generatedImageUrl}
                  alt="Generated Synkora share card"
                  className="w-full rounded-[22px] border border-white/10 bg-black/20 shadow-[0_24px_80px_rgba(4,8,20,0.45)]"
                />
              ) : (
                <div className="flex aspect-[1.91/1] items-center justify-center rounded-[22px] border border-dashed border-white/15 bg-black/[0.15] px-8 text-center">
                  <div className="max-w-md">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 text-white/80">
                      <Sparkles size={22} />
                    </div>
                    <h3 className="mt-4 text-2xl font-semibold tracking-[-0.04em] text-white">
                      Generate a polished social card
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-white/[0.65]">
                      Create a modern Synkora-branded PNG you can upload directly to LinkedIn, X, or anywhere else.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {error && (
              <p className="rounded-2xl border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                {error}
              </p>
            )}
          </div>

          <div className="space-y-4">
            <div className="rounded-[28px] border border-white/10 bg-white/[0.05] p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-white/40">
                What You Export
              </p>
              <h3 className="mt-3 text-2xl font-semibold tracking-[-0.04em] text-white">
                A single polished PNG
              </h3>
              <p className="mt-3 text-sm leading-6 text-white/[0.65]">
                No public link, no social URL sharing workflow in the UI. Just generate the image and upload it directly wherever you want.
              </p>
            </div>

            {sharePreview && (
              <div className="rounded-[28px] border border-white/10 bg-white/[0.05] p-5">
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full border border-[#7C3AED]/35 bg-[#7C3AED]/18 px-3 py-1 text-xs font-semibold text-[#e2d7ff]">
                    {sharePreview.classification}
                  </span>
                  {sharePreview.scoreLabel && (
                    <span className="rounded-full border border-[#06B6D4]/30 bg-[#06B6D4]/14 px-3 py-1 text-xs font-medium text-[#b8f5ff]">
                      {sharePreview.scoreLabel}
                    </span>
                  )}
                </div>

                <h4 className="mt-4 text-xl font-semibold tracking-[-0.03em] text-white">
                  {sharePreview.headline}
                </h4>
                <p className="mt-2 text-sm leading-6 text-white/[0.65]">
                  {sharePreview.insight}
                </p>

                {(sharePreview.strengths[0] || sharePreview.growthEdges[0]) && (
                  <div className="mt-4 space-y-3">
                    {sharePreview.strengths[0] && (
                      <div className="rounded-2xl border border-white/10 bg-black/[0.15] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/40">
                          Strongest Signal
                        </p>
                        <p className="mt-2 text-sm leading-6 text-white/[0.82]">
                          {sharePreview.strengths[0]}
                        </p>
                      </div>
                    )}
                    {sharePreview.growthEdges[0] && (
                      <div className="rounded-2xl border border-white/10 bg-black/[0.15] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/40">
                          Next Growth Edge
                        </p>
                        <p className="mt-2 text-sm leading-6 text-white/[0.82]">
                          {sharePreview.growthEdges[0]}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            <div className="space-y-3 rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] p-5">
              <button
                onClick={handleGenerate}
                disabled={isCreating}
                className="flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#08101f] transition hover:bg-white/92 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Sparkles size={16} />
                {isCreating ? 'Generating image…' : generatedImageUrl ? 'Regenerate image' : 'Generate share image'}
              </button>

              <button
                onClick={handleDownload}
                disabled={!generatedImageUrl || isDownloading}
                className="flex w-full items-center justify-center gap-2 rounded-2xl border border-white/12 bg-white/[0.06] px-4 py-3 text-sm font-semibold text-white transition hover:bg-white/[0.1] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {downloaded ? <Check size={16} /> : <Download size={16} />}
                {isDownloading ? 'Downloading…' : downloaded ? 'Downloaded PNG' : 'Download PNG'}
              </button>

              <p className="px-1 text-xs leading-5 text-white/[0.42]">
                Best for posting directly on LinkedIn, X, or any other social platform as an image attachment.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
