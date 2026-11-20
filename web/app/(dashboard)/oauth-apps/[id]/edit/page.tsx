'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import { PencilLine } from 'lucide-react'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import DashboardPageShell from '@/components/dashboard/DashboardPageShell'
import { apiClient } from '@/lib/api/client'

interface OAuthApp {
  id: number
  provider: string
  app_name: string
  auth_method: string
  client_id: string
  redirect_uri: string
  scopes: string[] | null
  is_active: boolean
  is_default: boolean
  description: string | null
  config: Record<string, any> | null
}

const DEFAULT_SCOPES: Record<string, string[]> = {
  github: ['repo', 'user', 'read:org'],
  SLACK: [
    'channels:history', 'channels:read', 'groups:history', 'groups:read',
    'im:history', 'im:read', 'mpim:history', 'mpim:read', 'users:read', 'team:read',
  ],
  gmail: [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/userinfo.email',
  ],
}

const sectionClassName =
  'rounded-[1.9rem] border border-line bg-white p-6 shadow-soft'

const labelClassName = 'mb-1.5 block text-sm font-semibold text-ink-soft'
const inputClassName =
  'w-full rounded-[1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink placeholder:text-ash focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint'
const monoInputClassName = `${inputClassName} font-mono`
const helperClassName = 'mt-1.5 text-xs leading-5 text-ink-mute'
const checkboxClassName =
  'h-4 w-4 rounded border-taupe text-hotpink focus:ring-2 focus:ring-mint'
const primaryButtonClassName =
  'inline-flex items-center justify-center gap-2 rounded-[1rem] bg-ink px-5 py-3 text-sm font-semibold text-white shadow-soft transition-colors hover:bg-night disabled:cursor-not-allowed disabled:opacity-60'
const secondaryButtonClassName =
  'inline-flex items-center justify-center rounded-[1rem] border border-black/10 bg-white/85 px-5 py-3 text-sm font-semibold text-ink-soft transition-colors hover:border-tan hover:bg-paper hover:text-ink'
const scopePillClassName =
  'inline-flex rounded-full border border-line bg-paper px-2.5 py-1 font-mono text-[11px] text-bark'
const selectionCardClassName =
  'flex items-start gap-3 rounded-[1.2rem] border border-black/10 bg-white/80 px-4 py-3 transition-colors hover:border-paper-dim hover:bg-cream'

