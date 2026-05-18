'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ExampleConversation } from '@/components/landing/ExampleConversation'
import { PricingCTA } from '@/components/landing/PricingCTA'

interface LandingData {
  slug: string
  agent_name: string
  agent_avatar?: string
  allow_subscriptions?: boolean
  tagline?: string
  long_description?: string
  hero_image_url?: string
  preview_video_url?: string
  gallery_images?: { url: string; caption?: string; order: number }[]
  example_conversations?: { title: string; messages: { role: string; content: string }[] }[]
  cta_label?: string
  pricing?: {
    id: string
    pricing_model: string
    session_credits?: number
    daily_credits?: number
    weekly_credits?: number
    monthly_credits?: number
    trial_messages?: number
  } | null
  creator?: {
    username?: string
    display_name?: string
    bio?: string
    avatar_url?: string
    website_url?: string
    twitter_url?: string
    linkedin_url?: string
    github_url?: string
  } | null
  creator_bio?: string
  creator_display_name?: string
  accent_color?: string
}

function toEmbedUrl(url: string): string {
  if (!url) return url
  try {
    const u = new URL(url)
    if (u.hostname === 'youtu.be') return `https://www.youtube.com/embed/${u.pathname.slice(1)}`
    if ((u.hostname === 'www.youtube.com' || u.hostname === 'youtube.com') && u.searchParams.get('v'))
      return `https://www.youtube.com/embed/${u.searchParams.get('v')}`
    if ((u.hostname === 'www.youtube.com' || u.hostname === 'youtube.com') && u.pathname.startsWith('/shorts/'))
      return `https://www.youtube.com/embed/${u.pathname.split('/shorts/')[1].split('/')[0]}`
    return url
  } catch { return url }
}

