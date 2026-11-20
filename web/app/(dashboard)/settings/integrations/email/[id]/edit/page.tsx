'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Save, TestTube, Trash2, CheckCircle, XCircle } from 'lucide-react'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import toast from 'react-hot-toast'
import { integrationsApi } from '@/lib/api/integrations'

export default function EditIntegrationPage() {
  const router = useRouter()
  const params = useParams()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  
  const [integrationType, setIntegrationType] = useState('')
  const [provider, setProvider] = useState('')
  const [isActive, setIsActive] = useState(false)
  
  // SMTP fields
  const [smtpHost, setSmtpHost] = useState('')
  const [smtpPort, setSmtpPort] = useState('587')
  const [smtpUsername, setSmtpUsername] = useState('')
  const [smtpPassword, setSmtpPassword] = useState('')
  const [smtpUseTls, setSmtpUseTls] = useState(true)
  const [smtpUseSsl, setSmtpUseSsl] = useState(false)
  const [fromEmail, setFromEmail] = useState('')
  const [fromName, setFromName] = useState('')
  
  // SendGrid fields
  const [sendgridApiKey, setSendgridApiKey] = useState('')
  const [replyTo, setReplyTo] = useState('')
  
  // Mailgun fields
  const [mailgunApiKey, setMailgunApiKey] = useState('')
  const [mailgunDomain, setMailgunDomain] = useState('')

  // Brevo fields
  const [brevoApiKey, setBrevoApiKey] = useState('')

  useEffect(() => {
    loadIntegration()
  }, [params.id])

  const loadIntegration = async () => {
    try {
      setLoading(true)
      const data = await integrationsApi.getConfig(params.id as string)
      
      setIntegrationType(data.integration_type)
      setProvider(data.provider)
      setIsActive(data.is_active)
      
      // Load SMTP fields
      if (data.provider === 'smtp') {
        setSmtpHost(data.config_data.settings?.host || '')
        setSmtpPort(data.config_data.settings?.port?.toString() || '587')
        setSmtpUsername(data.config_data.credentials?.username || '')
        setSmtpPassword(data.config_data.credentials?.password || '')
        setSmtpUseTls(data.config_data.settings?.use_tls ?? true)
        setSmtpUseSsl(data.config_data.settings?.use_ssl ?? false)
        setFromEmail(data.config_data.settings?.from_email || '')
        setFromName(data.config_data.settings?.from_name || '')
      }
      
      // Load SendGrid fields
      if (data.provider === 'sendgrid') {
        setSendgridApiKey(data.config_data.credentials?.api_key || '')
        setFromEmail(data.config_data.settings?.from_email || '')
        setFromName(data.config_data.settings?.from_name || '')
        setReplyTo(data.config_data.settings?.reply_to || '')
      }
      
      // Load Mailgun fields
      if (data.provider === 'mailgun') {
        setMailgunApiKey(data.config_data.credentials?.api_key || '')
        setMailgunDomain(data.config_data.credentials?.domain || data.config_data.settings?.domain || '')
        setFromEmail(data.config_data.settings?.from_email || '')
        setFromName(data.config_data.settings?.from_name || '')
        setReplyTo(data.config_data.settings?.reply_to || '')
      }

      // Load Brevo fields
      if (data.provider === 'brevo') {
        setBrevoApiKey(data.config_data.credentials?.api_key || '')
        setFromEmail(data.config_data.settings?.from_email || '')
        setFromName(data.config_data.settings?.from_name || '')
        setReplyTo(data.config_data.settings?.reply_to || '')
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load integration')
      toast.error('Failed to load integration')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)

    try {
      const configData: any = {
        version: '1.0',
        credentials: {},
        settings: {},
      }

      if (provider === 'smtp') {
        configData.credentials = {
          username: smtpUsername,
          password: smtpPassword,
        }
        configData.settings = {
          host: smtpHost,
          port: parseInt(smtpPort),
          use_tls: smtpUseTls,
          use_ssl: smtpUseSsl,
          from_email: fromEmail,
          from_name: fromName,
        }
      } else if (provider === 'sendgrid') {
        configData.credentials = {
          api_key: sendgridApiKey,
        }
        configData.settings = {
          from_email: fromEmail,
          from_name: fromName,
          reply_to: replyTo,
        }
      } else if (provider === 'mailgun') {
        configData.credentials = {
          api_key: mailgunApiKey,
          domain: mailgunDomain,
        }
        configData.settings = {
          from_email: fromEmail,
          from_name: fromName,
          reply_to: replyTo,
        }
      } else if (provider === 'brevo') {
        configData.credentials = {
          api_key: brevoApiKey,
        }
        configData.settings = {
          from_email: fromEmail,
          from_name: fromName,
          reply_to: replyTo,
        }
      }

      await integrationsApi.updateConfig(params.id as string, {
        config_data: configData,
        is_active: isActive,
      })

      toast.success('Integration updated successfully')
      router.push('/settings/integrations')
    } catch (err: any) {
      setError(err.message || 'Failed to update integration')
      toast.error(err.message || 'Failed to update integration')
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await integrationsApi.testConnection(params.id as string)
      setTestResult(result)
      if (result.success) {
        toast.success('Connection test successful!')
      } else {
        toast.error(`Connection test failed: ${result.message}`)
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to test connection')
    } finally {
      setTesting(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this integration?')) {
      return
    }
    
    try {
      await integrationsApi.deleteConfig(params.id as string)
      toast.success('Integration deleted successfully')
      router.push('/settings/integrations')
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete integration')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-ink-soft hover:text-ink mb-4"
        >
          <ArrowLeft size={20} />
          Back
        </button>
        <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Edit Integration</h1>
        <p className="text-ink-soft mt-1">
          Update your {provider} configuration
        </p>
      </div>

      {error && (
        <div className="mb-6">
          <ErrorAlert message={error} />
        </div>
      )}

      {testResult && (
        <div className={`mb-6 p-4 rounded-lg border ${testResult.success ? 'bg-leaf-wash border-mint' : 'bg-blush-wash border-blush'}`}>
          <div className="flex items-center gap-2">
            {testResult.success ? (
              <CheckCircle className="text-leaf" size={20} />
            ) : (
              <XCircle className="text-leaf" size={20} />
            )}
            <span className={testResult.success ? 'text-forest' : 'text-wine'}>
              {testResult.message}
            </span>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-line shadow-sm p-6 space-y-6">
        {/* Basic Info */}
        <div>
          <label className="block text-sm font-medium text-ink-soft mb-2">
            Integration Type
          </label>
          <input
            type="text"
            value={integrationType}
            disabled
            className="w-full px-4 py-2 border border-taupe rounded-lg bg-sand"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-ink-soft mb-2">
            Provider
          </label>
          <input
            type="text"
            value={provider}
            disabled
            className="w-full px-4 py-2 border border-taupe rounded-lg bg-sand"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_active"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 text-leaf border-taupe rounded focus:ring-leaf"
          />
          <label htmlFor="is_active" className="text-sm text-ink-soft">
            Active
          </label>
        </div>

        {/* SMTP Configuration */}
        {provider === 'smtp' && (
          <>
            <div className="border-t pt-6">
              <h3 className="text-lg font-semibold text-ink mb-4">SMTP Configuration</h3>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-ink-soft mb-2">
                    SMTP Host *
                  </label>
                  <input
                    type="text"
                    value={smtpHost}
                    onChange={(e) => setSmtpHost(e.target.value)}
                    placeholder="smtp.gmail.com"
                    className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-ink-soft mb-2">
                    SMTP Port *
                  </label>
                  <input
                    type="number"
                    value={smtpPort}
                    onChange={(e) => setSmtpPort(e.target.value)}
                    placeholder="587"
                    className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <label className="block text-sm font-medium text-ink-soft mb-2">
                    Username *
                  </label>
                  <input
                    type="text"
                    value={smtpUsername}
                    onChange={(e) => setSmtpUsername(e.target.value)}
                    placeholder="your-email@gmail.com"
                    className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-ink-soft mb-2">
                    Password *
                  </label>
                  <input
                    type="password"
                    value={smtpPassword}
                    onChange={(e) => setSmtpPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                    required
                  />
                </div>
              </div>

              <div className="flex gap-6 mt-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={smtpUseTls}
                    onChange={(e) => setSmtpUseTls(e.target.checked)}
                    className="w-4 h-4 text-leaf border-taupe rounded focus:ring-leaf"
                  />
                  <span className="text-sm text-ink-soft">Use TLS</span>
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={smtpUseSsl}
                    onChange={(e) => setSmtpUseSsl(e.target.checked)}
                    className="w-4 h-4 text-leaf border-taupe rounded focus:ring-leaf"
                  />
                  <span className="text-sm text-ink-soft">Use SSL</span>
                </label>
              </div>
            </div>
          </>
        )}

        {/* SendGrid Configuration */}
        {provider === 'sendgrid' && (
          <>
            <div className="border-t pt-6">
              <h3 className="text-lg font-semibold text-ink mb-4">SendGrid Configuration</h3>
              
              <div>
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  API Key *
                </label>
                <input
                  type="password"
                  value={sendgridApiKey}
                  onChange={(e) => setSendgridApiKey(e.target.value)}
                  placeholder="SG.••••••••"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                  required
                />
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  Reply To
                </label>
                <input
                  type="email"
                  value={replyTo}
                  onChange={(e) => setReplyTo(e.target.value)}
                  placeholder="support@example.com"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                />
              </div>
            </div>
          </>
        )}

        {/* Mailgun Configuration */}
        {provider === 'mailgun' && (
          <>
            <div className="border-t pt-6">
              <h3 className="text-lg font-semibold text-ink mb-4">Mailgun Configuration</h3>
              
              <div>
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  API Key *
                </label>
                <input
                  type="password"
                  value={mailgunApiKey}
                  onChange={(e) => setMailgunApiKey(e.target.value)}
                  placeholder="key-••••••••••••••••••••••••••••"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                  required
                />
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  Domain *
                </label>
                <input
                  type="text"
                  value={mailgunDomain}
                  onChange={(e) => setMailgunDomain(e.target.value)}
                  placeholder="mg.example.com"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                  required
                />
                <p className="text-xs text-ink-mute mt-1">
                  Your Mailgun sending domain (e.g., mg.example.com)
                </p>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  Reply To
                </label>
                <input
                  type="email"
                  value={replyTo}
                  onChange={(e) => setReplyTo(e.target.value)}
                  placeholder="support@example.com"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                />
              </div>
            </div>
          </>
        )}

        {/* Brevo Configuration */}
        {provider === 'brevo' && (
          <>
            <div className="border-t pt-6">
              <h3 className="text-lg font-semibold text-ink mb-4">Brevo Configuration</h3>

              <div>
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  API Key *
                </label>
                <input
                  type="password"
                  value={brevoApiKey}
                  onChange={(e) => setBrevoApiKey(e.target.value)}
                  placeholder="xkeysib-••••••••••••••••••••••••••••"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                  required
                />
                <p className="text-xs text-ink-mute mt-1">
                  Found in Brevo dashboard → SMTP & API → API Keys
                </p>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  Reply To
                </label>
                <input
                  type="email"
                  value={replyTo}
                  onChange={(e) => setReplyTo(e.target.value)}
                  placeholder="support@example.com"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                />
              </div>
            </div>
          </>
        )}

        {/* Common Email Settings */}
        <div className="border-t pt-6">
          <h3 className="text-lg font-semibold text-ink mb-4">Email Settings</h3>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-ink-soft mb-2">
                From Email *
              </label>
              <input
                type="email"
                value={fromEmail}
                onChange={(e) => setFromEmail(e.target.value)}
                placeholder="noreply@example.com"
                className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-ink-soft mb-2">
                From Name *
              </label>
              <input
                type="text"
                value={fromName}
                onChange={(e) => setFromName(e.target.value)}
                placeholder="My Platform"
                className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                required
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-between pt-6 border-t">
          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testing || saving}
              className="flex items-center gap-2 px-4 py-2 border border-taupe text-ink-soft rounded-lg hover:bg-cream transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {testing ? (
                <>
                  <LoadingSpinner />
                  Testing...
                </>
              ) : (
                <>
                  <TestTube size={20} />
                  Test Connection
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleDelete}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 border border-blush text-danger rounded-lg hover:bg-blush-wash transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Trash2 size={20} />
              Delete
            </button>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => router.back()}
              className="px-6 py-2 border border-taupe text-ink-soft rounded-lg hover:bg-cream transition-colors"
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-6 py-2 bg-leaf text-white rounded-lg hover:bg-forest transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? (
                <>
                  <LoadingSpinner />
                  Saving...
                </>
              ) : (
                <>
                  <Save size={20} />
                  Save Changes
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
