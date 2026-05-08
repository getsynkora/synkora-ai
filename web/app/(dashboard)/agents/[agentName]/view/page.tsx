'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Image from 'next/image'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
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
  DollarSign
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { getLLMConfigs } from '@/lib/api/agent-llm-configs'
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

export default function AgentViewPage() {
  const params = useParams()
  const router = useRouter()
  const agentName = params.agentName as string
  
  const [agent, setAgent] = useState<AgentDetails | null>(null)
  const [defaultLLMConfig, setDefaultLLMConfig] = useState<AgentLLMConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [showMoreActions, setShowMoreActions] = useState(false)
  const [publicSlug, setPublicSlug] = useState<string | null>(null)

  useEffect(() => {
    fetchAgentDetails()
  }, [agentName])

  const fetchAgentDetails = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getAgent(agentName)
      setAgent(data)

      // Fetch the default LLM config
      if (data.id) {
        const llmConfigs = await getLLMConfigs(data.id)
        const defaultConfig = llmConfigs.find(config => config.is_default)
        setDefaultLLMConfig(defaultConfig || null)
      }

      // Fetch public profile to get slug (for public page link)
      try {
        const profileRes = await apiClient.request('GET', `/api/v1/agents/${agentName}/public-profile`)
        if (profileRes?.profile?.is_published && profileRes?.profile?.slug) {
          setPublicSlug(profileRes.profile.slug)
        }
      } catch {
        // No public profile yet — that's fine
      }
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
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-red-50/60 via-white to-rose-50/40">
        <div className="text-center">
          <div className="relative">
            <div className="animate-spin rounded-full h-16 w-16 border-4 border-slate-200 border-t-primary-500 mx-auto"></div>
            <Sparkles className="w-6 h-6 text-primary-500 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
          </div>
          <p className="mt-6 text-slate-600 font-medium">Loading agent details...</p>
        </div>
      </div>
    )
  }

  if (error || !agent) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-red-50/60 via-white to-rose-50/40">
        <div className="text-center bg-white rounded-2xl shadow-xl p-8 max-w-md">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <XCircle className="w-8 h-8 text-red-600" />
          </div>
          <h3 className="text-xl font-semibold text-slate-900 mb-2">Error Loading Agent</h3>
          <p className="text-slate-600 mb-6">{error || 'Agent not found'}</p>
          <button
            onClick={() => router.push('/agents')}
            className="px-6 py-2.5 bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-lg hover:from-primary-600 hover:to-primary-700 transition-all shadow-sm hover:shadow-md font-medium"
          >
            Back to Agents
          </button>
        </div>
      </div>
    )
  }

  const successRate = agent.stats?.total_executions 
    ? Math.round((agent.stats.successful_executions / agent.stats.total_executions) * 100)
    : 0

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50/60 via-white to-rose-50/40">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 max-w-7xl">
        {/* Back Button */}
        <button
          onClick={() => router.push('/agents')}
          className="group inline-flex items-center gap-2 text-gray-600 hover:text-primary-600 mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
          <span className="text-sm font-medium">Back to Agents</span>
        </button>

        {/* Hero Section */}
        <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6 mb-5">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-5">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-lg flex items-center justify-center shadow-md overflow-hidden relative">
                  {agent.avatar ? (
                    agent.avatar.startsWith('http://') || agent.avatar.startsWith('https://') ? (
                      // Use regular img tag for external URLs (presigned URLs with query parameters)
                      <img
                        src={agent.avatar}
                        alt={agent.agent_name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      // Use Next.js Image for relative/local URLs
                      <Image
                        src={agent.avatar}
                        alt={agent.agent_name}
                        fill
                        className="object-cover"
                      />
                    )
                  ) : (
                    <Sparkles className="w-6 h-6 text-white" />
                  )}
                </div>
                <div>
                  <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">{agent.agent_name}</h1>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
                      agent.status === 'active' 
                        ? 'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-600/20' 
                        : 'bg-slate-100 text-slate-700 ring-1 ring-slate-600/20'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                        agent.status === 'active' ? 'bg-emerald-500' : 'bg-slate-500'
                      }`}></span>
                      {agent.status}
                    </span>
                    <span className="text-sm text-slate-500 capitalize">• {agent.agent_type}</span>
                  </div>
                </div>
              </div>
              <p className="text-gray-600 text-sm leading-relaxed max-w-3xl">{agent.description}</p>
            </div>
            
            <div className="flex gap-2">
              <button
                onClick={() => router.push(`/agents/${agentName}/edit`)}
                className="flex items-center gap-1.5 px-3 py-2 bg-gradient-to-r from-primary-500 to-primary-600 text-white text-sm rounded-lg hover:from-primary-600 hover:to-primary-700 transition-all shadow-sm hover:shadow-md font-medium"
              >
                <Edit className="w-4 h-4" />
                Edit
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-1.5 px-3 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition-all shadow-sm hover:shadow-md disabled:opacity-50 font-medium"
              >
                <Trash2 className="w-4 h-4" />
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>

          {/* Primary Quick Actions */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => router.push(`/agents/${agentName}/chat`)}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-lg hover:from-primary-600 hover:to-primary-700 transition-all shadow-sm hover:shadow-md font-medium text-sm"
            >
              <MessageSquare className="w-4 h-4" />
              Chat
            </button>

            <button
              onClick={() => router.push(`/agents/${agentName}/landing-page`)}
              className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-all text-sm font-medium"
            >
              <Globe className="w-4 h-4 text-primary-600" />
              Landing Page
            </button>

            {publicSlug && (
              <a
                href={`/a/${publicSlug}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-3 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-all text-sm font-medium shadow-sm"
              >
                <DollarSign className="w-4 h-4" />
                View Public Page
              </a>
            )}

            <button
              onClick={() => router.push(`/agents/${agentName}/knowledge-bases`)}
              className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-all text-sm font-medium"
            >
              <Database className="w-4 h-4 text-purple-600" />
              Knowledge
            </button>

            <button
              onClick={() => router.push(`/agents/${agentName}/tools`)}
              className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-all text-sm font-medium"
            >
              <Settings className="w-4 h-4 text-emerald-600" />
              Tools
            </button>

            <button
              onClick={() => router.push(`/agents/${agentName}/llm-configs`)}
              className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-all text-sm font-medium"
            >
              <Cpu className="w-4 h-4 text-indigo-600" />
              AI Model
            </button>

            <button
              onClick={() => router.push(`/agents/${agentName}/autonomous`)}
              className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-all text-sm font-medium"
            >
              <Bot className="w-4 h-4 text-red-600" />
              Autonomous
            </button>

            <div className="h-6 w-px bg-gray-200 mx-1" />

            <button
              onClick={() => setShowMoreActions(!showMoreActions)}
              className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-all text-sm font-medium"
            >
              More
              <ChevronDown className={`w-4 h-4 transition-transform ${showMoreActions ? 'rotate-180' : ''}`} />
            </button>
          </div>

          {/* Expandable More Actions */}
          {showMoreActions && (
            <div className="mt-4 pt-4 border-t border-gray-100">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Integrations */}
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Integrations</p>
                  <div className="space-y-1">
                    <button
                      onClick={() => router.push(`/agents/${agentName}/slack-bots`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none">
                        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#E01E5A"/>
                      </svg>
                      Slack
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/messaging-bots`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <MessageCircle className="w-4 h-4 text-green-600" />
                      Messaging Bots
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/telegram-bots`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="#0088cc">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
                      </svg>
                      Telegram
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/webhooks`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Webhook className="w-4 h-4 text-teal-600" />
                      Webhooks
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/database-connections`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Database className="w-4 h-4 text-blue-600" />
                      Database Connections
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/compute`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Server className="w-4 h-4 text-violet-600" />
                      Compute
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/voice`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Mic className="w-4 h-4 text-cyan-600" />
                      Voice
                    </button>
                  </div>
                </div>

                {/* Deployment */}
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Deployment</p>
                  <div className="space-y-1">
                    <button
                      onClick={() => router.push(`/agents/${agentName}/widgets`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Code className="w-4 h-4 text-orange-600" />
                      Widgets
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/domains`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Globe className="w-4 h-4 text-blue-600" />
                      Domains
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/api-keys`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Key className="w-4 h-4 text-amber-600" />
                      API Keys
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/subscriptions`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Bell className="w-4 h-4 text-red-500" />
                      Subscriptions
                    </button>
                  </div>
                </div>

                {/* Advanced */}
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Advanced</p>
                  <div className="space-y-1">
                    <button
                      onClick={() => router.push(`/agents/${agentName}/autonomous`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Bot className="w-4 h-4 text-red-600" />
                      Autonomous Mode
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/sub-agents`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Users className="w-4 h-4 text-rose-600" />
                      Sub-Agents
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/mcp-servers`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Zap className="w-4 h-4 text-indigo-600" />
                      MCP Servers
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/outputs`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Activity className="w-4 h-4 text-sky-600" />
                      Outputs
                    </button>
                    <button
                      onClick={() => router.push(`/agents/${agentName}/chat-customization`)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-50 transition-all text-sm"
                    >
                      <Sparkles className="w-4 h-4 text-violet-600" />
                      Customize Chat
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Stats Cards */}
        {agent.stats && Object.keys(agent.stats).length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-5">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-9 h-9 bg-red-100 rounded-lg flex items-center justify-center">
                  <Activity className="w-5 h-5 text-primary-600" />
                </div>
                <TrendingUp className="w-3 h-3 text-slate-400" />
              </div>
              <p className="text-xs font-medium text-slate-600 mb-1">Total Executions</p>
              <p className="text-2xl font-bold text-slate-900">{agent.stats.total_executions || 0}</p>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center">
                  <CheckCircle className="w-4 h-4 text-emerald-600" />
                </div>
                <span className="text-[10px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                  {successRate}%
                </span>
              </div>
              <p className="text-xs font-medium text-slate-600 mb-1">Success Rate</p>
              <p className="text-2xl font-bold text-emerald-600">{successRate}%</p>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 bg-red-100 rounded-lg flex items-center justify-center">
                  <XCircle className="w-4 h-4 text-red-600" />
                </div>
              </div>
              <p className="text-xs font-medium text-slate-600 mb-1">Failed Executions</p>
              <p className="text-2xl font-bold text-slate-900">{agent.stats.failed_executions || 0}</p>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 bg-red-100 rounded-lg flex items-center justify-center">
                  <Clock className="w-4 h-4 text-primary-600" />
                </div>
              </div>
              <p className="text-xs font-medium text-slate-600 mb-1">Avg. Execution Time</p>
              <p className="text-2xl font-bold text-slate-900">
                {agent.stats.average_execution_time 
                  ? `${agent.stats.average_execution_time.toFixed(2)}s`
                  : '0s'}
              </p>
            </div>
          </div>
        )}

        {/* Configuration Details */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          {/* AI Model Configuration */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 bg-red-100 rounded-lg flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-primary-600" />
                </div>
                <h2 className="text-base font-semibold text-gray-900">Default AI Model</h2>
              </div>
              <span className="text-xs text-primary-600 bg-red-50 px-2.5 py-1 rounded-full font-medium">
                Default Model
              </span>
            </div>
            {defaultLLMConfig ? (
              <div className="space-y-2.5">
                <div className="flex justify-between items-center py-1.5 border-b border-slate-100">
                  <span className="text-sm font-medium text-slate-600">Config Name</span>
                  <span className="text-sm font-semibold text-slate-900">{defaultLLMConfig.name}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-slate-100">
                  <span className="text-sm font-medium text-slate-600">Provider</span>
                  <span className="text-sm font-semibold text-slate-900 capitalize">{defaultLLMConfig.provider}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-slate-100">
                  <span className="text-sm font-medium text-slate-600">Model</span>
                  <span className="text-sm font-semibold text-slate-900">{defaultLLMConfig.model_name}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-slate-100">
                  <span className="text-sm font-medium text-slate-600">Temperature</span>
                  <span className="text-sm font-semibold text-slate-900">{defaultLLMConfig.temperature ?? 'N/A'}</span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <span className="text-sm font-medium text-slate-600">Max Tokens</span>
                  <span className="text-sm font-semibold text-slate-900">{defaultLLMConfig.max_tokens?.toLocaleString() ?? 'N/A'}</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-sm text-slate-500">No default AI model configured</p>
                <button
                  onClick={() => router.push(`/agents/${agentName}/edit?tab=llm-models`)}
                  className="mt-3 text-sm text-primary-600 hover:text-primary-700 font-medium"
                >
                  Configure AI Model →
                </button>
              </div>
            )}
          </div>

          {/* System Prompt */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
            <div className="flex items-center gap-2 mb-4">
                <div className="w-9 h-9 bg-red-100 rounded-lg flex items-center justify-center">
                  <MessageSquare className="w-5 h-5 text-primary-600" />
              </div>
              <h2 className="text-base font-semibold text-gray-900">System Prompt</h2>
            </div>
            <div className="bg-slate-50 rounded-lg p-4 max-h-48 overflow-y-auto">
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap font-mono">
                {agent.system_prompt}
              </p>
            </div>
          </div>
        </div>

        {/* Tools Configuration */}
        {agent.tools_config && agent.tools_config.tools && agent.tools_config.tools.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
            <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 bg-red-100 rounded-lg flex items-center justify-center">
                  <Settings className="w-4 h-4 text-primary-600" />
              </div>
              <h2 className="text-base font-semibold text-gray-900">Configured Tools</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {agent.tools_config.tools.map((tool, index) => (
                <div
                  key={index}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    tool.enabled
                      ? 'bg-red-50 border-primary-200'
                      : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-semibold text-slate-900 text-sm">{tool.name}</h3>
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                        tool.enabled
                          ? 'bg-red-100 text-primary-700'
                          : 'bg-slate-200 text-slate-600'
                      }`}
                    >
                      {tool.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">{tool.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Metadata */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center">
              <Calendar className="w-4 h-4 text-slate-600" />
            </div>
            <h2 className="text-base font-semibold text-gray-900">Metadata</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="flex items-center gap-2 p-2.5 bg-slate-50 rounded-lg">
              <Box className="w-4 h-4 text-slate-500" />
              <div>
                <p className="text-xs font-medium text-slate-500">Agent ID</p>
                <p className="text-xs font-mono text-slate-900 truncate">{agent.id}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2.5 bg-slate-50 rounded-lg">
              <Calendar className="w-4 h-4 text-slate-500" />
              <div>
                <p className="text-xs font-medium text-slate-500">Created</p>
                <p className="text-xs text-slate-900">
                  {new Date(agent.created_at).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                  })}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2.5 bg-slate-50 rounded-lg">
              <Clock className="w-4 h-4 text-slate-500" />
              <div>
                <p className="text-xs font-medium text-slate-500">Last Updated</p>
                <p className="text-xs text-slate-900">
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
  )
}
