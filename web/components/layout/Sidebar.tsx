'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuthStore } from '@/lib/store/authStore'
import { usePermissions } from '@/hooks/usePermissions'
import { cn } from '@/lib/utils/cn'

interface NavItem {
  name: string
  href: string
  icon: React.ReactNode
}

interface NavGroup {
  name: string
  icon: React.ReactNode
  children: NavItem[]
}

type NavEntry = NavItem | NavGroup

function isGroup(entry: NavEntry): entry is NavGroup {
  return 'children' in entry
}

const navigation: NavEntry[] = [
  {
    name: 'Dashboard',
    href: '/dashboard',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    )
  },
  {
    name: 'Agents',
    href: '/agents',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    )
  },
  {
    name: 'Browse Agents',
    href: '/browse',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    )
  },
  {
    name: 'MCP Servers',
    href: '/mcp-servers',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
      </svg>
    )
  },
  {
    name: 'Custom Tools',
    href: '/custom-tools',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
      </svg>
    )
  },
  {
    name: 'Knowledge Bases',
    href: '/knowledge-bases',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
    )
  },
  {
    name: 'Data Sources',
    href: '/data-sources',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
      </svg>
    )
  },
  {
    name: 'Database Connections',
    href: '/database-connections',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
      </svg>
    )
  },
  // Products submenu
  {
    name: 'Products',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
    ),
    children: [
      {
        name: 'Rate My Life',
        href: '/rate-my-life',
        icon: (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
          </svg>
        )
      },
      {
        name: 'War Room',
        href: '/war-room',
        icon: (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
        )
      },
      {
        name: 'Live Lab',
        href: '/live-lab',
        icon: (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
        )
      },
      {
        name: 'Load Testing',
        href: '/load-testing',
        icon: (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        )
      },
    ]
  },
  {
    name: 'Scheduled Tasks',
    href: '/scheduled-tasks',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    )
  },
  {
    name: 'Projects',
    href: '/projects',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
      </svg>
    )
  },
  {
    name: 'Escalations',
    href: '/escalations',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    )
  },
  {
    name: 'Integrations',
    href: '/oauth-apps',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
      </svg>
    )
  },
  {
    name: 'Email Templates',
    href: '/email-templates',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    )
  },
  {
    name: 'Billing',
    href: '/billing',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
      </svg>
    )
  },
]

const settingsNavigation = [
  {
    name: 'Profile',
    href: '/settings/profile',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    )
  },
  {
    name: 'Human Contacts',
    href: '/settings/human-contacts',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    )
  },
  {
    name: 'Team',
    href: '/settings/team',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    )
  },
  {
    name: 'Social Auth',
    href: '/settings/social-auth-config',
    platformOnly: true,
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
      </svg>
    )
  },
  {
    name: 'SAML / SSO',
    href: '/settings/saml-config',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    )
  },
  {
    name: 'Activity',
    href: '/settings/activity',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
      </svg>
    )
  },
  {
    name: 'Integrations',
    href: '/settings/integrations',
    permission: { resource: 'integration_configs', action: 'read' },
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z" />
      </svg>
    )
  },
  {
    name: 'Subscription Plans',
    href: '/settings/subscription-plans',
    platformOnly: true,
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    )
  },
  {
    name: 'Compute',
    href: '/settings/compute',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
      </svg>
    )
  },
  {
    name: 'Creator Profile',
    href: '/settings/creator-profile',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
      </svg>
    )
  },
  {
    name: 'Earnings',
    href: '/settings/creator-profile?tab=earnings',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    )
  },
  {
    name: 'My Subscriptions',
    href: '/settings/agent-subscriptions',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    )
  },
]

interface SidebarProps {
  mobileOpen?: boolean
  onMobileClose?: () => void
}

