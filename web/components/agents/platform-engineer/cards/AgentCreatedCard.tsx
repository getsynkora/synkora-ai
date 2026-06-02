'use client'

import { CheckCircle } from 'lucide-react'
import Link from 'next/link'

interface Props {
  agentName: string
  agentSlug?: string
}

export function AgentCreatedCard({ agentName, agentSlug }: Props) {
  const encoded = encodeURIComponent(agentSlug || agentName)

  return (
    <div className="flex items-center gap-2 text-sm text-[#5c8a69]">
      <CheckCircle className="h-4 w-4 shrink-0" />
      <span>
        Agent <Link href={`/agents/${encoded}/view`} className="font-semibold text-[#223328] underline underline-offset-2 hover:opacity-70">{agentName}</Link> created.
      </span>
    </div>
  )
}
