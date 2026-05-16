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
    <section className="bg-[#f7f2e7] px-4 py-14 sm:px-6 sm:py-20">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="mb-4 text-4xl font-medium tracking-[-0.05em] text-[#171717]">Simple, Transparent Pricing</h2>
          <p className="text-xl leading-relaxed text-[#575149]">Start free. Self-host forever for free. Scale on cloud as you grow.</p>
        </div>

        {loading ? (
          <div className="grid md:grid-cols-3 gap-6 mb-10">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse rounded-[2rem] border border-black/10 bg-white/60 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
                <div className="mb-2 h-6 w-24 rounded bg-black/10" />
                <div className="mb-4 h-4 w-32 rounded bg-black/5" />
                <div className="mb-4 h-8 w-20 rounded bg-black/10" />
                <div className="space-y-2">
                  <div className="h-4 w-full rounded bg-black/5" />
                  <div className="h-4 w-3/4 rounded bg-black/5" />
                  <div className="h-4 w-5/6 rounded bg-black/5" />
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
                <div key={plan.id} className={`relative rounded-[2rem] bg-white/60 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)] ${isPopular ? 'ring-2 ring-[#79dfbc] shadow-[0_24px_60px_rgba(0,0,0,0.08)]' : 'border border-black/10'}`}>
                  {isPopular && (
                    <div className="absolute left-1/2 -top-3 -translate-x-1/2 rounded-full bg-[#191919] px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#f7f2e7]">
                      Popular
                    </div>
                  )}
                  <h3 className="mb-1 text-xl font-semibold tracking-[-0.03em] text-[#171717]">{plan.name}</h3>
                  <p className="mb-4 text-sm text-[#6d675f]">{plan.description || 'Choose this plan'}</p>
                  <div className="mb-4">
                    <span className="text-3xl font-semibold text-[#171717]">${plan.price_monthly || 0}</span>
                    <span className="text-[#6d675f]">/month</span>
                  </div>
                  <ul className="space-y-2 mb-6">
                    {features.slice(0, 3).map((feature, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm text-[#575149]">
                        <svg className="h-4 w-4 text-[#2d8b69]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
              <div key={i} className={`relative rounded-[2rem] bg-white/60 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)] ${plan.popular ? 'ring-2 ring-[#79dfbc] shadow-[0_24px_60px_rgba(0,0,0,0.08)]' : 'border border-black/10'}`}>
                {plan.popular && (
                  <div className="absolute left-1/2 -top-3 -translate-x-1/2 rounded-full bg-[#191919] px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#f7f2e7]">
                    Popular
                  </div>
                )}
                <h3 className="mb-1 text-xl font-semibold tracking-[-0.03em] text-[#171717]">{plan.name}</h3>
                <p className="mb-4 text-sm text-[#6d675f]">{plan.desc}</p>
                <div className="mb-4">
                  <span className="text-3xl font-semibold text-[#171717]">{plan.price}</span>
                  {plan.price !== 'Free' && <span className="text-[#6d675f]">/month</span>}
                </div>
                <ul className="space-y-2">
                  {plan.features.map((f, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm text-[#575149]">
                      <svg className="h-4 w-4 text-[#2d8b69]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
          <Link href="/pricing" className="inline-flex items-center gap-2 font-semibold text-[#1f1d19] hover:text-black">
            View all pricing details
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </section>
  )
}
