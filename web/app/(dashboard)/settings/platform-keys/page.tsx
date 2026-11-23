'use client'

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import { extractErrorMessage } from '@/lib/api/error'
import { platformKeysApi, type PlatformKey } from '@/lib/api/platform-keys'

const PERMISSION_LABELS: Record<string, string> = {
  'tenants:manage': 'Manage customer workspaces',
  'billing:read': 'Read plan and usage',
  'webhooks:manage': 'Manage webhooks',
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : 'Never'
}

export default function PlatformKeysPage() {
  const [keys, setKeys] = useState<PlatformKey[]>([])
  const [available, setAvailable] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [forbidden, setForbidden] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('')
  const [permissions, setPermissions] = useState<string[]>(['tenants:manage', 'billing:read', 'webhooks:manage'])
  const [newKey, setNewKey] = useState<string | null>(null)

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await platformKeysApi.list()
      setKeys(data.keys)
      setAvailable(data.available_permissions)
    } catch (err: any) {
      if (err?.response?.status === 403) {
        setForbidden(true)
      } else {
        setError(extractErrorMessage(err, 'Failed to load platform keys'))
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const togglePermission = (permission: string) => {
    setPermissions((current) =>
      current.includes(permission) ? current.filter((p) => p !== permission) : [...current, permission]
    )
  }

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || permissions.length === 0) return
    setSaving(true)
    try {
      const created = await platformKeysApi.create(name.trim(), permissions)
      setNewKey(created.api_key)
      setName('')
      await load()
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to create the key'))
    } finally {
      setSaving(false)
    }
  }

  const regenerate = async (key: PlatformKey) => {
    if (!window.confirm(`Regenerate "${key.name}"? The current key stops working immediately.`)) return
    try {
      const created = await platformKeysApi.regenerate(key.id)
      setNewKey(created.api_key)
      await load()
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to regenerate the key'))
    }
  }

  const setActive = async (key: PlatformKey, isActive: boolean) => {
    try {
      await platformKeysApi.setActive(key.id, isActive)
      await load()
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to update the key'))
    }
  }

  const remove = async (key: PlatformKey) => {
    if (!window.confirm(`Delete "${key.name}"? Anything using it stops working.`)) return
    try {
      await platformKeysApi.remove(key.id)
      await load()
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to delete the key'))
    }
  }

  const copy = (value: string) => {
    navigator.clipboard.writeText(value).then(
      () => toast.success('Copied'),
      () => toast.error('Copy failed; select the key and copy it')
    )
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
      <div className="mb-8">
        <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Platform keys</h1>
        <p className="mt-1 text-ink-soft text-sm">
          Connect your own system to this workspace: create and manage your customers&apos; workspaces, their plans,
          usage, agents and keys. Widget and agent keys stay on each agent&apos;s API keys page.
        </p>
      </div>

      {forbidden ? (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold text-ink">Owners and admins only</h2>
          <p className="mt-1 text-sm text-ink-soft">
            A platform key can act for the whole workspace, so only owners and admins can manage them. Ask one of them
            to create a key for you.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

          {newKey && (
            <div className="rounded-lg border border-line bg-sand p-4" role="status">
              <p className="text-sm font-semibold text-ink">Copy this key now. It is shown only once.</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <code className="min-w-0 flex-1 break-all rounded bg-white px-3 py-2 text-xs text-ink">{newKey}</code>
                <button
                  type="button"
                  onClick={() => copy(newKey)}
                  className="rounded-[1rem] bg-ink px-4 py-2 text-sm font-semibold text-white hover:bg-black"
                >
                  Copy
                </button>
                <button
                  type="button"
                  onClick={() => setNewKey(null)}
                  className="rounded-[1rem] px-4 py-2 text-sm font-semibold text-ink-soft hover:text-ink"
                >
                  Done
                </button>
              </div>
            </div>
          )}

          <form onSubmit={create} className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold text-ink mb-1">Create a platform key</h2>
            <p className="text-sm text-ink-mute mb-5">Give each system its own key, so you can revoke one without the others.</p>
            <label className="block text-sm font-medium text-ink" htmlFor="platform-key-name">
              Name
            </label>
            <input
              id="platform-key-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Production integration"
              maxLength={255}
              className="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
            />
            <fieldset className="mt-5">
              <legend className="text-sm font-medium text-ink">Permissions</legend>
              <div className="mt-2 space-y-3">
                {Object.entries(available).map(([permission, description]) => (
                  <label key={permission} className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={permissions.includes(permission)}
                      onChange={() => togglePermission(permission)}
                      className="mt-1"
                    />
                    <span>
                      <span className="block text-sm font-medium text-ink">
                        {PERMISSION_LABELS[permission] || permission}
                      </span>
                      <span className="block text-xs text-ink-mute">{description}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            <button
              type="submit"
              disabled={saving || !name.trim() || permissions.length === 0}
              className="mt-6 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white hover:bg-black disabled:opacity-50"
            >
              {saving ? 'Creating…' : 'Create key'}
            </button>
          </form>

          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold text-ink mb-4">Keys</h2>
            {keys.length === 0 ? (
              <p className="text-sm text-ink-mute">No platform keys yet.</p>
            ) : (
              <ul className="divide-y divide-line">
                {keys.map((key) => (
                  <li key={key.id} className="flex flex-wrap items-start justify-between gap-4 py-4">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-ink">
                        {key.name}
                        {!key.is_active && <span className="ml-2 text-xs font-normal text-ink-mute">(switched off)</span>}
                      </p>
                      <p className="mt-1 text-xs text-ink-mute">
                        <code>{key.key_prefix}…</code>
                      </p>
                      <p className="mt-1 text-xs text-ink-soft">
                        {key.permissions.map((p) => PERMISSION_LABELS[p] || p).join(', ')}
                      </p>
                      <p className="mt-1 text-xs text-ink-mute">Last used: {formatDate(key.last_used_at)}</p>
                    </div>
                    <div className="flex flex-wrap gap-3 text-sm font-semibold">
                      <button type="button" onClick={() => regenerate(key)} className="text-ink-soft hover:text-ink">
                        Regenerate
                      </button>
                      <button
                        type="button"
                        onClick={() => setActive(key, !key.is_active)}
                        className="text-ink-soft hover:text-ink"
                      >
                        {key.is_active ? 'Switch off' : 'Switch on'}
                      </button>
                      <button type="button" onClick={() => remove(key)} className="text-plum hover:underline">
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
