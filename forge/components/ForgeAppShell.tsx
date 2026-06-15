'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BadgeDollarSign,
  Binary,
  BrainCircuit,
  ClipboardList,
  Code2,
  Gauge,
  HelpCircle,
  LayoutDashboard,
  LogOut,
  Menu,
  Network,
  Settings2,
  Sparkles,
  Swords,
  Users,
} from 'lucide-react'

const navItems = [
  { href: '/workspace', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/onboarding', label: 'Onboarding', icon: ClipboardList },
  { href: '/diagnostic', label: 'Diagnostic', icon: Gauge },
  { href: '/coding', label: 'Coding', icon: Code2 },
  { href: '/system-design', label: 'System Design', icon: Network },
  { href: '/ai-engineering', label: 'AI Engineering', icon: BrainCircuit },
  { href: '/mock-loop', label: 'War Room', icon: Swords },
  { href: '/guild', label: 'Guild Prep', icon: Users },
  { href: '/plans', label: 'Plans', icon: BadgeDollarSign },
  { href: '/admin', label: 'Admin', icon: Settings2 },
]

export default function ForgeAppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(true)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const timeout = window.setTimeout(() => setLoading(false), 760)
    return () => window.clearTimeout(timeout)
  }, [pathname])

  return (
    <div className={`os-page ${collapsed ? 'sidebar-collapsed' : 'sidebar-expanded'}`}>
      {loading ? (
        <div className="forge-loader" aria-label="Loading Synkora Forge">
          <div className="loader-mark">
            <Sparkles size={34} />
          </div>
          <div className="loader-copy">
            <strong>Synkora Forge</strong>
            <span>Calibrating interview signal</span>
          </div>
          <div className="loader-bar"><span /></div>
        </div>
      ) : null}

      <aside className="os-sidebar">
        <div className="sidebar-head">
          <Link href="/" className="os-brand" title="Synkora Forge">
            <span><Binary size={20} /></span>
            <div>
              <strong>Synkora Forge</strong>
              <em>Readiness Console</em>
            </div>
          </Link>
          <button
            type="button"
            className="sidebar-toggle"
            onClick={() => setCollapsed((current) => !current)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <Menu size={20} />
          </button>
        </div>
        <nav className="os-nav" aria-label="Forge product navigation">
          {navItems.map((item) => {
            const active = pathname === item.href
            return (
              <Link key={item.href} href={item.href} className={active ? 'active' : ''} title={item.label}>
                <item.icon size={17} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>
        <div className="os-sidebar-footer">
          <button type="button" title="Help"><HelpCircle size={18} /><span>Help</span></button>
          <button type="button" title="Log out"><LogOut size={18} /><span>Log out</span></button>
        </div>
      </aside>
      <div className="os-main">
        {pathname !== '/workspace' ? (
          <header className="os-topbar">
            <div>
              <span>Private alpha</span>
              <strong>Forge interview operations platform</strong>
            </div>
            <Link href="/diagnostic">Run diagnostic</Link>
          </header>
        ) : null}
        {children}
      </div>
    </div>
  )
}

export function PageHeader({
  kicker,
  title,
  description,
}: {
  kicker: string
  title: string
  description: string
}) {
  return (
    <header className="os-page-header">
      <span>{kicker}</span>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  )
}

export function ScoreBars({
  scores,
}: {
  scores: { label: string; value: number }[]
}) {
  return (
    <div className="score-bars">
      {scores.map((score) => (
        <div key={score.label} className="score-bar-row">
          <div>
            <span>{score.label}</span>
            <strong>{score.value}</strong>
          </div>
          <div className="score-rail">
            <span style={{ width: `${score.value}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}
