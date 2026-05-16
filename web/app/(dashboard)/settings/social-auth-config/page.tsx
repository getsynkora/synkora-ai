'use client'

import { useState, useEffect } from 'react'
import { Lock } from 'lucide-react'
import toast from 'react-hot-toast'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import EmptyState from '@/components/common/EmptyState'
import { socialAuthConfigApi, type ProviderConfig } from '@/lib/api/social-auth-config'
import { extractErrorMessage } from '@/lib/api/error'
import type { SocialProvider } from '@/types/social-auth'
import { usePermissions } from '@/hooks/usePermissions'
import { ProviderIcon } from '@/components/social-auth/ProviderIcon'

interface EditFormData {
  client_id: string
  client_secret: string
  redirect_uri: string
}

const PROVIDER_INFO: Record<SocialProvider, { name: string; color: string; description: string }> = {
  google: {
    name: 'Google',
    color: 'bg-blue-50 border-blue-200',
    description: 'Allow users to sign in with their Google account'
  },
  microsoft: {
    name: 'Microsoft',
    color: 'bg-sky-50 border-sky-200',
    description: 'Allow users to sign in with their Microsoft account'
  },
  apple: {
    name: 'Apple',
    color: 'bg-gray-50 border-gray-200',
    description: 'Allow users to sign in with their Apple ID'
  }
}

