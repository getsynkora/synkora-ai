'use client'

import { useEffect, useRef } from 'react'
import Link from 'next/link'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Zap } from 'lucide-react'

gsap.registerPlugin(ScrollTrigger)

export default function LandingDemoSection() {
  const sectionRef = useRef<HTMLElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const section = sectionRef.current
    const stage = stageRef.current
    if (!section || !stage) return

    const layers = Array.from(stage.querySelectorAll<HTMLElement>('[data-depth]'))

    const handleMouseMove = (event: MouseEvent) => {
      const rect = stage.getBoundingClientRect()
      const x = (event.clientX - rect.left) / rect.width - 0.5
      const y = (event.clientY - rect.top) / rect.height - 0.5

      layers.forEach((layer) => {
        const depth = Number(layer.dataset.depth || 0)
        gsap.to(layer, {
          x: x * depth,
          y: y * depth,
          duration: 1,
          ease: 'power3.out',
        })
      })
    }

    const handleMouseLeave = () => {
      layers.forEach((layer) => {
        gsap.to(layer, {
          x: 0,
          y: 0,
          duration: 1.1,
          ease: 'power3.out',
        })
      })
    }

    const ctx = gsap.context(() => {
      gsap.fromTo(
        '.demo-badge, .demo-title, .demo-copy, .demo-cta',
        { opacity: 0, y: 28 },
        {
          opacity: 1,
          y: 0,
          duration: 0.8,
          stagger: 0.1,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: section,
            start: 'top 78%',
            once: true,
          },
        }
      )

      gsap.fromTo(
        '.demo-stage-shell',
        { opacity: 0, y: 46, scale: 0.96, filter: 'blur(12px)' },
        {
          opacity: 1,
          y: 0,
          scale: 1,
          filter: 'blur(0px)',
          duration: 1,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: section,
            start: 'top 68%',
            once: true,
          },
        }
      )

      gsap.fromTo(
        '.demo-float',
        { opacity: 0, y: 24, scale: 0.9 },
        {
          opacity: 1,
          y: 0,
          scale: 1,
          duration: 0.75,
          stagger: 0.12,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: section,
            start: 'top 68%',
            once: true,
          },
        }
      )

      gsap.utils.toArray<HTMLElement>('.demo-orb').forEach((orb, index) => {
        gsap.to(orb, {
          x: index % 2 === 0 ? 24 : -22,
          y: index % 2 === 0 ? -18 : 22,
          duration: 6 + index,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
        })
      })

      gsap.utils.toArray<HTMLElement>('.demo-beam').forEach((beam, index) => {
        gsap.fromTo(
          beam,
          { xPercent: index % 2 === 0 ? -12 : 12, opacity: 0.18 },
          { xPercent: index % 2 === 0 ? 12 : -12, opacity: 0.42, duration: 5 + index, repeat: -1, yoyo: true, ease: 'sine.inOut' }
        )
      })

      gsap.utils.toArray<HTMLElement>('.demo-float').forEach((card, index) => {
        gsap.to(card, {
          y: index % 2 === 0 ? -12 : 12,
          rotate: index % 2 === 0 ? '+=1.2' : '-=1.2',
          duration: 4.8 + index,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
        })
      })

      gsap.utils.toArray<HTMLElement>('.demo-grid-line').forEach((line, index) => {
        gsap.fromTo(
          line,
          { scaleX: 0.88, opacity: 0.12 },
          { scaleX: 1.08, opacity: 0.34, duration: 2.6 + index * 0.2, repeat: -1, yoyo: true, ease: 'sine.inOut', transformOrigin: 'left center' }
        )
      })

      gsap.utils.toArray<HTMLElement>('.demo-pulse-ring').forEach((ring, index) => {
        gsap.fromTo(
          ring,
          { scale: 0.86, opacity: 0.38 },
          { scale: 1.16 + index * 0.04, opacity: 0, duration: 2.8 + index * 0.3, repeat: -1, delay: index * 0.28, ease: 'power1.out' }
        )
      })
    }, section)

    stage.addEventListener('mousemove', handleMouseMove)
    stage.addEventListener('mouseleave', handleMouseLeave)

    return () => {
      stage.removeEventListener('mousemove', handleMouseMove)
      stage.removeEventListener('mouseleave', handleMouseLeave)
      ctx.revert()
    }
  }, [])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const tryPlay = async () => {
      try {
        video.muted = true
        await video.play()
      } catch {
        // Ignore autoplay rejections; controls remain available for manual playback.
      }
    }

    void tryPlay()
    video.addEventListener('canplay', tryPlay)

    return () => {
      video.removeEventListener('canplay', tryPlay)
    }
  }, [])

  return (
    <section ref={sectionRef} id="demo" className="relative overflow-hidden px-4 py-20 sm:px-6 sm:py-28">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-0 h-[460px] w-[780px] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.94),rgba(255,255,255,0))]" />
        <div className="absolute left-[12%] top-[16%] h-64 w-64 rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.16),transparent_72%)]" />
        <div className="absolute right-[10%] top-[10%] h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(255,143,178,0.1),transparent_74%)]" />
      </div>

      <div className="relative mx-auto max-w-6xl">
        <div className="mb-12 text-center">
          <div className="demo-badge mb-5 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/60 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#444038] shadow-[0_12px_28px_rgba(0,0,0,0.04)] backdrop-blur">
            <span className="h-2 w-2 rounded-full bg-[#79dfbc]" />
            Product Demo
          </div>
          <h2 className="demo-title mb-4 text-4xl font-medium tracking-[-0.05em] text-[#171717] sm:text-5xl">
            See Synkora in action
          </h2>
          <p className="demo-copy mx-auto max-w-xl text-lg leading-relaxed text-[#565149]">
            Build production-ready AI agents - from the web UI or directly via API
          </p>
        </div>

        <div ref={stageRef} className="relative">
          <div data-depth="12" className="demo-orb absolute -left-8 top-[18%] h-36 w-36 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.95),transparent_72%)]" />
          <div data-depth="18" className="demo-orb absolute -right-4 top-[10%] h-44 w-44 rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.26),transparent_74%)]" />
          <div data-depth="14" className="demo-orb absolute bottom-[4%] left-[18%] h-40 w-40 rounded-full bg-[radial-gradient(circle,rgba(240,197,109,0.16),transparent_72%)]" />

          <div className="demo-stage-shell relative overflow-hidden rounded-[2.6rem] border border-black/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.76),rgba(242,234,221,0.64))] shadow-[0_34px_90px_rgba(0,0,0,0.1)] backdrop-blur-xl">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.92),transparent_26%),radial-gradient(circle_at_86%_20%,rgba(125,229,193,0.16),transparent_24%),radial-gradient(circle_at_18%_78%,rgba(255,143,178,0.1),transparent_22%)]" />
            <div className="absolute inset-[10px] rounded-[2.25rem] border border-white/60" />
            <div data-depth="10" className="demo-beam absolute -left-[8%] top-[18%] h-44 w-[42%] rotate-[15deg] rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.26),transparent_72%)] blur-3xl" />
            <div data-depth="9" className="demo-beam absolute right-[-6%] top-[40%] h-48 w-[34%] -rotate-[12deg] rounded-full bg-[radial-gradient(circle,rgba(255,143,178,0.18),transparent_72%)] blur-3xl" />

            <div className="absolute inset-x-[8%] top-[12%] h-[1px] bg-gradient-to-r from-transparent via-black/10 to-transparent demo-grid-line" />
            <div className="absolute inset-x-[14%] top-[22%] h-[1px] bg-gradient-to-r from-transparent via-[#79dfbc]/30 to-transparent demo-grid-line" />
            <div className="absolute inset-x-[10%] bottom-[20%] h-[1px] bg-gradient-to-r from-transparent via-black/10 to-transparent demo-grid-line" />

            <div className="flex items-center gap-2 border-b border-black/10 bg-[#eee7da]/90 px-4 py-3">
              <div className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-full bg-[#ff5f57]" />
                <div className="h-3 w-3 rounded-full bg-[#febc2e]" />
                <div className="h-3 w-3 rounded-full bg-[#28c840]" />
              </div>
              <div className="mx-4 flex-1">
                <div className="mx-auto flex max-w-xs items-center gap-2 rounded-md border border-black/10 bg-white/85 px-3 py-1 shadow-[0_10px_24px_rgba(0,0,0,0.04)]">
                  <svg className="h-3 w-3 shrink-0 text-[#7a736a]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                  <span className="truncate font-mono text-xs text-[#7a736a]">app.synkora.ai</span>
                </div>
              </div>
            </div>

            <div className="relative aspect-video bg-[#e9e1d3]">
              <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(0,0,0,0.05))]" />
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.34),transparent_42%)]" />
              <div className="pointer-events-none absolute left-1/2 top-6 h-20 w-20 -translate-x-1/2">
                <div className="demo-pulse-ring absolute inset-0 rounded-full border border-white/40" />
                <div className="demo-pulse-ring absolute inset-[10px] rounded-full border border-[#79dfbc]/28" />
              </div>
              <video
                ref={videoRef}
                src="/demo_video.mp4"
                poster="https://github.com/user-attachments/assets/4e0b11be-b9d8-4cde-9524-c8ec9467059f"
                autoPlay
                controls
                loop
                muted
                playsInline
                preload="metadata"
                className="h-full w-full object-cover"
              />
            </div>
          </div>

          <div data-depth="16" className="demo-float absolute -left-6 top-[16%] hidden rounded-[1.6rem] border border-black/10 bg-white/72 p-4 shadow-[0_22px_52px_rgba(0,0,0,0.08)] backdrop-blur-xl lg:block">
            <div className="mb-3 flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-[#79dfbc]" />
              <span className="h-px w-16 bg-black/10" />
            </div>
            <div className="space-y-2">
              <div className="h-2 w-24 rounded-full bg-black/10" />
              <div className="h-2 w-16 rounded-full bg-[#79dfbc]/45" />
              <div className="h-2 w-20 rounded-full bg-black/8" />
            </div>
          </div>

          <div data-depth="14" className="demo-float absolute -right-6 bottom-[14%] hidden rounded-[1.6rem] border border-black/10 bg-white/72 p-4 shadow-[0_22px_52px_rgba(0,0,0,0.08)] backdrop-blur-xl lg:block">
            <div className="mb-3 flex items-center justify-between gap-6">
              <span className="h-8 w-8 rounded-[0.9rem] bg-[#171717]" />
              <span className="h-2 w-12 rounded-full bg-[#ff8fb2]/55" />
            </div>
            <div className="space-y-2">
              <div className="h-2 w-24 rounded-full bg-black/10" />
              <div className="h-2 w-20 rounded-full bg-black/8" />
              <div className="h-2 w-14 rounded-full bg-[#f0c56d]/55" />
            </div>
          </div>
        </div>

        <div className="mt-10 text-center">
          <Link
            href="https://app.synkora.ai/signup"
            className="demo-cta inline-flex items-center gap-2 rounded-full bg-[#191919] px-7 py-3 text-sm font-semibold uppercase tracking-[0.16em] text-[#f7f2e7] shadow-[0_18px_40px_rgba(23,23,23,0.18)] transition-transform hover:-translate-y-0.5"
          >
            <Zap className="h-4 w-4" />
            Start Building Free
          </Link>
        </div>
      </div>
    </section>
  )
}
