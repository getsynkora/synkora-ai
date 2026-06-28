'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { Sparkles, Star, ArrowRight } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface PublicAgent {
  id: string
  agent_name: string
  slug?: string
  description: string
  avatar?: string
  category: string
  tags: string[]
  likes_count: number
  dislikes_count: number
  usage_count: number
  model_name: string
  created_at: string
}

const formatNumber = (num: number): string => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

const slugify = (text: string): string =>
  text.toLowerCase().trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '')

const PreBuiltAgentCard = ({ agent }: { agent: PublicAgent }) => {
  const getRating = () => {
    const total = agent.likes_count + agent.dislikes_count
    if (total === 0) return 4.5
    const ratio = agent.likes_count / total
    return Math.round((3 + ratio * 2) * 10) / 10
  }

  return (
    <Link href={`/a/${agent.slug || slugify(agent.agent_name)}`}>
      <div className="flex flex-col overflow-hidden rounded-[2rem] border border-black/10 bg-white/60 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-shadow duration-300 hover:shadow-[0_24px_56px_rgba(0,0,0,0.08)]">
        <div className="relative flex min-h-[16rem] items-center justify-center overflow-hidden border-b border-black/10 bg-[linear-gradient(180deg,#efe7d8_0%,#f3ecdf_100%)] md:min-h-[18.5rem]">
          {agent.avatar ? (
            <>
              <img
                src={agent.avatar}
                alt={agent.agent_name}
                className="absolute inset-0 h-full w-full object-cover object-center"
              />
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_24%,rgba(255,255,255,0.22),transparent_42%)]" />
              <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(243,236,223,0.08),rgba(243,236,223,0.04)_45%,rgba(255,255,255,0.1))]" />
            </>
          ) : (
            <div className="relative z-10 flex h-[7.75rem] w-[7.75rem] items-center justify-center rounded-[0.4rem] border border-white/90 bg-[#fcfbf8] shadow-[0_22px_40px_rgba(109,84,55,0.16)] md:h-[9.25rem] md:w-[9.25rem]">
              <Sparkles className="h-12 w-12 text-[#2d8b69]" />
            </div>
          )}
        </div>
        <div className="p-6 flex-1 flex flex-col">
          <div className="flex items-start justify-between gap-3 mb-1">
            <h3 className="line-clamp-1 text-lg font-semibold tracking-[-0.03em] text-[#171717]">{agent.agent_name}</h3>
            {getRating() > 0 && (
              <div className="flex shrink-0 items-center gap-1 text-[#b7832f]">
                <Star className="h-4 w-4 fill-current" />
                <span className="text-sm font-semibold">{getRating().toFixed(1)}</span>
              </div>
            )}
          </div>
          <p className="mb-3 text-sm uppercase tracking-[0.16em] text-[#7a736a]">{agent.category || 'AI Agent'}</p>
          <p className="mb-4 line-clamp-2 text-sm leading-relaxed text-[#575149]">
            {agent.description || 'No description provided'}
          </p>
          <div className="my-4 border-t border-black/10" />
          <div className="flex items-center gap-6 mb-5">
            <div>
              <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Uses</p>
              <p className="text-xl font-semibold text-[#171717]">{formatNumber(agent.usage_count || 0)}</p>
            </div>
            <div>
              <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Likes</p>
              <p className="text-xl font-semibold text-[#171717]">{agent.likes_count || 0}</p>
            </div>
            <div>
              <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Rating</p>
              <p className="text-xl font-semibold text-[#171717]">{getRating().toFixed(1)}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 mt-auto">
            <span className="flex-1 rounded-full border border-black/15 px-5 py-2.5 text-center text-sm font-semibold uppercase tracking-[0.14em] text-[#171717] transition-colors hover:bg-white/80">
              Try Agent
            </span>
            <span className="px-4 py-2.5 text-sm font-medium text-[#7a736a] transition-colors hover:text-[#171717]">
              View Details
            </span>
          </div>
        </div>
      </div>
    </Link>
  )
}

const AgentCardSkeleton = () => (
  <div className="animate-pulse overflow-hidden rounded-[2rem] border border-black/10 bg-white/60 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
    <div className="flex min-h-[16rem] items-center justify-center border-b border-black/10 bg-[#efe7d8] md:min-h-[18.5rem]">
      <div className="h-[7.75rem] w-[7.75rem] rounded-[0.4rem] bg-white shadow-lg md:h-[9.25rem] md:w-[9.25rem]" />
    </div>
    <div className="p-6">
      <div className="mb-2 h-5 w-32 rounded bg-black/10" />
      <div className="mb-4 h-4 w-24 rounded bg-black/5" />
      <div className="mb-2 h-4 w-full rounded bg-black/5" />
      <div className="mb-4 h-4 w-3/4 rounded bg-black/5" />
      <div className="mb-4 border-t border-black/10 pt-4">
        <div className="flex gap-6">
          <div>
            <div className="mb-1 h-3 w-10 rounded bg-black/5" />
            <div className="h-6 w-8 rounded bg-black/10" />
          </div>
          <div>
            <div className="mb-1 h-3 w-10 rounded bg-black/5" />
            <div className="h-6 w-8 rounded bg-black/10" />
          </div>
          <div>
            <div className="mb-1 h-3 w-12 rounded bg-black/5" />
            <div className="h-6 w-10 rounded bg-black/10" />
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="h-10 flex-1 rounded-full bg-black/5" />
        <div className="h-10 w-24 rounded-full bg-black/5" />
      </div>
    </div>
  </div>
)

