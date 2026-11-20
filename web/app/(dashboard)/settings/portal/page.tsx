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
        <div className="motion-safe:animate-spin rounded-full h-10 w-10 border-b-2 border-ink" />
      </div>
    )
  }

  return (
    <div className="dashboard-settings-page min-h-screen">
      <div className="max-w-3xl mx-auto px-4 md:px-6 py-4 md:py-6">

        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-ink tracking-tight">Portal Settings</h1>
            <p className="mt-1 text-sm text-ink-mute">
              Configure your white-label portal, a public site for your customers.
            </p>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-ink text-white rounded-lg hover:bg-ink-soft transition-[color,background-color,border-color,box-shadow,opacity,transform] text-sm font-medium shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>

        <div className="space-y-5">

          {/* Enable / Domain */}
          <div className="bg-white rounded-lg border border-line p-5 space-y-5">

            {/* Enable toggle */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-ink">Enable Portal</h3>
                <p className="mt-0.5 text-xs text-ink-mute">
                  Make your portal publicly accessible so visitors can browse and chat with your agents.
                </p>
              </div>
              <button
                onClick={() => setEnabled((v) => !v)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                  enabled
                    ? 'bg-leaf-wash text-forest hover:bg-mint'
                    : 'bg-sand text-ink-soft hover:bg-line'
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
              <div className="border-t border-sand pt-4">
                <label className="block text-xs font-medium text-ink-soft mb-1">
                  Tenant Slug <span className="text-ash font-normal">(read-only, use as NEXT_PUBLIC_TENANT_SLUG)</span>
                </label>
                <div className="flex items-center gap-2 px-3 py-2 bg-cream border border-line rounded-lg text-sm text-ink-soft font-mono">
                  <Globe className="w-3.5 h-3.5 text-ash flex-shrink-0" />
                  {portal.subdomain}
                </div>
              </div>
            )}

            {/* Custom domain */}
            <div className={portal?.subdomain ? '' : 'border-t border-sand pt-4'}>
              <label className="block text-xs font-medium text-ink-soft mb-1">
                Custom Domain <span className="text-ash font-normal">(optional, e.g. ai.yourcompany.com)</span>
              </label>
              <div className="relative">
                <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ash" />
                <input
                  type="text"
                  value={customDomain}
                  onChange={(e) => setCustomDomain(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-ink transition-colors"
                  placeholder="ai.yourcompany.com"
                />
              </div>
            </div>
          </div>

          {/* Featured Agents */}
          <div className="bg-white rounded-lg border border-line p-5">
            <h3 className="text-sm font-semibold text-ink mb-1">Featured Agents</h3>
            <p className="text-xs text-ink-mute mb-4">
              Select agents to highlight on your portal home page.
            </p>

            {agents.length === 0 ? (
              <p className="text-xs text-ash italic">No agents found.</p>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {agents.map((agent: any) => {
                  const slug = agent.slug || agent.agent_name
                  const checked = featuredSlugs.includes(slug)
                  return (
                    <label
                      key={slug}
                      className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                        checked ? 'border-ink bg-cream' : 'border-line hover:border-taupe'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleFeaturedAgent(slug)}
                        className="accent-ink"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-ink truncate">{agent.agent_name}</p>
                        {agent.description && (
                          <p className="text-xs text-ink-mute truncate">{agent.description}</p>
                        )}
                      </div>
                      {agent.portal_visibility && agent.portal_visibility !== 'hidden' && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-leaf-wash text-forest font-medium flex-shrink-0">
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
          <div className="bg-cream rounded-lg border border-line p-5">
            <h3 className="text-sm font-semibold text-ink mb-1.5">Deploy Your Portal</h3>
            <p className="text-xs text-ink-soft mb-3">
              Fork the <strong>synkora-portal</strong> repository, set these two environment variables, and
              deploy anywhere, Vercel, self-hosted, or any static host.
            </p>
            <div className="font-mono text-xs bg-white border border-line rounded p-3 space-y-1 text-ink">
              <p>NEXT_PUBLIC_SYNKORA_API_URL=https://your-api.com</p>
              <p>NEXT_PUBLIC_TENANT_SLUG={portal?.subdomain ?? 'your-slug'}</p>
            </div>
            <a
              href="https://github.com/your-org/synkora-portal"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-xs text-ink-soft hover:underline font-medium"
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
