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
  'rounded-[1.9rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)]'

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
    <div className={`rounded-[1.4rem] border border-black/10 bg-white/80 p-1.5 shadow-[0_12px_28px_rgba(0,0,0,0.04)] ${className}`.trim()}>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => {
          const active = item.id === activeId

          if (onChange) {
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onChange(item.id)}
                className={`inline-flex items-center gap-2 rounded-[1rem] px-4 py-2.5 text-sm font-semibold transition-colors ${
                  active
                    ? 'bg-[#171717] text-white shadow-[0_10px_22px_rgba(0,0,0,0.12)]'
                    : 'text-gray-600 hover:bg-[#f7f2e7] hover:text-[#171717]'
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
              className={`inline-flex items-center gap-2 rounded-[1rem] px-4 py-2.5 text-sm font-semibold ${
                active ? 'bg-[#171717] text-white' : 'text-gray-600'
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
  badge,
  backHref,
  backLabel,
  actions,
  stats,
  children,
  maxWidthClassName = 'max-w-7xl',
  breadcrumbs,
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
                  <Link href={item.href} className="flex items-center gap-1 text-gray-500 transition-colors hover:text-[#171717]">
                    <Home className="h-3.5 w-3.5" />
                    {item.label}
                  </Link>
                ) : item.href && !isLast ? (
                  <Link href={item.href} className="text-gray-500 transition-colors hover:text-[#171717]">
                    {item.label}
                  </Link>
                ) : (
                  <span className={isLast ? 'font-medium text-gray-900' : 'text-gray-500'}>{item.label}</span>
                )}
                {!isLast && <ChevronRight className="h-3.5 w-3.5 text-gray-400" />}
              </div>
            )
          })}
        </div>

        <div className="mb-6 overflow-hidden rounded-[2rem] border border-[#eadfce] bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.96),_rgba(247,240,231,0.94)_50%,_rgba(237,230,220,0.92)_100%)] shadow-[0_28px_80px_-42px_rgba(88,63,39,0.32)]">
          <div className="flex flex-col gap-6 p-6 md:p-8">
            {backHref && backLabel ? (
              <Link
                href={backHref}
                className="inline-flex w-fit items-center gap-2 rounded-full border border-[#dbcdb9] bg-white/80 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:border-[#cdb79d] hover:text-gray-900"
              >
                <ChevronRight className="h-4 w-4 rotate-180" />
                {backLabel}
              </Link>
            ) : null}

            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl space-y-3">
                <div className="inline-flex items-center gap-2 rounded-full border border-[#dfd1be] bg-white/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7c5d45]">
                  <Icon className="h-3.5 w-3.5" />
                  {badge || title}
                </div>

                <div className="flex items-start gap-4">
                  <div className="rounded-[1.2rem] bg-[#f3ecde] p-3.5 shadow-[0_16px_30px_-24px_rgba(74,49,22,0.3)]">
                    <Icon className="h-6 w-6 text-[#171717]" />
                  </div>
                  <div>
                    <h1 className="text-3xl font-semibold tracking-[-0.04em] text-gray-950 md:text-[2.6rem]">
                      {title}
                    </h1>
                    {description ? (
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
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
                      className="rounded-[1.5rem] border border-white/70 bg-white/75 px-4 py-3 shadow-[0_20px_45px_-38px_rgba(77,51,28,0.4)] backdrop-blur"
                    >
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">{stat.label}</p>
                      <div className="mt-2 text-lg font-semibold text-gray-900">{stat.value}</div>
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
