'use client'

import { useState, useEffect } from 'react'
import {
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  RotateCw,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Trash2,
  RefreshCw,
  SkipForward
} from 'lucide-react'
import { useWebhooks } from '@/hooks/useWebhooks'
import { WebhookEvent, JevGateVerdict } from '@/types/webhooks'

export interface WebhookEventsProps {
  agentName: string
}

const statusConfig: Record<string, { icon: any; color: string; bg: string; label: string }> = {
  pending:   { icon: Clock,        color: 'text-gray-600',   bg: 'bg-gray-100',   label: 'Pending' },
  processing:{ icon: Loader2,      color: 'text-blue-600',   bg: 'bg-blue-100',   label: 'Processing' },
  completed: { icon: CheckCircle,  color: 'text-green-600',  bg: 'bg-green-100',  label: 'Completed' },
  success:   { icon: CheckCircle,  color: 'text-green-600',  bg: 'bg-green-100',  label: 'Success' },
  failed:    { icon: XCircle,      color: 'text-red-600',    bg: 'bg-red-100',    label: 'Failed' },
  retrying:  { icon: RotateCw,     color: 'text-orange-600', bg: 'bg-orange-100', label: 'Retrying' },
  retry:     { icon: RotateCw,     color: 'text-orange-600', bg: 'bg-orange-100', label: 'Retrying' },
  skipped:   { icon: SkipForward,  color: 'text-slate-600',  bg: 'bg-slate-100',  label: 'Skipped' },
}

