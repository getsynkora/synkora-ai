'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Layers3, Mail, Send, ShieldCheck, Sparkles } from 'lucide-react'
import { integrationsApi } from '@/lib/api/integrations'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

const INTEGRATION_TYPES = [
  { value: 'email', label: 'Email', icon: Mail },
]

const EMAIL_PROVIDERS = [
  { value: 'smtp', label: 'SMTP', description: 'Standard SMTP email service' },
  { value: 'sendgrid', label: 'SendGrid', description: 'SendGrid email API' },
  { value: 'mailgun', label: 'Mailgun', description: 'Mailgun email REST API' },
  { value: 'brevo', label: 'Brevo', description: 'Brevo transactional email API (recommended)' },
]

const labelClassName = 'mb-2 block text-sm font-semibold text-night'
const helperClassName = 'mt-2 text-xs leading-5 text-ink-mute'
const inputClassName =
  'w-full rounded-[1.15rem] border border-line bg-white px-4 py-3 text-sm text-ink placeholder:text-ash transition focus:border-leaf focus:outline-none focus:ring-4 focus:ring-mint/20'
const selectClassName =
  'w-full rounded-[1.15rem] border border-line bg-white px-4 py-3 text-sm text-ink transition focus:border-leaf focus:outline-none focus:ring-4 focus:ring-mint/20'
const checkboxClassName =
  'mt-0.5 h-4 w-4 rounded border-tan text-ink focus:ring-4 focus:ring-mint/20'
const secondaryButtonClassName =
  'inline-flex items-center justify-center gap-2 rounded-[1rem] border border-paper-dim bg-white px-4 py-3 text-sm font-semibold text-night transition hover:border-tan hover:bg-paper disabled:cursor-not-allowed disabled:opacity-50'
const primaryButtonClassName =
  'inline-flex items-center justify-center gap-2 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-50'

