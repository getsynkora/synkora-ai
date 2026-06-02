'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Settings, Send, Loader2, Lock, ArrowRight, Zap, List, Plug, Pencil, Trash2 } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { ChatMessage } from '@/components/chat/components/ChatMessage'
import type { Message } from '@/components/chat/types'
import { getPlatformAgentStatus, type PlatformAgentStatus } from '@/lib/api/platformEngineerApi'
import { SetupScreen } from '@/components/agents/platform-engineer/screens/SetupScreen'
import { ActionConfirmCard } from '@/components/agents/platform-engineer/cards/ActionConfirmCard'
import { IntegrationPromptCard } from '@/components/agents/platform-engineer/cards/IntegrationPromptCard'
import { AgentCreatedCard } from '@/components/agents/platform-engineer/cards/AgentCreatedCard'
import { parseActionMarkers } from '@/components/agents/platform-engineer/types'
import type { ActionCard, IntegrationCard } from '@/components/agents/platform-engineer/types'
import type { AgentCreateConfig, ActionCardStatus } from '@/components/agents/platform-engineer/cards/ActionConfirmCard'
import { apiClient } from '@/lib/api/http'
import { useChatTransport } from '@/components/chat/hooks/useChatTransport'
import type { ChatEvent } from '@/components/chat/hooks/useChatTransport'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'
const AGENT_NAME = 'platform_engineer_agent'
const MSG_STORAGE_KEY = 'pe-messages'
const CONV_ID_STORAGE_KEY = 'pe-conv-id'

type Screen = 'loading' | 'gate' | 'setup' | 'chat'

interface ToolStatus {
  tool_name: string
  status: 'started' | 'completed' | 'error'
  description: string
  details?: Record<string, unknown>
  duration_ms?: number
  input_tokens?: number
  output_tokens?: number
}

interface PEMessage extends Message {
  _actionCard?: ActionCard & { status: ActionCardStatus; createdAgentName?: string; createdAgentSlug?: string }
  _integrationCard?: IntegrationCard
}

const QUICK_ACTIONS = [
  { icon: Zap, label: 'Create an agent', prompt: 'I want to create a new AI agent. Help me design one.' },
  { icon: List, label: 'List my agents', prompt: 'Show me all my current agents' },
  { icon: Plug, label: 'Check integrations', prompt: 'What integrations are available and which ones do I have connected?' },
  { icon: Pencil, label: 'Update an agent', prompt: 'I want to update an existing agent. Which ones do I have?' },
]

