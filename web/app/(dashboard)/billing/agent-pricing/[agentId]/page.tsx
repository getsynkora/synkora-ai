'use client'

import { useParams, useSearchParams } from 'next/navigation'
import { useAgentPricing } from '@/hooks/useBilling'
import {
  AgentPricingForm,
  AgentRevenueCard,
} from '@/components/billing'
import { Loader2, ArrowLeft, DollarSign, TrendingUp, ChevronRight } from 'lucide-react'
import Link from 'next/link'

export default function AgentPricingPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const agentId = params.agentId as string
  const agentSlug = searchParams.get('from')
  const backHref = agentSlug ? `/agents/${agentSlug}/edit?tab=landing-page` : '/billing'

  const {
    pricing,
    revenue,
    earnings,
    loading,
    error,
    updatePricing
  } = useAgentPricing(agentId)

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        {/* Breadcrumb */}
        <nav className="mb-4 flex items-center gap-1.5 text-sm text-gray-500">
          {agentSlug ? (
            <>
              <Link href="/agents" className="hover:text-gray-900">Agents</Link>
              <ChevronRight className="h-3.5 w-3.5" />
              <Link href={`/agents/${agentSlug}/edit?tab=landing-page`} className="hover:text-gray-900">
                {agentSlug}
              </Link>
              <ChevronRight className="h-3.5 w-3.5" />
              <span className="text-gray-900 font-medium">Monetization</span>
            </>
          ) : (
            <>
              <Link href="/billing" className="hover:text-gray-900">Billing</Link>
              <ChevronRight className="h-3.5 w-3.5" />
              <span className="text-gray-900 font-medium">Monetization</span>
            </>
          )}
        </nav>

        <Link
          href={backHref}
          className="mb-4 inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {agentSlug ? 'Back to Agent' : 'Back to Billing'}
        </Link>
        <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Agent Monetization</h1>
        <p className="mt-2 text-gray-600">
          Configure pricing and view revenue for your agent
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Earnings Summary */}
      {earnings && (
        <div className="mb-8 grid gap-6 md:grid-cols-3">
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Your Earnings (30d)</p>
                <p className="mt-2 text-xl sm:text-3xl font-bold text-gray-900">
                  ${Number(earnings.creator_earnings_usd ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="rounded-full bg-primary-100 p-3">
                <DollarSign className="h-6 w-6 text-primary-600" />
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Revenue (30d)</p>
                <p className="mt-2 text-xl sm:text-3xl font-bold text-gray-900">
                  ${Number(earnings.total_revenue_usd ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="rounded-full bg-blue-100 p-3">
                <TrendingUp className="h-6 w-6 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Uses (30d)</p>
                <p className="mt-2 text-xl sm:text-3xl font-bold text-gray-900">
                  {earnings.total_transactions || 0}
                </p>
              </div>
              <div className="rounded-full bg-purple-100 p-3">
                <TrendingUp className="h-6 w-6 text-purple-600" />
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Pricing Configuration */}
        <div>
          <h2 className="mb-4 text-xl font-semibold text-gray-900">
            Pricing Configuration
          </h2>
          <AgentPricingForm
            agentId={agentId}
            initialPricing={pricing || undefined}
            onSubmit={updatePricing}
          />
        </div>

        {/* Revenue Overview */}
        <div>
          <h2 className="mb-4 text-xl font-semibold text-gray-900">
            Revenue Overview
          </h2>
          <AgentRevenueCard
            revenue={revenue}
          />
        </div>
      </div>

      {/* Revenue Details */}
      {revenue && revenue.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-4 text-xl font-semibold text-gray-900">
            Revenue History
          </h2>
          <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Uses
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Revenue
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Creator Share
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {revenue.map((item) => (
                  <tr key={item.id}>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      Revenue
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      {item.credits_used}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      ${Number(item.revenue_amount ?? 0).toFixed(2)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-primary-600">
                      ${Number(item.creator_earnings ?? 0).toFixed(2)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm">
                      <span
                        className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                          item.status === 'paid'
                            ? 'bg-green-100 text-green-800'
                            : item.status === 'pending'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {item.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Information Cards */}
      <div className="mt-8 grid gap-6 md:grid-cols-2">
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-6">
          <h3 className="mb-2 text-lg font-semibold text-blue-900">
            Per-Use Pricing
          </h3>
          <p className="text-sm text-blue-800">
            Charge users credits each time they use your agent. You earn 70% of the
            revenue, and the platform takes 30%.
          </p>
        </div>

        <div className="rounded-lg border border-purple-200 bg-purple-50 p-6">
          <h3 className="mb-2 text-lg font-semibold text-purple-900">
            Subscription Pricing
          </h3>
          <p className="text-sm text-purple-800">
            Offer unlimited access to your agent for a monthly fee. You earn 80% of
            the revenue, and the platform takes 20%.
          </p>
        </div>
      </div>
    </div>
  )
}
