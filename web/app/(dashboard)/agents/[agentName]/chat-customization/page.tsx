'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { ArrowLeft, Palette, MessageSquare, Eye, Zap } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import AgentPageShell, { AgentPagePanel, AgentPageTabs } from '@/components/agents/AgentPageShell'

type Tab = 'branding' | 'content' | 'advanced' | 'preview'

export default function ChatCustomizationPage() {
  const params = useParams()
  const router = useRouter()
  const agentName = params.agentName as string
  
  const [activeTab, setActiveTab] = useState<Tab>('branding')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [agentId, setAgentId] = useState<string | null>(null)

  // Form data
  const [formData, setFormData] = useState({
    chat_title: '',
    chat_welcome_message: '',
    chat_placeholder: '',
    chat_primary_color: '#0d9488',
    chat_logo_url: '',
    chat_background_color: '#ffffff',
    chat_font_family: 'Inter',
    chat_transport: 'sse' as 'sse' | 'websocket',
  })

  useEffect(() => {
    fetchChatConfig()
  }, [agentName])

  const fetchChatConfig = async () => {
    try {
      setLoading(true)
      // Fetch agent by slug to get the UUID required by the chat-config endpoint
      const agentData = await apiClient.getAgent(agentName)
      const id = agentData?.id || agentData?.data?.id
      setAgentId(id)
      const config = await apiClient.getChatConfig(id)
      
      if (config) {
        setFormData({
          chat_title: config.chat_title || '',
          chat_welcome_message: config.chat_welcome_message || '',
          chat_placeholder: config.chat_placeholder || '',
          chat_primary_color: config.chat_primary_color || '#0d9488',
          chat_logo_url: config.chat_logo_url || '',
          chat_background_color: config.chat_background_color || '#ffffff',
          chat_font_family: config.chat_font_family || 'Inter',
          chat_transport: (config.chat_transport as 'sse' | 'websocket') || 'sse',
        })
      }
    } catch (error) {
      console.error('Failed to fetch chat config:', error)
      toast.error('Failed to load chat configuration')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!agentId) return
    setSaving(true)

    try {
      await apiClient.updateChatConfig(agentId, formData)
      toast.success('Chat customization saved successfully!')
      router.push(`/agents/${agentName}/view`)
    } catch (error) {
      console.error('Failed to update chat config:', error)
      toast.error('Failed to save chat customization')
    } finally {
      setSaving(false)
    }
  }

  const tabs = [
    { id: 'branding' as Tab, label: 'Branding', icon: Palette },
    { id: 'content' as Tab, label: 'Content', icon: MessageSquare },
    { id: 'advanced' as Tab, label: 'Advanced', icon: Zap },
    { id: 'preview' as Tab, label: 'Preview', icon: Eye },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto"></div>
          <p className="mt-4 text-gray-600 text-sm">Loading chat configuration...</p>
        </div>
      </div>
    )
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Chat Customization"
      description="Customize the chat interface with your branding, tone, and messaging."
      icon={Palette}
      badge="Chat Experience"
      maxWidthClassName="max-w-[90rem]"
    >
        <div className="mb-6">
          <AgentPageTabs
            activeId={activeTab}
            onChange={(id) => setActiveTab(id as Tab)}
            items={tabs.map((tab) => {
              const Icon = tab.icon
              return { id: tab.id, label: tab.label, icon: <Icon size={18} /> }
            })}
          />
        </div>

        <AgentPagePanel className="overflow-hidden">
          {/* Tab Content */}
          <div className="p-6">
            {activeTab === 'branding' && (
              <BrandingTab formData={formData} setFormData={setFormData} />
            )}
            {activeTab === 'content' && (
              <ContentTab formData={formData} setFormData={setFormData} />
            )}
            {activeTab === 'advanced' && (
              <AdvancedTab formData={formData} setFormData={setFormData} />
            )}
            {activeTab === 'preview' && (
              <PreviewTab formData={formData} />
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-gray-200 px-6 py-4 bg-red-50 flex justify-between items-center">
            <div className="text-xs text-gray-600">
              Changes will be applied to all chat interfaces for this agent
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => router.push(`/agents/${agentName}/view`)}
                className="px-5 py-2 text-sm border border-gray-300 rounded-lg hover:bg-white hover:border-red-300 transition-colors font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={saving}
                className="px-5 py-2 text-sm bg-[#171717] text-white rounded-[1rem] hover:bg-black transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-semibold shadow-sm"
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </AgentPagePanel>
    </AgentPageShell>
  )
}

