'use client'

import { Lock, ArrowRight } from 'lucide-react'
import Link from 'next/link'

interface Props {
  planTier: string
}

export function PlanGateScreen({ planTier }: Props) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-6">
      <div className="w-16 h-16 rounded-full bg-primary-50 flex items-center justify-center">
        <Lock className="h-7 w-7 text-primary-500" />
      </div>

      <div className="space-y-2">
        <span className="inline-block px-3 py-1 bg-sand text-ink-soft rounded-full text-xs font-medium">
          You&apos;re on the {planTier.charAt(0) + planTier.slice(1).toLowerCase()} plan
        </span>
        <h3 className="text-lg font-extrabold tracking-tight text-ink">Platform Engineer Agent</h3>
        <p className="text-sm text-ink-soft leading-relaxed max-w-xs">
          Available on Hobby and above. This agent can actually create and manage AI agents on your behalf through natural conversation.
        </p>
      </div>

      <ul className="text-left space-y-2 text-sm text-ink-soft w-full max-w-xs">
        {[
          'Create agents through conversation',
          'Check integration status',
          'Manage agent configurations',
          'Get tool recommendations',
        ].map((feature) => (
          <li key={feature} className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-primary-500 flex-shrink-0" />
            {feature}
          </li>
        ))}
      </ul>

      <Link
        href="/billing/subscription"
        className="flex items-center gap-2 px-5 py-2.5 bg-ink hover:bg-ink/85 text-white rounded-lg text-sm font-bold hover:opacity-90 transition-opacity shadow-sm shadow-primary-500/20"
      >
        Upgrade Plan
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  )
}
