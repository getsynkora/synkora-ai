'use client'

import { useEffect, useRef } from 'react'
import { Swords, Scale } from 'lucide-react'
import { ParticipantCard } from './ParticipantCard'
import type { DebateMessage, DebateParticipant } from '@/lib/api/war-room'

interface DebateArenaProps {
  messages: DebateMessage[]
  participants: DebateParticipant[]
  streamingParticipantId: string | null
  streamingContent: string
  verdict: string | null
}

export function DebateArena({
  messages,
  participants,
  streamingParticipantId,
  streamingContent,
  verdict,
}: DebateArenaProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages.length, streamingContent])

  // Determine side for each participant (alternate left/right)
  const participantSides = new Map<string, 'left' | 'right'>()
  participants.forEach((p, i) => {
    participantSides.set(p.id, i % 2 === 0 ? 'left' : 'right')
  })

  // Group messages by round
  const rounds = new Map<number, DebateMessage[]>()
  for (const msg of messages) {
    if (!rounds.has(msg.round)) rounds.set(msg.round, [])
    rounds.get(msg.round)!.push(msg)
  }

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto px-4 md:px-6 py-6 space-y-2">
        {Array.from(rounds.entries()).map(([round, roundMessages]) => (
          <div key={round}>
            {/* Round divider */}
            <div className="flex items-center gap-4 my-8">
              <div className="flex-1 h-px bg-gradient-to-r from-transparent via-taupe to-transparent" />
              <div className="flex items-center gap-2 px-4 py-1.5 bg-white rounded-full border border-line shadow-sm">
                <Swords className="w-3.5 h-3.5 text-ash" />
                <span className="text-xs font-semibold text-ink-soft">
                  Round {round}
                </span>
              </div>
              <div className="flex-1 h-px bg-gradient-to-r from-transparent via-taupe to-transparent" />
            </div>

            {/* Messages */}
            <div className="space-y-5">
              {roundMessages
                .filter((m) => !m.is_verdict)
                .map((msg) => (
                  <ParticipantCard
                    key={msg.id}
                    agentName={msg.agent_name}
                    content={msg.content}
                    round={msg.round}
                    color={msg.color}
                    isExternal={msg.is_external}
                    side={participantSides.get(msg.participant_id) || 'left'}
                  />
                ))}
            </div>
          </div>
        ))}

        {/* Streaming indicator */}
        {streamingParticipantId && streamingParticipantId !== 'synthesizer' && (
          <div className="space-y-5">
            <ParticipantCard
              agentName={participants.find((p) => p.id === streamingParticipantId)?.agent_name || 'Agent'}
              content={streamingContent}
              round={0}
              color={participants.find((p) => p.id === streamingParticipantId)?.color || '#6366f1'}
              side={participantSides.get(streamingParticipantId) || 'left'}
              isStreaming
            />
          </div>
        )}

        {/* Synthesis streaming */}
        {streamingParticipantId === 'synthesizer' && (
          <div className="mt-10">
            <div className="flex items-center gap-4 my-8">
              <div className="flex-1 h-px bg-gradient-to-r from-transparent via-honey to-transparent" />
              <div className="flex items-center gap-2 px-4 py-1.5 bg-sand-deep rounded-full border border-honey shadow-sm">
                <Scale className="w-3.5 h-3.5 text-warn" />
                <span className="text-xs font-bold text-gold">
                  The Verdict
                </span>
              </div>
              <div className="flex-1 h-px bg-gradient-to-r from-transparent via-honey to-transparent" />
            </div>
            <ParticipantCard
              agentName="Synthesizer"
              content={streamingContent}
              round={0}
              color="#f59e0b"
              isVerdict
              isStreaming
              side="left"
            />
          </div>
        )}

        {/* Final verdict (after streaming complete) */}
        {verdict && !streamingParticipantId && (
          <div className="mt-10">
            <div className="flex items-center gap-4 my-8">
              <div className="flex-1 h-px bg-gradient-to-r from-transparent via-honey to-transparent" />
              <div className="flex items-center gap-2 px-4 py-1.5 bg-sand-deep rounded-full border border-honey shadow-sm">
                <Scale className="w-3.5 h-3.5 text-warn" />
                <span className="text-xs font-bold text-gold">
                  The Verdict
                </span>
              </div>
              <div className="flex-1 h-px bg-gradient-to-r from-transparent via-honey to-transparent" />
            </div>
            {messages
              .filter((m) => m.is_verdict)
              .map((msg) => (
                <ParticipantCard
                  key={msg.id}
                  agentName={msg.agent_name}
                  content={msg.content}
                  round={msg.round}
                  color="#f59e0b"
                  isVerdict
                  side="left"
                />
              ))}
          </div>
        )}

        {messages.length === 0 && !streamingParticipantId && (
          <div className="text-center py-20">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-sand mb-4">
              <Swords className="w-7 h-7 text-ash" />
            </div>
            <p className="text-sm text-ink-mute font-medium">The debate will appear here once started.</p>
            <p className="text-xs text-ash mt-1">Click "Start Debate" to begin the discussion.</p>
          </div>
        )}
      </div>
    </div>
  )
}
