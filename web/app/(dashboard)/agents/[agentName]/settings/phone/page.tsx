'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import { Phone, Key, Save, Copy, Check, Plus, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  getPhoneConfig,
  savePhoneConfig,
  checkCredential,
  saveVapiCredential,
  getPhoneNumbers,
  addPhoneNumber,
  removePhoneNumber,
  type PhoneConfig,
  type PhoneNumber,
} from '@/lib/api/phone'
import { apiClient } from '@/lib/api/client'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'it', label: 'Italian' },
  { value: 'nl', label: 'Dutch' },
  { value: 'pl', label: 'Polish' },
  { value: 'ja', label: 'Japanese' },
  { value: 'zh', label: 'Chinese' },
]

const DEFAULT_CONFIG: PhoneConfig = {
  enabled: false,
  provider: 'vapi',
  greeting: 'Hi, how can I help you today?',
  end_call_message: 'Goodbye! Have a great day.',
  voice_provider: null,
  voice_id: null,
  language: 'en',
  max_duration_seconds: 300,
  record_calls: false,
}

export default function AgentPhoneSettingsPage() {
  const params = useParams()
  const agentName = params.agentName as string

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [config, setConfig] = useState<PhoneConfig>(DEFAULT_CONFIG)
  const [credConfigured, setCredConfigured] = useState(false)
  const [vapiApiKey, setVapiApiKey] = useState('')
  const [savingKey, setSavingKey] = useState(false)
  const [phoneNumbers, setPhoneNumbers] = useState<PhoneNumber[]>([])
  const [newNumber, setNewNumber] = useState('')
  const [addingNumber, setAddingNumber] = useState(false)
  const [agentId, setAgentId] = useState<string>('')
  const [copiedWebhook, setCopiedWebhook] = useState(false)

  const webhookUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'}/api/v1/phone/webhook/vapi`

  useEffect(() => {
    load()
  }, [agentName])

  async function load() {
    try {
      setLoading(true)
      const [phoneConfig, credCheck, numbers, agent] = await Promise.all([
        getPhoneConfig(agentName),
        checkCredential('vapi'),
        getPhoneNumbers(),
        apiClient.getAgent(agentName),
      ])
      if (phoneConfig && Object.keys(phoneConfig).length > 0) {
        setConfig({ ...DEFAULT_CONFIG, ...phoneConfig } as PhoneConfig)
      }
      setCredConfigured(credCheck.configured)
      setAgentId(agent.id)
      setPhoneNumbers(numbers.filter((n: PhoneNumber) => n.agent_id === agent.id))
    } catch (err) {
      toast.error('Failed to load phone settings')
    } finally {
      setLoading(false)
    }
  }

  async function handleSaveConfig() {
    setSaving(true)
    try {
      const saved = await savePhoneConfig(agentName, config)
      setConfig({ ...DEFAULT_CONFIG, ...saved })
      toast.success('Phone settings saved')
    } catch {
      toast.error('Failed to save phone settings')
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveApiKey() {
    if (!vapiApiKey.trim()) return
    setSavingKey(true)
    try {
      await saveVapiCredential(vapiApiKey.trim())
      setVapiApiKey('')
      setCredConfigured(true)
      toast.success('Vapi API key saved')
    } catch {
      toast.error('Failed to save API key')
    } finally {
      setSavingKey(false)
    }
  }

  async function handleAddNumber() {
    if (!newNumber.trim() || !agentId) return
    setAddingNumber(true)
    try {
      const pn = await addPhoneNumber({ phone_number: newNumber.trim(), provider: 'vapi', agent_id: agentId })
      setPhoneNumbers((prev) => [...prev, pn])
      setNewNumber('')
      toast.success('Phone number added')
    } catch {
      toast.error('Failed to add phone number')
    } finally {
      setAddingNumber(false)
    }
  }

  async function handleRemoveNumber(id: string) {
    try {
      await removePhoneNumber(id)
      setPhoneNumbers((prev) => prev.filter((n) => n.id !== id))
      toast.success('Phone number removed')
    } catch {
      toast.error('Failed to remove phone number')
    }
  }

  function copyWebhook() {
    navigator.clipboard.writeText(webhookUrl)
    setCopiedWebhook(true)
    setTimeout(() => setCopiedWebhook(false), 2000)
  }

  if (loading) {
    return (
      <AgentPageShell agentName={agentName} title="Phone Settings" icon={Phone}>
        <AgentPagePanel>
          <div className="flex items-center justify-center h-40 text-gray-400 text-sm">Loading…</div>
        </AgentPagePanel>
      </AgentPageShell>
    )
  }

  return (
    <AgentPageShell agentName={agentName} title="Phone Settings" icon={Phone}>
      <AgentPagePanel>
        <div className="max-w-2xl space-y-8">

          {/* Header */}
          <div className="flex items-center gap-3">
            <Phone className="w-5 h-5 text-gray-500" />
            <div>
              <h2 className="text-base font-semibold text-gray-900">Inbound Phone Calls</h2>
              <p className="text-sm text-gray-500 mt-0.5">Let callers reach this agent via phone through Vapi.ai</p>
            </div>
          </div>

          {/* Enable toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700">Enable inbound calls</p>
              <p className="text-xs text-gray-500 mt-0.5">Allow this agent to answer phone calls</p>
            </div>
            <button
              onClick={() => setConfig((c) => ({ ...c, enabled: !c.enabled }))}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                config.enabled ? 'bg-rose-600' : 'bg-gray-200'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  config.enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Vapi API Key */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Key className="w-4 h-4 text-gray-400" />
              <label className="text-sm font-medium text-gray-700">Vapi API Key</label>
              {credConfigured && (
                <span className="text-xs text-green-600 font-medium bg-green-50 px-2 py-0.5 rounded-full">Configured</span>
              )}
            </div>
            <div className="flex gap-2">
              <input
                type="password"
                value={vapiApiKey}
                onChange={(e) => setVapiApiKey(e.target.value)}
                placeholder={credConfigured ? 'Enter new key to replace' : 'sk-...'}
                className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              />
              <button
                onClick={handleSaveApiKey}
                disabled={!vapiApiKey.trim() || savingKey}
                className="px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg disabled:opacity-50 hover:bg-gray-700 transition-colors"
              >
                {savingKey ? 'Saving…' : 'Save Key'}
              </button>
            </div>
          </div>

          {/* Webhook URL */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Webhook URL</label>
            <p className="text-xs text-gray-500">Configure this URL in your Vapi phone number settings</p>
            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
              <span className="flex-1 text-sm font-mono text-gray-600 truncate">{webhookUrl}</span>
              <button onClick={copyWebhook} className="text-gray-400 hover:text-gray-600 flex-shrink-0">
                {copiedWebhook ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Phone numbers */}
          <div className="space-y-3">
            <label className="text-sm font-medium text-gray-700">Phone Numbers (BYOP)</label>
            <p className="text-xs text-gray-500">Add numbers you own in Vapi and want to route to this agent</p>
            {phoneNumbers.map((pn) => (
              <div key={pn.id} className="flex items-center justify-between bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                <span className="text-sm font-mono text-gray-700">{pn.phone_number}</span>
                <button onClick={() => handleRemoveNumber(pn.id)} className="text-gray-400 hover:text-red-500">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
            <div className="flex gap-2">
              <input
                type="tel"
                value={newNumber}
                onChange={(e) => setNewNumber(e.target.value)}
                placeholder="+14155551234"
                className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              />
              <button
                onClick={handleAddNumber}
                disabled={!newNumber.trim() || addingNumber}
                className="px-3 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg disabled:opacity-50 hover:bg-gray-700 transition-colors flex items-center gap-1"
              >
                <Plus className="w-4 h-4" />
                Add
              </button>
            </div>
          </div>

          {/* Greeting */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Greeting</label>
            <textarea
              rows={2}
              value={config.greeting}
              onChange={(e) => setConfig((c) => ({ ...c, greeting: e.target.value }))}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 resize-none"
            />
          </div>

          {/* End call message */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">End Call Message</label>
            <textarea
              rows={2}
              value={config.end_call_message}
              onChange={(e) => setConfig((c) => ({ ...c, end_call_message: e.target.value }))}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 resize-none"
            />
          </div>

          {/* Voice ID */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Voice ID</label>
            <p className="text-xs text-gray-500">ElevenLabs or other TTS voice ID (optional)</p>
            <input
              type="text"
              value={config.voice_id ?? ''}
              onChange={(e) => setConfig((c) => ({ ...c, voice_id: e.target.value || null }))}
              placeholder="EXAVITQu4vr4xnSDxMaL"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
            />
          </div>

          {/* Language */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Language</label>
            <select
              value={config.language}
              onChange={(e) => setConfig((c) => ({ ...c, language: e.target.value }))}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 bg-white"
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>

          {/* Max duration */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Max Call Duration (seconds)</label>
            <input
              type="number"
              min={30}
              max={3600}
              value={config.max_duration_seconds}
              onChange={(e) => setConfig((c) => ({ ...c, max_duration_seconds: parseInt(e.target.value) || 300 }))}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
            />
          </div>

          {/* Record calls */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700">Record calls</p>
              <p className="text-xs text-gray-500 mt-0.5">Recording URLs will appear in call details</p>
            </div>
            <button
              onClick={() => setConfig((c) => ({ ...c, record_calls: !c.record_calls }))}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                config.record_calls ? 'bg-rose-600' : 'bg-gray-200'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  config.record_calls ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Save */}
          <div className="flex justify-end pt-2 border-t border-gray-100">
            <button
              onClick={handleSaveConfig}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-rose-600 rounded-lg disabled:opacity-50 hover:bg-rose-700 transition-colors"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saving…' : 'Save Settings'}
            </button>
          </div>
        </div>
      </AgentPagePanel>
    </AgentPageShell>
  )
}