export function AnimatedLanding({ data, slug }: { data: LandingData; slug: string }) {
  const rootRef = useRef<HTMLDivElement>(null)
  const navRef = useRef<HTMLElement>(null)
  const badgeRef = useRef<HTMLDivElement>(null)
  const headlineRef = useRef<HTMLHeadingElement>(null)
  const taglineRef = useRef<HTMLParagraphElement>(null)
  const subRef = useRef<HTMLParagraphElement>(null)
  const ctaRef = useRef<HTMLDivElement>(null)
  const heroImgRef = useRef<HTMLDivElement>(null)

  const [emailInput, setEmailInput] = useState('')
  const [emailLoading, setEmailLoading] = useState(false)
  const [emailDone, setEmailDone] = useState(false)
  const [emailError, setEmailError] = useState<string | null>(null)

  const {
    agent_name, agent_avatar, tagline, long_description, hero_image_url, preview_video_url,
    gallery_images, example_conversations, cta_label, pricing, creator,
    creator_bio, creator_display_name, accent_color, allow_subscriptions,
  } = data

  // Smooth scroll to section
  const scrollTo = (id: string) => {
    const el = document.getElementById(id)
    if (!el) return
    const top = el.getBoundingClientRect().top + window.scrollY - 72
    window.scrollTo({ top, behavior: 'smooth' })
  }

  const handleEmailSubscribe = async () => {
    if (!emailInput.trim()) return
    setEmailLoading(true)
    setEmailError(null)
    try {
      const res = await fetch(`/api/public/agents/${slug}/email-subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailInput }),
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d?.detail || 'Subscription failed')
      }
      setEmailDone(true)
    } catch (e: any) {
      setEmailError(e.message)
    } finally {
      setEmailLoading(false)
    }
  }

  const brandAccent = '#79dfbc'
  const brandBg = '#f7f2e7'
  const brandPanel = '#f4eee1'
  const brandSurface = '#fffaf1'
  const brandInk = '#171717'
  const brandMuted = '#6d675f'
  const accent = accent_color || brandAccent
  const pricingTiers = pricing ? [
    pricing.session_credits && { label: 'Session', credits: pricing.session_credits, tier: 'SESSION', desc: 'Single conversation' },
    pricing.daily_credits && { label: 'Daily', credits: pricing.daily_credits, tier: 'DAILY', desc: '24-hour access' },
    pricing.weekly_credits && { label: 'Weekly', credits: pricing.weekly_credits, tier: 'WEEKLY', desc: '7-day access' },
    pricing.monthly_credits && { label: 'Monthly', credits: pricing.monthly_credits, tier: 'MONTHLY', desc: '30-day access', popular: true },
  ].filter(Boolean) : []

  const isFree = !pricing || pricing.pricing_model === 'FREE'
  // Filter out gallery items with no URL and examples with no message content
  const validGallery = (gallery_images || []).filter(img => img.url?.trim())
  const validExamples = (example_conversations || [])
    .map(conv => ({ ...conv, messages: conv.messages.filter(m => m.content?.trim()) }))
    .filter(conv => conv.messages.length > 0)
  const hasGallery = validGallery.length > 0
  const hasExamples = validExamples.length > 0
  const hasCreator = creator || creator_bio || creator_display_name
  const displayName = creator?.display_name || creator_display_name
  const displayBio = creator?.bio || creator_bio

  useEffect(() => {
    let ctx: { revert: () => void } | undefined
    let rafId: number
    let timerId: ReturnType<typeof setTimeout>
    let loadHandler: (() => void) | undefined
    let cancelled = false

    Promise.all([import('gsap'), import('gsap/ScrollTrigger')]).then(
      ([{ default: gsap }, { ScrollTrigger }]) => {
        if (cancelled) return
        gsap.registerPlugin(ScrollTrigger)

        loadHandler = () => ScrollTrigger.refresh()
        ctx = gsap.context(() => {
      // ── Hero entrance sequence ──
      const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })

      tl.from(badgeRef.current, { y: -30, opacity: 0, duration: 0.6 })
        .from('.hero-word', { y: 80, opacity: 0, duration: 0.7, stagger: 0.08 }, '-=0.2')
        .from(taglineRef.current, { y: 30, opacity: 0, duration: 0.6 }, '-=0.3')
        .from(subRef.current, { y: 20, opacity: 0, duration: 0.5 }, '-=0.4')
        .from('.hero-cta-btn', { scale: 0.85, opacity: 0, duration: 0.5, stagger: 0.1, ease: 'back.out(1.7)' }, '-=0.3')
        .from(heroImgRef.current, { y: 60, opacity: 0, duration: 0.9, ease: 'power2.out' }, '-=0.5')

      // ── Nav links stagger entrance ──
      gsap.from('.nav-link', { y: -10, opacity: 0, duration: 0.4, stagger: 0.08, ease: 'power2.out', delay: 0.8 })

      // ── Nav shadow on scroll ──
      ScrollTrigger.create({
        start: 'top -60',
        onEnter: () => gsap.to(navRef.current, { boxShadow: '0 1px 20px rgba(0,0,0,0.08)', duration: 0.3 }),
        onLeaveBack: () => gsap.to(navRef.current, { boxShadow: 'none', duration: 0.3 }),
      })

      // ── Section reveals ──
      gsap.utils.toArray<HTMLElement>('.reveal-section').forEach(el => {
        gsap.fromTo(el,
          { y: 50, opacity: 0 },
          {
            y: 0, opacity: 1, duration: 0.8, ease: 'power3.out',
            scrollTrigger: {
              trigger: el,
              start: 'top bottom',   // fires as soon as any part enters viewport
              toggleActions: 'play none none none',
              invalidateOnRefresh: true,
            },
          }
        )
      })

      // ── Section header badge + title stagger ──
      gsap.utils.toArray<HTMLElement>('.section-header').forEach(el => {
        const children = el.querySelectorAll('.section-badge, .section-title, .section-sub')
        gsap.fromTo(children,
          { y: 30, opacity: 0 },
          {
            y: 0, opacity: 1, duration: 0.6, stagger: 0.15, ease: 'power3.out',
            scrollTrigger: { trigger: el, start: 'top bottom', toggleActions: 'play none none none', invalidateOnRefresh: true },
          }
        )
      })

      // ── Staggered card reveals ──
      gsap.utils.toArray<HTMLElement>('.stagger-cards').forEach(container => {
        const cards = container.querySelectorAll('.stagger-card')
        gsap.fromTo(cards,
          { y: 60, opacity: 0, scale: 0.95 },
          {
            y: 0, opacity: 1, scale: 1, duration: 0.6, stagger: 0.1, ease: 'back.out(1.4)',
            scrollTrigger: { trigger: container, start: 'top bottom', toggleActions: 'play none none none', invalidateOnRefresh: true },
          }
        )
      })

      // ── Gallery clip-path reveal ──
      gsap.utils.toArray<HTMLElement>('.gallery-img').forEach((el, i) => {
        gsap.from(el, {
          clipPath: 'inset(0 100% 0 0)',
          opacity: 0,
          duration: 0.7,
          ease: 'power3.out',
          delay: i * 0.07,
          scrollTrigger: { trigger: el, start: 'top 88%', toggleActions: 'play none none none' },
        })
      })

      // ── Example conversations slide in alternating ──
      gsap.utils.toArray<HTMLElement>('.example-conv').forEach((el, i) => {
        gsap.from(el, {
          x: i % 2 === 0 ? -60 : 60,
          opacity: 0,
          duration: 0.7,
          ease: 'power3.out',
          scrollTrigger: { trigger: el, start: 'top 85%', toggleActions: 'play none none none' },
        })
      })

      // ── Pricing highlight pulse ──
      gsap.to('.pricing-popular', {
        boxShadow: `0 20px 60px ${accent}35`,
        repeat: -1,
        yoyo: true,
        duration: 2,
        ease: 'sine.inOut',
      })

      // ── Creator card slide from right ──
      const creatorCard = document.querySelector('.creator-card')
      if (creatorCard) {
        gsap.from(creatorCard, {
          x: 80, opacity: 0, duration: 0.8, ease: 'power3.out',
          scrollTrigger: { trigger: creatorCard, start: 'top 80%', toggleActions: 'play none none none' },
        })
      }

      // ── Final CTA text burst ──
      const ctaSection = document.querySelector('.final-cta-section')
      if (ctaSection) {
        gsap.from(ctaSection.querySelectorAll('.cta-line'), {
          y: 40, opacity: 0, duration: 0.7, stagger: 0.15, ease: 'power3.out',
          scrollTrigger: { trigger: ctaSection, start: 'top 75%', toggleActions: 'play none none none' },
        })
      }

      // ── Parallax on hero background ──
      gsap.to('.hero-bg-glow', {
        y: -120,
        ease: 'none',
        scrollTrigger: { trigger: '.hero-section', start: 'top top', end: 'bottom top', scrub: true },
      })

      // ── Floating badge on hero ──
      gsap.to(badgeRef.current, {
        y: -8, duration: 2.5, repeat: -1, yoyo: true, ease: 'sine.inOut',
      })

        }, rootRef)

        // Recalculate scroll trigger positions after layout settles.
        if (document.readyState === 'complete') {
          rafId = requestAnimationFrame(() => ScrollTrigger.refresh())
          timerId = setTimeout(() => ScrollTrigger.refresh(), 300)
        } else {
          window.addEventListener('load', loadHandler)
        }
      }
    )

    return () => {
      cancelled = true
      ctx?.revert()
      if (loadHandler) window.removeEventListener('load', loadHandler)
      cancelAnimationFrame(rafId)
      clearTimeout(timerId)
    }
  }, [accent])

  return (
    <div
      ref={rootRef}
      className="min-h-screen overflow-x-hidden text-[#191919]"
      style={{ background: brandBg, fontFamily: '"Avenir Next", "Helvetica Neue", "Segoe UI", sans-serif' }}
    >

      {/* ── Navigation ── */}
      <header
        ref={navRef}
        className="sticky top-0 z-50 border-b border-black/10 bg-[#f7f2e7]/95 backdrop-blur-sm transition-shadow"
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between gap-6">
          <Link href="/" className="flex items-center gap-2.5 flex-shrink-0 hover:opacity-80 transition-opacity">
            {agent_avatar ? (
              <img src={agent_avatar} alt={agent_name} className="w-8 h-8 rounded-xl object-cover ring-1 ring-black/10" loading="lazy" />
            ) : (
              <div
                className="w-8 h-8 rounded-xl flex items-center justify-center text-[#11231d] font-bold text-sm select-none"
                style={{ background: brandAccent }}
              >
                {(agent_name || 'A')[0].toUpperCase()}
              </div>
            )}
            <span className="font-semibold text-[#171717] text-sm tracking-[-0.02em]">{agent_name}</span>
          </Link>

          <nav className="hidden md:flex items-center gap-7 text-sm text-[#6d675f]">
            {long_description && (
              <button onClick={() => scrollTo('about')} className="nav-link hover:text-[#171717] transition-colors cursor-pointer">About</button>
            )}
            {hasExamples && (
              <button onClick={() => scrollTo('examples')} className="nav-link hover:text-[#171717] transition-colors cursor-pointer">Examples</button>
            )}
            {hasGallery && (
              <button onClick={() => scrollTo('gallery')} className="nav-link hover:text-[#171717] transition-colors cursor-pointer">Gallery</button>
            )}
            <button onClick={() => scrollTo('pricing')} className="nav-link hover:text-[#171717] transition-colors cursor-pointer">Pricing</button>
            {allow_subscriptions && (
              <button onClick={() => scrollTo('subscribe')} className="nav-link hover:text-[#171717] transition-colors cursor-pointer">Subscribe</button>
            )}
            {hasCreator && (
              <button onClick={() => scrollTo('creator')} className="nav-link hover:text-[#171717] transition-colors cursor-pointer">Creator</button>
            )}
          </nav>

          <div className="flex items-center gap-3 flex-shrink-0">
            <Link href="/signin" className="hidden sm:block text-sm text-[#6d675f] hover:text-[#171717] transition-colors font-medium">
              Log In
            </Link>
            <button
              onClick={() => scrollTo('pricing')}
              className="rounded-full bg-[#191919] px-4 py-2 text-sm font-semibold text-[#f7f2e7] transition-all hover:-translate-y-0.5 hover:bg-black cursor-pointer"
            >
              Get Started
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="hero-section relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(121,223,188,0.22),transparent_34%),radial-gradient(circle_at_top_right,rgba(240,197,109,0.16),transparent_28%)] pointer-events-none" />
        <div
          className="hero-bg-glow absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] pointer-events-none"
          style={{ background: `radial-gradient(ellipse at center, ${brandAccent}20 0%, transparent 65%)` }}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(circle, rgba(30,22,14,0.1) 1.1px, transparent 1.1px)',
            backgroundSize: '28px 28px',
            WebkitMaskImage: 'radial-gradient(ellipse 100% 100% at 50% 0%, black 50%, transparent 100%)',
            maskImage: 'radial-gradient(ellipse 100% 100% at 50% 0%, black 50%, transparent 100%)',
          }}
        />

        <div className="relative max-w-5xl mx-auto px-6 pt-20 pb-12 text-center">
          {/* Badge */}
          <div
            ref={badgeRef}
            className="mb-8 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur cursor-default"
          >
            <span className="rounded-full px-2 py-0.5 text-xs font-bold text-[#11231d]" style={{ background: brandAccent }}>AI</span>
            <span className="text-sm text-[#6d675f]">Intelligent Agent — Ready to use</span>
          </div>

          {/* Split-word headline */}
          <h1 ref={headlineRef} className="mb-4 overflow-hidden text-5xl font-semibold leading-[1.04] tracking-[-0.06em] text-[#171717] md:text-7xl">
            {agent_name.split(' ').map((word, i) => (
              <span key={i} className="inline-block overflow-hidden mr-[0.25em] last:mr-0">
                <span className="hero-word inline-block">{word}</span>
              </span>
            ))}
          </h1>

          {tagline && (
            <p ref={taglineRef} className="mb-4 text-2xl font-medium tracking-[-0.04em] md:text-3xl" style={{ color: brandInk }}>
              {tagline}
            </p>
          )}

          {long_description && (
            <p ref={subRef} className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-[#565149] md:text-xl">
              {long_description.split('\n')[0].slice(0, 180)}
            </p>
          )}

          <div ref={ctaRef} className="flex items-center justify-center gap-4 flex-wrap">
            <button
              onClick={() => scrollTo('pricing')}
              className="hero-cta-btn rounded-full bg-[#191919] px-8 py-3.5 text-base font-semibold text-[#f7f2e7] shadow-[0_18px_40px_rgba(0,0,0,0.12)] transition-all hover:-translate-y-0.5 hover:bg-black cursor-pointer"
            >
              {cta_label || 'Try it for Free'}
            </button>
            {long_description && (
              <button
                onClick={() => scrollTo('about')}
                className="hero-cta-btn rounded-full border border-black/10 bg-white/70 px-8 py-3.5 text-base font-semibold text-[#171717] transition-all hover:-translate-y-0.5 hover:bg-white cursor-pointer"
              >
                Learn more
              </button>
            )}
          </div>

          {pricing?.trial_messages && pricing.trial_messages > 0 ? (
            <p className="mt-4 text-sm text-[#7a7267]">
              First {pricing.trial_messages} messages free — no credit card required
            </p>
          ) : null}
        </div>

        {/* Hero product screenshot */}
        {hero_image_url && (
          <div ref={heroImgRef} className="max-w-5xl mx-auto px-6 pb-0">
            <div className="overflow-hidden rounded-t-[2rem] border border-black/10 bg-white/75 shadow-[0_28px_70px_rgba(0,0,0,0.08)] backdrop-blur">
              <div className="flex items-center gap-2 border-b border-black/10 bg-[#f4eee1] px-4 py-3">
                <div className="flex gap-1.5">
                  <div className="h-3 w-3 rounded-full bg-[#ff5f57]" />
                  <div className="h-3 w-3 rounded-full bg-[#febc2e]" />
                  <div className="h-3 w-3 rounded-full bg-[#28c840]" />
                </div>
                <div className="flex-1 mx-4">
                  <div className="mx-auto max-w-xs rounded-full border border-black/10 bg-white px-3 py-1 text-center text-xs text-[#746c61]">
                    {agent_name}
                  </div>
                </div>
              </div>
              <img src={hero_image_url} alt={agent_name} className="w-full object-cover" loading="lazy" />
            </div>
          </div>
        )}
      </section>

      {/* ── About ── */}
      {long_description && (
        <section id="about" className="reveal-section px-6 py-24" style={{ background: brandPanel }}>
          <div className="max-w-4xl mx-auto">
            <div className="section-header text-center mb-12">
              <span className="section-badge mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
                About
              </span>
              <h2 className="section-title text-3xl font-medium tracking-[-0.05em] text-[#171717] md:text-4xl">What this agent does</h2>
            </div>
            <div className="rounded-[2rem] border border-black/10 bg-white/70 p-8 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur md:p-10">
              <p className="whitespace-pre-wrap text-lg leading-relaxed text-[#565149]">{long_description}</p>
            </div>
          </div>
        </section>
      )}

      {/* ── Gallery ── */}
      {hasGallery && (
        <section id="gallery" className="reveal-section px-6 py-20">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-12">
              <span className="mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
                Gallery
              </span>
              <h2 className="text-3xl font-medium tracking-[-0.05em] text-[#171717] md:text-4xl">Screenshots & Media</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
              {validGallery.map((img, i) => (
                <div key={i} className="gallery-img group relative aspect-video overflow-hidden rounded-[1.7rem] border border-black/10 bg-white/70 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-shadow hover:shadow-[0_24px_60px_rgba(0,0,0,0.1)] cursor-pointer">
                  <img src={img.url} alt={img.caption || ''} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" loading="lazy" />
                  {img.caption && (
                    <div className="absolute bottom-0 left-0 right-0 translate-y-full bg-gradient-to-t from-black/65 to-transparent px-3 py-2 text-xs font-medium text-white transition-transform duration-300 group-hover:translate-y-0">
                      {img.caption}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Video ── */}
      {preview_video_url && (
        <section className="reveal-section px-6 py-20" style={{ background: brandPanel }}>
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-12">
              <span className="mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
                Demo
              </span>
              <h2 className="text-3xl font-medium tracking-[-0.05em] text-[#171717] md:text-4xl">See it in action</h2>
            </div>
            <div className="aspect-video overflow-hidden rounded-[2rem] border border-black/10 bg-white/75 shadow-[0_22px_60px_rgba(0,0,0,0.08)]">
              <iframe
                src={toEmbedUrl(preview_video_url)}
                className="w-full h-full"
                allowFullScreen
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              />
            </div>
          </div>
        </section>
      )}

      {/* ── Example Conversations ── */}
      {hasExamples && (
        <section id="examples" className="reveal-section px-6 py-20">
          <div className="max-w-3xl mx-auto">
            <div className="text-center mb-12">
              <span className="mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
                Examples
              </span>
              <h2 className="mb-3 text-3xl font-medium tracking-[-0.05em] text-[#171717] md:text-4xl">Real conversations</h2>
              <p className="text-lg text-[#565149]">See exactly what you can expect</p>
            </div>
            <div className="space-y-5">
              {validExamples.map((conv, i) => (
                <div key={i} className="example-conv">
                  <ExampleConversation title={conv.title} messages={conv.messages as any} theme="light" accentColor={accent} />
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Pricing ── */}
      <section id="pricing" className="reveal-section px-6 py-24" style={{ background: brandPanel }}>
        <div className="max-w-5xl mx-auto">
          <div className="section-header text-center mb-16">
            <span className="section-badge mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
              Pricing
            </span>
            <h2 className="section-title mb-4 text-3xl font-medium tracking-[-0.05em] text-[#171717] md:text-4xl">Simple, transparent pricing</h2>
            <p className="section-sub text-lg text-[#565149]">Pay only for what you use. No hidden fees.</p>
          </div>

          {!isFree && pricingTiers.length > 0 ? (
            <>
              <div className={`stagger-cards grid gap-6 mb-10 ${
                pricingTiers.length === 1 ? 'max-w-xs mx-auto' :
                pricingTiers.length === 2 ? 'grid-cols-2 max-w-lg mx-auto' :
                pricingTiers.length === 3 ? 'grid-cols-3 max-w-2xl mx-auto' :
                'grid-cols-2 lg:grid-cols-4'
              }`}>
                {pricingTiers.map((t: any) => (
                  <div
                    key={t.tier}
                    className={`stagger-card relative rounded-2xl p-7 border-2 transition-all hover:-translate-y-2 hover:shadow-xl cursor-default ${
                      t.popular ? 'pricing-popular bg-white' : 'border-black/10 bg-white/70 shadow-[0_18px_40px_rgba(0,0,0,0.05)]'
                    }`}
                    style={t.popular ? { borderColor: brandAccent, background: brandSurface } : {}}
                  >
                    {t.popular && (
                      <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-[#171717] px-4 py-1 text-xs font-bold text-[#f7f2e7]" >
                        Most Popular
                      </div>
                    )}
                    <div className="mb-4 text-xs font-bold uppercase tracking-[0.18em] text-[#7a7267]">{t.label}</div>
                    <div className="flex items-baseline gap-1 mb-1">
                      <span className="text-4xl font-semibold tracking-[-0.05em] text-[#171717]">{t.credits}</span>
                      <span className="text-sm font-medium text-[#7a7267]">credits</span>
                    </div>
                    <p className="mt-3 text-sm text-[#565149]">{t.desc}</p>
                    <div className="mt-6">
                      <a
                        href={`/agents/${slug}/chat`}
                        className="block w-full py-2.5 text-center text-sm font-semibold rounded-xl transition-all hover:opacity-90"
                        style={t.popular ? { background: '#171717', color: '#f7f2e7' } : { background: '#f4eee1', color: '#171717' }}
                      >
                        Get started
                      </a>
                    </div>
                  </div>
                ))}
              </div>
              <PricingCTA
                agentSlug={slug}
                agentName={agent_name}
                pricingId={pricing!.id}
                tiers={pricingTiers as any}
                trialMessages={pricing?.trial_messages || 0}
                accentColor={accent}
                isFree={false}
              />
            </>
          ) : (
            <div className="text-center">
              <div className="inline-block rounded-[2rem] border border-black/10 bg-white/75 px-12 py-10 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-shadow hover:shadow-[0_24px_60px_rgba(0,0,0,0.08)]">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full" style={{ background: `${brandAccent}22` }}>
                  <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke={brandInk} strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="mb-2 text-3xl font-semibold tracking-[-0.05em] text-[#171717]">Free</div>
                <div className="mb-6 text-[#565149]">No cost to use this agent</div>
                <PricingCTA agentSlug={slug} agentName={agent_name} pricingId="" tiers={[]} trialMessages={0} accentColor={accent} isFree={true} />
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ── Creator ── */}
      {hasCreator && (
        <section id="creator" className="reveal-section px-6 py-20">
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-10">
              <span className="mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
                Creator
              </span>
              <h2 className="text-3xl font-medium tracking-[-0.05em] text-[#171717]">Meet the creator</h2>
            </div>
            <div className="creator-card flex flex-col items-center gap-6 rounded-[2rem] border border-black/10 bg-white/75 p-8 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-shadow hover:shadow-[0_24px_60px_rgba(0,0,0,0.08)] sm:flex-row sm:items-start">
              {creator?.avatar_url ? (
                <img src={creator.avatar_url} alt={displayName || ''} className="h-20 w-20 flex-shrink-0 rounded-full border border-black/10 object-cover" loading="lazy" />
              ) : (
                <div className="flex h-20 w-20 flex-shrink-0 items-center justify-center rounded-full text-2xl font-bold text-[#11231d]" style={{ background: brandAccent }}>
                  {(displayName || 'C')[0].toUpperCase()}
                </div>
              )}
              <div className="flex-1 text-center sm:text-left">
                <div className="mb-2 text-xl font-semibold tracking-[-0.03em] text-[#171717]">{displayName || 'Creator'}</div>
                {displayBio && <p className="mb-4 text-sm leading-relaxed text-[#565149]">{displayBio}</p>}
                <div className="flex items-center justify-center sm:justify-start gap-4 flex-wrap">
                  {creator?.website_url && <a href={creator.website_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-[#171717] hover:underline">Website ↗</a>}
                  {creator?.twitter_url && <a href={creator.twitter_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-[#171717] hover:underline">Twitter ↗</a>}
                  {creator?.github_url && <a href={creator.github_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-[#171717] hover:underline">GitHub ↗</a>}
                  {creator?.linkedin_url && <a href={creator.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-[#171717] hover:underline">LinkedIn ↗</a>}
                  {creator?.username && <Link href={`/creators/${creator.username}`} className="text-sm font-medium text-[#171717] hover:underline">View all agents ↗</Link>}
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── Free Email Subscription ── */}
      {allow_subscriptions && (
        <section id="subscribe" className="reveal-section px-6 py-20" style={{ background: brandPanel }}>
          <div className="max-w-xl mx-auto text-center">
            <div className="section-header mb-8">
              <span className="section-badge mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
                Free Updates
              </span>
              <h2 className="section-title mb-3 text-3xl font-medium tracking-[-0.05em] text-[#171717] md:text-4xl">
                Stay in the loop
              </h2>
              <p className="section-sub text-lg text-[#565149]">
                Subscribe to receive agent outputs and updates by email — completely free.
              </p>
            </div>

            {emailDone ? (
              <div className="flex items-center justify-center gap-3 rounded-[1.6rem] border border-black/10 bg-white/80 px-6 py-4 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
                <span className="text-2xl">✓</span>
                <p className="font-semibold text-[#171717]">You're subscribed! Check your inbox.</p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex gap-2">
                  <input
                    type="email"
                    value={emailInput}
                    onChange={e => setEmailInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleEmailSubscribe()}
                    placeholder="your@email.com"
                    className="flex-1 rounded-[1.2rem] border border-black/10 bg-white/90 px-4 py-3.5 text-sm text-[#171717] shadow-sm focus:border-transparent focus:outline-none focus:ring-2"
                    style={{ '--tw-ring-color': brandAccent } as React.CSSProperties}
                  />
                  <button
                    onClick={handleEmailSubscribe}
                    disabled={emailLoading || !emailInput.trim()}
                    className="rounded-[1.2rem] bg-[#171717] px-6 py-3.5 text-sm font-semibold text-[#f7f2e7] shadow-sm transition-all hover:bg-black disabled:opacity-50"
                  >
                    {emailLoading ? '...' : 'Subscribe Free'}
                  </button>
                </div>
                {emailError && <p className="text-red-500 text-sm">{emailError}</p>}
                <p className="text-xs text-[#7a7267]">No spam. Unsubscribe anytime.</p>
              </div>
            )}
          </div>
        </section>
      )}

      {/* ── Final CTA ── */}
      <section
        className="final-cta-section px-6 py-24 text-center text-white"
        style={{ background: 'linear-gradient(135deg, #171717 0%, #23221f 60%, #2d8b69 140%)' }}
      >
        <div className="max-w-2xl mx-auto">
          <h2 className="cta-line mb-4 text-3xl font-medium tracking-[-0.05em] md:text-5xl">Ready to get started?</h2>
          <p className="cta-line mb-10 text-lg text-white/70">{tagline || `Start using ${agent_name} today.`}</p>
          <div className="cta-line flex items-center justify-center gap-4 flex-wrap">
            <a
              href="#pricing"
              className="rounded-full bg-[#f7f2e7] px-8 py-4 text-base font-semibold text-[#171717] transition-all hover:-translate-y-0.5 hover:bg-white"
            >
              {cta_label || 'Try it for Free'}
            </a>
            <Link href="/signup" className="rounded-full border border-white/20 bg-white/10 px-8 py-4 text-base font-semibold text-white transition-colors hover:bg-white/16">
              Create account
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-white/8 bg-[#171717] px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-sm text-[#a79f92] sm:flex-row">
          <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            {agent_avatar ? (
              <img src={agent_avatar} alt={agent_name} className="h-6 w-6 rounded-md object-cover ring-1 ring-white/10" loading="lazy" />
            ) : (
              <div className="flex h-6 w-6 items-center justify-center rounded-md text-xs font-bold text-[#11231d]" style={{ background: brandAccent }}>
                {(agent_name || 'A')[0].toUpperCase()}
              </div>
            )}
            <span>{agent_name}</span>
          </Link>
          <div className="flex items-center gap-6">
            <Link href="/signin" className="transition-colors hover:text-white">Sign in</Link>
            <Link href="/signup" className="transition-colors hover:text-white">Sign up</Link>
          </div>
          <span>Powered by Synkora</span>
        </div>
      </footer>
    </div>
  )
}
