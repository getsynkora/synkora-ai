'use client'

import { CreditTransaction } from '@/types/billing'
import { ArrowUpRight, ArrowDownRight, Clock } from 'lucide-react'

interface CreditTransactionHistoryProps {
  transactions: CreditTransaction[]
  loading?: boolean
}

export default function CreditTransactionHistory({
  transactions,
  loading = false,
}: CreditTransactionHistoryProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-line bg-white p-6">
        <div className="motion-safe:animate-pulse space-y-4">
          <div className="h-4 w-1/4 rounded bg-line" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 rounded bg-sand" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (transactions.length === 0) {
    return (
      <div className="rounded-lg border border-line bg-white p-6">
        <h3 className="mb-4 text-lg font-semibold text-ink">
          Transaction History
        </h3>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <Clock className="mb-3 h-12 w-12 text-ash" />
          <p className="text-ink-soft">No transactions yet</p>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-line bg-white p-6">
      <h3 className="mb-4 text-lg font-semibold text-ink">
        Transaction History
      </h3>
      <div className="space-y-3">
        {transactions.map((transaction) => {
          const isCredit = (transaction.credits_amount ?? 0) > 0
          return (
            <div
              key={transaction.id}
              className="flex items-center justify-between rounded-lg border border-sand p-4 transition-colors hover:bg-cream"
            >
              <div className="flex items-center space-x-3">
                <div
                  className={`rounded-full p-2 ${
                    isCredit ? 'bg-leaf-wash' : 'bg-primary-100'
                  }`}
                >
                  {isCredit ? (
                    <ArrowDownRight className="h-4 w-4 text-leaf" />
                  ) : (
                    <ArrowUpRight className="h-4 w-4 text-primary-600" />
                  )}
                </div>
                <div>
                  <p className="font-medium text-ink">
                    {transaction.description || transaction.transaction_type}
                  </p>
                  <p className="text-sm text-ink-soft">
                    {new Date(transaction.created_at).toLocaleString()}
                  </p>
                  {transaction.action_type && (
                    <p className="text-xs text-ink-mute">
                      {transaction.action_type}
                    </p>
                  )}
                </div>
              </div>
              <div className="text-right">
                <p
                  className={`text-lg font-semibold ${
                    isCredit ? 'text-leaf' : 'text-primary-600'
                  }`}
                >
                  {isCredit ? '+' : ''}
                  {(transaction.credits_amount ?? 0).toLocaleString()} credits
                </p>
                <p className="text-sm text-ink-soft">
                  Balance: {(transaction.balance_after ?? 0).toLocaleString()}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
