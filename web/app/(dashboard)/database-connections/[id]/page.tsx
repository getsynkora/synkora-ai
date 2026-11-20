'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  Database,
  ArrowLeft,
  Edit,
  Trash2,
  TestTube,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Loader2,
  Copy,
  Home,
  ChevronRight,
  Server
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { extractErrorMessage } from '@/lib/api/error'

interface DatabaseConnection {
  id: number
  name: string
  description: string | null
  type: string
  host: string
  port: number
  database: string | null
  username: string | null
  status: string
  last_tested_at: string | null
  last_test_status: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export default function DatabaseConnectionDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const [connection, setConnection] = useState<DatabaseConnection | null>(null)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)
  const [deleteModal, setDeleteModal] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchConnection()
  }, [params.id])

  const fetchConnection = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getDatabaseConnection(params.id as string)
      setConnection(data)
    } catch {
      toast.error('Failed to load connection details')
      router.push('/database-connections')
    } finally {
      setLoading(false)
    }
  }

  const testConnection = async () => {
    setTesting(true)
    try {
      const data = await apiClient.testDatabaseConnection(params.id as string)
      if (data.success) {
        toast.success('Connection test successful')
        fetchConnection() // Refresh to get updated test status
      } else {
        toast.error(data.message || 'Connection test failed')
      }
    } catch (error: any) {
      toast.error(extractErrorMessage(error, 'Failed to test connection'))
    } finally {
      setTesting(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await apiClient.deleteDatabaseConnection(params.id as string)
      toast.success('Connection deleted successfully')
      router.push('/database-connections')
    } catch (error: any) {
      toast.error(extractErrorMessage(error, 'Failed to delete connection'))
    } finally {
      setDeleting(false)
      setDeleteModal(false)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  }

  const getStatusColor = (status: string) => {
    if (status === 'active') return 'bg-leaf-wash text-leaf'
    if (status === 'inactive') return 'bg-sand-deep text-ink-mute'
    if (status === 'error') return 'bg-blush-wash text-danger'
    return 'bg-sand-deep text-gold' // pending
  }

  const getStatusIcon = (status: string) => {
    if (status === 'active') return <CheckCircle className="w-4 h-4" />
    if (status === 'inactive') return <XCircle className="w-4 h-4" />
    if (status === 'error') return <AlertCircle className="w-4 h-4" />
    return <Clock className="w-4 h-4" /> // pending
  }

  const getStatusText = (status: string) => {
    if (status === 'active') return 'Active'
    if (status === 'inactive') return 'Inactive'
    if (status === 'error') return 'Error'
    return 'Pending'
  }

  const getTypeColor = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'POSTGRESQL': return 'bg-sky-wash text-azure'
      case 'ELASTICSEARCH': return 'bg-sand-deep text-ink-soft'
      case 'MYSQL': return 'bg-sand-deep text-gold'
      case 'MONGODB': return 'bg-leaf-wash text-leaf'
      default: return 'bg-sand text-ink-mute'
    }
  }

  const formatDateTime = (value: string | null) => {
    if (!value) return 'Never'
    return new Date(value).toLocaleString()
  }

  const getLastTestStatusText = (status: string | null) => {
    if (!status) return 'Not available'
    if (status === 'success') return 'Success'
    if (status === 'failed') return 'Failed'
    return getStatusText(status)
  }

  const authSegment = connection?.username ? `${connection.username}@` : ''
  const databaseSegment = connection?.database || ''
  const connectionString = `${connection?.type.toLowerCase()}://${authSegment}${connection?.host}:${connection?.port}/${databaseSegment}`

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 motion-safe:animate-spin rounded-full border-b-2 border-danger"></div>
          <p className="text-ink-soft">Loading connection details…</p>
        </div>
      </div>
    )
  }

  if (!connection) {
    return null
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-4 flex items-center gap-1.5 text-sm">
          <Link href="/" className="flex items-center gap-1 text-ink-mute transition-colors hover:text-ink">
            <Home className="h-3.5 w-3.5" />
            Home
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-ash" />
          <Link href="/database-connections" className="text-ink-mute transition-colors hover:text-ink">
            Database Connections
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-ash" />
          <span className="truncate font-medium text-ink">{connection.name}</span>
        </div>

        <div className="bg-cream mb-6 overflow-hidden rounded-[2rem] border border-sand-deep shadow-soft">
          <div className="flex flex-col gap-6 p-6 md:p-8">
            <Link
              href="/database-connections"
              className="inline-flex w-fit items-center gap-2 rounded-full border border-line bg-white/80 px-4 py-2 text-sm font-semibold text-ink-soft transition-colors hover:border-tan hover:text-ink"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Connections
            </Link>

            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl space-y-3">

                <div className="flex items-start gap-4">
                  <div className={`rounded-[1.2rem] p-3.5 shadow-soft ${getTypeColor(connection.type)}`}>
                    <Database className="h-6 w-6" />
                  </div>
                  <div className="min-w-0">
                    <h1 className="truncate text-3xl font-semibold tracking-[-0.04em] text-ink md:text-[2.6rem]">
                      {connection.name}
                    </h1>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ${getTypeColor(connection.type)}`}>
                        {connection.type}
                      </span>
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ${getStatusColor(connection.status)}`}>
                        {getStatusIcon(connection.status)}
                        {getStatusText(connection.status)}
                      </span>
                    </div>
                    {connection.description && (
                      <p className="mt-3 max-w-2xl text-sm leading-6 text-ink-soft">
                        {connection.description}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  onClick={testConnection}
                  disabled={testing}
                  className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
                >
                  {testing ? (
                    <>
                      <Loader2 className="h-4 w-4 motion-safe:animate-spin" />
                      Testing...
                    </>
                  ) : (
                    <>
                      <TestTube className="h-4 w-4" />
                      Test Connection
                    </>
                  )}
                </button>
                <Link
                  href={`/database-connections/${params.id as string}/edit`}
                  className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-5 py-3 text-sm font-semibold text-ink-soft transition-colors hover:border-tan hover:text-ink"
                >
                  <Edit className="h-4 w-4" />
                  Edit
                </Link>
                <button
                  onClick={() => setDeleteModal(true)}
                  className="inline-flex items-center gap-2 rounded-full border border-blush bg-blush-wash px-5 py-3 text-sm font-semibold text-danger transition-colors hover:bg-blush-wash"
                >
                  <Trash2 className="h-4 w-4" />
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="space-y-6">
            <div className="rounded-[1.7rem] border border-black/10 bg-white/80 p-5 shadow-soft">
              <p className="text-[11px] font-semibold text-ink-mute">Status</p>
              <div className="mt-4 space-y-4">
                <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold ${getStatusColor(connection.status)}`}>
                  {getStatusIcon(connection.status)}
                  {getStatusText(connection.status)}
                </span>

                <div className="grid gap-3">
                  <div className="rounded-[1.15rem] border border-black/10 bg-cream px-4 py-3">
                    <div className="text-[10px] font-medium text-ink-mute">Last Tested</div>
                    <div className="mt-1 text-sm font-semibold text-ink">{formatDateTime(connection.last_tested_at)}</div>
                  </div>

                  <div className="rounded-[1.15rem] border border-black/10 bg-leaf-wash px-4 py-3">
                    <div className="text-[10px] font-medium text-ink-mute">Last Test Status</div>
                    <div className="mt-1 text-sm font-semibold text-ink">
                      {getLastTestStatusText(connection.last_test_status)}
                    </div>
                  </div>
                </div>

                {connection.last_error && (
                  <div className="rounded-[1.2rem] border border-blush bg-blush-wash/90 p-4">
                    <p className="text-xs font-semibold text-danger">Last Error</p>
                    <p className="mt-2 text-sm leading-6 text-danger">{connection.last_error}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-[1.7rem] border border-black/10 bg-white/80 p-5 shadow-soft">
              <p className="text-[11px] font-semibold text-ink-mute">Metadata</p>
              <div className="mt-4 grid gap-3">
                <div className="rounded-[1.15rem] border border-black/10 bg-cream px-4 py-3">
                  <div className="text-[10px] font-medium text-ink-mute">Created</div>
                  <div className="mt-1 text-sm font-semibold text-ink">{formatDateTime(connection.created_at)}</div>
                </div>
                <div className="rounded-[1.15rem] border border-black/10 bg-paper px-4 py-3">
                  <div className="text-[10px] font-medium text-ink-mute">Last Updated</div>
                  <div className="mt-1 text-sm font-semibold text-ink">{formatDateTime(connection.updated_at)}</div>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-[1.8rem] border border-black/10 bg-white/80 p-6 shadow-soft md:p-7">
              <div className="mb-5 flex items-center gap-3">
                <div className="rounded-[1rem] bg-sand p-2.5">
                  <Server className="h-[18px] w-[18px] text-ink" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-ink">Connection Details</h2>
                  <p className="text-sm text-ink-mute">Core host and credential information</p>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-[1.2rem] border border-black/10 bg-cream p-4">
                  <div className="text-[10px] font-medium text-ink-mute">Host</div>
                  <div className="mt-2 flex items-start gap-2">
                    <p className="min-w-0 flex-1 break-all font-mono text-sm font-semibold text-ink">{connection.host}</p>
                    <button
                      onClick={() => copyToClipboard(connection.host)}
                      className="rounded-full border border-black/10 p-2 text-ink-mute transition-colors hover:bg-white hover:text-ink"
                    >
                      <Copy className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="rounded-[1.2rem] border border-black/10 bg-cream p-4">
                  <div className="text-[10px] font-medium text-ink-mute">Port</div>
                  <div className="mt-2 font-mono text-sm font-semibold text-ink">{connection.port}</div>
                </div>

                <div className="rounded-[1.2rem] border border-black/10 bg-leaf-wash p-4">
                  <div className="text-[10px] font-medium text-ink-mute">Database</div>
                  <div className="mt-2 font-mono text-sm font-semibold text-ink">{connection.database || 'Not configured'}</div>
                </div>

                <div className="rounded-[1.2rem] border border-black/10 bg-paper p-4">
                  <div className="text-[10px] font-medium text-ink-mute">Username</div>
                  <div className="mt-2 font-mono text-sm font-semibold text-ink">{connection.username || 'Not configured'}</div>
                </div>
              </div>
            </div>

            <div className="rounded-[1.8rem] border border-black/10 bg-white/80 p-6 shadow-soft md:p-7">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-ink">Connection String</h2>
                  <p className="text-sm text-ink-mute">Quick copy reference for this connection</p>
                </div>
                <button
                  onClick={() => copyToClipboard(connectionString)}
                  className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-cream px-4 py-2 text-sm font-semibold text-ink-soft transition-colors hover:bg-white hover:text-ink"
                >
                  <Copy className="h-4 w-4" />
                  Copy
                </button>
              </div>

              <div className="rounded-[1.3rem] border border-black/10 bg-cream p-4">
                <p className="break-all font-mono text-sm leading-6 text-ink">{connectionString}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {deleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
          <div className="w-full max-w-md rounded-[1.8rem] border border-black/10 bg-cream p-6 shadow-soft">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-[1rem] bg-sand-deep p-2.5">
                <Trash2 className="h-6 w-6 text-danger" />
              </div>
              <h3 className="text-lg font-semibold text-ink">Delete Connection</h3>
            </div>

            <p className="mb-6 text-ink-soft">
              Are you sure you want to delete <span className="font-semibold text-ink">{connection.name}</span>?
              This action cannot be undone.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteModal(false)}
                disabled={deleting}
                className="rounded-[1rem] border border-black/10 bg-sand-deep px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-line disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
              >
                {deleting ? (
                  <>
                    <Loader2 className="h-4 w-4 motion-safe:animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="h-4 w-4" />
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
