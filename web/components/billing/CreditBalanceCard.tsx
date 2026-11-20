'use client'

import { CreditBalance } from '@/types/billing'
import { TrendingUp } from 'lucide-react'

interface CreditBalanceCardProps {
  balance: CreditBalance
}

export default function CreditBalanceCard({ balance }: CreditBalanceCardProps) {
  const usagePercentage = balance.total_credits > 0
    ? ((balance.total_credits - balance.available_credits) / balance.total_credits) * 100
    : 0

  const isLow = usagePercentage > 80

  return (
    <div className="rounded-lg border border-line bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-ink">Credit Balance</h3>
        {isLow && (
          <div className="flex items-center text-sm text-primary-600">
            <TrendingUp className="mr-1 h-4 w-4" />
            <span>Low</span>
          </div>
        )}
      </div>

      <div className="mb-4">
        <div className="flex items-baseline">
          <span className="text-4xl font-bold text-ink">
            {balance.available_credits.toLocaleString()}
          </span>
          <span className="ml-2 text-ink-soft">
            / {balance.total_credits.toLocaleString()} credits
          </span>
        </div>
      </div>

      <div className="mb-2">
        <div className="h-2 w-full overflow-hidden rounded-full bg-line">
          <div
            className={`h-full transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
              isLow ? 'bg-primary-600' : 'bg-primary-500'
            }`}
            style={{ width: `${Math.min(usagePercentage, 100)}%` }}
          />
        </div>
      </div>

      <div className="flex justify-between text-sm text-ink-soft">
        <span>{usagePercentage.toFixed(1)}% used</span>
        {isLow && (
          <span className="font-semibold text-primary-600">Low balance</span>
        )}
      </div>

      {balance.next_reset_at && (
        <div className="mt-4 border-t border-line pt-4">
          <p className="text-sm text-ink-soft">
            Next reset: {new Date(balance.next_reset_at).toLocaleDateString()}
          </p>
        </div>
      )}
    </div>
  )
}
