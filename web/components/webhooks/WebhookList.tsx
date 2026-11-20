'use client'

import { useEffect, useState } from 'react'
import {
  Webhook,
  Github,
  MessageSquare,
  CheckSquare,
  Activity,
  Copy,
  Edit,
  Trash2,
  MoreVertical,
  Loader2,
  AlertCircle,
  Plus,
  Save,
  X,
  Shield,
  ShieldOff
} from 'lucide-react'
import { useWebhooks } from '@/hooks/useWebhooks'
import { Webhook as WebhookType } from '@/types/webhooks'
import toast from 'react-hot-toast'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

export interface WebhookListProps {
  agentName: string
  refreshKey?: number
  onCreateClick?: () => void
}

const providerIcons: Record<string, any> = {
  github: Github,
  clickup: CheckSquare,
  jira: Activity,
  slack: MessageSquare,
  sentry: Shield,
  custom: Webhook
}

const providerColors: Record<string, string> = {
  github: 'bg-sand text-ink-soft',
  clickup: 'bg-sand-deep text-ink-soft',
  jira: 'bg-sky-wash text-azure',
  slack: 'bg-sand-deep text-ink-soft',
  sentry: 'bg-sand-deep text-gold',
  custom: 'bg-sand-deep text-gold'
}

const providerEventTypes: Record<string, string[]> = {
  github: ['pull_request', 'issues', 'push', 'release'],
  sentry: ['issue', 'error', 'event_alert', 'issue_alert', 'metric_alert'],
  clickup: ['taskCreated', 'taskUpdated', 'taskDeleted', 'taskCommentPosted'],
  jira: ['issue_created', 'issue_updated', 'issue_deleted', 'comment_created'],
  slack: ['message', 'app_mention', 'reaction_added'],
  custom: ['webhook']
}

