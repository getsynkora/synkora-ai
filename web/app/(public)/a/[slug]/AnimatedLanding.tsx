'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { ExampleConversation } from '@/components/landing/ExampleConversation'
import { PricingCTA } from '@/components/landing/PricingCTA'

gsap.registerPlugin(ScrollTrigger)

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

  const accent = accent_color || '#e11d48'
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
    const onLoad = () => ScrollTrigger.refresh()
    const ctx = gsap.context(() => {
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
    // requestAnimationFrame runs after the first paint; the timeout
    // catches late-loading images that shift the layout.
    let rafId: number
    let timerId: ReturnType<typeof setTimeout>
    if (document.readyState === 'complete') {
      rafId = requestAnimationFrame(() => ScrollTrigger.refresh())
      timerId = setTimeout(() => ScrollTrigger.refresh(), 300)
    } else {
      window.addEventListener('load', onLoad)
    }

    return () => {
      ctx.revert()
      window.removeEventListener('load', onLoad)
      cancelAnimationFrame(rafId)
      clearTimeout(timerId)
    }
  }, [accent])

  return (
    <div ref={rootRef} className="min-h-screen bg-white text-gray-900 overflow-x-hidden">

      {/* ── Navigation ── */}
      <header
        ref={navRef}
        className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-gray-100 transition-shadow"
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between gap-6">
          <Link href="/" className="flex items-center gap-2.5 flex-shrink-0 hover:opacity-80 transition-opacity">
            {agent_avatar ? (
              <img src={agent_avatar} alt={agent_name} className="w-8 h-8 rounded-lg object-cover" />
            ) : (
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm select-none"
                style={{ background: accent }}
              >
                {(agent_name || 'A')[0].toUpperCase()}
              </div>
            )}
            <span className="font-semibold text-gray-900 text-sm">{agent_name}</span>
          </Link>

          <nav className="hidden md:flex items-center gap-7 text-sm text-gray-500">
            {long_description && (
              <button onClick={() => scrollTo('about')} className="nav-link hover:text-gray-900 transition-colors cursor-pointer">About</button>
            )}
            {hasExamples && (
              <button onClick={() => scrollTo('examples')} className="nav-link hover:text-gray-900 transition-colors cursor-pointer">Examples</button>
            )}
            {hasGallery && (
              <button onClick={() => scrollTo('gallery')} className="nav-link hover:text-gray-900 transition-colors cursor-pointer">Gallery</button>
            )}
            <button onClick={() => scrollTo('pricing')} className="nav-link hover:text-gray-900 transition-colors cursor-pointer">Pricing</button>
            {allow_subscriptions && (
              <button onClick={() => scrollTo('subscribe')} className="nav-link hover:text-gray-900 transition-colors cursor-pointer">Subscribe</button>
            )}
            {hasCreator && (
              <button onClick={() => scrollTo('creator')} className="nav-link hover:text-gray-900 transition-colors cursor-pointer">Creator</button>
            )}
          </nav>

          <div className="flex items-center gap-3 flex-shrink-0">
            <Link href="/signin" className="hidden sm:block text-sm text-gray-600 hover:text-gray-900 transition-colors font-medium">
              Log In
            </Link>
            <button
              onClick={() => scrollTo('pricing')}
              className="px-4 py-2 text-sm font-semibold text-white rounded-lg transition-all hover:opacity-90 hover:scale-105 cursor-pointer"
              style={{ background: accent }}
            >
              Get Started
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="hero-section relative overflow-hidden">
        <div
          className="hero-bg-glow absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] pointer-events-none"
          style={{ background: `radial-gradient(ellipse at center, ${accent}18 0%, transparent 65%)` }}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(circle, #e5e7eb 1.5px, transparent 1.5px)',
            backgroundSize: '28px 28px',
            WebkitMaskImage: 'radial-gradient(ellipse 100% 100% at 50% 0%, black 50%, transparent 100%)',
            maskImage: 'radial-gradient(ellipse 100% 100% at 50% 0%, black 50%, transparent 100%)',
          }}
        />

        <div className="relative max-w-5xl mx-auto px-6 pt-20 pb-12 text-center">
          {/* Badge */}
          <div ref={badgeRef} className="inline-flex items-center gap-2 mb-8 px-4 py-2 bg-white border border-gray-200 rounded-full shadow-sm cursor-default">
            <span className="px-2 py-0.5 text-xs font-bold text-white rounded-full" style={{ background: accent }}>AI</span>
            <span className="text-sm text-gray-600">Intelligent Agent — Ready to use</span>
          </div>

          {/* Split-word headline */}
          <h1 ref={headlineRef} className="text-5xl md:text-7xl font-extrabold text-gray-900 leading-[1.08] tracking-tight mb-4 overflow-hidden">
            {agent_name.split(' ').map((word, i) => (
              <span key={i} className="inline-block overflow-hidden mr-[0.25em] last:mr-0">
                <span className="hero-word inline-block">{word}</span>
              </span>
            ))}
          </h1>

          {tagline && (
            <p ref={taglineRef} className="text-2xl md:text-3xl font-semibold mb-4" style={{ color: accent }}>
              {tagline}
            </p>
          )}

          {long_description && (
            <p ref={subRef} className="text-lg md:text-xl text-gray-500 max-w-2xl mx-auto mb-10 leading-relaxed">
              {long_description.split('\n')[0].slice(0, 180)}
            </p>
          )}

          <div ref={ctaRef} className="flex items-center justify-center gap-4 flex-wrap">
            <button
              onClick={() => scrollTo('pricing')}
              className="hero-cta-btn px-8 py-3.5 text-white font-semibold rounded-full text-base transition-all hover:opacity-90 hover:-translate-y-0.5 shadow-lg cursor-pointer"
              style={{ background: accent, boxShadow: `0 8px 24px ${accent}40` }}
            >
              {cta_label || 'Try it for Free'}
            </button>
            {long_description && (
              <button
                onClick={() => scrollTo('about')}
                className="hero-cta-btn px-8 py-3.5 bg-white border-2 border-gray-200 hover:border-gray-300 text-gray-700 font-semibold rounded-full text-base transition-all hover:-translate-y-0.5 cursor-pointer"
              >
                Learn more
              </button>
            )}
          </div>

          {pricing?.trial_messages && pricing.trial_messages > 0 ? (
            <p className="mt-4 text-sm text-gray-400">
              First {pricing.trial_messages} messages free — no credit card required
            </p>
          ) : null}
        </div>

        {/* Hero product screenshot */}
        {hero_image_url && (
          <div ref={heroImgRef} className="max-w-5xl mx-auto px-6 pb-0">
            <div className="rounded-t-2xl overflow-hidden border-t border-l border-r border-gray-200 shadow-2xl shadow-gray-300/40">
              <div className="bg-gray-100 border-b border-gray-200 px-4 py-2.5 flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-gray-300" />
                  <div className="w-3 h-3 rounded-full bg-gray-300" />
                  <div className="w-3 h-3 rounded-full bg-gray-300" />
                </div>
                <div className="flex-1 mx-4">
                  <div className="bg-white rounded-md px-3 py-1 text-xs text-gray-400 max-w-xs mx-auto text-center border border-gray-200">
                    {agent_name}
                  </div>
                </div>
              </div>
              <img src={hero_image_url} alt={agent_name} className="w-full object-cover" />
            </div>
          </div>
        )}
      </section>

      {/* ── About ── */}
      {long_description && (
        <section id="about" className="py-24 px-6 bg-gray-50/60 reveal-section">
          <div className="max-w-4xl mx-auto">
            <div className="section-header text-center mb-12">
              <span className="section-badge inline-block px-3 py-1 text-xs font-semibold uppercase tracking-widest rounded-full mb-4 text-white" style={{ background: accent }}>
                About
              </span>
              <h2 className="section-title text-3xl md:text-4xl font-extrabold text-gray-900">What this agent does</h2>
            </div>
            <div className="bg-white rounded-2xl p-8 md:p-10 border border-gray-200 shadow-sm">
              <p className="text-gray-600 text-lg leading-relaxed whitespace-pre-wrap">{long_description}</p>
            </div>
          </div>
        </section>
      )}

      {/* ── Gallery ── */}
      {hasGallery && (
        <section id="gallery" className="py-20 px-6 reveal-section">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-12">
              <span className="inline-block px-3 py-1 text-xs font-semibold uppercase tracking-widest rounded-full mb-4 text-white" style={{ background: accent }}>
                Gallery
              </span>
              <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900">Screenshots & Media</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
              {validGallery.map((img, i) => (
                <div key={i} className="gallery-img relative aspect-video rounded-xl overflow-hidden border border-gray-200 shadow-md hover:shadow-xl transition-shadow group cursor-pointer">
                  <img src={img.url} alt={img.caption || ''} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                  {img.caption && (
                    <div className="absolute bottom-0 left-0 right-0 px-3 py-2 bg-gradient-to-t from-black/60 to-transparent text-xs text-white font-medium translate-y-full group-hover:translate-y-0 transition-transform duration-300">
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
        <section className="py-20 px-6 bg-gray-50/60 reveal-section">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-12">
              <span className="inline-block px-3 py-1 text-xs font-semibold uppercase tracking-widest rounded-full mb-4 text-white" style={{ background: accent }}>
                Demo
              </span>
              <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900">See it in action</h2>
            </div>
            <div className="rounded-2xl overflow-hidden border border-gray-200 shadow-xl aspect-video">
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
        <section id="examples" className="py-20 px-6 reveal-section">
          <div className="max-w-3xl mx-auto">
            <div className="text-center mb-12">
              <span className="inline-block px-3 py-1 text-xs font-semibold uppercase tracking-widest rounded-full mb-4 text-white" style={{ background: accent }}>
                Examples
              </span>
              <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 mb-3">Real conversations</h2>
              <p className="text-gray-500 text-lg">See exactly what you can expect</p>
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
      <section id="pricing" className="py-24 px-6 bg-gray-50/60 reveal-section">
        <div className="max-w-5xl mx-auto">
          <div className="section-header text-center mb-16">
            <span className="section-badge inline-block px-3 py-1 text-xs font-semibold uppercase tracking-widest rounded-full mb-4 text-white" style={{ background: accent }}>
              Pricing
            </span>
            <h2 className="section-title text-3xl md:text-4xl font-extrabold text-gray-900 mb-4">Simple, transparent pricing</h2>
            <p className="section-sub text-gray-500 text-lg">Pay only for what you use. No hidden fees.</p>
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
                      t.popular ? 'pricing-popular bg-white' : 'bg-white border-gray-200 shadow-sm'
                    }`}
                    style={t.popular ? { borderColor: accent } : {}}
                  >
                    {t.popular && (
                      <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-4 py-1 text-white rounded-full text-xs font-bold whitespace-nowrap" style={{ background: accent }}>
                        Most Popular
                      </div>
                    )}
                    <div className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-4">{t.label}</div>
                    <div className="flex items-baseline gap-1 mb-1">
                      <span className="text-4xl font-extrabold text-gray-900">{t.credits}</span>
                      <span className="text-gray-400 text-sm font-medium">credits</span>
                    </div>
                    <p className="text-gray-500 text-sm mt-3">{t.desc}</p>
                    <div className="mt-6">
                      <a
                        href={`/agents/${encodeURIComponent(agent_name)}/chat`}
                        className="block w-full py-2.5 text-center text-sm font-semibold rounded-xl transition-all hover:opacity-90"
                        style={t.popular ? { background: accent, color: '#fff' } : { background: '#f3f4f6', color: '#374151' }}
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
              <div className="inline-block bg-white border-2 border-gray-200 rounded-2xl px-12 py-10 shadow-sm hover:shadow-md transition-shadow">
                <div className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4" style={{ background: `${accent}15` }}>
                  <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke={accent} strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="text-3xl font-extrabold text-gray-900 mb-2">Free</div>
                <div className="text-gray-500 mb-6">No cost to use this agent</div>
                <PricingCTA agentSlug={slug} agentName={agent_name} pricingId="" tiers={[]} trialMessages={0} accentColor={accent} isFree={true} />
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ── Creator ── */}
      {hasCreator && (
        <section id="creator" className="py-20 px-6 reveal-section">
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-10">
              <span className="inline-block px-3 py-1 text-xs font-semibold uppercase tracking-widest rounded-full mb-4 text-white" style={{ background: accent }}>
                Creator
              </span>
              <h2 className="text-3xl font-extrabold text-gray-900">Meet the creator</h2>
            </div>
            <div className="creator-card bg-white border border-gray-200 rounded-2xl p-8 shadow-sm hover:shadow-md transition-shadow flex flex-col sm:flex-row items-center sm:items-start gap-6">
              {creator?.avatar_url ? (
                <img src={creator.avatar_url} alt={displayName || ''} className="w-20 h-20 rounded-full object-cover border-2 border-gray-200 flex-shrink-0" />
              ) : (
                <div className="w-20 h-20 rounded-full flex items-center justify-center text-white text-2xl font-bold flex-shrink-0" style={{ background: accent }}>
                  {(displayName || 'C')[0].toUpperCase()}
                </div>
              )}
              <div className="flex-1 text-center sm:text-left">
                <div className="text-xl font-bold text-gray-900 mb-2">{displayName || 'Creator'}</div>
                {displayBio && <p className="text-gray-500 text-sm leading-relaxed mb-4">{displayBio}</p>}
                <div className="flex items-center justify-center sm:justify-start gap-4 flex-wrap">
                  {creator?.website_url && <a href={creator.website_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:underline" style={{ color: accent }}>Website ↗</a>}
                  {creator?.twitter_url && <a href={creator.twitter_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:underline" style={{ color: accent }}>Twitter ↗</a>}
                  {creator?.github_url && <a href={creator.github_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:underline" style={{ color: accent }}>GitHub ↗</a>}
                  {creator?.linkedin_url && <a href={creator.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:underline" style={{ color: accent }}>LinkedIn ↗</a>}
                  {creator?.username && <Link href={`/creators/${creator.username}`} className="text-sm font-medium hover:underline" style={{ color: accent }}>View all agents ↗</Link>}
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── Free Email Subscription ── */}
      {allow_subscriptions && (
        <section id="subscribe" className="py-20 px-6 bg-gray-50/60 reveal-section">
          <div className="max-w-xl mx-auto text-center">
            <div className="section-header mb-8">
              <span className="section-badge inline-block px-3 py-1 text-xs font-semibold uppercase tracking-widest rounded-full mb-4 text-white" style={{ background: accent }}>
                Free Updates
              </span>
              <h2 className="section-title text-3xl md:text-4xl font-extrabold text-gray-900 mb-3">
                Stay in the loop
              </h2>
              <p className="section-sub text-gray-500 text-lg">
                Subscribe to receive agent outputs and updates by email — completely free.
              </p>
            </div>

            {emailDone ? (
              <div className="flex items-center justify-center gap-3 py-4 px-6 bg-white border border-gray-200 rounded-2xl shadow-sm">
                <span className="text-2xl">✓</span>
                <p className="font-semibold text-gray-900">You're subscribed! Check your inbox.</p>
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
                    className="flex-1 px-4 py-3.5 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:border-transparent shadow-sm"
                    style={{ '--tw-ring-color': accent } as React.CSSProperties}
                  />
                  <button
                    onClick={handleEmailSubscribe}
                    disabled={emailLoading || !emailInput.trim()}
                    className="px-6 py-3.5 rounded-xl font-semibold text-white text-sm transition-all hover:opacity-90 disabled:opacity-50 shadow-sm"
                    style={{ background: accent }}
                  >
                    {emailLoading ? '...' : 'Subscribe Free'}
                  </button>
                </div>
                {emailError && <p className="text-red-500 text-sm">{emailError}</p>}
                <p className="text-xs text-gray-400">No spam. Unsubscribe anytime.</p>
              </div>
            )}
          </div>
        </section>
      )}

      {/* ── Final CTA ── */}
      <section
        className="final-cta-section py-24 px-6 text-white text-center"
        style={{ background: `linear-gradient(135deg, ${accent} 0%, ${accent}cc 100%)` }}
      >
        <div className="max-w-2xl mx-auto">
          <h2 className="cta-line text-3xl md:text-5xl font-extrabold mb-4 tracking-tight">Ready to get started?</h2>
          <p className="cta-line text-white/70 text-lg mb-10">{tagline || `Start using ${agent_name} today.`}</p>
          <div className="cta-line flex items-center justify-center gap-4 flex-wrap">
            <a
              href="#pricing"
              className="px-8 py-4 bg-white font-bold rounded-full text-base hover:bg-gray-50 transition-all hover:scale-105"
              style={{ color: accent }}
            >
              {cta_label || 'Try it for Free'}
            </a>
            <Link href="/signup" className="px-8 py-4 bg-white/10 border-2 border-white/30 text-white font-semibold rounded-full text-base hover:bg-white/20 transition-colors">
              Create account
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-white border-t border-gray-100 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-gray-400">
          <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            {agent_avatar ? (
              <img src={agent_avatar} alt={agent_name} className="w-6 h-6 rounded-md object-cover" />
            ) : (
              <div className="w-6 h-6 rounded-md flex items-center justify-center text-white font-bold text-xs" style={{ background: accent }}>
                {(agent_name || 'A')[0].toUpperCase()}
              </div>
            )}
            <span>{agent_name}</span>
          </Link>
          <div className="flex items-center gap-6">
            <Link href="/signin" className="hover:text-gray-700 transition-colors">Sign in</Link>
            <Link href="/signup" className="hover:text-gray-700 transition-colors">Sign up</Link>
          </div>
          <span>Powered by AI</span>
        </div>
      </footer>
    </div>
  )
}
