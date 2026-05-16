'use client'

import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
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
  const [scrolled, setScrolled] = useState(false)
  const pathname = usePathname()
  const navRef = useRef<HTMLElement>(null)
  const brandRef = useRef<HTMLDivElement>(null)
  const centerRef = useRef<HTMLDivElement>(null)
  const actionsRef = useRef<HTMLDivElement>(null)
  const stars = useGitHubStars()

  const isActiveLink = (href: string) => pathname === href || pathname.startsWith(`${href}/`)

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 16)
    }

    gsap.fromTo(brandRef.current, { opacity: 0, x: -24 }, { opacity: 1, x: 0, duration: 0.75, ease: 'power3.out' })
    gsap.fromTo(centerRef.current?.children || [], { opacity: 0, y: -14 }, { opacity: 1, y: 0, duration: 0.5, stagger: 0.06, delay: 0.15, ease: 'power2.out' })
    gsap.fromTo(actionsRef.current?.children || [], { opacity: 0, x: 18 }, { opacity: 1, x: 0, duration: 0.55, stagger: 0.07, delay: 0.2, ease: 'power2.out' })

    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <nav
      ref={navRef}
      className={`fixed top-0 z-50 w-full border-b transition-all duration-300 ${
        scrolled
          ? 'border-black/10 bg-[#f7f2e7]/92 backdrop-blur-xl'
          : 'border-transparent bg-[#f7f2e7]/76 backdrop-blur-md'
      }`}
    >
      <div className="mx-auto max-w-[1480px] px-6 py-3 lg:px-10">
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-6 xl:grid-cols-[auto_minmax(0,1fr)_auto]">
          <div ref={brandRef} className="min-w-0">
            <Link href="/" className="inline-flex flex-col">
              <div className="flex items-center gap-3">
                <span className="whitespace-nowrap text-[2rem] font-semibold leading-none tracking-[0.18em] text-[#141414] sm:text-[2.2rem]">
                  SYNKORA
                </span>
                <span className="rounded-full border border-black/10 bg-white/65 px-2.5 py-1 text-[10px] font-semibold uppercase leading-none tracking-[0.24em] text-[#5d564c]">
                  Beta
                </span>
              </div>
              <span className="mt-2 whitespace-nowrap text-xs uppercase tracking-[0.22em] text-[#7a7267]">
                Open-source AI platform
              </span>
            </Link>
          </div>

          <div
            ref={centerRef}
            className="hidden items-center justify-center gap-12 xl:flex"
          >
            {navItems.map((item) => {
              const isActive = isActiveLink(item.href)

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive ? 'page' : undefined}
                  className={`whitespace-nowrap text-[0.94rem] font-medium uppercase tracking-[0.18em] transition-colors ${
                    isActive ? 'text-[#171717]' : 'text-[#4e473e] hover:text-black'
                  }`}
                >
                  <span className={isActive ? 'nav-brush-active' : undefined}>{item.label}</span>
                </Link>
              )
            })}
          </div>

          <div ref={actionsRef} className="flex items-center justify-end gap-3 sm:gap-4">
            <a
              href="https://github.com/getsynkora/synkora-ai"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden items-center gap-2 whitespace-nowrap rounded-full border border-black/10 bg-white/65 px-4 py-2.5 text-sm font-medium text-[#1d1a15] transition-colors hover:bg-white lg:inline-flex"
            >
              <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              {stars !== null ? formatStars(stars) : 'Star'}
            </a>
            <Link
              href="/signin"
              className="hidden whitespace-nowrap px-4 py-2 text-sm font-medium text-[#4e473e] transition-colors hover:text-black sm:inline-flex"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="inline-flex whitespace-nowrap rounded-[1.75rem] bg-[#181818] px-5 py-3 text-sm font-semibold uppercase tracking-[0.18em] text-[#f7f2e7] transition-transform hover:-translate-y-0.5 sm:px-7"
            >
              Get Started
            </Link>
          </div>
        </div>
      </div>
    </nav>
  )
}
