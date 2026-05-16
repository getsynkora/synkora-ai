'use client'

import Link from 'next/link'
import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Zap } from 'lucide-react'
import Footer from '@/components/landing/Footer'
import { useGitHubStars, formatStars } from '@/lib/hooks/useGitHubStars'

gsap.registerPlugin(ScrollTrigger)

export default function CTASectionClient() {
  const ctaSectionRef = useRef<HTMLElement>(null)
  const footerRef = useRef<HTMLDivElement>(null)
  const ctaBoxRef = useRef<HTMLDivElement>(null)
  const stars = useGitHubStars()

  useEffect(() => {
    const triggers: ScrollTrigger[] = []
    const ctaBox = ctaBoxRef.current

    if (ctaSectionRef.current && ctaBox) {
      const t = ScrollTrigger.create({
        trigger: ctaSectionRef.current,
        start: 'top 80%',
        onEnter: () => {
          const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })
          tl.fromTo(
            ctaBox,
            { opacity: 0, scale: 0.94, y: 52, filter: 'blur(14px)' },
            { opacity: 1, scale: 1, y: 0, filter: 'blur(0px)', duration: 1.02 }
          )
          tl.fromTo(
            '.cta-kicker, .cta-line, .cta-actions',
            { opacity: 0, y: 24 },
            { opacity: 1, y: 0, duration: 0.7, stagger: 0.1 },
            '-=0.56'
          )
          tl.fromTo(
            '.cta-float',
            { opacity: 0, y: 20, scale: 0.88 },
            { opacity: 1, y: 0, scale: 1, duration: 0.65, stagger: 0.12 },
            '-=0.52'
          )
        },
        once: true,
      })
      triggers.push(t)
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

    if (ctaBox) {
      gsap.utils.toArray<HTMLElement>('.cta-orb').forEach((orb, index) => {
        gsap.to(orb, {
          x: index % 2 === 0 ? 22 : -18,
          y: index % 2 === 0 ? -16 : 20,
          duration: 6.2 + index,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
        })
      })

      gsap.utils.toArray<HTMLElement>('.cta-beam').forEach((beam, index) => {
        gsap.fromTo(
          beam,
          { xPercent: index % 2 === 0 ? -10 : 10, opacity: 0.18 },
          { xPercent: index % 2 === 0 ? 10 : -10, opacity: 0.42, duration: 4.6 + index * 0.6, repeat: -1, yoyo: true, ease: 'sine.inOut' }
        )
      })

      gsap.utils.toArray<HTMLElement>('.cta-pulse-ring').forEach((ring, index) => {
        gsap.fromTo(
          ring,
          { scale: 0.82, opacity: 0.32 },
          { scale: 1.18 + index * 0.04, opacity: 0, duration: 2.8 + index * 0.3, repeat: -1, delay: index * 0.35, ease: 'power1.out' }
        )
      })

      gsap.utils.toArray<HTMLElement>('.cta-float').forEach((card, index) => {
        gsap.to(card, {
          y: index % 2 === 0 ? -10 : 10,
          rotate: index % 2 === 0 ? '+=1.2' : '-=1.2',
          duration: 5 + index * 0.8,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
        })
      })
    }

    return () => { triggers.forEach(t => t.kill()) }
  }, [])

  return (
    <>
      <section ref={ctaSectionRef} className="bg-[#f7f2e7] px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-4xl mx-auto text-center">
          <div
            ref={ctaBoxRef}
            className="cta-box relative overflow-hidden rounded-[2.7rem] border border-black/10 bg-[#171717] p-12 shadow-[0_34px_90px_rgba(0,0,0,0.2)] md:p-16"
          >
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.08),transparent_24%),radial-gradient(circle_at_82%_18%,rgba(125,229,193,0.16),transparent_22%),radial-gradient(circle_at_18%_80%,rgba(255,143,178,0.12),transparent_20%)]" />
            <div className="absolute inset-[10px] rounded-[2.25rem] border border-white/8" />
            <div className="absolute inset-0 opacity-40">
              <div className="cta-orb absolute right-0 top-0 h-64 w-64 -translate-y-32 translate-x-32 rounded-full bg-white/12 blur-3xl" />
              <div className="cta-orb absolute bottom-0 left-0 h-48 w-48 -translate-x-24 translate-y-24 rounded-full bg-[#7de5c1]/18 blur-2xl" />
              <div className="cta-orb absolute left-[36%] top-[24%] h-40 w-40 rounded-full bg-[#ff8fb2]/16 blur-3xl" />
            </div>
            <div className="cta-beam absolute left-[-8%] top-[18%] h-44 w-[42%] rotate-[16deg] rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.22),transparent_72%)] blur-3xl" />
            <div className="cta-beam absolute right-[-8%] top-[42%] h-44 w-[36%] -rotate-[12deg] rounded-full bg-[radial-gradient(circle,rgba(255,143,178,0.16),transparent_72%)] blur-3xl" />
            <div className="relative">
              <div className="cta-kicker mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/6 px-3 py-1.5 font-mono text-sm text-[#7de5c1]">
                <span className="h-2 w-2 rounded-full bg-[#7de5c1]" />
                Own the stack
              </div>
              <div className="relative mx-auto mb-8 h-24 w-24">
                <div className="cta-pulse-ring absolute inset-0 rounded-full border border-[#7de5c1]/28" />
                <div className="cta-pulse-ring absolute inset-[12px] rounded-full border border-white/18" />
                <div className="relative flex h-24 w-24 items-center justify-center rounded-full border border-white/10 bg-white/6 shadow-[0_18px_46px_rgba(0,0,0,0.2)]">
                  <Zap className="h-8 w-8 text-[#7de5c1]" />
                </div>
              </div>
              <h2 className="cta-line mb-5 text-4xl font-medium tracking-[-0.05em] text-white md:text-5xl">
                Own your AI infrastructure
              </h2>
              <p className="cta-line mx-auto mb-8 max-w-xl text-lg text-white/80 md:text-xl">
                No vendor lock-in. Your LLM keys. Your data. Deploy to Slack, WhatsApp, Teams, and your product — all from one platform you control.
              </p>
              <div className="cta-actions flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="https://app.synkora.ai/signup"
                  className="inline-flex items-center gap-2 rounded-full bg-[#7de5c1] px-8 py-4 font-semibold text-[#101915] transition-transform hover:-translate-y-0.5"
                >
                  <Zap className="w-5 h-5" />
                  Get Started Free
                </Link>
                <a
                  href="https://github.com/getsynkora/synkora-ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-8 py-4 font-semibold text-white transition-colors hover:bg-white/10"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                  </svg>
                  {stars !== null ? formatStars(stars) : 'Star'}
                </a>
              </div>

              <div className="cta-float absolute left-0 top-10 hidden rounded-[1.3rem] border border-white/8 bg-white/6 p-3 shadow-[0_18px_40px_rgba(0,0,0,0.18)] backdrop-blur md:block">
                <div className="mb-2 flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-[#7de5c1]" />
                  <span className="h-px w-12 bg-white/12" />
                </div>
                <div className="space-y-2">
                  <div className="h-2 w-20 rounded-full bg-white/15" />
                  <div className="h-2 w-14 rounded-full bg-[#7de5c1]/35" />
                </div>
              </div>

              <div className="cta-float absolute right-0 bottom-6 hidden rounded-[1.3rem] border border-white/8 bg-white/6 p-3 shadow-[0_18px_40px_rgba(0,0,0,0.18)] backdrop-blur md:block">
                <div className="mb-2 flex items-center justify-between gap-5">
                  <span className="h-7 w-7 rounded-[0.8rem] bg-white/10" />
                  <span className="h-2 w-10 rounded-full bg-[#ff8fb2]/45" />
                </div>
                <div className="space-y-2">
                  <div className="h-2 w-16 rounded-full bg-white/14" />
                  <div className="h-2 w-12 rounded-full bg-[#7de5c1]/28" />
                </div>
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
