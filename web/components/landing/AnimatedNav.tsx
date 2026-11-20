'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useGitHubStars, formatStars } from '@/lib/hooks/useGitHubStars'

const navItems = [
  { href: '/how-it-works', label: 'How It Works' },
  { href: '/pricing', label: 'Pricing' },
  { href: '/integrations', label: 'Integrations' },
  { href: '/alternatives', label: 'Alternatives' },
]

export default function AnimatedNav() {
  const pathname = usePathname()
  const stars = useGitHubStars()

  const isActiveLink = (href: string) => pathname === href || pathname.startsWith(`${href}/`)

  return (
    <nav className="landing fixed top-0 z-50 w-full border-b border-ink/10 bg-paper">
      <div className="mx-auto max-w-[1480px] px-6 py-3 lg:px-10">
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-6 xl:grid-cols-[auto_minmax(0,1fr)_auto]">
          <div className="min-w-0">
            <Link href="/" className="inline-flex flex-col">
              <div className="flex items-center gap-3">
                <span className="whitespace-nowrap text-[2rem] font-semibold leading-none text-ink sm:text-[2.2rem]">
                  SYNKORA
                </span>
              </div>
              <span className="mt-2 whitespace-nowrap text-xs text-ink-mute">
                Enterprise AI Platform
              </span>
            </Link>
          </div>

          <div className="hidden items-center justify-center gap-12 xl:flex">
            {navItems.map((item) => {
              const isActive = isActiveLink(item.href)

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive ? 'page' : undefined}
                  className={`whitespace-nowrap text-[0.94rem] font-medium transition-colors ${
                    isActive ? 'text-ink' : 'text-ink-soft hover:text-black'
                  }`}
                >
                  <span className={isActive ? 'nav-brush-active' : undefined}>{item.label}</span>
                </Link>
              )
            })}
          </div>

          <div className="flex items-center justify-end gap-3 sm:gap-4">
            <a
              href="https://github.com/getsynkora/synkora-ai"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden items-center gap-2 whitespace-nowrap rounded-full border border-black/10 bg-white/65 px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-white lg:inline-flex"
            >
              <svg aria-hidden="true" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              <span className="inline-block min-w-[2rem] text-center">
                {stars !== null ? formatStars(stars) : ''}
              </span>
            </a>
            <Link
              href="/signin"
              className="hidden whitespace-nowrap px-4 py-2 text-sm font-medium text-ink-soft transition-colors hover:text-black sm:inline-flex"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="inline-flex whitespace-nowrap rounded-[1.75rem] bg-ink px-5 py-3 text-sm font-semibold text-paper transition-colors hover:bg-black sm:px-7"
            >
              Get Started
            </Link>
          </div>
        </div>
      </div>
    </nav>
  )
}
