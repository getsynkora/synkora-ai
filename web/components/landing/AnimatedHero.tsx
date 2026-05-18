'use client'

import { useEffect, useRef } from 'react'
import Link from 'next/link'
import { Check, Database, Globe2, ShieldCheck, Sparkles, Workflow } from 'lucide-react'
import { formatStars } from '@/lib/utils/formatStars'

const surfaceCards = [
  {
    title: 'Knowledge Base',
    subtitle: 'Ground responses on your own data',
    icon: Database,
    position: 'left-[2%] top-[13%]',
    style: 'w-[250px] rotate-[-10deg]',
    accent: '#79dfbc',
  },
  {
    title: 'Human Approval',
    subtitle: 'Insert guardrails before actions',
    icon: ShieldCheck,
    position: 'right-[2%] top-[7%]',
    style: 'w-[248px] rotate-[9deg]',
    accent: '#ff8fb2',
  },
  {
    title: 'Workflow Engine',
    subtitle: 'Tools, memory, and orchestration',
    icon: Workflow,
    position: 'left-[10%] bottom-[10%]',
    style: 'w-[262px] rotate-[7deg]',
    accent: '#f0c56d',
  },
  {
    title: 'Deploy Anywhere',
    subtitle: 'Slack, WhatsApp, Teams, API',
    icon: Globe2,
    position: 'right-[9%] bottom-[14%]',
    style: 'w-[252px] rotate-[-8deg]',
    accent: '#171717',
  },
]

const signalDots = [
  { id: 'node-1', path: 'hero-path-1', fill: '#79dfbc', radius: 6, startX: 140, startY: 128, duration: 11.5, delay: 0.1 },
  { id: 'node-2', path: 'hero-path-2', fill: '#171717', radius: 5, startX: 708, startY: 132, duration: 12.8, delay: 0.35 },
  { id: 'node-3', path: 'hero-path-3', fill: '#ff8fb2', radius: 5.5, startX: 174, startY: 564, duration: 10.7, delay: 0.2 },
  { id: 'node-4', path: 'hero-path-4', fill: '#f0c56d', radius: 6, startX: 742, startY: 534, duration: 13.2, delay: 0.55 },
  { id: 'node-5', path: 'hero-path-5', fill: '#79dfbc', radius: 4.5, startX: 248, startY: 214, duration: 9.8, delay: 0.45 },
]

