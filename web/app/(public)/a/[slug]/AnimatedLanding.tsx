'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ExampleConversation } from '@/components/landing/ExampleConversation'
import { PricingCTA } from '@/components/landing/PricingCTA'
import { useTranslations } from 'next-intl'

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
  const tt = useTranslations('publicAgent')
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
        throw new Error(d?.detail || tt('subscriptionFailed'))
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
    pricing.session_credits && { label: tt('tierSession'), credits: pricing.session_credits, tier: 'SESSION', desc: tt('tierSessionDesc') },
    pricing.daily_credits && { label: tt('tierDaily'), credits: pricing.daily_credits, tier: 'DAILY', desc: tt('tierDailyDesc') },
    pricing.weekly_credits && { label: tt('tierWeekly'), credits: pricing.weekly_credits, tier: 'WEEKLY', desc: tt('tierWeeklyDesc') },
    pricing.monthly_credits && { label: tt('tierMonthly'), credits: pricing.monthly_credits, tier: 'MONTHLY', desc: tt('tierMonthlyDesc'), popular: true },
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

  return (
    <div
      ref={rootRef}
      className="min-h-screen overflow-x-hidden text-ink"
      style={{ background: brandBg, fontFamily: '"Avenir Next", "Helvetica Neue", "Segoe UI", sans-serif' }}
    >

      {/* ── Navigation ── */}
      <header
        ref={navRef}
        className="sticky top-0 z-50 border-b border-black/10 bg-paper/95 transition-shadow"
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between gap-6">
          <Link href="/" className="flex items-center gap-2.5 flex-shrink-0 hover:opacity-80 transition-opacity">
            {agent_avatar ? (
              <img src={agent_avatar} alt={agent_name} className="w-8 h-8 rounded-xl object-cover ring-1 ring-black/10" loading="lazy" />
            ) : (
              <div
                className="w-8 h-8 rounded-xl flex items-center justify-center text-ink font-bold text-sm select-none"
                style={{ background: brandAccent }}
              >
                {(agent_name || 'A')[0].toUpperCase()}
              </div>
            )}
            <span className="font-semibold text-ink text-sm tracking-[-0.02em]">{agent_name}</span>
          </Link>

          <nav className="hidden md:flex items-center gap-7 text-sm text-ink-mute">
            {long_description && (
              <button onClick={() => scrollTo('about')} className="nav-link hover:text-ink transition-colors cursor-pointer">About</button>
            )}
            {hasExamples && (
              <button onClick={() => scrollTo('examples')} className="nav-link hover:text-ink transition-colors cursor-pointer">Examples</button>
            )}
            {hasGallery && (
              <button onClick={() => scrollTo('gallery')} className="nav-link hover:text-ink transition-colors cursor-pointer">Gallery</button>
            )}
            <button onClick={() => scrollTo('pricing')} className="nav-link hover:text-ink transition-colors cursor-pointer">Pricing</button>
            {allow_subscriptions && (
              <button onClick={() => scrollTo('subscribe')} className="nav-link hover:text-ink transition-colors cursor-pointer">Subscribe</button>
            )}
            {hasCreator && (
              <button onClick={() => scrollTo('creator')} className="nav-link hover:text-ink transition-colors cursor-pointer">Creator</button>
            )}
          </nav>

          <div className="flex items-center gap-3 flex-shrink-0">
            <Link href="/signin" className="hidden sm:block text-sm text-ink-mute hover:text-ink transition-colors font-medium">
              Log In
            </Link>
            <button
              onClick={() => scrollTo('pricing')}
              className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-paper transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:-translate-y-0.5 hover:bg-black cursor-pointer"
            >
              {tt('getStarted')}
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="hero-section relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none" />
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
            className="mb-8 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2 shadow-soft cursor-default"
          >
            <span className="rounded-full px-2 py-0.5 text-xs font-bold text-ink" style={{ background: brandAccent }}>AI</span>
            <span className="text-sm text-ink-mute">Intelligent Agent, Ready to use</span>
          </div>

          {/* Split-word headline */}
          <h1 ref={headlineRef} className="mb-4 overflow-hidden text-5xl font-semibold leading-[1.04] tracking-[-0.06em] text-ink md:text-7xl">
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
            <p ref={subRef} className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-ink-soft md:text-xl">
              {long_description.split('\n')[0].slice(0, 180)}
            </p>
          )}

          <div ref={ctaRef} className="flex items-center justify-center gap-4 flex-wrap">
            <button
              onClick={() => scrollTo('pricing')}
              className="hero-cta-btn rounded-full bg-ink px-8 py-3.5 text-base font-semibold text-paper shadow-soft transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:-translate-y-0.5 hover:bg-black cursor-pointer"
            >
              {cta_label || tt('tryFree')}
            </button>
            {long_description && (
              <button
                onClick={() => scrollTo('about')}
                className="hero-cta-btn rounded-full border border-black/10 bg-white/70 px-8 py-3.5 text-base font-semibold text-ink transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:-translate-y-0.5 hover:bg-white cursor-pointer"
              >
                {tt('learnMore')}
              </button>
            )}
          </div>

          {pricing?.trial_messages && pricing.trial_messages > 0 ? (
            <p className="mt-4 text-sm text-ink-mute">
              First {pricing.trial_messages} messages free, no credit card required
            </p>
          ) : null}
        </div>

        {/* Hero product screenshot */}
        {hero_image_url && (
          <div ref={heroImgRef} className="max-w-5xl mx-auto px-6 pb-0">
            <div className="overflow-hidden rounded-t-[2rem] border border-black/10 bg-white/75 shadow-soft">
              <div className="flex items-center gap-2 border-b border-black/10 bg-sand px-4 py-3">
                <div className="flex gap-1.5">
                  <div className="h-3 w-3 rounded-full bg-ink" />
                  <div className="h-3 w-3 rounded-full bg-warn" />
                  <div className="h-3 w-3 rounded-full bg-mint" />
                </div>
                <div className="flex-1 mx-4">
                  <div className="mx-auto max-w-xs rounded-full border border-black/10 bg-white px-3 py-1 text-center text-xs text-ink-mute">
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
              <h2 className="section-title text-3xl font-medium tracking-[-0.05em] text-ink md:text-4xl">What this agent does</h2>
            </div>
            <div className="rounded-[2rem] border border-black/10 bg-white/70 p-8 shadow-soft md:p-10">
              <p className="whitespace-pre-wrap text-lg leading-relaxed text-ink-soft">{long_description}</p>
            </div>
          </div>
        </section>
      )}

      {/* ── Gallery ── */}
      {hasGallery && (
        <section id="gallery" className="reveal-section px-6 py-20">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-12">
              <span className="mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold text-ink-soft">
                {tt('gallery')}
              </span>
              <h2 className="text-3xl font-medium tracking-[-0.05em] text-ink md:text-4xl">{tt('screenshotsMedia')}</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
              {validGallery.map((img, i) => (
                <div key={i} className="gallery-img group relative aspect-video overflow-hidden rounded-[1.7rem] border border-black/10 bg-white/70 shadow-soft transition-shadow hover:shadow-soft cursor-pointer">
                  <img src={img.url} alt={img.caption || ''} className="w-full h-full object-cover group-hover:scale-105 transition-transform motion-reduce:transition-none duration-500" loading="lazy" />
                  {img.caption && (
                    <div className="absolute bottom-0 left-0 right-0 translate-y-full bg-gradient-to-t from-black/65 to-transparent px-3 py-2 text-xs font-medium text-white transition-transform motion-reduce:transition-none duration-300 group-hover:translate-y-0">
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
              <h2 className="text-3xl font-medium tracking-[-0.05em] text-ink md:text-4xl">See it in action</h2>
            </div>
            <div className="aspect-video overflow-hidden rounded-[2rem] border border-black/10 bg-white/75 shadow-soft">
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
              <span className="mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold text-ink-soft">
                {tt('examples')}
              </span>
              <h2 className="mb-3 text-3xl font-medium tracking-[-0.05em] text-ink md:text-4xl">{tt('realConversations')}</h2>
              <p className="text-lg text-ink-soft">See exactly what you can expect</p>
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
            <span className="section-badge mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold text-ink-soft">
              {tt('pricing')}
            </span>
            <h2 className="section-title mb-4 text-3xl font-medium tracking-[-0.05em] text-ink md:text-4xl">{tt('simplePricing')}</h2>
            <p className="section-sub text-lg text-ink-soft">Pay only for what you use. No hidden fees.</p>
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
                    className={`stagger-card relative rounded-2xl p-7 border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:-translate-y-2 hover:shadow-xl cursor-default ${
                      t.popular ? 'pricing-popular bg-white' : 'border-black/10 bg-white/70 shadow-soft'
                    }`}
                    style={t.popular ? { borderColor: brandAccent, background: brandSurface } : {}}
                  >
                    {t.popular && (
                      <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-ink px-4 py-1 text-xs font-bold text-paper" >
                        {tt('mostPopular')}
                      </div>
                    )}
                    <div className="mb-4 text-xs font-bold text-ink-mute">{t.label}</div>
                    <div className="flex items-baseline gap-1 mb-1">
                      <span className="text-4xl font-semibold tracking-[-0.05em] text-ink">{t.credits}</span>
                      <span className="text-sm font-medium text-ink-mute">{tt('credits')}</span>
                    </div>
                    <p className="mt-3 text-sm text-ink-soft">{t.desc}</p>
                    <div className="mt-6">
                      <a
                        href={`/agents/${slug}/chat`}
                        className="block w-full py-2.5 text-center text-sm font-semibold rounded-xl transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:opacity-90"
                        style={t.popular ? { background: 'rgb(var(--ink))', color: 'rgb(var(--paper))' } : { background: 'rgb(var(--sand))', color: 'rgb(var(--ink))' }}
                      >
                        {tt('getStartedLower')}
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
              <div className="inline-block rounded-[2rem] border border-black/10 bg-white/75 px-12 py-10 shadow-soft transition-shadow hover:shadow-soft">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full" style={{ background: `${brandAccent}22` }}>
                  <svg aria-hidden="true" className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke={brandInk} strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="mb-2 text-3xl font-semibold tracking-[-0.05em] text-ink">Free</div>
                <div className="mb-6 text-ink-soft">No cost to use this agent</div>
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
              <span className="mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold text-ink-soft">
                {tt('creator')}
              </span>
              <h2 className="text-3xl font-medium tracking-[-0.05em] text-ink">{tt('meetCreator')}</h2>
            </div>
            <div className="creator-card flex flex-col items-center gap-6 rounded-[2rem] border border-black/10 bg-white/75 p-8 shadow-soft transition-shadow hover:shadow-soft sm:flex-row sm:items-start">
              {creator?.avatar_url ? (
                <img src={creator.avatar_url} alt={displayName || ''} className="h-20 w-20 flex-shrink-0 rounded-full border border-black/10 object-cover" loading="lazy" />
              ) : (
                <div className="flex h-20 w-20 flex-shrink-0 items-center justify-center rounded-full text-2xl font-bold text-ink" style={{ background: brandAccent }}>
                  {(displayName || 'C')[0].toUpperCase()}
                </div>
              )}
              <div className="flex-1 text-center sm:text-left">
                <div className="mb-2 text-xl font-semibold tracking-[-0.03em] text-ink">{displayName || 'Creator'}</div>
                {displayBio && <p className="mb-4 text-sm leading-relaxed text-ink-soft">{displayBio}</p>}
                <div className="flex items-center justify-center sm:justify-start gap-4 flex-wrap">
                  {creator?.website_url && <a href={creator.website_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-ink hover:underline">Website ↗</a>}
                  {creator?.twitter_url && <a href={creator.twitter_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-ink hover:underline">Twitter ↗</a>}
                  {creator?.github_url && <a href={creator.github_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-ink hover:underline">GitHub ↗</a>}
                  {creator?.linkedin_url && <a href={creator.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-ink hover:underline">LinkedIn ↗</a>}
                  {creator?.username && <Link href={`/creators/${creator.username}`} className="text-sm font-medium text-ink hover:underline">View all agents ↗</Link>}
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
              <span className="section-badge mb-4 inline-block rounded-full border border-black/10 bg-white/70 px-3 py-1 text-xs font-semibold text-ink-soft">
                {tt('freeUpdates')}
              </span>
              <h2 className="section-title mb-3 text-3xl font-medium tracking-[-0.05em] text-ink md:text-4xl">
                {tt('stayInLoop')}
              </h2>
              <p className="section-sub text-lg text-ink-soft">
                {tt('subscribeBlurb')}
              </p>
            </div>

            {emailDone ? (
              <div className="flex items-center justify-center gap-3 rounded-[1.6rem] border border-black/10 bg-white/80 px-6 py-4 shadow-soft">
                <span className="text-2xl">✓</span>
                <p className="font-semibold text-ink">{tt('subscribed')}</p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex gap-2">
                  <input
                    type="email"
                    value={emailInput}
                    onChange={e => setEmailInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleEmailSubscribe()}
                    placeholder={tt('emailPlaceholder')}
                    className="flex-1 rounded-[1.2rem] border border-black/10 bg-white/90 px-4 py-3.5 text-sm text-ink shadow-sm focus:border-transparent focus:outline-none focus:ring-2"
                    style={{ '--tw-ring-color': brandAccent } as React.CSSProperties}
                  />
                  <button
                    onClick={handleEmailSubscribe}
                    disabled={emailLoading || !emailInput.trim()}
                    className="rounded-[1.2rem] bg-ink px-6 py-3.5 text-sm font-semibold text-paper shadow-sm transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:bg-black disabled:opacity-50"
                  >
                    {emailLoading ? '...' : tt('subscribeFree')}
                  </button>
                </div>
                {emailError && <p className="text-leaf text-sm">{emailError}</p>}
                <p className="text-xs text-ink-mute">No spam. Unsubscribe anytime.</p>
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
              className="rounded-full bg-paper px-8 py-4 text-base font-semibold text-ink transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:-translate-y-0.5 hover:bg-white"
            >
              {cta_label || tt('tryFree')}
            </a>
            <Link href="/signup" className="rounded-full border border-white/20 bg-white/10 px-8 py-4 text-base font-semibold text-white transition-colors hover:bg-white/16">
              {tt('createAccount')}
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-white/8 bg-ink px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-sm text-taupe sm:flex-row">
          <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            {agent_avatar ? (
              <img src={agent_avatar} alt={agent_name} className="h-6 w-6 rounded-md object-cover ring-1 ring-white/10" loading="lazy" />
            ) : (
              <div className="flex h-6 w-6 items-center justify-center rounded-md text-xs font-bold text-ink" style={{ background: brandAccent }}>
                {(agent_name || 'A')[0].toUpperCase()}
              </div>
            )}
            <span>{agent_name}</span>
          </Link>
          <div className="flex items-center gap-6">
            <Link href="/signin" className="transition-colors hover:text-white">{tt('signIn')}</Link>
            <Link href="/signup" className="transition-colors hover:text-white">{tt('signUp')}</Link>
          </div>
          <span>{tt('poweredBy')}</span>
        </div>
      </footer>
    </div>
  )
}
