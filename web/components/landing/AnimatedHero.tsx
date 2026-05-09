'use client'

import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import Link from 'next/link'
import { Check } from 'lucide-react'

export default function AnimatedHero() {
  const heroRef = useRef<HTMLDivElement>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ctx = gsap.context(() => {
      const titleWords = titleRef.current ? Array.from(titleRef.current.querySelectorAll('.word')) : []

      if (titleWords.length > 0) {
        gsap.fromTo(titleWords,
          { opacity: 0, scale: 0.5, filter: 'blur(20px)', y: 100 },
          { opacity: 1, scale: 1, filter: 'blur(0px)', y: 0, duration: 1.2, stagger: 0.12, ease: 'expo.out', delay: 0.3 }
        )
      }

      gsap.fromTo('.hero-badge',
        { opacity: 0, y: -30, scale: 0.8 },
        { opacity: 1, y: 0, scale: 1, duration: 0.8, ease: 'back.out(1.7)' }
      )

      gsap.fromTo('.hero-subtext',
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, duration: 0.8, delay: 1.2, ease: 'power2.out' }
      )

      gsap.fromTo('.hero-cta',
        { opacity: 0, y: 30, scale: 0.9 },
        { opacity: 1, y: 0, scale: 1, duration: 0.6, delay: 1.5, stagger: 0.1, ease: 'back.out(1.7)' }
      )

      gsap.fromTo('.hero-trust',
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.6, delay: 1.8, stagger: 0.08, ease: 'power2.out' }
      )

      gsap.to('.orb', {
        y: '+=30', duration: 3, ease: 'sine.inOut', yoyo: true, repeat: -1,
        stagger: { each: 0.5, from: 'random' }
      })
      gsap.to('.orb', {
        x: '+=20', duration: 4, ease: 'sine.inOut', yoyo: true, repeat: -1,
        stagger: { each: 0.7, from: 'random' }
      })
    }, heroRef)

    return () => ctx.revert()
  }, [])

  useEffect(() => {
    const grid = gridRef.current
    if (!grid) return

    const handleMouseMove = (e: MouseEvent) => {
      const rect = grid.getBoundingClientRect()
      const x = ((e.clientX - rect.left) / rect.width - 0.5) * 40
      const y = ((e.clientY - rect.top) / rect.height - 0.5) * 40
      gsap.to(grid, { x, y, duration: 1.2, ease: 'power2.out' })
    }

    grid.addEventListener('mousemove', handleMouseMove)
    return () => grid.removeEventListener('mousemove', handleMouseMove)
  }, [])

  return (
    <div ref={heroRef} className="relative min-h-screen overflow-hidden bg-gradient-to-br from-gray-50 via-white to-red-50">
      {/* Animated Grid Background */}
      <div className="absolute inset-0 overflow-hidden opacity-30">
        <div
          ref={gridRef}
          className="absolute inset-0"
          style={{
            backgroundImage: `
              linear-gradient(to right, rgb(255 68 79 / 0.1) 1px, transparent 1px),
              linear-gradient(to bottom, rgb(255 68 79 / 0.1) 1px, transparent 1px)
            `,
            backgroundSize: '80px 80px'
          }}
        />
      </div>

      {/* Floating Orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="orb absolute top-20 left-[10%] w-64 h-64 bg-gradient-to-br from-red-400/30 to-rose-400/30 rounded-full blur-3xl" />
        <div className="orb absolute top-40 right-[15%] w-96 h-96 bg-gradient-to-br from-red-400/20 to-pink-400/20 rounded-full blur-3xl" />
        <div className="orb absolute bottom-20 left-[20%] w-80 h-80 bg-gradient-to-br from-pink-400/25 to-red-400/25 rounded-full blur-3xl" />
        <div className="orb absolute bottom-40 right-[10%] w-72 h-72 bg-gradient-to-br from-red-400/30 to-rose-400/30 rounded-full blur-3xl" />
      </div>

      {/* Content */}
      <div className="relative z-10 pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-4xl mx-auto">

            {/* Badge */}
            <div className="hero-badge inline-flex items-center gap-3 px-4 py-2 bg-white border border-gray-200 rounded-full shadow-sm mb-8">
              <div className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-gray-800" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
                <span className="text-sm font-semibold text-gray-800">Open Source</span>
              </div>
              <span className="text-gray-300">|</span>
              <span className="text-sm font-medium text-gray-500">MIT License</span>
              <span className="text-gray-300">|</span>
              <span className="flex items-center gap-1 text-sm font-medium text-gray-500">
                <svg className="w-3.5 h-3.5 text-yellow-400 fill-current" viewBox="0 0 24 24">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                </svg>
                Star us on GitHub
              </span>
            </div>

            {/* Headline */}
            <h1 ref={titleRef} className="text-5xl md:text-7xl font-bold text-gray-900 mb-6 leading-tight">
              <span className="word inline-block mr-3">The</span>
              <span className="word inline-block mr-3">AI</span>
              <span className="word inline-block mr-3">agent</span>
              <span className="word inline-block mr-3">platform</span>
              <br />
              <span className="word inline-block text-red-500 mr-3">your</span>
              <span className="word inline-block text-red-500 mr-3">team</span>
              <span className="word inline-block text-red-500 mr-3">actually</span>
              <span className="word inline-block text-red-500">owns</span>
            </h1>

            {/* Subheadline */}
            <p className="hero-subtext text-xl text-gray-600 mb-10 max-w-2xl mx-auto leading-relaxed">
              Build agents that connect to your data, deploy to Slack, WhatsApp, Teams, and your product — using your own OpenAI or Anthropic keys. Self-host for free or use Synkora Cloud.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
              <Link
                href="https://app.synkora.ai/signup"
                className="hero-cta w-full sm:w-auto px-8 py-4 bg-red-500 hover:bg-red-600 text-white text-lg font-semibold rounded-xl transition-all shadow-xl shadow-red-500/30 hover:shadow-2xl hover:shadow-red-500/40 hover:scale-105 text-center"
              >
                Start Building Free
              </Link>
              <a
                href="#demo"
                className="hero-cta w-full sm:w-auto px-8 py-4 bg-gray-900 hover:bg-gray-800 text-white text-lg font-semibold rounded-xl transition-all shadow-xl hover:shadow-2xl hover:scale-105 flex items-center justify-center gap-2"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
                Watch Demo
              </a>
            </div>

            {/* Trust signals */}
            <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
              {[
                'No vendor lock-in',
                'Bring your own LLM keys',
                'Self-host on your infrastructure',
                'Slack · WhatsApp · Teams · API',
              ].map((item, i) => (
                <div key={i} className="hero-trust flex items-center gap-1.5 text-sm text-gray-500">
                  <Check className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                  {item}
                </div>
              ))}
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
