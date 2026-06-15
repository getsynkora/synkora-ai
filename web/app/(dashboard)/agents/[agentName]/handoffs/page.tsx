'use client'

import { useEffect, useState, useCallback, use } from 'react'
import { MessageCircle, CheckCircle, RefreshCw, User, Clock, ArrowRightLeft, Send } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

interface Handoff {
  id: string
  agent_id: string | null
  name: string
  handoff_status: string
  handoff_at: string | null
  handoff_summary: string | null
  source: string | null
  external_user_name: string | null
  external_user_email: string | null
  message_count: number
  last_activity_at: string | null
}

interface Message {
  id: string
  role: string
  content: string
  created_at: string | null
}

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function HandoffCard({
  handoff,
  onResolved,
}: {
  handoff: Handoff
  agentName: string
  onResolved: () => void
}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [reply, setReply] = useState('')
  const [sending, setSending] = useState(false)
  const [resolving, setResolving] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadMessages = useCallback(async () => {
    setLoadingMessages(true)
    try {
      const { apiClient } = await import('@/lib/api/client')
      // API returns AgentResponse: { success, data: { messages: [...] } }
      const resp = await apiClient.request('GET', `/api/v1/agents/conversations/${handoff.id}/messages?limit=50`)
      const msgs = resp?.data?.messages ?? resp?.messages
      if (Array.isArray(msgs)) setMessages(msgs)
    } catch {
      // silent — error already shown via the card-level error state
    } finally {
      setLoadingMessages(false)
    }
  }, [handoff.id])

  useEffect(() => {
    if (expanded) loadMessages()
  }, [expanded, loadMessages])

  async function sendReply() {
    if (!reply.trim()) return
    setSending(true)
    setError(null)
    try {
      const { apiClient } = await import('@/lib/api/client')
      await apiClient.request('POST', `/api/v1/conversations/${handoff.id}/handoff/reply`, {
        message: reply.trim(),
      })
      setReply('')
      await loadMessages()
    } catch {
      setError('Failed to send reply')
    } finally {
      setSending(false)
    }
  }

  async function resolve() {
    setResolving(true)
    try {
      const { apiClient } = await import('@/lib/api/client')
      await apiClient.request('POST', `/api/v1/conversations/${handoff.id}/handoff/resolve`)
      onResolved()
    } catch {
      setError('Failed to resolve')
    } finally {
      setResolving(false)
    }
  }

  const roleBubble = (role: string) => {
    const r = role.toLowerCase()
    if (r === 'user') return 'bg-[#171717] text-white self-end'
    if (r === 'operator') return 'bg-emerald-600 text-white self-end'
    return 'bg-white border border-[#e5d9ca] text-gray-800 self-start'
  }

  const isDarkBubble = (role: string) => {
    const r = role.toLowerCase()
    return r === 'user' || r === 'operator'
  }

  const roleLabel = (role: string) => {
    const r = role.toLowerCase()
    if (r === 'user') return 'User'
    if (r === 'operator') return 'You'
    return 'Agent'
  }

  return (
    <AgentPagePanel>
      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 min-w-0">
            <div className="rounded-full bg-amber-100 p-2 flex-shrink-0">
              <User className="w-4 h-4 text-amber-700" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-gray-900">
                  {handoff.external_user_name || 'Anonymous User'}
                </span>
                {handoff.external_user_email && (
                  <span className="text-xs text-gray-500">{handoff.external_user_email}</span>
                )}
              </div>
              {handoff.handoff_summary && (
                <p className="mt-1 text-sm text-gray-600 leading-snug">{handoff.handoff_summary}</p>
              )}
              <div className="mt-1.5 flex items-center gap-3 text-xs text-gray-400">
                <span className="flex items-center gap-1">
                  <MessageCircle className="w-3 h-3" />
                  {handoff.message_count} messages
                </span>
                {handoff.source && <span>via {handoff.source}</span>}
                {handoff.handoff_at && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {timeAgo(handoff.handoff_at)}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={() => setExpanded(e => !e)}
              className="px-3 py-1.5 text-xs font-medium rounded-[0.35rem] border border-[#dbcdb9] bg-white hover:bg-[#f7f2e7] text-gray-700 transition-colors"
            >
              {expanded ? 'Hide' : 'Open'}
            </button>
            <button
              onClick={resolve}
              disabled={resolving}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-[0.35rem] bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              <CheckCircle className="w-3.5 h-3.5" />
              {resolving ? 'Resolving…' : 'Resolve'}
            </button>
          </div>
        </div>

        {error && (
          <p className="mt-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded-[0.35rem] px-3 py-2">
            {error}
          </p>
        )}

        {expanded && (
          <div className="mt-4 space-y-3 border-t border-[#e5d9ca] pt-4">
            {/* Message thread */}
            <div className="max-h-72 overflow-y-auto flex flex-col gap-2 rounded-[0.45rem] bg-[#faf7f2] border border-[#e5d9ca] p-3">
              {loadingMessages ? (
                <p className="text-xs text-gray-400 text-center py-6">Loading messages…</p>
              ) : messages.length === 0 ? (
                <p className="text-xs text-gray-400 text-center py-6">No messages yet.</p>
              ) : (
                messages.map(msg => (
                  <div
                    key={msg.id}
                    className={`flex flex-col max-w-[78%] ${
                      msg.role.toLowerCase() === 'user' || msg.role.toLowerCase() === 'operator'
                        ? 'ml-auto items-end'
                        : 'items-start'
                    }`}
                  >
                    <span className="text-[10px] text-gray-400 mb-0.5 px-1">{roleLabel(msg.role)}</span>
                    <div className={`rounded-[0.4rem] px-3 py-2 text-xs leading-relaxed ${roleBubble(msg.role)}`}>
                      <div className={`prose prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 prose-p:my-1 prose-pre:my-1 prose-ul:my-1 prose-ol:my-1 prose-headings:my-1 ${isDarkBubble(msg.role) ? 'prose-invert' : 'prose-gray'}`}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Reply input */}
            <div className="flex gap-2">
              <textarea
                rows={2}
                value={reply}
                onChange={e => setReply(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendReply()
                  }
                }}
                placeholder="Type your reply… (Enter to send, Shift+Enter for new line)"
                className="flex-1 rounded-[0.4rem] border border-[#dbcdb9] bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#171717]/20 focus:border-[#c8b89a] resize-none"
              />
              <button
                onClick={sendReply}
                disabled={sending || !reply.trim()}
                className="flex items-center gap-1.5 px-4 py-2 rounded-[0.4rem] bg-[#171717] text-white text-sm font-medium hover:bg-gray-800 disabled:opacity-40 transition-colors self-end"
              >
                <Send className="w-3.5 h-3.5" />
                {sending ? '…' : 'Send'}
              </button>
            </div>
          </div>
        )}
      </div>
    </AgentPagePanel>
  )
}

export default function HandoffsPage({ params }: { params: Promise<{ agentName: string }> }) {
  const { agentName } = use(params)
  const [handoffs, setHandoffs] = useState<Handoff[]>([])
  const [loading, setLoading] = useState(true)

  const fetchHandoffs = useCallback(async () => {
    try {
      const { apiClient } = await import('@/lib/api/client')
      const data = await apiClient.request('GET', '/api/v1/conversations/handoffs')
      if (Array.isArray(data)) setHandoffs(data)
    } catch {
      setHandoffs([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHandoffs()
    const interval = setInterval(fetchHandoffs, 10_000)
    return () => clearInterval(interval)
  }, [fetchHandoffs])

  const decodedName = decodeURIComponent(agentName)

  return (
    <AgentPageShell
      agentName={agentName}
      title="Human Handoffs"
      description={`Active conversations waiting for your response from agent "${decodedName}"`}
      icon={ArrowRightLeft}
      badge="Support Inbox"
      backHref={`/agents/${agentName}/view`}
      backLabel="Back to Agent"
      stats={[
        {
          label: 'Waiting',
          value: loading ? '—' : handoffs.length,
        },
      ]}
      actions={
        <button
          onClick={fetchHandoffs}
          className="inline-flex items-center gap-2 rounded-[0.35rem] border border-[#dbcdb9] bg-white/80 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:border-[#cdb79d] hover:text-gray-900"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      }
    >
      {loading ? (
        <AgentPagePanel className="flex items-center justify-center py-20">
          <div className="w-6 h-6 border-2 border-gray-300 border-t-gray-700 rounded-full animate-spin" />
        </AgentPagePanel>
      ) : handoffs.length === 0 ? (
        <AgentPagePanel className="py-20 text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-[#f3ecde] flex items-center justify-center mb-4">
            <MessageCircle className="w-6 h-6 text-[#7c5d45]" />
          </div>
          <p className="text-sm font-medium text-gray-700">No active handoffs</p>
          <p className="text-xs text-gray-400 mt-1 max-w-xs mx-auto">
            When a user requests human support the agent will transfer the conversation here.
          </p>
        </AgentPagePanel>
      ) : (
        <div className="space-y-4">
          {handoffs.map(h => (
            <HandoffCard
              key={h.id}
              handoff={h}
              agentName={agentName}
              onResolved={fetchHandoffs}
            />
          ))}
        </div>
      )}
    </AgentPageShell>
  )
}
