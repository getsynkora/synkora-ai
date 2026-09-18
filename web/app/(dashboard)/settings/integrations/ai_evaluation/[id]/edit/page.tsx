'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { BrainCircuit, CheckCircle2, CircleAlert, ExternalLink, Trash2 } from 'lucide-react'
import { integrationsApi } from '@/lib/api/integrations'
import { usePermissions } from '@/hooks/usePermissions'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

const labelClassName = 'mb-2 block text-sm font-semibold text-[#2b241d]'
const helperClassName = 'mt-2 text-xs leading-5 text-[#75695f]'
const inputClassName =
  'w-full rounded-[1.15rem] border border-[#ddd1bf] bg-white px-4 py-3 text-sm text-[#171717] placeholder:text-[#9a8f84] transition focus:border-[#2d8b69] focus:outline-none focus:ring-4 focus:ring-[#7de5c1]/20'
const secondaryButtonClassName =
  'inline-flex items-center justify-center gap-2 rounded-[1rem] border border-[#d8cab8] bg-white px-4 py-3 text-sm font-semibold text-[#3c342d] transition hover:border-[#c6b39c] hover:bg-[#f7f1e7] disabled:cursor-not-allowed disabled:opacity-50'
const primaryButtonClassName =
  'inline-flex items-center justify-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-50'
const dangerButtonClassName =
  'inline-flex items-center justify-center gap-2 rounded-[1rem] border border-red-200 bg-white px-4 py-3 text-sm font-semibold text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50'

