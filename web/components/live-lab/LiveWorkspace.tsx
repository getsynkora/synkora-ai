'use client'

import { useEffect, useRef } from 'react'

interface LiveWorkspaceProps {
  content: string
  isStreaming: boolean
}

export function LiveWorkspace({ content, isStreaming }: LiveWorkspaceProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isStreaming && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [content, isStreaming])

  return (
    <div className="flex h-full flex-col bg-transparent">
      <div className="flex items-center justify-between border-b border-[#eadfce] bg-[#f7f1e7] px-5 py-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8c6b4d]">Output</h3>
        {isStreaming && (
          <span className="flex items-center gap-1.5 rounded-full border border-[#cfe5d7] bg-[#edf7f1] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#24543b]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#2b7a52] animate-pulse" />
            Streaming
          </span>
        )}
      </div>
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.98),_rgba(248,242,233,0.96)_58%,_rgba(241,232,220,0.95)_100%)] px-5 py-5"
      >
        {!content ? (
          <div className="flex h-full items-center justify-center">
            <p className="rounded-[1.2rem] border border-dashed border-[#ddcfbc] bg-white/80 px-5 py-4 text-sm font-medium text-[#8c6b4d]">
              {isStreaming ? 'Waiting for output...' : 'No output generated'}
            </p>
          </div>
        ) : (
          <div className="prose prose-sm max-w-none">
            <div className="whitespace-pre-wrap rounded-[1.35rem] border border-white/75 bg-white/82 px-4 py-4 font-mono text-[13px] leading-6 text-[#41382e] shadow-[0_22px_50px_-44px_rgba(76,52,31,0.4)]">
              {content}
              {isStreaming && (
                <span className="ml-0.5 inline-block h-4 w-2 animate-pulse align-text-bottom bg-[#2b7a52]" />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