const staticAgents = [
  { name: 'Support Agent', category: 'Customer Support', description: 'Handles customer queries 24/7 using your knowledge base. Routes complex issues to humans via HITL approval gates.', usage_count: 1240, likes_count: 89 },
  { name: 'Code Reviewer', category: 'Engineering', description: 'Reviews pull requests, flags issues, and generates documentation. Integrates with GitHub and posts summaries to Slack.', usage_count: 980, likes_count: 74 },
  { name: 'Marketing Lead', category: 'Marketing', description: 'Drafts content, analyzes campaign performance, and manages your social media calendar autonomously.', usage_count: 760, likes_count: 61 },
]

export default function AgentsSectionClient() {
  const sectionRef = useRef<HTMLElement>(null)
  const [publicAgents, setPublicAgents] = useState<PublicAgent[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchPublicAgents = async () => {
      try {
        const params = new URLSearchParams()
        params.append('sort_by', 'popular')
        params.append('limit', '6')
        const response = await fetch(`${API_URL}/api/v1/agents/public?${params}`)
        const data = await response.json()
        if (data.success) {
          setPublicAgents(data.data.agents || [])
        }
      } catch {
        // fall through to static agents
      } finally {
        setLoading(false)
      }
    }
    fetchPublicAgents()
  }, [])

  useEffect(() => {
    if (!sectionRef.current || loading) return
    const agentCards = Array.from(sectionRef.current.querySelectorAll('.agent-card-animated'))
    if (agentCards.length === 0) return

    const sectionEl = sectionRef.current
    let trigger: { kill: () => void } | undefined
    let cancelled = false

    Promise.all([import('gsap'), import('gsap/ScrollTrigger')]).then(
      ([{ default: gsap }, { ScrollTrigger }]) => {
        if (cancelled) return
        gsap.registerPlugin(ScrollTrigger)
        trigger = ScrollTrigger.create({
          trigger: sectionEl,
          start: 'top 75%',
          onEnter: () => {
            gsap.fromTo(agentCards,
              { opacity: 0, y: 60, scale: 0.95 },
              { opacity: 1, y: 0, scale: 1, duration: 0.8, stagger: 0.15, ease: 'power3.out' }
            )
          },
          once: true,
        })
      }
    )

    return () => {
      cancelled = true
      trigger?.kill()
    }
  }, [publicAgents, loading])

  return (
    <section ref={sectionRef} className="bg-[#f4eee1] px-4 py-16 sm:px-6 sm:py-24">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/60 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
            <Sparkles className="h-4 w-4" />
            Pre-built Agents
          </div>
          <h2 className="mb-5 text-3xl font-medium tracking-[-0.05em] text-[#171717] sm:text-5xl">
            Powerful AI Agents
            <span className="block text-[#2d8b69]">
              Ready to Deploy
            </span>
          </h2>
          <p className="mx-auto max-w-2xl text-xl leading-relaxed text-[#575149]">
            Start from a template or build from scratch. Every agent is fully customizable.
          </p>
        </div>

        {loading ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[...Array(6)].map((_, i) => <AgentCardSkeleton key={i} />)}
          </div>
        ) : publicAgents.length > 0 ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {publicAgents.map((agent) => (
              <div key={agent.id} className="agent-card-animated">
                <PreBuiltAgentCard agent={agent} />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {staticAgents.map((agent, i) => (
              <div key={i} className="flex flex-col overflow-hidden rounded-[2rem] border border-black/10 bg-white/60 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-shadow hover:shadow-[0_24px_56px_rgba(0,0,0,0.08)]">
                <div className="flex min-h-[16rem] items-center justify-center border-b border-black/10 bg-[#efe7d8] md:min-h-[18.5rem]">
                  <div className="flex h-[7.75rem] w-[7.75rem] items-center justify-center rounded-[0.4rem] border border-white/90 bg-white shadow-[0_22px_40px_rgba(109,84,55,0.16)] md:h-[9.25rem] md:w-[9.25rem]">
                    <Sparkles className="h-12 w-12 text-[#2d8b69]" />
                  </div>
                </div>
                <div className="p-6 flex-1 flex flex-col">
                  <h3 className="mb-1 text-lg font-semibold tracking-[-0.03em] text-[#171717]">{agent.name}</h3>
                  <p className="mb-3 text-sm uppercase tracking-[0.16em] text-[#7a736a]">{agent.category}</p>
                  <p className="mb-4 text-sm leading-relaxed text-[#575149]">{agent.description}</p>
                  <div className="mt-auto flex items-center gap-6 border-t border-black/10 pt-4">
                    <div>
                      <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Uses</p>
                      <p className="text-xl font-semibold text-[#171717]">{formatNumber(agent.usage_count)}</p>
                    </div>
                    <div>
                      <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Likes</p>
                      <p className="text-xl font-semibold text-[#171717]">{agent.likes_count}</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="text-center mt-16">
          <Link
            href="https://app.synkora.ai/signup"
            className="group inline-flex items-center gap-3 rounded-full bg-[#191919] px-10 py-5 text-lg font-semibold text-[#f7f2e7] transition-transform hover:-translate-y-0.5"
          >
            <span>Start Building Free</span>
            <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
          </Link>
        </div>
      </div>
    </section>
  )
}
