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
  github: 'bg-gray-100 text-gray-700',
  clickup: 'bg-purple-100 text-purple-700',
  jira: 'bg-blue-100 text-blue-700',
  slack: 'bg-pink-100 text-pink-700',
  sentry: 'bg-orange-100 text-orange-700',
  custom: 'bg-amber-100 text-amber-700'
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
          <div className="p-2.5 bg-red-100 rounded-lg flex-shrink-0">
            <Trash2 className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-gray-900">Delete Webhook</h3>
            <p className="text-sm text-gray-600 mt-1">
              Are you sure you want to delete <span className="font-medium text-gray-900">"{webhook.name}"</span>?
              This will permanently remove the webhook and all its event history. This action cannot be undone.
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={deleting}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={deleting}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            {deleting ? 'Deleting...' : 'Delete'}
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
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h3 className="text-base font-semibold text-gray-900">Edit Webhook</h3>
          <button onClick={onCancel} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Webhook Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
              required
            />
          </div>

          {/* Active toggle */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
            <label className="flex items-center gap-3 cursor-pointer">
              <div className="relative">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={formData.is_active}
                  onChange={e => setFormData(prev => ({ ...prev, is_active: e.target.checked }))}
                />
                <div className={`w-10 h-6 rounded-full transition-colors ${formData.is_active ? 'bg-green-500' : 'bg-gray-300'}`} />
                <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${formData.is_active ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
              <span className="text-sm font-medium text-gray-900">{formData.is_active ? 'Active' : 'Inactive'}</span>
            </label>
          </div>

          {/* Event Types */}
          {availableEvents.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Event Types <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 gap-2">
                {availableEvents.map(event => (
                  <label
                    key={event}
                    className={`flex items-center gap-2 p-2.5 border-2 rounded-lg cursor-pointer transition-all text-sm ${
                      formData.event_types.includes(event)
                        ? 'border-red-500 bg-red-50'
                        : 'border-gray-200 hover:border-gray-300 bg-white'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={formData.event_types.includes(event)}
                      onChange={() => toggleEvent(event)}
                      className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500"
                    />
                    <span className="font-medium text-gray-900">{event}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Signature Verification */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Signature Verification</label>
            <label className="flex items-center gap-3 cursor-pointer">
              <div className="relative">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={formData.verify_signature}
                  onChange={e => setFormData(prev => ({ ...prev, verify_signature: e.target.checked }))}
                />
                <div className={`w-10 h-6 rounded-full transition-colors ${formData.verify_signature ? 'bg-red-500' : 'bg-gray-300'}`} />
                <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${formData.verify_signature ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
              <div>
                <span className="text-sm font-medium text-gray-900">{formData.verify_signature ? 'Enabled' : 'Disabled'}</span>
                <p className="text-xs text-gray-500">
                  {formData.verify_signature
                    ? 'Requests without a valid signature will be rejected'
                    : 'All incoming requests will be accepted without signature check'}
                </p>
              </div>
            </label>
          </div>

          {/* Smart filtering (Jev) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Smart filtering (Jev)</label>
            <label className="flex items-center gap-3 cursor-pointer">
              <div className="relative">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={formData.jev_enabled}
                  onChange={e => setFormData(prev => ({ ...prev, jev_enabled: e.target.checked }))}
                />
                <div className={`w-10 h-6 rounded-full transition-colors ${formData.jev_enabled ? 'bg-red-500' : 'bg-gray-300'}`} />
                <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${formData.jev_enabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
              <div>
                <span className="text-sm font-medium text-gray-900">{formData.jev_enabled ? 'Enabled' : 'Disabled'}</span>
                <p className="text-xs text-gray-500">
                  Check each event before running the agent, so routine noise (bot chatter, status changes, &quot;LGTM&quot;)
                  doesn&apos;t use an agent run.
                </p>
              </div>
            </label>

            {formData.jev_enabled && (
              <div className="mt-3 p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-4">
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
                        className="mt-0.5 accent-red-500"
                      />
                      <span>
                        <span className="text-sm font-medium text-gray-900">{label}</span>
                        <span className="block text-xs text-gray-500">{hint}</span>
                      </span>
                    </label>
                  ))}
                </div>

                <div>
                  <label className="flex items-center justify-between text-sm text-gray-700 mb-1.5">
                    <span>Skip only when needs-action is below</span>
                    <span className="font-mono text-xs bg-white border border-gray-200 px-2 py-0.5 rounded">
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
                    className="w-full accent-red-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Lower is safer: fewer events are skipped, more reach the agent.</p>
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-1.5">What should the agent act on? (optional)</label>
                  <textarea
                    value={formData.jev_instructions}
                    onChange={e => setFormData(prev => ({ ...prev, jev_instructions: e.target.value.slice(0, 1000) }))}
                    rows={3}
                    placeholder="Act on new pull requests and failing builds. Ignore bot comments and label changes."
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  />
                </div>

                <p className="text-xs text-slate-600">
                  Event text is sent to TypeSafe for scoring and needs a TypeSafe API key under Settings → Integrations.
                  If TypeSafe is unavailable or unsure, the event runs normally.
                </p>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2 border-t border-gray-200">
            <button
              type="button"
              onClick={onCancel}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 rounded-lg transition-all disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {saving ? 'Saving...' : 'Save Changes'}
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
          <Loader2 className="w-8 h-8 text-red-500 animate-spin mx-auto mb-3" />
          <p className="text-gray-600 text-sm">Loading webhooks...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <div>
              <p className="font-medium text-red-900">Error Loading Webhooks</p>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (webhooks.length === 0) {
    return (
      <div className="p-16 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
          <Webhook className="w-8 h-8 text-red-600" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">No Webhooks Yet</h3>
        <p className="text-gray-600 mb-6 max-w-md mx-auto text-sm">
          Create your first webhook to receive real-time events from GitHub, ClickUp, Jira, Slack, or Sentry.
        </p>
        <button
          onClick={onCreateClick}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 rounded-lg transition-all shadow-sm hover:shadow-md"
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
                className="border border-gray-200 rounded-lg p-5 hover:border-red-300 hover:shadow-sm transition-all bg-white"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4 flex-1">
                    <div className={`p-2.5 rounded-lg ${colorClass}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold text-gray-900">{webhook.name}</h3>
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                          webhook.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            webhook.is_active ? 'bg-green-600' : 'bg-gray-400'
                          }`} />
                          {webhook.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>

                      <div className="flex items-center gap-4 text-sm text-gray-600 mb-3 flex-wrap">
                        <span className="capitalize">{webhook.provider}</span>
                        {webhook.event_types && webhook.event_types.length > 0 && (
                          <>
                            <span className="text-gray-300">•</span>
                            <span>{webhook.event_types.join(', ')}</span>
                          </>
                        )}
                        <span className="text-gray-300">•</span>
                        <span className={`inline-flex items-center gap-1 text-xs font-medium ${webhook.config?.verify_signature !== false ? 'text-green-600' : 'text-gray-400'}`}>
                          {webhook.config?.verify_signature !== false
                            ? <><Shield className="w-3 h-3" /> Signature: On</>
                            : <><ShieldOff className="w-3 h-3" /> Signature: Off</>
                          }
                        </span>
                      </div>

                      <div className="flex items-center gap-2 bg-gray-50 rounded-lg p-3 border border-gray-200">
                        <code className="text-xs text-gray-700 flex-1 truncate font-mono">
                          {`${API_URL}${webhook.webhook_url}`}
                        </code>
                        <button
                          onClick={() => handleCopyUrl(webhook.webhook_url)}
                          className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded transition-colors flex-shrink-0"
                          title="Copy URL"
                        >
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="flex items-center gap-6 mt-3 text-xs text-gray-500">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-green-600">{webhook.success_count || 0}</span>
                          <span>successful</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-red-600">{webhook.failure_count || 0}</span>
                          <span>failed</span>
                        </div>
                        {webhook.last_triggered_at && (
                          <>
                            <span className="text-gray-300">•</span>
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
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
                    >
                      {isDeleting || isSaving ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <MoreVertical className="w-5 h-5" />
                      )}
                    </button>

                    {actionMenuOpen === webhook.id && (
                      <>
                        <div className="fixed inset-0 z-10" onClick={() => setActionMenuOpen(null)} />
                        <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20">
                          <button
                            onClick={() => {
                              setActionMenuOpen(null)
                              setEditTarget(webhook)
                            }}
                            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                          >
                            <Edit className="w-4 h-4" />
                            Edit
                          </button>
                          <button
                            onClick={() => {
                              setActionMenuOpen(null)
                              setDeleteTarget(webhook)
                            }}
                            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
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
