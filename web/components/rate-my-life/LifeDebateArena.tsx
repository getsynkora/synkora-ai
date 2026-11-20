'use client'

import { useEffect, useRef, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils/cn'
import type { DebateMessage, DebateParticipant } from '@/lib/api/war-room'

interface LifeDebateArenaProps {
  messages: DebateMessage[]
  participants: DebateParticipant[]
  streamingParticipantId: string | null
  streamingContent: string
  verdict: string | null
  currentRound: number
  totalRounds: number
}

/** Strip [SCORES] block from display text */
function cleanContent(text: string): string {
  return text
    .replace(/\[SCORES?\][\s\S]*?(?=\n\n|\n(?=[A-Z])|\s*$)/gi, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

/** Thinking dots animation */
function ThinkingIndicator({ color, name }: { color: string; name: string }) {
  return (
    <div className="flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div
        className="w-9 h-9 rounded-xl flex items-center justify-center text-white text-sm font-bold shadow-lg flex-shrink-0"
        style={{
          backgroundColor: color,
          boxShadow: `0 0 20px ${color}50, 0 0 0 2px white, 0 0 0 4px ${color}40`,
        }}
      >
        {name.charAt(0)}
      </div>
      <div className="pt-2">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-bold" style={{ color }}>{name}</span>
          <span className="text-[10px] text-ash font-medium">is thinking…</span>
        </div>
        <div className="flex gap-1.5">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-2 h-2 rounded-full motion-safe:animate-bounce"
              style={{
                backgroundColor: color,
                animationDelay: `${i * 150}ms`,
                animationDuration: '800ms',
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

/** Compact markdown for debate messages */
function DebateMarkdown({ content, color }: { content: string; color: string }) {
  return (
    <div className="debate-md text-[13.5px] leading-[1.75] text-ink-soft">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h3 className="text-sm font-bold text-ink mt-3 mb-1.5 first:mt-0">{children}</h3>
          ),
          h2: ({ children }) => (
            <h3 className="text-sm font-bold text-ink mt-3 mb-1.5 first:mt-0">{children}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="text-[13px] font-bold text-ink mt-2.5 mb-1 first:mt-0">{children}</h4>
          ),
          p: ({ children }) => (
            <p className="mb-2.5 last:mb-0">{children}</p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-ink">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="text-ink-soft">{children}</em>
          ),
          ul: ({ children }) => (
            <ul className="space-y-1 mb-2.5 last:mb-0">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="space-y-1 mb-2.5 last:mb-0 list-decimal list-inside">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="flex gap-2 text-[13.5px]">
              <span className="mt-px select-none flex-shrink-0" style={{ color }}>&#x25CF;</span>
              <span className="flex-1">{children}</span>
            </li>
          ),
          blockquote: ({ children }) => (
            <blockquote
              className="border-l-[3px] pl-3.5 my-2.5 py-0.5 text-ink-soft italic"
              style={{ borderLeftColor: `${color}60` }}
            >
              {children}
            </blockquote>
          ),
          code: ({ children, className }: any) => {
            const isInline = !className
            if (isInline) {
              return (
                <code className="px-1.5 py-0.5 rounded text-[12px] font-mono bg-sand text-ink">
                  {children}
                </code>
              )
            }
            return (
              <pre className="my-2.5 p-3 rounded-lg bg-ink text-sand text-[12px] font-mono overflow-x-auto">
                <code>{children}</code>
              </pre>
            )
          },
          hr: () => <hr className="my-3 border-line" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

/** Single debate message card */
function MessageCard({
  msg,
  color,
  isStreaming = false,
  animDelay = 0,
}: {
  msg: { agent_name: string; content: string; round: number; is_verdict?: boolean }
  color: string
  isStreaming?: boolean
  animDelay?: number
}) {
  const displayContent = cleanContent(msg.content)
  const isVerdict = msg.is_verdict

  return (
    <div
      className={cn(
        'flex items-start gap-3 group',
        !isStreaming && 'animate-in fade-in slide-in-from-bottom-3 duration-500',
      )}
      style={!isStreaming ? { animationDelay: `${animDelay}ms` } : undefined}
    >
      {/* Avatar */}
      <div
        className={cn(
          'w-9 h-9 rounded-xl flex items-center justify-center text-white text-sm font-bold shadow-md flex-shrink-0 transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-300',
          isStreaming && 'scale-105',
          isVerdict && 'w-10 h-10',
        )}
        style={{
          backgroundColor: color,
          boxShadow: isStreaming
            ? `0 0 24px ${color}50, 0 0 0 2px white, 0 0 0 4px ${color}40`
            : `0 2px 8px ${color}30`,
        }}
      >
        {isVerdict ? (
          <svg aria-hidden="true" className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
          </svg>
        ) : (
          msg.agent_name.charAt(0).toUpperCase()
        )}
      </div>

      {/* Bubble */}
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 mb-1 px-0.5">
          <span className="text-[13px] font-bold" style={{ color }}>
            {msg.agent_name}
          </span>
          {isVerdict && (
            <span className="text-[10px] font-bold px-2 py-0.5 bg-sand-deep text-gold rounded-md">
              Final Verdict
            </span>
          )}
          {!isVerdict && msg.round > 0 && (
            <span className="text-[10px] text-ash font-medium">Round {msg.round}</span>
          )}
          {isStreaming && (
            <span className="flex items-center gap-1 text-[10px] font-medium text-leaf">
              <span className="w-1.5 h-1.5 rounded-full bg-leaf motion-safe:animate-pulse" />
              Speaking
            </span>
          )}
        </div>

        {/* Content */}
        <div
          className={cn(
            'rounded-2xl rounded-tl-md px-4 py-3.5 shadow-sm border transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-300',
            isVerdict
              ? 'bg-sand-deep border-honey/60'
              : 'bg-white',
            isStreaming && !isVerdict && 'shadow-md',
          )}
          style={!isVerdict ? {
            borderColor: isStreaming ? `${color}40` : `${color}18`,
            boxShadow: isStreaming ? `0 4px 24px ${color}12` : undefined,
          } : undefined}
        >
          <DebateMarkdown content={displayContent} color={color} />
          {isStreaming && (
            <span
              className="inline-block w-[2.5px] h-[16px] rounded-full motion-safe:animate-pulse ml-0.5 -mb-0.5"
              style={{ backgroundColor: color }}
            />
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────

export function LifeDebateArena({
  messages,
  participants,
  streamingParticipantId,
  streamingContent,
  verdict,
  currentRound,
  totalRounds,
}: LifeDebateArenaProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [hasInitialScroll, setHasInitialScroll] = useState(false)

  // Auto-scroll to bottom on new content
  useEffect(() => {
    if (!scrollRef.current) return
    const el = scrollRef.current
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 200
    if (isNearBottom || !hasInitialScroll) {
      el.scrollTo({ top: el.scrollHeight, behavior: hasInitialScroll ? 'smooth' : 'instant' })
      if (!hasInitialScroll) setHasInitialScroll(true)
    }
  }, [messages.length, streamingContent, hasInitialScroll])

  // Group messages by round
  const rounds = useMemo(() => {
    const map = new Map<number, DebateMessage[]>()
    for (const msg of messages) {
      if (msg.is_verdict) continue
      if (!map.has(msg.round)) map.set(msg.round, [])
      map.get(msg.round)!.push(msg)
    }
    return map
  }, [messages])

  const verdictMessages = useMemo(() => messages.filter(m => m.is_verdict), [messages])

  // Find active speaker info
  const activeSpeaker = streamingParticipantId
    ? participants.find(p => p.id === streamingParticipantId) || null
    : null
  const isSynthesizing = streamingParticipantId === 'synthesizer'

  // Progress
  const isLive = streamingParticipantId !== null
  const totalParticipantsPerRound = participants.length
  const completedInCurrentRound = rounds.get(currentRound)?.length ?? 0

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Live Status Bar */}
      {isLive && (
        <div className="mx-4 mt-3">
          <div className="bg-white/90 rounded-xl border border-line px-4 py-2.5 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                {/* Active speaker avatar + name */}
                {activeSpeaker && !isSynthesizing && (
                  <div className="flex items-center gap-2">
                    <div
                      className="w-6 h-6 rounded-lg flex items-center justify-center text-white text-[10px] font-bold motion-safe:animate-pulse"
                      style={{ backgroundColor: activeSpeaker.color }}
                    >
                      {activeSpeaker.agent_name.charAt(0)}
                    </div>
                    <span className="text-xs font-semibold text-ink-soft">
                      {activeSpeaker.agent_name}
                    </span>
                    <span className="text-[10px] text-leaf font-medium flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-leaf motion-safe:animate-pulse" />
                      speaking
                    </span>
                  </div>
                )}
                {isSynthesizing && (
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-lg flex items-center justify-center text-white text-[10px] font-bold bg-warn motion-safe:animate-pulse">
                      S
                    </div>
                    <span className="text-xs font-semibold text-gold">
                      Synthesizing verdict...
                    </span>
                  </div>
                )}
              </div>
              <span className="text-[10px] text-ash font-medium tabular-nums">
                Round {currentRound}/{totalRounds}
              </span>
            </div>

            {/* Progress bar */}
            <div className="flex items-center gap-1.5">
              {Array.from({ length: totalRounds }, (_, i) => {
                const roundNum = i + 1
                const roundComplete = roundNum < currentRound
                const roundActive = roundNum === currentRound
                const roundMsgs = rounds.get(roundNum)?.length ?? 0
                const pct = roundComplete ? 100 : roundActive
                  ? Math.max(5, (roundMsgs / totalParticipantsPerRound) * 100)
                  : 0
                return (
                  <div key={roundNum} className="flex-1 h-1.5 rounded-full bg-sand overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-700 ease-out',
                        roundComplete ? 'bg-mint' : roundActive ? 'bg-hotpink' : 'bg-line',
                      )}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                )
              })}
              {/* Verdict slot */}
              <div className="w-8 h-1.5 rounded-full bg-sand overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-700',
                    isSynthesizing ? 'bg-honey w-1/2' : verdict ? 'bg-honey w-full' : 'w-0',
                  )}
                />
              </div>
            </div>

            {/* Participant dots showing who has spoken */}
            <div className="flex items-center gap-2 mt-2">
              {participants.map((p) => {
                const hasSpoken = (rounds.get(currentRound) ?? []).some(
                  m => m.participant_id === p.id
                )
                const isSpeaking = streamingParticipantId === p.id
                return (
                  <div
                    key={p.id}
                    className={cn(
                      'flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-300',
                      hasSpoken || isSpeaking ? 'opacity-100' : 'opacity-40',
                    )}
                    style={{
                      backgroundColor: `${p.color}12`,
                      ...(isSpeaking ? {
                        boxShadow: `0 0 0 2px white, 0 0 0 3.5px ${p.color}, 0 0 12px ${p.color}30`,
                      } : {}),
                    }}
                  >
                    <span
                      className={cn('w-1.5 h-1.5 rounded-full', isSpeaking && 'motion-safe:animate-pulse')}
                      style={{ backgroundColor: p.color }}
                    />
                    <span style={{ color: hasSpoken || isSpeaking ? p.color : undefined }}>
                      {p.agent_name.split(' ').pop()}
                    </span>
                    {hasSpoken && !isSpeaking && (
                      <svg aria-hidden="true" className="w-2.5 h-2.5 text-leaf" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Message Stream */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 md:px-6 py-6 space-y-1">
          {Array.from(rounds.entries()).map(([round, roundMessages]) => (
            <div key={round}>
              {/* Round divider */}
              <div className="flex items-center gap-4 my-6 first:mt-0">
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-taupe to-transparent" />
                <div className="flex items-center gap-2 px-4 py-1 bg-white rounded-full border border-line shadow-sm">
                  <svg aria-hidden="true" className="w-3.5 h-3.5 text-hotpink" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span className="text-[11px] font-bold text-ink-soft">
                    Round {round}
                  </span>
                </div>
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-taupe to-transparent" />
              </div>

              {/* Messages */}
              <div className="space-y-5">
                {roundMessages.map((msg, i) => {
                  const participant = participants.find(p => p.id === msg.participant_id)
                  return (
                    <MessageCard
                      key={msg.id}
                      msg={msg}
                      color={participant?.color || msg.color || '#6366f1'}
                      animDelay={i * 80}
                    />
                  )
                })}
              </div>
            </div>
          ))}

          {/* Currently streaming message */}
          {streamingParticipantId && streamingParticipantId !== 'synthesizer' && streamingContent && (
            <div className="mt-5">
              <MessageCard
                msg={{
                  agent_name: activeSpeaker?.agent_name || 'Agent',
                  content: streamingContent,
                  round: currentRound,
                }}
                color={activeSpeaker?.color || '#6366f1'}
                isStreaming
              />
            </div>
          )}

          {/* Thinking indicator (participant_start fired but no chunks yet) */}
          {streamingParticipantId && streamingParticipantId !== 'synthesizer' && !streamingContent && (
            <div className="mt-5">
              <ThinkingIndicator
                color={activeSpeaker?.color || '#6366f1'}
                name={activeSpeaker?.agent_name || 'Agent'}
              />
            </div>
          )}

          {/* Synthesis / Verdict */}
          {(isSynthesizing || (verdict && !streamingParticipantId)) && (
            <div className="mt-8">
              {/* Verdict divider */}
              <div className="flex items-center gap-4 my-6">
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-honey to-transparent" />
                <div className="flex items-center gap-2 px-4 py-1.5 bg-sand-deep rounded-full border border-honey shadow-sm">
                  <svg aria-hidden="true" className="w-3.5 h-3.5 text-warn" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
                  </svg>
                  <span className="text-[11px] font-bold text-gold">
                    The Verdict
                  </span>
                </div>
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-honey to-transparent" />
              </div>

              {/* Streaming verdict */}
              {isSynthesizing && streamingContent && (
                <MessageCard
                  msg={{
                    agent_name: 'The Synthesizer',
                    content: streamingContent,
                    round: 0,
                    is_verdict: true,
                  }}
                  color="#f59e0b"
                  isStreaming
                />
              )}
              {isSynthesizing && !streamingContent && (
                <ThinkingIndicator color="#f59e0b" name="The Synthesizer" />
              )}

              {/* Completed verdict */}
              {!streamingParticipantId && verdictMessages.map((msg) => (
                <MessageCard
                  key={msg.id}
                  msg={msg}
                  color="#f59e0b"
                />
              ))}
            </div>
          )}

          {/* Empty state */}
          {messages.length === 0 && !streamingParticipantId && (
            <div className="text-center py-20">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-sand-deep mb-4">
                <svg aria-hidden="true" className="w-7 h-7 text-hotpink" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <p className="text-sm text-ink-mute font-medium">Preparing your life audit…</p>
              <p className="text-xs text-ash mt-1">5 specialist agents are getting ready to debate.</p>
            </div>
          )}

          {/* Bottom padding for scroll */}
          <div className="h-8" />
        </div>
      </div>
    </div>
  )
}
