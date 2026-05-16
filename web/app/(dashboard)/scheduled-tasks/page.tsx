'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  Clock,
  Plus,
  Trash2,
  CheckCircle,
  XCircle,
  Play,
  Pause,
  Search,
  Filter,
  AlertCircle,
  Calendar,
  Database,
  TrendingUp,
  Bot,
  Home,
  ChevronRight,
  FolderOpen,
  MoreHorizontal
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface ScheduledTask {
  id: number
  name: string
  description: string | null
  task_type: string
  schedule_type: string
  cron_expression: string | null
  interval_seconds: number | null
  database_connection_id: number | null
  query: string | null
  chart_config: any | null
  notification_config: any | null
  is_active: boolean
  last_run_at: string | null
  last_run_status: string | null
  next_run_at: string | null
  created_at: string
  updated_at: string
}

export default function ScheduledTasksPage() {
  const [tasks, setTasks] = useState<ScheduledTask[]>([])
  const [filteredTasks, setFilteredTasks] = useState<ScheduledTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; task: ScheduledTask | null }>({
    show: false,
    task: null,
  })
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchTasks()
  }, [])

  useEffect(() => {
    filterTasks()
  }, [searchQuery, filterType, filterStatus, tasks])

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest('[data-task-menu-root="true"]')) return
      setOpenMenuId(null)
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpenMenuId(null)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [])

  const fetchTasks = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getScheduledTasks()
      setTasks(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      toast.error('Failed to load scheduled tasks')
    } finally {
      setLoading(false)
    }
  }

  const filterTasks = () => {
    let filtered = tasks

    if (searchQuery) {
      filtered = filtered.filter(task =>
        task.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        task.task_type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        task.description?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    if (filterType !== 'all') {
      filtered = filtered.filter(task => task.task_type === filterType)
    }

    if (filterStatus !== 'all') {
      if (filterStatus === 'active') {
        filtered = filtered.filter(task => task.is_active)
      } else if (filterStatus === 'inactive') {
        filtered = filtered.filter(task => !task.is_active)
      }
    }

    setFilteredTasks(filtered)
  }

  const confirmDelete = async () => {
    if (!deleteModal.task) return

    setDeleting(true)
    try {
      await apiClient.deleteScheduledTask(deleteModal.task.id.toString())
      toast.success('Scheduled task deleted successfully')
      setDeleteModal({ show: false, task: null })
      fetchTasks()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete task')
    } finally {
      setDeleting(false)
    }
  }

  const toggleTask = async (task: ScheduledTask) => {
    try {
      await apiClient.toggleScheduledTask(task.id.toString())
      toast.success(`Task ${task.is_active ? 'paused' : 'activated'} successfully`)
      fetchTasks()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to toggle task')
    }
  }

  const executeTask = async (task: ScheduledTask) => {
    try {
      await apiClient.executeScheduledTask(task.id.toString())
      toast.success('Task execution started')
      fetchTasks()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to execute task')
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'DATABASE_QUERY': return <Database className="w-4 h-4" />
      case 'DATA_ANALYSIS': return <TrendingUp className="w-4 h-4" />
      case 'AUTONOMOUS_AGENT': return <Bot className="w-4 h-4" />
      default: return <Clock className="w-4 h-4" />
    }
  }

  const getTypeColor = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'DATABASE_QUERY': return 'bg-[#e7f0ff] text-[#325b93]'
      case 'DATA_ANALYSIS': return 'bg-[#efe7f7] text-[#6b4d86]'
      case 'AUTONOMOUS_AGENT': return 'bg-[#f8e4dd] text-[#9f4b31]'
      default: return 'bg-[#f3ecde] text-[#6e675d]'
    }
  }

  // Extract agent name from "[Autonomous] agent-name" task name format
  const getAutonomousAgentName = (task: ScheduledTask): string | null => {
    if (task.task_type?.toUpperCase() !== 'AUTONOMOUS_AGENT') return null
    const match = task.name.match(/^\[Autonomous\]\s+(.+)$/)
    return match ? match[1] : null
  }

  const getStatusColor = (isActive: boolean, lastRunStatus: string | null) => {
    if (!isActive) return 'bg-[#f1eadc] text-[#6e675d]'
    if (lastRunStatus === 'success') return 'bg-[#e8f4ee] text-[#2d8b69]'
    if (lastRunStatus === 'failed') return 'bg-[#fbe9e7] text-[#b44736]'
    return 'bg-[#f8eed9] text-[#ad7d25]'
  }

  const getStatusIcon = (isActive: boolean, lastRunStatus: string | null) => {
    if (!isActive) return <Pause className="w-3 h-3" />
    if (lastRunStatus === 'success') return <CheckCircle className="w-3 h-3" />
    if (lastRunStatus === 'failed') return <XCircle className="w-3 h-3" />
    return <Clock className="w-3 h-3" />
  }

  const getStatusText = (isActive: boolean, lastRunStatus: string | null) => {
    if (!isActive) return 'Paused'
    if (lastRunStatus === 'success') return 'Success'
    if (lastRunStatus === 'failed') return 'Failed'
    return 'Pending'
  }

  const formatSchedule = (task: ScheduledTask) => {
    if (task.schedule_type === 'cron') {
      return task.cron_expression || 'N/A'
    } else if (task.schedule_type === 'interval') {
      const seconds = task.interval_seconds || 0
      if (seconds < 60) return `Every ${seconds}s`
      if (seconds < 3600) return `Every ${Math.floor(seconds / 60)}m`
      if (seconds < 86400) return `Every ${Math.floor(seconds / 3600)}h`
      return `Every ${Math.floor(seconds / 86400)}d`
    }
    return 'N/A'
  }

  const formatCardDate = (dateString: string | null) => {
    if (!dateString) return 'Never'

    const date = new Date(dateString)
    const now = new Date()
    const diffMs = date.getTime() - now.getTime()

    if (Math.abs(diffMs) < 1000 * 60 * 60 * 24) {
      return 'Today'
    }

    if (diffMs > 0) {
      const futureDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

      if (futureDays === 1) return 'Tomorrow'
      if (futureDays < 7) return `In ${futureDays} days`
      if (futureDays < 30) return `In ${Math.ceil(futureDays / 7)} weeks`
    } else {
      const diffDays = Math.floor(Math.abs(diffMs) / (1000 * 60 * 60 * 24))

      if (diffDays === 1) return 'Yesterday'
      if (diffDays < 7) return `${diffDays} days ago`
      if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
    }

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const formatTaskTypeLabel = (type: string) =>
    type
      ?.toLowerCase()
      .split('_')
      .map(part => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ') || 'Task'

  const uniqueTypes = Array.from(new Set(tasks.map(t => t.task_type)))

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600"></div>
      </div>
    )
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-4 flex items-center gap-1.5 text-sm">
          <Link href="/" className="flex items-center gap-1 text-gray-500 transition-colors hover:text-[#171717]">
            <Home className="w-3.5 h-3.5" />
            Home
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
          <span className="font-medium text-gray-900">Scheduled Tasks</span>
        </div>

        <div className="mb-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Scheduled Tasks</h1>
              <p className="mt-1 text-sm text-gray-600 hidden sm:block">
                Schedule and automate recurring tasks
              </p>
            </div>
            <Link
              href="/scheduled-tasks/create"
              prefetch={false}
              className="inline-flex flex-shrink-0 items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
            >
              <Plus className="w-4 h-4 md:w-5 md:h-5" />
              <span className="hidden sm:inline">Create Task</span>
              <span className="sm:hidden">New</span>
            </Link>
          </div>

          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f3ecde] p-2.5">
                  <Clock className="h-[18px] w-[18px] text-[#171717]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Total</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">{tasks.length}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#e8f4ee] p-2.5">
                  <Play className="h-[18px] w-[18px] text-[#2d8b69]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Active</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {tasks.filter(t => t.is_active).length}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#eef7f1] p-2.5">
                  <CheckCircle className="h-[18px] w-[18px] text-[#2d8b69]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Successful</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {tasks.filter(t => t.last_run_status === 'success').length}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#fbe9e7] p-2.5">
                  <XCircle className="h-[18px] w-[18px] text-[#b44736]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Failed</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {tasks.filter(t => t.last_run_status === 'failed').length}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f8e4dd] p-2.5">
                  <Bot className="h-[18px] w-[18px] text-[#9f4b31]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Autonomous</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {tasks.filter(t => t.task_type?.toUpperCase() === 'AUTONOMOUS_AGENT').length}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {tasks.length > 0 && (
            <div className="rounded-[1.3rem] border border-black/10 bg-white/80 p-3 shadow-[0_12px_28px_rgba(0,0,0,0.04)]">
              <div className="flex flex-col gap-3 lg:flex-row">
                <div className="relative flex-1">
                  <Search className="absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search scheduled tasks..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] py-3 pl-11 pr-4 text-sm text-gray-900 focus:border-[#2d8b69] focus:outline-none focus:ring-2 focus:ring-[#2d8b69]/15"
                  />
                </div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <div className="inline-flex items-center gap-2 self-start rounded-[1rem] bg-[#f7f2e7] px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#6e675d]">
                    <Filter className="h-3.5 w-3.5" />
                    Filters
                  </div>
                  <select
                    value={filterType}
                    onChange={(e) => setFilterType(e.target.value)}
                    className="rounded-[1rem] border border-black/10 bg-[#fcfaf5] px-3 py-3 text-sm text-gray-900 focus:border-[#2d8b69] focus:outline-none focus:ring-2 focus:ring-[#2d8b69]/15"
                  >
                    <option value="all">All Types</option>
                    {uniqueTypes.map(type => (
                      <option key={type} value={type}>{formatTaskTypeLabel(type)}</option>
                    ))}
                  </select>
                  <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="rounded-[1rem] border border-black/10 bg-[#fcfaf5] px-3 py-3 text-sm text-gray-900 focus:border-[#2d8b69] focus:outline-none focus:ring-2 focus:ring-[#2d8b69]/15"
                  >
                    <option value="all">All Status</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="mb-6 rounded-[1.3rem] border border-red-200 bg-red-50/90 p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-600" />
              <p className="text-red-700">{error}</p>
            </div>
          </div>
        )}

        {filteredTasks.length === 0 ? (
          <div className="rounded-[2rem] border border-black/10 bg-white/80 p-10 text-center shadow-[0_22px_55px_rgba(0,0,0,0.06)]">
            <div className="relative mx-auto mb-6 h-28 w-28">
              <div className="absolute inset-0 rotate-6 rounded-[1.75rem] bg-[#f3ecde]"></div>
              <div className="absolute inset-0 flex items-center justify-center rounded-[1.75rem] border border-black/10 bg-white shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
                <FolderOpen className="w-10 h-10 text-[#2d8b69]" />
              </div>
            </div>
            <h3 className="mb-2 text-xl font-semibold text-gray-900">
              {tasks.length === 0 ? 'Create your first scheduled task' : 'No results found'}
            </h3>
            <p className="mx-auto mb-6 max-w-md text-gray-600">
              {tasks.length === 0
                ? 'Create recurring jobs for data queries, analysis workflows, and autonomous agent runs.'
                : 'Try adjusting your search or filters to find what you need.'}
            </p>
            {tasks.length === 0 && (
              <Link
                href="/scheduled-tasks/create"
                className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
              >
                <Plus className="w-5 h-5" />
                Create Task
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredTasks.map((task) => (
              <div
                key={task.id}
                className="group relative flex min-h-[330px] flex-col rounded-[1.7rem] border border-black/10 bg-white/80 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-all hover:-translate-y-0.5 hover:border-black/15 hover:shadow-[0_22px_50px_rgba(0,0,0,0.08)]"
              >
                <div className="absolute right-4 top-4 z-20" data-task-menu-root="true">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setOpenMenuId(openMenuId === task.id ? null : task.id)
                    }}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-black/10 bg-white/90 text-[#5b564e] shadow-[0_8px_18px_rgba(0,0,0,0.08)] transition-colors hover:bg-white hover:text-[#171717]"
                    aria-label={`Open actions for ${task.name}`}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </button>

                  {openMenuId === task.id && (
                    <div className="absolute right-0 top-11 w-44 overflow-hidden rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] py-1.5 shadow-[0_20px_45px_rgba(0,0,0,0.14)]">
                      <button
                        type="button"
                        onClick={() => {
                          setOpenMenuId(null)
                          setDeleteModal({ show: true, task })
                        }}
                        className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </button>
                    </div>
                  )}
                </div>

                <Link
                  href={`/scheduled-tasks/${task.id}`}
                  prefetch={false}
                  className="flex flex-1 flex-col p-5 pr-16 focus:outline-none"
                  aria-label={`Open ${task.name}`}
                >
                  <div className="mb-4 flex min-w-0 items-start gap-3">
                    <div className={`rounded-[1.1rem] p-3 transition-colors group-hover:opacity-90 ${getTypeColor(task.task_type)}`}>
                      {getTypeIcon(task.task_type)}
                    </div>
                    <div className="min-w-0">
                      <h3 className="line-clamp-2 text-[1.05rem] font-semibold text-gray-900" title={task.name}>
                        {task.name}
                      </h3>
                      <p className="mt-1 flex items-center gap-1.5 text-sm text-gray-500">
                        <Calendar className="h-3.5 w-3.5 flex-shrink-0" />
                        <span className="truncate">{formatSchedule(task)}</span>
                      </p>
                    </div>
                  </div>

                  <div className="mb-4 flex flex-wrap gap-2">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${getStatusColor(task.is_active, task.last_run_status)}`}>
                      {getStatusIcon(task.is_active, task.last_run_status)}
                      {getStatusText(task.is_active, task.last_run_status)}
                    </span>
                    <span className="inline-flex items-center rounded-full bg-[#f7f2e7] px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-[#6e675d]">
                      {formatTaskTypeLabel(task.task_type)}
                    </span>
                  </div>

                  {task.description && (
                    <p className="mb-4 line-clamp-2 text-sm text-gray-500">
                      {task.description}
                    </p>
                  )}

                  <div className="grid grid-cols-3 gap-2.5">
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-3 py-3">
                      <div className="text-[10px] font-medium uppercase leading-snug tracking-[0.1em] text-gray-500 break-words">Schedule</div>
                      <div className="mt-1 line-clamp-2 text-sm font-semibold text-gray-900">{formatSchedule(task)}</div>
                    </div>
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#eef7f1] px-3 py-3">
                      <div className="text-[10px] font-medium uppercase leading-snug tracking-[0.1em] text-gray-500 break-words">Last Run</div>
                      <div className="mt-1 text-sm font-semibold text-gray-900">{formatCardDate(task.last_run_at)}</div>
                    </div>
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#f4efe4] px-3 py-3">
                      <div className="text-[10px] font-medium uppercase leading-snug tracking-[0.1em] text-gray-500 break-words">Next Run</div>
                      <div className="mt-1 text-sm font-semibold text-gray-900">{task.next_run_at ? formatCardDate(task.next_run_at) : 'Not set'}</div>
                    </div>
                  </div>
                </Link>

                <div className="flex flex-wrap gap-2 border-t border-black/5 px-5 pb-5 pt-3">
                  <button
                    type="button"
                    onClick={() => toggleTask(task)}
                    className={`inline-flex items-center gap-1.5 rounded-[0.95rem] px-3 py-2 text-xs font-semibold transition-colors ${
                      task.is_active
                        ? 'bg-[#f7f2e7] text-[#9a6b21] hover:bg-[#f3ecde]'
                        : 'bg-[#e8f4ee] text-[#2d8b69] hover:bg-[#dceddf]'
                    }`}
                    title={task.is_active ? 'Pause task' : 'Activate task'}
                  >
                    {task.is_active ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                    {task.is_active ? 'Pause' : 'Activate'}
                  </button>

                  <button
                    type="button"
                    onClick={() => executeTask(task)}
                    className="inline-flex items-center gap-1.5 rounded-[0.95rem] bg-[#f3ecde] px-3 py-2 text-xs font-semibold text-[#171717] transition-colors hover:bg-[#ece2cd]"
                    title="Run now"
                  >
                    <Play className="h-3.5 w-3.5" />
                    Run now
                  </button>

                  {getAutonomousAgentName(task) ? (
                    <Link
                      href={`/agents/${encodeURIComponent(getAutonomousAgentName(task)!)}/autonomous`}
                      prefetch={false}
                      className="inline-flex items-center gap-1.5 rounded-[0.95rem] bg-[#171717] px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-black"
                    >
                      <Bot className="h-3.5 w-3.5" />
                      Open
                    </Link>
                  ) : (
                    <Link
                      href={`/scheduled-tasks/${task.id}`}
                      prefetch={false}
                      className="inline-flex items-center gap-1.5 rounded-[0.95rem] bg-[#171717] px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-black"
                    >
                      Open
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {deleteModal.show && deleteModal.task && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.18)]">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-[1rem] bg-red-50 p-2.5">
                <Trash2 className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Delete Task</h3>
            </div>

            <p className="mb-6 text-gray-600">
              Are you sure you want to delete <span className="font-semibold text-gray-900">"{deleteModal.task.name}"</span>?
              This action cannot be undone and will permanently remove this scheduled task.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteModal({ show: false, task: null })}
                disabled={deleting}
                className="rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deleting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
