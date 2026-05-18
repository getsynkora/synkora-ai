'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  CheckCircle2,
  CircleAlert,
  CreditCard,
  Layers3,
  Send,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { integrationsApi } from '@/lib/api/integrations'
import { usePermissions } from '@/hooks/usePermissions'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

const PAYMENT_PROVIDERS = [
  { value: 'stripe', label: 'Stripe', description: 'Accept payments with Stripe' },
  { value: 'paddle', label: 'Paddle', description: 'Accept payments with Paddle (Merchant of Record)' },
  { value: 'paypal', label: 'PayPal', description: 'Accept payments with PayPal (Coming Soon)', disabled: true },
  { value: 'square', label: 'Square', description: 'Accept payments with Square (Coming Soon)', disabled: true },
]

const labelClassName = 'mb-2 block text-sm font-semibold text-[#2b241d]'
const helperClassName = 'mt-2 text-xs leading-5 text-[#75695f]'
const inputClassName =
  'w-full rounded-[1.15rem] border border-[#ddd1bf] bg-white px-4 py-3 text-sm text-[#171717] placeholder:text-[#9a8f84] transition focus:border-[#2d8b69] focus:outline-none focus:ring-4 focus:ring-[#7de5c1]/20'
const selectClassName =
  'w-full rounded-[1.15rem] border border-[#ddd1bf] bg-white px-4 py-3 text-sm text-[#171717] transition focus:border-[#2d8b69] focus:outline-none focus:ring-4 focus:ring-[#7de5c1]/20'
const textareaClassName =
  'w-full rounded-[1.15rem] border border-[#ddd1bf] bg-white px-4 py-3 text-sm text-[#171717] placeholder:text-[#9a8f84] transition focus:border-[#2d8b69] focus:outline-none focus:ring-4 focus:ring-[#7de5c1]/20'
const checkboxClassName =
  'mt-0.5 h-4 w-4 rounded border-[#cdbda7] text-[#171717] focus:ring-4 focus:ring-[#7de5c1]/20'
const secondaryButtonClassName =
  'inline-flex items-center justify-center gap-2 rounded-[1rem] border border-[#d8cab8] bg-white px-4 py-3 text-sm font-semibold text-[#3c342d] transition hover:border-[#c6b39c] hover:bg-[#f7f1e7] disabled:cursor-not-allowed disabled:opacity-50'
const primaryButtonClassName =
  'inline-flex items-center justify-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-50'

