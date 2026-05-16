'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Image from 'next/image'
import {
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  Eye,
  Star,
  Zap,
  Brain,
  Bell,
  Loader2,
  CheckCircle,
  Sparkles,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { apiClient } from '@/lib/api/client'
import { getLLMConfigs } from '@/lib/api/agent-llm-configs'
import { subscribeToAgent } from '@/lib/api/subscriptions'
import type { AgentLLMConfig } from '@/types/agent-llm-config'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface PublicAgent {
  id: string
  agent_name: string
  slug: string
  description: string
  avatar?: string
  category: string
  tags: string[]
  likes_count: number
  dislikes_count: number
  usage_count: number
  model_name: string
  created_at: string
  user_rating?: 'like' | 'dislike' | null
  system_prompt?: string
  tools?: any[]
  provider?: string
  allow_subscriptions?: boolean
}

const getInitials = (name: string) =>
  name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

const getCategoryTone = (category: string) => {
  const tones: Record<
    string,
    {
      avatar: string
      badge: string
      icon: string
      soft: string
    }
  > = {
    Productivity: {
      avatar: 'bg-[linear-gradient(135deg,_#171717,_#434343)] text-[#f8f4ec]',
      badge: 'border-[#d8e5d9] bg-[#eef7f1] text-[#24543b]',
      icon: 'text-[#24543b]',
      soft: 'bg-[#eef7f1]',
    },
    Support: {
      avatar: 'bg-[linear-gradient(135deg,_#1f513d,_#2d8b69)] text-white',
      badge: 'border-[#d8e5d9] bg-[#eef7f1] text-[#24543b]',
      icon: 'text-[#24543b]',
      soft: 'bg-[#eef7f1]',
    },
    Engineering: {
      avatar: 'bg-[linear-gradient(135deg,_#2b3348,_#4d638d)] text-white',
      badge: 'border-[#d7e1ef] bg-[#eef4fb] text-[#345c8a]',
      icon: 'text-[#345c8a]',
      soft: 'bg-[#eef4fb]',
    },
    Sales: {
      avatar: 'bg-[linear-gradient(135deg,_#6a4020,_#b36a3b)] text-white',
      badge: 'border-[#f0d8bf] bg-[#fff5e7] text-[#9d6a1d]',
      icon: 'text-[#9d6a1d]',
      soft: 'bg-[#fff5e7]',
    },
    Marketing: {
      avatar: 'bg-[linear-gradient(135deg,_#7b3553,_#bf5f87)] text-white',
      badge: 'border-[#efd8dd] bg-[#fdf3f5] text-[#8a445c]',
      icon: 'text-[#8a445c]',
      soft: 'bg-[#fdf3f5]',
    },
    Research: {
      avatar: 'bg-[linear-gradient(135deg,_#2e2f22,_#6f714f)] text-white',
      badge: 'border-[#e6dfc6] bg-[#f7f4e8] text-[#6b6643]',
      icon: 'text-[#6b6643]',
      soft: 'bg-[#f7f4e8]',
    },
    Analytics: {
      avatar: 'bg-[linear-gradient(135deg,_#1e4050,_#3d738b)] text-white',
      badge: 'border-[#d7e1ef] bg-[#eef4fb] text-[#345c8a]',
      icon: 'text-[#345c8a]',
      soft: 'bg-[#eef4fb]',
    },
    Content: {
      avatar: 'bg-[linear-gradient(135deg,_#5e3d27,_#aa7a52)] text-white',
      badge: 'border-[#e6dccf] bg-[#f8f3eb] text-[#7c5d45]',
      icon: 'text-[#7c5d45]',
      soft: 'bg-[#f8f3eb]',
    },
  }

  return (
    tones[category] || {
      avatar: 'bg-[linear-gradient(135deg,_#171717,_#444444)] text-[#f8f4ec]',
      badge: 'border-[#e6dccf] bg-[#f8f3eb] text-[#7c5d45]',
      icon: 'text-[#7c5d45]',
      soft: 'bg-[#f8f3eb]',
    }
  )
}

export default function AgentDetailPage() {
  const router = useRouter()
  const params = useParams()
  const agentId = params.agentId as string

  const [agent, setAgent] = useState<PublicAgent | null>(null)
  const [defaultLLMConfig, setDefaultLLMConfig] = useState<AgentLLMConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [userId, setUserId] = useState<string | null>(null)
  const [showSubscribeForm, setShowSubscribeForm] = useState(false)
  const [subscribeEmail, setSubscribeEmail] = useState('')
  const [subscribeStatus, setSubscribeStatus] = useState<'idle' | 'loading' | 'success' | 'already_subscribed'>('idle')

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const user = await apiClient.getCurrentUser()
        setUserId(user.id)
      } catch (error) {
        console.error('Failed to fetch user:', error)
        setUserId(`session_${Date.now()}`)
      }
    }
    fetchUser()
  }, [])

  useEffect(() => {
    if (agentId && userId) {
      fetchAgentDetails()
    }
  }, [agentId, userId])

  const fetchAgentDetails = async () => {
    if (!userId) return

    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/v1/agents/public/${agentId}?user_id=${encodeURIComponent(userId)}`)
      const data = await response.json()
      if (data.success) {
        setAgent(data.data)

        try {
          const llmConfigs = await getLLMConfigs(data.data.id)
          const defaultConfig = llmConfigs.find((config) => config.is_default)
          setDefaultLLMConfig(defaultConfig || null)
        } catch (error) {
          console.error('Failed to fetch LLM configs:', error)
        }
      } else {
        toast.error('Failed to load agent details')
        router.push('/browse')
      }
    } catch (error) {
      console.error('Failed to fetch agent details:', error)
      toast.error('Failed to load agent details')
      router.push('/browse')
    } finally {
      setLoading(false)
    }
  }

  const handleRating = async (rating: 'like' | 'dislike') => {
    if (!agent || !userId) return

    try {
      const response = await fetch(`${API_URL}/api/v1/agents/public/${agent.id}/rate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, rating }),
      })

      const data = await response.json()
      if (data.success) {
        toast.success(`Agent ${rating}d!`)
        fetchAgentDetails()
      }
    } catch (error) {
      console.error('Failed to rate agent:', error)
      toast.error('Failed to rate agent')
    }
  }

  const handleSubscribe = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!agent || !subscribeEmail.trim()) return
    try {
      setSubscribeStatus('loading')
      const result = await subscribeToAgent(agent.id, subscribeEmail.trim())
      if (result.message === 'Already subscribed') {
        setSubscribeStatus('already_subscribed')
      } else {
        setSubscribeStatus('success')
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to subscribe')
      setSubscribeStatus('idle')
    }
  }

  const getRatingPercentage = () => {
    if (!agent) return 0
    const total = agent.likes_count + agent.dislikes_count
    if (total === 0) return 0
    return Math.round((agent.likes_count / total) * 100)
  }

  if (loading) {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-14 w-14 animate-spin rounded-full border-4 border-[#171717] border-t-transparent"></div>
          <p className="mt-4 text-sm font-medium text-gray-600">Loading agent details...</p>
        </div>
      </div>
    )
  }

  if (!agent) {
    return null
  }

  const categoryTone = getCategoryTone(agent.category)

  return (
    <>
      <DashboardPageShell
        title={agent.agent_name}
        description={agent.description || 'A powerful AI agent ready to assist you with various tasks.'}
        icon={Sparkles}
        badge="Agent Discovery"
        maxWidthClassName="max-w-7xl"
        breadcrumbs={[
          { label: 'Home', href: '/' },
          { label: 'Browse', href: '/browse' },
          { label: agent.agent_name },
        ]}
        stats={[
          { label: 'Uses', value: agent.usage_count.toLocaleString() },
          { label: 'Positive', value: `${getRatingPercentage()}%` },
          { label: 'Category', value: agent.category },
        ]}
        actions={
          <>
            <button
              onClick={() => router.push(`/agents/${agent.slug}/chat`)}
              className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
            >
              <MessageSquare className="h-4 w-4" />
              Start Chat
            </button>
            {agent.allow_subscriptions ? (
              <button
                onClick={() => setShowSubscribeForm(true)}
                className="inline-flex items-center gap-2 rounded-[1rem] border border-[#e5d9ca] bg-white/85 px-4 py-3 text-sm font-semibold text-gray-700 transition-colors hover:bg-white hover:text-[#171717]"
              >
                <Bell className="h-4 w-4" />
                Subscribe
              </button>
            ) : null}
          </>
        }
      >
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_330px]">
          <div className="space-y-6">
            <DashboardPagePanel className="p-5 md:p-6">
              <div className="flex flex-col gap-5 md:flex-row">
                <div className={`relative flex h-28 w-28 flex-shrink-0 items-center justify-center overflow-hidden rounded-[1.9rem] text-2xl font-semibold shadow-[0_24px_45px_-30px_rgba(0,0,0,0.35)] ${categoryTone.avatar}`}>
                  {agent.avatar ? (
                    agent.avatar.startsWith('http://') || agent.avatar.startsWith('https://') ? (
                      <img
                        src={agent.avatar}
                        alt={agent.agent_name}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <Image
                        src={agent.avatar}
                        alt={agent.agent_name}
                        fill
                        className="object-cover"
                      />
                    )
                  ) : (
                    getInitials(agent.agent_name)
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${categoryTone.badge}`}>
                      {agent.category}
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-full border border-[#e6dccf] bg-white/80 px-3 py-1 text-xs font-medium text-gray-600">
                      <Eye className="h-3.5 w-3.5" />
                      {agent.usage_count} uses
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-full border border-[#e6dccf] bg-white/80 px-3 py-1 text-xs font-medium text-gray-600">
                      <ThumbsUp className="h-3.5 w-3.5" />
                      {agent.likes_count} likes
                    </span>
                  </div>

                  <p className="text-sm leading-7 text-gray-600">
                    {agent.description || 'A powerful AI agent ready to assist you with various tasks.'}
                  </p>

                  {agent.tags && agent.tags.length > 0 ? (
                    <div className="mt-5 flex flex-wrap gap-2">
                      {agent.tags.map((tag, idx) => (
                        <span
                          key={idx}
                          className="rounded-full border border-[#e6dccf] bg-[#fcfaf5] px-3 py-1.5 text-xs font-semibold text-[#7c5d45]"
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </DashboardPagePanel>

            {agent.description ? (
              <DashboardPagePanel className="p-5 md:p-6">
                <div className="mb-4 flex items-center gap-3">
                  <div className={`rounded-[1rem] p-2.5 ${categoryTone.soft}`}>
                    <Zap className={`h-4 w-4 ${categoryTone.icon}`} />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold tracking-[-0.03em] text-gray-950">Tools & Capabilities</h2>
                    <p className="text-sm text-gray-500">What this agent is designed to help with.</p>
                  </div>
                </div>
                <p className="text-sm leading-7 text-gray-700">{agent.description}</p>
              </DashboardPagePanel>
            ) : null}
          </div>

          <div className="space-y-5">
            <DashboardPagePanel className="p-5">
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#eef4fb] p-2.5">
                  <Brain className="h-4 w-4 text-[#345c8a]" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-gray-950">Model Configuration</h2>
                  <p className="text-xs text-gray-500">Current default runtime settings.</p>
                </div>
              </div>

              <div className="space-y-3">
                {defaultLLMConfig ? (
                  <>
                    <div className="rounded-[1rem] border border-[#e6dccf] bg-[#fcfaf5] px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9a7a5e]">Provider</p>
                      <p className="mt-1 text-sm font-semibold capitalize text-gray-900">{defaultLLMConfig.provider}</p>
                    </div>
                    <div className="rounded-[1rem] border border-[#e6dccf] bg-[#fcfaf5] px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9a7a5e]">Model</p>
                      <p className="mt-1 text-sm font-semibold text-gray-900">{defaultLLMConfig.model_name}</p>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                      <div className="rounded-[1rem] border border-[#e6dccf] bg-[#fcfaf5] px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9a7a5e]">Temperature</p>
                        <p className="mt-1 text-sm font-semibold text-gray-900">{defaultLLMConfig.temperature}</p>
                      </div>
                      <div className="rounded-[1rem] border border-[#e6dccf] bg-[#fcfaf5] px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9a7a5e]">Max Tokens</p>
                        <p className="mt-1 text-sm font-semibold text-gray-900">{defaultLLMConfig.max_tokens || 'Auto'}</p>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="rounded-[1rem] border border-dashed border-[#ddcfbc] bg-[#fcfaf5] px-4 py-4 text-sm text-[#8c6b4d]">
                    No LLM configuration available.
                  </div>
                )}

                <div className="rounded-[1rem] border border-[#e6dccf] bg-[#f8f3eb] px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9a7a5e]">Created</p>
                  <p className="mt-1 text-sm font-semibold text-gray-900">
                    {new Date(agent.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            </DashboardPagePanel>

            <DashboardPagePanel className="p-5">
              <h2 className="text-base font-semibold text-gray-950">Rate This Agent</h2>
              <p className="mt-1 text-xs text-gray-500">Share quick feedback with one tap.</p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <button
                  onClick={() => handleRating('like')}
                  className={`inline-flex items-center justify-center gap-2 rounded-[1rem] px-4 py-3 text-sm font-semibold transition-colors ${
                    agent.user_rating === 'like'
                      ? 'border border-[#cfe5d7] bg-[#edf7f1] text-[#24543b]'
                      : 'border border-[#e6dccf] bg-white/85 text-gray-700 hover:bg-[#eef7f1] hover:text-[#24543b]'
                  }`}
                >
                  <ThumbsUp className="h-4 w-4" />
                  Like
                </button>
                <button
                  onClick={() => handleRating('dislike')}
                  className={`inline-flex items-center justify-center gap-2 rounded-[1rem] px-4 py-3 text-sm font-semibold transition-colors ${
                    agent.user_rating === 'dislike'
                      ? 'border border-[#efd8dd] bg-[#fdf3f5] text-[#8a445c]'
                      : 'border border-[#e6dccf] bg-white/85 text-gray-700 hover:bg-[#fdf3f5] hover:text-[#8a445c]'
                  }`}
                >
                  <ThumbsDown className="h-4 w-4" />
                  Dislike
                </button>
              </div>
            </DashboardPagePanel>

            <DashboardPagePanel className="p-5">
              <h2 className="text-base font-semibold text-gray-950">Statistics</h2>
              <div className="mt-4 space-y-3">
                <div className="flex items-center justify-between rounded-[1rem] border border-[#e6dccf] bg-[#fcfaf5] px-4 py-3">
                  <span className="text-sm text-gray-600">Total Uses</span>
                  <span className="text-sm font-semibold text-gray-950">{agent.usage_count}</span>
                </div>
                <div className="flex items-center justify-between rounded-[1rem] border border-[#e6dccf] bg-[#eef7f1] px-4 py-3">
                  <span className="text-sm text-[#24543b]">Likes</span>
                  <span className="text-sm font-semibold text-[#24543b]">{agent.likes_count}</span>
                </div>
                <div className="flex items-center justify-between rounded-[1rem] border border-[#e6dccf] bg-[#fdf3f5] px-4 py-3">
                  <span className="text-sm text-[#8a445c]">Dislikes</span>
                  <span className="text-sm font-semibold text-[#8a445c]">{agent.dislikes_count}</span>
                </div>
                <div className="rounded-[1rem] border border-[#e6dccf] bg-[#f8f3eb] px-4 py-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-700">
                      <Star className="h-4 w-4 text-[#9d6a1d]" />
                      Rating
                    </span>
                    <span className="text-sm font-semibold text-gray-950">{getRatingPercentage()}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[#e8dece]">
                    <div
                      className="h-full rounded-full bg-[linear-gradient(90deg,_#171717,_#2d8b69)]"
                      style={{ width: `${getRatingPercentage()}%` }}
                    />
                  </div>
                </div>
              </div>
            </DashboardPagePanel>
          </div>
        </div>
      </DashboardPageShell>

      {showSubscribeForm ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[2rem] border border-[#e6dccf] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] p-6 shadow-[0_32px_90px_-45px_rgba(0,0,0,0.45)]">
            {subscribeStatus === 'success' ? (
              <div className="py-4 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#edf7f1]">
                  <CheckCircle className="h-7 w-7 text-[#2b7a52]" />
                </div>
                <h3 className="text-lg font-semibold text-gray-950">You&apos;re subscribed!</h3>
                <p className="mt-2 text-sm leading-6 text-gray-600">
                  You&apos;ll receive reports from <span className="font-semibold text-gray-900">{agent.agent_name}</span> in your inbox.
                </p>
                <button
                  onClick={() => {
                    setShowSubscribeForm(false)
                    setSubscribeStatus('idle')
                    setSubscribeEmail('')
                  }}
                  className="mt-5 inline-flex rounded-[1rem] border border-[#e6dccf] bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 transition-colors hover:bg-[#fcfaf5]"
                >
                  Close
                </button>
              </div>
            ) : subscribeStatus === 'already_subscribed' ? (
              <div className="py-4 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#fff5e7]">
                  <Bell className="h-7 w-7 text-[#9d6a1d]" />
                </div>
                <h3 className="text-lg font-semibold text-gray-950">Already subscribed</h3>
                <p className="mt-2 text-sm leading-6 text-gray-600">
                  <span className="font-semibold text-gray-900">{subscribeEmail}</span> is already subscribed to this agent&apos;s reports.
                </p>
                <button
                  onClick={() => {
                    setShowSubscribeForm(false)
                    setSubscribeStatus('idle')
                    setSubscribeEmail('')
                  }}
                  className="mt-5 inline-flex rounded-[1rem] border border-[#e6dccf] bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 transition-colors hover:bg-[#fcfaf5]"
                >
                  Close
                </button>
              </div>
            ) : (
              <>
                <div className="mb-5 flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="rounded-[1rem] bg-[#fff5e7] p-3">
                      <Bell className="h-5 w-5 text-[#9d6a1d]" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-950">Subscribe to reports</h3>
                      <p className="mt-1 text-sm text-gray-500">{agent.agent_name}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      setShowSubscribeForm(false)
                      setSubscribeEmail('')
                    }}
                    className="text-2xl leading-none text-gray-400 transition-colors hover:text-gray-700"
                  >
                    ×
                  </button>
                </div>

                <p className="mb-4 text-sm leading-6 text-gray-600">
                  Get this agent&apos;s scheduled reports delivered to your inbox automatically.
                </p>

                <form onSubmit={handleSubscribe} className="space-y-4">
                  <input
                    type="email"
                    required
                    autoFocus
                    value={subscribeEmail}
                    onChange={(e) => setSubscribeEmail(e.target.value)}
                    placeholder="your@email.com"
                    className="w-full rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-4 py-3.5 text-sm text-gray-900 placeholder-gray-400 outline-none transition focus:border-[#79dfbc] focus:ring-4 focus:ring-[#79dfbc]/20"
                  />

                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        setShowSubscribeForm(false)
                        setSubscribeEmail('')
                      }}
                      className="flex-1 rounded-[1rem] border border-[#e6dccf] bg-white px-4 py-3 text-sm font-semibold text-gray-700 transition-colors hover:bg-[#fcfaf5]"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={subscribeStatus === 'loading'}
                      className="flex flex-1 items-center justify-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-60"
                    >
                      {subscribeStatus === 'loading' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}
                      {subscribeStatus === 'loading' ? 'Subscribing...' : 'Subscribe'}
                    </button>
                  </div>

                  <p className="text-center text-xs text-gray-400">
                    You can unsubscribe anytime via the link in emails.
                  </p>
                </form>
              </>
            )}
          </div>
        </div>
      ) : null}
    </>
  )
}