export default function SocialAuthConfigPage() {
  const { hasPermission, loading: permissionsLoading } = usePermissions()
  const [providers, setProviders] = useState<ProviderConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<SocialProvider | null>(null)
  const [editingProvider, setEditingProvider] = useState<SocialProvider | null>(null)
  const [creatingProvider, setCreatingProvider] = useState<SocialProvider | null>(null)
  const [editFormData, setEditFormData] = useState<EditFormData>({
    client_id: '',
    client_secret: '',
    redirect_uri: ''
  })
  const [createFormData, setCreateFormData] = useState<EditFormData>({
    client_id: '',
    client_secret: '',
    redirect_uri: ''
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchProviders()
  }, [])

  const fetchProviders = async () => {
    try {
      setLoading(true)
      const data = await socialAuthConfigApi.listProviderConfigs()
      setProviders(Array.isArray(data) ? data : [])
    } catch (err: any) {
      const errorMessage = extractErrorMessage(err, 'Failed to load providers')
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (provider: SocialProvider) => {
    try {
      setError(null)
      await socialAuthConfigApi.deleteProviderConfig(provider)
      await fetchProviders()
      setDeleteConfirm(null)
      toast.success(`${provider.charAt(0).toUpperCase() + provider.slice(1)} provider deleted successfully`)
    } catch (err: any) {
      const errorMessage = extractErrorMessage(err, 'Failed to delete provider')
      setError(errorMessage)
      toast.error(errorMessage)
    }
  }

  const handleToggleEnabled = async (provider: ProviderConfig) => {
    try {
      setError(null)
      await socialAuthConfigApi.updateProviderConfig(provider.provider_name as SocialProvider, {
        provider: provider.provider_name as SocialProvider,
        client_id: provider.client_id,
        redirect_uri: provider.redirect_uri,
        is_enabled: !provider.enabled
      })
      await fetchProviders()
      toast.success(`${provider.provider_name.charAt(0).toUpperCase() + provider.provider_name.slice(1)} provider ${!provider.enabled ? 'enabled' : 'disabled'} successfully`)
    } catch (err: any) {
      const errorMessage = extractErrorMessage(err, 'Failed to toggle provider')
      setError(errorMessage)
      toast.error(errorMessage)
      console.error('Error toggling provider:', err)
    }
  }

  const handleEdit = (provider: ProviderConfig) => {
    setEditingProvider(provider.provider_name as SocialProvider)
    setEditFormData({
      client_id: provider.client_id || '',
      client_secret: '', // Don't pre-fill secret for security
      redirect_uri: provider.redirect_uri || ''
    })
  }

  const handleCancelEdit = () => {
    setEditingProvider(null)
    setEditFormData({
      client_id: '',
      client_secret: '',
      redirect_uri: ''
    })
  }

  const handleSaveEdit = async () => {
    if (!editingProvider) return

    try {
      setSaving(true)
      setError(null)
      await socialAuthConfigApi.updateProviderConfig(editingProvider, {
        provider: editingProvider,
        client_id: editFormData.client_id,
        client_secret: editFormData.client_secret,
        redirect_uri: editFormData.redirect_uri,
        is_enabled: providers.find(p => p.provider_name === editingProvider)?.enabled || false
      })
      await fetchProviders()
      handleCancelEdit()
      toast.success(`${editingProvider.charAt(0).toUpperCase() + editingProvider.slice(1)} provider updated successfully`)
    } catch (err: any) {
      const errorMessage = extractErrorMessage(err, 'Failed to update provider')
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setSaving(false)
    }
  }

  const handleAdd = (provider: SocialProvider) => {
    setCreatingProvider(provider)
    setCreateFormData({
      client_id: '',
      client_secret: '',
      redirect_uri: ''
    })
  }

  const handleCancelCreate = () => {
    setCreatingProvider(null)
    setCreateFormData({
      client_id: '',
      client_secret: '',
      redirect_uri: ''
    })
  }

  const handleCreate = async () => {
    if (!creatingProvider) return

    try {
      setSaving(true)
      setError(null)
      await socialAuthConfigApi.createProviderConfig({
        provider: creatingProvider,
        client_id: createFormData.client_id,
        client_secret: createFormData.client_secret,
        redirect_uri: createFormData.redirect_uri,
        is_enabled: true
      })
      await fetchProviders()
      handleCancelCreate()
      toast.success(`${creatingProvider.charAt(0).toUpperCase() + creatingProvider.slice(1)} provider created successfully`)
    } catch (err: any) {
      const errorMessage = extractErrorMessage(err, 'Failed to create provider')
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setSaving(false)
    }
  }

  const configuredProviders = providers.map(p => p.provider_name)
  const availableProviders = Object.keys(PROVIDER_INFO).filter(
    p => !configuredProviders.includes(p as SocialProvider)
  ) as SocialProvider[]

  // Check if user is platform owner
  const isPlatformOwner = hasPermission('platform', 'read')

  if (loading || permissionsLoading) {
    return (
      <div className="dashboard-settings-page flex min-h-screen items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // Check platform owner permission
  if (!isPlatformOwner) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
          <Lock className="mx-auto h-12 w-12 text-yellow-600 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Access Denied
          </h3>
          <p className="text-gray-600">
            You do not have permission to access social authentication configuration. This feature is only available to platform owners.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-settings-page min-h-screen p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-5">
          <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Social Authentication</h1>
          <p className="text-gray-600 mt-1 text-sm">
            Configure OAuth providers for user authentication
          </p>
        </div>

        {error && (
          <div className="mb-4">
            <ErrorAlert message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        {/* Stats Overview */}
        <div className="grid grid-cols-3 gap-4 mb-5">
          <div className="bg-white p-3.5 rounded-lg border border-gray-200 shadow-sm">
            <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Total</div>
            <div className="text-2xl font-semibold text-gray-900">{providers.length}</div>
          </div>
          <div className="bg-white p-3.5 rounded-lg border border-gray-200 shadow-sm">
            <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Enabled</div>
            <div className="text-2xl font-semibold text-emerald-600">
              {providers.filter(p => p.enabled).length}
            </div>
          </div>
          <div className="bg-white p-3.5 rounded-lg border border-gray-200 shadow-sm">
            <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Available</div>
            <div className="text-2xl font-semibold text-primary-600">
              {availableProviders.length}
            </div>
          </div>
        </div>

        {/* Configured Providers */}
        {providers.length > 0 && (
          <div className="mb-5">
            <h2 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">Configured Providers</h2>
            <div className="space-y-2.5">
              {providers.map((provider) => {
                const info = PROVIDER_INFO[provider.provider_name as SocialProvider]
                
                return (
                  <div key={provider.id} className="bg-white rounded-lg border border-gray-200 overflow-hidden hover:border-primary-300 hover:shadow-sm transition-all">
                    <div className="p-3.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3 flex-1">
                          <div className="w-10 h-10 rounded-lg bg-gray-50 border border-gray-200 flex items-center justify-center flex-shrink-0">
                            <ProviderIcon provider={provider.provider_name as SocialProvider} size="sm" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <h3 className="text-sm font-semibold text-gray-900">{info.name}</h3>
                              {provider.enabled ? (
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                  Enabled
                                </span>
                              ) : (
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                                  Disabled
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-gray-500 truncate">{info.description}</p>
                            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                              <span className="truncate">
                                Client ID: <code className="font-mono bg-gray-50 px-1.5 py-0.5 rounded">{provider.client_id ? `${provider.client_id.substring(0, 20)}...` : 'N/A'}</code>
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-1 ml-4">
                          <button
                            onClick={() => handleEdit(provider)}
                            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                            title="Edit"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>

                          <button
                            onClick={() => handleToggleEnabled(provider)}
                            className={`p-1.5 rounded transition-colors ${
                              provider.enabled
                                ? 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                                : 'text-green-600 hover:text-green-700 hover:bg-green-50'
                            }`}
                            title={provider.enabled ? 'Disable' : 'Enable'}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              {provider.enabled ? (
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                              ) : (
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                              )}
                            </svg>
                          </button>

                          {deleteConfirm === provider.provider_name ? (
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => handleDelete(provider.provider_name as SocialProvider)}
                                className="px-2 py-1 bg-red-600 text-white rounded text-xs font-medium hover:bg-red-700 transition-colors"
                              >
                                Confirm
                              </button>
                              <button
                                onClick={() => setDeleteConfirm(null)}
                                className="px-2 py-1 border border-gray-300 text-gray-700 rounded text-xs font-medium hover:bg-gray-50 transition-colors"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setDeleteConfirm(provider.provider_name as SocialProvider)}
                              className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                              title="Delete"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Available Providers */}
        {availableProviders.length > 0 && (
          <div className="mb-5">
            <h2 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">Available Providers</h2>
            <div className="grid grid-cols-3 gap-3">
              {availableProviders.map((provider) => {
                const info = PROVIDER_INFO[provider]
                return (
                  <button
                    key={provider}
                    onClick={() => handleAdd(provider)}
                    className="bg-white rounded-lg border border-gray-200 p-3.5 hover:border-primary-300 hover:shadow-sm transition-all text-left"
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className="w-8 h-8 rounded bg-gray-50 border border-gray-200 flex items-center justify-center flex-shrink-0">
                        <ProviderIcon provider={provider} size="sm" />
                      </div>
                      <h3 className="text-sm font-semibold text-gray-900">{info.name}</h3>
                    </div>
                    <p className="text-xs text-gray-500">{info.description}</p>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Empty State */}
        {providers.length === 0 && availableProviders.length === 0 && (
          <EmptyState
            title="All Providers Configured"
            description="All available social authentication providers have been configured."
          />
        )}

        {/* Create Modal */}
        {creatingProvider && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto border border-gray-200">
              <div className="p-5">
                <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">
                      Add {PROVIDER_INFO[creatingProvider].name} Provider
                    </h2>
                    <p className="text-xs text-gray-500 mt-0.5">Configure your {PROVIDER_INFO[creatingProvider].name} OAuth credentials</p>
                  </div>
                  <button
                    onClick={handleCancelCreate}
                    className="text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">
                      Client ID *
                    </label>
                    <input
                      type="text"
                      value={createFormData.client_id}
                      onChange={(e) => setCreateFormData({ ...createFormData, client_id: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all bg-white"
                      placeholder="Enter client ID"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">
                      Client Secret *
                    </label>
                    <input
                      type="password"
                      value={createFormData.client_secret}
                      onChange={(e) => setCreateFormData({ ...createFormData, client_secret: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all bg-white"
                      placeholder="Enter client secret"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">
                      Redirect URI *
                    </label>
                    <input
                      type="url"
                      value={createFormData.redirect_uri}
                      onChange={(e) => setCreateFormData({ ...createFormData, redirect_uri: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all bg-white"
                      placeholder="https://your-domain.com/api/v1/auth/callback"
                      required
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 mt-5 pt-4 border-t border-gray-200">
                  <button
                    onClick={handleCancelCreate}
                    disabled={saving}
                    className="px-3 py-1.5 text-xs border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreate}
                    disabled={saving || !createFormData.client_id || !createFormData.client_secret || !createFormData.redirect_uri}
                    className="px-3 py-1.5 text-xs bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-lg font-medium hover:from-primary-600 hover:to-primary-700 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {saving ? (
                      <>
                        <LoadingSpinner size="sm" />
                        Creating...
                      </>
                    ) : (
                      'Create Provider'
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Edit Modal */}
        {editingProvider && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto border border-gray-200">
              <div className="p-5">
                <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">
                      Edit {PROVIDER_INFO[editingProvider].name} Configuration
                    </h2>
                    <p className="text-xs text-gray-500 mt-0.5">Update your {PROVIDER_INFO[editingProvider].name} OAuth credentials</p>
                  </div>
                  <button
                    onClick={handleCancelEdit}
                    className="text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">
                      Client ID *
                    </label>
                    <input
                      type="text"
                      value={editFormData.client_id}
                      onChange={(e) => setEditFormData({ ...editFormData, client_id: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all bg-white"
                      placeholder="Enter client ID"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">
                      Client Secret *
                    </label>
                    <input
                      type="password"
                      value={editFormData.client_secret}
                      onChange={(e) => setEditFormData({ ...editFormData, client_secret: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all bg-white"
                      placeholder="Enter new client secret"
                      required
                    />
                    <p className="mt-1.5 text-xs text-gray-500 bg-primary-50 p-2 rounded border border-primary-100">
                      Leave blank to keep the existing secret
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">
                      Redirect URI *
                    </label>
                    <input
                      type="url"
                      value={editFormData.redirect_uri}
                      onChange={(e) => setEditFormData({ ...editFormData, redirect_uri: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all bg-white"
                      placeholder="https://your-domain.com/api/v1/auth/callback"
                      required
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 mt-5 pt-4 border-t border-gray-200">
                  <button
                    onClick={handleCancelEdit}
                    disabled={saving}
                    className="px-3 py-1.5 text-xs border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveEdit}
                    disabled={saving || !editFormData.client_id || !editFormData.redirect_uri}
                    className="px-3 py-1.5 text-xs bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-lg font-medium hover:from-primary-600 hover:to-primary-700 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {saving ? (
                      <>
                        <LoadingSpinner size="sm" />
                        Saving...
                      </>
                    ) : (
                      'Save Changes'
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Help Text */}
        <div className="bg-primary-50 border border-primary-200 rounded-lg p-4 mt-5">
          <h3 className="text-xs font-semibold text-primary-800 mb-2 uppercase tracking-wide">About Social Authentication</h3>
          <ul className="text-xs text-primary-700 space-y-1.5">
            <li className="flex items-start gap-2">
              <span className="text-primary-500 mt-0.5">•</span>
              <span>Configure OAuth providers to enable social login for your users</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary-500 mt-0.5">•</span>
              <span>Each provider requires client credentials from their developer console</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary-500 mt-0.5">•</span>
              <span>Users can link multiple social accounts to their profile</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary-500 mt-0.5">•</span>
              <span>Disabled providers will not appear on the login page</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
