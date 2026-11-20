'use client'

import { useState } from 'react'
import { extractErrorMessage } from '@/lib/api/error'
import { Trash2, AlertTriangle } from 'lucide-react'

interface MemoryMessage {
  id: string
  role: string
  content: string
  created_at: string
}

interface Props {
  agentName: string
  messages: MemoryMessage[]
  onCleared: () => void
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function isRememberMessage(content: string): boolean {
  return content.startsWith('[AUTONOMOUS MEMORY]')
}

function parseMemoryKey(content: string): string {
  // Extract the JSON key from "[AUTONOMOUS MEMORY] {"key": "value", ...}"
  try {
    const jsonStr = content.replace('[AUTONOMOUS MEMORY]', '').trim()
    const data = JSON.parse(jsonStr)
    return Object.keys(data).join(', ')
  } catch {
    return content.slice(0, 60)
  }
}

export function AutonomousMemoryViewer({ agentName, messages, onCleared }: Props) {
  const [confirming, setConfirming] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const memoryMessages = messages.filter(m => m.role === 'SYSTEM' && isRememberMessage(m.content))
  const conversationMessages = messages.filter(m => !isRememberMessage(m.content) || m.role !== 'SYSTEM')

  async function handleClear() {
    setError(null)
    setClearing(true)
    try {
      const { apiClient } = await import('@/lib/api/client')
      await apiClient.request(
        'DELETE',
        `/api/v1/agents/${encodeURIComponent(agentName)}/autonomous/memory`
      )
      setConfirming(false)
      onCleared()
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Clear failed'))
    } finally {
      setClearing(false)
    }
  }

  if (messages.length === 0) {
    return (
      <div className="py-10 text-center text-sm text-ink-mute">
        No memory yet. Memory is written after the first autonomous run.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-md bg-blush-wash border border-blush px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {/* Persistent key-value memory */}
      {memoryMessages.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-ink-soft mb-2">Persistent facts</h3>
          <div className="divide-y divide-sand border border-line rounded-md overflow-hidden">
            {memoryMessages.map(m => (
              <div key={m.id} className="flex items-center gap-3 px-4 py-2.5 bg-white">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-ink font-mono truncate">
                    {parseMemoryKey(m.content)}
                  </p>
                  <p className="text-xs text-ink-mute mt-0.5">{formatDate(m.created_at)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent conversation messages */}
      {conversationMessages.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-ink-soft mb-2">Recent conversation</h3>
          <div className="space-y-2">
            {conversationMessages.slice(-10).map(m => (
              <div
                key={m.id}
                className={`rounded-md px-3 py-2 text-sm ${
                  m.role === 'USER'
                    ? 'bg-sand text-ink'
                    : m.role === 'ASSISTANT'
                    ? 'bg-blush-wash text-ink'
                    : 'bg-sand-deep text-ink-soft text-xs font-mono'
                }`}
              >
                <span className="text-xs font-medium text-ink-mute mr-2">{m.role}</span>
                {m.content.slice(0, 300)}
                {m.content.length > 300 && '…'}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Clear all button */}
      <div className="pt-2 border-t border-line">
        {confirming ? (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm text-gold">
              <AlertTriangle className="w-4 h-4" />
              This will delete all memory. Are you sure?
            </div>
            <button
              onClick={handleClear}
              disabled={clearing}
              className="px-3 py-1.5 rounded-md text-sm font-medium text-white bg-ink hover:bg-danger disabled:opacity-50"
            >
              {clearing ? 'Clearing…' : 'Yes, clear all'}
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="px-3 py-1.5 rounded-md text-sm font-medium text-ink-soft border border-taupe hover:bg-cream"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            className="inline-flex items-center gap-2 text-sm text-leaf hover:text-leaf"
          >
            <Trash2 className="w-4 h-4" />
            Clear all memory
          </button>
        )}
      </div>
    </div>
  )
}
