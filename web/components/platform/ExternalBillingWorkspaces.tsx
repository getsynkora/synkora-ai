'use client'

import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { extractErrorMessage } from '@/lib/api/error'
import { workspaceBillingApi, type WorkspaceBilling } from '@/lib/api/workspace-billing'

/**
 * Platform admins: workspaces whose plan is paid for in another system. Their own platform key (with "Set the plan")
 * may then set their plan through the API; every other workspace is refused.
 */
export default function ExternalBillingWorkspaces() {
  const [search, setSearch] = useState('')
  const [shownFor, setShownFor] = useState('')
  const [workspaces, setWorkspaces] = useState<WorkspaceBilling[]>([])
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<string | null>(null)

  const load = useCallback(async (term: string) => {
    setLoading(true)
    try {
      setWorkspaces(await workspaceBillingApi.list(term || undefined))
      setShownFor(term)
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not load workspaces'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load('')
  }, [load])

  const toggle = async (workspace: WorkspaceBilling) => {
    const next = !workspace.external_billing
    const question = next
      ? `Let "${workspace.name}" set its own plan through the API? Only do this when it pays in another system.`
      : `Stop "${workspace.name}" setting its own plan? Its current plan stays as it is.`
    if (!window.confirm(question)) return
    setSavingId(workspace.id)
    try {
      const updated = await workspaceBillingApi.setExternalBilling(workspace.id, next)
      setWorkspaces((rows) => rows.map((row) => (row.id === updated.id ? updated : row)))
      toast.success(next ? 'External billing is on' : 'External billing is off')
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not save'))
    } finally {
      setSavingId(null)
    }
  }

  return (
    <section className="mt-10 bg-white shadow rounded-lg p-6">
      <h2 className="text-xl font-semibold text-ink mb-2">Workspaces billed in another system</h2>
      <p className="text-sm text-ink-soft mb-6">
        When on, the workspace&apos;s own platform key with &quot;Set the plan&quot; may change its plan, period and
        status through the API. Use it for workspaces that pay in your partner&apos;s system, not in Synkora.
      </p>

      <form
        className="flex flex-wrap gap-3 mb-4"
        onSubmit={(e) => {
          e.preventDefault()
          load(search.trim())
        }}
      >
        <label htmlFor="workspace-search" className="sr-only">
          Workspace name or id
        </label>
        <input
          id="workspace-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Workspace name or id"
          className="flex-1 min-w-[220px] px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-sand hover:bg-line border border-taupe text-ink rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
        >
          Search
        </button>
      </form>

      {loading ? (
        <p className="text-sm text-ink-mute">Loading…</p>
      ) : workspaces.length === 0 ? (
        <p className="text-sm text-ink-mute">
          {shownFor ? `No workspace matches "${shownFor}".` : 'No workspace is billed in another system yet. Search to find one.'}
        </p>
      ) : (
        <ul className="divide-y divide-line border border-line rounded-lg">
          {workspaces.map((workspace) => (
            <li key={workspace.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="font-medium text-ink truncate">{workspace.name}</p>
                <p className="text-xs text-ink-mute font-mono break-all">{workspace.id}</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={workspace.external_billing}
                aria-label={`External billing for ${workspace.name}`}
                disabled={savingId === workspace.id}
                onClick={() => toggle(workspace)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-50 ${
                  workspace.external_billing
                    ? 'bg-leaf-wash text-forest border-leaf'
                    : 'bg-white text-ink-soft border-taupe hover:bg-sand'
                }`}
              >
                {workspace.external_billing ? 'Billed externally' : 'Billed in Synkora'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