export function Sidebar({ mobileOpen = false, onMobileClose }: SidebarProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isPinned, setIsPinned] = useState(false)
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})
  const pathname = usePathname()
  const user = useAuthStore((state) => state.user)
  const { hasPermission } = usePermissions()

  // Auto-expand group if a child route is active
  useEffect(() => {
    for (const entry of navigation) {
      if (isGroup(entry)) {
        const hasActiveChild = entry.children.some(child => pathname?.startsWith(child.href))
        if (hasActiveChild) {
          setExpandedGroups(prev => ({ ...prev, [entry.name]: true }))
        }
      }
    }
  }, [pathname])

  // Close mobile sidebar on route change
  useEffect(() => {
    onMobileClose?.()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname])

  const handleMouseEnter = () => {
    if (!isPinned) {
      setIsExpanded(true)
    }
  }

  const handleMouseLeave = () => {
    if (!isPinned) {
      setIsExpanded(false)
    }
  }

  const togglePin = () => {
    setIsPinned(!isPinned)
    setIsExpanded(!isPinned)
  }

  const toggleGroup = (name: string) => {
    setExpandedGroups(prev => ({ ...prev, [name]: !prev[name] }))
  }

  // Labels are visible when desktop-expanded/pinned OR when mobile drawer is open
  const showLabels = isExpanded || isPinned || mobileOpen

  const renderNavItem = (item: NavItem, isChild = false) => {
    const isActive = pathname?.startsWith(item.href)
    return (
      <Link
        key={item.name}
        href={item.href}
        prefetch={false}
        className={cn(
          'relative flex items-center gap-3 overflow-hidden rounded-[1.2rem] transition-all',
          isChild ? 'px-3 py-2.5' : showLabels ? 'px-4 py-3.5' : 'mx-auto w-16 justify-center px-0 py-4',
          isActive
            ? 'border border-white/10 bg-white/[0.12] text-[#f7f2e7] shadow-[0_14px_30px_rgba(0,0,0,0.22)]'
            : 'text-[#b7afa2] hover:bg-white/[0.06] hover:text-[#f7f2e7]'
        )}
      >
        {isActive && (
          <span className="absolute left-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-r-full bg-[#7de5c1]" aria-hidden="true" />
        )}
        <div className={cn(
          'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full transition-colors',
          isActive ? 'bg-white/[0.1] text-[#f7f2e7]' : 'text-current'
        )}>
          {item.icon}
        </div>
        {showLabels && (
          <span className={cn(
            'whitespace-nowrap',
            isChild ? 'text-xs' : 'text-sm',
            isActive ? 'font-semibold text-[#fffaf0]' : 'font-medium'
          )}>
            {item.name}
          </span>
        )}
      </Link>
    )
  }

  const renderNavGroup = (group: NavGroup) => {
    const isOpen = expandedGroups[group.name] ?? false
    const hasActiveChild = group.children.some(child => pathname?.startsWith(child.href))

    return (
      <div key={group.name}>
        <button
          onClick={() => showLabels && toggleGroup(group.name)}
          className={cn(
            'relative w-full flex items-center gap-3 overflow-hidden px-3 py-3 rounded-[1.2rem] transition-all',
            showLabels ? 'px-4 py-3.5' : 'mx-auto w-16 justify-center px-0 py-4',
            hasActiveChild
              ? 'border border-white/10 bg-white/[0.1] text-[#f7f2e7]'
              : 'text-[#b7afa2] hover:bg-white/[0.06] hover:text-[#f7f2e7]'
          )}
        >
          {hasActiveChild && (
            <span className="absolute left-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-r-full bg-[#7de5c1]" aria-hidden="true" />
          )}
          <div className={cn(
            'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full transition-colors',
            hasActiveChild ? 'bg-white/[0.1] text-[#f7f2e7]' : 'text-current'
          )}>
            {group.icon}
          </div>
          {showLabels && (
            <>
              <span className={cn(
                'flex-1 whitespace-nowrap text-left text-sm',
                hasActiveChild ? 'font-semibold text-[#fffaf0]' : 'font-medium'
              )}>
                {group.name}
              </span>
              <svg
                className={cn(
                  'w-4 h-4 transition-transform duration-200 flex-shrink-0',
                  isOpen ? 'rotate-180' : 'rotate-0'
                )}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </>
          )}
        </button>
        {showLabels && isOpen && (
          <div className="ml-5 mt-1 mb-2 space-y-1 border-l border-white/10 pl-3.5">
            {group.children.map(child => renderNavItem(child, true))}
          </div>
        )}
      </div>
    )
  }

  return (
    <>
      {/* Mobile backdrop overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={onMobileClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar panel */}
      <div
        className={cn(
          'h-screen flex flex-col border-r border-white/8 bg-[#111111] py-6 shadow-[0_24px_60px_rgba(0,0,0,0.28)] transition-all duration-300 flex-shrink-0',
          // Mobile: fixed overlay; desktop: static in flex flow
          'fixed inset-y-0 left-0 z-50 md:relative md:inset-y-auto md:left-auto md:z-auto',
          // Mobile slide animation; desktop always visible
          mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
          // Width: mobile always w-64; desktop responsive
          'w-64',
          isExpanded || isPinned ? 'md:w-64' : 'md:w-24',
        )}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        {/* Logo and Pin Button */}
        <div className="mb-8 px-5">
          <div className={cn('flex items-center', showLabels ? 'justify-between' : 'justify-center')}>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-[#f7f2e7] text-[#111111] shadow-[0_8px_24px_rgba(0,0,0,0.24)]">
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              {showLabels && (
                <div className="flex flex-col">
                  <div className="flex items-center gap-3">
                    <span className="whitespace-nowrap text-[1.35rem] font-semibold uppercase tracking-[0.18em] text-[#f7f2e7]">
                      SYNKORA
                    </span>
                    <span className="rounded-full border border-white/10 bg-white/[0.08] px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.2em] text-[#d2cabf]">Beta</span>
                  </div>
                  <span className="mt-1 text-[10px] uppercase tracking-[0.22em] text-[#857d70]">Enterprise platform</span>
                </div>
              )}
            </div>
            {/* Pin toggle — hidden on mobile (close via backdrop instead) */}
            {showLabels && !mobileOpen && (
              <button
                onClick={togglePin}
                className="flex items-center gap-2 rounded-lg p-1 transition-colors hover:bg-white/8"
                title={isPinned ? 'Unlock sidebar' : 'Lock sidebar'}
              >
                <div className={cn(
                  'relative w-10 h-5 rounded-full transition-colors',
                  isPinned ? 'bg-[#f7f2e7]' : 'bg-white/18'
                )}>
                  <div className={cn(
                    'absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-[#111111] transition-transform',
                    isPinned ? 'translate-x-5' : 'translate-x-0'
                  )} />
                </div>
              </button>
            )}
            {/* Close button on mobile */}
            {mobileOpen && (
              <button
                onClick={onMobileClose}
                className="rounded-lg p-1.5 text-[#b7afa2] transition-colors hover:bg-white/8 hover:text-[#f7f2e7]"
                aria-label="Close menu"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className={cn(
          'flex-1 flex flex-col overflow-y-auto',
          showLabels ? 'space-y-2.5 px-4' : 'space-y-2 px-3'
        )}>
          {navigation.map((entry) =>
            isGroup(entry) ? renderNavGroup(entry) : renderNavItem(entry)
          )}

          {/* Settings Section */}
          <div className="mt-4 border-t border-white/10 pt-4">
            {showLabels && (
              <div className="px-4 mb-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#857d70]">
                  Settings
                </span>
              </div>
            )}
            {settingsNavigation.map((item) => {
              if (item.permission && !hasPermission(item.permission.resource, item.permission.action)) {
                return null
              }
              if (item.platformOnly && !hasPermission('platform', 'read')) {
                return null
              }
              const isActive = pathname?.startsWith(item.href)
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  prefetch={false}
                  className={cn(
                    'relative flex items-center gap-3 overflow-hidden px-3 py-3 rounded-[1.2rem] transition-all',
                    showLabels ? 'px-4 py-3.5' : 'mx-auto w-16 justify-center px-0 py-4',
                    isActive
                      ? 'border border-white/10 bg-white/[0.12] text-[#f7f2e7] shadow-[0_14px_30px_rgba(0,0,0,0.22)]'
                      : 'text-[#b7afa2] hover:bg-white/[0.06] hover:text-[#f7f2e7]'
                  )}
                >
                  {isActive && (
                    <span className="absolute left-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-r-full bg-[#7de5c1]" aria-hidden="true" />
                  )}
                  <div className={cn(
                    'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full transition-colors',
                    isActive ? 'bg-white/[0.1] text-[#f7f2e7]' : 'text-current'
                  )}>
                    {item.icon}
                  </div>
                  {showLabels && (
                    <span className={cn(
                      'whitespace-nowrap text-sm',
                      isActive ? 'font-semibold text-[#fffaf0]' : 'font-medium'
                    )}>
                      {item.name}
                    </span>
                  )}
                </Link>
              )
            })}
          </div>
        </nav>

        {/* User Section */}
        <div className={cn('mt-auto', showLabels ? 'px-4' : 'px-3')}>
          <div className={cn(showLabels ? 'flex items-center gap-3 rounded-[1.2rem] border border-white/10 bg-white/[0.06] p-4 transition-colors hover:bg-white/[0.1]' : 'flex justify-center')}>
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-[#f7f2e7] text-sm font-semibold text-[#111111]">
            {user?.name?.charAt(0).toUpperCase() || 'U'}
          </div>
          {showLabels && (
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium text-[#f7f2e7]">{user?.name || 'User'}</p>
              <p className="truncate text-xs text-[#8b8377]">{user?.email || ''}</p>
            </div>
          )}
        </div>
        </div>
      </div>
    </>
  )
}
