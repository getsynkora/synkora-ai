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
    surface: 'bg-[linear-gradient(145deg,rgba(255,255,255,0.82),rgba(249,241,233,0.88))]',
    iconWrap: 'bg-[#ffe8de]',
    iconColor: 'text-[#cf673e]',
    button: 'bg-white/78 hover:bg-white text-[#171717] border border-black/10',
  },
  {
    surface: 'bg-[linear-gradient(145deg,rgba(255,255,255,0.82),rgba(234,245,241,0.88))]',
    iconWrap: 'bg-[#e4f2ef]',
    iconColor: 'text-[#2d8b69]',
    button: 'bg-[#191919] hover:bg-black text-[#f7f2e7]',
  },
  {
    surface: 'bg-[linear-gradient(145deg,rgba(255,255,255,0.82),rgba(250,243,228,0.88))]',
    iconWrap: 'bg-[#fff0d8]',
    iconColor: 'text-[#d58a27]',
    button: 'bg-white/78 hover:bg-white text-[#171717] border border-black/10',
  },
]

const getIconForPlan = (name: string, index: number) => {
  const nameLower = name.toLowerCase()
  if (nameLower.includes('free') || nameLower.includes('starter')) {
    return <Sparkles className="w-5 h-5 text-[#cf673e]" />
  }
  if (nameLower.includes('pro') || nameLower.includes('professional')) {
    return <Zap className="w-5 h-5 text-[#2d8b69]" />
  }
  if (nameLower.includes('enterprise') || nameLower.includes('business')) {
    return <Building2 className="w-5 h-5 text-[#d58a27]" />
  }
  // Fallback based on index
  if (index === 0) return <Sparkles className="w-5 h-5 text-[#cf673e]" />
  if (index === 1) return <Zap className="w-5 h-5 text-[#2d8b69]" />
  return <Building2 className="w-5 h-5 text-[#d58a27]" />
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

  useEffect(() => {
    if (!loading && plans.length > 0 && containerRef.current) {
      const el = containerRef.current
      import('gsap').then(({ default: gsap }) => {
        gsap.fromTo(
          el.querySelectorAll('.pricing-card'),
          { opacity: 0, y: 40 },
          { opacity: 1, y: 0, duration: 0.6, stagger: 0.15, ease: 'power3.out' }
        )
      })
    }
  }, [loading, plans])

  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-[#f7f2e7] px-4 pb-12 pt-28 sm:px-6 sm:pb-16 sm:pt-32">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-[8%] top-[8%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.94),transparent_72%)]" />
          <div className="absolute right-[6%] top-[10%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,rgba(240,232,216,0.92),transparent_72%)]" />
          <div className="absolute left-[20%] top-[34%] h-56 w-56 rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.15),transparent_72%)]" />
        </div>

        <div className="relative max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/65 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e] shadow-[0_12px_28px_rgba(0,0,0,0.04)] backdrop-blur mb-6">
            <Sparkles className="w-4 h-4" />
            Simple, Transparent Pricing
          </div>
          <h1 className="text-4xl sm:text-6xl font-medium tracking-[-0.06em] text-[#171717] mb-4 sm:mb-6">
            Choose the plan that fits your needs
          </h1>
          <p className="text-base sm:text-xl text-[#5a544a] mb-8 sm:mb-10 leading-8">
            Start free, scale as you grow. All plans include our core features.
          </p>

          <div className="inline-flex items-center justify-center gap-4 rounded-full border border-black/10 bg-white/70 px-4 py-3 shadow-[0_12px_28px_rgba(0,0,0,0.04)] backdrop-blur mb-12">
            <span className={`text-sm font-semibold uppercase tracking-[0.16em] ${!isYearly ? 'text-[#171717]' : 'text-[#7a736a]'}`}>
              Monthly
            </span>
            <button
              onClick={() => setIsYearly(!isYearly)}
              className={`relative h-7 w-14 rounded-full transition-colors ${
                isYearly ? 'bg-[#2d8b69]' : 'bg-[#d9cfbf]'
              }`}
            >
              <div
                className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-transform ${
                  isYearly ? 'translate-x-8' : 'translate-x-1'
                }`}
              />
            </button>
            <span className={`text-sm font-semibold uppercase tracking-[0.16em] ${isYearly ? 'text-[#171717]' : 'text-[#7a736a]'}`}>
              Yearly
              <span className="ml-2 text-[11px] text-[#2d8b69] font-semibold">Save 20%</span>
            </span>
          </div>
        </div>
      </section>

      <section className="bg-[#f4eee1] pb-16 px-4 sm:px-6 sm:pb-24" ref={containerRef}>
        <div className="max-w-6xl mx-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 text-[#2d8b69] animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center py-20">
              <p className="text-[#5f594f] mb-4">{error}</p>
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 rounded-full bg-[#191919] px-6 py-3 font-semibold text-[#f7f2e7] transition-colors hover:bg-black"
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
                    className={`pricing-card relative rounded-[2rem] p-8 shadow-[0_24px_56px_rgba(0,0,0,0.06)] backdrop-blur ${
                      isPopular
                        ? 'border border-[#2d8b69]/25 ring-2 ring-[#79dfbc] bg-[linear-gradient(145deg,rgba(255,255,255,0.84),rgba(234,245,241,0.9))]'
                        : `border border-black/8 ${theme.surface}`
                    }`}
                  >
                    {isPopular && (
                      <div className="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-[#191919] px-4 py-1 text-sm font-semibold text-[#f7f2e7] shadow-[0_18px_36px_rgba(23,23,23,0.16)]">
                        Most Popular
                      </div>
                    )}

                    <div className="mb-6">
                      <div className="flex items-center gap-2 mb-2">
                        <div className={`flex h-10 w-10 items-center justify-center rounded-[1rem] ${theme.iconWrap}`}>
                          {getIconForPlan(plan.name, index)}
                        </div>
                        <h3 className="text-xl font-semibold tracking-[-0.03em] text-[#171717]">{plan.name}</h3>
                      </div>
                      <p className="text-[#5f594f] text-sm leading-6">{plan.description || 'Choose this plan to get started'}</p>
                    </div>

                    <div className="mb-6">
                      <div className="flex items-baseline gap-1">
                        <span className="text-4xl font-semibold tracking-[-0.05em] text-[#171717]">
                          ${isYearly && plan.price_yearly ? Math.round(plan.price_yearly / 12) : plan.price_monthly || 0}
                        </span>
                        <span className="text-[#7a736a]">/month</span>
                      </div>
                      {isYearly && plan.price_yearly && plan.price_yearly > 0 && (
                        <p className="mt-1 text-sm text-[#7a736a]">
                          ${plan.price_yearly} billed annually
                        </p>
                      )}
                    </div>

                    <Link
                      href="/signup"
                      className={`mb-8 block w-full rounded-full py-3 text-center font-semibold transition-all ${
                        isPopular ? 'bg-[#191919] text-[#f7f2e7] hover:bg-black' : theme.button
                      }`}
                    >
                      {(plan.price_monthly || 0) === 0 ? 'Start Free' : 'Get Started'}
                    </Link>

                    <ul className="space-y-3">
                      {features.slice(0, 8).map((feature, idx) => (
                        <li key={idx} className="flex items-start gap-3">
                          <Check className="w-5 h-5 text-[#2d8b69] flex-shrink-0 mt-0.5" />
                          <span className="text-[#39352f] text-sm leading-6">{feature}</span>
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

      <section className="bg-[#f7f2e7] px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-3xl mx-auto">
          <div className="mb-4 text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/60 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
              <Sparkles className="w-4 h-4" />
              Pricing FAQ
            </div>
          </div>
          <h2 className="text-3xl sm:text-4xl font-medium tracking-[-0.05em] text-[#171717] text-center mb-8 sm:mb-12">
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
              <div key={idx} className="rounded-[1.6rem] border border-black/8 bg-white/72 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur">
                <h3 className="font-semibold text-[#171717] mb-2 tracking-[-0.02em]">{faq.q}</h3>
                <p className="text-[#5f594f] leading-7">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[#f7f2e7] px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-4xl mx-auto text-center">
          <div className="relative overflow-hidden rounded-[2.7rem] border border-black/10 bg-[#171717] p-8 shadow-[0_34px_90px_rgba(0,0,0,0.2)] sm:p-12">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.08),transparent_24%),radial-gradient(circle_at_82%_18%,rgba(125,229,193,0.16),transparent_22%),radial-gradient(circle_at_18%_80%,rgba(255,143,178,0.12),transparent_20%)]" />
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
              className="inline-flex items-center gap-2 rounded-full bg-[#7de5c1] px-8 py-4 font-semibold text-[#101915] transition-transform hover:-translate-y-0.5"
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
