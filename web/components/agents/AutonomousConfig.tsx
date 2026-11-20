'use client'

import { useState } from 'react'
import { extractErrorMessage } from '@/lib/api/error'
import { Save, Play, ShieldCheck } from 'lucide-react'

interface AutonomousStatus {
  enabled: boolean
  task_id?: string
  goal?: string
  schedule?: string
  max_steps?: number
  is_active?: boolean
  // HITL approval settings
  require_approval?: boolean
  approval_mode?: string
  require_approval_tools?: string[]
  approval_channel?: string
  approval_channel_config?: Record<string, string>
  approval_timeout_minutes?: number
}

interface Props {
  agentName: string
  status: AutonomousStatus
  onSaved: () => void
  onTriggered: () => void
}

const SCHEDULE_OPTIONS = [
  { value: '5min', label: 'Every 5 minutes' },
  { value: '15min', label: 'Every 15 minutes' },
  { value: '30min', label: 'Every 30 minutes' },
  { value: 'hourly', label: 'Every hour' },
  { value: 'daily', label: 'Daily (9 AM)' },
  { value: 'weekly', label: 'Weekly (Mon 9 AM)' },
  { value: 'custom', label: 'Custom cron…' },
]

export function AutonomousConfig({ agentName, status, onSaved, onTriggered }: Props) {
  const isNew = !status.task_id

  const [goal, setGoal] = useState(status.goal ?? '')
  const [scheduleOption, setScheduleOption] = useState(() => {
    if (!status.schedule) return 'hourly'
    const known = SCHEDULE_OPTIONS.find(o => o.value === status.schedule)
    return known ? known.value : 'custom'
  })
  const [customCron, setCustomCron] = useState(
    scheduleOption === 'custom' ? (status.schedule ?? '') : ''
  )
  const [maxSteps, setMaxSteps] = useState(status.max_steps ?? 20)

  // HITL approval settings
  const [requireApproval, setRequireApproval] = useState(status.require_approval ?? false)
  const [approvalMode, setApprovalMode] = useState<'smart' | 'explicit'>(
    (status.approval_mode as 'smart' | 'explicit') ?? 'smart'
  )
  const [approvalTools, setApprovalTools] = useState(
    (status.require_approval_tools ?? []).join(', ')
  )
  const [approvalChannel, setApprovalChannel] = useState(status.approval_channel ?? 'chat')
  const [channelConfigRaw, setChannelConfigRaw] = useState(
    status.approval_channel_config && Object.keys(status.approval_channel_config).length > 0
      ? JSON.stringify(status.approval_channel_config, null, 2)
      : ''
  )
  const [approvalTimeout, setApprovalTimeout] = useState(status.approval_timeout_minutes ?? 60)

  const [saving, setSaving] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const effectiveSchedule = scheduleOption === 'custom' ? customCron : scheduleOption

  async function handleSave() {
    setError(null)
    setSaving(true)
    try {
      const { apiClient } = await import('@/lib/api/client')
      const url = `/api/v1/agents/${encodeURIComponent(agentName)}/autonomous`
      let channelConfig: Record<string, string> = {}
      if (channelConfigRaw.trim()) {
        try {
          channelConfig = JSON.parse(channelConfigRaw)
        } catch {
          setError('Approval channel config must be valid JSON')
          setSaving(false)
          return
        }
      }

      const body: Record<string, unknown> = {
        goal,
        schedule: effectiveSchedule,
        max_steps: maxSteps,
        require_approval: requireApproval,
        approval_mode: approvalMode,
        require_approval_tools: approvalMode === 'explicit'
          ? approvalTools.split(',').map(s => s.trim()).filter(Boolean)
          : [],
        approval_channel: approvalChannel || null,
        approval_channel_config: channelConfig,
        approval_timeout_minutes: approvalTimeout,
      }

      if (isNew) {
        await apiClient.request('POST', url, body)
      } else {
        await apiClient.request('PATCH', url, body)
      }
      onSaved()
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Save failed'))
    } finally {
      setSaving(false)
    }
  }

  async function handleTrigger() {
    setError(null)
    setTriggering(true)
    try {
      const { apiClient } = await import('@/lib/api/client')
      await apiClient.request(
        'POST',
        `/api/v1/agents/${encodeURIComponent(agentName)}/autonomous/trigger`
      )
      onTriggered()
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Trigger failed'))
    } finally {
      setTriggering(false)
    }
  }

  return (
    <div className="space-y-5">
      {error && (
        <div className="rounded-md bg-blush-wash border border-blush px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {/* Goal */}
      <div>
        <label className="block text-sm font-medium text-ink-soft mb-1">Goal</label>
        <textarea
          rows={4}
          className="w-full rounded-md border border-taupe px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ink"
          placeholder="What should this agent do on every run? Be specific."
          value={goal}
          onChange={e => setGoal(e.target.value)}
        />
      </div>

      {/* Schedule */}
      <div>
        <label className="block text-sm font-medium text-ink-soft mb-1">Schedule</label>
        <div className="flex flex-wrap gap-2">
          {SCHEDULE_OPTIONS.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setScheduleOption(opt.value)}
              className={`px-3 py-1.5 rounded-md text-sm border transition-colors ${
                scheduleOption === opt.value
                  ? 'bg-ink text-white border-ink'
                  : 'bg-white text-ink-soft border-taupe hover:border-hotpink'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {scheduleOption === 'custom' && (
          <input
            type="text"
            className="mt-2 w-full rounded-md border border-taupe px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ink"
            placeholder="e.g. 0 */4 * * *"
            value={customCron}
            onChange={e => setCustomCron(e.target.value)}
          />
        )}
      </div>

      {/* Max steps */}
      <div>
        <label className="block text-sm font-medium text-ink-soft mb-1">
          Max steps per run
        </label>
        <input
          type="number"
          min={1}
          max={100}
          className="w-32 rounded-md border border-taupe px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ink"
          value={maxSteps}
          onChange={e => setMaxSteps(parseInt(e.target.value, 10) || 20)}
        />
        <p className="mt-1 text-xs text-ink-mute">
          Tool-call budget per execution (1–100).
        </p>
      </div>

      {/* Human Approval */}
      <div className="border border-line rounded-lg p-4 space-y-4">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-4 h-4 text-ink-mute" />
          <span className="text-sm font-medium text-ink-soft">Human-in-the-Loop Approval</span>
          <label className="ml-auto flex items-center gap-2 cursor-pointer">
            <span className="text-xs text-ink-mute">{requireApproval ? 'On' : 'Off'}</span>
            <button
              type="button"
              role="switch"
              aria-checked={requireApproval}
              onClick={() => setRequireApproval(v => !v)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                requireApproval ? 'bg-ink' : 'bg-line'
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform motion-reduce:transition-none ${
                  requireApproval ? 'translate-x-4.5' : 'translate-x-0.5'
                }`}
              />
            </button>
          </label>
        </div>

        {requireApproval && (
          <div className="space-y-3 pl-7">
            {/* Approval mode */}
            <div>
              <label className="block text-xs font-medium text-ink-soft mb-1">Mode</label>
              <div className="flex gap-2">
                {(['smart', 'explicit'] as const).map(m => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setApprovalMode(m)}
                    className={`px-3 py-1.5 rounded-md text-xs border transition-colors ${
                      approvalMode === m
                        ? 'bg-ink text-white border-ink'
                        : 'bg-white text-ink-soft border-taupe hover:border-hotpink'
                    }`}
                  >
                    {m === 'smart' ? 'Smart (auto-detect action tools)' : 'Explicit (specify tools)'}
                  </button>
                ))}
              </div>
              <p className="mt-1 text-xs text-ash">
                {approvalMode === 'smart'
                  ? 'Automatically gates tools that write, post, send, or modify data.'
                  : 'Only gate the specific tools you list below.'}
              </p>
            </div>

            {/* Explicit tool list */}
            {approvalMode === 'explicit' && (
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">
                  Tools to gate (comma-separated)
                </label>
                <input
                  type="text"
                  className="w-full rounded-md border border-taupe px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-ink"
                  placeholder="internal_twitter_post_tweet, internal_send_email"
                  value={approvalTools}
                  onChange={e => setApprovalTools(e.target.value)}
                />
              </div>
            )}

            {/* Notification channel */}
            <div>
              <label className="block text-xs font-medium text-ink-soft mb-1">Approval channel</label>
              <select
                className="w-full rounded-md border border-taupe px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-ink"
                value={approvalChannel}
                onChange={e => setApprovalChannel(e.target.value)}
              >
                <option value="chat">Dashboard Chat (memory conversation)</option>
                <option value="slack">Slack</option>
                <option value="whatsapp">WhatsApp Business</option>
                <option value="whatsapp_web">WhatsApp Web (device-linked)</option>
              </select>
            </div>

            {/* Channel config */}
            {approvalChannel !== 'chat' && (
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">
                  Channel config (JSON)
                </label>
                <textarea
                  rows={3}
                  className="w-full rounded-md border border-taupe px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-ink"
                  placeholder={
                    approvalChannel === 'slack'
                      ? '{"channel_id": "C0123ABCDEF"}'
                      : approvalChannel === 'whatsapp'
                      ? '{"bot_id": "uuid", "to_phone": "+1234567890"}'
                      : '{"session_id": "wa-xyz", "to_phone": "+1234567890"}'
                  }
                  value={channelConfigRaw}
                  onChange={e => setChannelConfigRaw(e.target.value)}
                />
              </div>
            )}

            {/* Timeout */}
            <div>
              <label className="block text-xs font-medium text-ink-soft mb-1">
                Approval timeout (minutes)
              </label>
              <input
                type="number"
                min={5}
                max={1440}
                className="w-28 rounded-md border border-taupe px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-ink"
                value={approvalTimeout}
                onChange={e => setApprovalTimeout(parseInt(e.target.value, 10) || 60)}
              />
              <p className="mt-1 text-xs text-ash">
                If not approved within this window the action is cancelled.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !goal.trim() || !effectiveSchedule.trim()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium text-white bg-ink hover:bg-danger disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Save className="w-4 h-4" />
          {saving ? 'Saving…' : isNew ? 'Enable' : 'Save'}
        </button>

        {!isNew && (
          <button
            type="button"
            onClick={handleTrigger}
            disabled={triggering}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium text-leaf border border-blush hover:bg-blush-wash disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Play className="w-4 h-4" />
            {triggering ? 'Queuing…' : 'Run Now'}
          </button>
        )}
      </div>
    </div>
  )
}
