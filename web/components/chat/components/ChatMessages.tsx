'use client'

import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { Attachment, FormDefinition, Message, SuggestionPrompt } from '../types'
import { ChatMessage } from './ChatMessage'
import { Sparkles, MessageSquare, Lightbulb } from 'lucide-react'

interface ChatConfig {
  chat_title?: string
  chat_logo_url?: string
  chat_welcome_message?: string
  chat_placeholder?: string
  chat_primary_color?: string
  chat_background_color?: string
  chat_font_family?: string
}

interface ToolStatus {
  tool_name: string
  status: 'started' | 'completed' | 'error'
  description: string
  details?: {
    file_path?: string
    path?: string
    command?: string
    repo_url?: string
    url?: string
    branch?: string
  }
  duration_ms?: number
  input_tokens?: number
  output_tokens?: number
}

interface ChatMessagesProps {
  messages: Message[]
  isStreaming?: boolean
  onCopyMessage?: (content: string, messageId: string) => void
  onRetry?: (messageId: string) => void
  onDeleteMessage?: (messageId: string) => void
  thinkingStatus?: string
  toolStatus?: ToolStatus | null
  recentTools?: ToolStatus[]
  streamStartTime?: number | null
  className?: string
  suggestionPrompts?: SuggestionPrompt[]
  onSuggestionClick?: (prompt: string) => void
  onActionClick?: (text: string) => void
  chatConfig?: ChatConfig | null
  agentAvatar?: string
  userAvatar?: string
  userName?: string
  agentName?: string
  conversationId?: string
  onFormSubmit?: (form: FormDefinition, answers: Record<string, unknown>, attachments?: Attachment[]) => Promise<void> | void
  formSubmissionDisabled?: boolean
  onFeedback?: (messageId: string, rating: 1 | -1) => void
}

/**
 * ChatMessages - Scrollable container for displaying chat messages
 * Implements auto-scroll and virtual scrolling for performance
 */
export function ChatMessages({
  messages,
  isStreaming = false,
  onCopyMessage,
  onRetry,
  onDeleteMessage,
  thinkingStatus,
  toolStatus,
  recentTools = [],
  streamStartTime,
  className,
  suggestionPrompts = [],
  onSuggestionClick,
  onActionClick,
  chatConfig,
  agentAvatar,
  userAvatar,
  userName,
  agentName,
  conversationId,
  onFormSubmit,
  formSubmissionDisabled = false,
  onFeedback,
}: ChatMessagesProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const shouldAutoScrollRef = useRef(true)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      scrollToBottom()
    }
  }, [messages])

  // Check if user has scrolled up
  const handleScroll = () => {
    if (!containerRef.current) return

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100

    shouldAutoScrollRef.current = isNearBottom
  }

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior })
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className={cn(
        'flex-1 overflow-y-auto overflow-x-hidden px-3 py-3 sm:px-4 sm:py-4 lg:px-5',
        className
      )}
    >
      {messages.length === 0 ? (
        <EmptyState
          suggestionPrompts={suggestionPrompts}
          onSuggestionClick={onSuggestionClick}
          chatConfig={chatConfig}
        />
      ) : (
        <div className="mx-auto max-w-[68rem] space-y-5">
          {messages.map((message, index) => {
            const isLastMessage = index === messages.length - 1
            const isStreamingMessage = isStreaming && isLastMessage

            return (
              <ChatMessage
                key={message.id}
                message={message}
                isStreaming={isStreamingMessage}
                thinkingStatus={isStreamingMessage ? thinkingStatus : undefined}
                toolStatus={isStreamingMessage ? toolStatus : undefined}
                recentTools={isStreamingMessage ? recentTools : []}
                streamStartTime={isStreamingMessage ? streamStartTime : undefined}
                onCopy={onCopyMessage}
                onRetry={onRetry}
                onDelete={onDeleteMessage}
                onActionClick={onActionClick}
                chatConfig={chatConfig}
                agentAvatar={agentAvatar}
                userAvatar={userAvatar}
                userName={userName}
                agentName={agentName}
                conversationId={conversationId}
                onFormSubmit={onFormSubmit}
                formSubmissionDisabled={formSubmissionDisabled}
                onFeedback={onFeedback}
              />
            )
          })}
          <div ref={messagesEndRef} />
        </div>
      )}
    </div>
  )
}

interface EmptyStateProps {
  suggestionPrompts?: SuggestionPrompt[]
  onSuggestionClick?: (prompt: string) => void
  chatConfig?: ChatConfig | null
}

