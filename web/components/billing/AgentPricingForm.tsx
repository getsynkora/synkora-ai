'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'

interface AgentPricingFormProps {
  agentId: string
  initialPricing?: any
  onSubmit: (pricing: any) => Promise<void>
  loading?: boolean
}

const TIER_FIELDS = [
  { key: 'session_credits', label: 'Session (1 conversation)', desc: 'Credits for a single chat session' },
  { key: 'daily_credits', label: 'Daily (24 hours)', desc: 'Credits for 24-hour access' },
  { key: 'weekly_credits', label: 'Weekly (7 days)', desc: 'Credits for 7-day access' },
  { key: 'monthly_subscription_credits', label: 'Monthly (30 days)', desc: 'Credits for 30-day rolling access' },
]

export default function AgentPricingForm({ agentId, initialPricing, onSubmit, loading = false }: AgentPricingFormProps) {
  const [form, setForm] = useState({
    pricing_model: initialPricing?.pricing_model || 'FREE',
    credits_per_use: initialPricing?.credits_per_use ?? '',
    session_credits: initialPricing?.session_credits ?? '',
    daily_credits: initialPricing?.daily_credits ?? '',
    weekly_credits: initialPricing?.weekly_credits ?? '',
    monthly_subscription_credits: initialPricing?.monthly_subscription_credits ?? '',
    trial_messages: initialPricing?.trial_messages ?? 0,
    revenue_share_percentage: initialPricing?.revenue_share_percentage ?? 70,
    email_subscription_model: initialPricing?.email_subscription_model || 'FREE',
    email_subscription_price_cents: initialPricing?.email_subscription_price_cents ?? '',
    email_subscription_trial_emails: initialPricing?.email_subscription_trial_emails ?? 0,
  })
  const [submitting, setSubmitting] = useState(false)

  const set = (key: string, value: any) => setForm(f => ({ ...f, [key]: value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await onSubmit({
        agent_id: agentId,
        ...form,
        credits_per_use: form.credits_per_use === '' ? null : Number(form.credits_per_use),
        session_credits: form.session_credits === '' ? null : Number(form.session_credits),
        daily_credits: form.daily_credits === '' ? null : Number(form.daily_credits),
        weekly_credits: form.weekly_credits === '' ? null : Number(form.weekly_credits),
        monthly_subscription_credits: form.monthly_subscription_credits === '' ? null : Number(form.monthly_subscription_credits),
        email_subscription_price_cents: form.email_subscription_price_cents === '' ? null : Number(form.email_subscription_price_cents),
        trial_messages: Number(form.trial_messages),
        email_subscription_trial_emails: Number(form.email_subscription_trial_emails),
        revenue_share_percentage: Number(form.revenue_share_percentage),
      })
    } finally {
      setSubmitting(false)
    }
  }

  const isFree = form.pricing_model === 'FREE'

  return (
    <form onSubmit={handleSubmit} className="space-y-8">

      {/* Pricing model */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h3 className="font-semibold text-gray-900 mb-4">Pricing Model</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[
            { value: 'FREE', label: 'Free', desc: 'Anyone can use for free' },
            { value: 'PER_USE', label: 'Per Use', desc: 'Charge per message' },
            { value: 'SESSION', label: 'Session', desc: 'Pay per conversation' },
            { value: 'DAILY', label: 'Daily', desc: '24-hour access' },
            { value: 'WEEKLY', label: 'Weekly', desc: '7-day access' },
            { value: 'MONTHLY', label: 'Monthly', desc: '30-day access' },
          ].map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => set('pricing_model', opt.value)}
              className={`text-left p-3 rounded-lg border-2 transition-all ${
                form.pricing_model === opt.value
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="font-medium text-sm text-gray-900">{opt.label}</div>
              <div className="text-xs text-gray-500 mt-0.5">{opt.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Per-use cost */}
      {form.pricing_model === 'PER_USE' && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Per-Use Cost</h3>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Credits per message</label>
            <input
              type="number" min="1"
              value={form.credits_per_use}
              onChange={e => set('credits_per_use', e.target.value)}
              placeholder="e.g. 5"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
        </div>
      )}

      {/* Chat access tiers */}
      {!isFree && form.pricing_model !== 'PER_USE' && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="font-semibold text-gray-900 mb-1">Chat Access Tiers</h3>
          <p className="text-xs text-gray-500 mb-4">Leave a tier blank to hide it from the pricing page. Set at least one.</p>
          <div className="space-y-4">
            {TIER_FIELDS.filter(t => {
              if (form.pricing_model === 'SESSION') return t.key === 'session_credits'
              if (form.pricing_model === 'DAILY') return t.key === 'daily_credits'
              if (form.pricing_model === 'WEEKLY') return t.key === 'weekly_credits'
              if (form.pricing_model === 'MONTHLY') return t.key === 'monthly_subscription_credits'
              return true
            }).map(tier => (
              <div key={tier.key} className="flex items-center gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">{tier.label}</label>
                  <p className="text-xs text-gray-400">{tier.desc}</p>
                </div>
                <div className="w-40">
                  <input
                    type="number" min="1"
                    value={(form as any)[tier.key]}
                    onChange={e => set(tier.key, e.target.value)}
                    placeholder="credits"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-right focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trial messages */}
      {!isFree && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="font-semibold text-gray-900 mb-1">Free Trial</h3>
          <p className="text-xs text-gray-500 mb-4">Let users try before they pay. Set 0 to disable.</p>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Free messages before paywall</label>
            <input
              type="number" min="0"
              value={form.trial_messages}
              onChange={e => set('trial_messages', e.target.value)}
              className="w-40 border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
        </div>
      )}

      {/* Email subscription pricing */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h3 className="font-semibold text-gray-900 mb-1">Email Subscription Pricing</h3>
        <p className="text-xs text-gray-500 mb-4">Separate from chat access — controls who gets emailed when your agent runs.</p>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Email subscription model</label>
            <div className="flex gap-3">
              {[
                { value: 'FREE', label: 'Free' },
                { value: 'ONE_TIME', label: 'One-time payment' },
                { value: 'MONTHLY', label: 'Monthly recurring' },
              ].map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => set('email_subscription_model', opt.value)}
                  className={`px-4 py-2 rounded-lg border text-sm font-medium transition-all ${
                    form.email_subscription_model === opt.value
                      ? 'border-primary-500 bg-primary-50 text-primary-700'
                      : 'border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {form.email_subscription_model !== 'FREE' && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Price (cents)</label>
                <input
                  type="number" min="1"
                  value={form.email_subscription_price_cents}
                  onChange={e => set('email_subscription_price_cents', e.target.value)}
                  placeholder="e.g. 99 = $0.99"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Free trial emails</label>
                <input
                  type="number" min="0"
                  value={form.email_subscription_trial_emails}
                  onChange={e => set('email_subscription_trial_emails', e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Revenue share */}
      {!isFree && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="font-semibold text-gray-900 mb-1">Revenue Share</h3>
          <p className="text-xs text-gray-500 mb-4">Your percentage of each payment. Platform keeps the rest.</p>
          <div className="flex items-center gap-3">
            <input
              type="range" min="0" max="100" step="5"
              value={form.revenue_share_percentage}
              onChange={e => set('revenue_share_percentage', e.target.value)}
              className="flex-1"
            />
            <span className="w-16 text-right font-semibold text-primary-600">{form.revenue_share_percentage}%</span>
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>You: {form.revenue_share_percentage}%</span>
            <span>Platform: {100 - Number(form.revenue_share_percentage)}%</span>
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={loading || submitting}
          className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {(loading || submitting) && <Loader2 className="h-4 w-4 animate-spin" />}
          Save pricing
        </button>
      </div>
    </form>
  )
}