export default function CreatePaymentIntegrationPage() {
  const router = useRouter()
  const { hasPermission } = usePermissions()
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isPlatformOwner = hasPermission('platform', 'create')

  const [provider, setProvider] = useState('stripe')
  const [secretKey, setSecretKey] = useState('')
  const [publishableKey, setPublishableKey] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [currency, setCurrency] = useState('usd')
  const [captureMethod, setCaptureMethod] = useState('automatic')

  const [paddleApiKey, setPaddleApiKey] = useState('')
  const [paddleClientToken, setPaddleClientToken] = useState('')
  const [paddleWebhookSecret, setPaddleWebhookSecret] = useState('')
  const [paddleEnvironment, setPaddleEnvironment] = useState('sandbox')
  const [paddleCreditsProductId, setPaddleCreditsProductId] = useState('')

  const [description, setDescription] = useState('')
  const [isActive, setIsActive] = useState(false)
  const [isPlatformConfig, setIsPlatformConfig] = useState(true)

  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)

    try {
      let configData: any = { version: '1.0' }

      if (provider === 'stripe') {
        configData = {
          version: '1.0',
          credentials: {
            secret_key: secretKey,
            publishable_key: publishableKey,
            webhook_secret: webhookSecret || undefined,
          },
          settings: {
            currency,
            capture_method: captureMethod,
          },
        }
      } else if (provider === 'paddle') {
        configData = {
          version: '1.0',
          credentials: {
            api_key: paddleApiKey,
            client_side_token: paddleClientToken,
            webhook_secret: paddleWebhookSecret || undefined,
          },
          settings: {
            environment: paddleEnvironment,
            credits_product_id: paddleCreditsProductId || undefined,
          },
        }
      }

      const response = await fetch('/api/integration-configs/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          integration_type: 'payment',
          provider,
          config_data: configData,
        }),
      })

      const data = await response.json()

      if (response.ok && data.success) {
        setTestResult({ success: true, message: 'Connection successful!' })
      } else {
        setTestResult({ success: false, message: data.error || 'Connection failed' })
      }
    } catch (err: any) {
      setTestResult({ success: false, message: err.message })
    } finally {
      setTesting(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      let configData: any = { version: '1.0' }

      if (provider === 'stripe') {
        configData = {
          version: '1.0',
          credentials: {
            secret_key: secretKey,
            publishable_key: publishableKey,
            webhook_secret: webhookSecret || undefined,
          },
          settings: {
            currency,
            capture_method: captureMethod,
          },
          metadata: {
            description: description || 'Stripe payment integration',
          },
        }
      } else if (provider === 'paddle') {
        configData = {
          version: '1.0',
          credentials: {
            api_key: paddleApiKey,
            client_side_token: paddleClientToken,
            webhook_secret: paddleWebhookSecret || undefined,
          },
          settings: {
            environment: paddleEnvironment,
            credits_product_id: paddleCreditsProductId || undefined,
          },
          metadata: {
            description: description || 'Paddle payment integration (Merchant of Record)',
          },
        }
      }

      await integrationsApi.createConfig({
        integration_type: 'payment',
        provider,
        config_data: configData,
        is_active: isActive,
        is_platform_config: isPlatformConfig,
      })

      router.push('/settings/integrations?tab=payment')
    } catch (err: any) {
      setError(err.message || 'Failed to create integration')
    } finally {
      setLoading(false)
    }
  }

  const isFormValid = provider === 'stripe'
    ? secretKey && publishableKey
    : provider === 'paddle'
      ? paddleApiKey && paddleClientToken
      : false

  const currentProvider = PAYMENT_PROVIDERS.find((item) => item.value === provider)

  return (
    <DashboardPageShell
      title="Add Payment Integration"
      description="Configure a payment provider to accept payments across your platform."
      icon={CreditCard}
      badge="Settings"
      maxWidthClassName="max-w-5xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Settings', href: '/settings/profile' },
        { label: 'Integrations', href: '/settings/integrations' },
        { label: 'Payment', href: '/settings/integrations?tab=payment' },
        { label: 'Create' },
      ]}
      stats={[
        { label: 'Provider', value: currentProvider?.label || 'Payment' },
        { label: 'Scope', value: isPlatformOwner && isPlatformConfig ? 'Platform' : 'Workspace' },
      ]}
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {error ? <ErrorAlert message={error} /> : null}

        {testResult ? (
          <DashboardPagePanel className="p-4">
            <div
              className={`flex items-start gap-3 rounded-[1.25rem] border px-4 py-3 ${
                testResult.success
                  ? 'border-[#7de5c1]/45 bg-[#7de5c1]/14 text-[#1c5c45]'
                  : 'border-[#efb7b1] bg-[#fff1ef] text-[#9f3d33]'
              }`}
            >
              {testResult.success ? (
                <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0" />
              ) : (
                <CircleAlert className="mt-0.5 h-5 w-5 flex-shrink-0" />
              )}
              <div className="text-sm font-medium">{testResult.message}</div>
            </div>
          </DashboardPagePanel>
        ) : null}

        <DashboardPagePanel className="p-6 md:p-7">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(260px,0.8fr)]">
            <div>
              <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-[#9a7a5e]">
                <Sparkles className="h-3.5 w-3.5" />
                Provider
              </div>
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-[#171717]">
                Choose your payment provider
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#6f655c]">
                Select the provider, then add the credentials and settings required for payment flows.
              </p>

              <div className="mt-5">
                <label className={labelClassName}>Payment Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className={selectClassName}
                  required
                >
                  {PAYMENT_PROVIDERS.map((prov) => (
                    <option key={prov.value} value={prov.value} disabled={prov.disabled}>
                      {prov.label} - {prov.description}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="rounded-[1.7rem] border border-[#e6d8c6] bg-[#f7f1e7] p-5">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-white p-3 shadow-[0_18px_38px_-30px_rgba(70,42,17,0.35)]">
                  <CreditCard className="h-5 w-5 text-[#171717]" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-[#171717]">{currentProvider?.label}</p>
                  <p className="text-xs text-[#75695f]">{currentProvider?.description}</p>
                </div>
              </div>

              <div className="mt-5 space-y-3 text-sm text-[#51473e]">
                <div className="rounded-[1.15rem] border border-white/80 bg-white/75 px-4 py-3">
                  Test the configuration before saving to confirm credentials and settings.
                </div>
                <div className="rounded-[1.15rem] border border-white/80 bg-white/75 px-4 py-3">
                  Keep inactive while reviewing, or activate it immediately after validation.
                </div>
              </div>
            </div>
          </div>
        </DashboardPagePanel>

        {provider === 'stripe' ? (
          <>
            <DashboardPagePanel className="p-6 md:p-7">
              <div className="mb-5 flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#eef8f3] p-3">
                  <ShieldCheck className="h-5 w-5 text-[#2d8b69]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[#171717]">Stripe credentials</h2>
                  <p className="text-sm text-[#6f655c]">
                    Add the keys required to connect Stripe and verify webhook requests.
                  </p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className={labelClassName}>Secret Key *</label>
                  <input
                    type="password"
                    value={secretKey}
                    onChange={(e) => setSecretKey(e.target.value)}
                    placeholder="sk_test_..."
                    className={inputClassName}
                    required
                  />
                  <p className={helperClassName}>Your Stripe secret key (starts with sk_).</p>
                </div>

                <div>
                  <label className={labelClassName}>Publishable Key *</label>
                  <input
                    type="text"
                    value={publishableKey}
                    onChange={(e) => setPublishableKey(e.target.value)}
                    placeholder="pk_test_..."
                    className={inputClassName}
                    required
                  />
                  <p className={helperClassName}>Your Stripe publishable key (starts with pk_).</p>
                </div>
              </div>

              <div className="mt-4">
                <label className={labelClassName}>Webhook Secret (Optional)</label>
                <input
                  type="password"
                  value={webhookSecret}
                  onChange={(e) => setWebhookSecret(e.target.value)}
                  placeholder="whsec_..."
                  className={inputClassName}
                />
                <p className={helperClassName}>Webhook signing secret for verifying webhook events.</p>
              </div>
            </DashboardPagePanel>

            <DashboardPagePanel className="p-6 md:p-7">
              <div className="mb-5 flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#fff4e5] p-3">
                  <Layers3 className="h-5 w-5 text-[#9b6333]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[#171717]">Payment settings</h2>
                  <p className="text-sm text-[#6f655c]">
                    Configure the default currency, capture behavior, and internal description.
                  </p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className={labelClassName}>Default Currency</label>
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className={selectClassName}
                  >
                    <option value="usd">USD - US Dollar</option>
                    <option value="eur">EUR - Euro</option>
                    <option value="gbp">GBP - British Pound</option>
                    <option value="cad">CAD - Canadian Dollar</option>
                    <option value="aud">AUD - Australian Dollar</option>
                  </select>
                </div>

                <div>
                  <label className={labelClassName}>Capture Method</label>
                  <select
                    value={captureMethod}
                    onChange={(e) => setCaptureMethod(e.target.value)}
                    className={selectClassName}
                  >
                    <option value="automatic">Automatic - Capture immediately</option>
                    <option value="manual">Manual - Capture later</option>
                  </select>
                </div>
              </div>

              <div className="mt-4">
                <label className={labelClassName}>Description (Optional)</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g., Production Stripe account"
                  rows={3}
                  className={textareaClassName}
                />
              </div>
            </DashboardPagePanel>
          </>
        ) : null}

        {provider === 'paddle' ? (
          <>
            <DashboardPagePanel className="p-6 md:p-7">
              <div className="rounded-[1.35rem] border border-[#cfe2ff] bg-[#eef5ff] px-4 py-4 text-sm leading-6 text-[#32507a]">
                <span className="font-semibold text-[#244264]">Paddle as Merchant of Record:</span>{' '}
                Paddle handles VAT and tax compliance, invoicing, and global payment processing for regulated markets.
              </div>

              <div className="mt-5 flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#eef8f3] p-3">
                  <ShieldCheck className="h-5 w-5 text-[#2d8b69]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[#171717]">Paddle credentials</h2>
                  <p className="text-sm text-[#6f655c]">
                    Add the API access and client token needed for Paddle checkout and webhooks.
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div>
                  <label className={labelClassName}>API Key *</label>
                  <input
                    type="password"
                    value={paddleApiKey}
                    onChange={(e) => setPaddleApiKey(e.target.value)}
                    placeholder="pdl_..."
                    className={inputClassName}
                    required
                  />
                  <p className={helperClassName}>Your Paddle API key from Developer Tools.</p>
                </div>

                <div>
                  <label className={labelClassName}>Client-Side Token *</label>
                  <input
                    type="text"
                    value={paddleClientToken}
                    onChange={(e) => setPaddleClientToken(e.target.value)}
                    placeholder="test_..."
                    className={inputClassName}
                    required
                  />
                  <p className={helperClassName}>
                    Client-side token for Paddle.js initialization.
                  </p>
                </div>
              </div>

              <div className="mt-4">
                <label className={labelClassName}>Webhook Secret (Optional)</label>
                <input
                  type="password"
                  value={paddleWebhookSecret}
                  onChange={(e) => setPaddleWebhookSecret(e.target.value)}
                  placeholder="pdl_ntfset_..."
                  className={inputClassName}
                />
                <p className={helperClassName}>Webhook secret key for verifying notifications.</p>
              </div>
            </DashboardPagePanel>

            <DashboardPagePanel className="p-6 md:p-7">
              <div className="mb-5 flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#fff4e5] p-3">
                  <Layers3 className="h-5 w-5 text-[#9b6333]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[#171717]">Paddle settings</h2>
                  <p className="text-sm text-[#6f655c]">
                    Choose the environment and optionally link a product for credit top-ups.
                  </p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className={labelClassName}>Environment *</label>
                  <select
                    value={paddleEnvironment}
                    onChange={(e) => setPaddleEnvironment(e.target.value)}
                    className={selectClassName}
                    required
                  >
                    <option value="sandbox">Sandbox - For testing</option>
                    <option value="production">Production - Live payments</option>
                  </select>
                </div>

                <div>
                  <label className={labelClassName}>Credits Product ID (Optional)</label>
                  <input
                    type="text"
                    value={paddleCreditsProductId}
                    onChange={(e) => setPaddleCreditsProductId(e.target.value)}
                    placeholder="pro_..."
                    className={inputClassName}
                  />
                  <p className={helperClassName}>Product ID used for credit top-ups.</p>
                </div>
              </div>

              <div className="mt-4">
                <label className={labelClassName}>Description (Optional)</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g., Production Paddle account"
                  rows={3}
                  className={textareaClassName}
                />
              </div>

              <div className="mt-4 rounded-[1.25rem] border border-[#e6d8c6] bg-[#f7f1e7] px-4 py-4">
                <p className="text-sm font-semibold text-[#3b322a]">Webhook URL</p>
                <code className="mt-2 block rounded-[0.95rem] bg-white px-3 py-2 text-xs text-[#5c5148]">
                  https://your-domain.com/api/v1/billing/webhook/paddle
                </code>
              </div>
            </DashboardPagePanel>
          </>
        ) : null}

        {isPlatformOwner ? (
          <DashboardPagePanel className="p-6">
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={isPlatformConfig}
                onChange={(e) => setIsPlatformConfig(e.target.checked)}
                className={checkboxClassName}
              />
              <div>
                <div className="text-sm font-semibold text-[#171717]">Platform configuration</div>
                <p className="mt-1 text-sm leading-6 text-[#6f655c]">
                  Enable this to make the configuration available platform-wide. Only Platform Owners can create platform configurations.
                </p>
              </div>
            </label>
          </DashboardPagePanel>
        ) : null}

        <DashboardPagePanel className="p-6">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className={checkboxClassName}
            />
            <div>
              <div className="text-sm font-semibold text-[#171717]">Activate integration</div>
              <p className="mt-1 text-sm leading-6 text-[#6f655c]">
                Make this the active payment provider after it is saved.
              </p>
            </div>
          </label>
        </DashboardPagePanel>

        <DashboardPagePanel className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={!isFormValid || testing}
              className={secondaryButtonClassName}
            >
              {testing ? (
                <>
                  <LoadingSpinner size="sm" />
                  Testing...
                </>
              ) : (
                'Test Connection'
              )}
            </button>

            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => router.back()}
                disabled={loading}
                className={secondaryButtonClassName}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!isFormValid || loading}
                className={primaryButtonClassName}
              >
                {loading ? (
                  <>
                    <LoadingSpinner size="sm" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" />
                    Create Integration
                  </>
                )}
              </button>
            </div>
          </div>
        </DashboardPagePanel>
      </form>
    </DashboardPageShell>
  )
}
