'use client'

import { useState } from 'react'
import { ExternalLink, AlertCircle, KeyRound, ChevronDown, ChevronUp } from 'lucide-react'

interface Props {
  provider: string
  message: string
  connect_url: string
  type?: 'oauth' | 'api_key'
  compact?: boolean
}

export function IntegrationPromptCard({ provider, message, connect_url, type = 'oauth', compact = false }: Props) {
  const [isMinimized, setIsMinimized] = useState(false)
  const displayName = provider.charAt(0).toUpperCase() + provider.slice(1).replace(/_/g, ' ')
  const isApiKey = type === 'api_key'
  const label = isApiKey ? `${displayName} API key required` : `${displayName} not connected`
  const action = isApiKey ? `Add API Key` : `Connect`

  if (compact) {
    return (
      <p className="flex items-center gap-1.5 text-sm text-gold">
        <AlertCircle className="h-3.5 w-3.5 shrink-0" />
        {label} —{' '}
        <a href={connect_url} className="font-semibold underline underline-offset-2 hover:opacity-70">
          {action}
        </a>
      </p>
    )
  }

  if (isMinimized) {
    return (
      <div className="overflow-hidden rounded-[1.45rem] border border-tan bg-cream p-4 shadow-soft">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[0.95rem] bg-ink text-white shadow-soft">
            {isApiKey ? <KeyRound className="h-4.5 w-4.5" /> : <AlertCircle className="h-4.5 w-4.5" />}
          </div>

          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold text-gold">Action required</p>
            <p className="mt-1 truncate text-sm font-semibold tracking-[-0.02em] text-ink">{label}</p>
          </div>

          <div className="flex items-center gap-2">
            <a
              href={connect_url}
              className="hidden sm:inline-flex items-center gap-2 rounded-[0.95rem] border border-tan bg-white/75 px-3 py-2 text-xs font-semibold text-night transition-colors hover:bg-white"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              {action} {displayName}
            </a>
            <button
              type="button"
              onClick={() => setIsMinimized(false)}
              aria-label={`Expand ${displayName} integration prompt`}
              className="inline-flex h-10 w-10 items-center justify-center rounded-[0.95rem] border border-tan bg-white/75 text-bark transition-colors hover:bg-white hover:text-ink"
            >
              <ChevronDown className="h-4 w-4" />
            </button>
          </div>
        </div>

        <a
          href={connect_url}
          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-[0.95rem] border border-tan bg-white/75 px-3 py-2.5 text-sm font-semibold text-night transition-colors hover:bg-white sm:hidden"
        >
          <ExternalLink className="h-4 w-4" />
          {action} {displayName}
        </a>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-[1.8rem] border border-tan bg-cream p-5 shadow-soft">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[1rem] bg-ink text-white shadow-soft">
          {isApiKey ? <KeyRound className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold text-gold">Action required</p>
              <p className="mt-1 text-[1.02rem] font-semibold tracking-[-0.03em] text-ink">{label}</p>
            </div>
            <button
              type="button"
              onClick={() => setIsMinimized(true)}
              aria-label={`Minimize ${displayName} integration prompt`}
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[0.95rem] border border-tan bg-white/75 text-bark transition-colors hover:bg-white hover:text-ink"
            >
              <ChevronUp className="h-4 w-4" />
            </button>
          </div>
          <p className="mt-1 text-sm leading-6 text-bark">{message}</p>
        </div>
      </div>

      <a
        href={connect_url}
        className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-[1.15rem] bg-ink px-4 py-3 text-sm font-semibold text-paper transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-200 hover:-translate-y-0.5 hover:bg-ink shadow-soft"
      >
        <ExternalLink className="h-4 w-4" />
        {isApiKey ? `Add ${displayName} API Key` : `Connect ${displayName}`}
      </a>
    </div>
  )
}
