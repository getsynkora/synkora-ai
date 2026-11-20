'use client'

import { SubscriptionPlan } from '@/types/billing'
import { Check } from 'lucide-react'

interface SubscriptionPlanCardProps {
  plan: SubscriptionPlan
  currentPlanId?: string
  onSelect: (planId: string) => void
  loading?: boolean
}

export default function SubscriptionPlanCard({
  plan,
  currentPlanId,
  onSelect,
  loading = false,
}: SubscriptionPlanCardProps) {
  const isCurrent = currentPlanId === plan.id
  const isPopular = plan.name === 'Professional'

  return (
    <div
      className={`relative rounded-xl border-2 p-5 shadow-sm transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:shadow-md bg-white ${
        isCurrent
          ? 'border-primary-500 bg-primary-50/30'
          : isPopular
          ? 'border-primary-400 bg-primary-50/20'
          : 'border-line hover:border-primary-200'
      }`}
    >
      {isPopular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="rounded-full bg-ink hover:bg-ink/85 px-3 py-1 text-xs font-semibold text-white shadow-sm">
            Most Popular
          </span>
        </div>
      )}

      {isCurrent && (
        <div className="absolute -top-3 right-4">
          <span className="rounded-full bg-ink hover:bg-ink/85 px-3 py-1 text-xs font-semibold text-white shadow-sm">
            Current Plan
          </span>
        </div>
      )}

      <div className="mb-4">
        <h3 className="text-lg font-bold text-ink">{plan.name}</h3>
        {plan.description && (
          <p className="mt-1 text-xs text-ink-soft">{plan.description}</p>
        )}
      </div>

      <div className="mb-5">
        <div className="flex items-baseline">
          <span className="text-3xl font-bold text-ink">
            ${plan.price_monthly}
          </span>
          <span className="ml-2 text-sm text-ink-soft">/month</span>
        </div>
        {plan.price_yearly && (
          <div className="mt-1 text-xs text-ink-soft">
            or ${plan.price_yearly}/year
          </div>
        )}
        <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-primary-100 px-2.5 py-1">
          <svg aria-hidden="true" className="w-3.5 h-3.5 text-primary-600" fill="currentColor" viewBox="0 0 20 20">
            <path d="M8.433 7.418c.155-.103.346-.196.567-.267v1.698a2.305 2.305 0 01-.567-.267C8.07 8.34 8 8.114 8 8c0-.114.07-.34.433-.582zM11 12.849v-1.698c.22.071.412.164.567.267.364.243.433.468.433.582 0 .114-.07.34-.433.582a2.305 2.305 0 01-.567.267z" />
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-13a1 1 0 10-2 0v.092a4.535 4.535 0 00-1.676.662C6.602 6.234 6 7.009 6 8c0 .99.602 1.765 1.324 2.246.48.32 1.054.545 1.676.662v1.941c-.391-.127-.68-.317-.843-.504a1 1 0 10-1.51 1.31c.562.649 1.413 1.076 2.353 1.253V15a1 1 0 102 0v-.092a4.535 4.535 0 001.676-.662C13.398 13.766 14 12.991 14 12c0-.99-.602-1.765-1.324-2.246A4.535 4.535 0 0011 9.092V7.151c.391.127.68.317.843.504a1 1 0 101.511-1.31c-.563-.649-1.413-1.076-2.354-1.253V5z" clipRule="evenodd" />
          </svg>
          <span className="text-xs font-semibold text-primary-700">
            {plan.credits_monthly.toLocaleString()} credits/mo
          </span>
        </div>
      </div>

      {plan.features && (
        <ul className="mb-5 space-y-2">
          {Object.entries(plan.features).map(([key, value]) => {
            // Format the feature key to be more readable
            const featureName = key
              .split('_')
              .map(word => word.charAt(0).toUpperCase() + word.slice(1))
              .join(' ');
            
            // Display the feature based on its value
            let displayText = featureName;
            if (typeof value === 'number') {
              if (value === -1) {
                displayText = `Unlimited ${featureName}`;
              } else {
                displayText = `${featureName}: ${value}`;
              }
            } else if (typeof value === 'boolean') {
              if (!value) return null; // Don't show false features
            }

            return (
              <li key={key} className="flex items-start">
                <Check className="mr-2 h-4 w-4 flex-shrink-0 text-primary-500 mt-0.5" />
                <span className="text-xs text-ink-soft">{displayText}</span>
              </li>
            );
          })}
        </ul>
      )}

      <button
        onClick={() => onSelect(plan.id)}
        disabled={loading || isCurrent}
        className={`w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm ${
          isCurrent
            ? 'cursor-not-allowed bg-line text-ink-mute'
            : isPopular
            ? 'bg-ink hover:bg-ink/85 text-white hover:from-primary-600 hover:to-primary-700 hover:shadow-md'
            : 'bg-primary-500 text-white hover:bg-primary-600'
        }`}
      >
        {loading ? 'Processing…' : isCurrent ? 'Current Plan' : 'Select Plan'}
      </button>
    </div>
  )
}
