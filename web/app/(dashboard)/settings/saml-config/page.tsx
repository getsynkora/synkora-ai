'use client'

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import { samlConfigApi } from '@/lib/api/saml-config'
import { extractErrorMessage } from '@/lib/api/error'
import type { SAMLConfig, SAMLConfigCreateRequest } from '@/types/saml-config'

type IdpMethod = 'url' | 'xml'

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

export default function SAMLConfigPage() {
  const [config, setConfig] = useState<SAMLConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [idpMethod, setIdpMethod] = useState<IdpMethod>('url')

  const [idpMetadataUrl, setIdpMetadataUrl] = useState('')
  const [idpMetadataXml, setIdpMetadataXml] = useState('')
  const [spEntityId, setSpEntityId] = useState('')
  const [acsUrl, setAcsUrl] = useState('')
  const [emailAttribute, setEmailAttribute] = useState('email')
  const [nameAttribute, setNameAttribute] = useState('displayName')
  const [jitProvisioning, setJitProvisioning] = useState(true)
  const [forceSaml, setForceSaml] = useState(false)
  const [isActive, setIsActive] = useState(true)

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await samlConfigApi.getConfig()
      setConfig(data)
      if (data) {
        populateForm(data)
      } else {
        // Pre-fill sensible SP defaults for new config
        const origin = typeof window !== 'undefined' ? window.location.origin : ''
        setSpEntityId(`${origin}/saml/sp`)
      }
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to load SAML configuration'))
    } finally {
      setLoading(false)
    }
  }

  const populateForm = (data: SAMLConfig) => {
    setIdpMetadataUrl(data.idp_metadata_url ?? '')
    setIdpMethod(data.idp_metadata_url ? 'url' : 'xml')
    setSpEntityId(data.sp_entity_id)
    setAcsUrl(data.acs_url)
    setEmailAttribute(data.email_attribute)
    setNameAttribute(data.name_attribute ?? 'displayName')
    setJitProvisioning(data.jit_provisioning)
    setForceSaml(data.force_saml)
    setIsActive(data.is_active)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (idpMethod === 'url' && !idpMetadataUrl.trim()) {
      toast.error('IdP Metadata URL is required')
      return
    }
    if (idpMethod === 'xml' && !idpMetadataXml.trim()) {
      toast.error('IdP Metadata XML is required')
      return
    }
    if (!spEntityId.trim() || !acsUrl.trim()) {
      toast.error('SP Entity ID and ACS URL are required')
      return
    }

    const payload: SAMLConfigCreateRequest = {
      idp_metadata_url: idpMethod === 'url' ? idpMetadataUrl.trim() : null,
      idp_metadata_xml: idpMethod === 'xml' ? idpMetadataXml.trim() : null,
      sp_entity_id: spEntityId.trim(),
      acs_url: acsUrl.trim(),
      email_attribute: emailAttribute.trim() || 'email',
      name_attribute: nameAttribute.trim() || null,
      jit_provisioning: jitProvisioning,
      force_saml: forceSaml,
      is_active: isActive,
    }

    try {
      setSaving(true)
      const saved = await samlConfigApi.saveConfig(payload)
      setConfig(saved)
      populateForm(saved)
      toast.success('SAML configuration saved successfully')
    } catch (err: any) {
      const msg = extractErrorMessage(err, 'Failed to save SAML configuration')
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
      await samlConfigApi.deleteConfig()
      setConfig(null)
      setIdpMetadataUrl('')
      setIdpMetadataXml('')
      setForceSaml(false)
      setIsActive(true)
      setShowDeleteConfirm(false)
      toast.success('SAML configuration removed')
    } catch (err: any) {
      const msg = extractErrorMessage(err, 'Failed to delete SAML configuration')
      setError(msg)
      toast.error(msg)
    } finally {
      setDeleting(false)
    }
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? (typeof window !== 'undefined' ? window.location.origin : '')
  const spMetadataUrl = config ? `${apiBase}/console/api/auth/saml/${config.tenant_id}/metadata` : null
  const spLoginUrl = config ? `${apiBase}/console/api/auth/saml/${config.tenant_id}/login` : null

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
            <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">SAML 2.0 SSO</h1>
            <p className="mt-1 text-gray-600 text-sm">
              Connect your Identity Provider (Okta, Azure AD, Google Workspace, Ping) to enable single sign-on
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
            <li>Create a SAML application in your IdP (Okta, Azure AD, etc.)</li>
            <li>Enter the SP Entity ID and ACS URL from below into your IdP</li>
            <li>Copy the IdP Metadata URL from your IdP and paste it here</li>
            <li>Save — your users can now sign in via your IdP</li>
          </ol>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">

        {/* Service Provider Details */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Service Provider (SP) Details</h2>
          <p className="text-sm text-gray-500 mb-5">Copy these values into your Identity Provider when creating the SAML application.</p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">SP Entity ID (Audience URI)</label>
              <input
                type="text"
                value={spEntityId}
                onChange={(e) => setSpEntityId(e.target.value)}
                placeholder="https://your-app.com/saml/sp"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
              <p className="mt-1 text-xs text-gray-500">Unique identifier for this application in your IdP.</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">ACS URL (Assertion Consumer Service URL)</label>
              <input
                type="text"
                value={acsUrl}
                onChange={(e) => setAcsUrl(e.target.value)}
                placeholder={`${apiBase}/console/api/auth/saml/YOUR_TENANT_ID/acs`}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
              <p className="mt-1 text-xs text-gray-500">
                The URL your IdP posts the SAML assertion to after authentication.
                {config && (
                  <span className="ml-1 text-primary-600 font-medium">
                    Your tenant ID: <code>{config.tenant_id}</code>
                  </span>
                )}
              </p>
            </div>

            {/* SP Metadata URL — only shown once config exists */}
            {config && spMetadataUrl && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">SP Metadata URL</label>
                <div className="flex items-center px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
                  <code className="text-xs text-gray-700 flex-1 break-all">{spMetadataUrl}</code>
                  <CopyButton value={spMetadataUrl} />
                </div>
                <p className="mt-1 text-xs text-gray-500">Some IdPs can import SP configuration automatically from this URL.</p>
              </div>
            )}

            {config && spLoginUrl && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">SSO Login URL</label>
                <div className="flex items-center px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
                  <code className="text-xs text-gray-700 flex-1 break-all">{spLoginUrl}</code>
                  <CopyButton value={spLoginUrl} />
                </div>
                <p className="mt-1 text-xs text-gray-500">Direct users here to initiate SAML login. Add to your IdP's login button or email.</p>
              </div>
            )}
          </div>
        </div>

        {/* Identity Provider Configuration */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Identity Provider (IdP) Configuration</h2>
          <p className="text-sm text-gray-500 mb-5">Provide the metadata from your Identity Provider.</p>

          {/* Method tabs */}
          <div className="flex border-b border-gray-200 mb-5">
            <button
              type="button"
              onClick={() => setIdpMethod('url')}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                idpMethod === 'url'
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Metadata URL
            </button>
            <button
              type="button"
              onClick={() => setIdpMethod('xml')}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                idpMethod === 'xml'
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Paste XML
            </button>
          </div>

          {idpMethod === 'url' ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">IdP Metadata URL</label>
              <input
                type="url"
                value={idpMetadataUrl}
                onChange={(e) => setIdpMetadataUrl(e.target.value)}
                placeholder="https://company.okta.com/app/abc123/sso/saml/metadata"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
              <div className="mt-2 space-y-1 text-xs text-gray-500">
                <p><span className="font-medium text-gray-600">Okta:</span> App → Sign On tab → SAML Signing Certificates → Metadata URL</p>
                <p><span className="font-medium text-gray-600">Azure AD:</span> Enterprise App → Single sign-on → App Federation Metadata Url</p>
                <p><span className="font-medium text-gray-600">Google:</span> Admin Console → Apps → SAML apps → Download Metadata</p>
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">IdP Metadata XML</label>
              <textarea
                value={idpMetadataXml}
                onChange={(e) => setIdpMetadataXml(e.target.value)}
                rows={8}
                placeholder={'<?xml version="1.0"?>\n<EntityDescriptor ...>...</EntityDescriptor>'}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white font-mono"
              />
              {config?.has_idp_metadata_xml && !idpMetadataXml && (
                <p className="mt-1.5 text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded border border-amber-200">
                  Metadata XML is already stored. Paste new XML to replace it, or switch to Metadata URL.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Attribute Mapping */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Attribute Mapping</h2>
          <p className="text-sm text-gray-500 mb-5">Map SAML assertion attributes to user fields. Defaults work for most IdPs.</p>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email attribute</label>
              <input
                type="text"
                value={emailAttribute}
                onChange={(e) => setEmailAttribute(e.target.value)}
                placeholder="email"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Display name attribute</label>
              <input
                type="text"
                value={nameAttribute}
                onChange={(e) => setNameAttribute(e.target.value)}
                placeholder="displayName"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
              />
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
                <p className="text-sm font-medium text-gray-900">Enable SAML SSO</p>
                <p className="text-xs text-gray-500 mt-0.5">Allow users to sign in via your Identity Provider.</p>
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
                <p className="text-xs text-gray-500 mt-0.5">Automatically create an account on first SAML login. Disable to require pre-created accounts.</p>
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

            {/* Force SAML */}
            <div className="flex items-center justify-between py-3">
              <div>
                <p className="text-sm font-medium text-gray-900">Require SAML (disable password login)</p>
                <p className="text-xs text-gray-500 mt-0.5">Block all password-based logins. Users must authenticate via your IdP.</p>
              </div>
              <button
                type="button"
                onClick={() => setForceSaml(!forceSaml)}
                className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${
                  forceSaml ? 'bg-red-500' : 'bg-gray-200'
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                  forceSaml ? 'translate-x-5' : 'translate-x-0'
                }`} />
              </button>
            </div>

            {forceSaml && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                Enabling this will immediately block all password-based logins including your own account.
                Make sure SAML is working and tested before turning this on.
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
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

          {config && !showDeleteConfirm && (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="px-4 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Remove SAML
            </button>
          )}

          {showDeleteConfirm && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-red-600">Remove SAML configuration?</span>
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
      </form>

      {/* Help */}
      <div className="bg-primary-50 border border-primary-200 rounded-lg p-4 mt-6">
        <h3 className="text-xs font-semibold text-primary-800 uppercase tracking-wide mb-2">About SAML 2.0 SSO</h3>
        <ul className="text-xs text-primary-700 space-y-1.5">
          <li className="flex items-start gap-2">
            <span className="text-primary-500 mt-0.5">•</span>
            <span>Each organization has its own SAML configuration — fully tenant-isolated</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary-500 mt-0.5">•</span>
            <span>Supports Okta, Azure AD, Google Workspace, Ping Identity, OneLogin, and any SAML 2.0 compliant IdP</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary-500 mt-0.5">•</span>
            <span>With JIT provisioning, new users are automatically created on first login — no manual user creation needed</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary-500 mt-0.5">•</span>
            <span>Use SCIM provisioning (Settings → SCIM) for full lifecycle management including deprovisioning</span>
          </li>
        </ul>
      </div>
    </div>
  )
}
