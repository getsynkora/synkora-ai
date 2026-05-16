'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  Clock,
  ArrowLeft,
  Save,
  Loader2,
  Database,
  Calendar,
  Mail,
  MessageSquare,
  Home,
  ChevronRight,
  CheckCircle,
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { getAgents } from '@/lib/api/agents'

interface TaskFormData {
  name: string
  description: string
  task_type: string
  interval_seconds: number
  database_connection_id: string
  query: string
  agent_id: string
  agent_prompt: string
  config: any
  notification_config: {
    email_enabled: boolean
    email_recipients: string[]
    slack_enabled: boolean
    slack_webhook_url: string
    notify_on_success: boolean
    notify_on_failure: boolean
  }
  is_active: boolean
}

interface DatabaseConnection {
  id: string
  name: string
  type: string
}

interface Agent {
  id: string
  name: string
}

// Common interval presets
const intervalPresets = [
  { label: 'Every minute', value: 60 },
  { label: 'Every 5 minutes', value: 300 },
  { label: 'Every 15 minutes', value: 900 },
  { label: 'Every 30 minutes', value: 1800 },
  { label: 'Every hour', value: 3600 },
  { label: 'Every 2 hours', value: 7200 },
  { label: 'Every 6 hours', value: 21600 },
  { label: 'Every 12 hours', value: 43200 },
  { label: 'Every day', value: 86400 },
  { label: 'Every week', value: 604800 },
]

const getTaskTypeLabel = (type: string) => {
  switch (type) {
    case 'database_query':
      return 'Database Query'
    case 'chart_generation':
      return 'Chart Generation'
    case 'agent_task':
      return 'Agent Task'
    default:
      return 'Scheduled Task'
  }
}

