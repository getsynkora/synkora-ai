'use client'

import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface ChatContainerProps {
  children: ReactNode
  className?: string
  showLeftSidebar?: boolean
  showRightSidebar?: boolean
  style?: React.CSSProperties
}

/**
 * ChatContainer - Main layout container for the chat interface
 * Provides a 3-column layout: left sidebar, main chat area, right sidebar
 */
export function ChatContainer({
  children,
  className,
  style,
}: ChatContainerProps) {
  return (
    <div
      className={cn(
        'flex h-screen w-full bg-cream',
        className
      )}
      style={style}
    >
      {children}
    </div>
  )
}

interface ChatContainerSectionProps {
  children: ReactNode
  className?: string
  side?: 'left' | 'center' | 'right'
  onMouseEnter?: () => void
  onMouseLeave?: () => void
}

/**
 * ChatContainerSection - Individual section within the container
 */
export function ChatContainerSection({
  children,
  className,
  side = 'center',
  onMouseEnter,
  onMouseLeave,
}: ChatContainerSectionProps) {
  const sideStyles = {
    left: 'hidden md:flex md:w-56 border-r border-line/60 bg-cream/50 flex-shrink-0 flex-col',
    center: 'flex-1 flex flex-col min-w-0 bg-white',
    right: 'hidden lg:flex lg:w-72 border-l border-line/60 bg-cream/30 flex-shrink-0 flex-col',
  }

  return (
    <div
      className={cn(sideStyles[side], className)}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {children}
    </div>
  )
}