// ── Delete confirmation modal ──────────────────────────────────────────────
function DeleteModal({
  webhook,
  onConfirm,
  onCancel,
  deleting
}: {
  webhook: WebhookType
  onConfirm: () => void
  onCancel: () => void
  deleting: boolean
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onCancel} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-start gap-4 mb-5">
          <div className="p-2.5 bg-sand-deep rounded-lg flex-shrink-0">
            <Trash2 className="w-5 h-5 text-leaf" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-ink">Delete Webhook</h3>
            <p className="text-sm text-ink-soft mt-1">
              Are you sure you want to delete <span className="font-medium text-ink">"{webhook.name}"</span>?
              This will permanently remove the webhook and all its event history. This action cannot be undone.
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={deleting}
            className="px-4 py-2 text-sm font-medium text-ink-soft bg-sand rounded-lg hover:bg-line transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={deleting}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-danger hover:bg-danger rounded-lg transition-colors disabled:opacity-50"
          >
            {deleting ? <Loader2 className="w-4 h-4 motion-safe:animate-spin" /> : <Trash2 className="w-4 h-4" />}
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Edit modal ─────────────────────────────────────────────────────────────
function EditModal({
  webhook,
  onSave,
  onCancel,
  saving
}: {
  webhook: WebhookType
  onSave: (data: { name: string; is_active: boolean; event_types: string[]; config: Record<string, any> }) => void
  onCancel: () => void
  saving: boolean
}) {
  const [formData, setFormData] = useState({
    name: webhook.name,
    is_active: webhook.is_active,
    event_types: webhook.event_types || [],
    verify_signature: webhook.config?.verify_signature !== false,
    jev_enabled: webhook.config?.jev_gate?.enabled === true,
    jev_mode: (webhook.config?.jev_gate?.mode === 'enforce' ? 'enforce' : 'shadow') as 'shadow' | 'enforce',
    jev_min_actionable: Number(webhook.config?.jev_gate?.min_actionable ?? 0.2),
    jev_instructions: (webhook.config?.jev_gate?.instructions as string | undefined) ?? ''
  })

  const availableEvents = providerEventTypes[webhook.provider.toLowerCase()] || []

  const toggleEvent = (event: string) => {
    setFormData(prev => ({
      ...prev,
      event_types: prev.event_types.includes(event)
        ? prev.event_types.filter(e => e !== event)
        : [...prev.event_types, event]
    }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      toast.error('Please enter a webhook name')
      return
    }
    if (formData.event_types.length === 0) {
      toast.error('Please select at least one event type')
      return
    }
    const config: Record<string, any> = { ...(webhook.config || {}), verify_signature: formData.verify_signature }
    // Keep stored gate settings when switching it off; only add the key once it has been used.
    if (formData.jev_enabled || webhook.config?.jev_gate) {
      config.jev_gate = {
        ...(webhook.config?.jev_gate || {}),
        enabled: formData.jev_enabled,
        mode: formData.jev_mode,
        min_actionable: formData.jev_min_actionable,
        instructions: formData.jev_instructions.trim()
      }
    }
    onSave({
      name: formData.name,
      is_active: formData.is_active,
      event_types: formData.event_types,
      config
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onCancel} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <h3 className="text-base font-semibold text-ink">Edit Webhook</h3>
          <button onClick={onCancel} className="p-1.5 text-ash hover:text-ink-soft hover:bg-sand rounded-lg transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-1.5">
              Webhook Name <span className="text-leaf">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
              required
            />
          </div>

          {/* Active toggle */}
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-2">Status</label>
            <label className="flex items-center gap-3 cursor-pointer">
              <div className="relative">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={formData.is_active}
                  onChange={e => setFormData(prev => ({ ...prev, is_active: e.target.checked }))}
                />
                <div className={`w-10 h-6 rounded-full transition-colors ${formData.is_active ? 'bg-leaf' : 'bg-taupe'}`} />
                <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform motion-reduce:transition-none ${formData.is_active ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
              <span className="text-sm font-medium text-ink">{formData.is_active ? 'Active' : 'Inactive'}</span>
            </label>
          </div>

          {/* Event Types */}
          {availableEvents.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-ink-soft mb-2">
                Event Types <span className="text-leaf">*</span>
              </label>
              <div className="grid grid-cols-2 gap-2">
                {availableEvents.map(event => (
                  <label
                    key={event}
                    className={`flex items-center gap-2 p-2.5 border-2 rounded-lg cursor-pointer transition-[color,background-color,border-color,box-shadow,opacity,transform] text-sm ${
                      formData.event_types.includes(event)
                        ? 'border-ink bg-blush-wash'
                        : 'border-line hover:border-taupe bg-white'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={formData.event_types.includes(event)}
                      onChange={() => toggleEvent(event)}
                      className="w-4 h-4 text-leaf border-taupe rounded focus:ring-ink"
                    />
                    <span className="font-medium text-ink">{event}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Signature Verification */}
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-2">Signature Verification</label>
            <label className="flex items-center gap-3 cursor-pointer">
              <div className="relative">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={formData.verify_signature}
                  onChange={e => setFormData(prev => ({ ...prev, verify_signature: e.target.checked }))}
                />
                <div className={`w-10 h-6 rounded-full transition-colors ${formData.verify_signature ? 'bg-ink' : 'bg-taupe'}`} />
                <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform motion-reduce:transition-none ${formData.verify_signature ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
              <div>
                <span className="text-sm font-medium text-ink">{formData.verify_signature ? 'Enabled' : 'Disabled'}</span>
                <p className="text-xs text-ink-mute">
                  {formData.verify_signature
                    ? 'Requests without a valid signature will be rejected'
                    : 'All incoming requests will be accepted without signature check'}
                </p>
              </div>
            </label>
          </div>

          {/* Smart filtering (Jev) */}
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-2">Smart filtering (Jev)</label>
            <label className="flex items-center gap-3 cursor-pointer">
              <div className="relative">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={formData.jev_enabled}
                  onChange={e => setFormData(prev => ({ ...prev, jev_enabled: e.target.checked }))}
                />
                <div className={`w-10 h-6 rounded-full transition-colors ${formData.jev_enabled ? 'bg-ink' : 'bg-taupe'}`} />
                <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform motion-reduce:transition-none ${formData.jev_enabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
              <div>
                <span className="text-sm font-medium text-ink">{formData.jev_enabled ? 'Enabled' : 'Disabled'}</span>
                <p className="text-xs text-ink-mute">
                  Check each event before running the agent, so routine noise (bot chatter, status changes, &quot;LGTM&quot;)
                  doesn&apos;t use an agent run.
                </p>
              </div>
            </label>

            {formData.jev_enabled && (
              <div className="mt-3 p-4 bg-cream border border-line rounded-lg space-y-4">
                <div className="space-y-2">
                  {([
                    ['shadow', 'Test only', 'Score every event and record it, but always run the agent. Start here.'],
                    ['enforce', 'Skip noise', 'Skip events that are confidently not actionable. Skipped events stay in the event log.']
                  ] as const).map(([value, label, hint]) => (
                    <label key={value} className="flex items-start gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="jev_mode"
                        checked={formData.jev_mode === value}
                        onChange={() => setFormData(prev => ({ ...prev, jev_mode: value }))}
                        className="mt-0.5 accent-brand"
                      />
                      <span>
                        <span className="text-sm font-medium text-ink">{label}</span>
                        <span className="block text-xs text-ink-mute">{hint}</span>
                      </span>
                    </label>
                  ))}
                </div>

                <div>
                  <label className="flex items-center justify-between text-sm text-ink-soft mb-1.5">
                    <span>Skip only when needs-action is below</span>
                    <span className="font-mono text-xs bg-white border border-line px-2 py-0.5 rounded">
                      {Math.round(formData.jev_min_actionable * 100)}%
                    </span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={0.5}
                    step={0.05}
                    value={formData.jev_min_actionable}
                    onChange={e => setFormData(prev => ({ ...prev, jev_min_actionable: parseFloat(e.target.value) }))}
                    className="w-full accent-brand"
                  />
                  <p className="text-xs text-ink-mute mt-1">Lower is safer: fewer events are skipped, more reach the agent.</p>
                </div>

                <div>
                  <label className="block text-sm text-ink-soft mb-1.5">What should the agent act on? (optional)</label>
                  <textarea
                    value={formData.jev_instructions}
                    onChange={e => setFormData(prev => ({ ...prev, jev_instructions: e.target.value.slice(0, 1000) }))}
                    rows={3}
                    placeholder="Act on new pull requests and failing builds. Ignore bot comments and label changes."
                    className="w-full px-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent"
                  />
                </div>

                <p className="text-xs text-ink-soft">
                  Event text is sent to TypeSafe for scoring and needs a TypeSafe API key under Settings → Integrations.
                  If TypeSafe is unavailable or unsure, the event runs normally.
                </p>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2 border-t border-line">
            <button
              type="button"
              onClick={onCancel}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-ink-soft bg-sand rounded-lg hover:bg-line transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-ink hover:bg-ink/85 rounded-lg transition-[color,background-color,border-color,box-shadow,opacity,transform] disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 motion-safe:animate-spin" /> : <Save className="w-4 h-4" />}
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────
export function WebhookList({ agentName, refreshKey = 0, onCreateClick }: WebhookListProps) {
  const { webhooks, isLoading: loading, error, deleteWebhook, updateWebhook } = useWebhooks(agentName)
  const [actionMenuOpen, setActionMenuOpen] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<WebhookType | null>(null)
  const [editTarget, setEditTarget] = useState<WebhookType | null>(null)

  const handleCopyUrl = (url: string) => {
    const fullUrl = `${API_URL}${url}`
    navigator.clipboard.writeText(fullUrl)
    toast.success('Webhook URL copied to clipboard')
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setDeleting(deleteTarget.id)
    try {
      await deleteWebhook(deleteTarget.id)
      toast.success('Webhook deleted successfully')
      setDeleteTarget(null)
    } catch (error: any) {
      toast.error(error.message || 'Failed to delete webhook')
    } finally {
      setDeleting(null)
    }
  }

  const handleEditSave = async (data: { name: string; is_active: boolean; event_types: string[]; config: Record<string, any> }) => {
    if (!editTarget) return
    setSaving(editTarget.id)
    try {
      await updateWebhook(editTarget.id, data)
      toast.success('Webhook updated successfully')
      setEditTarget(null)
    } catch (error: any) {
      toast.error(error.message || 'Failed to update webhook')
    } finally {
      setSaving(null)
    }
  }

  if (loading && webhooks.length === 0) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-leaf motion-safe:animate-spin mx-auto mb-3" />
          <p className="text-ink-soft text-sm">Loading webhooks…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-blush-wash border border-blush rounded-lg p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-danger flex-shrink-0" />
            <div>
              <p className="font-medium text-wine">Error Loading Webhooks</p>
              <p className="text-sm text-danger mt-1">{error}</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (webhooks.length === 0) {
    return (
      <div className="p-16 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-sand-deep rounded-full mb-4">
          <Webhook className="w-8 h-8 text-leaf" />
        </div>
        <h3 className="text-lg font-semibold text-ink mb-2">No Webhooks Yet</h3>
        <p className="text-ink-soft mb-6 max-w-md mx-auto text-sm">
          Create your first webhook to receive real-time events from GitHub, ClickUp, Jira, Slack, or Sentry.
        </p>
        <button
          onClick={onCreateClick}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-ink hover:bg-ink/85 rounded-lg transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm hover:shadow-md"
        >
          <Plus className="w-4 h-4" />
          Create Webhook
        </button>
      </div>
    )
  }

  return (
    <>
      <div className="p-6">
        <div className="grid gap-4">
          {webhooks.map((webhook) => {
            const Icon = providerIcons[webhook.provider.toLowerCase()] || Webhook
            const colorClass = providerColors[webhook.provider.toLowerCase()] || providerColors.custom
            const isDeleting = deleting === webhook.id
            const isSaving = saving === webhook.id

            return (
              <div
                key={webhook.id}
                className="border border-line rounded-lg p-5 hover:border-blush hover:shadow-sm transition-[color,background-color,border-color,box-shadow,opacity,transform] bg-white"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4 flex-1">
                    <div className={`p-2.5 rounded-lg ${colorClass}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold text-ink">{webhook.name}</h3>
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                          webhook.is_active
                            ? 'bg-leaf-wash text-forest'
                            : 'bg-sand text-ink-soft'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            webhook.is_active ? 'bg-leaf' : 'bg-ash'
                          }`} />
                          {webhook.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>

                      <div className="flex items-center gap-4 text-sm text-ink-soft mb-3 flex-wrap">
                        <span className="capitalize">{webhook.provider}</span>
                        {webhook.event_types && webhook.event_types.length > 0 && (
                          <>
                            <span className="text-taupe">•</span>
                            <span>{webhook.event_types.join(', ')}</span>
                          </>
                        )}
                        <span className="text-taupe">•</span>
                        <span className={`inline-flex items-center gap-1 text-xs font-medium ${webhook.config?.verify_signature !== false ? 'text-leaf' : 'text-ash'}`}>
                          {webhook.config?.verify_signature !== false
                            ? <><Shield className="w-3 h-3" /> Signature: On</>
                            : <><ShieldOff className="w-3 h-3" /> Signature: Off</>
                          }
                        </span>
                      </div>

                      <div className="flex items-center gap-2 bg-cream rounded-lg p-3 border border-line">
                        <code className="text-xs text-ink-soft flex-1 truncate font-mono">
                          {`${API_URL}${webhook.webhook_url}`}
                        </code>
                        <button
                          onClick={() => handleCopyUrl(webhook.webhook_url)}
                          className="p-1.5 text-ink-mute hover:text-leaf hover:bg-blush-wash rounded transition-colors flex-shrink-0"
                          title="Copy URL"
                        >
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="flex items-center gap-6 mt-3 text-xs text-ink-mute">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-leaf">{webhook.success_count || 0}</span>
                          <span>successful</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-danger">{webhook.failure_count || 0}</span>
                          <span>failed</span>
                        </div>
                        {webhook.last_triggered_at && (
                          <>
                            <span className="text-taupe">•</span>
                            <span>Last triggered {new Date(webhook.last_triggered_at).toLocaleDateString()}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="relative ml-4">
                    <button
                      onClick={() => setActionMenuOpen(actionMenuOpen === webhook.id ? null : webhook.id)}
                      disabled={isDeleting || isSaving}
                      className="p-2 text-ash hover:text-ink-soft hover:bg-sand rounded-lg transition-colors disabled:opacity-50"
                    >
                      {isDeleting || isSaving ? (
                        <Loader2 className="w-5 h-5 motion-safe:animate-spin" />
                      ) : (
                        <MoreVertical className="w-5 h-5" />
                      )}
                    </button>

                    {actionMenuOpen === webhook.id && (
                      <>
                        <div className="fixed inset-0 z-10" onClick={() => setActionMenuOpen(null)} />
                        <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-line py-1 z-20">
                          <button
                            onClick={() => {
                              setActionMenuOpen(null)
                              setEditTarget(webhook)
                            }}
                            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-ink-soft hover:bg-cream transition-colors"
                          >
                            <Edit className="w-4 h-4" />
                            Edit
                          </button>
                          <button
                            onClick={() => {
                              setActionMenuOpen(null)
                              setDeleteTarget(webhook)
                            }}
                            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-danger hover:bg-blush-wash transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                            Delete
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <DeleteModal
          webhook={deleteTarget}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
          deleting={deleting === deleteTarget.id}
        />
      )}

      {/* Edit modal */}
      {editTarget && (
        <EditModal
          webhook={editTarget}
          onSave={handleEditSave}
          onCancel={() => setEditTarget(null)}
          saving={saving === editTarget.id}
        />
      )}
    </>
  )
}
