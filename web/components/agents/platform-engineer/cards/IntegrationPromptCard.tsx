'use client'

import { ExternalLink, AlertCircle, KeyRound } from 'lucide-react'

interface Props {
  provider: string
  message: string
  connect_url: string
  type?: 'oauth' | 'api_key'
}

export function IntegrationPromptCard({ provider, message, connect_url, type = 'oauth' }: Props) {
  const displayName = provider.charAt(0).toUpperCase() + provider.slice(1).replace(/_/g, ' ')
  const isApiKey = type === 'api_key'

  return (
    <div className="overflow-hidden rounded-[1.8rem] border border-[#e7d2ab] bg-[linear-gradient(180deg,_rgba(255,251,242,0.98),_rgba(248,239,216,0.96))] p-5 shadow-[0_24px_60px_-40px_rgba(114,79,21,0.28)]">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[1rem] bg-[#171717] text-white shadow-[0_18px_34px_-24px_rgba(0,0,0,0.42)]">
          {isApiKey
            ? <KeyRound className="h-5 w-5" />
            : <AlertCircle className="h-5 w-5" />
          }
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#9a6a17]">Action required</p>
          <p className="mt-1 text-[1.02rem] font-semibold tracking-[-0.03em] text-[#171717]">
            {isApiKey ? `${displayName} API key required` : `${displayName} not connected`}
          </p>
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