export default function CreateIntegrationPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [integrationType, setIntegrationType] = useState('email')
  const [provider, setProvider] = useState('smtp')

  const [smtpHost, setSmtpHost] = useState('')
  const [smtpPort, setSmtpPort] = useState('587')
  const [smtpUsername, setSmtpUsername] = useState('')
  const [smtpPassword, setSmtpPassword] = useState('')
  const [smtpUseTls, setSmtpUseTls] = useState(true)
  const [smtpUseSsl, setSmtpUseSsl] = useState(false)
  const [fromEmail, setFromEmail] = useState('')
  const [fromName, setFromName] = useState('')

  const [sendgridApiKey, setSendgridApiKey] = useState('')
  const [replyTo, setReplyTo] = useState('')

  const [mailgunApiKey, setMailgunApiKey] = useState('')
  const [mailgunDomain, setMailgunDomain] = useState('')

  const [brevoApiKey, setBrevoApiKey] = useState('')

  const [isPlatformConfig, setIsPlatformConfig] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
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

      await integrationsApi.createConfig({
        integration_type: integrationType,
        provider,
        config_data: configData,
        is_platform_config: isPlatformConfig,
      })

      router.push('/settings/integrations')
    } catch (err: any) {
      setError(err.message || 'Failed to create integration')
    } finally {
      setLoading(false)
    }
  }

  const currentProvider = EMAIL_PROVIDERS.find((item) => item.value === provider)

  return (
    <DashboardPageShell
      title="Add Email Integration"
      description="Configure an email delivery provider for transactional and platform messaging."
      icon={Mail}
      badge="Settings"
      maxWidthClassName="max-w-5xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Settings', href: '/settings/profile' },
        { label: 'Integrations', href: '/settings/integrations' },
        { label: 'Email', href: '/settings/integrations?tab=email' },
        { label: 'Create' },
      ]}
      stats={[
        { label: 'Provider', value: currentProvider?.label || 'Email' },
        { label: 'Scope', value: isPlatformConfig ? 'Platform' : 'Tenant fallback' },
      ]}
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {error ? <ErrorAlert message={error} /> : null}

        <DashboardPagePanel className="p-6 md:p-7">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(260px,0.8fr)]">
            <div>
              <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold text-clay">
                <Sparkles className="h-3.5 w-3.5" />
                Setup
              </div>
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-ink">
                Choose the email provider
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-mute">
                Select the provider and add the credentials needed for sending transactional email across the platform.
              </p>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div>
                  <label className={labelClassName}>Integration Type</label>
                  <select
                    value={integrationType}
                    onChange={(e) => setIntegrationType(e.target.value)}
                    className={selectClassName}
                    required
                  >
                    {INTEGRATION_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className={labelClassName}>Provider</label>
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    className={selectClassName}
                    required
                  >
                    {EMAIL_PROVIDERS.map((prov) => (
                      <option key={prov.value} value={prov.value}>
                        {prov.label} - {prov.description}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="rounded-[1.7rem] border border-line bg-paper p-5">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-white p-3 shadow-soft">
                  <Mail className="h-5 w-5 text-ink" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-ink">{currentProvider?.label}</p>
                  <p className="text-xs text-ink-mute">{currentProvider?.description}</p>
                </div>
              </div>

              <div className="mt-5 space-y-3 text-sm text-ink-soft">
                <div className="rounded-[1.15rem] border border-white/80 bg-white/75 px-4 py-3">
                  Keep sending identity details consistent so templates and notifications stay readable.
                </div>
                <div className="rounded-[1.15rem] border border-white/80 bg-white/75 px-4 py-3">
                  Platform mode makes this config available as a fallback when tenants have not configured their own provider.
                </div>
              </div>
            </div>
          </div>
        </DashboardPagePanel>

        {provider === 'smtp' ? (
          <DashboardPagePanel className="p-6 md:p-7">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-[1rem] bg-leaf-wash p-3">
                <ShieldCheck className="h-5 w-5 text-leaf" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-ink">SMTP configuration</h2>
                <p className="text-sm text-ink-mute">
                  Add the mail server address, credentials, and transport settings.
                </p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className={labelClassName}>SMTP Host *</label>
                <input
                  type="text"
                  value={smtpHost}
                  onChange={(e) => setSmtpHost(e.target.value)}
                  placeholder="smtp.gmail.com"
                  className={inputClassName}
                  required
                />
              </div>

              <div>
                <label className={labelClassName}>SMTP Port *</label>
                <input
                  type="number"
                  value={smtpPort}
                  onChange={(e) => setSmtpPort(e.target.value)}
                  placeholder="587"
                  className={inputClassName}
                  required
                />
              </div>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div>
                <label className={labelClassName}>Username *</label>
                <input
                  type="text"
                  value={smtpUsername}
                  onChange={(e) => setSmtpUsername(e.target.value)}
                  placeholder="your-email@gmail.com"
                  className={inputClassName}
                  required
                />
              </div>

              <div>
                <label className={labelClassName}>Password *</label>
                <input
                  type="password"
                  value={smtpPassword}
                  onChange={(e) => setSmtpPassword(e.target.value)}
                  placeholder="••••••••"
                  className={inputClassName}
                  required
                />
              </div>
            </div>

            <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:gap-8">
              <label className="flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={smtpUseTls}
                  onChange={(e) => setSmtpUseTls(e.target.checked)}
                  className={checkboxClassName}
                />
                <div>
                  <div className="text-sm font-semibold text-ink">Use TLS</div>
                  <p className="mt-1 text-xs leading-5 text-ink-mute">Recommended for modern SMTP providers.</p>
                </div>
              </label>

              <label className="flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={smtpUseSsl}
                  onChange={(e) => setSmtpUseSsl(e.target.checked)}
                  className={checkboxClassName}
                />
                <div>
                  <div className="text-sm font-semibold text-ink">Use SSL</div>
                  <p className="mt-1 text-xs leading-5 text-ink-mute">Enable only if your provider expects SSL transport.</p>
                </div>
              </label>
            </div>
          </DashboardPagePanel>
        ) : null}

        {provider === 'sendgrid' ? (
          <DashboardPagePanel className="p-6 md:p-7">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-[1rem] bg-leaf-wash p-3">
                <ShieldCheck className="h-5 w-5 text-leaf" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-ink">SendGrid configuration</h2>
                <p className="text-sm text-ink-mute">
                  Connect SendGrid with an API key and optional reply-to address.
                </p>
              </div>
            </div>

            <div>
              <label className={labelClassName}>API Key *</label>
              <input
                type="password"
                value={sendgridApiKey}
                onChange={(e) => setSendgridApiKey(e.target.value)}
                placeholder="SG.••••••••"
                className={inputClassName}
                required
              />
            </div>

            <div className="mt-4">
              <label className={labelClassName}>Reply To</label>
              <input
                type="email"
                value={replyTo}
                onChange={(e) => setReplyTo(e.target.value)}
                placeholder="support@example.com"
                className={inputClassName}
              />
            </div>
          </DashboardPagePanel>
        ) : null}

        {provider === 'mailgun' ? (
          <DashboardPagePanel className="p-6 md:p-7">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-[1rem] bg-leaf-wash p-3">
                <ShieldCheck className="h-5 w-5 text-leaf" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-ink">Mailgun configuration</h2>
                <p className="text-sm text-ink-mute">
                  Add the Mailgun API key, sending domain, and optional reply-to address.
                </p>
              </div>
            </div>

            <div>
              <label className={labelClassName}>API Key *</label>
              <input
                type="password"
                value={mailgunApiKey}
                onChange={(e) => setMailgunApiKey(e.target.value)}
                placeholder="key-••••••••••••••••••••••••••••"
                className={inputClassName}
                required
              />
            </div>

            <div className="mt-4">
              <label className={labelClassName}>Domain *</label>
              <input
                type="text"
                value={mailgunDomain}
                onChange={(e) => setMailgunDomain(e.target.value)}
                placeholder="mg.example.com"
                className={inputClassName}
                required
              />
              <p className={helperClassName}>Your Mailgun sending domain, for example `mg.example.com`.</p>
            </div>

            <div className="mt-4">
              <label className={labelClassName}>Reply To</label>
              <input
                type="email"
                value={replyTo}
                onChange={(e) => setReplyTo(e.target.value)}
                placeholder="support@example.com"
                className={inputClassName}
              />
            </div>
          </DashboardPagePanel>
        ) : null}

        {provider === 'brevo' ? (
          <DashboardPagePanel className="p-6 md:p-7">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-[1rem] bg-leaf-wash p-3">
                <ShieldCheck className="h-5 w-5 text-leaf" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-ink">Brevo configuration</h2>
                <p className="text-sm text-ink-mute">
                  Add the API key used for transactional email delivery.
                </p>
              </div>
            </div>

            <div>
              <label className={labelClassName}>API Key *</label>
              <input
                type="password"
                value={brevoApiKey}
                onChange={(e) => setBrevoApiKey(e.target.value)}
                placeholder="xkeysib-••••••••••••••••••••••••••••"
                className={inputClassName}
                required
              />
              <p className={helperClassName}>Found in Brevo dashboard under SMTP & API, then API Keys.</p>
            </div>

            <div className="mt-4">
              <label className={labelClassName}>Reply To</label>
              <input
                type="email"
                value={replyTo}
                onChange={(e) => setReplyTo(e.target.value)}
                placeholder="support@example.com"
                className={inputClassName}
              />
            </div>
          </DashboardPagePanel>
        ) : null}

        <DashboardPagePanel className="p-6">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={isPlatformConfig}
              onChange={(e) => setIsPlatformConfig(e.target.checked)}
              className={checkboxClassName}
            />
            <div>
              <div className="text-sm font-semibold text-ink">Platform configuration</div>
              <p className="mt-1 text-sm leading-6 text-ink-mute">
                Enable this to make the configuration available to all tenants as a fallback when they do not have their own email provider configured.
              </p>
            </div>
          </label>
        </DashboardPagePanel>

        <DashboardPagePanel className="p-6 md:p-7">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-[1rem] bg-paper p-3">
              <Layers3 className="h-5 w-5 text-gold" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-ink">Email settings</h2>
              <p className="text-sm text-ink-mute">
                Define the sending identity that recipients will see in outgoing emails.
              </p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className={labelClassName}>From Email *</label>
              <input
                type="email"
                value={fromEmail}
                onChange={(e) => setFromEmail(e.target.value)}
                placeholder="noreply@example.com"
                className={inputClassName}
                required
              />
            </div>

            <div>
              <label className={labelClassName}>From Name *</label>
              <input
                type="text"
                value={fromName}
                onChange={(e) => setFromName(e.target.value)}
                placeholder="My Platform"
                className={inputClassName}
                required
              />
            </div>
          </div>
        </DashboardPagePanel>

        <DashboardPagePanel className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => router.back()}
              className={secondaryButtonClassName}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
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
        </DashboardPagePanel>
      </form>
    </DashboardPageShell>
  )
}
