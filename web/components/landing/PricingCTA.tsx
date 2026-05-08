'use client'

import { useState } from 'react'
import { useAuthStore } from '@/lib/store/authStore'
import { apiClient } from '@/lib/api/client'

interface PricingTier {
  tier: string
  label: string
  credits: number
  desc: string
  popular?: boolean
}

interface PricingCTAProps {
  agentSlug: string
  agentName: string
  pricingId: string
  tiers: PricingTier[]
  trialMessages: number
  accentColor?: string
  isFree?: boolean
}

export function PricingCTA({ agentSlug, agentName, pricingId, tiers, trialMessages, accentColor = '#e11d48', isFree }: PricingCTAProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const [selectedTier, setSelectedTier] = useState<string | null>(tiers[0]?.tier || null)
  const [loading, setLoading] = useState(false)
  const [guestEmail, setGuestEmail] = useState('')
  // Guests see the email form immediately; authenticated users see the credits button
  const [showEmailForm, setShowEmailForm] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (isFree) {
    return (
      <a
        href={`/agents/${encodeURIComponent(agentName)}/chat`}
        className="inline-flex items-center gap-2 px-8 py-3.5 rounded-full font-semibold text-white text-base transition-all hover:opacity-90"
        style={{ background: accentColor }}
      >
        Start chatting →
      </a>
    )
  }

  const handleSubscribe = async () => {
    if (!selectedTier) return
    setLoading(true)
    setError(null)
    try {
      if (isAuthenticated) {
        await apiClient.request('POST', `/api/public/agents/${agentSlug}/subscribe`, {
          pricing_id: pricingId,
          tier: selectedTier,
        })
        window.location.reload()
      } else {
        setShowEmailForm(true)
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  const handleGuestCheckout = async () => {
    if (!selectedTier || !guestEmail) return
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.request('POST', `/api/public/agents/${agentSlug}/checkout`, {
        pricing_id: pricingId,
        tier: selectedTier,
        guest_email: guestEmail,
        success_url: window.location.href + '?access_token={CHECKOUT_SESSION_ID}',
        cancel_url: window.location.href,
      })
      window.location.href = (data as any).checkout_url
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Checkout failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto space-y-4">
      {/* Tier selector (only shown when multiple tiers) */}
      {tiers.length > 1 && (
        <div className="grid grid-cols-2 gap-3">
          {tiers.map(t => (
            <button
              key={t.tier}
              onClick={() => setSelectedTier(t.tier)}
              className="p-4 rounded-xl border-2 text-left transition-all bg-white hover:bg-gray-50"
              style={selectedTier === t.tier ? { borderColor: accentColor } : { borderColor: '#e5e7eb' }}
            >
              <div className="font-semibold text-sm text-gray-900">{t.label}</div>
              <div className="text-gray-400 text-xs mt-0.5">{t.credits} credits</div>
            </button>
          ))}
        </div>
      )}

      {/* Authenticated users: subscribe with credits */}
      {isAuthenticated && !showEmailForm && (
        <button
          onClick={handleSubscribe}
          disabled={loading || !selectedTier}
          className="w-full py-3.5 rounded-full font-semibold text-white text-base transition-all hover:opacity-90 disabled:opacity-50 shadow-lg"
          style={{ background: accentColor, boxShadow: `0 8px 24px ${accentColor}40` }}
        >
          {loading ? 'Processing...' : 'Subscribe with credits'}
        </button>
      )}

      {/* Guest users: email form shown directly */}
      {(!isAuthenticated || showEmailForm) && (
        <div className="space-y-2">
          <div className="flex gap-2">
            <input
              type="email"
              value={guestEmail}
              onChange={e => setGuestEmail(e.target.value)}
              placeholder="your@email.com"
              className="flex-1 px-4 py-3 bg-white border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:border-transparent"
              style={{ '--tw-ring-color': accentColor } as React.CSSProperties}
            />
            <button
              onClick={handleGuestCheckout}
              disabled={loading || !guestEmail}
              className="px-6 py-3 rounded-xl font-semibold text-white text-sm transition-all hover:opacity-90 disabled:opacity-50"
              style={{ background: accentColor }}
            >
              {loading ? '...' : 'Continue →'}
            </button>
          </div>
          {isAuthenticated && (
            <button onClick={() => setShowEmailForm(false)} className="text-xs text-gray-400 hover:text-gray-600 w-full text-center">
              ← Back to credits
            </button>
          )}
        </div>
      )}

      {error && <p className="text-red-500 text-sm text-center">{error}</p>}
      {trialMessages > 0 && (
        <p className="text-gray-400 text-xs text-center">
          First {trialMessages} messages free — no credit card required
        </p>
      )}
    </div>
  )
}
