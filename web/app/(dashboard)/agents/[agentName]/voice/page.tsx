'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { Mic, Volume2, Key, Save, Trash2 } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

interface VoiceConfig {
  stt_provider: 'web_speech' | 'openai_whisper'
  tts_provider: 'web_speech' | 'openai_tts' | 'elevenlabs'
  tts_voice?: string
  tts_model?: string
  language?: string
}

interface VoiceApiKey {
  id: string
  provider: string
  is_active: boolean
  created_at: string
}

export default function AgentVoicePage() {
  const params = useParams()
  const router = useRouter()
  const agentName = params.agentName as string
  
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [agentData, setAgentData] = useState<any>(null)
  
  // Voice configuration
  const [voiceEnabled, setVoiceEnabled] = useState(false)
  const [voiceConfig, setVoiceConfig] = useState<VoiceConfig>({
    stt_provider: 'web_speech',
    tts_provider: 'web_speech',
    language: 'en-US',
  })
  
  // API Keys management
  const [apiKeys, setApiKeys] = useState<VoiceApiKey[]>([])
  const [showAddKey, setShowAddKey] = useState(false)
  const [newKey, setNewKey] = useState({
    provider: 'openai_tts',
    api_key: '',
  })

  useEffect(() => {
    fetchAgentData()
    fetchApiKeys()
  }, [agentName])

  const fetchAgentData = async () => {
    try {
      setLoading(true)
      const agent = await apiClient.getAgent(agentName)
      setAgentData(agent)
      
      // Load voice configuration
      if (agent.voice_enabled) {
        setVoiceEnabled(true)
      }
      
      if (agent.voice_config) {
        setVoiceConfig({
          stt_provider: agent.voice_config.stt_provider || 'web_speech',
          tts_provider: agent.voice_config.tts_provider || 'web_speech',
          tts_voice: agent.voice_config.tts_voice,
          tts_model: agent.voice_config.tts_model,
          language: agent.voice_config.language || 'en-US',
        })
      }
    } catch (error) {
      console.error('Failed to fetch agent:', error)
      toast.error('Failed to load agent data')
    } finally {
      setLoading(false)
    }
  }

  const fetchApiKeys = async () => {
    try {
      const response = await apiClient.request('GET', `/api/v1/voice/api-keys`)
      setApiKeys(response?.data?.api_keys || [])
    } catch (error) {
      console.error('Failed to fetch API keys:', error)
    }
  }

  const handleSaveConfig = async () => {
    setSaving(true)
    try {
      await apiClient.updateAgent(agentName, {
        voice_enabled: voiceEnabled,
        voice_config: voiceEnabled ? voiceConfig : null,
      })
      
      toast.success('Voice configuration saved successfully!')
    } catch (error) {
      console.error('Failed to save configuration:', error)
      toast.error('Failed to save voice configuration')
    } finally {
      setSaving(false)
    }
  }

  const handleAddApiKey = async () => {
    if (!newKey.api_key) {
      toast.error('Please enter an API key')
      return
    }

    try {
      await apiClient.request('POST', '/api/v1/voice/api-keys', newKey)
      toast.success('API key added successfully!')
      setShowAddKey(false)
      setNewKey({ provider: 'openai_tts', api_key: '' })
      fetchApiKeys()
    } catch (error) {
      console.error('Failed to add API key:', error)
      toast.error('Failed to add API key')
    }
  }

  const handleDeleteApiKey = async (keyId: string) => {
    if (!confirm('Are you sure you want to delete this API key?')) return

    try {
      await apiClient.request('DELETE', `/api/v1/voice/api-keys/${keyId}`)
      toast.success('API key deleted successfully!')
      fetchApiKeys()
    } catch (error) {
      console.error('Failed to delete API key:', error)
      toast.error('Failed to delete API key')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto"></div>
          <p className="mt-4 text-gray-600 text-sm">Loading voice settings...</p>
        </div>
      </div>
    )
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Voice Settings"
      description={<>Configure voice input and output for <span className="font-semibold text-gray-900">{agentData?.agent_name}</span>.</>}
      icon={Mic}
      badge="Voice Experience"
      maxWidthClassName="max-w-[90rem]"
    >

        {/* Enable Voice */}
        <AgentPagePanel className="p-5 mb-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                <Mic size={20} className="text-red-600" />
                Enable Voice Chat
              </h2>
              <p className="text-xs text-gray-600 mt-1">
                Allow users to interact with this agent using voice
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={voiceEnabled}
                onChange={(e) => setVoiceEnabled(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-12 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
            </label>
          </div>
        </AgentPagePanel>

        {voiceEnabled && (
          <>
            {/* Speech-to-Text Configuration */}
            <AgentPagePanel className="p-5 mb-5">
              <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Mic size={20} className="text-red-600" />
                Speech-to-Text (STT)
              </h2>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-2">
                    STT Provider
                  </label>
                  <select
                    value={voiceConfig.stt_provider}
                    onChange={(e) => setVoiceConfig({ ...voiceConfig, stt_provider: e.target.value as any })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  >
                    <option value="web_speech">Web Speech API (Free, Browser-based)</option>
                    <option value="openai_whisper">OpenAI Whisper (Paid, High Accuracy)</option>
                  </select>
                  <p className="mt-2 text-xs text-gray-600">
                    {voiceConfig.stt_provider === 'web_speech' 
                      ? '✅ Free browser-based speech recognition. Works offline in supported browsers.'
                      : '💰 Requires OpenAI API key. Provides superior accuracy and supports 50+ languages.'}
                  </p>
                </div>

                {voiceConfig.stt_provider === 'openai_whisper' && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <p className="text-xs text-red-800">
                      ⚠️ OpenAI Whisper requires an API key. Add your OpenAI API key in the API Keys section below.
                    </p>
                  </div>
                )}
              </div>
            </AgentPagePanel>

            {/* Text-to-Speech Configuration */}
            <AgentPagePanel className="p-5 mb-5">
              <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Volume2 size={20} className="text-red-600" />
                Text-to-Speech (TTS)
              </h2>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-2">
                    TTS Provider
                  </label>
                  <select
                    value={voiceConfig.tts_provider}
                    onChange={(e) => setVoiceConfig({ ...voiceConfig, tts_provider: e.target.value as any })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  >
                    <option value="web_speech">Web Speech API (Free, Basic)</option>
                    <option value="openai_tts">OpenAI TTS (Paid, Natural)</option>
                    <option value="elevenlabs">ElevenLabs (Paid, Premium)</option>
                  </select>
                  <p className="mt-2 text-xs text-gray-600">
                    {voiceConfig.tts_provider === 'web_speech' && '✅ Free browser-based text-to-speech. Basic quality.'}
                    {voiceConfig.tts_provider === 'openai_tts' && '💰 Natural-sounding voices from OpenAI. Requires API key.'}
                    {voiceConfig.tts_provider === 'elevenlabs' && '💎 Premium quality voices with emotion. Requires API key.'}
                  </p>
                </div>

                {voiceConfig.tts_provider === 'openai_tts' && (
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-2">
                      Voice
                    </label>
                    <select
                      value={voiceConfig.tts_voice || 'alloy'}
                      onChange={(e) => setVoiceConfig({ ...voiceConfig, tts_voice: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                    >
                      <option value="alloy">Alloy (Neutral)</option>
                      <option value="echo">Echo (Male)</option>
                      <option value="fable">Fable (British Male)</option>
                      <option value="onyx">Onyx (Deep Male)</option>
                      <option value="nova">Nova (Female)</option>
                      <option value="shimmer">Shimmer (Soft Female)</option>
                    </select>
                  </div>
                )}

                {voiceConfig.tts_provider === 'elevenlabs' && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <p className="text-xs text-red-800">
                      💡 ElevenLabs voices can be configured after adding your API key. You'll be able to select from your available voices.
                    </p>
                  </div>
                )}

                {(voiceConfig.tts_provider === 'openai_tts' || voiceConfig.tts_provider === 'elevenlabs') && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <p className="text-xs text-red-800">
                      ⚠️ {voiceConfig.tts_provider === 'openai_tts' ? 'OpenAI' : 'ElevenLabs'} TTS requires an API key. Add your API key in the section below.
                    </p>
                  </div>
                )}
              </div>
            </AgentPagePanel>

            {/* Language Configuration */}
            <AgentPagePanel className="p-5 mb-5">
              <h2 className="text-base font-semibold text-gray-900 mb-4">Language Settings</h2>
              
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-2">
                  Primary Language
                </label>
                <select
                  value={voiceConfig.language || 'en-US'}
                  onChange={(e) => setVoiceConfig({ ...voiceConfig, language: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                >
                  <option value="en-US">English (US)</option>
                  <option value="en-GB">English (UK)</option>
                  <option value="es-ES">Spanish (Spain)</option>
                  <option value="es-MX">Spanish (Mexico)</option>
                  <option value="fr-FR">French</option>
                  <option value="de-DE">German</option>
                  <option value="it-IT">Italian</option>
                  <option value="pt-BR">Portuguese (Brazil)</option>
                  <option value="ja-JP">Japanese</option>
                  <option value="ko-KR">Korean</option>
                  <option value="zh-CN">Chinese (Simplified)</option>
                  <option value="zh-TW">Chinese (Traditional)</option>
                </select>
              </div>
            </AgentPagePanel>

            {/* API Keys Management */}
            <AgentPagePanel className="p-5 mb-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                  <Key size={20} className="text-red-600" />
                  Voice API Keys
                </h2>
                <button
                  onClick={() => setShowAddKey(!showAddKey)}
                  className="px-3 py-2 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg hover:from-red-600 hover:to-red-700 transition-all text-xs font-medium shadow-sm"
                >
                  {showAddKey ? 'Cancel' : 'Add API Key'}
                </button>
              </div>

              {showAddKey && (
                <div className="mb-5 p-4 bg-red-50 rounded-lg border border-red-200">
                  <h3 className="font-medium text-gray-900 mb-3 text-sm">Add New API Key</h3>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-2">
                        Provider
                      </label>
                      <select
                        value={newKey.provider}
                        onChange={(e) => setNewKey({ ...newKey, provider: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      >
                        <option value="openai_whisper">OpenAI Whisper (STT)</option>
                        <option value="openai_tts">OpenAI TTS</option>
                        <option value="elevenlabs">ElevenLabs</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-2">
                        API Key
                      </label>
                      <input
                        type="password"
                        value={newKey.api_key}
                        onChange={(e) => setNewKey({ ...newKey, api_key: e.target.value })}
                        placeholder="sk-..."
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      />
                    </div>
                    <button
                      onClick={handleAddApiKey}
                      className="w-full px-4 py-2 text-sm bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg hover:from-red-600 hover:to-red-700 transition-all font-medium shadow-sm"
                    >
                      Save API Key
                    </button>
                  </div>
                </div>
              )}

              {apiKeys.length > 0 ? (
                <div className="space-y-2">
                  {apiKeys.map((key) => (
                    <div
                      key={key.id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200"
                    >
                      <div>
                        <div className="font-medium text-gray-900 text-sm capitalize">{key.provider.replace(/_/g, ' ')}</div>
                        <div className="text-xs text-gray-600">
                          Added {new Date(key.created_at).toLocaleDateString()}
                        </div>
                      </div>
                      <button
                        onClick={() => handleDeleteApiKey(key.id)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded transition-colors"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Key size={40} className="mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No API keys configured</p>
                  <p className="text-xs mt-1">Add API keys to use cloud-based voice providers</p>
                </div>
              )}
            </AgentPagePanel>
          </>
        )}

        {/* Save Button */}
        <div className="flex justify-end gap-3">
          <button
            onClick={() => router.push(`/agents/${agentName}/view`)}
            className="px-5 py-2 text-sm border border-gray-300 rounded-lg hover:bg-white hover:border-red-300 transition-colors font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleSaveConfig}
            disabled={saving}
            className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            <Save size={16} />
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
    </AgentPageShell>
  )
}
