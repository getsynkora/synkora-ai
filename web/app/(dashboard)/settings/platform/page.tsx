'use client'

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { apiClient } from '@/lib/api/client'
import { extractErrorMessage } from '@/lib/api/error'
import { useProfile } from '@/hooks/useProfile'

interface KeyRotationResult {
  task_id: string
  status: string
  message: string
}

interface PlatformSettings {
  id?: string
  stripe_publishable_key?: string
  stripe_secret_key?: string
  stripe_webhook_secret?: string
  created_at?: string
  updated_at?: string
}

export default function PlatformSettingsPage() {
  const { profile } = useProfile()
  const isPlatformAdmin = profile?.is_platform_admin ?? false

  const [settings, setSettings] = useState<PlatformSettings>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  // Key rotation state
  const [rotationInProgress, setRotationInProgress] = useState(false)
  const [rotationResult, setRotationResult] = useState<KeyRotationResult | null>(null)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const data = await apiClient.request('GET', '/api/v1/platform-settings')
      if (data) {
        setSettings({
          stripe_publishable_key: data.stripe_publishable_key || '',
          stripe_secret_key: '', // Not returned by backend for security
          stripe_webhook_secret: '', // Not returned by backend for security
        })
      }
    } catch (error) {
      console.error('Failed to load settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMessage(null)

    try {
      // Update Stripe keys
      await apiClient.request('PUT', '/api/v1/platform-settings/stripe-keys', {
        secret_key: settings.stripe_secret_key || undefined,
        publishable_key: settings.stripe_publishable_key || undefined,
        webhook_secret: settings.stripe_webhook_secret || undefined
      })

      setMessage({ type: 'success', text: 'Stripe settings saved successfully!' })
      // Clear sensitive fields after save
      setSettings({
        ...settings,
        stripe_secret_key: '',
        stripe_webhook_secret: ''
      })
      loadSettings()
    } catch (error: any) {
      setMessage({ type: 'error', text: extractErrorMessage(error, 'Failed to save settings') })
    } finally {
      setSaving(false)
    }
  }

  const handleDryRun = async () => {
    setRotationInProgress(true)
    setRotationResult(null)
    try {
      const resp = await apiClient.request('POST', '/api/v1/platform-settings/key-rotation/dry-run')
      const data: KeyRotationResult = resp?.data || resp
      setRotationResult(data)
      toast.success('Dry run queued successfully.')
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Dry run failed.'))
    } finally {
      setRotationInProgress(false)
    }
  }

  const handleStartRotation = async () => {
    setShowConfirmDialog(false)
    setRotationInProgress(true)
    setRotationResult(null)
    try {
      const resp = await apiClient.request('POST', '/api/v1/platform-settings/key-rotation/start')
      const data: KeyRotationResult = resp?.data || resp
      setRotationResult(data)
      toast.success('Key rotation queued successfully.')
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Key rotation failed.'))
    } finally {
      setRotationInProgress(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500"></div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Platform Settings</h1>
        <p className="mt-2 text-gray-600">Configure Stripe payment integration for the platform</p>
      </div>

      {message && (
        <div className={`mb-6 p-4 rounded-lg ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Stripe Configuration */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Stripe Configuration</h2>
          <p className="text-sm text-gray-600 mb-4">
            Configure your Stripe API keys to enable payment processing. You can find these keys in your{' '}
            <a href="https://dashboard.stripe.com/apikeys" target="_blank" rel="noopener noreferrer" className="text-emerald-600 hover:text-emerald-700">
              Stripe Dashboard
            </a>.
          </p>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Stripe Publishable Key
              </label>
              <input
                type="text"
                value={settings.stripe_publishable_key || ''}
                onChange={(e) => setSettings({ ...settings, stripe_publishable_key: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                placeholder="pk_test_..."
              />
              <p className="mt-1 text-xs text-gray-500">
                This key is safe to expose in your frontend code
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Stripe Secret Key
              </label>
              <input
                type="password"
                value={settings.stripe_secret_key || ''}
                onChange={(e) => setSettings({ ...settings, stripe_secret_key: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                placeholder="sk_test_..."
              />
              <p className="mt-1 text-xs text-gray-500">
                Keep this key secure and never expose it in frontend code
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Stripe Webhook Secret
              </label>
              <input
                type="password"
                value={settings.stripe_webhook_secret || ''}
                onChange={(e) => setSettings({ ...settings, stripe_webhook_secret: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                placeholder="whsec_..."
              />
              <p className="mt-1 text-xs text-gray-500">
                Used to verify webhook events from Stripe
              </p>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>

      {/* Encryption Key Rotation — platform admin only */}
      {isPlatformAdmin && (
        <div className="mt-10 bg-white shadow rounded-lg p-6 border border-red-100">
          <h2 className="text-xl font-semibold text-gray-900 mb-2 flex items-center gap-2">
            <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
            Encryption Key Rotation
          </h2>
          <p className="text-sm text-gray-600 mb-6">
            Re-encrypts all stored secrets with the primary encryption key. Use this after rotating{' '}
            <code className="px-1 py-0.5 bg-gray-100 rounded text-xs font-mono">ENCRYPTION_KEY</code>.
            Set{' '}
            <code className="px-1 py-0.5 bg-gray-100 rounded text-xs font-mono">ENCRYPTION_KEY=NEW_KEY,OLD_KEY</code>,
            restart, then rotate. After rotation, set{' '}
            <code className="px-1 py-0.5 bg-gray-100 rounded text-xs font-mono">ENCRYPTION_KEY=NEW_KEY</code>{' '}
            and restart again.
          </p>

          <div className="flex items-center gap-3 flex-wrap">
            <button
              type="button"
              onClick={handleDryRun}
              disabled={rotationInProgress}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 border border-gray-300 text-gray-800 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {rotationInProgress ? 'Working...' : 'Dry Run'}
            </button>
            <button
              type="button"
              onClick={() => setShowConfirmDialog(true)}
              disabled={rotationInProgress}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {rotationInProgress ? 'Working...' : 'Start Rotation'}
            </button>
          </div>

          {/* Status box after a call */}
          {rotationResult && (
            <div className="mt-5 p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-1 text-sm">
              <div className="flex items-center gap-2">
                <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold uppercase ${rotationResult.status === 'queued' ? 'bg-blue-100 text-blue-700' : 'bg-gray-200 text-gray-700'}`}>
                  {rotationResult.status}
                </span>
                <span className="text-gray-700">{rotationResult.message}</span>
              </div>
              <p className="text-xs text-gray-500">Task ID: <span className="font-mono">{rotationResult.task_id}</span></p>
            </div>
          )}
        </div>
      )}

      {/* Confirm dialog for Start Rotation */}
      {showConfirmDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Confirm Key Rotation</h3>
            <p className="text-sm text-gray-600 mb-6">
              This will re-encrypt <strong>all stored secrets</strong> using the current primary encryption key. This operation cannot be undone. Make sure you have configured{' '}
              <code className="px-1 py-0.5 bg-gray-100 rounded text-xs font-mono">ENCRYPTION_KEY=NEW_KEY,OLD_KEY</code>{' '}
              and restarted the API before proceeding.
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowConfirmDialog(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleStartRotation}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
              >
                Yes, Start Rotation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