export function WebhookEvents({ agentName }: WebhookEventsProps) {
  const { webhooks, isLoading, getWebhookEvents, deleteWebhookEvent } = useWebhooks(agentName)
  const [events, setEvents] = useState<WebhookEvent[]>([])
  const [loadingEvents, setLoadingEvents] = useState(false)
  const [selectedWebhook, setSelectedWebhook] = useState<string | null>(null)
  const [expandedEvent, setExpandedEvent] = useState<string | null>(null)
  const [deletingEvent, setDeletingEvent] = useState<string | null>(null)

  useEffect(() => {
    if (webhooks.length > 0 && !selectedWebhook) {
      setSelectedWebhook(webhooks[0].id)
    }
  }, [webhooks])

  useEffect(() => {
    if (selectedWebhook) {
      loadEvents()
    }
  }, [selectedWebhook])

  const loadEvents = async () => {
    if (!selectedWebhook) return
    setLoadingEvents(true)
    try {
      const webhookEvents = await getWebhookEvents(selectedWebhook, 100)
      setEvents(webhookEvents)
    } catch (error) {
      console.error('Failed to load events:', error)
    } finally {
      setLoadingEvents(false)
    }
  }

  const handleDeleteEvent = async (e: React.MouseEvent, eventId: string) => {
    e.stopPropagation()
    if (!selectedWebhook) return
    setDeletingEvent(eventId)
    try {
      await deleteWebhookEvent(selectedWebhook, eventId)
      setEvents(prev => prev.filter(ev => ev.id !== eventId))
      if (expandedEvent === eventId) setExpandedEvent(null)
    } catch (error) {
      console.error('Failed to delete event:', error)
    } finally {
      setDeletingEvent(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-red-500 animate-spin mx-auto mb-3" />
          <p className="text-gray-600 text-sm">Loading events...</p>
        </div>
      </div>
    )
  }

  if (webhooks.length === 0) {
    return (
      <div className="p-16 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
          <Activity className="w-8 h-8 text-red-600" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">No Webhooks Created</h3>
        <p className="text-gray-600 text-sm">
          Create a webhook first to see event history
        </p>
      </div>
    )
  }

  return (
    <div className="p-6">
      {/* Webhook Selector */}
      <div className="mb-6 flex items-end gap-3">
        <div className="flex-1 max-w-md">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Webhook
          </label>
          <select
            value={selectedWebhook || ''}
            onChange={(e) => setSelectedWebhook(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
          >
            {webhooks.map(webhook => (
              <option key={webhook.id} value={webhook.id}>
                {webhook.name} ({webhook.provider})
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={loadEvents}
          disabled={loadingEvents}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loadingEvents ? 'animate-spin' : ''}`} />
          Refresh
        </button>
        {events.length > 0 && (
          <span className="text-sm text-gray-500 self-center">{events.length} event{events.length !== 1 ? 's' : ''}</span>
        )}
      </div>

      {/* Events List */}
      {loadingEvents ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <Loader2 className="w-8 h-8 text-red-500 animate-spin mx-auto mb-3" />
            <p className="text-gray-600 text-sm">Loading events...</p>
          </div>
        </div>
      ) : events.length === 0 ? (
        <div className="text-center py-12">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
            <Activity className="w-8 h-8 text-gray-400" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No Events Yet</h3>
          <p className="text-gray-600 text-sm">
            This webhook hasn't received any events yet
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {events.map((event) => {
            const config = statusConfig[event.status as keyof typeof statusConfig] || statusConfig.pending
            const Icon = config.icon
            const isExpanded = expandedEvent === event.id

            return (
              <div
                key={event.id}
                className="border border-gray-200 rounded-lg bg-white hover:border-red-200 transition-colors"
              >
                <button
                  onClick={() => setExpandedEvent(isExpanded ? null : event.id)}
                  className="w-full p-4 text-left"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      <div className={`p-2 rounded-lg ${config.bg} mt-0.5`}>
                        <Icon className={`w-4 h-4 ${config.color} ${event.status === 'processing' ? 'animate-spin' : ''}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-1">
                          <span className="font-medium text-gray-900">{event.event_type}</span>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.color}`}>
                            {config.label}
                          </span>
                          {event.retry_count > 0 && (
                            <span className="text-xs text-gray-500">
                              Retry {event.retry_count}
                            </span>
                          )}
                          {(() => {
                            const gate = event.parsed_data?.jev_gate as JevGateVerdict | undefined
                            if (gate?.mode === 'shadow' && gate.reason.startsWith('shadow: would skip')) {
                              return (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
                                  Jev would skip
                                </span>
                              )
                            }
                            return null
                          })()}
                        </div>
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          {event.event_id && (
                            <span className="font-mono">{event.event_id}</span>
                          )}
                          <span>
                            {new Date(event.created_at).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <button
                        onClick={(e) => handleDeleteEvent(e, event.id)}
                        disabled={deletingEvent === event.id}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors disabled:opacity-50"
                        title="Delete event"
                      >
                        {deletingEvent === event.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                      {isExpanded ? (
                        <ChevronDown className="w-5 h-5 text-gray-400" />
                      ) : (
                        <ChevronRight className="w-5 h-5 text-gray-400" />
                      )}
                    </div>
                  </div>
                </button>

                {isExpanded && (
                  <div className="border-t border-gray-200 p-4 bg-gray-50">
                    <div className="space-y-4">
                      {/* Error Message */}
                      {event.error_message && (
                        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                          <div className="flex items-start gap-2">
                            <AlertCircle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
                            <div>
                              <p className="text-sm font-medium text-red-900 mb-1">Error</p>
                              <p className="text-xs text-red-700">{event.error_message}</p>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Jev gate verdict */}
                      {(() => {
                        const gate = event.parsed_data?.jev_gate as JevGateVerdict | undefined
                        if (!gate) return null
                        return (
                          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                            <p className="text-xs font-semibold text-slate-800 mb-1.5">
                              Jev gate ({gate.mode === 'enforce' ? 'enforcing' : 'test only'})
                            </p>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                              <div>
                                <span className="text-slate-500">Decision:</span>
                                <span className="ml-2 font-medium text-slate-900">{gate.action === 'skip' ? 'Skipped' : 'Ran agent'}</span>
                              </div>
                              <div>
                                <span className="text-slate-500">Needs action:</span>
                                <span className="ml-2 font-medium text-slate-900">
                                  {gate.actionable === null ? '—' : `${Math.round(gate.actionable * 100)}%`}
                                </span>
                              </div>
                              <div>
                                <span className="text-slate-500">Latency:</span>
                                <span className="ml-2 font-medium text-slate-900">
                                  {gate.latency_ms === null ? '—' : `${gate.latency_ms} ms`}
                                </span>
                              </div>
                            </div>
                            <p className="text-xs text-slate-600 mt-1.5">{gate.reason}</p>
                          </div>
                        )
                      })()}

                      {/* Payload */}
                      <div>
                        <h4 className="text-xs font-semibold text-gray-700 mb-2">Payload</h4>
                        <div className="bg-white border border-gray-200 rounded-lg p-3">
                          <pre className="text-xs text-gray-700 overflow-x-auto">
                            {JSON.stringify(event.payload, null, 2)}
                          </pre>
                        </div>
                      </div>

                      {/* Parsed Data */}
                      {event.parsed_data && (
                        <div>
                          <h4 className="text-xs font-semibold text-gray-700 mb-2">Parsed Data</h4>
                          <div className="bg-white border border-gray-200 rounded-lg p-3">
                            <pre className="text-xs text-gray-700 overflow-x-auto">
                              {JSON.stringify(event.parsed_data, null, 2)}
                            </pre>
                          </div>
                        </div>
                      )}

                      {/* Processing Times */}
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        {event.processing_started_at && (
                          <div>
                            <span className="text-gray-500">Started:</span>
                            <span className="ml-2 text-gray-900">
                              {new Date(event.processing_started_at).toLocaleTimeString()}
                            </span>
                          </div>
                        )}
                        {event.processing_completed_at && (
                          <div>
                            <span className="text-gray-500">Completed:</span>
                            <span className="ml-2 text-gray-900">
                              {new Date(event.processing_completed_at).toLocaleTimeString()}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