export default function EditOAuthAppPage() {
  const router = useRouter()
  const params = useParams()
  const appId = params?.id as string

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [app, setApp] = useState<OAuthApp | null>(null)

  const [formData, setFormData] = useState({
    app_name: '',
    auth_method: 'oauth',
    client_id: '',
    client_secret: '',
    redirect_uri: '',
    scopes: [] as string[],
    api_token: '',       // new password/token (blank = keep existing)
    is_active: true,
    is_default: false,
    description: '',
    config: {} as Record<string, any>,
  })

  const fetchOAuthApp = useCallback(async () => {
    if (!appId) return
    try {
      setLoading(true)
      const data = await apiClient.getOAuthApp(parseInt(appId))
      setApp(data)
      setFormData({
        app_name: data.app_name || '',
        auth_method: data.auth_method || 'oauth',
        client_id: data.client_id || '',
        client_secret: '',
        redirect_uri: data.redirect_uri || '',
        scopes: data.scopes || [],
        api_token: '',
        is_active: data.is_active ?? true,
        is_default: data.is_default ?? false,
        description: data.description || '',
        config: data.config || {},
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }, [appId])

  useEffect(() => {
    fetchOAuthApp()
  }, [fetchOAuthApp])

  const handleScopeChange = (scope: string, checked: boolean) => {
    if (checked) {
      setFormData({ ...formData, scopes: [...formData.scopes, scope] })
    } else {
      setFormData({ ...formData, scopes: formData.scopes.filter(s => s !== scope) })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const updateData: any = {
        app_name: formData.app_name,
        redirect_uri: formData.redirect_uri,
        scopes: formData.scopes,
        is_active: formData.is_active,
        is_default: formData.is_default,
        description: formData.description,
        config: formData.config,
      }
      if (formData.auth_method === 'oauth') {
        updateData.client_id = formData.client_id
        if (formData.client_secret) updateData.client_secret = formData.client_secret
      }
      if (formData.auth_method === 'github_app') {
        updateData.client_id = formData.client_id
        if (formData.client_secret) updateData.client_secret = formData.client_secret
      }
      if ((formData.auth_method === 'api_token' || formData.auth_method === 'basic_auth') && formData.api_token) {
        updateData.api_token = formData.api_token
      }
      await apiClient.updateOAuthApp(parseInt(appId), updateData)
      router.push('/oauth-apps')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!app) {
    return (
      <div className="min-h-screen p-4 md:p-6">
        <div className="mx-auto max-w-4xl">
          <ErrorAlert message="OAuth app not found" />
        </div>
      </div>
    )
  }

  const availableScopes = DEFAULT_SCOPES[app.provider] || []
  const isMailisk = app.provider === 'mailisk'

  return (
    <DashboardPageShell
      title={`Edit ${app.app_name}`}
      description={
        <span className="capitalize">
          Update credentials, scopes, and defaults for this {app.provider} connection.
        </span>
      }
      icon={PencilLine}
      badge="OAuth Apps"
      backHref="/oauth-apps"
      backLabel="Back to Connected Accounts"
      maxWidthClassName="max-w-5xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'OAuth Apps', href: '/oauth-apps' },
        { label: app.app_name },
        { label: 'Edit' },
      ]}
    >
      <div className="space-y-5">
        {error && (
          <div className="mb-5">
            <ErrorAlert message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Basic Information */}
          <div className={sectionClassName}>
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-ink">Basic Information</h2>
                <p className="mt-1 text-sm text-ink-mute">Name, description, and connection status.</p>
              </div>
              <div className="rounded-full border border-line bg-white/80 px-3 py-1 text-[11px] font-semibold text-clay">
                {app.provider}, {app.auth_method?.replace('_', ' ')}
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label className={labelClassName}>Connection Name *</label>
                <input
                  type="text"
                  required
                  value={formData.app_name}
                  onChange={(e) => setFormData({ ...formData, app_name: e.target.value })}
                  className={inputClassName}
                />
              </div>
              <div>
                <label className={labelClassName}>Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className={inputClassName}
                  rows={3}
                />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <label className={selectionCardClassName}>
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className={checkboxClassName}
                  />
                  <div>
                    <div className="text-sm font-semibold text-ink">Active</div>
                    <p className="text-xs text-ink-mute">Allow this connection to be used immediately.</p>
                  </div>
                </label>
                <label className={selectionCardClassName}>
                  <input
                    type="checkbox"
                    checked={formData.is_default}
                    onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                    className={checkboxClassName}
                  />
                  <div>
                    <div className="text-sm font-semibold text-ink">Default for this provider</div>
                    <p className="text-xs text-ink-mute">Use this account as the primary connection by default.</p>
                  </div>
                </label>
              </div>
            </div>
          </div>

          {/* Credentials — OAuth */}
          {formData.auth_method === 'oauth' && (
            <div className={sectionClassName}>
              <div className="mb-4">
                <h2 className="text-base font-semibold text-ink">OAuth Credentials</h2>
                <p className="mt-1 text-sm text-ink-mute">Rotate the secret only when you need to replace it.</p>
              </div>
              <div className="space-y-4">
                <div>
                  <label className={labelClassName}>Client ID *</label>
                  <input
                    type="text"
                    required
                    value={formData.client_id}
                    onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                    className={monoInputClassName}
                  />
                </div>
                <div>
                  <label className={labelClassName}>Client Secret</label>
                  <input
                    type="password"
                    value={formData.client_secret}
                    onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                    className={monoInputClassName}
                    placeholder="Leave blank to keep current secret"
                  />
                  <p className={helperClassName}>Only enter a new value to replace the existing secret.</p>
                </div>
                <div>
                  <label className={labelClassName}>Redirect URI *</label>
                  <input
                    type="url"
                    required
                    value={formData.redirect_uri}
                    onChange={(e) => setFormData({ ...formData, redirect_uri: e.target.value })}
                    className={monoInputClassName}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Credentials — Basic Auth (Username + Password → JWT) */}
          {formData.auth_method === 'basic_auth' && (
            <div className={sectionClassName}>
              <div className="mb-4">
                <h2 className="text-base font-semibold text-ink">Login Credentials</h2>
                <p className="mt-1 text-sm text-ink-mute">These settings are used to fetch and refresh access tokens.</p>
              </div>
              <div className="space-y-4">
                <div>
                  <label className={labelClassName}>Password {formData.api_token ? '*' : '(leave blank to keep current)'}</label>
                  <input
                    type="password"
                    value={formData.api_token}
                    onChange={(e) => setFormData({ ...formData, api_token: e.target.value })}
                    className={monoInputClassName}
                    placeholder="Leave blank to keep current password"
                  />
                  <p className={helperClassName}>
                    Encrypted and stored securely. Changing the password will clear the cached JWT token and trigger a fresh login on next use.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Credentials — API Token */}
          {formData.auth_method === 'api_token' && (
            <div className={sectionClassName}>
              <div className="mb-4">
                <h2 className="text-base font-semibold text-ink">API Token</h2>
                <p className="mt-1 text-sm text-ink-mute">Token-based authentication with optional custom headers.</p>
              </div>
              <div className="space-y-4">
                {isMailisk && (
                  <>
                    <div>
                      <label className={labelClassName}>Mailisk Namespace *</label>
                      <input
                        type="text"
                        required
                        value={formData.config.namespace || ''}
                        onChange={(e) => setFormData({ ...formData, config: { ...formData.config, namespace: e.target.value.trim().toLowerCase() } })}
                        className={monoInputClassName}
                        placeholder="your-team"
                      />
                      <p className={helperClassName}>
                        Used to generate inboxes like <code className="bg-sand px-1 rounded">run-123@your-team.mailisk.net</code>.
                      </p>
                    </div>
                    <div>
                      <label className={labelClassName}>Mailisk API Base URL</label>
                      <input
                        type="url"
                        value={formData.config.base_url || ''}
                        onChange={(e) => setFormData({ ...formData, config: { ...formData.config, base_url: e.target.value } })}
                        className={monoInputClassName}
                        placeholder="https://api.mailisk.com"
                      />
                      <p className={helperClassName}>Leave blank to use the default Mailisk API endpoint.</p>
                    </div>
                  </>
                )}
                <div>
                  <label className={labelClassName}>API Token (leave blank to keep current)</label>
                  <input
                    type="password"
                    value={formData.api_token}
                    onChange={(e) => setFormData({ ...formData, api_token: e.target.value })}
                    className={monoInputClassName}
                    placeholder="Leave blank to keep current token"
                  />
                  <p className={helperClassName}>Only enter a new value to replace the existing token.</p>
                </div>
              </div>
            </div>
          )}

          {/* Credentials — GitHub App */}
          {formData.auth_method === 'github_app' && (
            <div className={sectionClassName}>
              <div className="mb-4">
                <h2 className="text-base font-semibold text-ink">GitHub App Credentials</h2>
                <p className="mt-1 text-sm text-ink-mute">Update App ID or private key. Installation is resolved automatically from the configured repositories.</p>
              </div>
              <div className="space-y-4">
                <div>
                  <label className={labelClassName}>App ID *</label>
                  <input
                    type="text"
                    required
                    value={formData.client_id}
                    onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                    className={monoInputClassName}
                    placeholder="123456"
                  />
                  <p className={helperClassName}>The numeric App ID from GitHub App settings.</p>
                </div>
                <div>
                  <label className={labelClassName}>Private Key (PEM)</label>
                  <textarea
                    rows={7}
                    value={formData.client_secret}
                    onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                    className={monoInputClassName + ' text-xs'}
                    placeholder={'Leave blank to keep existing key\n-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----'}
                  />
                  <p className={helperClassName}>Only enter a new key to replace the existing one.</p>
                </div>
              </div>
            </div>
          )}

          {/* Scopes (OAuth only) */}
          {formData.auth_method === 'oauth' && availableScopes.length > 0 && (
            <div className={sectionClassName}>
              <div className="mb-4">
                <h2 className="text-base font-semibold text-ink">OAuth Scopes</h2>
                <p className="mt-1 text-sm text-ink-mute">Choose which permissions this connection should request.</p>
              </div>
              <div className="grid gap-2">
                {availableScopes.map((scope) => (
                  <label key={scope} className={selectionCardClassName}>
                    <input
                      type="checkbox"
                      checked={formData.scopes.includes(scope)}
                      onChange={(e) => handleScopeChange(scope, e.target.checked)}
                      className={checkboxClassName}
                    />
                    <span className={scopePillClassName}>{scope}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="submit"
              disabled={saving}
              className={`${primaryButtonClassName} flex-1`}
            >
              {saving ? (
                <span className="flex items-center justify-center gap-2">
                  <LoadingSpinner size="sm" />
                  Saving...
                </span>
              ) : (
                'Save Changes'
              )}
            </button>
            <Link
              href="/oauth-apps"
              className={secondaryButtonClassName}
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </DashboardPageShell>
  )
}