function EmptyState({ suggestionPrompts = [], onSuggestionClick, chatConfig }: EmptyStateProps) {
  const primaryColor = chatConfig?.chat_primary_color || '#0d9488'
  const welcomeMessage = chatConfig?.chat_welcome_message || 'Ask me anything! I\'m here to help you with information, analysis, and creative tasks.'
  const hasConfiguredPrompts = suggestionPrompts.length > 0

  const getIconComponent = (iconName?: string) => {
    if (!iconName) {
      return <Sparkles size={22} />
    }
    if (iconName.length <= 4 && /\p{Emoji}/u.test(iconName)) {
      return <span className="text-2xl">{iconName}</span>
    }
    switch (iconName.toLowerCase()) {
      case 'sparkles':
        return <Sparkles size={22} />
      case 'message':
      case 'messagesquare':
        return <MessageSquare size={22} />
      case 'lightbulb':
      case 'bulb':
        return <Lightbulb size={22} />
      default:
        return <span className="text-2xl">{iconName}</span>
    }
  }

  return (
    <div className="flex h-full flex-col items-center justify-center px-3 py-4 text-center sm:px-4 sm:py-6">
      {/* Hero Icon */}
      <div
        className="mb-3 flex h-12 w-12 items-center justify-center rounded-[1.1rem] border border-white/60 shadow-[0_16px_30px_-24px_rgba(31,22,15,0.2)]"
        style={{
          background: `linear-gradient(180deg, ${primaryColor}18, rgba(255,255,255,0.78))`
        }}
      >
        <Sparkles
          size={20}
          style={{ color: primaryColor }}
        />
      </div>

      {/* Bold Heading */}
      <h1 className="mb-1.5 text-[1.7rem] font-semibold tracking-[-0.05em] text-gray-900 md:text-[2.1rem]">
        How can I help you today?
      </h1>
      <p className="mb-4 max-w-[36rem] text-[0.92rem] leading-6 text-gray-500 md:text-[1rem] md:leading-7">
        {welcomeMessage}
      </p>

      {/* Suggestion Cards */}
      {hasConfiguredPrompts ? (
        <div className="grid w-full max-w-[42rem] grid-cols-1 gap-2.5 md:grid-cols-2">
          {suggestionPrompts.map((prompt, index) => (
            <button
              key={index}
              onClick={() => onSuggestionClick?.(prompt.prompt)}
              className="group flex items-start gap-2.5 rounded-[1.1rem] border border-black/10 bg-[linear-gradient(180deg,_rgba(255,255,255,0.78),_rgba(250,245,238,0.96))] p-3 text-left shadow-[0_18px_34px_-32px_rgba(31,22,15,0.22)] transition-all duration-200 hover:-translate-y-0.5 hover:border-black/15 hover:shadow-[0_22px_40px_-28px_rgba(31,22,15,0.26)]"
            >
              <div
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[0.85rem] border border-white/70"
                style={{
                  background: `linear-gradient(135deg, ${primaryColor}18, ${primaryColor}08)`
                }}
              >
                <div style={{ color: primaryColor }}>
                  {getIconComponent(prompt.icon)}
                </div>
              </div>
              <div className="min-w-0 flex-1 pt-0.5">
                <div className="mb-0.5 text-[0.98rem] font-semibold tracking-[-0.03em] text-gray-900 sm:text-[1.02rem]">
                  {prompt.title}
                </div>
                {prompt.description && (
                  <div className="text-[0.86rem] leading-5 text-gray-500">
                    {prompt.description}
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="grid w-full max-w-[42rem] grid-cols-1 gap-2.5 md:grid-cols-2">
          <SuggestionCard
            icon="💡"
            title="Get Ideas"
            description="Brainstorm creative solutions and explore possibilities"
            onSuggestionClick={onSuggestionClick}
          />
          <SuggestionCard
            icon="📊"
            title="Analyze Data"
            description="Extract insights and patterns from your information"
            onSuggestionClick={onSuggestionClick}
          />
          <SuggestionCard
            icon="✍️"
            title="Write Content"
            description="Create engaging copy, articles, and documentation"
            onSuggestionClick={onSuggestionClick}
          />
          <SuggestionCard
            icon="🔍"
            title="Research"
            description="Deep dive into topics and gather information"
            onSuggestionClick={onSuggestionClick}
          />
        </div>
      )}
    </div>
  )
}

interface SuggestionCardProps {
  icon: string
  title: string
  description?: string
  onSuggestionClick?: (prompt: string) => void
}

function SuggestionCard({ icon, title, description, onSuggestionClick }: SuggestionCardProps) {
  return (
    <button
      onClick={() => onSuggestionClick?.(title)}
      className="group flex items-start gap-2.5 rounded-[1.1rem] border border-black/10 bg-[linear-gradient(180deg,_rgba(255,255,255,0.78),_rgba(250,245,238,0.96))] p-3 text-left shadow-[0_18px_34px_-32px_rgba(31,22,15,0.22)] transition-all duration-200 hover:-translate-y-0.5 hover:border-black/15 hover:shadow-[0_22px_40px_-28px_rgba(31,22,15,0.26)]"
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[0.85rem] border border-white/70 bg-[linear-gradient(180deg,_rgba(255,255,255,0.78),_rgba(246,239,230,0.92))] text-[1.2rem]">
        <span>{icon}</span>
      </div>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="mb-0.5 text-[0.98rem] font-semibold tracking-[-0.03em] text-gray-900">{title}</div>
        {description && (
          <div className="text-[0.86rem] leading-5 text-gray-500">{description}</div>
        )}
      </div>
    </button>
  )
}
