'use client'

import { Plus, Edit2, Trash2, Star, StarOff, Power, PowerOff } from 'lucide-react'
import { AgentLLMConfig } from '@/types/agent-llm-config'
import { getModelLabel } from '@/types/agent-llm-config'

interface LLMConfigListProps {
  configs: AgentLLMConfig[]
  onAdd: () => void
  onEdit: (config: AgentLLMConfig) => void
  onDelete: (configId: string) => void
  onSetDefault: (configId: string) => void
  onToggleEnabled: (configId: string, enabled: boolean) => void
  isLoading?: boolean
}

export default function LLMConfigList({
  configs,
  onAdd,
  onEdit,
  onDelete,
  onSetDefault,
  onToggleEnabled,
  isLoading = false,
}: LLMConfigListProps) {

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="motion-safe:animate-spin rounded-full h-8 w-8 border-b-2 border-danger"></div>
      </div>
    )
  }

  if (configs.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-sand-deep mb-4">
          <Plus className="w-8 h-8 text-hotpink" />
        </div>
        <h3 className="text-lg font-medium text-ink mb-2">No AI Model Configurations</h3>
        <p className="text-ink-mute mb-6">
          Add your first AI model configuration to get started
        </p>
        <button
          onClick={onAdd}
          className="inline-flex items-center gap-2 px-4 py-2 bg-ink text-white rounded-lg hover:from-danger hover:to-danger transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Add Configuration
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-ink">
          AI Model Configurations ({configs.length})
        </h3>
        <button
          onClick={onAdd}
          className="inline-flex items-center gap-2 px-4 py-2 bg-ink text-white rounded-lg hover:from-danger hover:to-danger transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Add Configuration
        </button>
      </div>

      <div className="space-y-3">
        {configs.map((config) => (
          <div
            key={config.id}
            className="bg-white border border-line rounded-lg p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start gap-4">
              {/* Config Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="text-base font-medium text-ink truncate">
                    {config.name}
                  </h4>
                  {config.is_default && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blush-wash text-leaf text-xs font-medium rounded">
                      <Star className="w-3 h-3 fill-current" />
                      Default
                    </span>
                  )}
                  {!config.enabled && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-sand text-ink-soft text-xs font-medium rounded">
                      Disabled
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div>
                    <span className="text-ink-mute">Provider:</span>
                    <span className="ml-2 text-ink font-medium capitalize">
                      {config.provider}
                    </span>
                  </div>
                  <div>
                    <span className="text-ink-mute">Model:</span>
                    <span className="ml-2 text-ink font-medium">
                      {getModelLabel(config.provider, config.model_name)}
                    </span>
                  </div>
                  {config.temperature !== undefined && (
                    <div>
                      <span className="text-ink-mute">Temperature:</span>
                      <span className="ml-2 text-ink font-medium">
                        {config.temperature}
                      </span>
                    </div>
                  )}
                  {config.max_tokens !== undefined && (
                    <div>
                      <span className="text-ink-mute">Max Tokens:</span>
                      <span className="ml-2 text-ink font-medium">
                        {config.max_tokens}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1">
                {!config.is_default && (
                  <button
                    onClick={() => onSetDefault(config.id)}
                    className="p-2 text-ash hover:text-leaf hover:bg-blush-wash rounded-lg transition-colors"
                    title="Set as default"
                  >
                    <StarOff className="w-4 h-4" />
                  </button>
                )}

                <button
                  onClick={() => onToggleEnabled(config.id, !config.enabled)}
                  className={`p-2 rounded-lg transition-colors ${
                    config.enabled
                      ? 'text-leaf hover:bg-leaf-wash'
                      : 'text-ash hover:bg-cream'
                  }`}
                  title={config.enabled ? 'Disable' : 'Enable'}
                >
                  {config.enabled ? (
                    <Power className="w-4 h-4" />
                  ) : (
                    <PowerOff className="w-4 h-4" />
                  )}
                </button>

                <button
                  onClick={() => onEdit(config)}
                  className="p-2 text-ash hover:text-leaf hover:bg-blush-wash rounded-lg transition-colors"
                  title="Edit"
                >
                  <Edit2 className="w-4 h-4" />
                </button>

                <button
                  onClick={() => onDelete(config.id)}
                  className={`p-2 rounded-lg transition-colors ${
                    config.is_default
                      ? 'text-line cursor-not-allowed'
                      : 'text-ash hover:text-danger hover:bg-blush-wash'
                  }`}
                  title={config.is_default ? 'Cannot delete the default configuration' : 'Delete'}
                  disabled={config.is_default}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