// Branding Tab Component
function BrandingTab({ formData, setFormData }: any) {
  return (
    <div className="max-w-5xl space-y-5">
      <div>
        <h3 className="text-base font-semibold text-gray-900 mb-1">
          Brand Identity
        </h3>
        <p className="text-xs text-gray-600 mb-3">
          Customize the visual appearance of your chat interface
        </p>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-2">
          Logo URL
        </label>
        <input
          type="text"
          value={formData.chat_logo_url}
          onChange={(e) => setFormData({ ...formData, chat_logo_url: e.target.value })}
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
          placeholder="https://example.com/logo.png"
        />
        <p className="mt-1 text-xs text-gray-500">
          Enter the URL of your logo image (PNG, JPG, or SVG)
        </p>
        {formData.chat_logo_url && (
          <div className="mt-2">
            <img 
              src={formData.chat_logo_url} 
              alt="Logo preview" 
              className="h-10 object-contain border border-gray-200 rounded p-2"
              onError={(e) => {
                e.currentTarget.style.display = 'none'
              }}
            />
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-2">
            Primary Color
          </label>
          <div className="flex gap-2">
            <input
              type="color"
              value={formData.chat_primary_color}
              onChange={(e) => setFormData({ ...formData, chat_primary_color: e.target.value })}
              className="h-9 w-16 rounded border border-gray-300 cursor-pointer"
            />
            <input
              type="text"
              value={formData.chat_primary_color}
              onChange={(e) => setFormData({ ...formData, chat_primary_color: e.target.value })}
              className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
              placeholder="#0d9488"
            />
          </div>
          <p className="mt-1 text-xs text-gray-500">
            Used for buttons, links, and accents
          </p>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-2">
            Background Color
          </label>
          <div className="flex gap-2">
            <input
              type="color"
              value={formData.chat_background_color}
              onChange={(e) => setFormData({ ...formData, chat_background_color: e.target.value })}
              className="h-9 w-16 rounded border border-gray-300 cursor-pointer"
            />
            <input
              type="text"
              value={formData.chat_background_color}
              onChange={(e) => setFormData({ ...formData, chat_background_color: e.target.value })}
              className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
              placeholder="#ffffff"
            />
          </div>
          <p className="mt-1 text-xs text-gray-500">
            Main background color for the chat interface
          </p>
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-2">
          Font Family
        </label>
        <select
          value={formData.chat_font_family}
          onChange={(e) => setFormData({ ...formData, chat_font_family: e.target.value })}
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
        >
          <option value="Inter">Inter (Default)</option>
          <option value="Arial">Arial</option>
          <option value="Helvetica">Helvetica</option>
          <option value="Georgia">Georgia</option>
          <option value="Times New Roman">Times New Roman</option>
          <option value="Courier New">Courier New</option>
          <option value="Verdana">Verdana</option>
          <option value="Roboto">Roboto</option>
          <option value="Open Sans">Open Sans</option>
          <option value="Lato">Lato</option>
        </select>
        <p className="mt-1 text-xs text-gray-500">
          Choose a font that matches your brand
        </p>
      </div>

      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <h4 className="text-xs font-medium text-red-900 mb-2">💡 Branding Tips</h4>
        <ul className="text-xs text-red-800 space-y-1 list-disc list-inside">
          <li>Use your brand's primary color for consistency</li>
          <li>Ensure good contrast between text and background</li>
          <li>Keep your logo simple and recognizable</li>
          <li>Test on both light and dark backgrounds</li>
        </ul>
      </div>
    </div>
  )
}

// Content Tab Component
function ContentTab({ formData, setFormData }: any) {
  return (
    <div className="max-w-5xl space-y-5">
      <div>
        <h3 className="text-base font-semibold text-gray-900 mb-1">
          Chat Content
        </h3>
        <p className="text-xs text-gray-600 mb-3">
          Customize the text and messaging in your chat interface
        </p>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-2">
          Chat Title
        </label>
        <input
          type="text"
          value={formData.chat_title}
          onChange={(e) => setFormData({ ...formData, chat_title: e.target.value })}
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
          placeholder="Chat with AI Assistant"
        />
        <p className="mt-1 text-xs text-gray-500">
          Displayed at the top of the chat interface
        </p>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-2">
          Welcome Message
        </label>
        <textarea
          value={formData.chat_welcome_message}
          onChange={(e) => setFormData({ ...formData, chat_welcome_message: e.target.value })}
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
          rows={4}
          placeholder="Hello! I'm here to help you. How can I assist you today?"
        />
        <p className="mt-1 text-xs text-gray-500">
          First message shown to users when they start a conversation
        </p>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-2">
          Input Placeholder
        </label>
        <input
          type="text"
          value={formData.chat_placeholder}
          onChange={(e) => setFormData({ ...formData, chat_placeholder: e.target.value })}
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
          placeholder="Type your message..."
        />
        <p className="mt-1 text-xs text-gray-500">
          Placeholder text in the message input field
        </p>
      </div>

      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <h4 className="text-xs font-medium text-red-900 mb-2">✍️ Content Tips</h4>
        <ul className="text-xs text-red-800 space-y-1 list-disc list-inside">
          <li>Keep your welcome message friendly and concise</li>
          <li>Clearly state what your agent can help with</li>
          <li>Use action-oriented placeholder text</li>
          <li>Match your brand's tone and voice</li>
        </ul>
      </div>
    </div>
  )
}

// Preview Tab Component
function PreviewTab({ formData }: any) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-semibold text-gray-900 mb-1">
          Live Preview
        </h3>
        <p className="text-xs text-gray-600 mb-3">
          See how your chat interface will look with the current settings
        </p>
      </div>

      <div 
        className="border-2 border-gray-200 rounded-lg p-5"
        style={{ 
          backgroundColor: formData.chat_background_color,
          fontFamily: formData.chat_font_family 
        }}
      >
        {/* Header */}
        <div className="flex items-center gap-3 mb-5 pb-3 border-b border-gray-200">
          {formData.chat_logo_url && (
            <img 
              src={formData.chat_logo_url} 
              alt="Logo" 
              className="h-7 object-contain"
            />
          )}
          <h2 className="text-lg font-semibold" style={{ color: formData.chat_primary_color }}>
            {formData.chat_title || 'Chat with AI Assistant'}
          </h2>
        </div>

        {/* Welcome Message */}
        <div className="mb-5">
          <div className="bg-gray-100 rounded-lg p-3 max-w-md">
            <p className="text-gray-800 text-sm">
              {formData.chat_welcome_message || 'Hello! How can I help you today?'}
            </p>
          </div>
        </div>

        {/* Input Field */}
        <div className="flex gap-2">
          <input
            type="text"
            placeholder={formData.chat_placeholder || 'Type your message...'}
            className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg"
            disabled
          />
          <button
            className="px-5 py-2 text-sm rounded-lg text-white font-medium"
            style={{ backgroundColor: formData.chat_primary_color }}
            disabled
          >
            Send
          </button>
        </div>
      </div>

      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <h4 className="text-xs font-medium text-red-900 mb-2">👁️ Preview Note</h4>
        <p className="text-xs text-red-800">
          This is a simplified preview. The actual chat interface will include additional features like message history, typing indicators, and more.
        </p>
      </div>
    </div>
  )
}

