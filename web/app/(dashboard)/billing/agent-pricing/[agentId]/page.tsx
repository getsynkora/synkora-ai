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
        <Loader2 className="h-8 w-8 motion-safe:animate-spin text-primary-500" />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        {/* Breadcrumb */}
        <nav className="mb-4 flex items-center gap-1.5 text-sm text-ink-mute">
          {agentSlug ? (
            <>
              <Link href="/agents" className="hover:text-ink">Agents</Link>
              <ChevronRight className="h-3.5 w-3.5" />
              <Link href={`/agents/${agentSlug}/edit?tab=landing-page`} className="hover:text-ink">
                {agentSlug}
              </Link>
              <ChevronRight className="h-3.5 w-3.5" />
              <span className="text-ink font-medium">Monetization</span>
            </>
          ) : (
            <>
              <Link href="/billing" className="hover:text-ink">Billing</Link>
              <ChevronRight className="h-3.5 w-3.5" />
              <span className="text-ink font-medium">Monetization</span>
            </>
          )}
        </nav>

        <Link
          href={backHref}
          className="mb-4 inline-flex items-center text-sm text-ink-soft hover:text-ink"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {agentSlug ? 'Back to Agent' : 'Back to Billing'}
        </Link>
        <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Agent Monetization</h1>
        <p className="mt-2 text-ink-soft">
          Configure pricing and view revenue for your agent
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-blush bg-blush-wash p-4">
          <p className="text-sm text-wine">{error}</p>
        </div>
      )}

      {/* Earnings Summary */}
      {earnings && (
        <div className="mb-8 grid gap-6 md:grid-cols-3">
          <div className="rounded-lg border border-line bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-ink-soft">Your Earnings (30d)</p>
                <p className="mt-2 text-xl sm:text-3xl font-bold text-ink">
                  ${Number(earnings.creator_earnings_usd ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="rounded-full bg-primary-100 p-3">
                <DollarSign className="h-6 w-6 text-primary-600" />
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-line bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-ink-soft">Total Revenue (30d)</p>
                <p className="mt-2 text-xl sm:text-3xl font-bold text-ink">
                  ${Number(earnings.total_revenue_usd ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="rounded-full bg-sky-wash p-3">
                <TrendingUp className="h-6 w-6 text-azure" />
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-line bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-ink-soft">Total Uses (30d)</p>
                <p className="mt-2 text-xl sm:text-3xl font-bold text-ink">
                  {earnings.total_transactions || 0}
                </p>
              </div>
              <div className="rounded-full bg-sand-deep p-3">
                <TrendingUp className="h-6 w-6 text-plum" />
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Pricing Configuration */}
        <div>
          <h2 className="mb-4 text-xl font-semibold text-ink">
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
          <h2 className="mb-4 text-xl font-semibold text-ink">
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
          <h2 className="mb-4 text-xl font-semibold text-ink">
            Revenue History
          </h2>
          <div className="overflow-x-auto rounded-lg border border-line bg-white">
            <table className="min-w-full divide-y divide-line">
              <thead className="bg-cream">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                    Uses
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                    Revenue
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                    Creator Share
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-white">
                {revenue.map((item) => (
                  <tr key={item.id}>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-ink">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-ink">
                      Revenue
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-ink">
                      {item.credits_used}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-ink">
                      ${Number(item.revenue_amount ?? 0).toFixed(2)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-primary-600">
                      ${Number(item.creator_earnings ?? 0).toFixed(2)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm">
                      <span
                        className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                          item.status === 'paid'
                            ? 'bg-leaf-wash text-forest'
                            : item.status === 'pending'
                            ? 'bg-sand-deep text-gold'
                            : 'bg-sand text-ink'
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
        <div className="rounded-lg border border-sky-wash bg-sky-wash p-6">
          <h3 className="mb-2 text-lg font-semibold text-azure">
            Per-Use Pricing
          </h3>
          <p className="text-sm text-azure">
            Charge users credits each time they use your agent. You earn 70% of the
            revenue, and the platform takes 30%.
          </p>
        </div>

        <div className="rounded-lg border border-blush bg-blush-wash p-6">
          <h3 className="mb-2 text-lg font-semibold text-wine">
            Subscription Pricing
          </h3>
          <p className="text-sm text-wine">
            Offer unlimited access to your agent for a monthly fee. You earn 80% of
            the revenue, and the platform takes 20%.
          </p>
        </div>
      </div>
    </div>
  )
}
