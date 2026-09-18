'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { BrainCircuit, CheckCircle2, CircleAlert, ExternalLink } from 'lucide-react'
import { integrationsApi } from '@/lib/api/integrations'
import { usePermissions } from '@/hooks/usePermissions'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

const labelClassName = 'mb-2 block text-sm font-semibold text-[#2b241d]'
const helperClassName = 'mt-2 text-xs leading-5 text-[#75695f]'
const inputClassName =
  'w-full rounded-[1.15rem] border border-[#ddd1bf] bg-white px-4 py-3 text-sm text-[#171717] placeholder:text-[#9a8f84] transition focus:border-[#2d8b69] focus:outline-none focus:ring-4 focus:ring-[#7de5c1]/20'
const secondaryButtonClassName =
  'inline-flex items-center justify-center gap-2 rounded-[1rem] border border-[#d8cab8] bg-white px-4 py-3 text-sm font-semibold text-[#3c342d] transition hover:border-[#c6b39c] hover:bg-[#f7f1e7] disabled:cursor-not-allowed disabled:opacity-50'
const primaryButtonClassName =
  'inline-flex items-center justify-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-50'

export default function CreateAIEvaluationIntegrationPage() {
  const router = useRouter()
  const { hasPermission } = usePermissions()

  const isPlatformOwner = hasPermission('platform', 'create')

  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('https://api.typesafe.ai/v1')
  const [model, setModel] = useState('jev-latest')
  const [isDefault, setIsDefault] = useState(true)
  const [isPlatformConfig, setIsPlatformConfig] = useState(false)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!apiKey.trim()) {
      setError('API key is required')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await integrationsApi.createConfig({
        integration_type: 'ai_evaluation',
        provider: 'typesafe',
        config_data: {
          api_key: apiKey.trim(),
          base_url: baseUrl.trim() || 'https://api.typesafe.ai/v1',
          model: model.trim() || 'jev-latest',
        },
        is_active: true,
        is_default: isDefault,
        is_platform_config: isPlatformOwner ? isPlatformConfig : false,
      })
      setSuccess(true)
      setTimeout(() => router.push('/settings/integrations'), 1200)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to save configuration')
    } finally {
      setLoading(false)
    }
  }

  return (
    <DashboardPageShell
      title="Add TypeSafe AI"
      description="Connect TypeSafe AI to enable structured evaluation tools for your agents."
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
        {/* Header */}
        <div className="mb-8 flex items-start gap-4 border-b border-[#ede5d8] pb-6">
          <div className="rounded-[1.15rem] bg-[#f3ecde] p-3">
            <BrainCircuit size={24} className="text-[#171717]" />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-[#171717]">TypeSafe AI (Jev)</h2>
            <p className="mt-1 text-sm text-[#75695f]">
              The first System One model for structured decisions. Evaluates choices, scores, and
              yes/no questions in parallel — powering recruiting, lead scoring, content moderation,
              and support triage in your agents.
            </p>
            <a
              href="https://console.typesafe.ai/settings/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs text-[#2d8b69] hover:underline"
            >
              Get your API key from TypeSafe Console
              <ExternalLink size={11} />
            </a>
          </div>
        </div>

        {/* Success state */}
        {success && (
          <div className="mb-6 flex items-center gap-3 rounded-[1.15rem] border border-green-200 bg-green-50 px-4 py-3">
            <CheckCircle2 size={18} className="text-green-600" />
            <span className="text-sm font-medium text-green-700">Configuration saved. Redirecting…</span>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="mb-6 flex items-center gap-3 rounded-[1.15rem] border border-red-200 bg-red-50 px-4 py-3">
            <CircleAlert size={18} className="text-red-500" />
            <span className="text-sm text-red-700">{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* API Key */}
          <div>
            <label className={labelClassName}>
              API Key <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              className={inputClassName}
              placeholder="ts-..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              required
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

          {/* Base URL (advanced) */}
          <div>
            <label className={labelClassName}>Base URL</label>
            <input
              type="url"
              className={inputClassName}
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.typesafe.ai/v1"
            />
            <p className={helperClassName}>
              Only change this if you are using a self-hosted or proxy endpoint.
            </p>
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
            <p className={helperClassName}>
              <code>jev-latest</code> always uses the most recent version of the Jev model.
            </p>
          </div>

          {/* Options */}
          <div className="space-y-3 rounded-[1.15rem] border border-[#ede5d8] bg-[#faf7f2] p-4">
            <label className="flex cursor-pointer items-center gap-3">
              <input
                type="checkbox"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-[#cdbda7] accent-[#171717]"
              />
              <span className="text-sm text-[#2b241d]">
                Set as default AI evaluation provider
              </span>
            </label>

            {isPlatformOwner && (
              <label className="flex cursor-pointer items-center gap-3">
                <input
                  type="checkbox"
                  checked={isPlatformConfig}
                  onChange={(e) => setIsPlatformConfig(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-[#cdbda7] accent-[#171717]"
                />
                <span className="text-sm text-[#2b241d]">
                  Platform-level config (available as fallback for all tenants)
                </span>
              </label>
            )}
          </div>

          {/* Capabilities summary */}
          <div className="rounded-[1.15rem] border border-[#ddd1bf] bg-[#f9f6f0] p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-[#75695f]">
              What this unlocks for your agents
            </p>
            <ul className="space-y-1.5 text-sm text-[#3c342d]">
              {[
                'Resume & application evaluation against job criteria',
                'Lead scoring by ICP fit, intent, and urgency',
                'Support ticket triage, routing, and escalation detection',
                'Content moderation with policy-specific criteria',
                'Custom structured evaluation with any questions you define',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-[#2d8b69]" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 border-t border-[#ede5d8] pt-6">
            <button
              type="button"
              onClick={() => router.push('/settings/integrations')}
              className={secondaryButtonClassName}
            >
              Cancel
            </button>
            <button type="submit" disabled={loading || !apiKey.trim()} className={primaryButtonClassName}>
              {loading ? 'Saving…' : 'Save Configuration'}
            </button>
          </div>
        </form>
      </DashboardPagePanel>
    </DashboardPageShell>
  )
}
