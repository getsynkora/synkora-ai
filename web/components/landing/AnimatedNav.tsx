'use client'

import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import Link from 'next/link'

export default function AnimatedNav() {
  const [scrolled, setScrolled] = useState(false)
  const navRef = useRef<HTMLElement>(null)
  const logoRef = useRef<HTMLDivElement>(null)
  const linksRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20)
    }

    // Initial animation
    gsap.fromTo(logoRef.current,
      { opacity: 0, x: -50 },
      { opacity: 1, x: 0, duration: 0.8, ease: 'power3.out' }
    )

    const navLinks = linksRef.current ? Array.from(linksRef.current.children) : []
    if (navLinks.length > 0) {
      gsap.fromTo(navLinks,
        { opacity: 0, y: -20 },
        { opacity: 1, y: 0, duration: 0.6, stagger: 0.1, delay: 0.3, ease: 'power2.out' }
      )
    }

    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <nav
      ref={navRef}
      className={`fixed top-0 w-full z-50 transition-all duration-300 ${
        scrolled ? 'bg-white/80 backdrop-blur-lg shadow-sm' : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div ref={logoRef} className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary-500 rounded-xl flex items-center justify-center">
              <svg
                className="w-6 h-6 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-gray-900">Synkora</span>
                <span className="px-1.5 py-0.5 bg-red-100 text-red-600 text-[10px] font-bold rounded uppercase tracking-wider">Beta</span>
              </div>
              <span className="text-xs text-gray-600 -mt-1">Open-source AI platform</span>
            </div>
          </div>

          {/* Navigation Links */}
          <div ref={linksRef} className="flex items-center gap-6">
            <Link
              href="/how-it-works"
              className="text-gray-600 hover:text-gray-900 font-medium transition-colors hidden md:block"
            >
              How It Works
            </Link>
            <Link
              href="/pricing"
              className="text-gray-600 hover:text-gray-900 font-medium transition-colors hidden md:block"
            >
              Pricing
            </Link>
            <Link
              href="/alternatives"
              className="text-gray-600 hover:text-gray-900 font-medium transition-colors hidden md:block"
            >
              Alternatives
            </Link>
            {/* GitHub Star */}
            <a
              href="https://github.com/getsynkora/synkora-ai"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden md:inline-flex items-center gap-2 px-3 py-1.5 bg-gray-900 hover:bg-gray-700 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              <span>Star on GitHub</span>
              <svg className="w-3.5 h-3.5 text-yellow-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
            </a>
            <Link
              href="/signin"
              className="px-5 py-2 text-gray-700 hover:text-gray-900 font-medium transition-colors"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="px-5 py-2 bg-primary-500 hover:bg-primary-600 text-white font-medium rounded-lg transition-colors shadow-lg shadow-primary-500/30"
            >
              Get Started
            </Link>
          </div>
        </div>
      </div>
    </nav>
  )
}
