'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { Check, Zap, Building2, Sparkles, ArrowRight, Loader2 } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface SubscriptionPlan {
  id: string
  name: string
  description: string
  price_monthly: number
  price_yearly: number | null
  credits_monthly: number
  max_agents: number
  max_knowledge_bases?: number
  max_team_members: number
  features: string[] | Record<string, boolean | string | number>
  is_active: boolean
  is_popular?: boolean
  display_order?: number
}

const planAccentStyles = [
  {
    surface: ' bg-white',
    iconWrap: 'bg-sand-deep',
    iconColor: 'text-rust',
    button: 'bg-white/78 hover:bg-white text-ink border border-black/10',
  },
  {
    surface: ' bg-white',
    iconWrap: 'bg-leaf-wash',
    iconColor: 'text-leaf',
    button: 'bg-ink hover:bg-black text-paper',
  },
  {
    surface: ' bg-white',
    iconWrap: 'bg-sand-deep',
    iconColor: 'text-warn',
    button: 'bg-white/78 hover:bg-white text-ink border border-black/10',
  },
]

const getIconForPlan = (name: string, index: number) => {
  const nameLower = name.toLowerCase()
  if (nameLower.includes('free') || nameLower.includes('starter')) {
    return <Sparkles className="w-5 h-5 text-rust" />
  }
  if (nameLower.includes('pro') || nameLower.includes('professional')) {
    return <Zap className="w-5 h-5 text-leaf" />
  }
  if (nameLower.includes('enterprise') || nameLower.includes('business')) {
    return <Building2 className="w-5 h-5 text-warn" />
  }
  // Fallback based on index
  if (index === 0) return <Sparkles className="w-5 h-5 text-rust" />
  if (index === 1) return <Zap className="w-5 h-5 text-leaf" />
  return <Building2 className="w-5 h-5 text-warn" />
}

const formatFeatures = (plan: SubscriptionPlan): string[] => {
  const featureList: string[] = []

  // Add credit info
  if (plan.credits_monthly) {
    featureList.push(`${plan.credits_monthly.toLocaleString()} credits/month`)
  }

  // Add limits
  if (plan.max_agents === -1 || plan.max_agents > 100) {
    featureList.push('Unlimited agents')
  } else if (plan.max_agents) {
    featureList.push(`${plan.max_agents} agent${plan.max_agents > 1 ? 's' : ''}`)
  }

  if (plan.max_knowledge_bases !== undefined) {
    if (plan.max_knowledge_bases === -1 || plan.max_knowledge_bases > 100) {
      featureList.push('Unlimited knowledge bases')
    } else if (plan.max_knowledge_bases > 0) {
      featureList.push(`${plan.max_knowledge_bases} knowledge base${plan.max_knowledge_bases > 1 ? 's' : ''}`)
    }
  }

  if (plan.max_team_members === -1 || plan.max_team_members > 100) {
    featureList.push('Unlimited team members')
  } else if (plan.max_team_members && plan.max_team_members > 1) {
    featureList.push(`${plan.max_team_members} team members`)
  }

  // Add features from the features field
  if (Array.isArray(plan.features)) {
    featureList.push(...plan.features)
  } else if (plan.features && typeof plan.features === 'object') {
    Object.entries(plan.features).forEach(([key, value]) => {
      // Convert camelCase or snake_case to readable format
      const readable = key
        .replace(/_/g, ' ')
        .replace(/([A-Z])/g, ' $1')
        .toLowerCase()
        .replace(/^\w/, c => c.toUpperCase())
        .trim()

      if (value === true) {
        featureList.push(readable)
      } else if (typeof value === 'string' && value) {
        featureList.push(`${readable}: ${value}`)
      } else if (typeof value === 'number' && value > 0) {
        featureList.push(`${readable}: ${value}`)
      }
    })
  }

  return featureList
}

