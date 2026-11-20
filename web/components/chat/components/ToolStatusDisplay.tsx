'use client'

import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { Check, Loader2, AlertCircle, Terminal, FileText, GitBranch, Globe, Database, Search, Clock, Timer } from 'lucide-react'

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

interface ToolStatusDisplayProps {
  currentTool: ToolStatus | null
  recentTools: ToolStatus[]
  primaryColor?: string
  className?: string
  isStreaming?: boolean
  streamStartTime?: number | null
}

/**
 * Get an icon for the tool based on its name
 */
function getToolIcon(toolName: string) {
  if (toolName.includes('file') || toolName.includes('write') || toolName.includes('read') || toolName.includes('edit')) {
    return FileText
  }
  if (toolName.includes('git') || toolName.includes('branch') || toolName.includes('commit')) {
    return GitBranch
  }
  if (toolName.includes('browser') || toolName.includes('web') || toolName.includes('navigate')) {
    return Globe
  }
  if (toolName.includes('sql') || toolName.includes('database') || toolName.includes('query')) {
    return Database
  }
  if (toolName.includes('search')) {
    return Search
  }
  return Terminal
}

/**
 * Format duration in a human-readable way
 */
function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`
  }
  const seconds = ms / 1000
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`
  }
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = (seconds % 60).toFixed(0)
  return `${minutes}m ${remainingSeconds}s`
}

/**
 * Format elapsed time for the overall timer (more readable format)
 */
function formatElapsedTime(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60

  if (minutes > 0) {
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
  }
  return `0:${remainingSeconds.toString().padStart(2, '0')}`
}

/**
 * ToolStatusDisplay - Displays tool execution status like Claude Code CLI
 * Shows clear distinction between running and completed tools with timing info
 */
export function ToolStatusDisplay({
  currentTool,
  recentTools,
  primaryColor = '#0d9488',
  className,
  isStreaming = false,
  streamStartTime = null,
}: ToolStatusDisplayProps) {
  const [elapsedTime, setElapsedTime] = useState(0)

  // Update elapsed time every 500ms while streaming (was 100ms = 10 re-renders/sec)
  useEffect(() => {
    if (!isStreaming || !streamStartTime) {
      return
    }

    const interval = setInterval(() => {
      setElapsedTime(Date.now() - streamStartTime)
    }, 500)

    return () => clearInterval(interval)
  }, [isStreaming, streamStartTime])

  // Reset elapsed time when streaming stops
  useEffect(() => {
    if (!isStreaming) {
      // Keep the final time displayed for a moment
    }
  }, [isStreaming])

  // Don't render if there's no current tool and no recent tools
  if (!currentTool && recentTools.length === 0) {
    return null
  }

  // Combine current and recent tools for display (max 5 items)
  const allTools = currentTool
    ? [currentTool, ...recentTools.slice(0, 4)]
    : recentTools.slice(0, 5)

  return (
    <div
      className={cn(
        'rounded-lg border border-line bg-white overflow-hidden shadow-sm',
        className
      )}
    >
      {/* Header with overall timer */}
      {(isStreaming || elapsedTime > 0) && (
        <div
          className="flex items-center justify-between px-3 py-2 border-b border-sand"
          style={{ backgroundColor: `${primaryColor}08` }}
        >
          <div className="flex items-center gap-2">
            {isStreaming && (
              <Loader2
                size={14}
                className="motion-safe:animate-spin"
                style={{ color: primaryColor }}
              />
            )}
            <span className="text-xs font-medium text-ink-soft">
              {isStreaming ? 'Processing' : 'Completed'}
            </span>
          </div>
          <div
            className="flex items-center gap-1.5 text-xs font-mono tabular-nums"
            style={{ color: primaryColor }}
          >
            <Timer size={12} />
            <span>{formatElapsedTime(elapsedTime)}</span>
          </div>
        </div>
      )}

      {/* Tool list */}
      <div className="divide-y divide-sand">
        {allTools.map((tool, index) => {
          const Icon = getToolIcon(tool.tool_name)
          const isRunning = tool.status === 'started'
          const isCompleted = tool.status === 'completed'
          const isError = tool.status === 'error'

          return (
            <div
              key={`${tool.tool_name}-${index}`}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 transition-colors',
                isRunning && 'bg-sand-deep/50'
              )}
            >
              {/* Status indicator */}
              <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
                {isRunning ? (
                  <div className="relative">
                    {/* Animated spinner for running */}
                    <Loader2
                      size={18}
                      className="motion-safe:animate-spin"
                      style={{ color: primaryColor }}
                    />
                    {/* Pulsing ring for more visibility */}
                    <div
                      className="absolute inset-0 rounded-full motion-safe:animate-ping opacity-30"
                      style={{ backgroundColor: primaryColor }}
                    />
                  </div>
                ) : isCompleted ? (
                  <div
                    className="w-5 h-5 rounded flex items-center justify-center"
                    style={{ backgroundColor: 'rgb(var(--mint))' }}
                  >
                    <Check size={12} className="text-white" strokeWidth={3} />
                  </div>
                ) : (
                  <div className="w-5 h-5 rounded bg-ink flex items-center justify-center">
                    <AlertCircle size={12} className="text-white" />
                  </div>
                )}
              </div>

              {/* Tool icon */}
              <Icon
                size={14}
                className={cn(
                  'flex-shrink-0',
                  isRunning ? 'text-ink-soft' : 'text-ash'
                )}
              />

              {/* Description */}
              <span
                className={cn(
                  'text-sm flex-1 truncate',
                  isRunning ? 'text-ink font-medium' : 'text-ink-mute'
                )}
              >
                {tool.description}
              </span>

              {/* Metrics (duration, tokens) */}
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* File path or detail (if available) */}
                {tool.details?.file_path && (
                  <span className="text-ash truncate max-w-[100px] text-xs font-mono">
                    {tool.details.file_path.split('/').slice(-2).join('/')}
                  </span>
                )}

                {/* Duration */}
                {isCompleted && tool.duration_ms !== undefined && (
                  <span className="text-xs text-ash flex items-center gap-1 tabular-nums">
                    <Clock size={10} />
                    {formatDuration(tool.duration_ms)}
                  </span>
                )}

                {/* Running indicator text */}
                {isRunning && (
                  <span
                    className="text-xs font-medium motion-safe:animate-pulse"
                    style={{ color: primaryColor }}
                  >
                    Running...
                  </span>
                )}

                {/* Error indicator */}
                {isError && (
                  <span className="text-xs text-leaf font-medium">
                    Failed
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
