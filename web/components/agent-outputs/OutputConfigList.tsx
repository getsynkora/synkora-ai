'use client'

import { useState } from 'react'
import { 
  Send, 
  Mail,
  MessageSquare,
  Webhook,
  Edit,
  Trash2,
  MoreVertical,
  Loader2,
  AlertCircle,
  Plus,
  CheckCircle,
  XCircle
} from 'lucide-react'
import { useAgentOutputs } from '@/hooks/useAgentOutputs'
import toast from 'react-hot-toast'
import type { OutputConfig } from '@/types/agent-outputs'

export interface OutputConfigListProps {
  agentId: string
  refreshKey?: number
  onCreateClick?: () => void
  onEditClick?: (config: OutputConfig) => void
}

const providerIcons: Record<string, any> = {
  slack: MessageSquare,
  email: Mail,
  webhook: Webhook
}

const providerColors: Record<string, string> = {
  slack: 'bg-sand-deep text-ink-soft',
  email: 'bg-sky-wash text-azure',
  webhook: 'bg-sand-deep text-ink-soft'
}

export function OutputConfigList({ agentId, refreshKey = 0, onCreateClick, onEditClick }: OutputConfigListProps) {
  const { outputs: configs, loading, error, deleteOutput } = useAgentOutputs(agentId)
  const [actionMenuOpen, setActionMenuOpen] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  const handleDelete = async (configId: string) => {
    if (!confirm('Are you sure you want to delete this output configuration? This action cannot be undone.')) {
      return
    }

    setDeleting(configId)
    setActionMenuOpen(null)

    try {
      await deleteOutput(configId)
      toast.success('Output configuration deleted successfully')
    } catch (error: any) {
      toast.error(error.message || 'Failed to delete output configuration')
    } finally {
      setDeleting(null)
    }
  }

  if (loading && configs.length === 0) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-leaf motion-safe:animate-spin mx-auto mb-3" />
          <p className="text-ink-soft text-sm">Loading output configurations…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-blush-wash border border-blush rounded-lg p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-danger flex-shrink-0" />
            <div>
              <p className="font-medium text-wine">Error Loading Output Configurations</p>
              <p className="text-sm text-danger mt-1">{error}</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (configs.length === 0) {
    return (
      <div className="p-16 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-sand-deep rounded-full mb-4">
          <Send className="w-8 h-8 text-leaf" />
        </div>
        <h3 className="text-lg font-semibold text-ink mb-2">No Output Configurations Yet</h3>
        <p className="text-ink-soft mb-6 max-w-md mx-auto text-sm">
          Create your first output configuration to route agent responses to Slack, Email, or external webhooks.
        </p>
        <button
          onClick={onCreateClick}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-ink hover:bg-ink/85 rounded-lg transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm hover:shadow-md"
        >
          <Plus className="w-4 h-4" />
          Create Output Configuration
        </button>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="grid gap-4">
        {configs.map((config) => {
          const Icon = providerIcons[config.provider] || Send
          const colorClass = providerColors[config.provider] || 'bg-sand text-ink-soft'

          return (
            <div
              key={config.id}
              className="border border-line rounded-lg p-5 hover:border-blush hover:shadow-sm transition-[color,background-color,border-color,box-shadow,opacity,transform] bg-white"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4 flex-1">
                  <div className={`p-2.5 rounded-lg ${colorClass}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-semibold text-ink">{config.name}</h3>
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                        config.is_enabled
                          ? 'bg-leaf-wash text-forest'
                          : 'bg-sand text-ink-soft'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          config.is_enabled ? 'bg-leaf' : 'bg-ash'
                        }`} />
                        {config.is_enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    
                    {config.description && (
                      <p className="text-sm text-ink-soft mb-3">{config.description}</p>
                    )}

                    <div className="flex items-center gap-4 text-sm text-ink-soft mb-3">
                      <span className="capitalize">{config.provider}</span>
                      {config.provider === 'slack' && config.config?.channel && (
                        <>
                          <span className="text-taupe">•</span>
                          <span className="font-mono text-xs">{config.config.channel}</span>
                        </>
                      )}
                      {config.provider === 'email' && config.config?.to && (
                        <>
                          <span className="text-taupe">•</span>
                          <span className="text-xs">{config.config.to.join(', ')}</span>
                        </>
                      )}
                      {config.provider === 'webhook' && config.config?.url && (
                        <>
                          <span className="text-taupe">•</span>
                          <span className="font-mono text-xs truncate max-w-xs">{config.config.url}</span>
                        </>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-xs text-ink-mute">
                      {config.send_on_webhook_trigger && (
                        <div className="flex items-center gap-1.5">
                          <CheckCircle className="w-3.5 h-3.5 text-leaf" />
                          <span>Webhook triggers</span>
                        </div>
                      )}
                      {config.send_on_chat_completion && (
                        <div className="flex items-center gap-1.5">
                          <CheckCircle className="w-3.5 h-3.5 text-leaf" />
                          <span>Chat completions</span>
                        </div>
                      )}
                      {config.retry_on_failure && (
                        <div className="flex items-center gap-1.5">
                          <span className="text-ash">•</span>
                          <span>Retries: {config.max_retries}</span>
                        </div>
                      )}
                    </div>

                    {config.output_template && (
                      <div className="mt-3 p-2 bg-cream rounded border border-line">
                        <p className="text-xs text-ink-mute mb-1">Custom Template:</p>
                        <code className="text-xs text-ink-soft font-mono block truncate">
                          {config.output_template}
                        </code>
                      </div>
                    )}
                  </div>
                </div>

                <div className="relative ml-4">
                  <button
                    onClick={() => setActionMenuOpen(actionMenuOpen === config.id ? null : config.id)}
                    disabled={deleting === config.id}
                    className="p-2 text-ash hover:text-ink-soft hover:bg-sand rounded-lg transition-colors disabled:opacity-50"
                  >
                    {deleting === config.id ? (
                      <Loader2 className="w-5 h-5 motion-safe:animate-spin" />
                    ) : (
                      <MoreVertical className="w-5 h-5" />
                    )}
                  </button>

                  {actionMenuOpen === config.id && (
                    <>
                      <div
                        className="fixed inset-0 z-10"
                        onClick={() => setActionMenuOpen(null)}
                      />
                      <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-line py-1 z-20">
                        <button
                          onClick={() => {
                            setActionMenuOpen(null)
                            onEditClick?.(config)
                          }}
                          className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-ink-soft hover:bg-cream transition-colors"
                        >
                          <Edit className="w-4 h-4" />
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(config.id)}
                          className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-danger hover:bg-blush-wash transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                          Delete
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
