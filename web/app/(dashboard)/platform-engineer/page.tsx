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

type PEActionCard = ActionCard & { status: ActionCardStatus; createdAgentName?: string; createdAgentSlug?: string }

interface PEMessage extends Message {
  _actionCards?: PEActionCard[]
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
    setThinkingStatus('Thinking…')

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
          const { displayText, actionCards, integrationCard } = parseActionMarkers(fullResponse)
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last.role === 'assistant') {
              // Merge new action cards with existing status/name so in-progress state is preserved
              const mergedCards: PEActionCard[] = actionCards.map((ac, i) => {
                const existing = last._actionCards?.[i]
                return {
                  ...ac,
                  status: existing?.status ?? 'pending',
                  createdAgentName: existing?.createdAgentName,
                  createdAgentSlug: existing?.createdAgentSlug,
                }
              })
              next[next.length - 1] = {
                ...last,
                content: displayText,
                _actionCards: mergedCards.length > 0 ? mergedCards : last._actionCards,
                _integrationCard: integrationCard ?? last._integrationCard,
              }
            }
            return next
          })
        } else if (event.type === 'status') {
          if (!event.content?.includes('completed')) {
            setThinkingStatus(event.content || 'Thinking…')
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

  const handleConfirm = async (config: AgentCreateConfig, messageId: string, cardIndex: number) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== messageId) return m
        const cards = m._actionCards?.map((c, i) =>
          i === cardIndex ? { ...c, status: 'creating' as ActionCardStatus } : c
        )
        return { ...m, _actionCards: cards }
      })
    )
    try {
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
      const responseData = res.data?.data || res.data
      const created = responseData?.agent_name || config.name
      const createdSlug: string | undefined = responseData?.slug

      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== messageId) return m
          const cards = m._actionCards?.map((c, i) =>
            i === cardIndex
              ? { ...c, status: 'created' as ActionCardStatus, createdAgentName: created, createdAgentSlug: createdSlug }
              : c
          )
          return { ...m, _actionCards: cards }
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
        prev.map((m) => {
          if (m.id !== messageId) return m
          const cards = m._actionCards?.map((c, i) =>
            i === cardIndex && c.status === 'creating' ? { ...c, status: 'pending' as ActionCardStatus } : c
          )
          return { ...m, _actionCards: cards }
        })
      )
      toast.error(detail)
    }
  }

  const handleCancelAction = (messageId: string, cardIndex: number) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== messageId) return m
        const cards = m._actionCards?.map((c, i) =>
          i === cardIndex && c.status === 'pending' ? { ...c, status: 'cancelled' as ActionCardStatus } : c
        )
        return { ...m, _actionCards: cards }
      })
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
        <div className="h-10 w-10 motion-safe:animate-spin rounded-full border-b-2 border-ink" />
      </div>
    )
  }

  // --- Plan Gate ---
  if (screen === 'gate') {
    return (
      <div className="dashboard-resource-page relative flex min-h-screen items-center justify-center overflow-hidden p-4">
        <div className="pointer-events-none absolute inset-0 opacity-[0.2]" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-24 opacity-70" />

        <div className="relative w-full max-w-3xl overflow-hidden rounded-[2.4rem] border border-line bg-paper p-10 text-center shadow-soft md:p-12">
          <div className="pointer-events-none absolute inset-0 opacity-[0.14]" />
          <div className="relative">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-[1.25rem] border border-black/10 bg-ink text-white shadow-soft">
              <Lock className="h-7 w-7" />
            </div>
            <div className="space-y-3">
              <span className="inline-block rounded-full border border-line bg-white/75 px-3 py-1 text-[11px] font-semibold text-bark">
              {status?.plan_tier ? `${status.plan_tier} plan` : 'Free plan'}
              </span>
              <p className="text-[11px] font-semibold text-ash">
                Platform Engineer
              </p>
              <h3 className="mx-auto max-w-2xl text-[clamp(2.5rem,5vw,4.6rem)] font-light leading-[0.92] tracking-[-0.07em] text-ink">
                <span className="block">Platform Engineer</span>
                <span className="editorial-highlight mt-3 inline-block">Agent</span>
              </h3>
              <p className="mx-auto max-w-xl text-sm leading-6 text-ink-soft md:text-base">
                Available on Hobby and above. Create and manage AI agents through natural conversation.
              </p>
            </div>
            <ul className="mx-auto mt-8 grid max-w-2xl gap-3 text-left sm:grid-cols-2">
              {['Create agents through conversation', 'Check integration status', 'Manage agent configurations', 'Get tool recommendations'].map((f) => (
                <li
                  key={f}
                  className="rounded-[1.2rem] border border-black/10 bg-white/70 px-4 py-3 text-sm text-ink-soft shadow-soft"
                >
                  <div className="mb-1 h-1.5 w-10 rounded-full bg-ink" />
                  {f}
                </li>
              ))}
            </ul>
            <Link href="/billing/subscription" className="mt-8 inline-flex items-center gap-2 rounded-[1rem] bg-ink px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black">
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
        <div className="relative flex flex-shrink-0 items-center justify-between overflow-hidden border-b border-line bg-paper px-4 py-3 md:px-8">
          <div className="pointer-events-none absolute inset-0 opacity-[0.16]" />
          <div className="flex items-center gap-2.5">
            <PlatformEngineerMark className="h-9 w-9 rounded-[1rem] bg-ink text-white shadow-soft" />
            <div>
              <p className="text-[11px] font-semibold leading-tight text-ash">Platform Engineer</p>
              <p className="text-sm font-semibold leading-tight text-ink">LLM Configuration</p>
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

  // Track agent names that have been successfully created to deduplicate cards across messages
  const alreadyCreated = new Set<string>()
  for (const message of messages) {
    for (const card of message._actionCards || []) {
      if (card.status === 'created' && card.config?.name) {
        alreadyCreated.add(card.config.name)
      }
    }
  }

  return (
    <div className="dashboard-resource-page flex h-[calc(100vh-4rem)] flex-col">
      {/* Sub-header */}
      <div className="relative flex flex-shrink-0 items-center justify-between overflow-hidden border-b border-line bg-paper px-4 py-3 md:px-8">
        <div className="pointer-events-none absolute inset-0 opacity-[0.16]" />
        <div className="flex items-center gap-2.5">
          <PlatformEngineerMark className="h-9 w-9 rounded-[1rem] bg-ink text-white shadow-soft" />
          <div>
            <p className="text-[11px] font-semibold leading-tight text-ash">Platform Engineer</p>
            <p className="text-sm font-semibold text-ink leading-tight">Platform Engineer</p>
            {status?.is_configured && (
              <p className="text-xs text-ink-mute leading-tight">{status.provider} / {status.model_name}</p>
            )}
          </div>
        </div>
        <div className="relative flex items-center gap-1">
          {messages.length > 0 && (
            <button
              onClick={clearConversation}
              title="Clear conversation"
              className="flex h-9 w-9 items-center justify-center rounded-[0.9rem] text-ink-mute transition-colors hover:bg-white/80 hover:text-ink"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => setScreen('setup')}
            title="Configure LLM"
              className="flex h-9 w-9 items-center justify-center rounded-[0.9rem] text-ink-mute transition-colors hover:bg-white/80 hover:text-ink"
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
                const hasCards = (message._actionCards?.length ?? 0) > 0
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

                    {(hasCards || shouldShowIntegrationCard) && (
                      <div className="pl-6 sm:pl-8">
                        <div className="space-y-4">
                          {message._actionCards?.map((card, cardIndex) => {
                            if (card.status === 'created' && card.createdAgentName) {
                              return (
                                <AgentCreatedCard
                                  key={cardIndex}
                                  agentName={card.createdAgentName}
                                  agentSlug={card.createdAgentSlug}
                                />
                              )
                            }
                            // Skip cards for agents already created by a different card/message
                            if (card.status === 'pending' && alreadyCreated.has(card.config?.name)) {
                              return null
                            }
                            return (
                              <ActionConfirmCard
                                key={cardIndex}
                                config={card.config}
                                status={card.status}
                                onConfirm={(config) => handleConfirm(config, message.id, cardIndex)}
                                onCancel={() => handleCancelAction(message.id, cardIndex)}
                              />
                            )
                          })}

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
        <div className="border-t border-sand bg-white/80 px-4 md:px-8 py-3 flex-shrink-0">
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

  // Auto-resize textarea as content grows
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [value])

  return (
    <div className="relative flex min-h-full items-center justify-center overflow-hidden px-4 py-12 text-center md:px-8 md:py-16">
      <div className="pointer-events-none absolute inset-0 opacity-[0.12]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-32 opacity-70" />

      <div className="relative w-full max-w-4xl">
        <div className="mx-auto max-w-3xl space-y-5">
          <PlatformEngineerMark className="mx-auto h-16 w-16 rounded-[1.45rem] bg-ink text-white shadow-soft" iconClassName="h-7 w-7" />
          <div className="space-y-4">
            <p className="text-[11px] font-semibold text-ash">
              Platform Engineer
            </p>
            <h1 className="text-[clamp(3rem,8vw,6rem)] font-light leading-[0.9] tracking-[-0.075em] text-ink sm:whitespace-nowrap">
              What will <span className="editorial-highlight inline-block">you build?</span>
            </h1>
            <p className="mx-auto max-w-2xl text-sm font-medium text-night sm:text-[0.95rem]">
              Create and manage AI agents through conversation
            </p>
            <p className="mx-auto max-w-xl text-sm leading-6 text-ink-soft md:text-base">
              No code needed.
            </p>
          </div>
        </div>

        <div className="mx-auto mt-10 max-w-3xl text-left">
          <div className="rounded-[2rem] border border-black/10 bg-white px-5 py-4 shadow-soft">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Describe the agent you want to build…"
              rows={3}
              className="w-full resize-none !bg-transparent text-base leading-relaxed text-ink placeholder:text-ash outline-none min-h-[80px] max-h-[320px] overflow-y-auto"
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
                className="flex h-11 w-11 items-center justify-center rounded-[1rem] bg-ink text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isStreaming ? <Loader2 className="h-4 w-4 motion-safe:animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <p className="mt-3 text-center text-[11px] font-semibold text-ash">
            Describe the workflow, tools, or integrations you need
          </p>
        </div>

        <div className="mx-auto mt-8 flex max-w-4xl flex-wrap items-center justify-center gap-2.5">
          {QUICK_ACTIONS.map(({ icon: Icon, label, prompt }) => (
            <button
              key={label}
              disabled={isStreaming}
              onClick={() => onSend(prompt)}
              className="flex items-center gap-2 rounded-full border border-black/10 bg-transparent px-4 py-2.5 text-sm font-medium text-ink-soft transition-colors hover:border-hotpink/45 hover:bg-white/50 hover:text-ink disabled:opacity-50"
            >
              <Icon className="h-3.5 w-3.5 text-ink-mute" />
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
    <div className="rounded-[1.7rem] border border-line bg-white px-4 pt-3 pb-2 shadow-soft transition-shadow hover:shadow-soft">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Ask the Platform Engineer anything…"
        rows={1}
        className="w-full text-sm text-ink placeholder:text-ash resize-none outline-none bg-transparent min-h-[36px] max-h-[120px] overflow-y-auto leading-relaxed"
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
          className="flex h-10 w-10 items-center justify-center rounded-[1rem] bg-ink text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isStreaming ? <Loader2 className="h-4 w-4 motion-safe:animate-spin" /> : <Send className="h-4 w-4" />}
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
      <svg aria-hidden="true" className={iconClassName} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z" />
      </svg>
    </div>
  )
}