export default function CreateScheduledTaskPage() {
  const router = useRouter()
  const [formData, setFormData] = useState<TaskFormData>({
    name: '',
    description: '',
    task_type: 'database_query',
    interval_seconds: 3600,
    database_connection_id: '',
    query: '',
    agent_id: '',
    agent_prompt: '',
    config: null,
    notification_config: {
      email_enabled: false,
      email_recipients: [],
      slack_enabled: false,
      slack_webhook_url: '',
      notify_on_success: false,
      notify_on_failure: true
    },
    is_active: true
  })

  const [connections, setConnections] = useState<DatabaseConnection[]>([])
  const [loadingConnections, setLoadingConnections] = useState(true)
  const [agents, setAgents] = useState<Agent[]>([])
  const [loadingAgents, setLoadingAgents] = useState(true)
  const [saving, setSaving] = useState(false)
  const [emailInput, setEmailInput] = useState('')

  useEffect(() => {
    fetchConnections()
    fetchAgents()
  }, [])

  const fetchConnections = async () => {
    try {
      const data = await apiClient.getDatabaseConnections()
      setConnections(data)
    } catch {
      toast.error('Failed to load database connections')
    } finally {
      setLoadingConnections(false)
    }
  }

  const fetchAgents = async () => {
    try {
      const data = await getAgents()
      setAgents(Array.isArray(data) ? data : data.items || [])
    } catch {
      toast.error('Failed to load agents')
    } finally {
      setLoadingAgents(false)
    }
  }

  const handleInputChange = (field: keyof TaskFormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleNotificationChange = (field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      notification_config: {
        ...prev.notification_config,
        [field]: value
      }
    }))
  }

  const addEmailRecipient = () => {
    if (emailInput && emailInput.includes('@')) {
      setFormData(prev => ({
        ...prev,
        notification_config: {
          ...prev.notification_config,
          email_recipients: [...prev.notification_config.email_recipients, emailInput]
        }
      }))
      setEmailInput('')
    } else {
      toast.error('Please enter a valid email address')
    }
  }

  const removeEmailRecipient = (email: string) => {
    setFormData(prev => ({
      ...prev,
      notification_config: {
        ...prev.notification_config,
        email_recipients: prev.notification_config.email_recipients.filter(e => e !== email)
      }
    }))
  }

  const formatInterval = (seconds: number): string => {
    if (seconds >= 86400) {
      const days = Math.floor(seconds / 86400)
      return `${days} day${days > 1 ? 's' : ''}`
    } else if (seconds >= 3600) {
      const hours = Math.floor(seconds / 3600)
      return `${hours} hour${hours > 1 ? 's' : ''}`
    } else if (seconds >= 60) {
      const minutes = Math.floor(seconds / 60)
      return `${minutes} minute${minutes > 1 ? 's' : ''}`
    }
    return `${seconds} second${seconds > 1 ? 's' : ''}`
  }

  const inputClass = 'w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-3.5 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#2d8b69]'
  const textareaClass = `${inputClass} resize-none`
  const selectClass = `${inputClass} appearance-none`
  const labelClass = 'mb-1.5 block text-sm font-semibold text-gray-700'
  const helpTextClass = 'mt-2 text-xs leading-relaxed text-gray-500'
  const sectionClass = 'rounded-[1.9rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] p-5 shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)] md:p-6'
  const subCardClass = 'rounded-[1.35rem] border border-black/10 bg-white/70 p-4'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.name) {
      toast.error('Please enter a task name')
      return
    }

    if (formData.interval_seconds < 60) {
      toast.error('Interval must be at least 60 seconds')
      return
    }

    if (formData.task_type === 'agent_task') {
      if (!formData.agent_id) {
        toast.error('Please select an agent for this task')
        return
      }
      if (!formData.agent_prompt) {
        toast.error('Please enter a prompt for this task')
        return
      }
    }

    setSaving(true)

    try {
      const config: Record<string, any> = { ...(formData.config || {}) }
      if (formData.task_type === 'agent_task') {
        config.agent_id = formData.agent_id
        config.prompt = formData.agent_prompt
      }

      await apiClient.createScheduledTask({
        name: formData.name,
        description: formData.description,
        task_type: formData.task_type,
        interval_seconds: formData.interval_seconds,
        database_connection_id: formData.database_connection_id || undefined,
        query: formData.query || undefined,
        config,
        is_active: formData.is_active,
      })
      toast.success('Scheduled task created successfully')
      router.push('/scheduled-tasks')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create task')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-4 flex items-center gap-1.5 text-sm">
          <Link href="/" className="flex items-center gap-1 text-gray-500 transition-colors hover:text-[#171717]">
            <Home className="h-3.5 w-3.5" />
            Home
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
          <Link href="/scheduled-tasks" className="text-gray-500 transition-colors hover:text-[#171717]">
            Scheduled Tasks
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
          <span className="font-medium text-gray-900">Create</span>
        </div>

        <div className="mb-6 overflow-hidden rounded-[2rem] border border-[#eadfce] bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.96),_rgba(247,240,231,0.94)_50%,_rgba(237,230,220,0.92)_100%)] shadow-[0_28px_80px_-42px_rgba(88,63,39,0.32)]">
          <div className="flex flex-col gap-6 p-6 md:p-8">
            <Link
              href="/scheduled-tasks"
              className="inline-flex w-fit items-center gap-2 rounded-full border border-[#dbcdb9] bg-white/80 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:border-[#cdb79d] hover:text-gray-900"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Scheduled Tasks
            </Link>

            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl space-y-3">
                <div className="inline-flex items-center gap-2 rounded-full border border-[#dfd1be] bg-white/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7c5d45]">
                  <Clock className="h-3.5 w-3.5" />
                  Scheduled Automation
                </div>

                <div className="flex items-start gap-4">
                  <div className="rounded-[1.2rem] bg-[#f3ecde] p-3.5 shadow-[0_16px_30px_-24px_rgba(74,49,22,0.3)]">
                    <Clock className="h-6 w-6 text-[#171717]" />
                  </div>
                  <div>
                    <h1 className="text-3xl font-semibold tracking-[-0.04em] text-gray-950 md:text-[2.6rem]">
                      Create Scheduled Task
                    </h1>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
                      Schedule automated tasks to run at regular intervals.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[1.5rem] border border-white/70 bg-white/75 px-4 py-3 shadow-[0_20px_45px_-38px_rgba(77,51,28,0.4)] backdrop-blur">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Task Type</p>
                  <p className="mt-2 text-lg font-semibold text-gray-900">{getTaskTypeLabel(formData.task_type)}</p>
                </div>
                <div className="rounded-[1.5rem] border border-white/70 bg-white/75 px-4 py-3 shadow-[0_20px_45px_-38px_rgba(77,51,28,0.4)] backdrop-blur">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Cadence</p>
                  <p className="mt-2 text-lg font-semibold text-gray-900">{formatInterval(formData.interval_seconds)}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className={sectionClass}>
            <div className="mb-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Section 1</p>
              <h2 className="mt-2 text-lg font-semibold text-gray-950">Basic Information</h2>
              <p className="mt-1 text-sm text-gray-500">Define the task name, purpose, and what kind of work it runs.</p>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="md:col-span-2">
                <label className={labelClass}>
                  Task Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  placeholder="Daily Sales Report"
                  className={inputClass}
                  required
                />
              </div>

              <div className="md:col-span-2">
                <label className={labelClass}>
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => handleInputChange('description', e.target.value)}
                  placeholder="Generate daily sales report and send to team"
                  rows={3}
                  className={textareaClass}
                />
              </div>

              <div>
                <label className={labelClass}>
                  Task Type
                </label>
                <select
                  value={formData.task_type}
                  onChange={(e) => handleInputChange('task_type', e.target.value)}
                  className={selectClass}
                >
                  <option value="database_query">Database Query</option>
                  <option value="chart_generation">Chart Generation</option>
                  <option value="agent_task">Agent Task</option>
                </select>
              </div>

              <div className={`${subCardClass} flex items-start gap-3`}>
                <div className="rounded-[1rem] bg-[#f3ecde] p-2.5">
                  <CheckCircle className="h-4 w-4 text-[#171717]" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">Current setup</p>
                  <p className="mt-1 text-sm text-gray-500">
                    This task will start as <span className="font-medium text-gray-900">{formData.is_active ? 'active' : 'inactive'}</span> and run as a{' '}
                    <span className="font-medium text-gray-900">{getTaskTypeLabel(formData.task_type)}</span>.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className={sectionClass}>
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-[1rem] bg-[#f3ecde] p-3">
                <Calendar className="h-5 w-5 text-[#171717]" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-950">Schedule Interval</h2>
                <p className="text-sm text-gray-500">Choose how often this task should run.</p>
              </div>
            </div>

            <div className="space-y-5">
              <div>
                <label className={labelClass}>
                  Run Every <span className="text-red-500">*</span>
                </label>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                  <input
                    type="number"
                    value={formData.interval_seconds}
                    onChange={(e) => handleInputChange('interval_seconds', parseInt(e.target.value) || 60)}
                    min="60"
                    className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-3.5 text-sm text-gray-900 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#2d8b69] sm:w-40"
                    required
                  />
                  <div className="flex flex-wrap items-center gap-2 text-sm text-gray-600">
                    <span>seconds</span>
                    <span className="rounded-full bg-[#f7f2e7] px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#6e675d]">
                      {formatInterval(formData.interval_seconds)}
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <label className={labelClass}>
                  Quick Select
                </label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
                  {intervalPresets.map((preset) => (
                    <button
                      key={preset.value}
                      type="button"
                      onClick={() => handleInputChange('interval_seconds', preset.value)}
                      className={`rounded-[1rem] border px-3 py-2.5 text-sm font-medium transition-all ${
                        formData.interval_seconds === preset.value
                          ? 'border-[#d8ccb8] bg-[#f3ecde] text-[#171717] shadow-[0_12px_28px_rgba(0,0,0,0.04)]'
                          : 'border-black/10 bg-white/75 text-gray-700 hover:bg-[#fcfaf5]'
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {(formData.task_type === 'database_query' || formData.task_type === 'chart_generation') && (
            <div className={sectionClass}>
              <div className="mb-5 flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f3ecde] p-3">
                  <Database className="h-5 w-5 text-[#171717]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-gray-950">Database & Query</h2>
                  <p className="text-sm text-gray-500">Choose a data source and optionally provide a query.</p>
                </div>
              </div>

              <div className="space-y-5">
                <div>
                  <label className={labelClass}>
                    Database Connection
                  </label>
                  {loadingConnections ? (
                    <div className="flex items-center gap-2 rounded-[1.2rem] border border-black/10 bg-white/75 px-4 py-3 text-sm text-gray-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading connections...
                    </div>
                  ) : connections.length === 0 ? (
                    <div className="rounded-[1.2rem] border border-yellow-200 bg-yellow-50/80 p-4">
                      <p className="text-sm text-yellow-800">
                        No database connections found.{' '}
                        <Link href="/database-connections/create" className="font-medium underline">
                          Create one first
                        </Link>
                      </p>
                    </div>
                  ) : (
                    <select
                      value={formData.database_connection_id}
                      onChange={(e) => handleInputChange('database_connection_id', e.target.value)}
                      className={selectClass}
                    >
                      <option value="">Select a connection (optional)</option>
                      {connections.map((conn) => (
                        <option key={conn.id} value={conn.id}>
                          {conn.name} ({conn.type})
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                <div>
                  <label className={labelClass}>
                    SQL Query
                  </label>
                  <textarea
                    value={formData.query}
                    onChange={(e) => handleInputChange('query', e.target.value)}
                    placeholder="SELECT * FROM sales WHERE date = CURRENT_DATE"
                    rows={6}
                    className={`${textareaClass} font-mono`}
                  />
                  <p className={helpTextClass}>
                    Leave empty to use agent&apos;s default query generation
                  </p>
                </div>
              </div>
            </div>
          )}

          {formData.task_type === 'agent_task' && (
            <div className={sectionClass}>
              <div className="mb-5 flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f3ecde] p-3">
                  <MessageSquare className="h-5 w-5 text-[#171717]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-gray-950">Agent Task</h2>
                  <p className="text-sm text-gray-500">Pick the agent and define what it should do on each run.</p>
                </div>
              </div>

              <div className="space-y-5">
                <div>
                  <label className={labelClass}>
                    Agent <span className="text-red-500">*</span>
                  </label>
                  {loadingAgents ? (
                    <div className="flex items-center gap-2 rounded-[1.2rem] border border-black/10 bg-white/75 px-4 py-3 text-sm text-gray-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading agents...
                    </div>
                  ) : agents.length === 0 ? (
                    <div className="rounded-[1.2rem] border border-yellow-200 bg-yellow-50/80 p-4">
                      <p className="text-sm text-yellow-800">No agents found. Create an agent first.</p>
                    </div>
                  ) : (
                    <select
                      value={formData.agent_id}
                      onChange={(e) => handleInputChange('agent_id', e.target.value)}
                      className={selectClass}
                      required
                    >
                      <option value="">Select an agent</option>
                      {agents.map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                <div>
                  <label className={labelClass}>
                    Prompt <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={formData.agent_prompt}
                    onChange={(e) => handleInputChange('agent_prompt', e.target.value)}
                    placeholder="What should the agent do when this task runs?"
                    rows={4}
                    className={textareaClass}
                    required
                  />
                </div>
              </div>
            </div>
          )}

          <div className={sectionClass}>
            <div className="mb-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Section 4</p>
              <h2 className="mt-2 text-lg font-semibold text-gray-950">Notifications</h2>
              <p className="mt-1 text-sm text-gray-500">Decide who gets notified and when.</p>
            </div>

            <div className="space-y-5">
              <div className={subCardClass}>
                <div className="mb-3 flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={formData.notification_config.email_enabled}
                    onChange={(e) => handleNotificationChange('email_enabled', e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-[#171717] focus:ring-[#2d8b69]"
                  />
                  <Mail className="h-4 w-4 text-gray-600" />
                  <label className="text-sm font-semibold text-gray-700">
                    Email Notifications
                  </label>
                </div>

                {formData.notification_config.email_enabled && (
                  <div className="space-y-3 border-t border-black/10 pt-4">
                    <div>
                      <label className={labelClass}>
                        Recipients
                      </label>
                      <div className="flex gap-2">
                        <input
                          type="email"
                          value={emailInput}
                          onChange={(e) => setEmailInput(e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addEmailRecipient())}
                          placeholder="email@example.com"
                          className={inputClass}
                        />
                        <button
                          type="button"
                          onClick={addEmailRecipient}
                          className="rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
                        >
                          Add
                        </button>
                      </div>
                      {formData.notification_config.email_recipients.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {formData.notification_config.email_recipients.map((email) => (
                            <span
                              key={email}
                              className="inline-flex items-center gap-1 rounded-full bg-[#f7f2e7] px-3 py-1 text-sm text-[#6e675d]"
                            >
                              {email}
                              <button
                                type="button"
                                onClick={() => removeEmailRecipient(email)}
                                className="font-semibold text-[#171717] transition-colors hover:text-black"
                              >
                                x
                              </button>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className={subCardClass}>
                <div className="mb-3 flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={formData.notification_config.slack_enabled}
                    onChange={(e) => handleNotificationChange('slack_enabled', e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-[#171717] focus:ring-[#2d8b69]"
                  />
                  <MessageSquare className="h-4 w-4 text-gray-600" />
                  <label className="text-sm font-semibold text-gray-700">
                    Slack Notifications
                  </label>
                </div>

                {formData.notification_config.slack_enabled && (
                  <div className="border-t border-black/10 pt-4">
                    <label className={labelClass}>
                      Webhook URL
                    </label>
                    <input
                      type="url"
                      value={formData.notification_config.slack_webhook_url}
                      onChange={(e) => handleNotificationChange('slack_webhook_url', e.target.value)}
                      placeholder="https://hooks.slack.com/services/..."
                      className={inputClass}
                    />
                  </div>
                )}
              </div>

              <div className={subCardClass}>
                <label className="mb-3 block text-sm font-semibold text-gray-700">
                  Notify When
                </label>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 rounded-[1rem] border border-black/10 bg-white/70 px-3 py-3">
                    <input
                      type="checkbox"
                      checked={formData.notification_config.notify_on_success}
                      onChange={(e) => handleNotificationChange('notify_on_success', e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 text-[#171717] focus:ring-[#2d8b69]"
                    />
                    <span className="text-sm text-gray-700">Task succeeds</span>
                  </label>
                  <label className="flex items-center gap-3 rounded-[1rem] border border-black/10 bg-white/70 px-3 py-3">
                    <input
                      type="checkbox"
                      checked={formData.notification_config.notify_on_failure}
                      onChange={(e) => handleNotificationChange('notify_on_failure', e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 text-[#171717] focus:ring-[#2d8b69]"
                    />
                    <span className="text-sm text-gray-700">Task fails</span>
                  </label>
                </div>
              </div>
            </div>
          </div>

          <div className={sectionClass}>
            <div className="mb-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Section 5</p>
              <h2 className="mt-2 text-lg font-semibold text-gray-950">Task Status</h2>
              <p className="mt-1 text-sm text-gray-500">Choose whether the task should start running immediately after creation.</p>
            </div>

            <label className="flex items-center gap-3 rounded-[1.25rem] border border-black/10 bg-white/75 px-4 py-4">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => handleInputChange('is_active', e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-[#171717] focus:ring-[#2d8b69]"
              />
              <span className="text-sm font-medium text-gray-700">
                Activate task immediately after creation
              </span>
            </label>
          </div>

          <div className="flex flex-col-reverse gap-3 pt-1 sm:flex-row sm:items-center sm:justify-end">
            <Link
              href="/scheduled-tasks"
              className="inline-flex items-center justify-center rounded-[1rem] border border-black/10 bg-[#f1eadc] px-5 py-3 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8]"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center justify-center gap-2 rounded-[1rem] bg-[#171717] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Create Task
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
