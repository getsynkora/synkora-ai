'use client'

import { QuotaPoolUsage } from '@/types/billing'

interface QuotaUsageCardProps {
  pools: QuotaPoolUsage[]
}

export default function QuotaUsageCard({ pools }: QuotaUsageCardProps) {
  const resets = new Date(pools[0].period_end).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

  return (
    <div className="rounded-lg border border-line bg-white p-6">
      <div className="mb-5 flex items-baseline justify-between gap-4">
        <h3 className="text-lg font-semibold text-ink">Included messages</h3>
        <p className="text-sm text-ink-soft">Resets {resets}</p>
      </div>

      <ul className="space-y-5">
        {pools.map((pool) => {
          const percent = pool.limit > 0 ? Math.min((pool.used / pool.limit) * 100, 100) : 100
          const full = pool.remaining === 0
          const low = !full && percent >= 80

          return (
            <li key={pool.key}>
              <div className="mb-2 flex items-baseline justify-between gap-4">
                <span className="text-sm font-medium text-ink">{pool.label}</span>
                <span className="text-sm text-ink-soft">
                  {pool.used.toLocaleString()} of {pool.limit.toLocaleString()} used
                </span>
              </div>
              <div
                className="h-2 w-full overflow-hidden rounded-full bg-line"
                role="progressbar"
                aria-label={pool.label}
                aria-valuemin={0}
                aria-valuemax={pool.limit}
                aria-valuenow={Math.min(pool.used, pool.limit)}
              >
                <div
                  className={`h-full ${full || low ? 'bg-danger' : 'bg-ink'}`}
                  style={{ width: `${percent}%` }}
                />
              </div>
              {full && <p className="mt-1.5 text-sm text-danger">Limit reached. Upgrade your plan to keep going.</p>}
              {low && <p className="mt-1.5 text-sm text-ink-soft">{pool.remaining.toLocaleString()} left this month.</p>}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
