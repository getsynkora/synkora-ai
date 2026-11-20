'use client'

import { ActionUsageBreakdown } from '@/types/billing'
import { BarChart3 } from 'lucide-react'

interface UsageAnalyticsChartProps {
  analytics: ActionUsageBreakdown[]
  loading?: boolean
}

export default function UsageAnalyticsChart({
  analytics,
  loading = false,
}: UsageAnalyticsChartProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-line bg-white p-6">
        <div className="motion-safe:animate-pulse space-y-4">
          <div className="h-4 w-1/4 rounded bg-line" />
          <div className="h-64 rounded bg-sand" />
        </div>
      </div>
    )
  }

  if (analytics.length === 0) {
    return (
      <div className="rounded-lg border border-line bg-white p-6">
        <h3 className="mb-4 text-lg font-semibold text-ink">
          Usage Analytics
        </h3>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <BarChart3 className="mb-3 h-12 w-12 text-ash" />
          <p className="text-ink-soft">No usage data yet</p>
        </div>
      </div>
    )
  }

  const maxCredits = Math.max(...analytics.map((a) => a.credits_used || 0))

  return (
    <div className="rounded-lg border border-line bg-white p-6">
      <h3 className="mb-4 text-lg font-semibold text-ink">
        Usage Analytics
      </h3>
      <div className="space-y-4">
        {analytics.map((item, index) => {
          const creditsUsed = item.credits_used || 0
          const percentage = maxCredits > 0 ? (creditsUsed / maxCredits) * 100 : 0
          return (
            <div key={item.action_type || index} className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-ink">
                  {item.action_type || 'Unknown'}
                </span>
                <span className="text-ink-soft">
                  {creditsUsed.toLocaleString()} credits
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-sand">
                <div
                  className="h-full rounded-full bg-primary-500 transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                  style={{ width: `${percentage}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-xs text-ink-mute">
                <span>{item.count || 0} uses</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