// Advanced Tab Component
function AdvancedTab({ formData, setFormData }: any) {
  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h3 className="text-base font-semibold text-gray-900 mb-1">Advanced Settings</h3>
        <p className="text-xs text-gray-600 mb-4">
          Fine-tune the technical behaviour of your chat interface.
        </p>
      </div>

      {/* Chat Transport */}
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-2">
          Chat Transport
        </label>
        <div className="space-y-2">
          {([
            {
              value: 'sse',
              label: 'Server-Sent Events (SSE)',
              description: 'Default. Each message opens a new HTTP stream. Works everywhere, no extra setup.',
            },
            {
              value: 'websocket',
              label: 'WebSocket',
              description: 'Persistent connection. Saves ~20–50 ms per message after the first by reusing the same socket. Recommended for high-frequency or latency-sensitive chats.',
            },
          ] as const).map(({ value, label, description }) => (
            <label
              key={value}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                formData.chat_transport === value
                  ? 'border-red-500 bg-red-50'
                  : 'border-gray-200 hover:border-gray-300 bg-white'
              }`}
            >
              <input
                type="radio"
                name="chat_transport"
                value={value}
                checked={formData.chat_transport === value}
                onChange={() => setFormData({ ...formData, chat_transport: value })}
                className="mt-0.5 accent-red-600"
              />
              <div>
                <p className={`text-sm font-medium ${formData.chat_transport === value ? 'text-red-700' : 'text-gray-800'}`}>
                  {label}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">{description}</p>
              </div>
            </label>
          ))}
        </div>
        <p className="mt-2 text-xs text-gray-500">
          Changes take effect the next time a user loads the chat page.
        </p>
      </div>
    </div>
  )
}
