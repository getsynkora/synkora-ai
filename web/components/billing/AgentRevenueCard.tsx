'use client'

import { AgentRevenue } from '@/types/billing'
import { DollarSign, TrendingUp } from 'lucide-react'

interface AgentRevenueCardProps {
  revenue: AgentRevenue[]
  loading?: boolean
}

export default function AgentRevenueCard({
  revenue,
  loading = false,
}: AgentRevenueCardProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-4 w-1/4 rounded bg-gray-200" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 rounded bg-gray-100" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (revenue.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h3 className="mb-4 text-lg font-semibold text-gray-900">
          Agent Revenue
        </h3>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <DollarSign className="mb-3 h-12 w-12 text-gray-400" />
          <p className="text-gray-600">No revenue data yet</p>
        </div>
      </div>
    )
  }

  const totalRevenue = revenue.reduce((sum, r) => sum + Number(r.revenue_amount ?? 0), 0)
  const totalCreatorShare = revenue.reduce(
    (sum, r) => sum + Number(r.creator_earnings ?? 0),
    0
  )

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h3 className="mb-4 text-lg font-semibold text-gray-900">
        Agent Revenue
      </h3>

      <div className="mb-6 grid grid-cols-2 gap-4">
        <div className="rounded-lg bg-primary-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-primary-700">Total Revenue</span>
            <TrendingUp className="h-4 w-4 text-primary-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-primary-900">
            ${totalRevenue.toFixed(2)}
          </p>
        </div>
        <div className="rounded-lg bg-blue-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-blue-700">Your Share</span>
            <DollarSign className="h-4 w-4 text-blue-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-blue-900">
            ${totalCreatorShare.toFixed(2)}
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {revenue.map((item) => (
          <div
            key={item.id}
            className="flex items-center justify-between rounded-lg border border-gray-100 p-4 transition-colors hover:bg-gray-50"
          >
            <div>
              <p className="font-medium text-gray-900">Agent Revenue</p>
              <p className="text-sm text-gray-600">
                {new Date(item.created_at).toLocaleDateString()}
                {item.payout_date && ` - Paid: ${new Date(item.payout_date).toLocaleDateString()}`}
              </p>
              <p className="text-xs text-gray-500">
                Status: <span className={`font-medium ${item.status === 'paid' ? 'text-green-600' : item.status === 'pending' ? 'text-yellow-600' : 'text-red-600'}`}>{item.status}</span>
              </p>
            </div>
            <div className="text-right">
              <p className="text-lg font-semibold text-gray-900">
                ${Number(item.revenue_amount ?? 0).toFixed(2)}
              </p>
              <p className="text-sm text-primary-600">
                Your share: ${Number(item.creator_earnings ?? 0).toFixed(2)}
              </p>
              <p className="text-xs text-gray-500">
                {item.credits_used} credits used
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
