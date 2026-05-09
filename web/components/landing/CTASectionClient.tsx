'use client'

import Link from 'next/link'
import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Zap } from 'lucide-react'
import Footer from '@/components/landing/Footer'

gsap.registerPlugin(ScrollTrigger)

export default function CTASectionClient() {
  const ctaSectionRef = useRef<HTMLElement>(null)
  const footerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const triggers: ScrollTrigger[] = []

    if (ctaSectionRef.current) {
      const ctaBox = ctaSectionRef.current.querySelector('.cta-box')
      if (ctaBox) {
        const t = ScrollTrigger.create({
          trigger: ctaSectionRef.current,
          start: 'top 80%',
          onEnter: () => {
            gsap.fromTo(ctaBox,
              { opacity: 0, scale: 0.9, y: 50 },
              { opacity: 1, scale: 1, y: 0, duration: 1, ease: 'back.out(1.4)' }
            )
          },
          once: true,
        })
        triggers.push(t)
      }
    }

    if (footerRef.current) {
      const t = ScrollTrigger.create({
        trigger: footerRef.current,
        start: 'top 90%',
        onEnter: () => {
          gsap.fromTo(footerRef.current,
            { opacity: 0, y: 30 },
            { opacity: 1, y: 0, duration: 0.8 }
          )
        },
        once: true,
      })
      triggers.push(t)
    }

    return () => { triggers.forEach(t => t.kill()) }
  }, [])

  return (
    <>
      <section ref={ctaSectionRef} className="py-14 sm:py-20 px-4 sm:px-6 bg-white">
        <div className="max-w-4xl mx-auto text-center">
          <div className="cta-box bg-gradient-to-br from-red-600 via-red-500 to-rose-600 rounded-3xl p-12 md:p-16 shadow-2xl shadow-red-500/20 relative overflow-hidden">
            <div className="absolute inset-0 opacity-30">
              <div className="absolute top-0 right-0 w-64 h-64 bg-white/20 rounded-full blur-3xl -translate-y-32 translate-x-32" />
              <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/15 rounded-full blur-2xl translate-y-24 -translate-x-24" />
            </div>
            <div className="relative">
              <h2 className="text-4xl md:text-5xl font-bold text-white mb-5">
                Own your AI infrastructure
              </h2>
              <p className="text-lg md:text-xl text-white/90 mb-8 max-w-xl mx-auto">
                No vendor lock-in. Your LLM keys. Your data. Deploy to Slack, WhatsApp, Teams, and your product — all from one platform you control.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="https://app.synkora.ai/signup"
                  className="inline-flex items-center gap-2 px-8 py-4 bg-white hover:bg-gray-50 text-red-600 font-semibold rounded-xl transition-all shadow-lg"
                >
                  <Zap className="w-5 h-5" />
                  Get Started Free
                </Link>
                <a
                  href="https://github.com/getsynkora/synkora-ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-8 py-4 bg-white/10 hover:bg-white/20 text-white font-semibold rounded-xl transition-all border border-white/20"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                  </svg>
                  Star on GitHub
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div ref={footerRef}>
        <Footer />
      </div>
    </>
  )
}
