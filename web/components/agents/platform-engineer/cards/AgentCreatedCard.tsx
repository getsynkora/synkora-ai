'use client'

import { CheckCircle, ExternalLink, MessageSquare } from 'lucide-react'
import Link from 'next/link'

interface Props {
  agentName: string
  agentSlug?: string
}

export function AgentCreatedCard({ agentName, agentSlug }: Props) {
  const encoded = encodeURIComponent(agentSlug || agentName)

  return (
    <div className="overflow-hidden rounded-[1.8rem] border border-[#cfe1d5] bg-[linear-gradient(180deg,_rgba(247,255,250,0.98),_rgba(237,248,241,0.96))] p-5 shadow-[0_26px_64px_-42px_rgba(34,60,42,0.28)]">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[1rem] bg-[#171717] text-white shadow-[0_18px_34px_-24px_rgba(0,0,0,0.42)]">
          <CheckCircle className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#5c8a69]">Provisioned</p>
          <p className="mt-1 text-[1.05rem] font-semibold tracking-[-0.03em] text-[#171717]">
            Agent created: {agentName}
          </p>
          <p className="mt-1 text-sm leading-6 text-[#4e5e54]">
            Open the agent profile to review the configuration, or jump straight into chat.
          </p>
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
        <Link
          href={`/agents/${encoded}/view`}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-[1.15rem] border border-[#ceddd2] bg-white/90 px-4 py-3 text-sm font-semibold text-[#223328] transition-all duration-200 hover:-translate-y-0.5 hover:bg-white"
        >
          <ExternalLink className="h-4 w-4" />
          View Agent
        </Link>
        <Link
          href={`/agents/${encoded}/chat`}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-[1.15rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-[#faf5ea] transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#0f0f0f] shadow-[0_22px_44px_-28px_rgba(0,0,0,0.48)]"
        >
          <MessageSquare className="h-4 w-4" />
          Chat Now
        </Link>
      </div>
    </div>
  )
}
