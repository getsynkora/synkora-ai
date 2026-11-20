'use client'

import { useState } from 'react'
import Image from 'next/image'
import { 
  Sparkles, 
  Settings, 
  Share2, 
  MoreVertical,
  Download,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface SuggestionPrompt {
  title: string
  description?: string
  icon?: string
  prompt: string
}

interface Agent {
  agent_name: string
  agent_type: string
  description?: string
  avatar?: string
  status: string
  model?: string
  provider?: string
  suggestion_prompts?: SuggestionPrompt[]
}

interface ChatConfig {
  chat_title?: string
  chat_logo_url?: string
  chat_welcome_message?: string
  chat_placeholder?: string
  chat_primary_color?: string
  chat_background_color?: string
  chat_font_family?: string
}

interface LLMConfig {
  id: string
  name?: string
  provider: string
  model_name: string
  enabled: boolean
  is_default: boolean
}

interface ChatHeaderProps {
  agent: Agent | null
  chatConfig?: ChatConfig | null
  llmConfigs?: LLMConfig[]
  selectedLLMConfigId?: string
  onLLMConfigChange?: (configId: string) => void
  onSettingsClick?: () => void
  onShareClick?: () => void
  onExportClick?: () => void
  onClearChat?: () => void
  onRefresh?: () => void
  className?: string
}

/**
 * ChatHeader - Header component with agent info and action buttons
 */
export function ChatHeader({
  agent,
  chatConfig,
  llmConfigs,
  selectedLLMConfigId,
  onLLMConfigChange,
  onSettingsClick,
  onShareClick,
  onExportClick,
  onClearChat,
  onRefresh,
  className,
}: ChatHeaderProps) {
  const [showMenu, setShowMenu] = useState(false)
  
  // Get enabled LLM configs for dropdown
  const enabledConfigs = llmConfigs?.filter(config => config.enabled) || []
  
  // Use custom title if available, otherwise fall back to agent name
  const displayTitle = chatConfig?.chat_title || agent?.agent_name || 'Agent'
  
  // Prioritize agent avatar for header display (logo is for sidebar only)
  const hasAgentAvatar = agent?.avatar
  
  // Get primary color for theming
  const primaryColor = chatConfig?.chat_primary_color || '#0d9488' // teal-600 as default
  
  // Generate gradient background for logo
  const logoGradient = `linear-gradient(135deg, ${primaryColor}, ${primaryColor}dd)`

  return (
    <div
      className={cn(
        'flex items-center justify-between px-4 py-2.5 border-b border-line/80 bg-white/95',
        className
      )}
    >
      {/* Agent Info - More Compact */}
      <div className="flex items-center gap-3">
        {hasAgentAvatar ? (
          <div className="w-9 h-9 rounded-lg overflow-hidden shadow-md flex items-center justify-center bg-white relative ring-2 ring-sand">
            {agent.avatar && (agent.avatar.startsWith('http://') || agent.avatar.startsWith('https://')) ? (
              <img
                src={agent.avatar}
                alt={displayTitle}
                className="w-full h-full object-cover"
              />
            ) : (
              <Image
                src={agent.avatar!}
                alt={displayTitle}
                fill
                className="object-cover"
              />
            )}
          </div>
        ) : (
          <div 
            className="w-9 h-9 rounded-lg flex items-center justify-center shadow-md ring-2 ring-white"
            style={{ background: logoGradient }}
          >
            <Sparkles size={18} className="text-white" />
          </div>
        )}
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-semibold text-ink">
              {displayTitle}
            </h1>
            <span
              className={cn(
                'px-1.5 py-0.5 rounded text-[10px] font-medium',
                agent?.status === 'active'
                  ? 'bg-leaf-wash text-forest'
                  : 'bg-sand text-ink-soft'
              )}
            >
              {agent?.status || 'Unknown'}
            </span>
          </div>
          <p className="text-xs text-ink-mute line-clamp-1">
            {agent?.agent_type === 'digital_clone' ? '🤖 Digital Clone' : agent?.description || agent?.agent_type || 'AI Assistant'}
          </p>
        </div>
      </div>

      {/* Action Buttons - More Compact */}
      <div className="flex items-center gap-1.5 min-w-0">
        {/* LLM Config Dropdown - Compact */}
        {enabledConfigs.length > 0 && (
          <select
            value={selectedLLMConfigId || ''}
            onChange={(e) => {
              if (onLLMConfigChange && e.target.value) {
                onLLMConfigChange(e.target.value)
              }
            }}
            className="hidden sm:block max-w-[160px] px-2.5 py-1.5 rounded-lg bg-cream border border-line text-xs font-medium text-ink-soft hover:bg-sand focus:outline-none focus:ring-2 focus:ring-warn focus:border-transparent cursor-pointer"
          >
            {enabledConfigs.map((config) => (
              <option key={config.id} value={config.id}>
                {config.provider}/{config.model_name}{config.is_default ? ' (default)' : ''}
              </option>
            ))}
          </select>
        )}
        
        {(!enabledConfigs.length && agent?.model) && (
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-cream border border-line">
            <span className="text-xs font-medium text-ink-soft">{agent.model}</span>
          </div>
        )}

        {/* Refresh - Compact */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="p-1.5 rounded-lg transition-colors hover:bg-sand-deep"
            style={{
              color: primaryColor,
            }}
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        )}

        {/* Share - Compact */}
        {onShareClick && (
          <button
            onClick={onShareClick}
            className="p-1.5 rounded-lg transition-colors hover:bg-sand-deep"
            style={{
              color: primaryColor,
            }}
            title="Share"
          >
            <Share2 size={16} />
          </button>
        )}

        {/* Settings - Compact */}
        {onSettingsClick && (
          <button
            onClick={onSettingsClick}
            className="p-1.5 rounded-lg transition-colors hover:bg-sand-deep"
            style={{
              color: primaryColor,
            }}
            title="Settings"
          >
            <Settings size={16} />
          </button>
        )}

        {/* More Menu - Compact */}
        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="p-1.5 rounded-lg hover:bg-cream transition-colors"
            title="More"
          >
            <MoreVertical size={16} className="text-ink-soft" />
          </button>

          {showMenu && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setShowMenu(false)}
              />
              <div className="absolute right-0 mt-1 w-40 bg-white rounded-lg shadow-xl border border-line py-1 z-20">
                {onExportClick && (
                  <button
                    onClick={() => {
                      onExportClick()
                      setShowMenu(false)
                    }}
                    className="w-full px-3 py-1.5 text-left text-xs text-ink-soft hover:bg-sand-deep flex items-center gap-2 transition-colors"
                  >
                    <Download size={14} />
                    Export
                  </button>
                )}
                {onClearChat && (
                  <button
                    onClick={() => {
                      onClearChat()
                      setShowMenu(false)
                    }}
                    className="w-full px-3 py-1.5 text-left text-xs text-leaf hover:bg-blush-wash flex items-center gap-2 transition-colors"
                  >
                    <Trash2 size={14} />
                    Clear
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
