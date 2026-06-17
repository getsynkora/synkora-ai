'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import toast from 'react-hot-toast'
import { Video, Send, Trash2, ChevronDown, ChevronRight, RefreshCw, Clock } from 'lucide-react'
import {
  dispatchMeetingBot,
  listMeetings,
  removeMeetingBot,
  getMeetingTranscript,
  type MeetingBot,
  type MeetingTranscript,
} from '@/lib/api/voice-meetings'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  ready: { label: 'Ready', color: 'text-gray-500' },
  joining_call: { label: 'Joining…', color: 'text-blue-500' },
  in_waiting_room: { label: 'Waiting Room', color: 'text-yellow-500' },
  in_call_not_recording: { label: 'In Call', color: 'text-blue-600' },
  in_call_recording: { label: 'Recording', color: 'text-green-600' },
  call_ended: { label: 'Call Ended', color: 'text-gray-400' },
  done: { label: 'Done', color: 'text-gray-500' },
  fatal: { label: 'Error', color: 'text-red-500' },
}

function BotStatusBadge({ code }: { code: string }) {
  const info = STATUS_LABELS[code] ?? { label: code, color: 'text-gray-500' }
  return <span className={`text-xs font-medium ${info.color}`}>{info.label}</span>
}

function TranscriptViewer({ agentSlug, botId }: { agentSlug: string; botId: string }) {
  const [transcript, setTranscript] = useState<MeetingTranscript | null>(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const data = await getMeetingTranscript(agentSlug, botId)
      setTranscript(data)
    } catch {
      toast.error('Failed to load transcript')
    } finally {
      setLoading(false)
    }
  }

  const toggle = () => {
    if (!open && !transcript) load()
    setOpen(!open)
  }

  return (
    <div className="mt-2">
      <button onClick={toggle} className="flex items-center gap-1 text-xs text-red-500 hover:underline">
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {open ? 'Hide transcript' : 'View transcript'}
      </button>
      {open && (
        <div className="mt-2 p-3 bg-gray-50 rounded text-xs text-gray-700 max-h-64 overflow-y-auto space-y-2">
          {loading && <p className="text-gray-400">Loading transcript…</p>}
          {!loading && !transcript && <p className="text-gray-400">No transcript available yet.</p>}
          {transcript?.segments.map((seg, i) => (
            <div key={i}>
              <span className="font-semibold text-gray-900">{seg.speaker}: </span>
              {seg.text}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AgentMeetingsPage() {
  const params = useParams()
  const agentName = decodeURIComponent(params?.agentName as string || '')

  const [bots, setBots] = useState<MeetingBot[]>([])
  const [loadingBots, setLoadingBots] = useState(true)
  const [meetingUrl, setMeetingUrl] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [dispatching, setDispatching] = useState(false)
  const [removingId, setRemovingId] = useState<string | null>(null)

  const fetchBots = useCallback(async () => {
    setLoadingBots(true)
    try {
      const data = await listMeetings(agentName)
      setBots(data.bots)
    } catch {
      // meeting bot may not be configured — silently show empty state
      setBots([])
    } finally {
      setLoadingBots(false)
    }
  }, [agentName])

  useEffect(() => { fetchBots() }, [fetchBots])

  const handleDispatch = async () => {
    if (!meetingUrl.trim()) {
      toast.error('Please enter a meeting URL')
      return
    }
    setDispatching(true)
    try {
      const bot = await dispatchMeetingBot(agentName, meetingUrl.trim(), scheduledAt || undefined)
      toast.success(`Bot dispatched: ${bot.bot_name}`)
      setMeetingUrl('')
      setScheduledAt('')
      await fetchBots()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? 'Failed to dispatch bot')
    } finally {
      setDispatching(false)
    }
  }

  const handleRemove = async (botId: string) => {
    setRemovingId(botId)
    try {
      await removeMeetingBot(agentName, botId)
      toast.success('Bot removed from meeting')
      await fetchBots()
    } catch {
      toast.error('Failed to remove bot')
    } finally {
      setRemovingId(null)
    }
  }

  const activeStatuses = new Set(['ready', 'joining_call', 'in_waiting_room', 'in_call_not_recording', 'in_call_recording'])
  const activeBots = bots.filter((b) => activeStatuses.has(b.status_code))
  const pastBots = bots.filter((b) => !activeStatuses.has(b.status_code))

  return (
    <AgentPageShell
      agentName={agentName}
      title="Meetings"
      description="Dispatch your agent to meetings and review transcripts from past sessions."
      icon={Video}
      badge="Meeting Bot"
    >
      <AgentPagePanel>
        <div className="space-y-8 p-6 md:p-8">
          {/* Dispatch */}
          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Send className="w-4 h-4" />
              Send Agent to Meeting
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Meeting URL</label>
                <input
                  type="url"
                  value={meetingUrl}
                  onChange={(e) => setMeetingUrl(e.target.value)}
                  placeholder="https://zoom.us/j/… or https://meet.google.com/…"
                  className="w-full border rounded px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Scheduled Time <span className="text-gray-400">(leave blank to join immediately)</span>
                </label>
                <input
                  type="datetime-local"
                  value={scheduledAt}
                  onChange={(e) => setScheduledAt(e.target.value)}
                  className="w-full border rounded px-3 py-2 text-sm"
                />
              </div>
              <div className="flex justify-end pt-1">
                <button
                  onClick={handleDispatch}
                  disabled={dispatching}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium text-white bg-red-500 hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <Video className="w-4 h-4" />
                  {dispatching ? 'Dispatching…' : 'Dispatch Bot'}
                </button>
              </div>
            </div>
          </section>

          {/* Active Bots */}
          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2 justify-between">
              <span className="flex items-center gap-2">
                <Video className="w-4 h-4" />
                Active Bots
              </span>
              <button onClick={fetchBots} className="text-gray-400 hover:text-gray-600">
                <RefreshCw className="w-4 h-4" />
              </button>
            </h2>
            {loadingBots ? (
              <p className="text-sm text-gray-400">Loading…</p>
            ) : activeBots.length === 0 ? (
              <p className="text-sm text-gray-400">No active bots.</p>
            ) : (
              <div className="space-y-2">
                {activeBots.map((bot) => (
                  <div key={bot.bot_id} className="flex items-start justify-between p-3 border rounded-lg">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-800">{bot.bot_name}</span>
                        <BotStatusBadge code={bot.status_code} />
                      </div>
                      <p className="text-xs text-gray-500 truncate mt-0.5">{bot.meeting_url}</p>
                    </div>
                    <button
                      onClick={() => handleRemove(bot.bot_id)}
                      disabled={removingId === bot.bot_id}
                      className="ml-3 text-red-400 hover:text-red-600 disabled:opacity-40"
                      title="Remove bot"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Past Meetings */}
          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Meeting History
            </h2>
            {loadingBots ? (
              <p className="text-sm text-gray-400">Loading…</p>
            ) : pastBots.length === 0 ? (
              <p className="text-sm text-gray-400">No past meetings yet.</p>
            ) : (
              <div className="space-y-2">
                {pastBots.map((bot) => (
                  <div key={bot.bot_id} className="p-3 border rounded-lg">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-800">{bot.bot_name}</span>
                          <BotStatusBadge code={bot.status_code} />
                        </div>
                        <p className="text-xs text-gray-500 truncate mt-0.5">{bot.meeting_url}</p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {new Date(bot.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    {bot.status_code === 'done' && (
                      <TranscriptViewer agentSlug={agentName} botId={bot.bot_id} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </AgentPagePanel>
    </AgentPageShell>
  )
}
