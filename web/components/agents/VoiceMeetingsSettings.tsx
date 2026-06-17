'use client'

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { Phone, Video, Bot, ChevronDown, ChevronRight, Save } from 'lucide-react'
import {
  getVoiceMeetingsConfig,
  saveVoiceMeetingsConfig,
  DEFAULT_CONFIG,
  type VoiceMeetingsConfig,
} from '@/lib/api/voice-meetings'

const PLATFORMS = [
  { value: 'zoom', label: 'Zoom' },
  { value: 'google_meet', label: 'Google Meet' },
  { value: 'teams', label: 'Microsoft Teams' },
  { value: 'slack_huddle', label: 'Slack Huddle' },
]

interface SectionProps {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
}

function Section({ title, icon, children, defaultOpen = false }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <span className="flex items-center gap-2 font-medium text-gray-800">
          {icon}
          {title}
        </span>
        {open ? <ChevronDown className="w-4 h-4 text-gray-500" /> : <ChevronRight className="w-4 h-4 text-gray-500" />}
      </button>
      {open && <div className="px-4 py-4 space-y-4">{children}</div>}
    </div>
  )
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer">
      <div
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-6 rounded-full transition-colors ${checked ? 'bg-red-500' : 'bg-gray-300'}`}
      >
        <span
          className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-4' : ''}`}
        />
      </div>
      <span className="text-sm text-gray-700">{label}</span>
    </label>
  )
}

interface Props {
  agentSlug: string
}

export default function VoiceMeetingsSettings({ agentSlug }: Props) {
  const [config, setConfig] = useState<VoiceMeetingsConfig>(DEFAULT_CONFIG)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getVoiceMeetingsConfig(agentSlug)
      .then((data) => setConfig({ ...DEFAULT_CONFIG, ...data }))
      .catch(() => toast.error('Failed to load Voice & Meetings settings'))
      .finally(() => setLoading(false))
  }, [agentSlug])

  const handleSave = async () => {
    setSaving(true)
    try {
      await saveVoiceMeetingsConfig(agentSlug, config)
      toast.success('Voice & Meetings settings saved')
    } catch {
      toast.error('Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const setPhone = (patch: Partial<typeof config.phone>) =>
    setConfig((c) => ({ ...c, phone: { ...c.phone, ...patch } }))
  const setWebCall = (patch: Partial<typeof config.web_call>) =>
    setConfig((c) => ({ ...c, web_call: { ...c.web_call, ...patch } }))
  const setBot = (patch: Partial<typeof config.meeting_bot>) =>
    setConfig((c) => ({ ...c, meeting_bot: { ...c.meeting_bot, ...patch } }))

  if (loading) return <div className="text-sm text-gray-500 py-4">Loading...</div>

  return (
    <div className="space-y-4">
      {/* Phone */}
      <Section title="Phone" icon={<Phone className="w-4 h-4" />} defaultOpen={config.phone.enabled}>
        <Toggle checked={config.phone.enabled} onChange={(v) => setPhone({ enabled: v })} label="Enable inbound phone calls" />
        {config.phone.enabled && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">STT Provider</label>
              <select
                value={config.phone.stt_provider}
                onChange={(e) => setPhone({ stt_provider: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm"
              >
                <option value="deepgram">Deepgram</option>
                <option value="openai_whisper">OpenAI Whisper</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">TTS Provider</label>
              <select
                value={config.phone.tts_provider}
                onChange={(e) => setPhone({ tts_provider: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm"
              >
                <option value="elevenlabs">ElevenLabs</option>
                <option value="openai_tts">OpenAI TTS</option>
                <option value="deepgram">Deepgram</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">TTS Voice ID</label>
              <input
                type="text"
                value={config.phone.tts_voice_id ?? ''}
                onChange={(e) => setPhone({ tts_voice_id: e.target.value || null })}
                placeholder="e.g. EXAVITQu4vr4xnSDxMaL"
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <p className="text-xs text-gray-500">
              Configure phone number and Vapi credentials in{' '}
              <a href={`/agents/${agentSlug}/settings/phone`} className="text-red-500 underline">
                Phone Settings
              </a>
              .
            </p>
          </>
        )}
      </Section>

      {/* Web Call */}
      <Section title="Web Call" icon={<Video className="w-4 h-4" />} defaultOpen={config.web_call.enabled}>
        <Toggle checked={config.web_call.enabled} onChange={(v) => setWebCall({ enabled: v })} label="Enable browser-based voice calls" />
        {config.web_call.enabled && (
          <>
            <Toggle
              checked={config.web_call.show_on_agent_card}
              onChange={(v) => setWebCall({ show_on_agent_card: v })}
              label="Show 'Call Agent' button on public agent card"
            />
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Vapi Public Key</label>
              <input
                type="text"
                value={config.web_call.vapi_public_key ?? ''}
                onChange={(e) => setWebCall({ vapi_public_key: e.target.value || null })}
                placeholder="Your Vapi public key (safe for browser)"
                className="w-full border rounded px-3 py-2 text-sm font-mono"
              />
              <p className="text-xs text-gray-500 mt-1">
                Find this in your{' '}
                <span className="text-gray-700 font-medium">Vapi Dashboard → Account → Public Key</span>.
                This is not your API secret.
              </p>
            </div>
          </>
        )}
      </Section>

      {/* Meeting Bot */}
      <Section title="Meeting Bot" icon={<Bot className="w-4 h-4" />} defaultOpen={config.meeting_bot.enabled}>
        <Toggle checked={config.meeting_bot.enabled} onChange={(v) => setBot({ enabled: v })} label="Enable meeting bot (Recall.ai)" />
        {config.meeting_bot.enabled && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Bot Display Name</label>
              <input
                type="text"
                value={config.meeting_bot.bot_name}
                onChange={(e) => setBot({ bot_name: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Bot Avatar URL (optional)</label>
              <input
                type="text"
                value={config.meeting_bot.bot_avatar_url ?? ''}
                onChange={(e) => setBot({ bot_avatar_url: e.target.value || null })}
                placeholder="https://..."
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-2">Supported Platforms</label>
              <div className="space-y-2">
                {PLATFORMS.map((p) => (
                  <label key={p.value} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.meeting_bot.platforms.includes(p.value)}
                      onChange={(e) => {
                        const next = e.target.checked
                          ? [...config.meeting_bot.platforms, p.value]
                          : config.meeting_bot.platforms.filter((x) => x !== p.value)
                        setBot({ platforms: next })
                      }}
                      className="rounded"
                    />
                    <span className="text-sm text-gray-700">{p.label}</span>
                  </label>
                ))}
              </div>
            </div>
            <Toggle
              checked={config.meeting_bot.auto_record}
              onChange={(v) => setBot({ auto_record: v })}
              label="Auto-record meetings"
            />
            <p className="text-xs text-gray-500">
              Configure Recall.ai credentials in{' '}
              <a href="/settings/oauth-apps" className="text-red-500 underline">
                OAuth Apps
              </a>
              .
            </p>
          </>
        )}
      </Section>

      <div className="flex justify-end pt-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium text-white bg-red-500 hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Save className="w-4 h-4" />
          {saving ? 'Saving…' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}
