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
      <p className="flex items-center gap-1.5 text-sm text-[#9a6a17]">
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
      <div className="overflow-hidden rounded-[1.45rem] border border-[#e7d2ab] bg-[linear-gradient(180deg,_rgba(255,251,242,0.98),_rgba(248,239,216,0.96))] p-4 shadow-[0_18px_42px_-34px_rgba(114,79,21,0.24)]">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[0.95rem] bg-[#171717] text-white shadow-[0_18px_34px_-24px_rgba(0,0,0,0.42)]">
            {isApiKey ? <KeyRound className="h-4.5 w-4.5" /> : <AlertCircle className="h-4.5 w-4.5" />}
          </div>

          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#9a6a17]">Action required</p>
            <p className="mt-1 truncate text-sm font-semibold tracking-[-0.02em] text-[#171717]">{label}</p>
          </div>

          <div className="flex items-center gap-2">
            <a
              href={connect_url}
              className="hidden sm:inline-flex items-center gap-2 rounded-[0.95rem] border border-[#d8c094] bg-white/75 px-3 py-2 text-xs font-semibold text-[#3f3321] transition-colors hover:bg-white"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              {action} {displayName}
            </a>
            <button
              type="button"
              onClick={() => setIsMinimized(false)}
              aria-label={`Expand ${displayName} integration prompt`}
              className="inline-flex h-10 w-10 items-center justify-center rounded-[0.95rem] border border-[#d8c094] bg-white/75 text-[#6c5c3f] transition-colors hover:bg-white hover:text-[#171717]"
            >
              <ChevronDown className="h-4 w-4" />
            </button>
          </div>
        </div>

        <a
          href={connect_url}
          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-[0.95rem] border border-[#d8c094] bg-white/75 px-3 py-2.5 text-sm font-semibold text-[#3f3321] transition-colors hover:bg-white sm:hidden"
        >
          <ExternalLink className="h-4 w-4" />
          {action} {displayName}
        </a>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-[1.8rem] border border-[#e7d2ab] bg-[linear-gradient(180deg,_rgba(255,251,242,0.98),_rgba(248,239,216,0.96))] p-5 shadow-[0_24px_60px_-40px_rgba(114,79,21,0.28)]">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[1rem] bg-[#171717] text-white shadow-[0_18px_34px_-24px_rgba(0,0,0,0.42)]">
          {isApiKey ? <KeyRound className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#9a6a17]">Action required</p>
              <p className="mt-1 text-[1.02rem] font-semibold tracking-[-0.03em] text-[#171717]">{label}</p>
            </div>
            <button
              type="button"
              onClick={() => setIsMinimized(true)}
              aria-label={`Minimize ${displayName} integration prompt`}
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[0.95rem] border border-[#d8c094] bg-white/75 text-[#6c5c3f] transition-colors hover:bg-white hover:text-[#171717]"
            >
              <ChevronUp className="h-4 w-4" />
            </button>
          </div>
          <p className="mt-1 text-sm leading-6 text-[#6c5c3f]">{message}</p>
        </div>
      </div>

      <a
        href={connect_url}
        className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-[1.15rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-[#faf5ea] transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#0f0f0f] shadow-[0_22px_44px_-28px_rgba(0,0,0,0.46)]"
      >
        <ExternalLink className="h-4 w-4" />
        {isApiKey ? `Add ${displayName} API Key` : `Connect ${displayName}`}
      </a>
    </div>
  )
}
