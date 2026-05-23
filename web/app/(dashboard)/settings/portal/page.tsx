'use client'

import { useState, useEffect, useCallback } from 'react'
import { Globe, ExternalLink, Save, ToggleLeft, ToggleRight, Link2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { getPortalSettings, updatePortalSettings, type TenantPortal } from '@/lib/api/portal'
import { getAgents } from '@/lib/api/agents'
import { usePermissions } from '@/hooks/usePermissions'

export default function PortalSettingsPage() {
  const router = useRouter()
  const { hasPermission } = usePermissions()
  const [permChecked, setPermChecked] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setPermChecked(true), 500)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {
    if (permChecked && !hasPermission('integration_configs', 'read')) {
      router.replace('/agents')
    }
  }, [permChecked, hasPermission, router])

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [portal, setPortal] = useState<TenantPortal | null>(null)
  const [agents, setAgents] = useState<any[]>([])

  const [enabled, setEnabled] = useState(false)
  const [customDomain, setCustomDomain] = useState('')
  const [featuredSlugs, setFeaturedSlugs] = useState<string[]>([])

  const loadData = useCallback(async () => {
    try {
      const [portalData, agentsData] = await Promise.all([
        getPortalSettings(),
        getAgents(1, 100),
      ])
      setPortal(portalData)
      setEnabled(portalData?.portal_enabled ?? false)
      setCustomDomain(portalData?.portal_domain ?? '')
      setFeaturedSlugs(portalData?.featured_agent_slugs ?? [])
      setAgents(Array.isArray(agentsData) ? agentsData : agentsData?.agents_list ?? agentsData?.agents ?? [])
    } catch {
      toast.error('Failed to load portal settings')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await updatePortalSettings({
        portal_enabled: enabled,
        portal_domain: customDomain.trim() || null,
        featured_agent_slugs: featuredSlugs,
      })
      setPortal(updated)
      setCustomDomain(updated?.portal_domain ?? '')
      setFeaturedSlugs(updated?.featured_agent_slugs ?? [])
      toast.success('Portal settings saved')
    } catch {
      toast.error('Failed to save portal settings')
    } finally {
      setSaving(false)
    }
  }

  const toggleFeaturedAgent = (slug: string) => {
    setFeaturedSlugs((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    )
  }

  if (loading) {
    return (
      <div className="dashboard-settings-page flex min-h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-gray-900" />
      </div>
    )
  }

  return (
    <div className="dashboard-settings-page min-h-screen">
      <div className="max-w-3xl mx-auto px-4 md:px-6 py-4 md:py-6">

        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">Portal Settings</h1>
            <p className="mt-1 text-sm text-gray-500">
              Configure your white-label portal — a public site for your customers.
            </p>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition-all text-sm font-medium shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>

        <div className="space-y-5">

          {/* Enable / Domain */}
          <div className="bg-white rounded-lg border border-gray-200 p-5 space-y-5">

            {/* Enable toggle */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Enable Portal</h3>
                <p className="mt-0.5 text-xs text-gray-500">
                  Make your portal publicly accessible so visitors can browse and chat with your agents.
                </p>
              </div>
              <button
                onClick={() => setEnabled((v) => !v)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                  enabled
                    ? 'bg-green-100 text-green-700 hover:bg-green-200'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {enabled ? (
                  <><ToggleRight className="w-4 h-4" /> Enabled</>
                ) : (
                  <><ToggleLeft className="w-4 h-4" /> Disabled</>
                )}
              </button>
            </div>

            {/* Subdomain read-only */}
            {portal?.subdomain && (
              <div className="border-t border-gray-100 pt-4">
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Tenant Slug <span className="text-gray-400 font-normal">(read-only — use as NEXT_PUBLIC_TENANT_SLUG)</span>
                </label>
                <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 font-mono">
                  <Globe className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                  {portal.subdomain}
                </div>
              </div>
            )}

            {/* Custom domain */}
            <div className={portal?.subdomain ? '' : 'border-t border-gray-100 pt-4'}>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Custom Domain <span className="text-gray-400 font-normal">(optional — e.g. ai.yourcompany.com)</span>
              </label>
              <div className="relative">
                <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                <input
                  type="text"
                  value={customDomain}
                  onChange={(e) => setCustomDomain(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-900 focus:border-gray-900 transition-colors"
                  placeholder="ai.yourcompany.com"
                />
              </div>
            </div>
          </div>

          {/* Featured Agents */}
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-1">Featured Agents</h3>
            <p className="text-xs text-gray-500 mb-4">
              Select agents to highlight on your portal home page.
            </p>

            {agents.length === 0 ? (
              <p className="text-xs text-gray-400 italic">No agents found.</p>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {agents.map((agent: any) => {
                  const slug = agent.slug || agent.agent_name
                  const checked = featuredSlugs.includes(slug)
                  return (
                    <label
                      key={slug}
                      className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                        checked ? 'border-gray-900 bg-gray-50' : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleFeaturedAgent(slug)}
                        className="accent-gray-900"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{agent.agent_name}</p>
                        {agent.description && (
                          <p className="text-xs text-gray-500 truncate">{agent.description}</p>
                        )}
                      </div>
                      {agent.portal_visibility && agent.portal_visibility !== 'hidden' && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium flex-shrink-0">
                          {agent.portal_visibility === 'public' ? 'Public' : 'Members Only'}
                        </span>
                      )}
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          {/* Deploy instructions */}
          <div className="bg-gray-50 rounded-lg border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-1.5">Deploy Your Portal</h3>
            <p className="text-xs text-gray-600 mb-3">
              Fork the <strong>synkora-portal</strong> repository, set these two environment variables, and
              deploy anywhere — Vercel, self-hosted, or any static host.
            </p>
            <div className="font-mono text-xs bg-white border border-gray-200 rounded p-3 space-y-1 text-gray-800">
              <p>NEXT_PUBLIC_SYNKORA_API_URL=https://your-api.com</p>
              <p>NEXT_PUBLIC_TENANT_SLUG={portal?.subdomain ?? 'your-slug'}</p>
            </div>
            <a
              href="https://github.com/your-org/synkora-portal"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-xs text-gray-700 hover:underline font-medium"
            >
              <ExternalLink className="w-3 h-3" />
              Fork synkora-portal on GitHub
            </a>
          </div>

        </div>
      </div>
    </div>
  )
}
