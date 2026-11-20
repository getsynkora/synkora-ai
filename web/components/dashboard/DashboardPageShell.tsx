'use client'

import Link from 'next/link'
import { ChevronRight, Home, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

interface DashboardBreadcrumb {
  label: string
  href?: string
}

interface DashboardHeroStat {
  label: string
  value: ReactNode
}

interface DashboardPageShellProps {
  title: string
  description?: ReactNode
  icon: LucideIcon
  badge?: string
  backHref?: string
  backLabel?: string
  actions?: ReactNode
  stats?: DashboardHeroStat[]
  children: ReactNode
  maxWidthClassName?: string
  breadcrumbs?: DashboardBreadcrumb[]
  heroOverflowVisible?: boolean
}

interface DashboardPagePanelProps {
  children: ReactNode
  className?: string
}

interface DashboardTabItem {
  id: string
  label: ReactNode
  icon?: ReactNode
}

interface DashboardPageTabsProps {
  items: DashboardTabItem[]
  activeId: string
  onChange?: (id: string) => void
  className?: string
}

const panelBaseClassName =
  'rounded-[0.5rem] border border-line bg-white shadow-soft'

export function DashboardPagePanel({ children, className = '' }: DashboardPagePanelProps) {
  return <div className={`${panelBaseClassName} ${className}`.trim()}>{children}</div>
}

export function DashboardPageTabs({
  items,
  activeId,
  onChange,
  className = '',
}: DashboardPageTabsProps) {
  return (
    <div className={`rounded-[0.45rem] border border-black/10 bg-white/80 p-1.5 shadow-soft ${className}`.trim()}>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => {
          const active = item.id === activeId

          if (onChange) {
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onChange(item.id)}
                className={`inline-flex items-center gap-2 rounded-[0.35rem] px-4 py-2.5 text-sm font-semibold transition-colors ${
                  active
                    ? 'bg-ink text-white shadow-soft'
                    : 'text-ink-soft hover:bg-paper hover:text-ink'
                }`}
              >
                {item.icon}
                {item.label}
              </button>
            )
          }

          return (
            <div
              key={item.id}
              className={`inline-flex items-center gap-2 rounded-[0.35rem] px-4 py-2.5 text-sm font-semibold ${
                active ? 'bg-ink text-white' : 'text-ink-soft'
              }`}
            >
              {item.icon}
              {item.label}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function DashboardPageShell({
  title,
  description,
  icon: Icon,
  backHref,
  backLabel,
  actions,
  stats,
  children,
  maxWidthClassName = 'max-w-7xl',
  breadcrumbs,
  heroOverflowVisible = false,
}: DashboardPageShellProps) {
  const crumbItems = breadcrumbs || [
    { label: 'Home', href: '/' },
    { label: title },
  ]

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className={`mx-auto ${maxWidthClassName}`.trim()}>
        <div className="mb-4 flex flex-wrap items-center gap-1.5 text-sm">
          {crumbItems.map((item, index) => {
            const isLast = index === crumbItems.length - 1

            return (
              <div key={`${item.label}-${index}`} className="flex items-center gap-1.5">
                {index === 0 && item.label === 'Home' && item.href ? (
                  <Link href={item.href} className="flex items-center gap-1 text-ink-mute transition-colors hover:text-ink">
                    <Home className="h-3.5 w-3.5" />
                    {item.label}
                  </Link>
                ) : item.href && !isLast ? (
                  <Link href={item.href} className="text-ink-mute transition-colors hover:text-ink">
                    {item.label}
                  </Link>
                ) : (
                  <span className={isLast ? 'font-medium text-ink' : 'text-ink-mute'}>{item.label}</span>
                )}
                {!isLast && <ChevronRight className="h-3.5 w-3.5 text-ash" />}
              </div>
            )
          })}
        </div>

        <div className={`bg-cream mb-6 rounded-[0.5rem] border border-sand-deep shadow-soft ${heroOverflowVisible ? 'overflow-visible' : 'overflow-hidden'}`}>
          <div className="flex flex-col gap-6 p-6 md:p-8">
            {backHref && backLabel ? (
              <Link
                href={backHref}
                className="inline-flex w-fit items-center gap-2 rounded-[0.35rem] border border-line bg-white/80 px-4 py-2 text-sm font-semibold text-ink-soft transition-colors hover:border-tan hover:text-ink"
              >
                <ChevronRight className="h-4 w-4 rotate-180" />
                {backLabel}
              </Link>
            ) : null}

            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl space-y-3">

                <div className="flex items-start gap-4">
                  <div className="rounded-[0.45rem] bg-sand p-3.5 shadow-soft">
                    <Icon className="h-6 w-6 text-ink" />
                  </div>
                  <div>
                    <h1 className="text-3xl font-semibold tracking-[-0.04em] text-ink md:text-[2.6rem]">
                      {title}
                    </h1>
                    {description ? (
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-soft">
                        {description}
                      </p>
                    ) : null}
                  </div>
                </div>
              </div>

              {actions ? (
                <div className="flex flex-wrap items-center gap-3">
                  {actions}
                </div>
              ) : stats && stats.length > 0 ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {stats.map((stat) => (
                    <div
                      key={stat.label}
                      className="rounded-[0.45rem] border border-white/70 bg-white/75 px-4 py-3 shadow-soft"
                    >
                      <p className="text-[11px] font-semibold text-clay">{stat.label}</p>
                      <div className="mt-2 text-lg font-semibold text-ink">{stat.value}</div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {children}
      </div>
    </div>
  )
}
