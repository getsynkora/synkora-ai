'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Sparkles, Star, ArrowRight } from 'lucide-react'

gsap.registerPlugin(ScrollTrigger)

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
      <div className="bg-white rounded-3xl overflow-hidden shadow-sm hover:shadow-lg transition-shadow duration-300 flex flex-col">
        <div className="relative bg-gradient-to-br from-red-100 via-pink-50 to-orange-50 pt-10 pb-12 flex items-center justify-center">
          {agent.avatar ? (
            <img
              src={agent.avatar}
              alt={agent.agent_name}
              className="w-24 h-24 rounded-2xl object-cover shadow-lg bg-white"
            />
          ) : (
            <div className="w-24 h-24 rounded-2xl bg-white shadow-lg flex items-center justify-center">
              <Sparkles className="w-12 h-12 text-red-500" />
            </div>
          )}
        </div>
        <div className="p-6 flex-1 flex flex-col">
          <div className="flex items-start justify-between gap-3 mb-1">
            <h3 className="text-lg font-bold text-gray-900 line-clamp-1">{agent.agent_name}</h3>
            {getRating() > 0 && (
              <div className="flex items-center gap-1 text-amber-500 flex-shrink-0">
                <Star className="w-4 h-4 fill-current" />
                <span className="font-semibold text-sm">{getRating().toFixed(1)}</span>
              </div>
            )}
          </div>
          <p className="text-sm text-gray-400 mb-3">{agent.category || 'AI Agent'}</p>
          <p className="text-sm text-gray-600 leading-relaxed line-clamp-2 mb-4">
            {agent.description || 'No description provided'}
          </p>
          <div className="border-t border-gray-100 my-4" />
          <div className="flex items-center gap-6 mb-5">
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Uses</p>
              <p className="text-xl font-bold text-gray-900">{formatNumber(agent.usage_count || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Likes</p>
              <p className="text-xl font-bold text-gray-900">{agent.likes_count || 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Rating</p>
              <p className="text-xl font-bold text-gray-900">{getRating().toFixed(1)}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 mt-auto">
            <span className="flex-1 px-5 py-2.5 border border-red-300 text-red-500 text-sm font-semibold rounded-xl hover:bg-red-50 hover:border-red-400 transition-colors text-center">
              Try Agent
            </span>
            <span className="px-4 py-2.5 text-gray-400 text-sm font-medium hover:text-gray-600 transition-colors">
              View Details
            </span>
          </div>
        </div>
      </div>
    </Link>
  )
}

const AgentCardSkeleton = () => (
  <div className="bg-white rounded-3xl overflow-hidden shadow-sm animate-pulse">
    <div className="bg-gradient-to-br from-red-50 via-pink-50 to-orange-50 pt-10 pb-12 flex items-center justify-center">
      <div className="w-24 h-24 bg-white rounded-2xl shadow-lg" />
    </div>
    <div className="p-6">
      <div className="h-5 bg-gray-200 rounded w-32 mb-2" />
      <div className="h-4 bg-gray-100 rounded w-24 mb-4" />
      <div className="h-4 bg-gray-100 rounded w-full mb-2" />
      <div className="h-4 bg-gray-100 rounded w-3/4 mb-4" />
      <div className="border-t border-gray-100 pt-4 mb-4">
        <div className="flex gap-6">
          <div>
            <div className="h-3 bg-gray-100 rounded w-10 mb-1" />
            <div className="h-6 bg-gray-200 rounded w-8" />
          </div>
          <div>
            <div className="h-3 bg-gray-100 rounded w-10 mb-1" />
            <div className="h-6 bg-gray-200 rounded w-8" />
          </div>
          <div>
            <div className="h-3 bg-gray-100 rounded w-12 mb-1" />
            <div className="h-6 bg-gray-200 rounded w-10" />
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex-1 h-10 bg-gray-100 rounded-xl" />
        <div className="h-10 bg-gray-50 rounded w-24" />
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
  const [loading, setLoading] = useState(true)

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

    const t = ScrollTrigger.create({
      trigger: sectionRef.current,
      start: 'top 75%',
      onEnter: () => {
        gsap.fromTo(agentCards,
          { opacity: 0, y: 60, scale: 0.95 },
          { opacity: 1, y: 0, scale: 1, duration: 0.8, stagger: 0.15, ease: 'power3.out' }
        )
      },
      once: true,
    })

    return () => { t.kill() }
  }, [publicAgents, loading])

  return (
    <section ref={sectionRef} className="py-16 sm:py-24 px-4 sm:px-6 bg-gradient-to-b from-gray-50 via-white to-gray-50">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-red-100 text-red-700 rounded-full text-sm font-bold mb-6 uppercase tracking-wider">
            <Sparkles className="w-4 h-4" />
            Pre-built Agents
          </div>
          <h2 className="text-3xl sm:text-5xl font-black text-gray-900 mb-5 tracking-tight">
            Powerful AI Agents
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-red-600 to-rose-600">
              Ready to Deploy
            </span>
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
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
              <div key={i} className="bg-white rounded-3xl overflow-hidden shadow-sm hover:shadow-lg transition-shadow flex flex-col">
                <div className="bg-gradient-to-br from-red-100 via-pink-50 to-orange-50 pt-10 pb-12 flex items-center justify-center">
                  <div className="w-24 h-24 rounded-2xl bg-white shadow-lg flex items-center justify-center">
                    <Sparkles className="w-12 h-12 text-red-500" />
                  </div>
                </div>
                <div className="p-6 flex-1 flex flex-col">
                  <h3 className="text-lg font-bold text-gray-900 mb-1">{agent.name}</h3>
                  <p className="text-sm text-gray-400 mb-3">{agent.category}</p>
                  <p className="text-sm text-gray-600 leading-relaxed mb-4">{agent.description}</p>
                  <div className="border-t border-gray-100 pt-4 mt-auto flex items-center gap-6">
                    <div>
                      <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Uses</p>
                      <p className="text-xl font-bold text-gray-900">{formatNumber(agent.usage_count)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Likes</p>
                      <p className="text-xl font-bold text-gray-900">{agent.likes_count}</p>
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
            className="inline-flex items-center gap-3 px-10 py-5 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700 text-white text-lg font-bold rounded-2xl transition-all shadow-xl hover:shadow-2xl hover:shadow-red-500/30 hover:scale-105 group"
          >
            <span>Start Building Free</span>
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </Link>
        </div>
      </div>
    </section>
  )
}
