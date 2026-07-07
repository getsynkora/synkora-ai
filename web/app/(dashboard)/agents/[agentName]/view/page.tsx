'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Image from 'next/image'
import toast from 'react-hot-toast'
import {
  Edit,
  Trash2,
  MessageSquare,
  Activity,
  Settings,
  Mic,
  Database,
  Zap,
  Code,
  MessageCircle,
  Sparkles,
  Clock,
  CheckCircle,
  XCircle,
  TrendingUp,
  Calendar,
  Box,
  Key,
  Users,
  Webhook,
  ChevronDown,
  Globe,
  Cpu,
  Bell,
  Bot,
  Server,
  DollarSign,
  BarChart2,
  Phone,
  X,
  MicOff,
  PhoneOff,
  Video,
  Copy,
  Maximize2,
  Check,
} from 'lucide-react'
import { createPortal } from 'react-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { apiClient } from '@/lib/api/client'
import { getLLMConfigs } from '@/lib/api/agent-llm-configs'
import { getLensOverview, type LensOverviewResponse } from '@/lib/api/agent-lens'
import { getVoiceMeetingsConfig, getWebCallToken } from '@/lib/api/voice-meetings'
import type { AgentLLMConfig } from '@/types/agent-llm-config'

interface AgentDetails {
  id: string
  agent_name: string
  agent_type: string
  description: string
  avatar?: string
  system_prompt: string
  llm_config: {
    provider: string
    model: string
    temperature: number
    max_tokens?: number
  }
  tools_config?: {
    tools: Array<{
      name: string
      description: string
      enabled: boolean
    }>
  }
  status: string
  allow_subscriptions?: boolean
  created_at: string
  updated_at: string
  stats?: {
    total_executions: number
    successful_executions: number
    failed_executions: number
    average_execution_time: number
  }
}

