'use client'

import dynamic from 'next/dynamic'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

// Lazy-load the Prism parser (~480 KB with all grammars) — only downloaded when
// a code block appears in a participant's message.
const SyntaxHighlighter = dynamic(
  () => import('react-syntax-highlighter').then((m) => ({ default: m.Prism })),
  {
    ssr: false,
    loading: () => (
      <pre className="bg-gray-900 text-gray-100 p-4 text-[13px] font-mono overflow-x-auto whitespace-pre">{}</pre>
    ),
  }
)
import { BadgeCheck, ExternalLink, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils/cn'
import { useState, useCallback } from 'react'

interface ParticipantCardProps {
  agentName: string
  content: string
  round: number
  color: string
  isVerdict?: boolean
  isExternal?: boolean
  isStreaming?: boolean
  side: 'left' | 'right'
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [text])

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2.5 right-2.5 p-1.5 rounded-md bg-white/10 hover:bg-white/20 text-gray-400 hover:text-white transition-all opacity-0 group-hover/code:opacity-100"
      title="Copy code"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  )
}

export function ParticipantCard({
  agentName,
  content,
  round,
  color,
  isVerdict = false,
  isExternal = false,
  isStreaming = false,
  side,
}: ParticipantCardProps) {
  // Generate a subtle background tint from the agent's color
  const tintBg = `${color}08`
  const accentBorder = `${color}25`

  return (
    <div
      className={cn(
        'flex gap-3',
        side === 'right' && 'flex-row-reverse',
        isVerdict && 'max-w-full',
        !isVerdict && 'max-w-[90%]',
        side === 'right' && !isVerdict && 'ml-auto',
      )}
    >
      {/* Avatar */}
      <div className="flex flex-col items-center gap-1 flex-shrink-0 pt-1">
        <div
          className={cn(
            'w-9 h-9 rounded-xl flex items-center justify-center text-white text-sm font-semibold shadow-sm',
            isVerdict && 'w-10 h-10 rounded-xl',
          )}
          style={{
            backgroundColor: color,
            boxShadow: `0 2px 8px ${color}40`,
          }}
        >
          {isVerdict ? (
            <BadgeCheck className="w-5 h-5" />
          ) : (
            agentName.charAt(0).toUpperCase()
          )}
        </div>
      </div>

      {/* Message bubble */}
      <div className="flex-1 min-w-0">
        {/* Header row */}
        <div className={cn(
          'flex items-center gap-2 mb-1.5 px-1',
          side === 'right' && 'flex-row-reverse',
        )}>
          <span
            className="text-[13px] font-semibold"
            style={{ color }}
          >
            {agentName}
          </span>
          {isVerdict && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 bg-amber-100 text-amber-800 rounded-md uppercase tracking-wide">
              Verdict
            </span>
          )}
          {isExternal && (
            <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 bg-purple-50 text-purple-700 rounded-md border border-purple-200">
              <ExternalLink className="w-2.5 h-2.5" />
              External
            </span>
          )}
          {!isVerdict && round > 0 && (
            <span className="text-[10px] text-gray-400 font-medium">R{round}</span>
          )}
        </div>

        {/* Content card */}
        <div
          className={cn(
            'rounded-2xl px-5 py-4 shadow-sm transition-all',
            isVerdict
              ? 'bg-gradient-to-br from-amber-50 via-amber-50/80 to-orange-50 border border-amber-200/60 shadow-amber-100/50'
              : 'bg-white border',
            side === 'left' && !isVerdict && 'rounded-tl-md',
            side === 'right' && !isVerdict && 'rounded-tr-md',
          )}
          style={!isVerdict ? {
            backgroundColor: `color-mix(in srgb, ${color} 3%, white)`,
            borderColor: accentBorder,
          } : undefined}
        >
          {/* Markdown content */}
          <div className={cn(
            'debate-markdown',
            isStreaming && 'streaming',
          )}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => (
                  <h1 className="text-lg font-bold text-gray-900 mt-4 mb-2 first:mt-0">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-base font-bold text-gray-900 mt-4 mb-2 first:mt-0">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-sm font-bold text-gray-800 mt-3 mb-1.5 first:mt-0">{children}</h3>
                ),
                p: ({ children }) => (
                  <p className="text-[13.5px] leading-[1.7] text-gray-700 mb-3 last:mb-0">{children}</p>
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold text-gray-900">{children}</strong>
                ),
                em: ({ children }) => (
                  <em className="italic text-gray-600">{children}</em>
                ),
                ul: ({ children }) => (
                  <ul className="space-y-1 mb-3 last:mb-0 ml-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="space-y-1 mb-3 last:mb-0 ml-1 list-decimal list-inside">{children}</ol>
                ),
                li: ({ children }) => (
                  <li className="text-[13.5px] leading-[1.7] text-gray-700 flex gap-2">
                    <span className="text-gray-400 mt-px select-none flex-shrink-0">&#8226;</span>
                    <span className="flex-1">{children}</span>
                  </li>
                ),
                blockquote: ({ children }) => (
                  <blockquote
                    className="border-l-3 pl-4 my-3 py-1 italic text-gray-600 bg-gray-50/50 rounded-r-lg"
                    style={{ borderLeftColor: `${color}60` }}
                  >
                    {children}
                  </blockquote>
                ),
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 underline decoration-blue-300 underline-offset-2 hover:decoration-blue-500 transition-colors"
                  >
                    {children}
                  </a>
                ),
                hr: () => <hr className="my-4 border-gray-200" />,
                table: ({ children }) => (
                  <div className="overflow-x-auto my-3 rounded-lg border border-gray-200">
                    <table className="min-w-full text-[13px]">{children}</table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-gray-50">{children}</thead>
                ),
                th: ({ children }) => (
                  <th className="px-3 py-2 text-left font-semibold text-gray-700 border-b border-gray-200">{children}</th>
                ),
                td: ({ children }) => (
                  <td className="px-3 py-2 text-gray-600 border-b border-gray-100">{children}</td>
                ),
                code: ({ className, children, ...props }: any) => {
                  const match = /language-(\w+)/.exec(className || '')
                  const language = match ? match[1] : ''
                  const codeString = String(children).replace(/\n$/, '')
                  const isInline = !className && !codeString.includes('\n')

                  if (isInline) {
                    return (
                      <code
                        className="px-1.5 py-0.5 rounded-md text-[12.5px] font-mono bg-gray-100 text-gray-800 border border-gray-200/60"
                        {...props}
                      >
                        {children}
                      </code>
                    )
                  }

                  return (
                    <div className="relative group/code my-3 rounded-xl overflow-hidden border border-gray-200/50">
                      {language && (
                        <div className="flex items-center justify-between px-4 py-1.5 bg-[#1e1e2e] border-b border-white/5">
                          <span className="text-[10px] font-mono text-gray-500 uppercase tracking-wider">{language}</span>
                        </div>
                      )}
                      <CopyButton text={codeString} />
                      <SyntaxHighlighter
                        style={oneDark}
                        language={language || 'text'}
                        PreTag="div"
                        customStyle={{
                          margin: 0,
                          padding: '16px',
                          fontSize: '12.5px',
                          lineHeight: '1.6',
                          background: '#1e1e2e',
                          borderRadius: 0,
                        }}
                        {...props}
                      >
                        {codeString}
                      </SyntaxHighlighter>
                    </div>
                  )
                },
              }}
            >
              {content}
            </ReactMarkdown>
            {isStreaming && (
              <span
                className="inline-block w-[3px] h-[18px] rounded-full animate-pulse ml-0.5 align-text-bottom"
                style={{ backgroundColor: color }}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
