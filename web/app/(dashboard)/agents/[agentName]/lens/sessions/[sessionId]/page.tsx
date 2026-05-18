'use client'

import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { createPortal } from 'react-dom'
import {
  ArrowLeft, User, Bot, Wrench, Brain, ChevronDown, ChevronRight,
  CheckCircle, XCircle, Copy, Check, DollarSign, MessageSquare,
  Settings2, Scissors, AlertTriangle, GitBranch, ArrowRight, Clock3, Sparkles,
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
        {(event.cache_read_tokens != null && event.cache_read_tokens > 0) && (
          <span className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold text-sky-700"
            title="Prompt cache read tokens (cheaper)">
            cached {formatTokens(event.cache_read_tokens)}
          </span>
        )}
        {event.context_utilization_pct != null && (
          <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
            event.context_utilization_pct >= 80
              ? 'border-red-200 bg-red-50 text-red-700'
              : event.context_utilization_pct >= 60
              ? 'border-amber-200 bg-amber-50 text-amber-700'
              : 'border-stone-200 bg-stone-50 text-slate-600'
          }`} title="Context window utilization">
            ctx {event.context_utilization_pct.toFixed(0)}%
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
// Tool pruning step — shows compaction event inline
// ---------------------------------------------------------------------------

function ToolPruningStep({ event }: { event: LensTimelineEvent }) {
  const hasDataWarning = (event.data_bearing_pruned ?? 0) > 0
  const pruned = event.tool_results_pruned ?? 0
  const total = event.tool_results_count ?? 0
  const tokensSaved = event.estimated_tokens_saved ?? 0
  const charsSaved = event.chars_saved ?? 0

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${
      hasDataWarning ? 'border-amber-300 bg-amber-50/70' : 'border-dashed border-stone-300 bg-stone-50/60'
    }`}>
      <div className="flex flex-wrap items-center gap-2.5">
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${
          hasDataWarning ? 'border-amber-300 bg-amber-100' : 'border-stone-300 bg-stone-100'
        }`}>
          <Scissors size={13} className={hasDataWarning ? 'text-amber-700' : 'text-slate-500'} />
        </div>
        <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${
          hasDataWarning ? 'text-amber-700' : 'text-slate-500'
        }`}>Context compacted</span>

        {total > 0 && (
          <span className="rounded-full border border-stone-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">
            {pruned}/{total} results pruned
          </span>
        )}

        {tokensSaved > 0 && (
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
            ~{formatTokens(tokensSaved)} tokens saved
          </span>
        )}

        {charsSaved > 0 && (
          <span className="text-[12px] text-slate-500">
            ({charsSaved.toLocaleString()} chars)
          </span>
        )}

        {hasDataWarning && (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-100 px-2.5 py-1 text-[11px] font-semibold text-amber-800">
            <AlertTriangle size={10} />
            {event.data_bearing_pruned} data result{(event.data_bearing_pruned ?? 0) > 1 ? 's' : ''} trimmed
          </span>
        )}

        {event.turn_index != null && (
          <span className="ml-auto text-[11px] text-slate-400 font-mono">turn {event.turn_index}</span>
        )}
      </div>

      {hasDataWarning && (
        <p className="mt-2 text-[12px] text-amber-700 leading-5">
          Data-bearing tool results (SQL rows, file contents) were trimmed to fit context window.
          The LLM may need to re-query to access the full data.
        </p>
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
  const hasPruning = steps.some(s => s.event_type === 'tool_pruning')
  const hasDataWarning = steps.some(s => s.event_type === 'tool_pruning' && (s.data_bearing_pruned ?? 0) > 0)
  const [open, setOpen] = useState(hasFailures || hasDataWarning)

  const llmCount = steps.filter(s => s.event_type === 'llm_call').length
  const toolCount = steps.filter(s => s.event_type === 'tool_call').length
  const pruningCount = steps.filter(s => s.event_type === 'tool_pruning').length
  const stepCost = steps.reduce((sum, s) => sum + (s.cost_usd ?? 0), 0)
  const stepLatency = steps.reduce((sum, s) => sum + (s.latency_ms ?? s.duration_ms ?? 0), 0)

  const summaryParts: string[] = []
  if (llmCount > 0) summaryParts.push(`${llmCount} LLM call${llmCount !== 1 ? 's' : ''}`)
  if (toolCount > 0) summaryParts.push(`${toolCount} tool call${toolCount !== 1 ? 's' : ''}`)
  if (pruningCount > 0) summaryParts.push(`${pruningCount} compaction${pruningCount !== 1 ? 's' : ''}`)

  const borderCls = hasDataWarning
    ? 'border-amber-200 bg-amber-50/60 hover:bg-amber-100/60'
    : hasFailures
    ? 'border-red-200 bg-red-50/70 hover:bg-red-100/80'
    : 'border-stone-200 bg-stone-50/80 hover:bg-white'

  return (
    <div className="my-4 sm:ml-14">
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex w-full flex-wrap items-center gap-2.5 rounded-lg border px-4 py-3 text-left transition-all ${borderCls}`}
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
        {hasPruning && (
          <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
            hasDataWarning
              ? 'border-amber-300 bg-amber-100 text-amber-800'
              : 'border-stone-200 bg-stone-100 text-slate-600'
          }`}>
            <Scissors size={10} />
            {hasDataWarning ? 'data trimmed' : 'compacted'}
          </span>
        )}
      </button>

      {open && (
        <div className="mt-3 space-y-3 pl-1">
          {steps.map((step, i) =>
            step.event_type === 'llm_call'
              ? <LLMCallStep key={`${step.id}-${i}`} event={step} />
              : step.event_type === 'tool_pruning'
              ? <ToolPruningStep key={`${step.id}-${i}`} event={step} />
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
  const [vizOpen, setVizOpen] = useState(false)

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
        <span className="ml-auto flex items-center gap-1.5">
          <span
            role="button"
            tabIndex={0}
            onClick={e => { e.stopPropagation(); setVizOpen(true) }}
            onKeyDown={e => e.key === 'Enter' && (e.stopPropagation(), setVizOpen(true))}
            className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:border-gray-300 hover:bg-gray-50 hover:text-slate-900 transition-colors"
          >
            <GitBranch size={11} />
            Visualize
          </span>
          <span className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600">
            {open ? 'Collapse' : 'Expand'}
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
        </span>
      </button>

      {open && (
        <div className="px-5 py-5">
          {turn.userMessage && <UserMessageRow event={turn.userMessage} />}
          {turn.steps.length > 0 && <ReasoningPanel steps={turn.steps} />}
          {turn.assistantMessage && <AssistantMessageRow event={turn.assistantMessage} />}
        </div>
      )}

      {vizOpen && <TurnFlowModal turn={turn} onClose={() => setVizOpen(false)} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Per-turn flow modal
// ---------------------------------------------------------------------------

const NODE_CFG: Record<string, { bg: string; border: string; dot: string; badge: string; glow: string; soft: string; Icon: React.ElementType }> = {
  user_message:      { bg: '#fff1f2', border: '#fda4af', dot: '#e11d48', glow: 'rgba(225,29,72,0.28)', soft: 'rgba(225,29,72,0.12)', badge: 'User',      Icon: User },
  llm_call:          { bg: '#f0f9ff', border: '#93c5fd', dot: '#2563eb', glow: 'rgba(37,99,235,0.28)', soft: 'rgba(37,99,235,0.12)', badge: 'LLM',       Icon: Brain },
  tool_call:         { bg: '#f0fdf4', border: '#86efac', dot: '#16a34a', glow: 'rgba(22,163,74,0.28)', soft: 'rgba(22,163,74,0.12)', badge: 'Tool',      Icon: Wrench },
  assistant_message: { bg: '#f8fafc', border: '#cbd5e1', dot: '#64748b', glow: 'rgba(100,116,139,0.24)', soft: 'rgba(148,163,184,0.12)', badge: 'Response',  Icon: Bot },
  tool_pruning:      { bg: '#fffbeb', border: '#fcd34d', dot: '#d97706', glow: 'rgba(217,119,6,0.28)', soft: 'rgba(217,119,6,0.12)', badge: 'Compacted', Icon: Scissors },
}
const NODE_DEF = { bg: '#f8fafc', border: '#e2e8f0', dot: '#94a3b8', glow: 'rgba(148,163,184,0.24)', soft: 'rgba(148,163,184,0.12)', badge: 'Event', Icon: Brain }
function ncfg(type: string) { return NODE_CFG[type] ?? NODE_DEF }

type LensFlowView = 'swimlane' | 'graph' | 'trace'
type LaneId = 'user' | 'agent' | 'tool' | 'response' | 'system'

interface FlowNodeMeta {
  lane: LaneId
  laneLabel: string
  actorLabel: string
  cycle: number
  transitionLabel: string
}

const LANE_META: Array<{
  id: LaneId
  label: string
  accent: string
  soft: string
  border: string
}> = [
  { id: 'user', label: 'User', accent: '#e11d48', soft: 'rgba(225,29,72,0.08)', border: 'rgba(225,29,72,0.22)' },
  { id: 'agent', label: 'LLM / Agent', accent: '#2563eb', soft: 'rgba(37,99,235,0.08)', border: 'rgba(37,99,235,0.22)' },
  { id: 'tool', label: 'Tools / Functions', accent: '#16a34a', soft: 'rgba(22,163,74,0.08)', border: 'rgba(22,163,74,0.22)' },
  { id: 'response', label: 'Response', accent: '#64748b', soft: 'rgba(100,116,139,0.08)', border: 'rgba(100,116,139,0.18)' },
  { id: 'system', label: 'System', accent: '#d97706', soft: 'rgba(217,119,6,0.08)', border: 'rgba(217,119,6,0.18)' },
]

const LANE_INDEX = Object.fromEntries(
  LANE_META.map((lane, index) => [lane.id, index])
) as Record<LaneId, number>

function eventLane(event: LensTimelineEvent): LaneId {
  switch (event.event_type) {
    case 'user_message':
      return 'user'
    case 'llm_call':
      return 'agent'
    case 'tool_call':
      return 'tool'
    case 'assistant_message':
      return 'response'
    case 'tool_pruning':
      return 'system'
    default:
      return 'system'
  }
}

function laneLabel(lane: LaneId): string {
  return LANE_META.find((item) => item.id === lane)?.label || lane
}

function actorLabel(event: LensTimelineEvent, lane: LaneId): string {
  if (event.event_type === 'llm_call') {
    return event.model ? event.model.replace(/^(anthropic|openai|google)\//i, '') : 'Primary agent'
  }
  if (event.event_type === 'tool_call') {
    return event.tool_name ? event.tool_name.replace(/^internal_/, '') : 'Function call'
  }
  if (event.event_type === 'assistant_message') return 'Assistant response'
  if (event.event_type === 'tool_pruning') return 'Context compaction'
  return laneLabel(lane)
}

function transitionLabel(fromLane: LaneId | null, toLane: LaneId): string {
  if (!fromLane || fromLane === toLane) {
    if (toLane === 'agent') return 'continued reasoning'
    if (toLane === 'tool') return 'continued tool chain'
    if (toLane === 'response') return 'response stream'
    return 'timeline step'
  }
  if (fromLane === 'user' && toLane === 'agent') return 'request -> reasoning'
  if (fromLane === 'agent' && toLane === 'tool') return 'tool dispatch'
  if (fromLane === 'tool' && toLane === 'agent') return 'tool feedback'
  if (fromLane === 'agent' && toLane === 'response') return 'final synthesis'
  if (fromLane === 'tool' && toLane === 'response') return 'tool result -> response'
  if (fromLane === 'agent' && toLane === 'system') return 'context trim'
  if (fromLane === 'system' && toLane === 'agent') return 'resume after compaction'
  return `${laneLabel(fromLane)} -> ${laneLabel(toLane)}`
}

function buildFlowMeta(nodes: LensTimelineEvent[]): Record<string, FlowNodeMeta> {
  const meta: Record<string, FlowNodeMeta> = {}
  let cycle = 0
  let previousLane: LaneId | null = null

  nodes.forEach((event) => {
    const lane = eventLane(event)
    if (event.event_type === 'user_message') {
      cycle = 0
    } else if (event.event_type === 'llm_call') {
      cycle += 1
    }

    meta[event.id] = {
      lane,
      laneLabel: laneLabel(lane),
      actorLabel: actorLabel(event, lane),
      cycle,
      transitionLabel: transitionLabel(previousLane, lane),
    }

    previousLane = lane
  })

  return meta
}

function flowCurvePath(fromX: number, fromY: number, toX: number, toY: number) {
  const control = Math.max(Math.abs(toX - fromX) * 0.44, 54)
  return `M ${fromX} ${fromY} C ${fromX + control} ${fromY}, ${toX - control} ${toY}, ${toX} ${toY}`
}

// ── Node label helpers ─────────────────────────────────────────────────────────
function nodeLabel(e: LensTimelineEvent): string {
  const trunc = (s: string, n = 48) => s.length > n ? s.slice(0, n - 1) + '…' : s
  switch (e.event_type) {
    case 'user_message':
      return trunc(e.content ?? e.content_preview ?? 'User message')
    case 'assistant_message':
      return trunc(e.content ?? e.content_preview ?? e.response_preview ?? 'Assistant response')
    case 'llm_call':
      return e.model
        ? `LLM · ${e.model.replace(/^(anthropic|openai|google)\//i, '')}`
        : `LLM call${e.call_index != null ? ` #${e.call_index}` : ''}`
    case 'tool_call':
      return e.tool_name ? e.tool_name.replace(/^internal_/, '') : 'Tool call'
    case 'tool_pruning':
      return `Compaction · ${e.tool_results_pruned ?? '?'}/${e.tool_results_count ?? '?'} trimmed`
    default:
      return (e.event_type as string).replace(/_/g, ' ')
  }
}

function nodeSub(e: LensTimelineEvent): string {
  switch (e.event_type) {
    case 'llm_call':
      return [
        e.input_tokens != null ? `${formatTokens(e.input_tokens)} in` : '',
        e.output_tokens != null ? `${formatTokens(e.output_tokens)} out` : '',
        e.latency_ms != null ? formatLatency(e.latency_ms) : '',
        e.cost_usd != null && e.cost_usd > 0 ? formatCost(e.cost_usd) : '',
      ].filter(Boolean).join(' · ')
    case 'tool_call':
      return [
        e.success === false ? '✗ failed' : '✓ ok',
        e.duration_ms != null ? formatLatency(e.duration_ms) : '',
      ].filter(Boolean).join(' · ')
    case 'user_message':
      return e.token_count != null ? `${e.token_count} tokens` : ''
    case 'assistant_message':
      return e.total_cost_usd != null && e.total_cost_usd > 0 ? formatCost(e.total_cost_usd) : ''
    case 'tool_pruning':
      return e.estimated_tokens_saved != null
        ? `~${formatTokens(e.estimated_tokens_saved)} tokens saved${(e.data_bearing_pruned ?? 0) > 0 ? ' · data trimmed ⚠' : ''}`
        : ''
    default:
      return ''
  }
}

function nodePreview(e: LensTimelineEvent): string {
  const trunc = (s: string, n = 72) => s.length > n ? `${s.slice(0, n - 1)}…` : s
  if (e.event_type === 'user_message' || e.event_type === 'assistant_message') {
    const content = e.content ?? e.content_preview ?? e.response_preview
    return content ? trunc(content) : nodeSub(e)
  }
  if (e.event_type === 'tool_call') {
    const preview = e.tool_result ?? e.tool_args
    return preview ? trunc(preview) : nodeSub(e)
  }
  return nodeSub(e)
}

// ── Node detail panel (shown inline below the flow) ────────────────────────────
function NodeDetailPanel({
  event,
  onClose,
  currentIndex,
  total,
  onSelectPrev,
  onSelectNext,
  meta,
}: {
  event: LensTimelineEvent
  onClose: () => void
  currentIndex: number
  total: number
  onSelectPrev: () => void
  onSelectNext: () => void
  meta: FlowNodeMeta
}) {
  const cfg = ncfg(event.event_type as string)
  const Icon = cfg.Icon
  const isError = (event.event_type === 'tool_call' && event.success === false) ||
                  (event.event_type === 'llm_call' && event.status === 'error')

  const rows: Array<{ label: string; value: React.ReactNode }> = []
  const add = (label: string, value: unknown) => {
    if (value == null || value === '' || value === 0) return
    rows.push({ label, value: String(value) })
  }

  add('Time', event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : null)
  add('Sequence', event.sequence)
  add('Lane', meta.laneLabel)
  add('Actor', meta.actorLabel)
  add('Transition', meta.transitionLabel)
  add('Cycle', meta.cycle > 0 ? `Loop ${meta.cycle}` : 'Initial')

  if (event.event_type === 'llm_call') {
    add('Model', event.model)
    add('Input tokens', event.input_tokens != null ? formatTokens(event.input_tokens) : null)
    add('Output tokens', event.output_tokens != null ? formatTokens(event.output_tokens) : null)
    add('Cache read', event.cache_read_tokens != null && event.cache_read_tokens > 0 ? formatTokens(event.cache_read_tokens) : null)
    add('Cache created', event.cache_creation_tokens != null && event.cache_creation_tokens > 0 ? formatTokens(event.cache_creation_tokens) : null)
    add('Latency', event.latency_ms != null ? formatLatency(event.latency_ms) : null)
    add('Cost', event.cost_usd != null && event.cost_usd > 0 ? formatCost(event.cost_usd) : null)
    add('Context use', event.context_utilization_pct != null ? `${event.context_utilization_pct.toFixed(1)}%` : null)
    add('Status', event.status)
    if (event.error) rows.push({ label: 'Error', value: <span className="text-red-400 break-words">{event.error}</span> })
  } else if (event.event_type === 'tool_call') {
    add('Tool', event.tool_name)
    rows.push({ label: 'Result', value: event.success === false ? <span className="text-red-400">Failed</span> : <span className="text-emerald-400">OK</span> })
    add('Duration', event.duration_ms != null ? formatLatency(event.duration_ms) : null)
    add('Retries', event.retry_count)
    if (event.error_message) rows.push({ label: 'Error', value: <span className="text-red-400 break-words">{event.error_message}</span> })
  } else if (event.event_type === 'user_message') {
    add('Tokens', event.token_count)
  } else if (event.event_type === 'assistant_message') {
    const totTok = (event.input_tokens ?? 0) + (event.output_tokens ?? 0)
    add('Total tokens', totTok > 0 ? totTok : null)
    add('Cost', event.total_cost_usd != null && event.total_cost_usd > 0 ? formatCost(event.total_cost_usd) : null)
    add('Latency', event.total_latency_ms != null ? formatLatency(event.total_latency_ms) : null)
  } else if (event.event_type === 'tool_pruning') {
    add('Results evaluated', event.tool_results_count)
    add('Results pruned', event.tool_results_pruned)
    add('Data tools trimmed', event.data_bearing_pruned)
    add('Chars saved', event.chars_saved?.toLocaleString())
    add('Tokens saved ~', event.estimated_tokens_saved != null ? formatTokens(event.estimated_tokens_saved) : null)
  }

  const content = event.content ?? event.content_preview
  const response = event.response_preview

  return (
    <div className="flex h-full min-h-[28rem] flex-col overflow-hidden rounded-[1.7rem] border border-[#e4d7c7] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,243,236,0.96))] shadow-[0_28px_80px_-48px_rgba(73,45,23,0.32)]">
      <div className="border-b border-[#eadfce] px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div
              className="flex h-11 w-11 items-center justify-center rounded-[1rem] border bg-white shadow-[0_18px_34px_-26px_rgba(73,45,23,0.35)]"
              style={{ borderColor: isError ? '#fca5a5' : cfg.border }}
            >
              <Icon size={18} style={{ color: isError ? '#dc2626' : cfg.dot }} />
            </div>
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-[#e7dccb] bg-white/75 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-[#7c5d45]">
                <Sparkles className="h-3 w-3" />
                {(event.event_type as string).replace(/_/g, ' ')}
              </div>
              <h3 className="mt-3 text-lg font-semibold tracking-[-0.03em] text-[#171717]">
                {nodeLabel(event)}
              </h3>
              <p className="mt-1 text-sm text-[#6c6258]">
                Step {currentIndex + 1} of {total}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-full border border-[#e1d4c1] bg-white/80 p-2 text-[#7f7266] transition-colors hover:border-[#cdb79d] hover:text-[#171717]"
          >
            <XCircle size={16} />
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onSelectPrev}
            disabled={currentIndex <= 0}
            className="inline-flex items-center gap-1 rounded-full border border-[#dfd1be] bg-white/75 px-3 py-1.5 text-xs font-semibold text-[#554a42] transition-colors hover:border-[#cdb79d] hover:text-[#171717] disabled:cursor-not-allowed disabled:opacity-45"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Previous
          </button>
          <button
            type="button"
            onClick={onSelectNext}
            disabled={currentIndex >= total - 1}
            className="inline-flex items-center gap-1 rounded-full border border-[#dfd1be] bg-white/75 px-3 py-1.5 text-xs font-semibold text-[#554a42] transition-colors hover:border-[#cdb79d] hover:text-[#171717] disabled:cursor-not-allowed disabled:opacity-45"
          >
            Next
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        {rows.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2">
            {rows.map(({ label, value }, i) => (
              <div
                key={i}
                className="rounded-[1.2rem] border border-[#e7dccb] bg-white/82 px-4 py-3 shadow-[0_18px_34px_-30px_rgba(73,45,23,0.18)]"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#90745a]">{label}</p>
                <div className="mt-2 text-sm font-medium break-words text-[#1d1b18]">{value}</div>
              </div>
            ))}
          </div>
        )}

        {(content || response) && (
          <div className="mt-4">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#90745a]">
              {content ? 'Content' : 'Response preview'}
            </p>
            <div className="max-h-72 overflow-auto rounded-[1.25rem] border border-[#e7dccb] bg-[#fcfaf5] p-4 text-[12px] leading-6 text-[#50483f] whitespace-pre-wrap break-words">
              {content ?? response}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Per-turn flow modal ────────────────────────────────────────────────────────
function TurnFlowModal({ turn, onClose }: { turn: Turn; onClose: () => void }) {
  const nodes: LensTimelineEvent[] = useMemo(() => [
    ...(turn.userMessage ? [turn.userMessage] : []),
    ...turn.steps,
    ...(turn.assistantMessage ? [turn.assistantMessage] : []),
  ], [turn])

  const [mounted, setMounted] = useState(false)
  const [viewMode, setViewMode] = useState<LensFlowView>('swimlane')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    setSelectedId(nodes[0]?.id ?? null)
  }, [nodes])

  useEffect(() => {
    setMounted(true)

    const previousOverflow = document.body.style.overflow
    const previousPaddingRight = document.body.style.paddingRight
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth
    document.body.style.overflow = 'hidden'
    if (scrollbarWidth > 0) {
      document.body.style.paddingRight = `${scrollbarWidth}px`
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.style.overflow = previousOverflow
      document.body.style.paddingRight = previousPaddingRight
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [onClose])

  const selectedIndex = Math.max(0, nodes.findIndex((node) => node.id === selectedId))
  const selected = nodes[selectedIndex] ?? null

  const flowMeta = useMemo(() => buildFlowMeta(nodes), [nodes])

  const counts = useMemo(() => ({
    llm: nodes.filter((node) => node.event_type === 'llm_call').length,
    tool: nodes.filter((node) => node.event_type === 'tool_call').length,
    response: nodes.filter((node) => node.event_type === 'assistant_message').length,
  }), [nodes])

  const swimlaneLayout = useMemo(() => {
    const stepGap = 170
    const leftRail = 120
    const topRail = 80
    const rowGap = 104
    const width = Math.max(1120, leftRail + 160 + Math.max(nodes.length - 1, 0) * stepGap)
    const height = topRail * 2 + (LANE_META.length - 1) * rowGap

    return {
      width,
      height,
      points: nodes.map((event, index) => ({
        id: event.id,
        x: leftRail + index * stepGap,
        y: topRail + LANE_INDEX[flowMeta[event.id].lane] * rowGap,
      })),
    }
  }, [flowMeta, nodes])

  const graphLayout = useMemo(() => {
    const stepGap = 168
    const leftRail = 96
    const baseY = 214
    const laneOffset: Record<LaneId, number> = {
      user: -92,
      agent: -20,
      tool: 44,
      response: 98,
      system: 8,
    }
    const width = Math.max(980, leftRail + 140 + Math.max(nodes.length - 1, 0) * stepGap)
    const height = 420

    return {
      width,
      height,
      baseY,
      points: nodes.map((event, index) => {
        const meta = flowMeta[event.id]
        const cycleNudge = meta.cycle > 1 ? Math.min(meta.cycle * 6, 18) : 0
        return {
          id: event.id,
          x: leftRail + index * stepGap,
          y: baseY + laneOffset[meta.lane] + cycleNudge,
        }
      }),
    }
  }, [flowMeta, nodes])

  if (!mounted) return null

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-3 sm:p-6"
      onMouseDown={onClose}
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,248,240,0.78),rgba(248,239,229,0.55)_34%,rgba(66,52,43,0.28)_100%)] backdrop-blur-[3px]" />
      <div
        className="relative z-10 flex h-[min(94vh,980px)] w-full max-w-[min(98vw,1720px)] flex-col overflow-hidden rounded-[2rem] border border-[#ddd2c4] bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.98),_rgba(247,240,231,0.97)_55%,_rgba(237,230,220,0.96)_100%)] shadow-[0_48px_140px_-54px_rgba(17,14,10,0.58)]"
        onMouseDown={e => e.stopPropagation()}
      >
        <div className="shrink-0 border-b border-[#e7dccb] px-5 py-4 md:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-[1.1rem] bg-[#f3ecde] shadow-[0_18px_34px_-24px_rgba(73,45,23,0.28)]">
                <GitBranch className="h-5 w-5 text-[#171717]" />
              </div>
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-[#dfd1be] bg-white/75 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-[#7c5d45]">
                  <Sparkles className="h-3.5 w-3.5" />
                  Interaction Flow
                </div>
                <h2 className="mt-3 text-2xl font-semibold tracking-[-0.04em] text-[#171717] md:text-[2rem]">
                  Interaction {turn.index} orchestration map
                </h2>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-[#6f655c]">
                  <span className="inline-flex items-center gap-1 rounded-full border border-[#e4d7c7] bg-white/70 px-3 py-1.5">
                    <Clock3 className="h-3.5 w-3.5" />
                    {turn.userMessage?.timestamp ? formatTime(turn.userMessage.timestamp) : 'Time unavailable'}
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full border border-[#e4d7c7] bg-white/70 px-3 py-1.5">
                    {nodes.length} event{nodes.length !== 1 ? 's' : ''}
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full border border-[#e4d7c7] bg-white/70 px-3 py-1.5">
                    {counts.llm} LLM
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full border border-[#e4d7c7] bg-white/70 px-3 py-1.5">
                    {counts.tool} tool
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full border border-[#e4d7c7] bg-white/70 px-3 py-1.5">
                    {counts.response} response
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full border border-[#e4d7c7] bg-white/70 px-3 py-1.5">
                    {Math.max(counts.llm, 1)} reasoning loop{Math.max(counts.llm, 1) !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start">
              <span className="hidden rounded-full border border-[#dfd1be] bg-white/75 px-3 py-1.5 text-xs font-semibold text-[#5d534b] sm:inline-flex">
                Select nodes to inspect details
              </span>
              <button
                onClick={onClose}
                className="rounded-full border border-[#dfd1be] bg-white/80 p-2 text-[#7f7266] transition-colors hover:border-[#cdb79d] hover:text-[#171717]"
              >
                <XCircle size={18} />
              </button>
            </div>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 gap-4 p-4 md:p-5 lg:grid-cols-[minmax(0,1.65fr)_360px]">
          <div className="flex min-h-[34rem] min-w-0 flex-col overflow-hidden rounded-[1.8rem] border border-[#e3d6c4] bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.98),rgba(248,243,235,0.98)_55%,rgba(240,234,224,0.98)_100%)] shadow-[0_34px_90px_-52px_rgba(92,63,40,0.28)]">
            <div className="border-b border-[#e7dccb] px-5 py-4">
              <div className="flex flex-wrap items-center gap-2">
                {Object.entries(NODE_CFG).map(([type, c]) => {
                  const Icon = c.Icon
                  const count = nodes.filter((node) => node.event_type === type).length
                  if (!count) return null
                  return (
                    <span
                      key={type}
                      className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em]"
                      style={{ borderColor: `${c.dot}33`, backgroundColor: c.soft, color: c.dot }}
                    >
                      <Icon size={11} />
                      {c.badge}
                      <span className="rounded-full bg-white/70 px-1.5 py-0.5 text-[9px] text-[#171717]">{count}</span>
                    </span>
                  )
                })}
                <span className="ml-auto inline-flex items-center gap-1 text-[11px] font-medium text-[#857669]">
                  <Sparkles className="h-3.5 w-3.5 text-[#d36c93]" />
                  Interactive flow map
                </span>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {([
                  { id: 'swimlane', label: 'Swimlane' },
                  { id: 'graph', label: 'Graph' },
                  { id: 'trace', label: 'Trace' },
                ] as const).map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setViewMode(tab.id)}
                    className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition-colors ${
                      viewMode === tab.id
                        ? 'border-[#dcc7af] bg-white text-[#171717] shadow-[0_14px_30px_-24px_rgba(73,45,23,0.24)]'
                        : 'border-[#e6d9c8] bg-[#f8f1e7] text-[#8d7f73] hover:bg-white'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="mt-4 overflow-x-auto">
                <div className="flex w-max gap-2 pb-1">
                  {nodes.map((event, index) => {
                    const cfg = ncfg(event.event_type as string)
                    const isActive = selected?.id === event.id
                    return (
                      <button
                        key={`${event.id}-chip`}
                        type="button"
                        onClick={() => setSelectedId(event.id)}
                        className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                          isActive
                            ? 'border-[#dcc7af] bg-white text-[#171717] shadow-[0_14px_30px_-24px_rgba(73,45,23,0.22)]'
                            : 'border-[#e4d8c8] bg-[#f7efe5] text-[#7d7268] hover:bg-white'
                        }`}
                      >
                        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-[#efe5d8] text-[10px] text-[#171717]">
                          {index + 1}
                        </span>
                        <span style={{ color: isActive ? '#171717' : cfg.dot }}>{cfg.badge}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-auto px-6 py-6">
              {viewMode === 'graph' ? (
                <div className="min-h-[28rem] overflow-x-auto pb-4">
                  <div
                    className="relative"
                    style={{ width: graphLayout.width, height: graphLayout.height }}
                  >
                    <div className="absolute inset-x-14 top-16 h-[300px] rounded-[2rem] border border-[#eadfce] bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.94),rgba(247,240,229,0.78)_58%,rgba(241,232,221,0.54)_100%)]" />
                    <div
                      className="absolute left-14 right-14 h-px bg-gradient-to-r from-transparent via-[#d8c6b2] to-transparent"
                      style={{ top: graphLayout.baseY }}
                    />

                    <svg
                      className="absolute inset-0"
                      width={graphLayout.width}
                      height={graphLayout.height}
                      viewBox={`0 0 ${graphLayout.width} ${graphLayout.height}`}
                      fill="none"
                    >
                      {graphLayout.points.slice(0, -1).map((point, index) => {
                        const nextPoint = graphLayout.points[index + 1]
                        const event = nodes[index]
                        const nextEvent = nodes[index + 1]
                        const accent = ncfg(event.event_type as string).dot
                        const nextMeta = flowMeta[nextEvent.id]
                        const dashed = flowMeta[event.id].lane !== nextMeta.lane

                        return (
                          <path
                            key={`${point.id}-graph-path`}
                            d={flowCurvePath(point.x, point.y, nextPoint.x, nextPoint.y)}
                            stroke={accent}
                            strokeOpacity={dashed ? 0.42 : 0.26}
                            strokeWidth={dashed ? 2.5 : 2}
                            strokeDasharray={dashed ? '7 9' : undefined}
                            strokeLinecap="round"
                          />
                        )
                      })}
                    </svg>

                    {nodes.map((event, index) => {
                      const meta = flowMeta[event.id]
                      const point = graphLayout.points[index]
                      const cfg = ncfg(event.event_type as string)
                      const Icon = cfg.Icon
                      const isSelected = selected?.id === event.id
                      const isError = (event.event_type === 'tool_call' && event.success === false) ||
                                      (event.event_type === 'llm_call' && event.status === 'error')
                      const isWarn = event.event_type === 'tool_pruning' && (event.data_bearing_pruned ?? 0) > 0
                      const labelBelow = index % 2 === 0

                      return (
                        <button
                          key={`${event.id}-graph-node`}
                          type="button"
                          onClick={() => setSelectedId(event.id)}
                          className="absolute -translate-x-1/2 -translate-y-1/2 text-left transition-transform duration-150"
                          style={{ left: point.x, top: point.y }}
                        >
                          <div className="relative">
                            <div
                              className="flex h-12 w-12 items-center justify-center rounded-full border-2 bg-white"
                              style={{
                                borderColor: isError ? '#ef4444' : isWarn ? '#f59e0b' : cfg.dot,
                                boxShadow: isSelected
                                  ? `0 0 0 8px ${cfg.soft}, 0 16px 44px -24px ${cfg.glow}`
                                  : `0 0 0 4px ${cfg.soft}, 0 14px 28px -22px rgba(92,63,40,0.24)`,
                              }}
                            >
                              <Icon size={16} style={{ color: isError ? '#fca5a5' : isWarn ? '#fcd34d' : cfg.dot }} />
                            </div>

                            <div
                              className={`absolute left-1/2 w-[170px] -translate-x-1/2 rounded-[1.2rem] border px-3 py-2.5 ${
                                labelBelow ? 'top-[3.7rem]' : 'bottom-[3.7rem]'
                              }`}
                              style={{
                                borderColor: isSelected ? `${cfg.dot}88` : '#e7dccb',
                                background: isSelected
                                  ? 'linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,241,233,0.98))'
                                  : 'linear-gradient(180deg, rgba(255,252,248,0.96), rgba(245,237,228,0.96))',
                                boxShadow: isSelected ? `0 24px 50px -38px ${cfg.glow}` : '0 24px 44px -38px rgba(92,63,40,0.24)',
                              }}
                            >
                              <div className="flex items-center gap-2">
                                <span
                                  className="inline-flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-[10px] font-semibold"
                                  style={{ backgroundColor: cfg.soft, color: cfg.dot }}
                                >
                                  {index + 1}
                                </span>
                                <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#8a7c6f]">
                                  {meta.actorLabel}
                                </span>
                              </div>
                              <p className="mt-2 text-[13px] font-semibold leading-5 text-[#171717] line-clamp-2">
                                {nodeLabel(event)}
                              </p>
                              {nodePreview(event) ? (
                                <p className="mt-1.5 text-[11px] leading-5 text-[#74695f] line-clamp-2">
                                  {nodePreview(event)}
                                </p>
                              ) : null}
                            </div>
                          </div>
                        </button>
                      )
                    })}

                    <div className="absolute bottom-4 left-14 right-14 flex flex-wrap gap-2 text-[11px] text-[#7f7468]">
                      <span className="inline-flex items-center gap-2 rounded-full border border-[#e4d8c8] bg-white/80 px-3 py-1.5">
                        <span className="h-2.5 w-2.5 rounded-full bg-[#d36c93]" />
                        Same-lane continuation
                      </span>
                      <span className="inline-flex items-center gap-2 rounded-full border border-[#e4d8c8] bg-white/80 px-3 py-1.5">
                        <span className="h-px w-5 border-t-2 border-dashed border-[#d36c93]" />
                        Cross-lane handoff
                      </span>
                    </div>
                  </div>
                </div>
              ) : null}

              {viewMode === 'swimlane' ? (
                <div className="min-h-[28rem] overflow-x-auto pb-4">
                  <div
                    className="relative"
                    style={{ width: swimlaneLayout.width, height: swimlaneLayout.height + 52 }}
                  >
                    <div className="absolute inset-0 rounded-[2rem] border border-[#e7dccb] bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(248,241,231,0.84))]" />

                    <svg
                      className="absolute inset-0"
                      width={swimlaneLayout.width}
                      height={swimlaneLayout.height + 52}
                      viewBox={`0 0 ${swimlaneLayout.width} ${swimlaneLayout.height + 52}`}
                      fill="none"
                    >
                      {LANE_META.map((lane) => {
                        const y = swimlaneLayout.points[0]
                          ? 80 + LANE_INDEX[lane.id] * 104
                          : 80 + LANE_INDEX[lane.id] * 104
                        return (
                          <g key={`${lane.id}-guide`}>
                            <line
                              x1="88"
                              y1={y}
                              x2={swimlaneLayout.width - 50}
                              y2={y}
                              stroke={lane.accent}
                              strokeOpacity="0.18"
                              strokeWidth="1.5"
                              strokeDasharray="7 10"
                            />
                          </g>
                        )
                      })}

                      {swimlaneLayout.points.slice(0, -1).map((point, index) => {
                        const nextPoint = swimlaneLayout.points[index + 1]
                        const event = nodes[index]
                        const nextEvent = nodes[index + 1]
                        const meta = flowMeta[event.id]
                        const nextMeta = flowMeta[nextEvent.id]
                        const accent = ncfg(event.event_type as string).dot
                        const crossLane = meta.lane !== nextMeta.lane

                        return (
                          <path
                            key={`${point.id}-swimlane-path`}
                            d={flowCurvePath(point.x, point.y, nextPoint.x, nextPoint.y)}
                            stroke={accent}
                            strokeOpacity={crossLane ? 0.52 : 0.28}
                            strokeWidth={crossLane ? 2.5 : 2}
                            strokeDasharray={crossLane ? '7 8' : undefined}
                            strokeLinecap="round"
                          />
                        )
                      })}
                    </svg>

                    {LANE_META.map((lane) => (
                      <div
                        key={lane.id}
                        className="absolute left-5 flex w-[165px] items-center gap-3 rounded-full border px-4 py-2.5"
                        style={{
                          top: 80 + LANE_INDEX[lane.id] * 104 - 24,
                          borderColor: lane.border,
                          backgroundColor: lane.soft,
                        }}
                      >
                        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: lane.accent }} />
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: lane.accent }}>
                            {lane.label}
                          </div>
                        </div>
                      </div>
                    ))}

                    {nodes.map((event, index) => {
                      const meta = flowMeta[event.id]
                      const point = swimlaneLayout.points[index]
                      const cfg = ncfg(event.event_type as string)
                      const Icon = cfg.Icon
                      const isSelected = selected?.id === event.id
                      const isError = (event.event_type === 'tool_call' && event.success === false) ||
                                      (event.event_type === 'llm_call' && event.status === 'error')
                      const isWarn = event.event_type === 'tool_pruning' && (event.data_bearing_pruned ?? 0) > 0
                      const floatUp = index % 2 === 1

                      return (
                        <button
                          key={`${event.id}-swimlane-node`}
                          type="button"
                          onClick={() => setSelectedId(event.id)}
                          className="absolute -translate-x-1/2 -translate-y-1/2 text-left transition-transform duration-150"
                          style={{ left: point.x, top: point.y }}
                        >
                          <div className="relative">
                            <div
                              className="flex h-11 w-11 items-center justify-center rounded-full border-2 bg-white"
                              style={{
                                borderColor: isError ? '#ef4444' : isWarn ? '#f59e0b' : cfg.dot,
                                boxShadow: isSelected
                                  ? `0 0 0 9px ${cfg.soft}, 0 20px 46px -26px ${cfg.glow}`
                                  : `0 0 0 4px ${cfg.soft}, 0 14px 28px -22px rgba(92,63,40,0.24)`,
                              }}
                            >
                              <Icon size={15} style={{ color: isError ? '#fca5a5' : isWarn ? '#fcd34d' : cfg.dot }} />
                            </div>

                            <div
                              className={`absolute left-1/2 w-[185px] -translate-x-1/2 rounded-[1.1rem] border px-3 py-2.5 ${
                                floatUp ? 'bottom-[3.6rem]' : 'top-[3.6rem]'
                              }`}
                              style={{
                                borderColor: isSelected ? `${cfg.dot}88` : '#e7dccb',
                                background: isSelected
                                  ? 'linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,241,233,0.98))'
                                  : 'linear-gradient(180deg, rgba(255,252,248,0.96), rgba(245,237,228,0.96))',
                                boxShadow: isSelected ? `0 28px 52px -38px ${cfg.glow}` : '0 24px 42px -36px rgba(92,63,40,0.24)',
                              }}
                            >
                              <div className="flex items-center gap-2">
                                <span
                                  className="inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-semibold"
                                  style={{ backgroundColor: cfg.soft, color: cfg.dot }}
                                >
                                  {index + 1}
                                </span>
                                <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#8a7b6f]">
                                  {meta.transitionLabel}
                                </span>
                              </div>
                              <p className="mt-2 text-[13px] font-semibold leading-5 text-[#171717] line-clamp-2">
                                {nodeLabel(event)}
                              </p>
                              <div className="mt-1.5 flex items-center gap-2 text-[11px] text-[#74695f]">
                                <span>{meta.actorLabel}</span>
                                {meta.cycle > 0 ? <span>Loop {meta.cycle}</span> : null}
                              </div>
                              {nodePreview(event) ? (
                                <p className="mt-1.5 text-[11px] leading-5 text-[#74695f] line-clamp-2">
                                  {nodePreview(event)}
                                </p>
                              ) : null}
                            </div>
                          </div>
                        </button>
                      )
                    })}

                    <div className="absolute bottom-4 right-5 flex flex-wrap justify-end gap-2 text-[11px] text-[#7f7468]">
                      <span className="inline-flex items-center gap-2 rounded-full border border-[#e4d8c8] bg-white/80 px-3 py-1.5">
                        <span className="h-2.5 w-2.5 rounded-full bg-[#d36c93]" />
                        Event node
                      </span>
                      <span className="inline-flex items-center gap-2 rounded-full border border-[#e4d8c8] bg-white/80 px-3 py-1.5">
                        <span className="h-px w-5 border-t-2 border-dashed border-[#d36c93]" />
                        Handoff between lanes
                      </span>
                    </div>
                  </div>
                </div>
              ) : null}

              {viewMode === 'trace' ? (
                <div className="min-h-[28rem] space-y-3">
                  {nodes.map((event, index) => {
                    const meta = flowMeta[event.id]
                    const cfg = ncfg(event.event_type as string)
                    const isSelected = selected?.id === event.id
                    const isError = (event.event_type === 'tool_call' && event.success === false) ||
                                    (event.event_type === 'llm_call' && event.status === 'error')
                    const isWarn = event.event_type === 'tool_pruning' && (event.data_bearing_pruned ?? 0) > 0

                    return (
                      <button
                        key={`${event.id}-trace`}
                        type="button"
                        onClick={() => setSelectedId(event.id)}
                        className={`flex w-full items-start gap-4 rounded-[1.35rem] border px-4 py-4 text-left transition-colors ${
                          isSelected ? 'border-[#dcc7af] bg-white shadow-[0_18px_40px_-30px_rgba(92,63,40,0.18)]' : 'border-[#e7dccb] bg-[#fcfaf6] hover:bg-white'
                        }`}
                      >
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#e1d3c0] bg-[#f2e9dd] text-[11px] font-semibold text-[#171717]">
                          {index + 1}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]"
                              style={{ borderColor: `${cfg.dot}33`, backgroundColor: cfg.soft, color: cfg.dot }}
                            >
                              {cfg.badge}
                            </span>
                            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8a7c6f]">{meta.laneLabel}</span>
                            <span className="text-xs text-[#74695f]">{meta.transitionLabel}</span>
                            <span className="ml-auto text-xs text-[#8a7c6f]">{event.timestamp ? formatTime(event.timestamp) : 'No time'}</span>
                          </div>
                          <p className="mt-3 text-sm font-semibold text-[#171717]">{nodeLabel(event)}</p>
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-[#74695f]">
                            <span>{meta.actorLabel}</span>
                            {meta.cycle > 0 ? <span>Loop {meta.cycle}</span> : null}
                            {nodeSub(event) ? <span>{nodeSub(event)}</span> : null}
                            {isError ? <span className="text-red-300">Failed</span> : null}
                            {isWarn ? <span className="text-amber-200">Trimmed</span> : null}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              ) : null}
            </div>
          </div>

          {selected ? (
            <NodeDetailPanel
              event={selected}
              onClose={() => setSelectedId(null)}
              currentIndex={selectedIndex}
              total={nodes.length}
              onSelectPrev={() => setSelectedId(nodes[Math.max(0, selectedIndex - 1)]?.id ?? selectedId)}
              onSelectNext={() => setSelectedId(nodes[Math.min(nodes.length - 1, selectedIndex + 1)]?.id ?? selectedId)}
              meta={flowMeta[selected.id]}
            />
          ) : (
            <div className="flex min-h-[34rem] items-center justify-center rounded-[1.8rem] border border-[#e4d7c7] bg-white/78 p-6 text-center shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)]">
              <div>
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-[1.2rem] bg-[#f3ecde]">
                  <GitBranch className="h-6 w-6 text-[#171717]" />
                </div>
                <h3 className="mt-4 text-lg font-semibold text-[#171717]">Select a node</h3>
                <p className="mt-2 text-sm leading-6 text-[#6f655c]">
                  Click any event card in the flow to inspect timing, model, tool result, content preview, and orchestration metadata.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
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
