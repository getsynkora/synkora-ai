'use client'

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import { oidcConfigApi } from '@/lib/api/oidc-config'
import { extractErrorMessage } from '@/lib/api/error'
import type { OIDCConfig, OIDCConfigRequest } from '@/types/oidc-config'

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      type="button"
      onClick={copy}
      className="ml-2 px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 rounded transition-colors whitespace-nowrap"
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  )
}

const DEFAULT_SCOPES = 'openid,email,profile'

export default function OIDCConfigPage() {
  const [config, setConfig] = useState<OIDCConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [testingLogin, setTestingLogin] = useState(false)
  const [loginUrl, setLoginUrl] = useState<string | null>(null)

  const [providerName, setProviderName] = useState('')
  const [discoveryUrl, setDiscoveryUrl] = useState('')
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [scopes, setScopes] = useState(DEFAULT_SCOPES)
  const [emailClaim, setEmailClaim] = useState('email')
  const [nameClaim, setNameClaim] = useState('name')
  const [jitProvisioning, setJitProvisioning] = useState(true)
  const [forceOidc, setForceOidc] = useState(false)
  const [isActive, setIsActive] = useState(true)

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await oidcConfigApi.getConfig()
      setConfig(data)
      if (data) {
        populateForm(data)
      }
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to load OIDC configuration'))
    } finally {
      setLoading(false)
    }
  }

  const populateForm = (data: OIDCConfig) => {
    setProviderName(data.provider_name)
    setDiscoveryUrl(data.discovery_url)
    setClientId(data.client_id)
    setClientSecret('')
    setScopes(data.scopes.join(','))
    setEmailClaim(data.email_claim)
    setNameClaim(data.name_claim)
    setJitProvisioning(data.jit_provisioning)
    setForceOidc(data.force_oidc)
    setIsActive(data.is_active)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!providerName.trim()) {
      toast.error('Provider Name is required')
      return
    }
    if (!discoveryUrl.trim()) {
      toast.error('Discovery URL is required')
      return
    }
    if (!clientId.trim()) {
      toast.error('Client ID is required')
      return
    }
    if (!config && !clientSecret.trim()) {
      toast.error('Client Secret is required when creating a new configuration')
      return
    }

    const scopeList = scopes.split(',').map((s) => s.trim()).filter(Boolean)

    const payload: OIDCConfigRequest = {
      provider_name: providerName.trim(),
      discovery_url: discoveryUrl.trim(),
      client_id: clientId.trim(),
      scopes: scopeList.length > 0 ? scopeList : ['openid', 'email', 'profile'],
      email_claim: emailClaim.trim() || 'email',
      name_claim: nameClaim.trim() || 'name',
      jit_provisioning: jitProvisioning,
      force_oidc: forceOidc,
      is_active: isActive,
    }

    // Only include client_secret if the user typed something
    if (clientSecret.trim()) {
      payload.client_secret = clientSecret.trim()
    }

    try {
      setSaving(true)
      const saved = await oidcConfigApi.saveConfig(payload)
      setConfig(saved)
      populateForm(saved)
      toast.success('OIDC configuration saved successfully')
    } catch (err: any) {
      const msg = extractErrorMessage(err, 'Failed to save OIDC configuration')
      setError(msg)
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    try {
      setDeleting(true)
      setError(null)
      await oidcConfigApi.deleteConfig()
      setConfig(null)
      setProviderName('')
      setDiscoveryUrl('')
      setClientId('')
      setClientSecret('')
      setScopes(DEFAULT_SCOPES)
      setEmailClaim('email')
      setNameClaim('name')
      setJitProvisioning(true)
      setForceOidc(false)
      setIsActive(true)
      setLoginUrl(null)
      setShowDeleteConfirm(false)
      toast.success('OIDC configuration removed')
    } catch (err: any) {
      const msg = extractErrorMessage(err, 'Failed to delete OIDC configuration')
      setError(msg)
      toast.error(msg)
    } finally {
      setDeleting(false)
    }
  }

  const handleTestLogin = async () => {
    try {
      setTestingLogin(true)
      setError(null)
      const url = await oidcConfigApi.getLoginUrl()
      setLoginUrl(url)
      toast.success('Login URL generated')
    } catch (err: any) {
      const msg = extractErrorMessage(err, 'Failed to get login URL')
      setError(msg)
      toast.error(msg)
    } finally {
      setTestingLogin(false)
    }
  }

  if (loading) {
    return (
      <div className="dashboard-settings-page flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="dashboard-settings-page max-w-4xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">OIDC SSO</h1>
            <p className="mt-1 text-gray-600 text-sm">
              Connect your OpenID Connect provider (Okta, Google Workspace, Azure AD, Auth0) to enable single sign-on
            </p>
          </div>
          {config && (
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
              config.is_active
                ? 'bg-green-100 text-green-800'
                : 'bg-gray-100 text-gray-600'
            }`}>
              {config.is_active ? 'Active' : 'Disabled'}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-6">
          <ErrorAlert message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {/* Setup steps — shown when no config yet */}
      {!config && (
        <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-xs font-semibold text-blue-800 uppercase tracking-wide mb-2">How to set up</h3>
          <ol className="space-y-1 text-xs text-blue-700 list-decimal list-inside">
            <li>Create an OIDC application in your provider (Okta, Google Workspace, Auth0, etc.)</li>
            <li>Set the redirect URI in your provider to your deployment&apos;s callback URL</li>
            <li>Copy the Discovery URL and Client ID from your provider and paste them here</li>
            <li>Save — your users can now sign in via your OIDC provider</li>
          </ol>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">

        {/* Provider Configuration */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Provider Configuration</h2>
          <p className="text-sm text-gray-500 mb-5">Enter the details from your OIDC provider&apos;s application settings.</p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Provider Name</label>
              <input
                type="text"
                value={providerName}
                onChange={(e) => setProviderName(e.target.value)}
                placeholder="e.g. Okta, Google Workspace, Auth0"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
              <p className="mt-1 text-xs text-gray-500">Display name shown to users on the login page.</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Discovery URL</label>
              <input
                type="url"
                value={discoveryUrl}
                onChange={(e) => setDiscoveryUrl(e.target.value)}
                placeholder="https://accounts.google.com/.well-known/openid-configuration"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
              <div className="mt-2 space-y-1 text-xs text-gray-500">
                <p><span className="font-medium text-gray-600">Okta:</span> https://your-domain.okta.com/.well-known/openid-configuration</p>
                <p><span className="font-medium text-gray-600">Google:</span> https://accounts.google.com/.well-known/openid-configuration</p>
                <p><span className="font-medium text-gray-600">Auth0:</span> https://your-tenant.auth0.com/.well-known/openid-configuration</p>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Client ID</label>
              <input
                type="text"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                placeholder="your-client-id"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Client Secret</label>
              <input
                type="password"
                value={clientSecret}
                onChange={(e) => setClientSecret(e.target.value)}
                placeholder={config?.has_client_secret ? 'Leave blank to keep existing secret' : 'your-client-secret'}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
              {config?.has_client_secret && (
                <p className="mt-1 text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded border border-amber-200">
                  A client secret is already stored. Leave blank to keep it, or enter a new value to replace it.
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Claims & Scopes */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Claims &amp; Scopes</h2>
          <p className="text-sm text-gray-500 mb-5">Configure which claims are used to identify users. Defaults work for most providers.</p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Scopes</label>
              <input
                type="text"
                value={scopes}
                onChange={(e) => setScopes(e.target.value)}
                placeholder="openid,email,profile"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
              <p className="mt-1 text-xs text-gray-500">Comma-separated list of OAuth scopes to request. The <code>openid</code> scope is always required.</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email claim</label>
                <input
                  type="text"
                  value={emailClaim}
                  onChange={(e) => setEmailClaim(e.target.value)}
                  placeholder="email"
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name claim</label>
                <input
                  type="text"
                  value={nameClaim}
                  onChange={(e) => setNameClaim(e.target.value)}
                  placeholder="name"
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Options */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-5">Options</h2>

          <div className="space-y-5">
            {/* Enable toggle */}
            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div>
                <p className="text-sm font-medium text-gray-900">Enable OIDC SSO</p>
                <p className="text-xs text-gray-500 mt-0.5">Allow users to sign in via your OIDC provider.</p>
              </div>
              <button
                type="button"
                onClick={() => setIsActive(!isActive)}
                className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${
                  isActive ? 'bg-primary-600' : 'bg-gray-200'
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                  isActive ? 'translate-x-5' : 'translate-x-0'
                }`} />
              </button>
            </div>

            {/* JIT provisioning */}
            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div>
                <p className="text-sm font-medium text-gray-900">Auto-provision accounts (JIT)</p>
                <p className="text-xs text-gray-500 mt-0.5">Automatically create an account on first OIDC login. Disable to require pre-created accounts.</p>
              </div>
              <button
                type="button"
                onClick={() => setJitProvisioning(!jitProvisioning)}
                className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${
                  jitProvisioning ? 'bg-primary-600' : 'bg-gray-200'
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                  jitProvisioning ? 'translate-x-5' : 'translate-x-0'
                }`} />
              </button>
            </div>

            {/* Force OIDC */}
            <div className="flex items-center justify-between py-3">
              <div>
                <p className="text-sm font-medium text-gray-900">Require OIDC (disable password login)</p>
                <p className="text-xs text-gray-500 mt-0.5">Block all password-based logins. Users must authenticate via your OIDC provider.</p>
              </div>
              <button
                type="button"
                onClick={() => setForceOidc(!forceOidc)}
                className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${
                  forceOidc ? 'bg-red-500' : 'bg-gray-200'
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                  forceOidc ? 'translate-x-5' : 'translate-x-0'
                }`} />
              </button>
            </div>

            {forceOidc && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                Enabling this will immediately block all password-based logins including your own account.
                Make sure OIDC is working and tested before turning this on.
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 flex-wrap">
          <button
            type="submit"
            disabled={saving}
            className="px-5 py-2.5 bg-gradient-to-r from-primary-500 to-primary-600 text-white text-sm font-medium rounded-lg hover:from-primary-600 hover:to-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm flex items-center gap-2"
          >
            {saving ? (
              <>
                <LoadingSpinner size="sm" />
                Saving...
              </>
            ) : (
              config ? 'Update Configuration' : 'Save Configuration'
            )}
          </button>

          {config && (
            <button
              type="button"
              onClick={handleTestLogin}
              disabled={testingLogin}
              className="px-4 py-2.5 text-sm font-medium text-primary-700 bg-primary-50 border border-primary-200 rounded-lg hover:bg-primary-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {testingLogin ? (
                <>
                  <LoadingSpinner size="sm" />
                  Fetching...
                </>
              ) : (
                'Test Login URL'
              )}
            </button>
          )}

          {config && !showDeleteConfirm && (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="px-4 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Remove OIDC
            </button>
          )}

          {showDeleteConfirm && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-red-600">Remove OIDC configuration?</span>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                {deleting ? 'Removing...' : 'Yes, remove'}
              </button>
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                className="px-3 py-1.5 border border-gray-300 text-gray-700 text-xs font-medium rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>

        {/* Login URL result */}
        {loginUrl && (
          <div className="bg-white shadow rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">OIDC Login URL</h3>
            <div className="flex items-center px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
              <code className="text-xs text-gray-700 flex-1 break-all">{loginUrl}</code>
              <CopyButton value={loginUrl} />
            </div>
            <p className="mt-1.5 text-xs text-gray-500">
              Share this URL with users to initiate OIDC login, or open it yourself to test the flow.
            </p>
          </div>
        )}
      </form>

      {/* Help */}
      <div className="bg-primary-50 border border-primary-200 rounded-lg p-4 mt-6">
        <h3 className="text-xs font-semibold text-primary-800 uppercase tracking-wide mb-2">About OIDC SSO</h3>
        <ul className="text-xs text-primary-700 space-y-1.5">
          <li className="flex items-start gap-2">
            <span className="text-primary-500 mt-0.5">•</span>
            <span>Each organization has its own OIDC configuration — fully tenant-isolated</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary-500 mt-0.5">•</span>
            <span>Supports Okta, Google Workspace, Azure AD, Auth0, Keycloak, and any OIDC-compliant provider</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary-500 mt-0.5">•</span>
            <span>With JIT provisioning, new users are automatically created on first login — no manual user creation needed</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary-500 mt-0.5">•</span>
            <span>The Discovery URL (OpenID Connect metadata document) is used to automatically configure endpoints and keys</span>
          </li>
        </ul>
      </div>
    </div>
  )
}
