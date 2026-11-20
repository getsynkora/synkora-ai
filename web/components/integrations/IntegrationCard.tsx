'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Settings, Trash2, TestTube, Lock } from 'lucide-react'
import type { IntegrationConfig } from '@/types/integrations'

interface IntegrationCardProps {
  config: IntegrationConfig
  onTest: (id: string) => Promise<void>
  onActivate?: (id: string) => Promise<void>
  onDelete?: (id: string) => Promise<void>
  isPlatformOwner?: boolean
}

export function IntegrationCard({ config, onTest, onActivate, onDelete, isPlatformOwner = false }: IntegrationCardProps) {
  const router = useRouter()
  const [testing, setTesting] = useState(false)
  const [activating, setActivating] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleTest = async () => {
    setTesting(true)
    try {
      await onTest(config.id)
    } finally {
      setTesting(false)
    }
  }

  const handleActivate = async () => {
    if (!onActivate) return
    setActivating(true)
    try {
      await onActivate(config.id)
    } finally {
      setActivating(false)
    }
  }

  const handleDelete = async () => {
    if (!onDelete) return
    if (confirm('Are you sure you want to delete this integration?')) {
      setDeleting(true)
      try {
        await onDelete(config.id)
      } finally {
        setDeleting(false)
      }
    }
  }

  const handleEdit = () => {
    router.push(`/settings/integrations/${config.integration_type}/${config.id}/edit`)
  }

  return (
    <div className="p-6 hover:bg-cream transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-lg font-semibold text-ink">{config.provider.toUpperCase()}</h3>
            <span
              className={`px-3 py-1 rounded-full text-xs font-medium ${
                config.is_active
                  ? 'bg-leaf-wash text-forest'
                  : 'bg-sand text-ink'
              }`}
            >
              {config.is_active ? 'Active' : 'Inactive'}
            </span>
            {config.is_default && (
              <span className="px-3 py-1 rounded-full text-xs font-medium bg-sky-wash text-azure">
                Default
              </span>
            )}
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-blush-wash text-wine">
              {config.integration_type}
            </span>
          </div>
          <p className="text-ink-soft mb-2">
            {config.config_data?.metadata?.description || `${config.integration_type} integration`}
          </p>
          <div className="flex items-center gap-4 text-sm text-ink-mute">
            {config.config_data?.settings?.from_email && (
              <>
                <span className="font-mono">{config.config_data.settings.from_email}</span>
                <span>•</span>
              </>
            )}
            <span>Updated {new Date(config.updated_at).toLocaleDateString()}</span>
          </div>
          {config.config_data?.metadata?.tags && config.config_data.metadata.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {config.config_data.metadata.tags.map((tag: string) => (
                <span key={tag} className="px-2 py-1 bg-sand text-ink-soft rounded text-xs">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 ml-4">
          <button
            onClick={handleTest}
            disabled={testing || activating || deleting}
            className="p-2 text-leaf hover:bg-leaf-wash rounded-lg transition-colors disabled:opacity-50"
            title="Test Connection"
          >
            {testing ? (
              <div className="motion-safe:animate-spin rounded-full h-5 w-5 border-b-2 border-leaf"></div>
            ) : (
              <TestTube size={20} />
            )}
          </button>

          {!config.is_active && onActivate && (
            <button
              onClick={handleActivate}
              disabled={testing || activating || deleting}
              className="px-3 py-1 text-sm bg-leaf text-white rounded-lg hover:bg-forest transition-colors disabled:opacity-50"
            >
              {activating ? 'Activating…' : 'Activate'}
            </button>
          )}

          <button
            onClick={handleEdit}
            disabled={testing || activating || deleting}
            className="p-2 text-leaf hover:bg-leaf-wash rounded-lg transition-colors disabled:opacity-50"
            title="Edit"
          >
            <Settings size={20} />
          </button>

          {onDelete && (
            <button
              onClick={handleDelete}
              disabled={
                testing || 
                activating || 
                deleting || 
                config.is_active ||
                (config.is_platform_config && !isPlatformOwner)
              }
              className="p-2 text-leaf hover:bg-blush-wash rounded-lg transition-colors disabled:opacity-50"
              title={
                config.is_active 
                  ? "Cannot delete active integration" 
                  : config.is_platform_config && !isPlatformOwner
                  ? "Only Platform Owners can delete platform configurations"
                  : "Delete"
              }
            >
              {deleting ? (
                <div className="motion-safe:animate-spin rounded-full h-5 w-5 border-b-2 border-danger"></div>
              ) : config.is_platform_config && !isPlatformOwner ? (
                <Lock size={20} />
              ) : (
                <Trash2 size={20} />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