export default function EditAIEvaluationIntegrationPage() {
  const router = useRouter()
  const params = useParams()
  const { hasPermission } = usePermissions()

  const isPlatformOwner = hasPermission('platform', 'update')
  const canDelete = hasPermission('integration_configs', 'delete')

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('https://api.typesafe.ai/v1')
  const [model, setModel] = useState('jev-latest')
  const [isDefault, setIsDefault] = useState(true)
  const [isPlatformConfig, setIsPlatformConfig] = useState(false)
  const [isActive, setIsActive] = useState(true)

  useEffect(() => {
    loadConfig()
  }, [params.id])

  const loadConfig = async () => {
    try {
      setLoading(true)
      const data = await integrationsApi.getConfig(params.id as string)
      const cd = (data.config_data || {}) as Record<string, any>
      setApiKey(cd.api_key || '')
      setBaseUrl(cd.base_url || 'https://api.typesafe.ai/v1')
      setModel(cd.model || 'jev-latest')
      setIsDefault(data.is_default ?? true)
      setIsPlatformConfig(data.is_platform_config ?? false)
      setIsActive(data.is_active ?? true)
    } catch (err: any) {
      setError(err?.message || 'Failed to load configuration')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!apiKey.trim()) {
      setError('API key is required')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await integrationsApi.updateConfig(params.id as string, {
        config_data: {
          api_key: apiKey.trim(),
          base_url: baseUrl.trim() || 'https://api.typesafe.ai/v1',
          model: model.trim() || 'jev-latest',
        },
        is_active: isActive,
        is_default: isDefault,
        is_platform_config: isPlatformOwner ? isPlatformConfig : undefined,
      })
      setSuccess(true)
      setTimeout(() => router.push('/settings/integrations'), 1200)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to save configuration')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Delete this TypeSafe AI configuration? Agents using it will lose access.')) return
    try {
      await integrationsApi.deleteConfig(params.id as string)
      router.push('/settings/integrations')
    } catch (err: any) {
      setError(err?.message || 'Failed to delete configuration')
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <DashboardPageShell
      title="Edit TypeSafe AI"
      description="Update your TypeSafe AI integration credentials."
      icon={BrainCircuit}
      badge="AI Evaluation"
      backHref="/settings/integrations"
      backLabel="Back to Integrations"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Settings', href: '/settings/profile' },
        { label: 'Integrations', href: '/settings/integrations' },
        { label: 'TypeSafe AI' },
      ]}
    >
      <DashboardPagePanel className="p-6 md:p-7">
        <div className="mb-8 flex items-start gap-4 border-b border-[#ede5d8] pb-6">
          <div className="rounded-[1.15rem] bg-[#f3ecde] p-3">
            <BrainCircuit size={24} className="text-[#171717]" />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-[#171717]">TypeSafe AI (Jev)</h2>
            <p className="mt-1 text-sm text-[#75695f]">
              Update your API key or model preference. Leave the API key field blank to keep the existing key.
            </p>
            <a
              href="https://console.typesafe.ai/settings/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs text-[#2d8b69] hover:underline"
            >
              TypeSafe Console
              <ExternalLink size={11} />
            </a>
          </div>
        </div>

        {success && (
          <div className="mb-6 flex items-center gap-3 rounded-[1.15rem] border border-green-200 bg-green-50 px-4 py-3">
            <CheckCircle2 size={18} className="text-green-600" />
            <span className="text-sm font-medium text-green-700">Configuration saved. Redirecting…</span>
          </div>
        )}

        {error && (
          <div className="mb-6 flex items-center gap-3 rounded-[1.15rem] border border-red-200 bg-red-50 px-4 py-3">
            <CircleAlert size={18} className="text-red-500" />
            <span className="text-sm text-red-700">{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* API Key */}
          <div>
            <label className={labelClassName}>API Key</label>
            <input
              type="password"
              className={inputClassName}
              placeholder="Leave blank to keep existing key"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              autoComplete="off"
            />
            <p className={helperClassName}>
              Found at{' '}
              <a
                href="https://console.typesafe.ai/settings/keys"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#2d8b69] hover:underline"
              >
                console.typesafe.ai/settings/keys
              </a>
            </p>
          </div>

          {/* Base URL */}
          <div>
            <label className={labelClassName}>Base URL</label>
            <input
              type="url"
              className={inputClassName}
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.typesafe.ai/v1"
            />
            <p className={helperClassName}>Only change for self-hosted or proxy endpoints.</p>
          </div>

          {/* Model */}
          <div>
            <label className={labelClassName}>Default Model</label>
            <select
              className={inputClassName}
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              <option value="jev-latest">jev-latest (recommended)</option>
              <option value="jev">jev (stable)</option>
            </select>
          </div>

          {/* Options */}
          <div className="space-y-3 rounded-[1.15rem] border border-[#ede5d8] bg-[#faf7f2] p-4">
            <label className="flex cursor-pointer items-center gap-3">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-[#cdbda7] accent-[#171717]"
              />
              <span className="text-sm text-[#2b241d]">Active</span>
            </label>
            <label className="flex cursor-pointer items-center gap-3">
              <input
                type="checkbox"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-[#cdbda7] accent-[#171717]"
              />
              <span className="text-sm text-[#2b241d]">Set as default AI evaluation provider</span>
            </label>
            {isPlatformOwner && (
              <label className="flex cursor-pointer items-center gap-3">
                <input
                  type="checkbox"
                  checked={isPlatformConfig}
                  onChange={(e) => setIsPlatformConfig(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-[#cdbda7] accent-[#171717]"
                />
                <span className="text-sm text-[#2b241d]">Platform-level config (fallback for all tenants)</span>
              </label>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between border-t border-[#ede5d8] pt-6">
            <div>
              {canDelete && (
                <button
                  type="button"
                  onClick={handleDelete}
                  className={dangerButtonClassName}
                >
                  <Trash2 size={15} />
                  Delete
                </button>
              )}
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => router.push('/settings/integrations')}
                className={secondaryButtonClassName}
              >
                Cancel
              </button>
              <button type="submit" disabled={saving} className={primaryButtonClassName}>
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          </div>
        </form>
      </DashboardPagePanel>
    </DashboardPageShell>
  )
}
