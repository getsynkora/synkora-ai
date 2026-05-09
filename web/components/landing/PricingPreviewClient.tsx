'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { ArrowRight } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface PricingPlan {
  id: string
  name: string
  description: string
  price_monthly: number
  price_yearly: number | null
  credits_monthly: number
  max_agents: number
  max_team_members: number
  features: Record<string, boolean | string | number>
  is_active: boolean
  is_popular?: boolean
}

const staticPlans = [
  { name: 'Self-hosted', price: 'Free', desc: 'Run on your own infrastructure. MIT licensed. No limits.', features: ['Unlimited agents', 'Unlimited team members', 'All features included', 'Your own LLM keys'], popular: false },
  { name: 'Cloud Starter', price: '$29', desc: 'Managed cloud hosting for small teams.', features: ['5 agents', '3 team members', '50,000 credits/month', 'Slack + web widget'], popular: true },
  { name: 'Cloud Pro', price: '$99', desc: 'For teams shipping production AI products.', features: ['Unlimited agents', 'Unlimited team members', '500,000 credits/month', 'All channels + priority support'], popular: false },
]

export default function PricingPreviewClient() {
  const [pricingPlans, setPricingPlans] = useState<PricingPlan[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchPricingPlans = async () => {
      try {
        const response = await fetch(`${API_URL}/api/v1/billing/plans`)
        const data = await response.json()
        const plansArray = Array.isArray(data) ? data : (data.data || data.plans || [])
        if (plansArray.length > 0) {
          const sorted = plansArray
            .filter((p: PricingPlan) => p.is_active !== false)
            .sort((a: PricingPlan, b: PricingPlan) => (a.price_monthly || 0) - (b.price_monthly || 0))
            .slice(0, 3)
          setPricingPlans(sorted)
        }
      } catch {
        // fall through to static plans
      } finally {
        setLoading(false)
      }
    }
    fetchPricingPlans()
  }, [])

  return (
    <section className="py-14 sm:py-20 px-4 sm:px-6 bg-gray-50">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">Simple, Transparent Pricing</h2>
          <p className="text-xl text-gray-600">Start free. Self-host forever for free. Scale on cloud as you grow.</p>
        </div>

        {loading ? (
          <div className="grid md:grid-cols-3 gap-6 mb-10">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm animate-pulse">
                <div className="h-6 bg-gray-200 rounded w-24 mb-2" />
                <div className="h-4 bg-gray-100 rounded w-32 mb-4" />
                <div className="h-8 bg-gray-200 rounded w-20 mb-4" />
                <div className="space-y-2">
                  <div className="h-4 bg-gray-100 rounded w-full" />
                  <div className="h-4 bg-gray-100 rounded w-3/4" />
                  <div className="h-4 bg-gray-100 rounded w-5/6" />
                </div>
              </div>
            ))}
          </div>
        ) : pricingPlans.length > 0 ? (
          <div className={`grid gap-6 mb-10 ${pricingPlans.length === 1 ? 'max-w-md mx-auto' : pricingPlans.length === 2 ? 'md:grid-cols-2 max-w-3xl mx-auto' : 'md:grid-cols-3'}`}>
            {pricingPlans.map((plan, idx) => {
              const isPopular = plan.is_popular || (pricingPlans.length >= 3 && idx === 1)
              const features: string[] = []
              if (plan.credits_monthly) features.push(`${plan.credits_monthly.toLocaleString()} credits/month`)
              if (plan.max_agents === -1 || plan.max_agents > 100) features.push('Unlimited agents')
              else if (plan.max_agents) features.push(`${plan.max_agents} agent${plan.max_agents > 1 ? 's' : ''}`)
              if (plan.max_team_members === -1 || plan.max_team_members > 100) features.push('Unlimited team members')
              else if (plan.max_team_members > 1) features.push(`${plan.max_team_members} team members`)

              return (
                <div key={plan.id} className={`relative bg-white rounded-2xl p-6 ${isPopular ? 'ring-2 ring-red-500 shadow-xl' : 'border border-gray-200 shadow-sm'}`}>
                  {isPopular && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-red-500 text-white text-xs font-semibold rounded-full">
                      Popular
                    </div>
                  )}
                  <h3 className="text-xl font-bold text-gray-900 mb-1">{plan.name}</h3>
                  <p className="text-sm text-gray-500 mb-4">{plan.description || 'Choose this plan'}</p>
                  <div className="mb-4">
                    <span className="text-3xl font-bold text-gray-900">${plan.price_monthly || 0}</span>
                    <span className="text-gray-500">/month</span>
                  </div>
                  <ul className="space-y-2 mb-6">
                    {features.slice(0, 3).map((feature, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm text-gray-600">
                        <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="grid md:grid-cols-3 gap-6 mb-10">
            {staticPlans.map((plan, i) => (
              <div key={i} className={`relative bg-white rounded-2xl p-6 ${plan.popular ? 'ring-2 ring-red-500 shadow-xl' : 'border border-gray-200 shadow-sm'}`}>
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-red-500 text-white text-xs font-semibold rounded-full">
                    Popular
                  </div>
                )}
                <h3 className="text-xl font-bold text-gray-900 mb-1">{plan.name}</h3>
                <p className="text-sm text-gray-500 mb-4">{plan.desc}</p>
                <div className="mb-4">
                  <span className="text-3xl font-bold text-gray-900">{plan.price}</span>
                  {plan.price !== 'Free' && <span className="text-gray-500">/month</span>}
                </div>
                <ul className="space-y-2">
                  {plan.features.map((f, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm text-gray-600">
                      <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        <div className="text-center">
          <Link href="/pricing" className="inline-flex items-center gap-2 text-red-600 hover:text-red-700 font-semibold">
            View all pricing details
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </section>
  )
}
