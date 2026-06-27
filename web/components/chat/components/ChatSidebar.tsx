'use client'

import { useState, useRef, useEffect } from 'react'
import {
  MessageSquare,
  Trash2,
  Settings,
  LogOut,
  User,
  ChevronDown,
  Share2,
  Pencil,
  Check,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface ChatSession {
  id: string
  title: string
  agentName: string
  lastMessage?: string
  timestamp: Date
  isActive?: boolean
}

interface ChatConfig {
  chat_primary_color?: string
  chat_background_color?: string
  chat_font_family?: string
}

interface ChatSidebarProps {
  sessions?: ChatSession[]
  activeSessionId?: string
  onSessionSelect?: (sessionId: string) => void
  onNewChat?: () => void
  onDeleteSession?: (sessionId: string) => void
  onRenameSession?: (sessionId: string, newName: string) => void
  onShareSession?: (sessionId: string) => void
  onSettingsClick?: () => void
  className?: string
  chatConfig?: ChatConfig | null
  agentName?: string
  agentAvatar?: string
  tenantName?: string
  tenantLogo?: string
}

/**
 * ChatSidebar - Left sidebar for managing chat sessions
 */
export function ChatSidebar({
  sessions = [],
  activeSessionId,
  onSessionSelect,
  onNewChat,
  onDeleteSession,
  onRenameSession,
  onShareSession,
  className,
  chatConfig,
  agentName,
  agentAvatar,
  tenantName,
  tenantLogo,
}: ChatSidebarProps) {
  const [showMenu, setShowMenu] = useState(false)

  const primaryColor = chatConfig?.chat_primary_color || '#0d9488'

  // Group sessions by time
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const lastWeek = new Date(today)
  lastWeek.setDate(lastWeek.getDate() - 7)

  const groupedSessions = {
    today: sessions.filter(s => s.timestamp >= today),
    yesterday: sessions.filter(s => s.timestamp >= yesterday && s.timestamp < today),
    lastWeek: sessions.filter(s => s.timestamp >= lastWeek && s.timestamp < yesterday),
    older: sessions.filter(s => s.timestamp < lastWeek),
  }

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header - Synkora Logo & Tenant Name */}
      <div className="p-4 border-b border-gray-100">
        <a
          href="/agents"
          className="flex items-center gap-2.5 hover:opacity-80 transition-opacity"
        >
          {tenantLogo ? (
            <img
              src={tenantLogo}
              alt={tenantName || 'Synkora'}
              className="w-8 h-8 rounded-lg object-contain flex-shrink-0"
            />
          ) : (
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-rose-500 to-pink-600 flex items-center justify-center flex-shrink-0 shadow-sm">
              <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                <path d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          )}
          <span className="font-bold text-gray-900 truncate">
            {tenantName || 'Synkora'}
          </span>
        </a>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-2 pt-2 pb-2">
        {sessions.length === 0 ? (
          <div className="py-12 text-center">
            <MessageSquare size={28} className="mx-auto text-gray-300 mb-3" />
            <p className="text-sm font-medium text-gray-400">No conversations</p>
            <p className="text-xs text-gray-400 mt-1">Start chatting to see history</p>
          </div>
        ) : (
          <div className="space-y-5">
            {groupedSessions.today.length > 0 && (
              <SessionGroup
                label="Today"
                sessions={groupedSessions.today}
                activeSessionId={activeSessionId}
                onSessionSelect={onSessionSelect}
                onDeleteSession={onDeleteSession}
                onRenameSession={onRenameSession}
                onShareSession={onShareSession}
                primaryColor={primaryColor}
              />
            )}
            {groupedSessions.yesterday.length > 0 && (
              <SessionGroup
                label="Yesterday"
                sessions={groupedSessions.yesterday}
                activeSessionId={activeSessionId}
                onSessionSelect={onSessionSelect}
                onDeleteSession={onDeleteSession}
                onRenameSession={onRenameSession}
                onShareSession={onShareSession}
                primaryColor={primaryColor}
              />
            )}
            {groupedSessions.lastWeek.length > 0 && (
              <SessionGroup
                label="Last 7 days"
                sessions={groupedSessions.lastWeek}
                activeSessionId={activeSessionId}
                onSessionSelect={onSessionSelect}
                onDeleteSession={onDeleteSession}
                onRenameSession={onRenameSession}
                onShareSession={onShareSession}
                primaryColor={primaryColor}
              />
            )}
            {groupedSessions.older.length > 0 && (
              <SessionGroup
                label="Older"
                sessions={groupedSessions.older}
                activeSessionId={activeSessionId}
                onSessionSelect={onSessionSelect}
                onDeleteSession={onDeleteSession}
                onRenameSession={onRenameSession}
                onShareSession={onShareSession}
                primaryColor={primaryColor}
              />
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-200/60">
        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-gray-100 rounded-xl transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
              <User size={16} className="text-gray-600" />
            </div>
            <span className="text-sm font-semibold text-gray-800 flex-1 text-left truncate">Settings</span>
            <ChevronDown size={16} className={cn('text-gray-400 transition-transform', showMenu && 'rotate-180')} />
          </button>

          {showMenu && (
            <div className="absolute bottom-full left-0 right-0 mb-1 bg-white rounded-xl shadow-lg border border-gray-200 py-1.5 z-50">
              <button
                onClick={() => {
                  window.location.href = '/settings/profile'
                  setShowMenu(false)
                }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                <User size={16} />
                Profile
              </button>
              <button
                onClick={() => {
                  const agent = window.location.pathname.split('/')[2]
                  window.location.href = `/agents/${agent}/edit`
                  setShowMenu(false)
                }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                <Settings size={16} />
                Agent Settings
              </button>
              <div className="border-t border-gray-100 my-1" />
              <button
                onClick={() => {
                  localStorage.removeItem('token')
                  window.location.href = '/signin'
                }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm font-medium text-red-600 hover:bg-red-50"
              >
                <LogOut size={16} />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

interface SessionGroupProps {
  label: string
  sessions: ChatSession[]
  activeSessionId?: string
  onSessionSelect?: (sessionId: string) => void
  onDeleteSession?: (sessionId: string) => void
  onRenameSession?: (sessionId: string, newName: string) => void
  onShareSession?: (sessionId: string) => void
  primaryColor: string
}

function SessionGroup({
  label,
  sessions,
  activeSessionId,
  onSessionSelect,
  onDeleteSession,
  onRenameSession,
  onShareSession,
  primaryColor,
}: SessionGroupProps) {
  return (
    <div>
      <p className="px-2 py-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide">
        {label}
      </p>
      <div className="space-y-1">
        {sessions.map((session) => (
          <SessionItem
            key={session.id}
            session={session}
            isActive={session.id === activeSessionId}
            onClick={() => onSessionSelect?.(session.id)}
            onDelete={() => onDeleteSession?.(session.id)}
            onRename={(newName) => onRenameSession?.(session.id, newName)}
            onShare={() => onShareSession?.(session.id)}
            primaryColor={primaryColor}
          />
        ))}
      </div>
    </div>
  )
}

interface SessionItemProps {
  session: ChatSession
  isActive?: boolean
  onClick?: () => void
  onDelete?: () => void
  onRename?: (newName: string) => void
  onShare?: () => void
  primaryColor: string
}

function SessionItem({ session, isActive, onClick, onDelete, onRename, onShare }: SessionItemProps) {
  const [showActions, setShowActions] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(session.title)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
  }, [isEditing])

  const startEditing = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditValue(session.title)
    setIsEditing(true)
  }

  const commitRename = () => {
    const trimmed = editValue.trim()
    if (trimmed && trimmed !== session.title) {
      onRename?.(trimmed)
    }
    setIsEditing(false)
  }

  const cancelRename = () => {
    setEditValue(session.title)
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') { e.preventDefault(); commitRename() }
    if (e.key === 'Escape') { e.preventDefault(); cancelRename() }
  }

  return (
    <div
      className={cn(
        'group relative flex items-center rounded-xl transition-all',
        isEditing ? 'bg-gray-100' : cn('cursor-pointer', isActive ? 'bg-gray-100' : 'hover:bg-gray-50')
      )}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {isEditing ? (
        <div className="flex flex-1 items-center gap-1 px-2 py-1.5 min-w-0">
          <input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={commitRename}
            className="flex-1 min-w-0 bg-white border border-gray-300 rounded-lg px-2 py-1 text-sm text-gray-900 focus:outline-none focus:border-gray-400"
          />
          <button
            onMouseDown={(e) => { e.preventDefault(); commitRename() }}
            className="p-1 hover:bg-gray-200 rounded-lg transition-colors flex-shrink-0"
            title="Save"
          >
            <Check size={13} className="text-green-600" />
          </button>
          <button
            onMouseDown={(e) => { e.preventDefault(); cancelRename() }}
            className="p-1 hover:bg-gray-200 rounded-lg transition-colors flex-shrink-0"
            title="Cancel"
          >
            <X size={13} className="text-gray-400" />
          </button>
        </div>
      ) : (
        <>
          <button
            onClick={onClick}
            onDoubleClick={onRename ? startEditing : undefined}
            className="flex-1 px-3 py-2.5 text-left min-w-0"
          >
            <p className={cn(
              'text-sm truncate',
              isActive ? 'font-semibold text-gray-900' : 'font-medium text-gray-700'
            )}>
              {session.title}
            </p>
          </button>

          {showActions && (
            <div className="flex items-center mr-1.5 gap-0.5">
              {onRename && (
                <button
                  onClick={startEditing}
                  className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                  title="Rename"
                >
                  <Pencil size={13} className="text-gray-400 hover:text-gray-700" />
                </button>
              )}
              {onShare && (
                <button
                  onClick={(e) => { e.stopPropagation(); onShare() }}
                  className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                  title="Share"
                >
                  <Share2 size={13} className="text-gray-400 hover:text-blue-500" />
                </button>
              )}
              {onDelete && (
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete() }}
                  className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                  title="Delete"
                >
                  <Trash2 size={13} className="text-gray-400 hover:text-red-500" />
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
