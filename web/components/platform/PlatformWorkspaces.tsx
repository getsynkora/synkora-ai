'use client'

import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { extractErrorMessage } from '@/lib/api/error'
import { platformWorkspacesApi, type PlatformWorkspace } from '@/lib/api/platform-workspaces'

const OWNER_STATUS: Record<string, { label: string; tone: string }> = {
  ACTIVE: { label: 'Active', tone: 'bg-leaf-wash text-forest border-leaf' },
  INACTIVE: { label: 'Email not verified', tone: 'bg-sand text-ink-soft border-taupe' },
  SUSPENDED: { label: 'Suspended', tone: 'bg-white text-ink-soft border-taupe' },
  DELETED: { label: 'Deleted', tone: 'bg-white text-ink-mute border-line' },
}

const buttonClass =
  'px-3 py-1.5 rounded-lg text-sm font-medium border border-taupe bg-white text-ink-soft hover:bg-sand transition-colors disabled:opacity-50'

/**
 * Platform admins: find a workspace by name, id or its owner's email, then suspend or reactivate it, activate its
 * owner (which also verifies an owner who never got the verification email) or suspend them, and mark it billed in
 * another system.
 */
export default function PlatformWorkspaces() {
  const [search, setSearch] = useState('')
  const [shownFor, setShownFor] = useState('')
  const [workspaces, setWorkspaces] = useState<PlatformWorkspace[]>([])
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<string | null>(null)

  const load = useCallback(async (term: string) => {
    setLoading(true)
    try {
      setWorkspaces(await platformWorkspacesApi.list(term || undefined))
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

  const save = async (
    workspace: PlatformWorkspace,
    question: string,
    action: () => Promise<PlatformWorkspace>,
    done: string
  ) => {
    if (!window.confirm(question)) return
    setSavingId(workspace.id)
    try {
      const updated = await action()
      setWorkspaces((rows) => rows.map((row) => (row.id === updated.id ? updated : row)))
      toast.success(done)
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not save'))
    } finally {
      setSavingId(null)
    }
  }

  const toggleWorkspace = (workspace: PlatformWorkspace) => {
    const suspending = workspace.status === 'ACTIVE'
    return save(
      workspace,
      suspending
        ? `Suspend "${workspace.name}"? Its members cannot use it, and its API keys and widgets stop working.`
        : `Reactivate "${workspace.name}"?`,
      () => platformWorkspacesApi.update(workspace.id, { status: suspending ? 'SUSPENDED' : 'ACTIVE' }),
      suspending ? 'Workspace suspended' : 'Workspace reactivated'
    )
  }

  const toggleOwner = (workspace: PlatformWorkspace) => {
    const owner = workspace.owner
    if (!owner) return
    const suspending = owner.status === 'ACTIVE'
    const question = suspending
      ? `Suspend ${owner.email}? They are signed out and cannot sign in again until reactivated.`
      : owner.status === 'INACTIVE'
        ? `Verify ${owner.email} and activate the account? Only do this when you know the address is theirs.`
        : `Reactivate ${owner.email}?`
    return save(
      workspace,
      question,
      () => platformWorkspacesApi.setOwnerStatus(workspace.id, suspending ? 'SUSPENDED' : 'ACTIVE'),
      suspending ? 'Owner suspended' : 'Owner is active'
    )
  }

  const toggleBilling = (workspace: PlatformWorkspace) => {
    const next = !workspace.external_billing
    return save(
      workspace,
      next
        ? `Let "${workspace.name}" set its own plan through the API? Only do this when it pays in another system.`
        : `Stop "${workspace.name}" setting its own plan? Its current plan stays as it is.`,
      () => platformWorkspacesApi.update(workspace.id, { external_billing: next }),
      next ? 'External billing is on' : 'External billing is off'
    )
  }

  return (
    <section className="mt-10 bg-white shadow rounded-lg p-6">
      <h2 className="text-xl font-semibold text-ink mb-2">Workspaces</h2>
      <p className="text-sm text-ink-soft mb-6">
        Find a workspace by its name, id or owner&apos;s email. Suspend it, activate its owner (this also verifies an
        owner who never got the verification email), or let it set its own plan when it pays in a partner&apos;s
        system.
      </p>

      <form
        className="flex flex-wrap gap-3 mb-4"
        onSubmit={(e) => {
          e.preventDefault()
          load(search.trim())
        }}
      >
        <label htmlFor="workspace-search" className="sr-only">
          Workspace name, id or owner email
        </label>
        <input
          id="workspace-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Workspace name, id or owner email"
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
          {shownFor
            ? `No workspace matches "${shownFor}".`
            : 'No workspace is billed in another system yet. Search to find any workspace.'}
        </p>
      ) : (
        <ul className="divide-y divide-line border border-line rounded-lg">
          {workspaces.map((workspace) => {
            const owner = workspace.owner
            const ownerStatus = owner ? OWNER_STATUS[owner.status] || OWNER_STATUS.SUSPENDED : null
            const busy = savingId === workspace.id
            return (
              <li key={workspace.id} className="grid gap-3 px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-ink truncate">
                      {workspace.name}
                      {workspace.status !== 'ACTIVE' && (
                        <span className="ml-2 px-2 py-0.5 rounded-full border border-taupe text-xs text-ink-soft">
                          Suspended
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-ink-mute font-mono break-all">{workspace.id}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" disabled={busy} onClick={() => toggleWorkspace(workspace)} className={buttonClass}>
                      {workspace.status === 'ACTIVE' ? 'Suspend workspace' : 'Reactivate workspace'}
                    </button>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={workspace.external_billing}
                      aria-label={`External billing for ${workspace.name}`}
                      disabled={busy}
                      onClick={() => toggleBilling(workspace)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-50 ${
                        workspace.external_billing
                          ? 'bg-leaf-wash text-forest border-leaf'
                          : 'bg-white text-ink-soft border-taupe hover:bg-sand'
                      }`}
                    >
                      {workspace.external_billing ? 'Billed externally' : 'Billed in Synkora'}
                    </button>
                  </div>
                </div>

                {owner && ownerStatus ? (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-paper px-3 py-2">
                    <p className="min-w-0 text-sm text-ink-soft">
                      Owner <span className="font-medium text-ink">{owner.name}</span>{' '}
                      <span className="break-all">{owner.email}</span>
                      <span className={`ml-2 px-2 py-0.5 rounded-full border text-xs ${ownerStatus.tone}`}>
                        {ownerStatus.label}
                      </span>
                    </p>
                    {owner.status !== 'DELETED' && (
                      <button type="button" disabled={busy} onClick={() => toggleOwner(workspace)} className={buttonClass}>
                        {owner.status === 'ACTIVE'
                          ? 'Suspend owner'
                          : owner.status === 'INACTIVE'
                            ? 'Verify and activate'
                            : 'Reactivate owner'}
                      </button>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-ink-mute">No owner</p>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
