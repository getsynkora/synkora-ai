'use client'

import { useState } from 'react'
import { Heart, Share2, MessageSquare, Download } from 'lucide-react'
import { cn } from '@/lib/utils'

interface AgentProfileProps {
  agentName: string
  agentType?: string
  description?: string
  avatar?: string
  creator?: string
  likes?: number
  interactions?: string
  isLiked?: boolean
  onLike?: () => void
  onShare?: () => void
  primaryColor?: string
  className?: string
}

/**
 * AgentProfile - Displays agent information with social interactions
 * Shows agent picture, name, creator, likes, interactions and action buttons
 */
export function AgentProfile({
  agentName,
  avatar,
  creator = 'Admin',
  likes = 0,
  interactions = '0',
  isLiked: initialIsLiked = false,
  onLike,
  onShare,
  primaryColor = '#14b8a6',
  className,
}: AgentProfileProps) {
  const [isLiked, setIsLiked] = useState(initialIsLiked)
  const [likeCount, setLikeCount] = useState(likes)
  const [showShareMenu, setShowShareMenu] = useState(false)

  const handleLike = () => {
    const newIsLiked = !isLiked
    setIsLiked(newIsLiked)
    setLikeCount(prev => newIsLiked ? prev + 1 : Math.max(0, prev - 1))
    onLike?.()
  }

  const handleShare = () => {
    setShowShareMenu(!showShareMenu)
    onShare?.()
  }

  const formatCount = (count: number): string => {
    if (count >= 1000000) {
      return `${(count / 1000000).toFixed(1)}M`
    }
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}k`
    }
    return count.toString()
  }

  const getInitials = (name: string): string => {
    return name
      .split(' ')
      .map(word => word.charAt(0))
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const copyShareLink = () => {
    const url = window.location.href
    navigator.clipboard.writeText(url)
    setShowShareMenu(false)
  }

  return (
    <div className={cn('p-4 bg-white border-b border-line', className)}>
      {/* Agent Avatar and Info */}
      <div className="flex items-start gap-3 mb-4">
        {/* Avatar */}
        {avatar ? (
          <img
            src={avatar}
            alt={agentName}
            className="w-16 h-16 rounded-full object-cover ring-2 ring-sand flex-shrink-0"
          />
        ) : (
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center flex-shrink-0 shadow-md"
            style={{
              background: `linear-gradient(135deg, ${primaryColor}, ${primaryColor}dd)`,
            }}
          >
            <span className="text-white font-bold text-lg">
              {getInitials(agentName)}
            </span>
          </div>
        )}

        {/* Info */}
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-ink text-base truncate">
            {agentName}
          </h3>
          <p className="text-xs text-ink-soft mt-0.5">
            By @{creator}
          </p>
          <p className="text-xs text-ink-mute mt-1 flex items-center gap-1">
            <MessageSquare size={12} />
            {interactions} interactions
          </p>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        {/* Download Button */}
        <button
          className="p-2 rounded-lg hover:bg-sand transition-colors"
          title="Download"
        >
          <Download size={16} className="text-ink-soft" />
        </button>

        {/* Like Button with Count */}
        <button
          onClick={handleLike}
          className={cn(
            'flex items-center gap-1.5 px-3 py-2 rounded-lg transition-[color,background-color,border-color,box-shadow,opacity,transform]',
            isLiked
              ? 'text-white shadow-md'
              : 'bg-sand hover:bg-line text-ink-soft'
          )}
          style={
            isLiked
              ? {
                  background: `linear-gradient(135deg, ${primaryColor}, ${primaryColor}dd)`,
                }
              : undefined
          }
          title={isLiked ? 'Unlike' : 'Like'}
        >
          <Heart
            size={16}
            className={cn('transition-transform motion-reduce:transition-none', isLiked && 'fill-current scale-110')}
          />
          <span className="text-sm font-semibold">
            {formatCount(likeCount)}
          </span>
        </button>

        {/* Dislike Button */}
        <button
          className="p-2 rounded-lg hover:bg-sand transition-colors"
          title="Dislike"
        >
          <Heart size={16} className="text-ink-soft rotate-180" />
        </button>

        {/* Share Button */}
        <div className="relative ml-auto">
          <button
            onClick={handleShare}
            className="p-2 rounded-lg hover:bg-sand transition-colors"
            title="Share"
          >
            <Share2 size={16} className="text-ink-soft" />
          </button>

          {/* Share Menu */}
          {showShareMenu && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-[9998]"
                onClick={() => setShowShareMenu(false)}
              />
              
              {/* Menu */}
              <div className="absolute right-0 top-full mt-2 bg-white rounded-lg shadow-xl border border-line py-2 min-w-[200px] z-[9999]">
                <button
                  onClick={copyShareLink}
                  className="w-full px-4 py-2 text-left text-sm text-ink-soft hover:bg-sand flex items-center gap-3"
                >
                  <svg aria-hidden="true" className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                    />
                  </svg>
                  Copy Link
                </button>
                <button
                  onClick={() => {
                    window.open(
                      `https://twitter.com/intent/tweet?text=Check out ${agentName}&url=${encodeURIComponent(window.location.href)}`,
                      '_blank'
                    )
                    setShowShareMenu(false)
                  }}
                  className="w-full px-4 py-2 text-left text-sm text-ink-soft hover:bg-sand flex items-center gap-3"
                >
                  <svg aria-hidden="true" className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z" />
                  </svg>
                  Share on Twitter
                </button>
                <button
                  onClick={() => {
                    window.open(
                      `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(window.location.href)}`,
                      '_blank'
                    )
                    setShowShareMenu(false)
                  }}
                  className="w-full px-4 py-2 text-left text-sm text-ink-soft hover:bg-sand flex items-center gap-3"
                >
                  <svg aria-hidden="true" className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                  </svg>
                  Share on Facebook
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
