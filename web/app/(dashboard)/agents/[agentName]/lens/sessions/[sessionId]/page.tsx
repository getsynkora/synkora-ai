'use client'

import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft, User, Bot, Wrench, Brain, ChevronDown, ChevronRight,
  CheckCircle, XCircle, Copy, Check, DollarSign, MessageSquare,
  Settings2,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getLensSessionDetail, type LensSessionDetailResponse, type LensTimelineEvent } from '@/lib/api/agent-lens'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

// ---------------------------------------------------------------------------
// Turn model — one turn = one user message + agent reasoning steps + assistant response
// ---------------------------------------------------------------------------

interface Turn {
  id: string
  index: number
  userMessage: LensTimelineEvent | null
  steps: LensTimelineEvent[]      // llm_call + tool_call
  assistantMessage: LensTimelineEvent | null
}

function dedupeEvents(events: LensTimelineEvent[]): LensTimelineEvent[] {
  // ES fire-and-forget can double-index the same event twice (different _id, same content).
  // Deduplicate by (event_type + timestamp) — safe because each event has a precise
  // timestamp and sequence resets per turn, making (type, timestamp) globally unique.
  const seen = new Set<string>()
  return events.filter(e => {
    const key = `${e.event_type}-${e.timestamp ?? e.id}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function buildTurns(events: LensTimelineEvent[]): Turn[] {
  const unique = dedupeEvents(events)
  const turns: Turn[] = []
  let current: Turn | null = null
  let turnIndex = 0

  for (const event of unique) {
    if (event.event_type === 'user_message') {
      if (current) turns.push(current)
      turnIndex++
      current = { id: event.id, index: turnIndex, userMessage: event, steps: [], assistantMessage: null }
    } else if (event.event_type === 'assistant_message') {
      if (!current) {
        turnIndex++
        current = { id: `orphan-${event.id}`, index: turnIndex, userMessage: null, steps: [], assistantMessage: null }
      }
      current.assistantMessage = event
      turns.push(current)
      current = null
    } else {
      // llm_call or tool_call
      if (!current) {
        turnIndex++
        current = { id: `pre-${event.id}`, index: turnIndex, userMessage: null, steps: [], assistantMessage: null }
      }
      current.steps.push(event)
    }
  }

  if (current) turns.push(current)
  return turns
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatTokens(n: number | null | undefined): string {
  if (n == null) return '-'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatLatency(ms: number | null | undefined): string {
  if (ms == null) return '-'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

function formatCost(usd: number | null | undefined): string {
  if (usd == null || usd === 0) return '$0.00'
  if (usd < 0.000001) return '< $0.000001'
  if (usd < 0.0001) return `$${usd.toFixed(6)}`
  if (usd < 0.01) return `$${usd.toFixed(4)}`
  return `$${usd.toFixed(2)}`
}

// ---------------------------------------------------------------------------
// JSON viewer — renders parsed JSON natively so string values show real newlines
// ---------------------------------------------------------------------------

function JsonNode({ value, depth }: { value: unknown; depth: number }): React.ReactElement {
  const [collapsed, setCollapsed] = useState(depth > 2)

  if (value === null) return <span className="text-slate-400">null</span>
  if (typeof value === 'boolean') return <span className="text-amber-700">{String(value)}</span>
  if (typeof value === 'number') return <span className="text-rose-700">{String(value)}</span>

  if (typeof value === 'string') {
    // Render the string with actual newlines — don't re-encode via JSON.stringify
    return value.includes('\n') ? (
      <span className="text-emerald-700">
        {'"'}
        <span className="whitespace-pre-wrap break-words">{value}</span>
        {'"'}
      </span>
    ) : (
      <span className="text-emerald-700">"{value}"</span>
    )
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-slate-400">[]</span>
    return (
      <span>
        <button onClick={() => setCollapsed(c => !c)} className="text-slate-500 transition-colors hover:text-slate-800">
          {collapsed ? `[…${value.length}]` : '['}
        </button>
        {!collapsed && (
          <>
            {value.map((item, i) => (
              <div key={i} className="pl-4">
                <JsonNode value={item} depth={depth + 1} />
                {i < value.length - 1 && <span className="text-slate-400">,</span>}
              </div>
            ))}
            <span>]</span>
          </>
        )}
      </span>
    )
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) return <span className="text-slate-400">{'{}'}</span>
    return (
      <span>
        <button onClick={() => setCollapsed(c => !c)} className="text-slate-500 transition-colors hover:text-slate-800">
          {collapsed ? `{…${entries.length}}` : '{'}
        </button>
        {!collapsed && (
          <>
            {entries.map(([k, v], i) => (
              <div key={k} className="pl-4">
                <span className="text-sky-700">"{k}"</span>
                <span className="text-slate-400">: </span>
                <JsonNode value={v} depth={depth + 1} />
                {i < entries.length - 1 && <span className="text-slate-400">,</span>}
              </div>
            ))}
            <span>{'}'}</span>
          </>
        )}
      </span>
    )
  }

  return <span className="text-slate-600">{String(value)}</span>
}

function JsonDisplay({ jsonStr, maxHeightClass = 'max-h-64' }: { jsonStr: string; maxHeightClass?: string }) {
  const parsed = useMemo(() => {
    try { return { ok: true as const, value: JSON.parse(jsonStr) } }
    catch { return { ok: false as const, value: null } }
  }, [jsonStr])

  if (!parsed.ok) {
    // Not valid JSON — show as plain text (shouldn't happen with fixed backend, but safe fallback)
    return (
      <pre className={`text-[12px] leading-6 text-slate-700 whitespace-pre-wrap break-all overflow-auto ${maxHeightClass}`}>
        {jsonStr}
      </pre>
    )
  }

  // Handle the truncation envelope produced by the backend when content exceeds storage limit
  const value = parsed.value
  if (
    value !== null &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    (value as Record<string, unknown>)._truncated === true
  ) {
    const preview = (value as Record<string, unknown>).preview as string
    const totalChars = (value as Record<string, unknown>).total_chars as number | undefined
    // The preview itself is a JSON fragment — try to parse it, fall back to text
    const previewParsed = (() => { try { return { ok: true, val: JSON.parse(preview) } } catch { return { ok: false, val: null } } })()
    return (
      <div className={`overflow-auto ${maxHeightClass}`}>
        <div className="text-[12px] font-mono leading-6">
          {previewParsed.ok
            ? <JsonNode value={previewParsed.val} depth={0} />
            : <pre className="text-[12px] leading-6 text-slate-700 whitespace-pre-wrap break-all">{preview}</pre>
          }
        </div>
        <div className="mt-2 text-[11px] font-medium text-amber-700">
          [truncated — showing first {preview.length} of {totalChars ?? '?'} chars]
        </div>
      </div>
    )
  }

  return (
    <div className={`text-[12px] font-mono leading-6 overflow-auto ${maxHeightClass}`}>
      <JsonNode value={value} depth={0} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Markdown renderer — for user and assistant message content
// ---------------------------------------------------------------------------

function MarkdownBody({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Inline code
        code({ className, children, ...props }) {
          const isBlock = className?.startsWith('language-')
          return isBlock ? (
            <pre className="my-3 overflow-auto rounded-2xl bg-slate-950 px-4 py-3.5 text-[12px] shadow-inner">
              <code className={`${className} whitespace-pre text-slate-100`} {...props}>
                {children}
              </code>
            </pre>
          ) : (
            <code className="rounded-md border border-rose-200/70 bg-rose-50 px-1.5 py-0.5 text-[12px] font-medium text-rose-700" {...props}>
              {children}
            </code>
          )
        },
        // Tables
        table({ children }) {
          return (
            <div className="my-3 overflow-auto rounded-2xl border border-stone-200 bg-white">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          )
        },
        th({ children }) { return <th className="border border-stone-200 bg-stone-50 px-3 py-2 text-left font-semibold text-slate-700">{children}</th> },
        td({ children }) { return <td className="border border-stone-200 px-3 py-2 text-slate-700">{children}</td> },
        // Lists
        ul({ children }) { return <ul className="my-2 list-disc space-y-1 pl-5 text-[15px] leading-7">{children}</ul> },
        ol({ children }) { return <ol className="my-2 list-decimal space-y-1 pl-5 text-[15px] leading-7">{children}</ol> },
        // Headings (smaller scale inside message bubbles)
        h1({ children }) { return <p className="mb-2 mt-4 text-lg font-semibold tracking-[-0.02em] text-slate-900 first:mt-0">{children}</p> },
        h2({ children }) { return <p className="mb-2 mt-4 text-base font-semibold tracking-[-0.01em] text-slate-900 first:mt-0">{children}</p> },
        h3({ children }) { return <p className="mb-1 mt-3 text-sm font-semibold text-slate-800 first:mt-0">{children}</p> },
        // Paragraph — avoid double margin on simple messages
        p({ children }) { return <p className="my-2 text-[15px] leading-7 text-slate-700">{children}</p> },
        // Bold / italic
        strong({ children }) { return <strong className="font-semibold text-slate-900">{children}</strong> },
        // Blockquote
        blockquote({ children }) {
          return (
            <blockquote className="my-3 rounded-r-2xl border-l-2 border-stone-300 bg-stone-50/80 py-2 pl-4 text-[15px] italic leading-7 text-slate-600">
              {children}
            </blockquote>
          )
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

// ---------------------------------------------------------------------------
// Small shared components
// ---------------------------------------------------------------------------

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={copy}
      title="Copy"
      className="rounded-lg border border-transparent p-1.5 text-slate-400 transition-colors hover:border-stone-200 hover:bg-white hover:text-slate-700"
    >
      {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
    </button>
  )
}

function Badge({ children, variant = 'gray' }: { children: React.ReactNode; variant?: 'gray' | 'purple' | 'green' | 'red' | 'amber' }) {
  const cls = {
    gray: 'border border-stone-200 bg-stone-100/90 text-slate-600',
    purple: 'border border-rose-200 bg-rose-50 text-rose-700',
    green: 'border border-emerald-200 bg-emerald-50 text-emerald-700',
    red: 'border border-red-200 bg-red-50 text-red-700',
    amber: 'border border-amber-200 bg-amber-50 text-amber-700',
  }[variant]
  return <span className={`inline-flex items-center rounded-full px-2 py-1 text-[11px] font-semibold ${cls}`}>{children}</span>
}

// ---------------------------------------------------------------------------
// Expandable message content (handles long messages)
// ---------------------------------------------------------------------------

const MESSAGE_COLLAPSE_THRESHOLD = 400

function MessageContent({ content, bgClass, borderClass }: {
  content: string
  bgClass: string
  borderClass: string
}) {
  const isLong = content.length > MESSAGE_COLLAPSE_THRESHOLD
  const [expanded, setExpanded] = useState(!isLong)

  return (
    <div className={`group relative rounded-xl border ${borderClass} ${bgClass} p-4 text-slate-800 shadow-sm`}>
      <div className={`max-w-none break-words ${!expanded ? 'line-clamp-6' : ''}`}>
        {content ? <MarkdownBody content={content} /> : <span className="text-sm italic text-slate-400">(empty)</span>}
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="mt-3 text-[13px] font-semibold text-rose-700 transition-colors hover:text-rose-800"
        >
          {expanded ? '↑ Show less' : `↓ Show more (${content.length} chars)`}
        </button>
      )}
      <span className="absolute right-3 top-3 opacity-0 transition-opacity group-hover:opacity-100">
        <CopyButton text={content} />
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// User message
// ---------------------------------------------------------------------------

function UserMessageRow({ event }: { event: LensTimelineEvent }) {
  const content = event.content ?? event.content_preview ?? ''
  return (
    <div className="mb-4 flex gap-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-rose-200 bg-rose-100/90 shadow-sm">
        <User size={16} className="text-rose-700" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="mb-3 flex flex-wrap items-center gap-2.5">
          <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-700">User</span>
          <span className="text-[12px] font-mono text-slate-500">{formatTime(event.timestamp)}</span>
          {event.token_count != null && event.token_count > 0 && (
            <Badge>{formatTokens(event.token_count)} tokens</Badge>
          )}
        </div>
        <MessageContent
          content={content}
          bgClass="bg-rose-50/70"
          borderClass="border-rose-100/90"
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Assistant message
// ---------------------------------------------------------------------------

function AssistantMessageRow({ event }: { event: LensTimelineEvent }) {
  const content = event.content ?? event.content_preview ?? ''
  const latency = event.latency_ms ?? event.total_latency_ms
  const cost = event.total_cost_usd ?? event.cost_usd
  const totalTokens = (event.input_tokens ?? 0) + (event.output_tokens ?? 0)
  return (
    <div className="mt-4 flex gap-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-300 bg-slate-900 shadow-sm">
        <Bot size={16} className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="mb-3 flex flex-wrap items-center gap-2.5">
          <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-700">Assistant</span>
          <span className="text-[12px] font-mono text-slate-500">{formatTime(event.timestamp)}</span>
          {totalTokens > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full border border-stone-200 bg-stone-100/90 px-2.5 py-1 text-[11px] font-semibold text-slate-700">
              {formatTokens(totalTokens)} tokens
            </span>
          )}
          {latency != null && (
            <span className="rounded-full border border-stone-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">
              {formatLatency(latency)}
            </span>
          )}
          {cost != null && cost > 0 && (
            <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
              <DollarSign size={10} className="-mt-0.5 mr-0.5" />
              {formatCost(cost)}
            </span>
          )}
        </div>
        <MessageContent
          content={content}
          bgClass="bg-white"
          borderClass="border-stone-200/90"
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// LLM Inputs panel — messages, system prompt, tools sent to the model
// ---------------------------------------------------------------------------

type LLMInputTab = 'messages' | 'system' | 'tools'

function LLMInputsPanel({ event }: { event: LensTimelineEvent }) {
  const hasMessages = !!event.messages_json
  const hasSystem = !!event.system_prompt_preview
  const hasTools = !!event.tools_json

  const defaultTab: LLMInputTab = hasMessages ? 'messages' : hasSystem ? 'system' : 'tools'
  const [tab, setTab] = useState<LLMInputTab>(defaultTab)

  if (!hasMessages && !hasSystem && !hasTools) return null

  const tabs: { id: LLMInputTab; label: string; count?: string }[] = []
  if (hasMessages) {
    let count = ''
    try { count = String(JSON.parse(event.messages_json!).length) } catch { /* */ }
    tabs.push({ id: 'messages', label: 'Messages', count })
  }
  if (hasSystem) tabs.push({ id: 'system', label: 'System Prompt' })
  if (hasTools) {
    let count = ''
    try { count = String(JSON.parse(event.tools_json!).length) } catch { /* */ }
    tabs.push({ id: 'tools', label: 'Tools', count })
  }

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-stone-200 bg-stone-50/80">
      {/* Tab bar */}
      <div className="flex border-b border-stone-200 bg-white/90">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-1 border-b-2 px-4 py-2 text-[11px] font-semibold transition-colors ${
              tab === t.id
                ? 'border-rose-500 text-slate-900'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
            {t.count && (
              <span className="rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px] text-slate-500">{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-2">
        {tab === 'messages' && event.messages_json && (
          <MessagesView jsonStr={event.messages_json} />
        )}
        {tab === 'system' && event.system_prompt_preview && (
          <div className="max-h-80 overflow-auto rounded-lg border border-stone-200 bg-white p-4">
            <MarkdownBody content={event.system_prompt_preview} />
          </div>
        )}
        {tab === 'tools' && event.tools_json && (
          <ToolsView jsonStr={event.tools_json} />
        )}
      </div>
    </div>
  )
}

// Renders tool definitions as structured cards
function ToolsView({ jsonStr }: { jsonStr: string }) {
  const parsed = useMemo(() => {
    try { return { ok: true as const, tools: JSON.parse(jsonStr) as Array<{ name: string; description?: string; parameters?: unknown }> }  }
    catch (e) { return { ok: false as const, error: String(e) } }
  }, [jsonStr])

  if (!parsed.ok) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-[12px] text-red-700">
        Failed to parse tools JSON: {parsed.error}
        <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-all rounded-xl bg-white/70 p-3 text-[11px] text-slate-600">{jsonStr.slice(0, 500)}</pre>
      </div>
    )
  }

  const tools = parsed.tools
  if (!Array.isArray(tools) || tools.length === 0) return <span className="text-[12px] text-slate-400">No tools</span>

  return (
    <div className="max-h-80 space-y-2 overflow-auto">
      {tools.map((tool, i) => (
        <ToolCard key={i} tool={tool} />
      ))}
    </div>
  )
}

function ToolCard({ tool }: { tool: { name: string; description?: string; parameters?: unknown } }) {
  const [paramsOpen, setParamsOpen] = useState(false)
  const hasParams = tool.parameters != null

  return (
    <div className="overflow-hidden rounded-lg border border-stone-200 bg-white">
      {/* Header */}
      <div className="flex items-start gap-3 px-3.5 py-3">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-rose-200 bg-rose-50">
          <Wrench size={12} className="text-rose-700" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-mono text-[12px] font-semibold text-slate-900">{tool.name}</div>
          {tool.description && (
            <div className="mt-1 text-[12px] leading-5 text-slate-500">{tool.description}</div>
          )}
        </div>
        {hasParams && (
          <button
            onClick={() => setParamsOpen(o => !o)}
            className="shrink-0 flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium text-slate-500 transition-colors hover:bg-stone-100 hover:text-slate-700"
          >
            params
            {paramsOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </button>
        )}
      </div>
      {/* Parameters */}
      {paramsOpen && hasParams && (
        <div className="border-t border-stone-200 bg-stone-50/80 px-3.5 py-3">
          <div className="text-[12px] font-mono">
            <JsonNode value={tool.parameters} depth={0} />
          </div>
        </div>
      )}
    </div>
  )
}

// Renders a trimmed conversation history as chat bubbles
function MessagesView({ jsonStr }: { jsonStr: string }) {
  const messages: Array<{ role: string; content: unknown }> = useMemo(() => {
    try { return JSON.parse(jsonStr) } catch { return [] }
  }, [jsonStr])

  if (messages.length === 0) return <span className="text-[12px] text-slate-400">No messages</span>

  return (
    <div className="max-h-80 space-y-2 overflow-auto">
      {messages.map((msg, i) => {
        const role = msg.role || 'unknown'
        const isUser = role === 'user'
        const isAssistant = role === 'assistant'
        const isTool = role === 'tool'
        const contentStr = typeof msg.content === 'string'
          ? msg.content
          : JSON.stringify(msg.content, null, 2)

        const roleCls = isUser
          ? 'border-rose-200 bg-rose-50/85 text-rose-700'
          : isAssistant
            ? 'border-stone-200 bg-white text-slate-700'
            : isTool
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border-stone-200 bg-stone-50 text-slate-600'

        return (
          <div key={i} className={`rounded-2xl border px-3 py-2.5 ${roleCls}`}>
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em]">{role}</div>
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words font-mono text-[12px] leading-6 text-slate-700">
              {contentStr}
            </pre>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// LLM call step (compact inline view inside reasoning panel)
// ---------------------------------------------------------------------------

function LLMCallStep({ event }: { event: LensTimelineEvent }) {
  const [responseExpanded, setResponseExpanded] = useState(event.status === 'error')
  const [inputsExpanded, setInputsExpanded] = useState(false)
  const isError = event.status === 'error'
  const hasInputs = !!(event.messages_json || event.system_prompt_preview || event.tools_json)

  return (
    <div className={`rounded-lg border px-4 py-3.5 text-sm ${
      isError ? 'border-red-200 bg-red-50/60' : 'border-stone-200 bg-white/90'
    }`}>
      <div className="flex flex-wrap items-center gap-2.5">
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${
          isError ? 'border-red-200 bg-red-100/90' : 'border-rose-200 bg-rose-50'
        }`}>
          <Brain size={14} className={isError ? 'text-red-700' : 'text-rose-700'} />
        </div>
        <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isError ? 'text-red-700' : 'text-slate-700'}`}>LLM call</span>
        {event.call_index != null && <span className="font-mono text-[12px] text-slate-500">#{event.call_index}</span>}
        {event.model && (
          <span className="rounded-full border border-stone-200 bg-stone-100/80 px-2.5 py-1 font-mono text-[11px] font-semibold text-slate-700">
            {event.model}
          </span>
        )}
        {/* Token counts — show dashes when 0 so the field is always visible */}
        <span className="text-[12px] text-slate-500">
          <span className="font-semibold text-slate-800">{event.input_tokens != null ? formatTokens(event.input_tokens) : '—'}</span>
          {' '}in
        </span>
        <span className="text-[12px] text-slate-500">
          <span className="font-semibold text-slate-800">{event.output_tokens != null ? formatTokens(event.output_tokens) : '—'}</span>
          {' '}out
        </span>
        {event.latency_ms != null && (
          <span className="rounded-full border border-stone-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">
            {formatLatency(event.latency_ms)}
          </span>
        )}
        {event.cost_usd != null && event.cost_usd > 0 && (
          <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
            <DollarSign size={10} className="mr-0.5" />
            {formatCost(event.cost_usd)}
          </span>
        )}
        {isError && (
          <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-100 px-2.5 py-1 text-[11px] font-semibold text-red-700">
            <XCircle size={10} />error
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {hasInputs && (
            <button
              onClick={() => setInputsExpanded(e => !e)}
              className="flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium text-slate-500 transition-colors hover:bg-stone-100 hover:text-slate-700"
              title="Show LLM inputs"
            >
              <Settings2 size={12} />
              <span>inputs</span>
              {inputsExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </button>
          )}
          {event.response_preview && (
            <button
              onClick={() => setResponseExpanded(e => !e)}
              className="flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium text-slate-500 transition-colors hover:bg-stone-100 hover:text-slate-700"
            >
              <MessageSquare size={12} />
              <span>response</span>
              {responseExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </button>
          )}
        </div>
      </div>
      {isError && event.error && (
        <div className="mt-3 break-words rounded-lg border border-red-200 bg-red-100/80 px-3.5 py-3 text-[13px] text-red-700">
          <span className="font-semibold">Error: </span>{event.error}
        </div>
      )}
      {inputsExpanded && <LLMInputsPanel event={event} />}
      {responseExpanded && event.response_preview && (
        <div className="mt-3 max-h-56 overflow-auto rounded-lg border border-stone-200 bg-stone-50/70 p-4">
          <MarkdownBody content={event.response_preview} />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tool call step (compact inline view inside reasoning panel)
// ---------------------------------------------------------------------------

function ToolCallStep({ event }: { event: LensTimelineEvent }) {
  const isFailed = event.success === false
  const [expanded, setExpanded] = useState(isFailed)

  // Pass raw strings to JsonDisplay — it handles parsing and pretty-printing
  const argsStr = event.tool_args ?? null
  const resultStr = event.tool_result ?? null

  return (
    <div className={`rounded-lg border px-4 py-3.5 text-sm ${
      isFailed ? 'border-red-200 bg-red-50/60' : 'border-stone-200 bg-white/90'
    }`}>
      <div className="flex flex-wrap items-center gap-2.5">
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${
          isFailed ? 'border-red-200 bg-red-100/90' : 'border-emerald-200 bg-emerald-50'
        }`}>
          <Wrench size={14} className={isFailed ? 'text-red-700' : 'text-emerald-700'} />
        </div>
        <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isFailed ? 'text-red-700' : 'text-slate-700'}`}>Tool call</span>
        <span className="font-mono text-[12px] font-semibold text-slate-900">{event.tool_name}</span>
        <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
          isFailed ? 'border-red-200 bg-red-100 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'
        }`}>
          {isFailed ? <XCircle size={10} /> : <CheckCircle size={10} />}
          {isFailed ? 'failed' : 'ok'}
        </span>
        {event.duration_ms != null && (
          <span className="rounded-full border border-stone-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">
            {formatLatency(event.duration_ms)}
          </span>
        )}
        {event.retry_count != null && event.retry_count > 0 && (
          <Badge variant="amber">{event.retry_count} retries</Badge>
        )}
        {(argsStr || resultStr) && (
          <button
            onClick={() => setExpanded(e => !e)}
            className="ml-auto flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium text-slate-500 transition-colors hover:bg-stone-100 hover:text-slate-700"
          >
            {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            args / result
          </button>
        )}
      </div>
      {isFailed && event.error_message && (
        <div className="mt-3 break-words rounded-lg border border-red-200 bg-red-100/80 px-3.5 py-3 text-[13px] text-red-700">
          <span className="font-semibold">Error: </span>{event.error_message}
        </div>
      )}
      {expanded && (
        <div className="mt-3 space-y-3">
          {argsStr && (
            <div>
              <div className="mb-1 flex items-center gap-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Args</span>
                <CopyButton text={argsStr} />
              </div>
              <div className="rounded-lg border border-stone-200 bg-white p-3">
                <JsonDisplay jsonStr={argsStr} maxHeightClass="max-h-48" />
              </div>
            </div>
          )}
          {resultStr && (
            <div>
              <div className="mb-1 flex items-center gap-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Result</span>
                <CopyButton text={resultStr} />
              </div>
              <div className={`rounded-lg border p-3 ${isFailed ? 'border-red-200 bg-red-50/70' : 'border-stone-200 bg-white'}`}>
                <JsonDisplay jsonStr={resultStr} maxHeightClass="max-h-48" />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Reasoning panel — collapsible, sits between user and assistant messages
// ---------------------------------------------------------------------------

function ReasoningPanel({ steps }: { steps: LensTimelineEvent[] }) {
  const hasFailures = steps.some(s =>
    (s.event_type === 'tool_call' && s.success === false) ||
    (s.event_type === 'llm_call' && s.status === 'error')
  )
  const [open, setOpen] = useState(hasFailures)

  const llmCount = steps.filter(s => s.event_type === 'llm_call').length
  const toolCount = steps.filter(s => s.event_type === 'tool_call').length
  const stepCost = steps.reduce((sum, s) => sum + (s.cost_usd ?? 0), 0)
  const stepLatency = steps.reduce((sum, s) => sum + (s.latency_ms ?? s.duration_ms ?? 0), 0)

  const summaryParts: string[] = []
  if (llmCount > 0) summaryParts.push(`${llmCount} LLM call${llmCount !== 1 ? 's' : ''}`)
  if (toolCount > 0) summaryParts.push(`${toolCount} tool call${toolCount !== 1 ? 's' : ''}`)

  return (
    <div className="my-4 sm:ml-14">
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex w-full flex-wrap items-center gap-2.5 rounded-lg border px-4 py-3 text-left transition-all ${
          hasFailures
            ? 'border-red-200 bg-red-50/70 text-red-700 hover:bg-red-100/80'
            : 'border-stone-200 bg-stone-50/80 text-slate-700 hover:bg-white'
        }`}
      >
        <ChevronRight
          size={15}
          className={`shrink-0 text-slate-400 transition-transform duration-200 ${open ? 'rotate-90' : ''}`}
        />
        <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Reasoning</span>
        <span className="text-[13px] font-semibold text-slate-800">{summaryParts.join(' · ') || 'Agent reasoning steps'}</span>
        {stepLatency > 0 && (
          <span className="font-mono text-[12px] text-slate-500">{formatLatency(stepLatency)}</span>
        )}
        {stepCost > 0 && (
          <span className={`inline-flex items-center text-[12px] font-semibold ${hasFailures ? 'text-red-600' : 'text-emerald-700'}`}>
            <DollarSign size={10} className="-mt-0.5" />
            {formatCost(stepCost)}
          </span>
        )}
        {hasFailures && (
          <span className="ml-1 inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-100 px-2.5 py-1 text-[11px] font-semibold text-red-700">
            <XCircle size={10} /> failures
          </span>
        )}
      </button>

      {open && (
        <div className="mt-3 space-y-3 pl-1">
          {steps.map((step, i) =>
            step.event_type === 'llm_call'
              ? <LLMCallStep key={`${step.id}-${i}`} event={step} />
              : <ToolCallStep key={`${step.id}-${i}`} event={step} />
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Turn card — one user→agent interaction
// ---------------------------------------------------------------------------

function TurnCard({ turn }: { turn: Turn }) {
  const [open, setOpen] = useState(true)

  return (
    <div className="mb-6 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      {/* Turn header strip */}
      <button
        onClick={() => setOpen(v => !v)}
        className={`flex w-full items-center gap-3 bg-gray-50 px-5 py-3 text-left transition-colors hover:bg-gray-100 ${
          open ? 'border-b border-gray-200' : ''
        }`}
      >
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-900">
          <span className="text-[11px] font-bold text-white">{turn.index}</span>
        </div>
        <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
          Interaction {turn.index}
        </span>
        {turn.userMessage && (
          <span className="text-[12px] font-mono text-slate-500">{formatTime(turn.userMessage.timestamp)}</span>
        )}
        <span className="ml-auto inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600">
          {open ? 'Collapse' : 'Expand'}
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
      </button>

      {open && (
        <div className="px-5 py-5">
          {/* User message */}
          {turn.userMessage && <UserMessageRow event={turn.userMessage} />}

          {/* Agent reasoning steps */}
          {turn.steps.length > 0 && <ReasoningPanel steps={turn.steps} />}

          {/* Assistant response */}
          {turn.assistantMessage && <AssistantMessageRow event={turn.assistantMessage} />}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Summary bar
// ---------------------------------------------------------------------------

function SummaryBar({ detail, llmCallCount, toolCallCount, failureCount }: {
  detail: LensSessionDetailResponse
  llmCallCount: number
  toolCallCount: number
  failureCount: number
}) {
  const stats = [
    { label: 'Total tokens', value: formatTokens(detail.total_tokens), sub: `${formatTokens(detail.input_tokens)} in / ${formatTokens(detail.output_tokens)} out`, accent: 'bg-rose-500' },
    { label: 'Total cost', value: formatCost(detail.total_cost_usd), sub: detail.total_cost_usd > 0 ? `$${(detail.total_cost_usd / Math.max(detail.message_count, 1)).toFixed(4)}/turn` : 'no cost', accent: 'bg-emerald-500', highlight: detail.total_cost_usd > 0 },
    { label: 'Interactions', value: String(detail.message_count), sub: 'user turns', accent: 'bg-slate-600' },
    { label: 'LLM calls', value: String(llmCallCount), sub: 'total completions', accent: 'bg-sky-500' },
    { label: 'Tool calls', value: String(toolCallCount), sub: failureCount > 0 ? `${failureCount} failed` : 'all succeeded', accent: failureCount > 0 ? 'bg-red-500' : 'bg-teal-500', error: failureCount > 0 },
    { label: 'Avg per turn', value: llmCallCount > 0 ? `${(llmCallCount / Math.max(detail.message_count, 1)).toFixed(1)}` : '—', sub: 'LLM calls/turn', accent: 'bg-amber-500' },
  ]
  return (
    <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {stats.map((s, i) => (
        <div
          key={i}
          className="relative overflow-hidden rounded-lg border border-gray-200 bg-white px-4 py-4"
        >
          <div className={`absolute inset-x-0 top-0 h-1 ${s.accent}`} />
          <div className="relative">
            <div className="mb-3 flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${s.accent}`} />
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{s.label}</p>
            </div>
            <p className={`mb-2 text-[28px] font-bold leading-none tracking-[-0.04em] ${s.error ? 'text-red-700' : s.highlight ? 'text-emerald-700' : 'text-slate-900'}`}>{s.value}</p>
            <p className="text-[12px] leading-5 text-slate-500">{s.sub}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SessionDetailPage() {
  const params = useParams()
  const agentSlug = params.agentName as string
  const sessionId = params.sessionId as string

  const [detail, setDetail] = useState<LensSessionDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newestFirst, setNewestFirst] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getLensSessionDetail(agentSlug, sessionId)
      setDetail(data)
    } catch (e: unknown) {
      setError((e as Error)?.message || 'Failed to load session')
    } finally {
      setLoading(false)
    }
  }, [agentSlug, sessionId])

  useEffect(() => { load() }, [load])

  const timeline = detail?.timeline ?? []
  const allTurns = buildTurns(timeline)
  const turns = newestFirst ? [...allTurns].reverse() : allTurns

  const failureCount = timeline.filter(e =>
    (e.event_type === 'tool_call' && e.success === false) ||
    (e.event_type === 'llm_call' && e.status === 'error')
  ).length
  const llmCallCount = timeline.filter(e => e.event_type === 'llm_call').length
  const toolCallCount = timeline.filter(e => e.event_type === 'tool_call').length

  return (
    <AgentPageShell
      agentName={agentSlug}
      title={detail?.name ?? 'Session Detail'}
      description={
        detail?.created_at
          ? `Captured ${new Date(detail.created_at).toLocaleString()}`
          : 'Inspect the full event timeline for this session.'
      }
      icon={MessageSquare}
      badge="Analytics"
      maxWidthClassName="max-w-[88rem]"
      actions={
        <button
          onClick={() => setNewestFirst(v => !v)}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-[1rem] border border-black/10 bg-white/80 px-4 py-3 text-sm font-semibold text-gray-600 transition-colors hover:bg-white hover:text-gray-900"
        >
          {newestFirst ? '↓ Newest first' : '↑ Oldest first'}
        </button>
      }
    >
      {error ? (
        <AgentPagePanel className="mb-6 border-[#eed6dd] bg-[linear-gradient(180deg,_rgba(252,245,247,0.98),_rgba(249,236,240,0.96))] p-4">
          <p className="text-sm font-medium text-[#8a445c]">{error}</p>
        </AgentPagePanel>
      ) : null}

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="text-center">
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-slate-900 border-t-transparent" />
            <p className="text-sm font-medium text-slate-500">Loading session...</p>
          </div>
        </div>
      ) : detail ? (
        <>
          <SummaryBar
            detail={detail}
            llmCallCount={llmCallCount}
            toolCallCount={toolCallCount}
            failureCount={failureCount}
          />

          {turns.length === 0 ? (
            <AgentPagePanel className="py-24 text-center">
              <p className="text-sm font-medium text-slate-400">No events recorded in this session</p>
            </AgentPagePanel>
          ) : (
            <div className="space-y-0">
              {turns.map(turn => (
                <TurnCard key={turn.id} turn={turn} />
              ))}
            </div>
          )}
        </>
      ) : null}
    </AgentPageShell>
  )
}