function SystemPromptModal({
  prompt,
  agentName,
  isOpen,
  onClose,
}: {
  prompt: string
  agentName: string
  isOpen: boolean
  onClose: () => void
}) {
  const [copied, setCopied] = useState(false)
  const [mounted, setMounted] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const wordCount = prompt.trim().split(/\s+/).filter(Boolean).length

  useEffect(() => {
    setMounted(true)
    return () => setMounted(false)
  }, [])

  useEffect(() => {
    if (!isOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      document.removeEventListener('keydown', onKey)
    }
  }, [isOpen, onClose])

  const handleCopy = () => {
    navigator.clipboard.writeText(prompt)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!mounted || !isOpen) return null

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-end justify-center p-4 sm:items-center"
      aria-modal="true"
      role="dialog"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"
        onClick={onClose}
      />

      {/* Sheet */}
      <div className="relative flex w-full max-w-2xl flex-col overflow-hidden rounded-[1.75rem] bg-white shadow-[0_32px_64px_-12px_rgba(0,0,0,0.25)] ring-1 ring-black/[0.06]"
           style={{ maxHeight: 'min(82vh, 700px)' }}>

        {/* Top accent bar */}
        <div className="h-1 w-full bg-gradient-to-r from-[#ffb347] via-[#ff5f8f] to-[#c471f5]" />

        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#fff0d9] to-[#ffe1cc]">
            <MessageSquare className="h-4 w-4 text-[#c47a35]" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-[0.95rem] font-semibold text-[#171717]">System Prompt</h3>
            <p className="text-[11px] text-[#9c9086]">{wordCount.toLocaleString()} words</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 rounded-[0.8rem] bg-[#f6f0e8] px-3.5 py-2 text-[12px] font-medium text-[#464038] transition-all hover:bg-[#ede4d8] active:scale-95"
            >
              {copied
                ? <><Check className="h-3.5 w-3.5 text-emerald-600" /><span className="text-emerald-700">Copied</span></>
                : <><Copy className="h-3.5 w-3.5" /><span>Copy</span></>}
            </button>
            <button
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-full text-[#9c9086] transition-all hover:bg-[#f1eadc] hover:text-[#464038] active:scale-95"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Divider */}
        <div className="mx-6 h-px bg-black/[0.06]" />

        {/* Body */}
        <div ref={scrollRef} className="overflow-y-auto px-6 py-5 overscroll-contain">
          <div className="text-[13.5px] leading-[1.75] text-[#3d3830]">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => <h1 className="mb-3 mt-6 text-[1.15rem] font-bold tracking-tight text-[#171717] first:mt-0">{children}</h1>,
                h2: ({ children }) => <h2 className="mb-2 mt-5 text-[1rem] font-semibold text-[#171717] first:mt-0">{children}</h2>,
                h3: ({ children }) => <h3 className="mb-2 mt-4 text-[0.9rem] font-semibold text-[#464038] first:mt-0">{children}</h3>,
                p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
                ul: ({ children }) => <ul className="mb-3 ml-5 list-disc space-y-1">{children}</ul>,
                ol: ({ children }) => <ol className="mb-3 ml-5 list-decimal space-y-1">{children}</ol>,
                li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                code: ({ inline, children }: { inline?: boolean; children?: React.ReactNode }) =>
                  inline ? (
                    <code className="rounded-md bg-[#f3ede4] px-1.5 py-0.5 font-mono text-[12px] text-[#a0522d]">{children}</code>
                  ) : (
                    <code className="text-[12px]">{children}</code>
                  ),
                pre: ({ children }) => (
                  <pre className="mb-3 overflow-x-auto rounded-[1rem] border border-black/[0.06] bg-[#faf6f0] p-4 font-mono text-[12px] leading-relaxed">
                    {children}
                  </pre>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="mb-3 rounded-r-lg border-l-[3px] border-[#ffb347] bg-[#fff8ee] px-4 py-2 text-[#6c5c40] italic">
                    {children}
                  </blockquote>
                ),
                strong: ({ children }) => <strong className="font-semibold text-[#171717]">{children}</strong>,
                em: ({ children }) => <em className="text-[#5a5248]">{children}</em>,
                hr: () => <hr className="my-5 border-black/[0.07]" />,
                a: ({ href, children }) => (
                  <a href={href} className="text-[#c47a35] underline decoration-[#ffb347]/60 underline-offset-2 hover:decoration-[#c47a35]" target="_blank" rel="noreferrer">
                    {children}
                  </a>
                ),
              }}
            >
              {prompt}
            </ReactMarkdown>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-black/[0.06] bg-[#fdfaf7] px-6 py-3">
          <p className="text-[11px] text-[#b0a898]">{prompt.length.toLocaleString()} characters</p>
          <button
            onClick={() => window.location.assign(`/agents/${agentName}/edit`)}
            className="flex items-center gap-1.5 rounded-[0.8rem] bg-[#171717] px-4 py-2 text-[12px] font-medium text-white transition-all hover:bg-[#2a2a2a] active:scale-95"
          >
            <Edit className="h-3.5 w-3.5" />
            Edit Prompt
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

export default function AgentViewPage() {
  const params = useParams()
  const router = useRouter()
  const agentName = params.agentName as string
  
  const [agent, setAgent] = useState<AgentDetails | null>(null)
  const [defaultLLMConfig, setDefaultLLMConfig] = useState<AgentLLMConfig | null>(null)
  const [lensStats, setLensStats] = useState<LensOverviewResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [showMoreActions, setShowMoreActions] = useState(false)
  const [publicSlug, setPublicSlug] = useState<string | null>(null)
  const [webCallEnabled, setWebCallEnabled] = useState(false)
  const [showCallModal, setShowCallModal] = useState(false)
  const [vapiPublicKey, setVapiPublicKey] = useState<string | null>(null)
  const [callActive, setCallActive] = useState(false)
  const [vapiInstance, setVapiInstance] = useState<any>(null)
  const [showPromptModal, setShowPromptModal] = useState(false)
  const [promptCopied, setPromptCopied] = useState(false)

  useEffect(() => {
    fetchAgentDetails()
  }, [agentName])

  const fetchAgentDetails = async () => {
    try {
      setLoading(true)

      // Step 1: fetch agent (need its ID for getLLMConfigs)
      const data = await apiClient.getAgent(agentName)
      setAgent(data)

      // Step 2: everything that can run in parallel
      const [llmConfigs] = await Promise.all([
        data.id ? getLLMConfigs(data.id) : Promise.resolve([]),
        // Public profile — only needs agentName, ignore failure
        apiClient.request('GET', `/api/v1/agents/${agentName}/public-profile`)
          .then((r: { profile?: { is_published?: boolean; slug?: string } }) => {
            if (r?.profile?.is_published && r.profile.slug) setPublicSlug(r.profile.slug)
          })
          .catch(() => {}),
        // Lens stats — only needs agentName, ignore failure
        getLensOverview(agentName, '30d')
          .then(setLensStats)
          .catch(() => {}),
        // Voice & Meetings config — show Call Agent button if web_call enabled
        getVoiceMeetingsConfig(agentName)
          .then((cfg) => {
            if (cfg?.web_call?.enabled && cfg?.web_call?.show_on_agent_card) {
              setWebCallEnabled(true)
              setVapiPublicKey(cfg.web_call.vapi_public_key ?? null)
            }
          })
          .catch(() => {}),
      ])

      const defaultConfig = llmConfigs.find((c: { is_default: boolean }) => c.is_default)
      setDefaultLLMConfig(defaultConfig ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to delete agent "${agentName}"?`)) {
      return
    }

    try {
      setDeleting(true)
      await apiClient.deleteAgent(agentName)
      toast.success('Agent deleted successfully!')
      router.push('/agents')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete agent')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
        <div className="mx-auto flex min-h-[70vh] max-w-[90rem] items-center justify-center">
          <div className="dashboard-surface px-10 py-12 text-center">
          <div className="relative">
              <div className="mx-auto h-14 w-14 animate-spin rounded-full border-[3px] border-black/10 border-t-[#181818]"></div>
              <Sparkles className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 text-[#ff5f8f]" />
          </div>
            <p className="mt-5 text-[14px] font-medium text-[#5b564e]">Loading agent details...</p>
          </div>
        </div>
      </div>
    )
  }

  if (error || !agent) {
    return (
      <div className="min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
        <div className="mx-auto flex min-h-[70vh] max-w-[90rem] items-center justify-center">
          <div className="dashboard-surface w-full max-w-md p-8 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-[0.35rem] bg-[#ffe1ea]">
              <XCircle className="h-7 w-7 text-red-600" />
          </div>
            <h3 className="mb-2 text-[1.15rem] font-semibold text-[#171717]">Error Loading Agent</h3>
            <p className="mb-6 text-[14px] text-[#5b564e]">{error || 'Agent not found'}</p>
            <button
              onClick={() => router.push('/agents')}
              className="rounded-[0.35rem] bg-[#181818] px-6 py-3 text-[14px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5"
            >
              Back to Agents
            </button>
          </div>
        </div>
      </div>
    )
  }

  const successRate = lensStats
    ? Math.round((1 - lensStats.stats.failure_rate) * 100)
    : 0

  return (
    <>
    <div className="min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
      <div className="mx-auto max-w-[90rem]">
        <div className="dashboard-surface mb-6 p-5 md:p-6 xl:p-7">
          <div className="mb-6 flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 flex-1">
              <div className="mb-3 inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/70 px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6e675d]">
                <Sparkles className="h-3 w-3 text-[#ff5f8f]" />
                Agent Detail
              </div>
              <div className="flex items-start gap-4">
                <div className="relative flex h-16 w-16 flex-shrink-0 items-center justify-center overflow-hidden rounded-[0.45rem] border border-white/80 bg-[#faf7f0] shadow-[0_18px_40px_rgba(0,0,0,0.06)]">
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
                    <Bot className="h-7 w-7 text-[#181818]" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <h1 className="text-[1.8rem] font-semibold tracking-[-0.05em] text-[#171717] md:text-[2.65rem]">
                    {agent.agent_name}
                  </h1>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className={`inline-flex items-center rounded-[0.35rem] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                      agent.status === 'active'
                        ? 'bg-[#def4eb] text-[#171717]'
                        : 'bg-white/70 text-[#5b564e] border border-black/[0.08]'
                    }`}>
                      <span className={`mr-1.5 h-1.5 w-1.5 rounded-full ${
                        agent.status === 'active' ? 'bg-[#2d8b69]' : 'bg-[#8a8378]'
                      }`}></span>
                      {agent.status}
                    </span>
                    <span className="dashboard-chip px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]">
                      {agent.agent_type}
                    </span>
                    <span className="dashboard-chip px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]">
                      Updated {new Date(agent.updated_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                      })}
                    </span>
                  </div>
                  <p className="mt-3 max-w-4xl text-[13px] leading-relaxed text-[#5b564e] md:text-[15px]">
                    {agent.description}
                  </p>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 xl:justify-end">
              <button
                onClick={() => router.push(`/agents/${agentName}/edit`)}
                className="inline-flex items-center gap-2 rounded-[0.35rem] bg-[#181818] px-5 py-3 text-[13px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 md:text-[14px]"
              >
                <Edit className="h-4 w-4" />
                Edit
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="inline-flex items-center gap-2 rounded-[0.35rem] bg-[#ffe1ea] px-5 py-3 text-[13px] font-medium text-[#171717] transition-colors hover:bg-[#ffd5e2] disabled:opacity-50 md:text-[14px]"
              >
                <Trash2 className="h-4 w-4" />
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => router.push(`/agents/${agentName}/chat`)}
              className="inline-flex items-center gap-2 rounded-[0.35rem] bg-[#181818] px-5 py-3 text-[13px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 md:text-[14px]"
            >
              <MessageSquare className="h-4 w-4" />
              Chat
            </button>

            {webCallEnabled && (
              <button
                onClick={() => setShowCallModal(true)}
                className="inline-flex items-center gap-2 rounded-[0.35rem] bg-green-600 px-5 py-3 text-[13px] font-medium text-white transition-transform hover:-translate-y-0.5 md:text-[14px]"
              >
                <Phone className="h-4 w-4" />
                Call Agent
              </button>
            )}

            <button
              onClick={() => router.push(`/agents/${agentName}/landing-page`)}
              className="inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/[0.72] px-4 py-3 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white md:text-[14px]"
            >
              <Globe className="h-4 w-4 text-[#ff5f8f]" />
              Landing Page
            </button>

            {publicSlug && (
              <a
                href={`/a/${publicSlug}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/[0.72] px-4 py-3 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white md:text-[14px]"
              >
                <DollarSign className="h-4 w-4 text-[#d9a441]" />
                View Public Page
              </a>
            )}

            <button
              onClick={() => router.push(`/agents/${agentName}/knowledge-bases`)}
              className="inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/[0.72] px-4 py-3 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white md:text-[14px]"
            >
              <Database className="h-4 w-4 text-[#7d68c9]" />
              Knowledge
            </button>

            <button
              onClick={() => router.push(`/agents/${agentName}/tools`)}
              className="inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/[0.72] px-4 py-3 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white md:text-[14px]"
            >
              <Settings className="h-4 w-4 text-[#2d8b69]" />
              Tools
            </button>

            <button
              onClick={() => router.push(`/agents/${agentName}/llm-configs`)}
              className="inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/[0.72] px-4 py-3 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white md:text-[14px]"
            >
              <Cpu className="h-4 w-4 text-[#4a67cc]" />
              AI Model
            </button>

            <button
              onClick={() => router.push(`/agents/${agentName}/autonomous`)}
              className="inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/[0.72] px-4 py-3 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white md:text-[14px]"
            >
              <Bot className="h-4 w-4 text-[#ff5f8f]" />
              Autonomous
            </button>

            <button
              onClick={() => setShowMoreActions(!showMoreActions)}
              className="inline-flex items-center gap-1.5 rounded-[0.35rem] border border-black/10 bg-white/[0.72] px-4 py-3 text-[13px] font-medium text-[#5b564e] transition-colors hover:bg-white hover:text-[#171717] md:text-[14px]"
            >
              More
              <ChevronDown className={`h-4 w-4 transition-transform ${showMoreActions ? 'rotate-180' : ''}`} />
            </button>
          </div>

          {showMoreActions && (
            <div className="dashboard-panel mt-5 p-4 md:p-5">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                {/* Integrations */}
                <div>
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8a8378]">Integrations</p>
                  <div className="space-y-1">
                    <button
                      onClick={() => router.push(`/agents/${agentName}/slack-bots`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none">
                        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#E01E5A"/>
                      </svg>
                      Slack
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/messaging-bots`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <MessageCircle className="w-4 h-4 text-green-600" />
                      Messaging Bots
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/telegram-bots`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="#0088cc">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
                      </svg>
                      Telegram
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/webhooks`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Webhook className="w-4 h-4 text-teal-600" />
                      Webhooks
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/database-connections`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Database className="w-4 h-4 text-blue-600" />
                      Database Connections
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/compute`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Server className="w-4 h-4 text-violet-600" />
                      Compute
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/voice-meetings`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Mic className="w-4 h-4 text-cyan-600" />
                      Voice & Meetings
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/meetings`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Video className="w-4 h-4 text-cyan-600" />
                      Meetings
                    </button>
                  </div>
                </div>

                {/* Deployment */}
                <div>
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8a8378]">Deployment</p>
                  <div className="space-y-1">
                    <button
                      onClick={() => router.push(`/agents/${agentName}/widgets`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Code className="w-4 h-4 text-orange-600" />
                      Widgets
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/domains`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Globe className="w-4 h-4 text-blue-600" />
                      Domains
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/api-keys`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Key className="w-4 h-4 text-amber-600" />
                      API Keys
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/subscriptions`)}
                      className="flex w-full items-center gap-2 rounded-[0.35rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Bell className="w-4 h-4 text-red-500" />
                      Subscriptions
                    </button>
                  </div>
                </div>

                {/* Advanced */}
                <div>
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8a8378]">Advanced</p>
                  <div className="space-y-1">
                    <button
                      onClick={() => router.push(`/agents/${agentName}/autonomous`)}
                      className="flex w-full items-center gap-2 rounded-[1rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Bot className="w-4 h-4 text-red-600" />
                      Autonomous Mode
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/sub-agents`)}
                      className="flex w-full items-center gap-2 rounded-[1rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Users className="w-4 h-4 text-rose-600" />
                      Sub-Agents
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/mcp-servers`)}
                      className="flex w-full items-center gap-2 rounded-[1rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Zap className="w-4 h-4 text-indigo-600" />
                      MCP Servers
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/outputs`)}
                      className="flex w-full items-center gap-2 rounded-[1rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Activity className="w-4 h-4 text-sky-600" />
                      Outputs
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/chat-customization`)}
                      className="flex w-full items-center gap-2 rounded-[1rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <Sparkles className="w-4 h-4 text-violet-600" />
                      Customize Chat
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/lens`)}
                      className="flex w-full items-center gap-2 rounded-[1rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <BarChart2 className="w-4 h-4 text-indigo-600" />
                      Lens
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/handoffs`)}
                      className="flex w-full items-center gap-2 rounded-[1rem] px-3 py-2 text-[13px] text-[#171717] transition-colors hover:bg-white/60"
                    >
                      <MessageCircle className="w-4 h-4 text-amber-600" />
                      Handoffs
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Stats Cards — sourced from Elasticsearch via Lens API (last 30 days) */}
        <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="dashboard-panel p-5 transition-all duration-300 hover:-translate-y-1">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#ffe1ea]">
                <Activity className="h-4 w-4 text-[#171717]" />
              </div>
              <TrendingUp className="h-4 w-4 text-[#8a8378]" />
            </div>
            <p className="mb-1 text-[13px] font-medium text-[#6c655c]">Sessions (30d)</p>
            <p className="text-[1.65rem] font-semibold tracking-[-0.04em] text-[#171717]">
              {lensStats ? lensStats.stats.total_sessions.toLocaleString() : '—'}
            </p>
          </div>

          <div className="dashboard-panel p-5 transition-all duration-300 hover:-translate-y-1">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#def4eb]">
                <CheckCircle className="h-4 w-4 text-[#171717]" />
              </div>
              {lensStats && (
                <span className={`rounded-[0.35rem] px-2.5 py-1 text-[11px] font-semibold ${
                  successRate >= 90 ? 'bg-[#def4eb] text-[#171717]' : successRate >= 70 ? 'bg-[#fff0d9] text-[#171717]' : 'bg-[#ffe1ea] text-[#171717]'
                }`}>
                  {successRate}%
                </span>
              )}
            </div>
            <p className="mb-1 text-[13px] font-medium text-[#6c655c]">Success Rate</p>
            <p className="text-[1.65rem] font-semibold tracking-[-0.04em] text-[#171717]">
              {lensStats ? `${successRate}%` : '—'}
            </p>
          </div>

          <div className="dashboard-panel p-5 transition-all duration-300 hover:-translate-y-1">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#fff0d9]">
                <Clock className="h-4 w-4 text-[#171717]" />
              </div>
            </div>
            <p className="mb-1 text-[13px] font-medium text-[#6c655c]">Avg. Latency</p>
            <p className="text-[1.65rem] font-semibold tracking-[-0.04em] text-[#171717]">
              {lensStats
                ? lensStats.stats.avg_latency_ms >= 1000
                  ? `${(lensStats.stats.avg_latency_ms / 1000).toFixed(1)}s`
                  : `${Math.round(lensStats.stats.avg_latency_ms)}ms`
                : '—'}
            </p>
          </div>

          <div className="dashboard-panel p-5 transition-all duration-300 hover:-translate-y-1">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#f0f9ff]">
                <DollarSign className="h-4 w-4 text-[#171717]" />
              </div>
            </div>
            <p className="mb-1 text-[13px] font-medium text-[#6c655c]">Total Cost (30d)</p>
            <p className="text-[1.65rem] font-semibold tracking-[-0.04em] text-[#171717]">
              {lensStats
                ? lensStats.stats.total_cost_usd === 0
                  ? '$0.00'
                  : lensStats.stats.total_cost_usd < 0.01
                    ? `$${lensStats.stats.total_cost_usd.toFixed(4)}`
                    : `$${lensStats.stats.total_cost_usd.toFixed(2)}`
                : '—'}
            </p>
          </div>
        </div>

        {/* Secondary stats row */}
        {lensStats && (lensStats.stats.total_tokens > 0 || lensStats.stats.total_tool_calls > 0) && (
          <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="dashboard-panel p-5">
              <div className="mb-2 flex items-center gap-2">
                <BarChart2 className="h-4 w-4 text-[#4a67cc]" />
                <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[#8a8378]">Tokens Used</p>
              </div>
              <p className="text-[1.4rem] font-semibold tracking-[-0.03em] text-[#171717]">
                {lensStats.stats.total_tokens >= 1_000_000
                  ? `${(lensStats.stats.total_tokens / 1_000_000).toFixed(1)}M`
                  : lensStats.stats.total_tokens >= 1_000
                    ? `${(lensStats.stats.total_tokens / 1_000).toFixed(1)}K`
                    : lensStats.stats.total_tokens.toLocaleString()}
              </p>
              <p className="mt-1 text-[11px] text-[#8a8378]">
                {lensStats.stats.input_tokens.toLocaleString()} in · {lensStats.stats.output_tokens.toLocaleString()} out
              </p>
            </div>
            <div className="dashboard-panel p-5">
              <div className="mb-2 flex items-center gap-2">
                <Zap className="h-4 w-4 text-[#d9a441]" />
                <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[#8a8378]">Tool Calls</p>
              </div>
              <p className="text-[1.4rem] font-semibold tracking-[-0.03em] text-[#171717]">
                {lensStats.stats.total_tool_calls.toLocaleString()}
              </p>
              <p className="mt-1 text-[11px] text-[#8a8378]">
                {lensStats.stats.failed_tool_calls > 0
                  ? `${lensStats.stats.failed_tool_calls} failed`
                  : 'all successful'}
              </p>
            </div>
            <div className="dashboard-panel p-5">
              <div className="mb-2 flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-[#2d8b69]" />
                <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[#8a8378]">Cost per Session</p>
              </div>
              <p className="text-[1.4rem] font-semibold tracking-[-0.03em] text-[#171717]">
                {lensStats.stats.avg_cost_per_session === 0
                  ? '$0.00'
                  : lensStats.stats.avg_cost_per_session < 0.001
                    ? `$${lensStats.stats.avg_cost_per_session.toFixed(5)}`
                    : `$${lensStats.stats.avg_cost_per_session.toFixed(4)}`}
              </p>
              <p className="mt-1 text-[11px] text-[#8a8378]">
                avg across {lensStats.stats.total_sessions} sessions
              </p>
            </div>
          </div>
        )}

        {/* Configuration Details */}
        <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* AI Model Configuration */}
          <div className="dashboard-panel p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#ffe1ea]">
                  <Sparkles className="h-4 w-4 text-[#171717]" />
                </div>
                <h2 className="text-[1rem] font-semibold text-[#171717] md:text-[1.1rem]">Default AI Model</h2>
              </div>
              <span className="rounded-[0.35rem] bg-[#ffe1ea] px-2.5 py-1 text-[11px] font-medium text-[#171717]">
                Default Model
              </span>
            </div>
            {defaultLLMConfig ? (
              <div className="space-y-2.5">
                <div className="flex items-center justify-between border-b border-black/[0.08] py-1.5">
                  <span className="text-[13px] font-medium text-[#6c655c]">Config Name</span>
                  <span className="text-[13px] font-semibold text-[#171717]">{defaultLLMConfig.name}</span>
                </div>
                <div className="flex items-center justify-between border-b border-black/[0.08] py-2">
                  <span className="text-[13px] font-medium text-[#6c655c]">Provider</span>
                  <span className="text-[13px] font-semibold capitalize text-[#171717]">{defaultLLMConfig.provider}</span>
                </div>
                <div className="flex items-center justify-between border-b border-black/[0.08] py-2">
                  <span className="text-[13px] font-medium text-[#6c655c]">Model</span>
                  <span className="text-[13px] font-semibold text-[#171717]">{defaultLLMConfig.model_name}</span>
                </div>
                <div className="flex items-center justify-between border-b border-black/[0.08] py-2">
                  <span className="text-[13px] font-medium text-[#6c655c]">Temperature</span>
                  <span className="text-[13px] font-semibold text-[#171717]">{defaultLLMConfig.temperature ?? 'N/A'}</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-[13px] font-medium text-[#6c655c]">Max Tokens</span>
                  <span className="text-[13px] font-semibold text-[#171717]">{defaultLLMConfig.max_tokens?.toLocaleString() ?? 'N/A'}</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-[13px] text-[#6c655c]">No default AI model configured</p>
                <button
                  onClick={() => router.push(`/agents/${agentName}/edit?tab=llm-models`)}
                  className="mt-3 text-[13px] font-medium text-[#171717] underline decoration-[#ff5f8f] decoration-2 underline-offset-4"
                >
                  Configure AI Model →
                </button>
              </div>
            )}
          </div>

          {/* System Prompt */}
          <div className="dashboard-panel p-5">
            <div className="mb-4 flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#fff0d9]">
                  <MessageSquare className="h-4.5 w-4.5 text-[#171717]" />
              </div>
              <h2 className="text-[1rem] font-semibold text-[#171717] md:text-[1.1rem]">System Prompt</h2>
              <div className="ml-auto flex items-center gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(agent.system_prompt)
                    setPromptCopied(true)
                    setTimeout(() => setPromptCopied(false), 2000)
                  }}
                  title="Copy system prompt"
                  className="flex items-center gap-1.5 rounded-[0.75rem] bg-[#f1eadc] px-3 py-1.5 text-[12px] font-medium text-[#464038] transition-colors hover:bg-[#e8dece]"
                >
                  {promptCopied ? <Check className="h-3.5 w-3.5 text-green-600" /> : <Copy className="h-3.5 w-3.5" />}
                  {promptCopied ? 'Copied!' : 'Copy'}
                </button>
                <button
                  onClick={() => setShowPromptModal(true)}
                  title="View as markdown"
                  className="flex items-center gap-1.5 rounded-[0.75rem] bg-[#f1eadc] px-3 py-1.5 text-[12px] font-medium text-[#464038] transition-colors hover:bg-[#e8dece]"
                >
                  <Maximize2 className="h-3.5 w-3.5" />
                  View
                </button>
              </div>
            </div>
            <div className="max-h-56 overflow-y-auto rounded-[1.35rem] bg-[#f1eadc] p-4">
              <p className="whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-[#464038] md:text-[13px]">
                {agent.system_prompt}
              </p>
            </div>
          </div>

          <SystemPromptModal
            prompt={agent.system_prompt}
            agentName={agentName as string}
            isOpen={showPromptModal}
            onClose={() => setShowPromptModal(false)}
          />
        </div>

        {/* Tools Configuration */}
        {agent.tools_config && agent.tools_config.tools && agent.tools_config.tools.length > 0 && (
          <div className="dashboard-panel mb-4 p-5">
            <div className="mb-3 flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#ffe1ea]">
                  <Settings className="h-4 w-4 text-[#171717]" />
              </div>
              <h2 className="text-[1rem] font-semibold text-[#171717] md:text-[1.1rem]">Configured Tools</h2>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {agent.tools_config.tools.map((tool, index) => (
                <div
                  key={index}
                  className={`rounded-[1.35rem] border p-4 transition-all ${
                    tool.enabled
                      ? 'border-black/[0.08] bg-white/72'
                      : 'border-black/[0.08] bg-[#f1eadc]'
                  }`}
                >
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <h3 className="text-[13px] font-semibold text-[#171717] md:text-[14px]">{tool.name}</h3>
                    <span
                  className={`rounded-[0.35rem] px-2.5 py-1 text-[11px] font-semibold ${
                        tool.enabled
                          ? 'bg-[#def4eb] text-[#171717]'
                          : 'bg-white/70 text-[#6c655c]'
                      }`}
                    >
                      {tool.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <p className="text-[12px] leading-relaxed text-[#5b564e] md:text-[13px]">{tool.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Metadata */}
        <div className="dashboard-panel p-5">
          <div className="mb-3 flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f1eadc]">
              <Calendar className="h-4 w-4 text-[#5b564e]" />
            </div>
            <h2 className="text-[1rem] font-semibold text-[#171717] md:text-[1.1rem]">Metadata</h2>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div className="flex items-center gap-2 rounded-[1.25rem] bg-[#f1eadc] p-3">
              <Box className="h-4 w-4 text-[#5b564e]" />
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8a8378]">Agent ID</p>
                <p className="truncate font-mono text-[12px] text-[#171717]">{agent.id}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-[1.25rem] bg-[#f1eadc] p-3">
              <Calendar className="h-4 w-4 text-[#5b564e]" />
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8a8378]">Created</p>
                <p className="text-[12px] text-[#171717]">
                  {new Date(agent.created_at).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                  })}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-[1.25rem] bg-[#f1eadc] p-3">
              <Clock className="h-4 w-4 text-[#5b564e]" />
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8a8378]">Last Updated</p>
                <p className="text-[12px] text-[#171717]">
                  {new Date(agent.updated_at).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                  })}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    {/* Call Agent modal */}

    {showCallModal && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">Call {agent?.agent_name}</h2>
            <button
              onClick={() => {
                if (vapiInstance) { vapiInstance.stop(); setVapiInstance(null) }
                setCallActive(false)
                setShowCallModal(false)
              }}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {!callActive ? (
            <div className="text-center py-6">
              <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                <Phone className="w-7 h-7 text-green-600" />
              </div>
              <p className="text-sm text-gray-500 mb-6">Start a voice conversation with this agent.</p>
              <button
                onClick={async () => {
                  if (!vapiPublicKey) {
                    toast.error('Vapi public key is not configured.')
                    return
                  }
                  try {
                    const token = await getWebCallToken(agentName)
                    if (!token.vapi_assistant_id) {
                      toast.error('No Vapi assistant configured. Save Phone Settings first to register the assistant.')
                      return
                    }
                    const Vapi = (await import('@vapi-ai/web')).default
                    const vapi = new Vapi(vapiPublicKey)
                    // The assistant is registered with our webhook as its model URL,
                    // so all conversation turns route through the full Synkora agent pipeline.
                    vapi.start(token.vapi_assistant_id)
                    vapi.on('call-end', () => { setCallActive(false); setVapiInstance(null) })
                    setVapiInstance(vapi)
                    setCallActive(true)
                  } catch {
                    toast.error('Failed to start call. Check Vapi configuration.')
                  }
                }}
                className="px-6 py-3 bg-green-600 text-white rounded-full font-medium hover:bg-green-700 text-sm"
              >
                Start Call
              </button>
            </div>
          ) : (
            <div className="text-center py-6">
              <div className="w-16 h-16 rounded-full bg-green-500 flex items-center justify-center mx-auto mb-4 animate-pulse">
                <Mic className="w-7 h-7 text-white" />
              </div>
              <p className="text-sm text-gray-700 font-medium mb-1">Call in progress</p>
              <p className="text-xs text-gray-400 mb-6">Speak to {agent?.agent_name}</p>
              <button
                onClick={() => {
                  if (vapiInstance) { vapiInstance.stop(); setVapiInstance(null) }
                  setCallActive(false)
                }}
                className="flex items-center gap-2 px-6 py-3 bg-red-500 text-white rounded-full font-medium hover:bg-red-600 text-sm mx-auto"
              >
                <PhoneOff className="w-4 h-4" />
                End Call
              </button>
            </div>
          )}
        </div>
      </div>
    )}
    </>
  )
}
