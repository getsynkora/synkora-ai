'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { ArrowLeft, Save, Globe, Palette } from 'lucide-react'
import { useAgentDomains } from '@/hooks/useAgentDomains'

export default function EditDomainPage() {
  const params = useParams()
  const router = useRouter()
  const agentName = params.agentName as string
  const domainId = params.domainId as string

  const { domains, loading, error, updateDomain } = useAgentDomains({ agentId: agentName })
  const [saving, setSaving] = useState(false)

  const domain = domains.find((d) => d.id === domainId)

  // DNS Settings
  const [dnsSettings, setDnsSettings] = useState({
    subdomain: '',
    domain: '',
    is_custom_domain: true,
  })

  useEffect(() => {
    if (domain) {
      setDnsSettings({
        subdomain: domain.subdomain || '',
        domain: domain.domain || '',
        is_custom_domain: domain.is_custom_domain,
      })
    }
  }, [domain])

  const handleSave = async () => {
    try {
      setSaving(true)
      // Ensure subdomain is explicitly set (empty string if blank)
      const updateData = {
        ...dnsSettings,
        subdomain: dnsSettings.subdomain || '',
      }
      await updateDomain(domainId, updateData)
      toast.success('DNS settings saved successfully!')
      router.push(`/agents/${agentName}/domains`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save DNS settings')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-warn mx-auto"></div>
          <p className="mt-4 text-ink-soft">Loading domain…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen p-4 md:p-8">
        <div className="max-w-3xl mx-auto">
          <div className="bg-blush-wash border border-blush rounded-lg p-4 text-wine">
            {error}
          </div>
        </div>
      </div>
    )
  }

  if (!domain) {
    return (
      <div className="min-h-screen p-4 md:p-8">
        <div className="max-w-3xl mx-auto">
          <div className="bg-sand-deep border border-honey rounded-lg p-4 text-gold">
            Domain not found
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 md:p-6">
      <div className="max-w-4xl mx-auto">
        <button
          onClick={() => router.push(`/agents/${agentName}/domains`)}
          className="flex items-center gap-2 text-warn hover:text-gold mb-6 transition-colors text-sm font-medium"
        >
          <ArrowLeft size={16} />
          Back to Domains
        </button>

        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Edit Domain Settings</h1>
            <p className="text-ink-soft mt-1 text-sm">
              Configure DNS settings for {domain.domain}
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => router.push(`/agents/${agentName}/chat-customization`)}
              className="px-4 py-2 text-sm bg-white border border-taupe text-ink-soft rounded-lg hover:bg-white hover:border-honey transition-colors shadow-sm font-medium"
            >
              <Palette className="w-4 h-4 mr-2 inline" />
              Chat Customization
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-5 py-2 text-sm bg-warn text-white rounded-lg hover:from-warn hover:to-warn transition-[color,background-color,border-color,box-shadow,opacity,transform] disabled:opacity-50 disabled:cursor-not-allowed shadow-sm font-medium"
            >
              <Save className="w-4 h-4 mr-2 inline" />
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </div>

        {/* DNS Settings */}
        <div className="space-y-5">
          <div className="bg-white rounded-xl shadow-sm border border-line p-5">
            <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
              <Globe className="w-4 h-4 text-warn" />
              Domain Configuration
            </h2>
            <div className="space-y-5">
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-2">
                  Domain Type
                </label>
                <div className="space-y-2">
                  <label className="flex items-start gap-2 p-3 border-2 border-line rounded-lg cursor-pointer hover:border-honey hover:bg-sand-deep/50 transition-colors">
                    <input
                      type="radio"
                      checked={dnsSettings.is_custom_domain}
                      onChange={() => setDnsSettings({ ...dnsSettings, is_custom_domain: true })}
                      className="mt-0.5 w-4 h-4 text-warn focus:ring-warn"
                    />
                    <div className="flex-1">
                      <span className="font-medium text-ink block mb-0.5 text-sm">
                        Custom Domain
                      </span>
                      <span className="text-xs text-ink-soft">
                        Use your own domain (e.g., chat.yourdomain.com)
                      </span>
                    </div>
                  </label>
                  <label className="flex items-start gap-2 p-3 border-2 border-line rounded-lg cursor-pointer hover:border-honey hover:bg-sand-deep/50 transition-colors">
                    <input
                      type="radio"
                      checked={!dnsSettings.is_custom_domain}
                      onChange={() => setDnsSettings({ ...dnsSettings, is_custom_domain: false })}
                      className="mt-0.5 w-4 h-4 text-warn focus:ring-warn"
                    />
                    <div className="flex-1">
                      <span className="font-medium text-ink block mb-0.5 text-sm">
                        Platform Subdomain
                      </span>
                      <span className="text-xs text-ink-soft">
                        Use a subdomain on our platform
                      </span>
                    </div>
                  </label>
                </div>
              </div>

              {dnsSettings.is_custom_domain ? (
                <>
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-2">
                      Domain Name *
                    </label>
                    <input
                      type="text"
                      value={dnsSettings.domain}
                      onChange={(e) => setDnsSettings({ ...dnsSettings, domain: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-warn focus:border-transparent"
                      placeholder="yourdomain.com"
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Enter your root domain (e.g., yourdomain.com)
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-2">
                      Platform Subdomain *
                    </label>
                    <input
                      type="text"
                      value={dnsSettings.subdomain}
                      onChange={(e) => setDnsSettings({ ...dnsSettings, subdomain: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-warn focus:border-transparent"
                      placeholder="myagent"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Required: A platform subdomain is always needed for fallback access and DNS mapping (e.g., myagent.synkora.ai)
                    </p>
                  </div>
                </>
              ) : (
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-2">
                    Subdomain *
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={dnsSettings.subdomain}
                      onChange={(e) => setDnsSettings({ ...dnsSettings, subdomain: e.target.value })}
                      className="flex-1 px-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-warn focus:border-transparent"
                      placeholder="yourname"
                    />
                    <span className="text-ink-soft text-sm">.platform.com</span>
                  </div>
                  <p className="text-xs text-ink-mute mt-1">
                    Choose a unique subdomain for your agent
                  </p>
                </div>
              )}

              <div className="bg-sand-deep border border-honey rounded-lg p-3 mt-4">
                <h3 className="font-medium text-gold text-xs mb-2">Current Domain</h3>
                <p className="text-gold text-sm font-mono">
                  {domain?.subdomain ? `${domain.subdomain}.${domain.domain}` : domain?.domain}
                </p>
                {domain?.is_verified ? (
                  <p className="text-leaf text-xs mt-2 flex items-center gap-1">
                    <span className="w-2 h-2 bg-leaf rounded-full"></span>
                    Verified
                  </p>
                ) : (
                  <p className="text-warn text-xs mt-2 flex items-center gap-1">
                    <span className="w-2 h-2 bg-warn rounded-full"></span>
                    Pending Verification
                  </p>
                )}
              </div>

              <div className="bg-sand-deep border border-honey rounded-lg p-4">
                <h3 className="font-medium text-gold text-sm mb-2 flex items-center gap-1.5">
                  
                  Important
                </h3>
                <ul className="text-gold text-xs space-y-1.5">
                  <li className="flex items-start gap-2">
                    <span className="text-warn mt-0.5">•</span>
                    <span>Changing domain settings will require DNS reconfiguration</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-warn mt-0.5">•</span>
                    <span>You will need to verify the new domain before it becomes active</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-warn mt-0.5">•</span>
                    <span>The old domain will remain active until the new one is verified</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
