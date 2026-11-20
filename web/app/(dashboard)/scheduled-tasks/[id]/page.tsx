'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import {
  Clock,
  Trash2,
  Play,
  Pause,
  CheckCircle,
  XCircle,
  AlertCircle,
  Calendar,
  Database,
  TrendingUp,
  Loader2,
  Activity
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { extractErrorMessage } from '@/lib/api/error'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

interface ScheduledTask {
  id: string
  name: string
  description: string | null
  task_type: string
  schedule_type: string
  cron_expression: string | null
  interval_seconds: number | null
  config: any
  is_active: boolean
  last_run_at: string | null
  last_run_status: string | null
  next_run_at: string | null
  created_at: string
  updated_at: string
}

interface TaskExecution {
  id: string
  status: string
  started_at: string
  completed_at: string | null
  result: any | null
  error_message: string | null
  execution_time_seconds: number | null
}

export default function ScheduledTaskDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const [task, setTask] = useState<ScheduledTask | null>(null)
  const [executions, setExecutions] = useState<TaskExecution[]>([])
  const [loading, setLoading] = useState(true)
  const [executionsLoading, setExecutionsLoading] = useState(true)
  const [deleteModal, setDeleteModal] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchTask()
    fetchExecutions()
  }, [params.id])

  const fetchTask = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getScheduledTask(params.id as string)
      setTask(data)
    } catch {
      toast.error('Failed to load task details')
      router.push('/scheduled-tasks')
    } finally {
      setLoading(false)
    }
  }

  const fetchExecutions = async () => {
    try {
      setExecutionsLoading(true)
      const data = await apiClient.getTaskExecutions(params.id as string, 0, 10)
      setExecutions(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error('Failed to load executions:', error)
      setExecutions([])
    } finally {
      setExecutionsLoading(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await apiClient.deleteScheduledTask(params.id as string)
      toast.success('Task deleted successfully')
      router.push('/scheduled-tasks')
    } catch (error: any) {
      toast.error(extractErrorMessage(error, 'Failed to delete task'))
    } finally {
      setDeleting(false)
      setDeleteModal(false)
    }
  }

  const toggleTask = async () => {
    if (!task) return
    
    try {
      await apiClient.toggleScheduledTask(params.id as string)
      toast.success(`Task ${task.is_active ? 'paused' : 'activated'} successfully`)
      fetchTask()
    } catch (error: any) {
      toast.error(extractErrorMessage(error, 'Failed to toggle task'))
    }
  }

  const executeTask = async () => {
    try {
      await apiClient.executeScheduledTask(params.id as string)
      toast.success('Task execution started')
      setTimeout(() => {
        fetchTask()
        fetchExecutions()
      }, 2000)
    } catch (error: any) {
      toast.error(extractErrorMessage(error, 'Failed to execute task'))
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'DATABASE_QUERY': return <Database className="w-6 h-6" />
      case 'DATA_ANALYSIS': return <TrendingUp className="w-6 h-6" />
      default: return <Clock className="w-6 h-6" />
    }
  }

  const getTypeColor = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'DATABASE_QUERY': return 'bg-sky-wash text-azure'
      case 'DATA_ANALYSIS': return 'bg-sand-deep text-ink-soft'
      default: return 'bg-sand text-ink-mute'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'success': return 'bg-leaf-wash text-leaf'
      case 'failed': return 'bg-blush-wash text-danger'
      case 'running': return 'bg-sky-wash text-azure'
      default: return 'bg-sand text-ink-mute'
    }
  }

  const formatSchedule = (task: ScheduledTask) => {
    if (task.schedule_type === 'cron') {
      return task.cron_expression || 'N/A'
    } else if (task.schedule_type === 'interval') {
      const seconds = task.interval_seconds || 0
      if (seconds < 60) return `Every ${seconds} seconds`
      if (seconds < 3600) return `Every ${Math.floor(seconds / 60)} minutes`
      if (seconds < 86400) return `Every ${Math.floor(seconds / 3600)} hours`
      return `Every ${Math.floor(seconds / 86400)} days`
    }
    return 'N/A'
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleString()
  }

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return 'N/A'
    if (seconds < 60) return `${seconds.toFixed(2)}s`
    return `${(seconds / 60).toFixed(2)}m`
  }

  const formatTaskTypeLabel = (type: string) =>
    type
      ?.toLowerCase()
      .split('_')
      .map(part => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ') || 'Task'

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-ink"></div>
      </div>
    )
  }

  if (!task) {
    return null
  }

  return (
    <DashboardPageShell
      title={task.name}
      description={task.description || `Review schedule, run history, and configuration for this ${formatTaskTypeLabel(task.task_type).toLowerCase()} task.`}
      icon={Clock}
      badge="Task Details"
      maxWidthClassName="max-w-6xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Scheduled Tasks', href: '/scheduled-tasks' },
        { label: task.name },
      ]}
      stats={[
        { label: 'Type', value: formatTaskTypeLabel(task.task_type) },
        { label: 'State', value: task.is_active ? 'Active' : 'Paused' },
        { label: 'Next Run', value: task.next_run_at ? formatDate(task.next_run_at) : 'Not scheduled' },
      ]}
      actions={
        <>
          <button
            onClick={toggleTask}
            className={`inline-flex items-center gap-2 rounded-[1rem] px-4 py-3 text-sm font-semibold transition-colors ${
              task.is_active
                ? 'border border-tan bg-sand text-gold hover:bg-sand-deep'
                : 'border border-leaf-wash bg-leaf-wash text-leaf hover:bg-leaf-wash'
            }`}
          >
            {task.is_active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {task.is_active ? 'Pause' : 'Activate'}
          </button>
          <button
            onClick={executeTask}
            className="inline-flex items-center gap-2 rounded-[1rem] border border-leaf-wash bg-leaf-wash px-4 py-3 text-sm font-semibold text-leaf transition-colors hover:bg-leaf-wash"
          >
            <Play className="w-4 h-4" />
            Run Now
          </button>
          <button
            onClick={() => setDeleteModal(true)}
            className="inline-flex items-center gap-2 rounded-[1rem] border border-blush-wash bg-cream px-4 py-3 text-sm font-semibold text-wine transition-colors hover:bg-blush-wash"
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Status Card */}
          <DashboardPagePanel className="p-6">
            <h2 className="mb-4 text-[11px] font-semibold text-clay">Status</h2>
            <div className="space-y-4">
              <div>
                <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold ${
                  task.is_active ? 'bg-leaf-wash text-leaf' : 'bg-sand text-ink-mute'
                }`}>
                  {task.is_active ? <CheckCircle className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                  {task.is_active ? 'Active' : 'Paused'}
                </span>
              </div>
              
              {task.last_run_at && (
                <div className="text-sm text-ink-soft">
                  <p className="mb-1 font-semibold text-ink">Last Run</p>
                  <p>{formatDate(task.last_run_at)}</p>
                  {task.last_run_status && (
                    <span className={`mt-1 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${getStatusColor(task.last_run_status)}`}>
                      {task.last_run_status === 'success'
                        ? <CheckCircle className="w-3 h-3" />
                        : task.last_run_status === 'running'
                          ? <Loader2 className="w-3 h-3 motion-safe:animate-spin" />
                          : <XCircle className="w-3 h-3" />}
                      {task.last_run_status}
                    </span>
                  )}
                </div>
              )}
              
              {task.next_run_at && (
                <div className="text-sm text-ink-soft">
                  <p className="mb-1 font-semibold text-ink">Next Run</p>
                  <p>{formatDate(task.next_run_at)}</p>
                </div>
              )}
            </div>
          </DashboardPagePanel>

          {/* Task Details */}
          <DashboardPagePanel className="lg:col-span-2 p-6">
            <h2 className="mb-4 text-lg font-semibold text-ink">Task Details</h2>
            
            {task.description && (
              <div className="mb-6 rounded-[1.2rem] border border-black/10 bg-cream p-4">
                <p className="text-sm text-ink-soft">{task.description}</p>
              </div>
            )}
            
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-ink-mute">Schedule Type</label>
                <p className="text-ink capitalize">{task.schedule_type}</p>
              </div>
              
              <div>
                <label className="mb-1 block text-sm font-medium text-ink-mute">Schedule</label>
                <div className="flex items-center gap-2 text-ink">
                  <Calendar className="w-4 h-4 text-ash" />
                  {formatSchedule(task)}
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-ink-mute">Task Type</label>
                <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold ${getTypeColor(task.task_type)}`}>
                  {getTypeIcon(task.task_type)}
                  {formatTaskTypeLabel(task.task_type)}
                </span>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-ink-mute">Execution Count</label>
                <div className="flex items-center gap-2 text-ink">
                  <Activity className="w-4 h-4 text-ash" />
                  {executions.length} recent run{executions.length === 1 ? '' : 's'}
                </div>
              </div>
              
              {task.config && Object.keys(task.config).length > 0 && (
                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium text-ink-mute">Configuration</label>
                  <pre className="overflow-x-auto rounded-[1.2rem] border border-black/10 bg-cream p-4 text-sm text-ink">
                    {JSON.stringify(task.config, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </DashboardPagePanel>
        </div>

        {/* Metadata */}
        <DashboardPagePanel className="mt-6 p-6">
          <h2 className="mb-4 text-lg font-semibold text-ink">Metadata</h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-ink-mute">Created</label>
              <p className="text-ink">{formatDate(task.created_at)}</p>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink-mute">Last Updated</label>
              <p className="text-ink">{formatDate(task.updated_at)}</p>
            </div>
          </div>
        </DashboardPagePanel>

        {/* Execution History */}
        <DashboardPagePanel className="mt-6 overflow-hidden">
          <div className="border-b border-sand-deep p-6">
            <div className="flex items-center gap-2">
              <div className="rounded-[1rem] bg-sand-deep p-2.5">
                <Activity className="w-5 h-5 text-ink" />
              </div>
              <h2 className="text-lg font-semibold text-ink">Execution History</h2>
            </div>
          </div>

          <div className="p-6">
            {executionsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 motion-safe:animate-spin text-ink" />
              </div>
            ) : executions.length === 0 ? (
              <div className="text-center py-12">
                <Activity className="w-12 h-12 text-ash mx-auto mb-3" />
                <p className="text-ink-soft">No execution history yet</p>
              </div>
            ) : (
              <div className="space-y-4">
                {executions.map((execution) => (
                  <div
                    key={execution.id}
                    className="rounded-[1.3rem] border border-black/10 bg-white/70 p-4 transition-colors hover:border-black/15"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${getStatusColor(execution.status)}`}>
                          {execution.status === 'success'
                            ? <CheckCircle className="w-3 h-3" />
                            : execution.status === 'running'
                              ? <Loader2 className="w-3 h-3 motion-safe:animate-spin" />
                              : <XCircle className="w-3 h-3" />}
                          {execution.status}
                        </span>
                        {execution.execution_time_seconds !== null && (
                          <span className="text-sm text-ink-soft">
                            Duration: {formatDuration(execution.execution_time_seconds)}
                          </span>
                        )}
                      </div>
                      <span className="text-sm text-ink-mute">
                        {formatDate(execution.started_at)}
                      </span>
                    </div>
                    
                    {execution.error_message && (
                      <div className="rounded-[1rem] border border-blush-wash bg-white p-3">
                        <p className="text-sm font-medium text-wine mb-1">Error</p>
                        <p className="text-sm text-danger">{execution.error_message}</p>
                      </div>
                    )}
                    
                    {execution.result && (
                      <div className="mt-2">
                        <p className="text-sm font-medium text-ink-soft mb-1">Result</p>
                        <pre className="overflow-x-auto rounded-[1rem] border border-black/10 bg-cream p-3 text-xs text-ink">
                          {JSON.stringify(execution.result, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </DashboardPagePanel>

      {/* Delete Modal */}
      {deleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4">
          <div className="w-full max-w-md rounded-[1.7rem] border border-line bg-cream p-6 shadow-soft">
            <div className="flex items-center gap-3 mb-4">
              <div className="rounded-[1rem] bg-sand-deep p-2.5">
                <AlertCircle className="w-6 h-6 text-danger" />
              </div>
              <h3 className="text-lg font-semibold text-ink">Delete Task</h3>
            </div>
            
            <p className="text-ink-soft mb-6">
              Are you sure you want to delete <span className="font-semibold">{task.name}</span>? 
              This action cannot be undone.
            </p>
            
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteModal(false)}
                disabled={deleting}
                className="rounded-[1rem] border border-black/10 bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:bg-cream disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
              >
                {deleting ? (
                  <>
                    <Loader2 className="w-4 h-4 motion-safe:animate-spin" />
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
    </DashboardPageShell>
  )
}
