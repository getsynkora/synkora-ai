'use client'

import { Agent } from '@/components/chat/types'

interface ChatConfig {
  chat_title?: string
  chat_logo_url?: string
  chat_primary_color?: string
  chat_header_background_color?: string
  chat_header_text_color?: string
  show_powered_by?: boolean
  powered_by_text?: string
  powered_by_url?: string
}

interface CustomChatHeaderProps {
  agent: Agent | null
  chatConfig: ChatConfig | null
  onClearChat?: () => void
  onRefresh?: () => void
}

export function CustomChatHeader({ agent, chatConfig, onClearChat, onRefresh }: CustomChatHeaderProps) {
  const headerBgColor = chatConfig?.chat_header_background_color || chatConfig?.chat_primary_color || '#10b981'
  const headerTextColor = chatConfig?.chat_header_text_color || '#ffffff'
  const showPoweredBy = chatConfig?.show_powered_by !== false
  const poweredByText = chatConfig?.powered_by_text || 'Powered by Synkora'
  const poweredByUrl = chatConfig?.powered_by_url || 'https://synkora.ai'

  return (
    <div 
      className="flex items-center justify-between px-6 py-4 border-b"
      style={{ 
        backgroundColor: headerBgColor,
        color: headerTextColor,
        borderBottomColor: `${headerBgColor}dd`
      }}
    >
      {/* Left: Logo and Title */}
      <div className="flex items-center gap-3">
        {chatConfig?.chat_logo_url ? (
          <img 
            src={chatConfig.chat_logo_url} 
            alt="Logo" 
            className="h-10 w-10 rounded-lg object-cover"
          />
        ) : (
          <div 
            className="h-10 w-10 rounded-lg flex items-center justify-center font-bold text-lg"
            style={{ backgroundColor: `${headerTextColor}20` }}
          >
            {(chatConfig?.chat_title || agent?.agent_name || 'AI')?.charAt(0).toUpperCase()}
          </div>
        )}
        <div>
          <h1 className="text-lg font-semibold">
            {chatConfig?.chat_title || agent?.agent_name || 'AI Assistant'}
          </h1>
          {agent?.description && (
            <p className="text-sm opacity-80 line-clamp-1">
              {agent.description}
            </p>
          )}
        </div>
      </div>

      {/* Right: Actions and Powered By */}
      <div className="flex items-center gap-3">
        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-2 rounded-lg transition-colors hover:bg-white/10"
              title="Refresh"
            >
              <svg aria-hidden="true" className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          )}
          {onClearChat && (
            <button
              onClick={onClearChat}
              className="p-2 rounded-lg transition-colors hover:bg-white/10"
              title="New Chat"
            >
              <svg aria-hidden="true" className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          )}
        </div>

        {/* Powered By Badge */}
        {showPoweredBy && (
          <a
            href={poweredByUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-white/10"
            style={{ backgroundColor: `${headerTextColor}10` }}
          >
            <svg aria-hidden="true" className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" />
            </svg>
            <span>{poweredByText}</span>
          </a>
        )}
      </div>
    </div>
  )
}