export default function AnimatedHero({ stars }: { stars?: number | null }) {
  const heroRef = useRef<HTMLDivElement>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const artRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const artElement = artRef.current
    if (!artElement) return

    const layers = Array.from(artElement.querySelectorAll<HTMLElement>('[data-depth]'))

    let ctx: { revert: () => void } | undefined
    let mouseMoveHandler: ((e: MouseEvent) => void) | undefined
    let mouseLeaveHandler: (() => void) | undefined
    let cancelled = false

    Promise.all([import('gsap'), import('gsap/MotionPathPlugin')]).then(
      ([{ default: gsap }, { MotionPathPlugin }]) => {
        if (cancelled) return
        gsap.registerPlugin(MotionPathPlugin)

        mouseMoveHandler = (event: MouseEvent) => {
          const rect = artElement.getBoundingClientRect()
          const x = (event.clientX - rect.left) / rect.width - 0.5
          const y = (event.clientY - rect.top) / rect.height - 0.5

          layers.forEach((layer) => {
            const depth = Number(layer.dataset.depth || 0)
            gsap.to(layer, {
              x: x * depth,
              y: y * depth,
              duration: 1.15,
              ease: 'power3.out',
            })
          })
        }

        mouseLeaveHandler = () => {
          layers.forEach((layer) => {
            gsap.to(layer, {
              x: 0,
              y: 0,
              duration: 1.25,
              ease: 'power3.out',
            })
          })
        }

        ctx = gsap.context(() => {
      const titleWords = titleRef.current ? Array.from(titleRef.current.querySelectorAll('.word')) : []
      const floatingCards = Array.from(artElement.querySelectorAll<HTMLElement>('.floating-card'))
      const ambientOrbs = Array.from(artElement.querySelectorAll<HTMLElement>('.ambient-orb'))
      const pulseRings = Array.from(artElement.querySelectorAll<HTMLElement>('.pulse-ring'))
      const orbitRings = Array.from(artElement.querySelectorAll<SVGCircleElement>('.orbit-ring'))
      const heroPaths = Array.from(artElement.querySelectorAll<SVGPathElement>('.hero-path'))
      const signalNodes = Array.from(artElement.querySelectorAll<SVGCircleElement>('.signal-node'))
      const heroBeams = Array.from(artElement.querySelectorAll<HTMLElement>('.hero-beam'))
      const stage = artElement.querySelector<HTMLElement>('.hero-stage')
      const heroCore = artElement.querySelector<HTMLElement>('.hero-core')

      if (titleWords.length > 0) {
        gsap.fromTo(
          titleWords,
          { opacity: 0, y: 56, filter: 'blur(10px)' },
          { opacity: 1, y: 0, filter: 'blur(0px)', duration: 1, stagger: 0.08, ease: 'expo.out', delay: 0.18 }
        )
      }

      gsap.fromTo('.hero-badge', { opacity: 0, y: -24 }, { opacity: 1, y: 0, duration: 0.7, ease: 'power2.out' })
      gsap.fromTo('.hero-subtext', { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.7, delay: 0.84, ease: 'power2.out' })
      gsap.fromTo('.hero-cta', { opacity: 0, y: 22 }, { opacity: 1, y: 0, duration: 0.6, delay: 0.98, stagger: 0.08, ease: 'power2.out' })
      gsap.fromTo('.hero-trust', { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.56, delay: 1.1, stagger: 0.06, ease: 'power2.out' })

      if (stage) {
        gsap.fromTo(
          stage,
          { opacity: 0, y: 34, scale: 0.97, filter: 'blur(12px)' },
          { opacity: 1, y: 0, scale: 1, filter: 'blur(0px)', duration: 1.05, delay: 0.45, ease: 'power3.out' }
        )
      }

      if (heroCore) {
        gsap.fromTo(
          heroCore,
          { opacity: 0, scale: 0.86, rotate: -8 },
          { opacity: 1, scale: 1, rotate: 0, duration: 0.95, delay: 0.82, ease: 'back.out(1.45)' }
        )
        gsap.to(heroCore, {
          y: -10,
          duration: 4.6,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
        })
      }

      gsap.fromTo(
        floatingCards,
        { opacity: 0, y: 42, scale: 0.92 },
        { opacity: 1, y: 0, scale: 1, duration: 0.95, stagger: 0.1, delay: 0.68, ease: 'power3.out' }
      )

      floatingCards.forEach((card, index) => {
        gsap.to(card, {
          y: index % 2 === 0 ? -14 : 14,
          x: index % 2 === 0 ? 8 : -8,
          rotate: index % 2 === 0 ? '+=2' : '-=2',
          duration: 5.1 + index * 0.45,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
        })
      })

      ambientOrbs.forEach((orb, index) => {
        gsap.to(orb, {
          x: index % 2 === 0 ? 24 : -20,
          y: index % 2 === 0 ? -18 : 20,
          duration: 6.8 + index,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
        })
      })

      heroBeams.forEach((beam, index) => {
        gsap.fromTo(
          beam,
          { xPercent: index % 2 === 0 ? -10 : 10, opacity: 0.2 },
          { xPercent: index % 2 === 0 ? 10 : -10, opacity: 0.44, duration: 5 + index * 0.6, repeat: -1, yoyo: true, ease: 'sine.inOut' }
        )
      })

      pulseRings.forEach((ring, index) => {
        gsap.fromTo(
          ring,
          { scale: 0.76, opacity: 0.35 },
          {
            scale: 1.15 + index * 0.05,
            opacity: 0,
            duration: 2.8 + index * 0.35,
            delay: index * 0.45,
            repeat: -1,
            ease: 'power1.out',
          }
        )
      })

      orbitRings.forEach((ring, index) => {
        gsap.to(ring, {
          rotate: index % 2 === 0 ? 360 : -360,
          transformOrigin: '50% 50%',
          duration: 26 + index * 8,
          repeat: -1,
          ease: 'none',
        })
      })

      heroPaths.forEach((path, index) => {
        const length = path.getTotalLength()
        gsap.set(path, {
          strokeDasharray: length,
          strokeDashoffset: length,
          opacity: 0.24,
        })

        gsap.to(path, {
          strokeDashoffset: 0,
          opacity: 0.9,
          duration: 1.25,
          delay: 0.74 + index * 0.12,
          ease: 'power2.out',
        })

        gsap.to(path, {
          opacity: index % 2 === 0 ? 0.4 : 0.28,
          duration: 2.3 + index * 0.25,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
          delay: 2 + index * 0.12,
        })
      })

      signalNodes.forEach((node, index) => {
        const pathId = node.dataset.path
        if (!pathId) return

        gsap.set(node, { transformOrigin: '50% 50%' })

        gsap.fromTo(
          node,
          { opacity: 0, scale: 0 },
          { opacity: 1, scale: 1, duration: 0.45, delay: 1.15 + index * 0.08, ease: 'back.out(2)' }
        )

        gsap.to(node, {
          duration: 9.8 + index * 0.9,
          delay: signalDots[index]?.delay || 0,
          repeat: -1,
          ease: 'none',
          motionPath: {
            path: `#${pathId}`,
            align: `#${pathId}`,
            alignOrigin: [0.5, 0.5],
            autoRotate: false,
          },
        })

        gsap.to(node, {
          scale: 1.5,
          opacity: 0.35,
          duration: 1.4 + index * 0.15,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
        })
      })
        }, heroRef)

        artElement.addEventListener('mousemove', mouseMoveHandler)
        artElement.addEventListener('mouseleave', mouseLeaveHandler)
      }
    )

    return () => {
      cancelled = true
      if (mouseMoveHandler) artElement.removeEventListener('mousemove', mouseMoveHandler)
      if (mouseLeaveHandler) artElement.removeEventListener('mouseleave', mouseLeaveHandler)
      ctx?.revert()
    }
  }, [])

  return (
    <div ref={heroRef} className="relative overflow-hidden bg-[#f7f2e7] pt-36">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-[5%] top-[4%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.94),transparent_72%)]" />
        <div className="absolute right-[3%] top-[3%] h-[640px] w-[640px] rounded-full bg-[radial-gradient(circle,rgba(240,232,216,0.92),transparent_72%)]" />
        <div className="absolute left-[16%] top-[22%] h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.14),transparent_72%)]" />
        <div className="absolute bottom-[8%] right-[16%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,143,178,0.1),transparent_74%)]" />
      </div>

      <div className="relative z-10 px-6 pb-20">
        <div className="mx-auto grid max-w-[1480px] gap-14 xl:grid-cols-[1fr_0.98fr] xl:items-center">
          <div className="max-w-4xl">
            <div className="hero-badge mb-8 inline-flex items-center gap-3 rounded-full border border-black/10 bg-white/65 px-4 py-2 shadow-[0_12px_32px_rgba(0,0,0,0.05)] backdrop-blur">
              <div className="flex items-center gap-1.5">
                <svg className="h-4 w-4 text-gray-800" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
                <span className="text-sm font-semibold uppercase tracking-[0.14em] text-[#221f1c]">Open Source</span>
              </div>
              <span className="text-black/20">|</span>
              <span className="text-sm font-medium text-[#5f5a52]">MIT License</span>
              <span className="text-black/20">|</span>
              <a
                href="https://github.com/getsynkora/synkora-ai"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sm font-medium text-[#5f5a52] hover:text-[#3d3933]"
              >
                <svg className="h-4 w-4 fill-current" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
                {stars != null ? formatStars(stars) : 'Star on GitHub'}
              </a>
            </div>

            <h1 ref={titleRef} className="max-w-4xl text-5xl font-medium leading-[0.92] tracking-[-0.05em] text-[#171717] md:text-7xl">
              <span className="word mr-3 inline-block">The</span>
              <span className="word mr-3 inline-block">AI</span>
              <span className="word mr-3 inline-block">agent</span>
              <span className="word mr-3 inline-block">platform</span>
              <br />
              <span className="word mr-3 inline-block">
                <span className="editorial-highlight">your</span>
              </span>
              <span className="word mr-3 inline-block">
                <span className="editorial-highlight">team</span>
              </span>
              <span className="word mr-3 inline-block">actually</span>
              <span className="word inline-block">owns</span>
            </h1>

            <p className="hero-subtext mt-8 max-w-2xl text-xl leading-relaxed text-[#4f4a42]">
              Build agents that connect to your data, deploy to Slack, WhatsApp, Teams, and your product - using your own OpenAI or Anthropic keys. Self-host for free or use Synkora Cloud.
            </p>

            <div className="mt-10 flex flex-col items-start gap-4 sm:flex-row">
              <Link
                href="https://app.synkora.ai/signup"
                className="hero-cta inline-flex w-full items-center justify-center rounded-full bg-[#191919] px-8 py-4 text-lg font-semibold text-[#f7f2e7] transition-transform hover:-translate-y-0.5 sm:w-auto"
              >
                Start Building Free
              </Link>
              <a
                href="#demo"
                className="hero-cta inline-flex w-full items-center justify-center gap-2 rounded-full border border-black/10 bg-white/68 px-8 py-4 text-lg font-semibold text-[#1a1a1a] shadow-[0_12px_32px_rgba(0,0,0,0.04)] transition-colors hover:bg-white sm:w-auto"
              >
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
                Watch Demo
              </a>
            </div>

            <div className="mt-12 flex flex-wrap items-center gap-x-6 gap-y-3">
              {[
                'No vendor lock-in',
                'Bring your own LLM keys',
                'Self-host on your infrastructure',
                'Slack / WhatsApp / Teams / API',
              ].map((item, i) => (
                <div key={i} className="hero-trust flex items-center gap-1.5 text-sm text-[#5b564e]">
                  <Check className="h-3.5 w-3.5 shrink-0 text-[#2d8b69]" />
                  {item}
                </div>
              ))}
            </div>
          </div>

          <div ref={artRef} className="relative hidden min-h-[680px] xl:block">
            <div data-depth="16" className="ambient-orb absolute left-[4%] top-[18%] h-56 w-56 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.88),transparent_72%)]" />
            <div data-depth="24" className="ambient-orb absolute right-[6%] top-[14%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.26),transparent_74%)]" />
            <div data-depth="18" className="ambient-orb absolute bottom-[6%] left-[26%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.72),transparent_76%)]" />

            <div
              data-depth="8"
              className="hero-stage absolute inset-x-[5%] top-[4%] bottom-[6%] overflow-hidden rounded-[3.15rem] border border-black/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.64),rgba(241,232,217,0.5))] shadow-[0_36px_90px_rgba(0,0,0,0.1)] backdrop-blur-xl"
            >
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.92),transparent_30%),radial-gradient(circle_at_82%_16%,rgba(125,229,193,0.18),transparent_24%),radial-gradient(circle_at_24%_78%,rgba(255,143,178,0.12),transparent_20%),linear-gradient(160deg,rgba(255,255,255,0.5),rgba(241,233,220,0.18))]" />
              <div className="absolute inset-[2px] rounded-[3rem] border border-white/50" />
              <div
                className="absolute inset-[6%] rounded-[2.6rem] border border-black/8 bg-[rgba(255,252,247,0.58)]"
                style={{
                  backgroundImage:
                    'linear-gradient(rgba(23,23,23,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(23,23,23,0.045) 1px, transparent 1px)',
                  backgroundSize: '38px 38px',
                }}
              />

              <div data-depth="12" className="hero-beam absolute left-[8%] top-[8%] h-[44%] w-[54%] rotate-[16deg] rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.32),transparent_72%)] blur-3xl" />
              <div data-depth="10" className="hero-beam absolute bottom-[-10%] right-[-4%] h-[48%] w-[46%] -rotate-[10deg] rounded-full bg-[radial-gradient(circle,rgba(255,143,178,0.22),transparent_70%)] blur-3xl" />
              <div data-depth="9" className="hero-beam absolute left-[26%] top-[28%] h-[36%] w-[34%] rounded-full bg-[radial-gradient(circle,rgba(240,197,109,0.18),transparent_70%)] blur-3xl" />

              <div className="absolute inset-[10%] overflow-hidden rounded-[2.25rem] border border-black/8 bg-[linear-gradient(140deg,rgba(255,255,255,0.5),rgba(247,241,232,0.22))]">
                <svg viewBox="0 0 900 700" className="absolute inset-0 h-full w-full">
                  <defs>
                    <linearGradient id="hero-gradient-mint" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#ffffff" stopOpacity="0.72" />
                      <stop offset="48%" stopColor="#79dfbc" stopOpacity="0.96" />
                      <stop offset="100%" stopColor="#171717" stopOpacity="0.4" />
                    </linearGradient>
                    <linearGradient id="hero-gradient-rose" x1="0%" y1="100%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#ffffff" stopOpacity="0.6" />
                      <stop offset="44%" stopColor="#ff8fb2" stopOpacity="0.92" />
                      <stop offset="100%" stopColor="#171717" stopOpacity="0.25" />
                    </linearGradient>
                    <linearGradient id="hero-gradient-amber" x1="0%" y1="50%" x2="100%" y2="50%">
                      <stop offset="0%" stopColor="#ffffff" stopOpacity="0.65" />
                      <stop offset="52%" stopColor="#f0c56d" stopOpacity="0.86" />
                      <stop offset="100%" stopColor="#171717" stopOpacity="0.22" />
                    </linearGradient>
                    <radialGradient id="hero-grid-glow" cx="50%" cy="50%" r="55%">
                      <stop offset="0%" stopColor="#ffffff" stopOpacity="0.82" />
                      <stop offset="42%" stopColor="#79dfbc" stopOpacity="0.18" />
                      <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
                    </radialGradient>
                  </defs>

                  <rect x="0" y="0" width="900" height="700" fill="url(#hero-grid-glow)" opacity="0.72" />

                  <circle className="orbit-ring" cx="450" cy="350" r="220" fill="none" stroke="rgba(23,23,23,0.08)" strokeWidth="1.1" strokeDasharray="8 18" />
                  <circle className="orbit-ring" cx="450" cy="350" r="165" fill="none" stroke="rgba(121,223,188,0.24)" strokeWidth="1.5" strokeDasharray="6 14" />
                  <circle className="orbit-ring" cx="450" cy="350" r="116" fill="none" stroke="rgba(255,143,178,0.18)" strokeWidth="1.2" strokeDasharray="5 12" />

                  <path id="hero-path-1" className="hero-path" d="M140 128 C 248 118 338 180 388 292 S 514 508 662 540" fill="none" stroke="url(#hero-gradient-mint)" strokeWidth="2.8" strokeLinecap="round" />
                  <path id="hero-path-2" className="hero-path" d="M708 132 C 650 214 592 278 534 320 C 498 346 470 356 450 356 C 430 356 402 346 366 320 C 304 274 252 212 186 150" fill="none" stroke="url(#hero-gradient-rose)" strokeWidth="2.4" strokeLinecap="round" />
                  <path id="hero-path-3" className="hero-path" d="M174 564 C 292 528 346 486 392 410 C 420 364 432 340 450 330 C 476 314 520 322 564 344 C 624 374 676 438 732 522" fill="none" stroke="url(#hero-gradient-amber)" strokeWidth="2.6" strokeLinecap="round" />
                  <path id="hero-path-4" className="hero-path" d="M742 534 C 664 468 606 424 556 394 C 510 366 482 348 450 348 C 414 348 382 370 324 410 C 266 450 222 502 174 566" fill="none" stroke="url(#hero-gradient-mint)" strokeWidth="2.2" strokeLinecap="round" />
                  <path id="hero-path-5" className="hero-path" d="M248 214 C 332 246 386 296 418 352 C 438 388 446 420 450 460 C 458 418 470 386 494 350 C 536 286 612 236 694 220" fill="none" stroke="url(#hero-gradient-rose)" strokeWidth="2.1" strokeLinecap="round" />

                  {[
                    [140, 128],
                    [186, 150],
                    [248, 214],
                    [450, 350],
                    [662, 540],
                    [732, 522],
                    [742, 534],
                    [708, 132],
                  ].map(([cx, cy], index) => (
                    <circle key={index} cx={cx} cy={cy} r="4.2" fill="white" opacity="0.86" />
                  ))}

                  {signalDots.map((dot) => (
                    <circle
                      key={dot.id}
                      className="signal-node"
                      data-path={dot.path}
                      cx={dot.startX}
                      cy={dot.startY}
                      r={dot.radius}
                      fill={dot.fill}
                    />
                  ))}
                </svg>

                <div className="hero-core absolute left-1/2 top-1/2 z-10 h-40 w-40 -translate-x-1/2 -translate-y-1/2">
                  <div className="pulse-ring absolute inset-0 rounded-full border border-[#79dfbc]/45 bg-[#79dfbc]/8" />
                  <div className="pulse-ring absolute inset-[10px] rounded-full border border-[#ff8fb2]/35 bg-[#ff8fb2]/5" />
                  <div className="pulse-ring absolute inset-[22px] rounded-full border border-[#f0c56d]/35 bg-[#f0c56d]/6" />

                  <div className="absolute inset-[15px] rounded-full border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(248,243,235,0.72))] shadow-[0_18px_36px_rgba(0,0,0,0.1)]" />
                  <div className="absolute inset-[34px] flex items-center justify-center rounded-full bg-[#171717] shadow-[0_16px_36px_rgba(23,23,23,0.2)]">
                    <Sparkles className="h-10 w-10 text-[#f7f2e7]" />
                  </div>

                  <div className="absolute left-1/2 top-2 h-3 w-3 -translate-x-1/2 rounded-full bg-[#79dfbc]" />
                  <div className="absolute bottom-4 left-4 h-2.5 w-2.5 rounded-full bg-[#ff8fb2]" />
                  <div className="absolute bottom-6 right-5 h-3 w-3 rounded-full bg-[#f0c56d]" />
                </div>
              </div>
            </div>

            {surfaceCards.map((card) => (
              <div
                key={card.title}
                data-depth="18"
                className={`floating-card absolute ${card.position} ${card.style} overflow-hidden rounded-[2rem] border border-black/10 bg-[rgba(255,255,255,0.8)] p-5 shadow-[0_28px_66px_rgba(0,0,0,0.08)] backdrop-blur-xl`}
              >
                <div
                  className="absolute inset-x-5 top-0 h-1 rounded-full"
                  style={{ background: `linear-gradient(90deg, transparent, ${card.accent}, transparent)` }}
                />
                <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.22),rgba(255,255,255,0))]" />
                <div className="relative">
                  <div
                    className="mb-4 flex h-12 w-12 items-center justify-center rounded-[1rem] border border-white/65"
                    style={{
                      background: `linear-gradient(135deg, ${card.accent}35, rgba(255,255,255,0.82))`,
                    }}
                  >
                    <card.icon
                      className="h-5 w-5"
                      style={{ color: card.accent === '#171717' ? '#171717' : '#1e1e1e' }}
                    />
                  </div>
                  <h3 className="text-lg font-semibold tracking-[-0.03em] text-[#171717]">{card.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-[#595349]">{card.subtitle}</p>
                  <div className="mt-5 flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: card.accent }} />
                    <span className="h-px flex-1 bg-black/8" />
                    <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#7a736a]">Live</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