export default function PlatformEngineerPage() {
  const [screen, setScreen] = useState<Screen>('loading')
  const [status, setStatus] = useState<PlatformAgentStatus | null>(null)
  const [messages, setMessages] = useState<PEMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [thinkingStatus, setThinkingStatus] = useState<string>('')
  const [toolStatus, setToolStatus] = useState<ToolStatus | null>(null)
  const [recentTools, setRecentTools] = useState<ToolStatus[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const convIdRef = useRef<string>('')

  // Use the same transport hook as normal agents
  const transport = useChatTransport('sse', API_URL)

  // Load persisted conversation on mount
  useEffect(() => {
    try {
      const savedConvId = localStorage.getItem(CONV_ID_STORAGE_KEY)
      if (savedConvId) {
        convIdRef.current = savedConvId
      } else {
        const id = crypto.randomUUID()
        localStorage.setItem(CONV_ID_STORAGE_KEY, id)
        convIdRef.current = id
      }
      const saved = localStorage.getItem(MSG_STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved) as PEMessage[]
        setMessages(parsed.map((m) => ({ ...m, timestamp: new Date(m.timestamp as unknown as string) })))
      }
    } catch {
      // ignore storage errors
    }
  }, [])

  // Persist messages whenever they change
  useEffect(() => {
    if (messages.length === 0) return
    try {
      localStorage.setItem(MSG_STORAGE_KEY, JSON.stringify(messages))
    } catch {
      // ignore storage errors
    }
  }, [messages])

  useEffect(() => {
    getPlatformAgentStatus()
      .then((s) => {
        setStatus(s)
        if (!s.has_access) setScreen('gate')
        else if (!s.is_configured) setScreen('setup')
        else setScreen('chat')
      })
      .catch(() => setScreen('chat'))
  }, [])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const clearConversation = useCallback(() => {
    setMessages([])
    const id = crypto.randomUUID()
    convIdRef.current = id
    try {
      localStorage.setItem(CONV_ID_STORAGE_KEY, id)
      localStorage.removeItem(MSG_STORAGE_KEY)
    } catch { /* ignore */ }
  }, [])

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isStreaming) return

    const userMsg: PEMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
    }
    const assistantMsg: PEMessage = {
      id: `asst-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput('')
    setIsStreaming(true)
    setThinkingStatus('Thinking...')

    try {
      let fullResponse = ''

      for await (const event of transport.sendMessage({
        agent_slug: AGENT_NAME,
        message: content,
        conversation_id: convIdRef.current || undefined,
        conversation_history: messages.slice(-10).map((m) => ({
          role: m.role,
          content: m.content,
        })),
      })) {
        if (event.type === 'chunk') {
          fullResponse += event.content
          setThinkingStatus('')
          const { displayText, actionCard, integrationCard } = parseActionMarkers(fullResponse)
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last.role === 'assistant') {
              next[next.length - 1] = {
                ...last,
                content: displayText,
                _actionCard: actionCard
                  ? { ...actionCard, status: last._actionCard?.status ?? 'pending' }
                  : last._actionCard,
                _integrationCard: integrationCard ?? last._integrationCard,
              }
            }
            return next
          })
        } else if (event.type === 'status') {
          if (!event.content?.includes('completed')) {
            setThinkingStatus(event.content || 'Thinking...')
          }
        } else if (event.type === 'tool_status') {
          const newToolStatus: ToolStatus = {
            tool_name: event.tool_name,
            status: event.status,
            description: event.description || `Using ${event.tool_name}`,
            details: event.details,
            duration_ms: event.duration_ms,
            input_tokens: event.input_tokens,
            output_tokens: event.output_tokens,
          }
          if (event.status === 'started') {
            setToolStatus(newToolStatus)
            setThinkingStatus(event.description || `Using ${event.tool_name}...`)
          } else {
            setRecentTools((prev) => [...prev, newToolStatus].slice(-5))
            setToolStatus(null)
          }
        } else if (event.type === 'done') {
          setThinkingStatus('')
          // Finalize assistant message with metadata
          const doneEvent = event as ChatEvent & { type: 'done' }
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last.role === 'assistant') {
              next[next.length - 1] = {
                ...last,
                metadata: {
                  ...last.metadata,
                  sources: (doneEvent.sources || []) as any[],
                  usage: doneEvent.metadata ? {
                    input_tokens: doneEvent.metadata.input_tokens || 0,
                    output_tokens: doneEvent.metadata.output_tokens || 0,
                    total_tokens: doneEvent.metadata.total_tokens || 0,
                  } : undefined,
                },
              }
            }
            return next
          })
        }
      }
    } catch (err: any) {
      const msg = err?.message || 'Failed to get response'
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last.role === 'assistant') {
          const existing = last.content ? `${last.content}\n\n` : ''
          next[next.length - 1] = { ...last, content: `${existing}Error: ${msg}`, isError: true }
        }
        return next
      })
      toast.error(msg)
    } finally {
      setIsStreaming(false)
      setThinkingStatus('')
      setToolStatus(null)
      setRecentTools([])
    }
  }, [isStreaming, messages, transport])

  const handleConfirm = async (config: AgentCreateConfig, messageId?: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m._actionCard?.status === 'pending' && (!messageId || m.id === messageId)
          ? { ...m, _actionCard: { ...m._actionCard!, status: 'creating' } }
          : m
      )
    )
    try {
      // Build tool objects for the backend (so it also creates AgentTool records)
      const toolObjects = (config.tools_list || []).map((t) => ({
        name: t,
        description: t.replace(/_/g, ' '),
        enabled: true,
      }))
      const wantsImageGeneration = (config.tools_list || []).includes('image_generation')
      const metadata = wantsImageGeneration || config.image_llm_model || config.image_llm_provider
        ? {
            image_generation_provider: config.image_llm_provider || 'openai',
            image_generation_model: config.image_llm_model || 'gpt-image-2',
          }
        : {}

      const res = await apiClient.axios.post('/api/v1/agents/', {
        config: {
          name: config.name,
          description: config.description,
          system_prompt: config.system_prompt,
          agent_type: 'llm_agent',
          llm_config: {
            provider: config.llm_provider,
            model_name: config.llm_model,
            temperature: 0.7,
            max_tokens: 4096,
            api_key: '',
          },
          tools: toolObjects,
          metadata,
        },
        agent_type: 'llm',
        is_public: false,
        category: config.category,
        tags: config.tags,
      })
      // Response: { success, message, data: { agent_id, agent_name } }
      const responseData = res.data?.data || res.data
      const created = responseData?.agent_name || config.name
      const createdSlug: string | undefined = responseData?.slug
      const agentId: string | undefined = responseData?.agent_id

      setMessages((prev) =>
        prev.map((m) => {
          if (m._actionCard?.status === 'creating') {
            return { ...m, _actionCard: { ...m._actionCard!, status: 'created', createdAgentName: created, createdAgentSlug: createdSlug } }
          }
          // Cancel any remaining pending duplicates for the same agent name
          if (m._actionCard?.status === 'pending' && m._actionCard.config?.name === config.name) {
            return { ...m, _actionCard: { ...m._actionCard!, status: 'cancelled' } }
          }
          return m
        })
      )
    } catch (err: any) {
      const status = err?.response?.status
      const rawDetail = err?.response?.data?.detail

      let detail: string
      if (status === 409) {
        detail = `An agent named "${config.name}" already exists. Ask the Platform Engineer to update it instead (add tools, change prompt, etc.).`
      } else if (Array.isArray(rawDetail)) {
        detail = rawDetail.map((e: any) => `${e.loc?.slice(-1)[0] ?? 'field'}: ${e.msg}`).join('; ')
      } else {
        detail = typeof rawDetail === 'string' ? rawDetail : err?.message || 'Agent creation failed'
      }

      setMessages((prev) =>
        prev.map((m) =>
          m._actionCard?.status === 'creating'
            ? { ...m, _actionCard: { ...m._actionCard!, status: 'pending' } }
            : m
        )
      )
      toast.error(detail)
    }
  }

  const handleCancelAction = (messageId?: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m._actionCard?.status === 'pending' && (!messageId || m.id === messageId)
          ? { ...m, _actionCard: { ...m._actionCard!, status: 'cancelled' } }
          : m
      )
    )
  }

  const handleCopyMessage = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content)
    } catch {
      // ignore
    }
  }

  const handleRetry = (messageId: string) => {
    const messageIndex = messages.findIndex((m) => m.id === messageId)
    if (messageIndex > 0) {
      const previousUserMessage = messages[messageIndex - 1]
      if (previousUserMessage.role === 'user') {
        setMessages((prev) => prev.slice(0, messageIndex))
        sendMessage(previousUserMessage.content)
      }
    }
  }

  // --- Loading ---
  if (screen === 'loading') {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-b-2 border-[#171717]" />
      </div>
    )
  }

  // --- Plan Gate ---
  if (screen === 'gate') {
    return (
      <div className="dashboard-resource-page relative flex min-h-screen items-center justify-center overflow-hidden p-4">
        <div className="pointer-events-none absolute inset-0 opacity-[0.2] [background-image:repeating-linear-gradient(90deg,transparent_0,transparent_12%,rgba(72,51,34,0.08)_12.2%,transparent_12.5%)]" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-[radial-gradient(circle_at_50%_0%,rgba(30,24,20,0.18),transparent_68%)] opacity-70" />
        <div className="pointer-events-none absolute left-[-4rem] top-12 h-40 w-40 rounded-full bg-white/70 blur-3xl" />
        <div className="pointer-events-none absolute bottom-10 right-[-3rem] h-44 w-44 rounded-full bg-[#ff5f8f]/15 blur-3xl" />

        <div className="relative w-full max-w-3xl overflow-hidden rounded-[2.4rem] border border-[#e1d4c3] bg-[linear-gradient(180deg,_rgba(251,246,238,0.98),_rgba(244,237,227,0.96))] p-10 text-center shadow-[0_28px_90px_-46px_rgba(88,63,39,0.34)] md:p-12">
          <div className="pointer-events-none absolute inset-0 opacity-[0.14] [background-image:repeating-linear-gradient(90deg,transparent_0,transparent_11%,rgba(72,51,34,0.08)_11.2%,transparent_11.5%)]" />
          <div className="relative">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-[1.25rem] border border-black/10 bg-[#171717] text-white shadow-[0_20px_44px_-24px_rgba(0,0,0,0.5)]">
              <Lock className="h-7 w-7" />
            </div>
            <div className="space-y-3">
              <span className="inline-block rounded-full border border-[#dfd1be] bg-white/75 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7c5d45]">
              {status?.plan_tier ? `${status.plan_tier} plan` : 'Free plan'}
              </span>
              <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[#8b8174]">
                Platform Engineer
              </p>
              <h3 className="mx-auto max-w-2xl text-[clamp(2.5rem,5vw,4.6rem)] font-light leading-[0.92] tracking-[-0.07em] text-gray-950">
                <span className="block">Platform Engineer</span>
                <span className="editorial-highlight mt-3 inline-block">Agent</span>
              </h3>
              <p className="mx-auto max-w-xl text-sm leading-6 text-gray-600 md:text-base">
                Available on Hobby and above. Create and manage AI agents through natural conversation.
              </p>
            </div>
            <ul className="mx-auto mt-8 grid max-w-2xl gap-3 text-left sm:grid-cols-2">
              {['Create agents through conversation', 'Check integration status', 'Manage agent configurations', 'Get tool recommendations'].map((f) => (
                <li
                  key={f}
                  className="rounded-[1.2rem] border border-black/10 bg-white/70 px-4 py-3 text-sm text-gray-700 shadow-[0_16px_34px_-28px_rgba(28,20,12,0.5)]"
                >
                  <div className="mb-1 h-1.5 w-10 rounded-full bg-[#171717]" />
                  {f}
                </li>
              ))}
            </ul>
            <Link href="/billing/subscription" className="mt-8 inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black">
              Upgrade Plan <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // --- Setup ---
  if (screen === 'setup') {
    return (
      <div className="dashboard-resource-page flex h-[calc(100vh-4rem)] flex-col">
        <div className="relative flex flex-shrink-0 items-center justify-between overflow-hidden border-b border-[#e7dac8] bg-[linear-gradient(180deg,_rgba(251,246,238,0.96),_rgba(247,239,229,0.92))] px-4 py-3 backdrop-blur-sm md:px-8">
          <div className="pointer-events-none absolute inset-0 opacity-[0.16] [background-image:repeating-linear-gradient(90deg,transparent_0,transparent_13%,rgba(72,51,34,0.08)_13.2%,transparent_13.5%)]" />
          <div className="flex items-center gap-2.5">
            <PlatformEngineerMark className="h-9 w-9 rounded-[1rem] bg-[#171717] text-white shadow-[0_20px_38px_-24px_rgba(0,0,0,0.5)]" />
            <div>
              <p className="text-[11px] font-semibold uppercase leading-tight tracking-[0.28em] text-[#8b8174]">Platform Engineer</p>
              <p className="text-sm font-semibold leading-tight text-gray-900">LLM Configuration</p>
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl px-4 py-6 md:px-8">
            <SetupScreen
              onConfigured={async () => {
                try {
                  const s = await getPlatformAgentStatus()
                  setStatus(s)
                } catch { /* ignore */ }
                setScreen('chat')
              }}
            />
          </div>
        </div>
      </div>
    )
  }

  // --- Chat ---
  const isEmpty = messages.length === 0

  const alreadyCreated = new Set<string>()
  for (const message of messages) {
    if (message._actionCard?.status === 'created' && message._actionCard.config?.name) {
      alreadyCreated.add(message._actionCard.config.name)
    }
  }

  const latestPendingById = new Set<string>()
  const seenAgentNames = new Set<string>()
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i]
    if (message._actionCard && message._actionCard.status !== 'created') {
      const agentName = message._actionCard.config?.name
      if (agentName && !alreadyCreated.has(agentName) && !seenAgentNames.has(agentName)) {
        seenAgentNames.add(agentName)
        latestPendingById.add(message.id)
      }
    }
  }

  return (
    <div className="dashboard-resource-page flex h-[calc(100vh-4rem)] flex-col">
      {/* Sub-header */}
      <div className="relative flex flex-shrink-0 items-center justify-between overflow-hidden border-b border-[#e7dac8] bg-[linear-gradient(180deg,_rgba(251,246,238,0.96),_rgba(247,239,229,0.92))] px-4 py-3 backdrop-blur-sm md:px-8">
        <div className="pointer-events-none absolute inset-0 opacity-[0.16] [background-image:repeating-linear-gradient(90deg,transparent_0,transparent_13%,rgba(72,51,34,0.08)_13.2%,transparent_13.5%)]" />
        <div className="flex items-center gap-2.5">
          <PlatformEngineerMark className="h-9 w-9 rounded-[1rem] bg-[#171717] text-white shadow-[0_20px_38px_-24px_rgba(0,0,0,0.5)]" />
          <div>
            <p className="text-[11px] font-semibold uppercase leading-tight tracking-[0.28em] text-[#8b8174]">Platform Engineer</p>
            <p className="text-sm font-semibold text-gray-900 leading-tight">Platform Engineer</p>
            {status?.is_configured && (
              <p className="text-xs text-gray-500 leading-tight">{status.provider} / {status.model_name}</p>
            )}
          </div>
        </div>
        <div className="relative flex items-center gap-1">
          {messages.length > 0 && (
            <button
              onClick={clearConversation}
              title="Clear conversation"
              className="flex h-9 w-9 items-center justify-center rounded-[0.9rem] text-gray-500 transition-colors hover:bg-white/80 hover:text-[#171717]"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => setScreen('setup')}
            title="Configure LLM"
              className="flex h-9 w-9 items-center justify-center rounded-[0.9rem] text-gray-500 transition-colors hover:bg-white/80 hover:text-[#171717]"
            >
              <Settings className="h-4 w-4" />
            </button>
        </div>
      </div>

      {/* Messages / Hero */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <HeroSection onSend={sendMessage} isStreaming={isStreaming} />
        ) : (
          <div className="mx-auto max-w-4xl px-3 py-3 sm:px-4 sm:py-4 lg:px-5">
            <div className="space-y-5">
              {messages.map((message, index) => {
                const isLastMessage = index === messages.length - 1
                const isStreamingMessage = isStreaming && isLastMessage
                const shouldShowActionCard =
                  !!message._actionCard &&
                  message._actionCard.status !== 'created' &&
                  latestPendingById.has(message.id)
                const shouldShowCreatedCard =
                  message._actionCard?.status === 'created' && !!message._actionCard.createdAgentName
                const shouldShowIntegrationCard = !!message._integrationCard

                return (
                  <div key={message.id} className="space-y-4">
                    <ChatMessage
                      message={message}
                      isStreaming={isStreamingMessage}
                      thinkingStatus={isStreamingMessage ? thinkingStatus : undefined}
                      toolStatus={isStreamingMessage ? toolStatus : undefined}
                      recentTools={isStreamingMessage ? recentTools : []}
                      onCopy={handleCopyMessage}
                      onRetry={handleRetry}
                      agentName="Platform Engineer"
                    />

                    {(shouldShowActionCard || shouldShowCreatedCard || shouldShowIntegrationCard) && (
                      <div className="pl-6 sm:pl-8">
                        <div className="space-y-4">
                          {shouldShowActionCard && (
                            <ActionConfirmCard
                              config={message._actionCard!.config}
                              status={message._actionCard!.status}
                              onConfirm={(config) => handleConfirm(config, message.id)}
                              onCancel={() => handleCancelAction(message.id)}
                            />
                          )}

                          {shouldShowCreatedCard && (
                            <AgentCreatedCard
                              agentName={message._actionCard!.createdAgentName!}
                              agentSlug={message._actionCard!.createdAgentSlug}
                            />
                          )}

                          {shouldShowIntegrationCard && (
                            <IntegrationPromptCard
                              provider={message._integrationCard!.provider}
                              message={message._integrationCard!.message}
                              connect_url={message._integrationCard!.connect_url}
                              type={message._integrationCard!.type}
                            />
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Input bar */}
      {!isEmpty && (
        <div className="border-t border-gray-100 bg-white/80 backdrop-blur-sm px-4 md:px-8 py-3 flex-shrink-0">
          <div className="max-w-4xl mx-auto">
            <ChatInputBar
              value={input}
              onChange={setInput}
              onSend={() => sendMessage(input)}
              isStreaming={isStreaming}
              textareaRef={textareaRef}
            />
          </div>
        </div>
      )}
    </div>
  )
}

// --- Sub-components ---

function HeroSection({
  onSend,
  isStreaming,
}: {
  onSend: (msg: string) => void
  isStreaming: boolean
}) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  return (
    <div className="relative flex min-h-full items-center justify-center overflow-hidden px-4 py-12 text-center md:px-8 md:py-16">
      <div className="pointer-events-none absolute inset-0 opacity-[0.12] [background-image:repeating-linear-gradient(90deg,transparent_0,transparent_12%,rgba(72,51,34,0.08)_12.2%,transparent_12.5%)]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-32 bg-[radial-gradient(circle_at_50%_0%,rgba(30,24,20,0.12),transparent_72%)] opacity-70" />
      <div className="pointer-events-none absolute bottom-16 right-8 h-48 w-48 rounded-full bg-[#ff5f8f]/10 blur-3xl" />

      <div className="relative w-full max-w-4xl">
        <div className="mx-auto max-w-3xl space-y-5">
          <PlatformEngineerMark className="mx-auto h-16 w-16 rounded-[1.45rem] bg-[#171717] text-white shadow-[0_24px_50px_-26px_rgba(0,0,0,0.48)]" iconClassName="h-7 w-7" />
          <div className="space-y-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.36em] text-[#8b8174]">
              Platform Engineer
            </p>
            <h1 className="text-[clamp(3rem,8vw,6rem)] font-light leading-[0.9] tracking-[-0.075em] text-gray-900 sm:whitespace-nowrap">
              What will <span className="editorial-highlight inline-block">you build?</span>
            </h1>
            <p className="mx-auto max-w-2xl text-sm font-medium uppercase tracking-[0.28em] text-[#403a33] sm:text-[0.95rem]">
              Create and manage AI agents through conversation
            </p>
            <p className="mx-auto max-w-xl text-sm leading-6 text-gray-600 md:text-base">
              No code needed.
            </p>
          </div>
        </div>

        <div className="mx-auto mt-10 max-w-3xl text-left">
          <div className="rounded-[2rem] border border-black/10 bg-[linear-gradient(180deg,_rgba(255,255,255,0.84),_rgba(250,246,239,0.92))] px-5 py-4 shadow-[0_24px_48px_-36px_rgba(30,22,14,0.3)] backdrop-blur-sm">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Describe the agent you want to build..."
              rows={2}
              className="w-full resize-none !bg-transparent text-base leading-relaxed text-gray-900 placeholder:text-gray-400 outline-none"
              style={{ backgroundColor: 'transparent' }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  if (value.trim()) onSend(value)
                }
              }}
            />
            <div className="mt-3 flex items-center justify-end">
              <button
                onClick={() => { if (value.trim()) onSend(value) }}
                disabled={!value.trim() || isStreaming}
                className="flex h-11 w-11 items-center justify-center rounded-[1rem] bg-[#171717] text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <p className="mt-3 text-center text-[11px] font-semibold uppercase tracking-[0.26em] text-[#8b8174]">
            Describe the workflow, tools, or integrations you need
          </p>
        </div>

        <div className="mx-auto mt-8 flex max-w-4xl flex-wrap items-center justify-center gap-2.5">
          {QUICK_ACTIONS.map(({ icon: Icon, label, prompt }) => (
            <button
              key={label}
              disabled={isStreaming}
              onClick={() => onSend(prompt)}
              className="flex items-center gap-2 rounded-full border border-black/10 bg-transparent px-4 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:border-[#ff5f8f]/45 hover:bg-white/50 hover:text-[#171717] disabled:opacity-50"
            >
              <Icon className="h-3.5 w-3.5 text-gray-500" />
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function ChatInputBar({
  value,
  onChange,
  onSend,
  isStreaming,
  textareaRef,
}: {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  isStreaming: boolean
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
}) {
  return (
    <div className="rounded-[1.7rem] border border-[#ded1bf] bg-[linear-gradient(180deg,_rgba(255,255,255,0.82),_rgba(250,245,238,0.92))] px-4 pt-3 pb-2 shadow-[0_18px_40px_-34px_rgba(30,22,14,0.5)] backdrop-blur-sm transition-shadow hover:shadow-[0_24px_48px_-34px_rgba(30,22,14,0.56)]">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Ask the Platform Engineer anything..."
        rows={1}
        className="w-full text-sm text-gray-900 placeholder:text-gray-400 resize-none outline-none bg-transparent min-h-[36px] max-h-[120px] overflow-y-auto leading-relaxed"
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            onSend()
          }
        }}
      />
      <div className="flex items-center justify-end pt-1">
        <button
          onClick={onSend}
          disabled={!value.trim() || isStreaming}
          className="flex h-10 w-10 items-center justify-center rounded-[1rem] bg-[#171717] text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </div>
  )
}

function PlatformEngineerMark({
  className = '',
  iconClassName = 'h-4 w-4',
}: {
  className?: string
  iconClassName?: string
}) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <svg className={iconClassName} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z" />
      </svg>
    </div>
  )
}
