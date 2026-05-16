'use client'

import { useState, useEffect, Suspense, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import { useSubscriptionPlans, useSubscription, useCredits, useUsageAnalytics } from '@/hooks/useBilling'
import { verifyCheckoutSession, getPaymentProviderConfig } from '@/lib/api/billing'
import {
  SubscriptionPlanCard,
  CreditBalanceCard,
  CreditTopupCard,
  CreditTransactionHistory,
  UsageAnalyticsChart,
} from '@/components/billing'
import { Loader2, CreditCard, TrendingUp, History } from 'lucide-react'
import toast, { Toaster } from 'react-hot-toast'
import { openCheckout, PaddleConfig } from '@/lib/paddle'

function BillingContent() {
  const [activeTab, setActiveTab] = useState<'subscription' | 'credits' | 'usage'>('subscription')
  const { plans, loading: plansLoading } = useSubscriptionPlans()
  const { subscription, create, upgrade, refetch: refetchSubscription } = useSubscription()
  const { balance, topups, transactions, loading: creditsLoading, topup, refetchBalance } = useCredits()
  const { actionBreakdown, loading: analyticsLoading } = useUsageAnalytics()

  const [processingPlanId, setProcessingPlanId] = useState<string | null>(null)
  const [processingTopupId, setProcessingTopupId] = useState<string | null>(null)
  const [paymentProvider, setPaymentProvider] = useState<{
    provider: string
    client_token: string | null
    environment: string | null
    is_configured: boolean
  } | null>(null)

  // Fetch active payment provider configuration
  useEffect(() => {
    const fetchPaymentConfig = async () => {
      try {
        const config = await getPaymentProviderConfig()
        setPaymentProvider(config)
      } catch (error) {
        console.error('Failed to fetch payment provider config:', error)
      }
    }
    fetchPaymentConfig()
  }, [])

  const handleSelectPlan = async (planId: string) => {
    try {
      setProcessingPlanId(planId)

      // Determine which payment provider to use
      const provider = (paymentProvider?.provider || 'stripe') as 'stripe' | 'paddle'

      let response: any
      // Check if user has an active subscription
      if (subscription) {
        // User has a subscription - upgrade it
        response = await upgrade({ plan_id: planId, payment_provider: provider })
      } else {
        // User doesn't have a subscription - create one
        response = await create({ plan_id: planId, payment_provider: provider })
      }

      // Handle checkout based on provider
      if (response && typeof response === 'object' && 'checkout_url' in response && response.checkout_url) {
        const responseProvider = response.provider || provider

        if (responseProvider === 'paddle' && paymentProvider?.client_token && response.session_id) {
          const paddleConfig: PaddleConfig = {
            clientToken: paymentProvider.client_token,
            environment: (paymentProvider.environment === 'production' ? 'production' : 'sandbox') as 'sandbox' | 'production',
          }
          // Open Paddle.js overlay checkout with callbacks
          openCheckout(paddleConfig, response.session_id, {
            onComplete: () => {
              toast.success('Payment successful! Your subscription is being activated.')
              // Refetch after short delay to allow webhook processing
              setTimeout(() => {
                refetchSubscription()
                refetchBalance()
              }, 2000)
            },
            onClose: () => {
              // User closed without completing - no action needed
            },
          })
          return
        } else if (response.checkout_url) {
          // Redirect to Stripe Checkout
          toast.loading('Redirecting to payment...', { id: 'checkout-redirect' })
          window.location.href = response.checkout_url
        }
      } else {
        // Direct subscription activation (no payment required)
        toast.success('Subscription activated successfully!')
        refetchSubscription()
      }
    } catch (error) {
      console.error('Failed to process subscription:', error)
      toast.error('Failed to process subscription. Please try again.')
    } finally {
      setProcessingPlanId(null)
    }
  }

  const handleSelectTopup = async (topupId: string) => {
    try {
      setProcessingTopupId(topupId)

      // Determine which payment provider to use
      const provider = (paymentProvider?.provider || 'stripe') as 'stripe' | 'paddle'

      const response: any = await topup({ topup_id: topupId, payment_provider: provider })

      // Check if we got a checkout URL or session_id
      if (response && typeof response === 'object' && ('checkout_url' in response || 'session_id' in response)) {
        const responseProvider = response.provider || provider

        if (responseProvider === 'paddle' && paymentProvider?.client_token && response.session_id) {
          const paddleConfig: PaddleConfig = {
            clientToken: paymentProvider.client_token,
            environment: (paymentProvider.environment === 'production' ? 'production' : 'sandbox') as 'sandbox' | 'production',
          }
          // Open Paddle.js overlay checkout with callbacks
          openCheckout(paddleConfig, response.session_id, {
            onComplete: () => {
              toast.success('Payment successful! Credits are being added.')
              setTimeout(() => {
                refetchBalance()
              }, 2000)
            },
            onClose: () => {
              // User closed without completing - no action needed
            },
          })
          return
        } else if (response.checkout_url) {
          // Redirect to Stripe Checkout
          toast.loading('Redirecting to payment...', { id: 'checkout-redirect' })
          window.location.href = response.checkout_url
        }
      } else {
        // Direct credit addition (no payment required)
        toast.success('Credits added successfully!')
        refetchBalance()
      }
    } catch (error) {
      console.error('Failed to purchase credits:', error)
      toast.error('Failed to purchase credits. Please try again.')
    } finally {
      setProcessingTopupId(null)
    }
  }

  // Handle success/cancel redirects from Stripe/Paddle
  const searchParams = useSearchParams()

  useEffect(() => {
    const sessionId = searchParams.get('session_id')
    const canceled = searchParams.get('canceled')
    const provider = searchParams.get('provider')

    if (sessionId && sessionId !== '{CHECKOUT_SESSION_ID}') {
      // Stripe payment successful - verify checkout session and create subscription if needed
      const verifySession = async () => {
        try {
          await verifyCheckoutSession(sessionId)
          toast.success('Payment successful! Your subscription has been activated.')

          // Refetch subscription data to show the updated plan
          refetchSubscription()
          refetchBalance()
        } catch (error) {
          console.error('Failed to verify checkout session:', error)
          toast.error('Payment successful, but subscription activation is pending. Please refresh the page.')
        } finally {
          // Clean up URL parameters after a short delay
          setTimeout(() => {
            const url = new URL(window.location.href)
            url.searchParams.delete('session_id')
            window.history.replaceState({}, '', url.toString())
          }, 1000)
        }
      }

      verifySession()
    } else if (provider === 'paddle') {
      // Paddle payment successful - subscription is handled via webhook
      toast.success('Payment successful! Your subscription is being activated.')

      // Refetch subscription data to show the updated plan
      refetchSubscription()
      refetchBalance()

      // Clean up URL parameters
      setTimeout(() => {
        const url = new URL(window.location.href)
        url.searchParams.delete('provider')
        // Paddle may add _ptxn parameter
        url.searchParams.delete('_ptxn')
        window.history.replaceState({}, '', url.toString())
      }, 1000)
    } else if (canceled) {
      // Payment canceled
      toast.error('Payment was cancelled. No charges were made.')

      // Clean up URL parameters
      const url = new URL(window.location.href)
      url.searchParams.delete('canceled')
      window.history.replaceState({}, '', url.toString())
    }
  }, [searchParams, refetchSubscription, refetchBalance])

  const tabs = [
    { id: 'subscription' as const, label: 'Subscription', icon: CreditCard },
    { id: 'credits' as const, label: 'Credits', icon: TrendingUp },
    { id: 'usage' as const, label: 'Usage', icon: History },
  ]

  return (
    <>
      <Toaster position="top-right" />
      <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
        <div className="max-w-7xl mx-auto">
          {/* Header - More Compact */}
          <div className="mb-6">
            <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Billing & Usage</h1>
            <p className="mt-1 text-sm text-gray-600">
              Manage your subscription, credits, and view usage analytics
            </p>
          </div>

          {/* Tabs - More Compact */}
          <div className="mb-6 border-b border-gray-200 bg-white rounded-t-lg px-4">
            <nav className="-mb-px flex space-x-6">
              {tabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center border-b-2 px-1 py-3 text-sm font-medium transition-colors ${
                      activeTab === tab.id
                        ? 'border-primary-500 text-primary-600'
                        : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                    }`}
                  >
                    <Icon className="mr-2 h-4 w-4" />
                    {tab.label}
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Subscription Tab */}
          {activeTab === 'subscription' && (
            <div className="space-y-6">
              {/* Current Subscription */}
              {subscription && (
                <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
                  <h2 className="mb-3 text-base font-semibold text-gray-900">
                    Current Subscription
                  </h2>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-base font-medium text-gray-900">
                        {subscription.plan_name}
                      </p>
                      <p className="text-sm text-gray-600">
                        Status: <span className="capitalize">{subscription.status}</span>
                      </p>
                      {subscription.current_period_end && (
                        <p className="text-sm text-gray-600">
                          Renews on:{' '}
                          {new Date(subscription.current_period_end).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                    {subscription.cancel_at_period_end && (
                      <span className="rounded-full bg-yellow-100 px-3 py-1 text-xs font-medium text-yellow-800">
                        Cancels at period end
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Available Plans */}
              <div>
                <h2 className="mb-4 text-base font-semibold text-gray-900">
                  Available Plans
                </h2>
                {plansLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
                  </div>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                    {plans.map((plan) => (
                      <SubscriptionPlanCard
                        key={plan.id}
                        plan={plan}
                        currentPlanId={subscription?.plan_id}
                        onSelect={handleSelectPlan}
                        loading={processingPlanId === plan.id}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Credits Tab */}
          {activeTab === 'credits' && (
            <div className="space-y-6">
              {/* Credit Balance */}
              {balance && (
                <CreditBalanceCard balance={balance} />
              )}

              {/* Credit Top-ups */}
              <div>
                <h2 className="mb-4 text-base font-semibold text-gray-900">
                  Purchase Credits
                </h2>
                {creditsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
                  </div>
                ) : !Array.isArray(topups) || topups.length === 0 ? (
                  <div className="rounded-lg border border-gray-200 bg-white p-8 text-center shadow-sm">
                    <p className="text-sm text-gray-600">No credit packages available</p>
                  </div>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {Array.isArray(topups) && topups.map((topup) => (
                      <CreditTopupCard
                        key={topup.id}
                        topup={topup}
                        onSelect={handleSelectTopup}
                        loading={processingTopupId === topup.id}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Transaction History */}
              <div>
                <h2 className="mb-4 text-base font-semibold text-gray-900">
                  Transaction History
                </h2>
                <CreditTransactionHistory
                  transactions={transactions}
                  loading={creditsLoading}
                />
              </div>
            </div>
          )}

          {/* Usage Tab */}
          {activeTab === 'usage' && (
            <div className="space-y-6">
              {/* Usage Analytics */}
              <div>
                <h2 className="mb-4 text-base font-semibold text-gray-900">
                  Usage Analytics
                </h2>
                <UsageAnalyticsChart
                  analytics={actionBreakdown}
                  loading={analyticsLoading}
                />
              </div>

              {/* Usage Summary */}
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <h3 className="mb-1 text-xs font-medium text-gray-600">
                    Total Actions
                  </h3>
                  <p className="text-2xl font-bold text-gray-900">
                    {actionBreakdown.reduce((sum, item) => sum + item.count, 0)}
                  </p>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <h3 className="mb-1 text-xs font-medium text-gray-600">
                    Credits Used
                  </h3>
                  <p className="text-2xl font-bold text-gray-900">
                    {actionBreakdown.reduce((sum, item) => sum + item.credits_used, 0)}
                  </p>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <h3 className="mb-1 text-xs font-medium text-gray-600">
                    Available Credits
                  </h3>
                  <p className="text-2xl font-bold text-primary-600">
                    {balance?.available_credits || 0}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

export default function BillingPage() {
  return (
    <Suspense fallback={
      <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
        </div>
      </div>
    }>
      <BillingContent />
    </Suspense>
  )
}
