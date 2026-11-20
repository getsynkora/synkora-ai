'use client'

import { useState, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface ExampleConversationProps {
  title: string
  messages: Message[]
  autoPlay?: boolean
  delay?: number
  theme?: 'dark' | 'light'
  accentColor?: string
}

export function ExampleConversation({
  title,
  messages,
  autoPlay = true,
  delay = 800,
  theme = 'dark',
  accentColor = '#e11d48',
}: ExampleConversationProps) {
  const validMessages = messages.filter(m => m.content?.trim())
  const [visibleCount, setVisibleCount] = useState(0)

  useEffect(() => {
    if (!autoPlay) {
      setVisibleCount(validMessages.length)
      return
    }
    if (visibleCount >= validMessages.length) return
    const timer = setTimeout(() => setVisibleCount(v => v + 1), delay)
    return () => clearTimeout(timer)
  }, [visibleCount, validMessages.length, autoPlay, delay])

  const isLight = theme === 'light'

  return (
    <div className={`rounded-2xl overflow-hidden border shadow-sm ${
      isLight
        ? 'bg-white border-line'
        : 'bg-white/5 border-white/10'
    }`}>
      {/* Title bar */}
      <div className={`px-4 py-3 border-b flex items-center gap-3 ${
        isLight ? 'bg-cream border-sand' : 'bg-white/5 border-white/5'
      }`}>
        <div className="flex gap-1.5">
          <div className={`w-3 h-3 rounded-full ${isLight ? 'bg-taupe' : 'bg-white/10'}`} />
          <div className={`w-3 h-3 rounded-full ${isLight ? 'bg-taupe' : 'bg-white/10'}`} />
          <div className={`w-3 h-3 rounded-full ${isLight ? 'bg-taupe' : 'bg-white/10'}`} />
        </div>
        <span className={`text-xs font-medium ${isLight ? 'text-ink-mute' : 'text-white/30'}`}>
          {title}
        </span>
      </div>

      {/* Messages */}
      <div className="p-5 space-y-3 min-h-[120px]">
        {validMessages.slice(0, visibleCount).map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            style={{ animation: 'fadeInUp 0.3s ease forwards' }}
          >
            {msg.role === 'assistant' && (
              <div
                className="w-6 h-6 rounded-full flex-shrink-0 mr-2 mt-0.5 flex items-center justify-center text-white text-xs font-bold"
                style={{ background: accentColor }}
              >
                AI
              </div>
            )}
            <div
              className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                msg.role === 'user'
                  ? isLight
                    ? 'bg-sand text-ink'
                    : 'bg-white/10 text-white/90'
                  : isLight
                    ? 'bg-white border border-line text-ink-soft shadow-sm'
                    : 'bg-white/5 border border-white/5 text-white/70'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {visibleCount < validMessages.length && (
          <div className="flex items-center justify-start gap-2">
            <div
              className="w-6 h-6 rounded-full flex-shrink-0 flex items-center justify-center text-white text-xs font-bold"
              style={{ background: accentColor }}
            >
              AI
            </div>
            <div className={`px-4 py-3 rounded-2xl flex gap-1.5 ${
              isLight ? 'bg-white border border-line shadow-sm' : 'bg-white/5 border border-white/5'
            }`}>
              {[0, 1, 2].map(i => (
                <div
                  key={i}
                  className={`w-1.5 h-1.5 rounded-full ${isLight ? 'bg-ash' : 'bg-white/30'}`}
                  style={{ animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite` }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-4px); }
        }
      `}</style>
    </div>
  )
}