export default function PricingPage() {
  const [isYearly, setIsYearly] = useState(false)
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const fetchPlans = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetch(`${API_URL}/api/v1/billing/plans`)
        const data = await response.json()

        // Handle both array response and wrapped response { success, data }
        const plansArray = Array.isArray(data) ? data : (data.data || data.plans || [])

        if (plansArray.length > 0) {
          // Sort by display_order or price
          const sortedPlans = plansArray
            .filter((p: SubscriptionPlan) => p.is_active !== false)
            .sort((a: SubscriptionPlan, b: SubscriptionPlan) => {
              if (a.display_order !== undefined && b.display_order !== undefined) {
                return a.display_order - b.display_order
              }
              return (a.price_monthly || 0) - (b.price_monthly || 0)
            })
          setPlans(sortedPlans)
        } else {
          setError('No pricing plans available')
        }
      } catch (err) {
        console.error('Failed to fetch plans:', err)
        setError('Unable to load pricing plans')
      } finally {
        setLoading(false)
      }
    }
    fetchPlans()
  }, [])

  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-paper px-4 pb-12 pt-28 sm:px-6 sm:pb-16 sm:pt-32">

        <div className="relative max-w-4xl mx-auto text-center">
          <h1 className="text-4xl sm:text-6xl font-medium tracking-[-0.06em] text-ink mb-4 sm:mb-6">
            Choose the plan that fits your needs
          </h1>
          <p className="text-base sm:text-xl text-ink-soft mb-8 sm:mb-10 leading-8">
            Start free, scale as you grow. All plans include our core features.
          </p>

          <div className="inline-flex items-center justify-center gap-4 rounded-full border border-black/10 bg-white/70 px-4 py-3 shadow-soft mb-12">
            <span className={`text-sm font-semibold ${!isYearly ? 'text-ink' : 'text-ink-mute'}`}>
              Monthly
            </span>
            <button
              onClick={() => setIsYearly(!isYearly)}
              className={`relative h-7 w-14 rounded-full transition-colors ${
                isYearly ? 'bg-leaf' : 'bg-line'
              }`}
            >
              <div
                className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-transform motion-reduce:transition-none ${
                  isYearly ? 'translate-x-8' : 'translate-x-1'
                }`}
              />
            </button>
            <span className={`text-sm font-semibold ${isYearly ? 'text-ink' : 'text-ink-mute'}`}>
              Yearly
              <span className="ml-2 text-[11px] text-leaf font-semibold">Save 20%</span>
            </span>
          </div>
        </div>
      </section>

      <section className="bg-sand pb-16 px-4 sm:px-6 sm:pb-24" ref={containerRef}>
        <div className="max-w-6xl mx-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 text-leaf motion-safe:animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center py-20">
              <p className="text-ink-soft mb-4">{error}</p>
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 font-semibold text-paper transition-colors hover:bg-black"
              >
                Get Started Free
              </Link>
            </div>
          ) : (
            <div className={`grid gap-8 ${plans.length === 1 ? 'max-w-md mx-auto' : plans.length === 2 ? 'md:grid-cols-2 max-w-3xl mx-auto' : 'md:grid-cols-3'}`}>
              {plans.map((plan, index) => {
                const features = formatFeatures(plan)
                const isPopular = plan.is_popular || (plans.length >= 3 && index === 1)
                const theme = planAccentStyles[index % planAccentStyles.length]

                return (
                  <div
                    key={plan.id}
                    className={`pricing-card relative rounded-[2rem] p-8 shadow-soft ${
                      isPopular
                        ? 'border border-leaf/25 ring-2 ring-mint bg-white'
                        : `border border-black/8 ${theme.surface}`
                    }`}
                  >
                    {isPopular && (
                      <div className="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-ink px-4 py-1 text-sm font-semibold text-paper shadow-soft">
                        Most Popular
                      </div>
                    )}

                    <div className="mb-6">
                      <div className="flex items-center gap-2 mb-2">
                        <div className={`flex h-10 w-10 items-center justify-center rounded-[1rem] ${theme.iconWrap}`}>
                          {getIconForPlan(plan.name, index)}
                        </div>
                        <h3 className="text-xl font-semibold tracking-[-0.03em] text-ink">{plan.name}</h3>
                      </div>
                      <p className="text-ink-soft text-sm leading-6">{plan.description || 'Choose this plan to get started'}</p>
                    </div>

                    <div className="mb-6">
                      <div className="flex items-baseline gap-1">
                        <span className="text-4xl font-semibold tracking-[-0.05em] text-ink">
                          ${isYearly && plan.price_yearly ? Math.round(plan.price_yearly / 12) : plan.price_monthly || 0}
                        </span>
                        <span className="text-ink-mute">/month</span>
                      </div>
                      {isYearly && plan.price_yearly && plan.price_yearly > 0 && (
                        <p className="mt-1 text-sm text-ink-mute">
                          ${plan.price_yearly} billed annually
                        </p>
                      )}
                    </div>

                    <Link
                      href="/signup"
                      className={`mb-8 block w-full rounded-full py-3 text-center font-semibold transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                        isPopular ? 'bg-ink text-paper hover:bg-black' : theme.button
                      }`}
                    >
                      {(plan.price_monthly || 0) === 0 ? 'Start Free' : 'Get Started'}
                    </Link>

                    <ul className="space-y-3">
                      {features.slice(0, 8).map((feature, idx) => (
                        <li key={idx} className="flex items-start gap-3">
                          <Check className="w-5 h-5 text-leaf flex-shrink-0 mt-0.5" />
                          <span className="text-night text-sm leading-6">{feature}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </section>

      <section className="bg-paper px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-3xl mx-auto">
          <div className="mb-4 text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/60 px-4 py-2 text-sm font-semibold text-ink-soft">
              <Sparkles className="w-4 h-4" />
              Pricing FAQ
            </div>
          </div>
          <h2 className="text-3xl sm:text-4xl font-medium tracking-[-0.05em] text-ink text-center mb-8 sm:mb-12">
            Frequently Asked Questions
          </h2>

          <div className="space-y-6">
            {[
              {
                q: 'What are credits?',
                a: 'Credits measure platform usage. 1 credit = 1 action (message, tool use, knowledge base query, or agent execution). File uploads cost 2 credits. Since you use your own LLM API keys, all models cost the same credits. Unused credits roll over on Professional and Enterprise plans.'
              },
              {
                q: 'Can I change plans anytime?',
                a: 'Yes! You can upgrade or downgrade your plan at any time. Changes take effect immediately, and we\'ll prorate any differences.'
              },
              {
                q: 'What payment methods do you accept?',
                a: 'We accept all major credit cards, PayPal, and bank transfers for enterprise plans. Payments are securely processed by Paddle.'
              },
              {
                q: 'Is there a refund policy?',
                a: 'Yes, we offer a 30-day money-back guarantee for new subscriptions. See our Terms of Service for full details.'
              },
              {
                q: 'Do you offer discounts for startups or nonprofits?',
                a: 'Yes! We offer special pricing for qualified startups and nonprofit organizations. Contact us to learn more.'
              },
              {
                q: 'Do I need to pay for LLM API costs separately?',
                a: 'Yes, you use your own LLM API keys (OpenAI, Anthropic, Google, etc.). Our pricing only covers platform features - agents, knowledge bases, tools, and integrations. This gives you full control over your AI costs and model selection.'
              }
            ].map((faq, idx) => (
              <div key={idx} className="rounded-[1.6rem] border border-black/8 bg-white/72 p-6 shadow-soft">
                <h3 className="font-semibold text-ink mb-2 tracking-[-0.02em]">{faq.q}</h3>
                <p className="text-ink-soft leading-7">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-paper px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-4xl mx-auto text-center">
          <div className="relative overflow-hidden rounded-[2.7rem] border border-black/10 bg-ink p-8 shadow-soft sm:p-12">
            <div className="absolute inset-0" />
            <div className="absolute inset-[10px] rounded-[2.2rem] border border-white/8" />
            <div className="relative">
            <h2 className="text-2xl sm:text-3xl font-medium tracking-[-0.05em] text-white mb-4">
              Ready to supercharge your workflows?
            </h2>
            <p className="text-white/90 mb-6 sm:mb-8 text-base sm:text-lg leading-8">
              Start building AI agents today. No credit card required.
            </p>
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-full bg-mint px-8 py-4 font-semibold text-ink transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
            >
              Get Started Free
              <ArrowRight className="w-5 h-5" />
            </Link>
            </div>
          </div>
        </div>
      </section>
    </PublicPageFrame>
  )
}
