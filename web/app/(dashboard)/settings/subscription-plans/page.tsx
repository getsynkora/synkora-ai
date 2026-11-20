'use client'

import { useState, useEffect } from 'react'
import { Check, CreditCard, Lock } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { usePermissions } from '@/hooks/usePermissions'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

interface SubscriptionPlan {
  id: string
  name: string
  description: string
  price_monthly: number
  price_yearly: number
  credits_monthly: number
  features: string[]
  is_active: boolean
  stripe_price_id_monthly?: string
  stripe_price_id_yearly?: string
}

export default function SubscriptionPlansPage() {
  const { hasPermission, loading: permissionsLoading } = usePermissions()
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadPlans()
  }, [])

  const loadPlans = async () => {
    try {
      const response: any = await apiClient.request('GET', '/api/v1/subscription-plans')
      setPlans(response.data || [])
    } catch (error) {
      console.error('Failed to load plans:', error)
    } finally {
      setLoading(false)
    }
  }

  // Check if user is platform owner
  const isPlatformOwner = hasPermission('platform', 'read')

  if (loading || permissionsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  // Check platform owner permission
  if (!isPlatformOwner) {
    return (
      <DashboardPageShell
        title="Subscription Plans"
        description="Manage subscription tiers and pricing."
        icon={CreditCard}
        badge="Settings"
        backHref="/settings/profile"
        backLabel="Back to Settings"
        breadcrumbs={[
          { label: 'Home', href: '/' },
          { label: 'Settings', href: '/settings/profile' },
          { label: 'Subscription Plans' },
        ]}
      >
        <DashboardPagePanel className="p-10 text-center">
          <Lock className="mx-auto mb-4 h-12 w-12 text-clay" />
          <h3 className="text-lg font-semibold text-ink">Access Denied</h3>
          <p className="mt-2 text-sm text-ink-soft">
            You do not have permission to access subscription plan configuration. This feature is only available to platform owners.
          </p>
        </DashboardPagePanel>
      </DashboardPageShell>
    )
  }

  return (
    <DashboardPageShell
      title="Subscription Plans"
      description="Manage subscription tiers and pricing."
      icon={CreditCard}
      badge="Settings"
      backHref="/settings/profile"
      backLabel="Back to Settings"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Settings', href: '/settings/profile' },
        { label: 'Subscription Plans' },
      ]}
      stats={[
        { label: 'Plans', value: plans.length },
        { label: 'Active', value: plans.filter((plan) => plan.is_active).length },
      ]}
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {plans.map((plan) => (
          <DashboardPagePanel key={plan.id} className="flex h-full flex-col p-5 sm:p-6">
            <div className="mb-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-xl font-semibold tracking-[-0.03em] text-ink">{plan.name}</h3>
                  <p className="mt-1.5 text-sm leading-6 text-ink-soft">{plan.description}</p>
                </div>
                <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${plan.is_active ? 'bg-leaf-wash text-forest' : 'bg-paper text-ink-soft'}`}>
                  {plan.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            </div>

            <div className="mb-5">
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-semibold tracking-[-0.05em] text-ink">${plan.price_monthly}</span>
                <span className="text-sm text-ink-mute">/month</span>
              </div>
              {plan.price_yearly > 0 ? (
                <p className="mt-1.5 text-xs text-ink-mute">
                  ${plan.price_yearly}/year, saving ${(plan.price_monthly * 12 - plan.price_yearly).toFixed(2)}
                </p>
              ) : null}
            </div>

            <div className="mb-5 inline-flex w-fit rounded-full border border-leaf-wash bg-leaf-wash px-3 py-1.5 text-xs font-semibold text-forest">
              {plan.credits_monthly.toLocaleString()} credits/month
            </div>

            <div className="mt-auto space-y-2.5 border-t border-sand-deep pt-5">
              {plan.features.map((feature, index) => (
                <div key={index} className="flex items-start gap-2.5">
                  <div className="mt-0.5 rounded-full bg-sand-deep p-1">
                    <Check className="h-3 w-3 text-ink" />
                  </div>
                  <span className="text-sm text-ink-soft">{feature}</span>
                </div>
              ))}
            </div>
          </DashboardPagePanel>
        ))}
      </div>

      <DashboardPagePanel className="mt-6 p-5 sm:p-6">
        <h3 className="text-sm font-semibold text-bark">Seeding Instructions</h3>
        <p className="mt-2 text-sm text-ink-soft">
          To seed the default subscription plans, run the following command in the API container.
        </p>
        <code className="mt-4 block overflow-x-auto rounded-[1.2rem] bg-ink p-4 font-mono text-xs text-paper">
          docker-compose exec api python -c "from src.services.billing.seed_plans import seed_subscription_plans; import asyncio; asyncio.run(seed_subscription_plans())"
        </code>
      </DashboardPagePanel>
    </DashboardPageShell>
  )
}
