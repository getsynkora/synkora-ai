'use client'

import { useSubscription } from '@/hooks/useBilling'
import { AlertCircle, TrendingUp, Users, Database, Zap, Lock } from 'lucide-react'
import Link from 'next/link'

interface ResourceLimit {
  name: string
  current: number
  limit: number
  icon: React.ReactNode
  upgradeRequired?: boolean
}

interface PlanLimitsCardProps {
  limits?: ResourceLimit[]
  showUpgradePrompt?: boolean
}

export default function PlanLimitsCard({ limits, showUpgradePrompt = true }: PlanLimitsCardProps) {
  const { subscription } = useSubscription()

  // Default limits if not provided
  const defaultLimits: ResourceLimit[] = [
    {
      name: 'Agents',
      current: 0,
      limit: subscription?.plan?.max_agents || 5,
      icon: <Users className="h-5 w-5" />,
    },
    {
      name: 'Knowledge Bases',
      current: 0,
      limit: subscription?.plan?.max_knowledge_bases || 3,
      icon: <Database className="h-5 w-5" />,
    },
    {
      name: 'Team Members',
      current: 0,
      limit: subscription?.plan?.max_team_members || 5,
      icon: <Users className="h-5 w-5" />,
    },
  ]

  const displayLimits = limits || defaultLimits

  const getProgressColor = (current: number, limit: number) => {
    const percentage = (current / limit) * 100
    if (percentage >= 90) return 'bg-ink'
    if (percentage >= 75) return 'bg-warn'
    return 'bg-leaf'
  }

  const getProgressPercentage = (current: number, limit: number) => {
    if (limit === -1) return 0 // Unlimited
    return Math.min((current / limit) * 100, 100)
  }

  return (
    <div className="rounded-lg border border-line bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-ink">Plan Usage</h3>
        {subscription && (
          <span className="rounded-full bg-leaf-wash px-3 py-1 text-sm font-medium text-forest">
            {subscription.plan_name}
          </span>
        )}
      </div>

      <div className="space-y-4">
        {displayLimits.map((resource, index) => {
          const isUnlimited = resource.limit === -1
          const isNearLimit = !isUnlimited && resource.current >= resource.limit * 0.9
          const isAtLimit = !isUnlimited && resource.current >= resource.limit

          return (
            <div key={index} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="text-ink-soft">{resource.icon}</div>
                  <span className="text-sm font-medium text-ink-soft">
                    {resource.name}
                  </span>
                  {resource.upgradeRequired && (
                    <Lock className="h-4 w-4 text-ash" />
                  )}
                </div>
                <span className="text-sm text-ink-soft">
                  {isUnlimited ? (
                    <span className="font-medium text-leaf">Unlimited</span>
                  ) : (
                    <>
                      <span className={isAtLimit ? 'font-semibold text-leaf' : ''}>
                        {resource.current}
                      </span>
                      {' / '}
                      {resource.limit}
                    </>
                  )}
                </span>
              </div>

              {!isUnlimited && (
                <>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-line">
                    <div
                      className={`h-full transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-300 ${getProgressColor(
                        resource.current,
                        resource.limit
                      )}`}
                      style={{
                        width: `${getProgressPercentage(resource.current, resource.limit)}%`,
                      }}
                    />
                  </div>

                  {isNearLimit && (
                    <div className="flex items-start gap-2 rounded-md bg-sand-deep p-2">
                      <AlertCircle className="h-4 w-4 flex-shrink-0 text-warn" />
                      <p className="text-xs text-gold">
                        {isAtLimit
                          ? `You've reached your ${resource.name.toLowerCase()} limit. Upgrade to add more.`
                          : `You're approaching your ${resource.name.toLowerCase()} limit.`}
                      </p>
                    </div>
                  )}
                </>
              )}
            </div>
          )
        })}
      </div>

      {showUpgradePrompt && (
        <div className="mt-6 rounded-lg bg-leaf-wash p-4">
          <div className="flex items-start gap-3">
            <TrendingUp className="h-5 w-5 flex-shrink-0 text-leaf" />
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-ink">
                Need more resources?
              </h4>
              <p className="mt-1 text-xs text-ink-soft">
                Upgrade your plan to unlock higher limits and premium features.
              </p>
              <Link
                href="/billing/subscription"
                className="mt-2 inline-flex items-center text-sm font-medium text-leaf hover:text-forest"
              >
                View Plans
                <Zap className="ml-1 h-4 w-4" />
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
