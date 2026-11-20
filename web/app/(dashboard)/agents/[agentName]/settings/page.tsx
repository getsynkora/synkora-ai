'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import { Globe, EyeOff, Users, Save, Settings } from 'lucide-react'
import toast from 'react-hot-toast'
import { getAgent, updateAgent } from '@/lib/api/agents'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

type PortalVisibility = 'hidden' | 'public' | 'members_only'

const VISIBILITY_OPTIONS: {
  value: PortalVisibility
  label: string
  description: string
  icon: React.ReactNode
}[] = [
  {
    value: 'hidden',
    label: 'Hidden',
    description: 'Not shown on portal public pages. Accessible inside the dashboard only.',
    icon: <EyeOff className="w-4 h-4" />,
  },
  {
    value: 'public',
    label: 'Public',
    description: 'Visible to anyone visiting your portal. Chat requires login.',
    icon: <Globe className="w-4 h-4" />,
  },
  {
    value: 'members_only',
    label: 'Members Only',
    description: 'Visible only to logged-in users of your portal.',
    icon: <Users className="w-4 h-4" />,
  },
]

export default function AgentPortalSettingsPage() {
  const params = useParams()
  const agentName = params.agentName as string

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [portalVisibility, setPortalVisibility] = useState<PortalVisibility>('hidden')

  useEffect(() => {
    async function load() {
      try {
        const agent = await getAgent(agentName)
        setPortalVisibility(agent.portal_visibility || 'hidden')
      } catch {
        toast.error('Failed to load agent settings')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [agentName])

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateAgent(agentName, { portal_visibility: portalVisibility })
      toast.success('Portal visibility saved')
    } catch {
      toast.error('Failed to save portal visibility')
    } finally {
      setSaving(false)
    }
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Portal Settings"
      description="Control how this agent appears on your white-label portal."
      icon={Settings}
      backHref={`/agents/${encodeURIComponent(agentName)}/view`}
      backLabel="Back to Agent"
      actions={
        <button
          onClick={handleSave}
          disabled={saving || loading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-ink text-white rounded-lg hover:from-danger hover:to-danger transition-[color,background-color,border-color,box-shadow,opacity,transform] text-xs font-medium shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Save className="w-3.5 h-3.5" />
          {saving ? 'Saving…' : 'Save'}
        </button>
      }
    >
      <AgentPagePanel className="p-5">
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-ink mb-0.5">Portal Visibility</h3>
          <p className="text-xs text-ink-mute">
            This is independent of the Synkora marketplace visibility (<code>is_public</code>).
          </p>
        </div>

        <div className="space-y-2.5">
          {VISIBILITY_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                portalVisibility === opt.value
                  ? 'border-ink bg-blush-wash'
                  : 'border-line bg-white hover:border-taupe'
              }`}
            >
              <input
                type="radio"
                name="portal_visibility"
                value={opt.value}
                checked={portalVisibility === opt.value}
                onChange={() => setPortalVisibility(opt.value)}
                className="mt-0.5 accent-danger"
                disabled={loading}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`${
                      portalVisibility === opt.value ? 'text-leaf' : 'text-ash'
                    }`}
                  >
                    {opt.icon}
                  </span>
                  <span className="text-sm font-medium text-ink">{opt.label}</span>
                </div>
                <p className="mt-0.5 text-xs text-ink-mute">{opt.description}</p>
              </div>
            </label>
          ))}
        </div>
      </AgentPagePanel>
    </AgentPageShell>
  )
}
