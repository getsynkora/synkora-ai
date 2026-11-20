'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Save, TestTube, Trash2, CheckCircle, XCircle } from 'lucide-react'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import toast from 'react-hot-toast'
import { integrationsApi } from '@/lib/api/integrations'

export default function EditPaymentIntegrationPage() {
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

  // Stripe fields
  const [stripeSecretKey, setStripeSecretKey] = useState('')
  const [stripePublishableKey, setStripePublishableKey] = useState('')
  const [stripeWebhookSecret, setStripeWebhookSecret] = useState('')
  const [currency, setCurrency] = useState('usd')

  // Paddle fields
  const [paddleApiKey, setPaddleApiKey] = useState('')
  const [paddleClientToken, setPaddleClientToken] = useState('')
  const [paddleWebhookSecret, setPaddleWebhookSecret] = useState('')
  const [paddleEnvironment, setPaddleEnvironment] = useState('sandbox')
  const [paddleCreditsProductId, setPaddleCreditsProductId] = useState('')

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

      // Load Stripe fields
      if (data.provider === 'stripe') {
        setStripeSecretKey(data.config_data.credentials?.secret_key || '')
        setStripePublishableKey(data.config_data.credentials?.publishable_key || '')
        setStripeWebhookSecret(data.config_data.credentials?.webhook_secret || '')
        setCurrency(data.config_data.settings?.currency || 'usd')
      }

      // Load Paddle fields
      if (data.provider === 'paddle') {
        setPaddleApiKey(data.config_data.credentials?.api_key || '')
        setPaddleClientToken(data.config_data.credentials?.client_side_token || '')
        setPaddleWebhookSecret(data.config_data.credentials?.webhook_secret || '')
        setPaddleEnvironment(data.config_data.settings?.environment || 'sandbox')
        setPaddleCreditsProductId(data.config_data.settings?.credits_product_id || '')
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

      if (provider === 'stripe') {
        configData.credentials = {
          secret_key: stripeSecretKey,
          publishable_key: stripePublishableKey,
          webhook_secret: stripeWebhookSecret,
        }
        configData.settings = {
          currency: currency,
        }
      } else if (provider === 'paddle') {
        configData.credentials = {
          api_key: paddleApiKey,
          client_side_token: paddleClientToken,
          webhook_secret: paddleWebhookSecret,
        }
        configData.settings = {
          environment: paddleEnvironment,
          credits_product_id: paddleCreditsProductId || undefined,
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
        <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Edit Payment Integration</h1>
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
            className="w-4 h-4 text-leaf border-taupe rounded focus:ring-ink"
          />
          <label htmlFor="is_active" className="text-sm text-ink-soft">
            Active
          </label>
        </div>

        {/* Stripe Configuration */}
        {provider === 'stripe' && (
          <>
            <div className="border-t pt-6">
              <h3 className="text-lg font-semibold text-ink mb-4">Stripe Configuration</h3>
              
              <div>
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  Secret Key *
                </label>
                <input
                  type="password"
                  value={stripeSecretKey}
                  onChange={(e) => setStripeSecretKey(e.target.value)}
                  placeholder="sk_test_••••••••"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
                  required
                />
                <p className="text-xs text-ink-mute mt-1">
                  Your Stripe secret key (starts with sk_test_ or sk_live_)
                </p>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  Publishable Key *
                </label>
                <input
                  type="text"
                  value={stripePublishableKey}
                  onChange={(e) => setStripePublishableKey(e.target.value)}
                  placeholder="pk_test_••••••••"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
                  required
                />
                <p className="text-xs text-ink-mute mt-1">
                  Your Stripe publishable key (starts with pk_test_ or pk_live_)
                </p>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  Webhook Secret
                </label>
                <input
                  type="password"
                  value={stripeWebhookSecret}
                  onChange={(e) => setStripeWebhookSecret(e.target.value)}
                  placeholder="whsec_••••••••"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
                />
                <p className="text-xs text-ink-mute mt-1">
                  Your Stripe webhook signing secret (optional, for webhook verification)
                </p>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  Currency *
                </label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
                  required
                >
                  <option value="usd">USD - US Dollar</option>
                  <option value="eur">EUR - Euro</option>
                  <option value="gbp">GBP - British Pound</option>
                  <option value="cad">CAD - Canadian Dollar</option>
                  <option value="aud">AUD - Australian Dollar</option>
                  <option value="jpy">JPY - Japanese Yen</option>
                  <option value="inr">INR - Indian Rupee</option>
                  <option value="sgd">SGD - Singapore Dollar</option>
                </select>
              </div>
            </div>
          </>
        )}

        {/* Paddle Configuration */}
        {provider === 'paddle' && (
          <>
            <div className="border-t pt-6">
              <div className="bg-sky-wash border border-sky-wash rounded-lg p-3 mb-4">
                <p className="text-sm text-azure">
                  <strong>Paddle as Merchant of Record:</strong> Paddle handles all VAT/tax compliance,
                  invoicing, and payment processing globally.
                </p>
              </div>

              <h3 className="text-lg font-semibold text-ink mb-4">Paddle Configuration</h3>

              <div>
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  API Key *
                </label>
                <input
                  type="password"
                  value={paddleApiKey}
                  onChange={(e) => setPaddleApiKey(e.target.value)}
                  placeholder="pdl_••••••••"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
                  required
                />
                <p className="text-xs text-ink-mute mt-1">
                  Your Paddle API key from the Developer Tools section
                </p>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  Client-Side Token *
                </label>
                <input
                  type="text"
                  value={paddleClientToken}
                  onChange={(e) => setPaddleClientToken(e.target.value)}
                  placeholder="test_••••••••"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
                  required
                />
                <p className="text-xs text-ink-mute mt-1">
                  Client-side token for Paddle.js initialization
                </p>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-ink-soft mb-2">
                  Webhook Secret
                </label>
                <input
                  type="password"
                  value={paddleWebhookSecret}
                  onChange={(e) => setPaddleWebhookSecret(e.target.value)}
                  placeholder="pdl_ntfset_••••••••"
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
                />
                <p className="text-xs text-ink-mute mt-1">
                  Webhook secret key for verifying webhook notifications
                </p>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-ink-soft mb-2">
                    Environment *
                  </label>
                  <select
                    value={paddleEnvironment}
                    onChange={(e) => setPaddleEnvironment(e.target.value)}
                    className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
                    required
                  >
                    <option value="sandbox">Sandbox - For testing</option>
                    <option value="production">Production - Live payments</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-ink-soft mb-2">
                    Credits Product ID
                  </label>
                  <input
                    type="text"
                    value={paddleCreditsProductId}
                    onChange={(e) => setPaddleCreditsProductId(e.target.value)}
                    placeholder="pro_••••••••"
                    className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
                  />
                  <p className="text-xs text-ink-mute mt-1">
                    Product ID for credit top-ups
                  </p>
                </div>
              </div>

              <div className="mt-4 p-3 bg-cream rounded-lg border border-line">
                <p className="text-sm text-ink-soft">
                  <strong>Webhook URL:</strong> Configure this URL in your Paddle dashboard:
                </p>
                <code className="text-sm text-ink bg-sand px-2 py-1 rounded mt-1 block">
                  https://your-domain.com/api/v1/billing/webhook/paddle
                </code>
              </div>
            </div>
          </>
        )}

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
              disabled={saving || isActive}
              className="flex items-center gap-2 px-4 py-2 border border-blush text-danger rounded-lg hover:bg-blush-wash transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title={isActive ? "Deactivate the integration before deleting" : "Delete integration"}
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
              className="flex items-center gap-2 px-6 py-2 bg-ink text-white rounded-lg hover:from-danger hover:to-danger transition-[color,background-color,border-color,box-shadow,opacity,transform] disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
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