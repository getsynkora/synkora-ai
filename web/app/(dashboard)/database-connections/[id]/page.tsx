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
    if (status === 'active') return 'bg-[#e8f4ee] text-[#2d8b69]'
    if (status === 'inactive') return 'bg-[#f1eadc] text-[#6e675d]'
    if (status === 'error') return 'bg-[#fbe9e7] text-[#b44736]'
    return 'bg-[#f8eed9] text-[#ad7d25]' // pending
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
      case 'POSTGRESQL': return 'bg-[#e7f0ff] text-[#325b93]'
      case 'ELASTICSEARCH': return 'bg-[#efe7f7] text-[#6b4d86]'
      case 'MYSQL': return 'bg-[#f7eadb] text-[#9c6228]'
      case 'MONGODB': return 'bg-[#e8f4ee] text-[#2d8b69]'
      default: return 'bg-[#f3ecde] text-[#6e675d]'
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
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-red-600"></div>
          <p className="text-gray-600">Loading connection details...</p>
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
          <Link href="/" className="flex items-center gap-1 text-gray-500 transition-colors hover:text-[#171717]">
            <Home className="h-3.5 w-3.5" />
            Home
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
          <Link href="/database-connections" className="text-gray-500 transition-colors hover:text-[#171717]">
            Database Connections
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
          <span className="truncate font-medium text-gray-900">{connection.name}</span>
        </div>

        <div className="mb-6 overflow-hidden rounded-[2rem] border border-[#eadfce] bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.96),_rgba(247,240,231,0.94)_50%,_rgba(237,230,220,0.92)_100%)] shadow-[0_28px_80px_-42px_rgba(88,63,39,0.32)]">
          <div className="flex flex-col gap-6 p-6 md:p-8">
            <Link
              href="/database-connections"
              className="inline-flex w-fit items-center gap-2 rounded-full border border-[#dbcdb9] bg-white/80 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:border-[#cdb79d] hover:text-gray-900"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Connections
            </Link>

            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl space-y-3">
                <div className="inline-flex items-center gap-2 rounded-full border border-[#dfd1be] bg-white/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7c5d45]">
                  <Database className="h-3.5 w-3.5" />
                  Connection Details
                </div>

                <div className="flex items-start gap-4">
                  <div className={`rounded-[1.2rem] p-3.5 shadow-[0_16px_30px_-24px_rgba(74,49,22,0.3)] ${getTypeColor(connection.type)}`}>
                    <Database className="h-6 w-6" />
                  </div>
                  <div className="min-w-0">
                    <h1 className="truncate text-3xl font-semibold tracking-[-0.04em] text-gray-950 md:text-[2.6rem]">
                      {connection.name}
                    </h1>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${getTypeColor(connection.type)}`}>
                        {connection.type}
                      </span>
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${getStatusColor(connection.status)}`}>
                        {getStatusIcon(connection.status)}
                        {getStatusText(connection.status)}
                      </span>
                    </div>
                    {connection.description && (
                      <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-600">
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
                  className="inline-flex items-center gap-2 rounded-full bg-[#171717] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
                >
                  {testing ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
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
                  className="inline-flex items-center gap-2 rounded-full border border-[#ddd2c2] bg-white px-5 py-3 text-sm font-semibold text-gray-700 transition-colors hover:border-[#ccb59a] hover:text-gray-900"
                >
                  <Edit className="h-4 w-4" />
                  Edit
                </Link>
                <button
                  onClick={() => setDeleteModal(true)}
                  className="inline-flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-5 py-3 text-sm font-semibold text-red-600 transition-colors hover:bg-red-100"
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
            <div className="rounded-[1.7rem] border border-black/10 bg-white/80 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-gray-500">Status</p>
              <div className="mt-4 space-y-4">
                <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold ${getStatusColor(connection.status)}`}>
                  {getStatusIcon(connection.status)}
                  {getStatusText(connection.status)}
                </span>

                <div className="grid gap-3">
                  <div className="rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-4 py-3">
                    <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Last Tested</div>
                    <div className="mt-1 text-sm font-semibold text-gray-900">{formatDateTime(connection.last_tested_at)}</div>
                  </div>

                  <div className="rounded-[1.15rem] border border-black/10 bg-[#eef7f1] px-4 py-3">
                    <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Last Test Status</div>
                    <div className="mt-1 text-sm font-semibold text-gray-900">
                      {getLastTestStatusText(connection.last_test_status)}
                    </div>
                  </div>
                </div>

                {connection.last_error && (
                  <div className="rounded-[1.2rem] border border-red-200 bg-red-50/90 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-red-700">Last Error</p>
                    <p className="mt-2 text-sm leading-6 text-red-700">{connection.last_error}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-[1.7rem] border border-black/10 bg-white/80 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-gray-500">Metadata</p>
              <div className="mt-4 grid gap-3">
                <div className="rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-4 py-3">
                  <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Created</div>
                  <div className="mt-1 text-sm font-semibold text-gray-900">{formatDateTime(connection.created_at)}</div>
                </div>
                <div className="rounded-[1.15rem] border border-black/10 bg-[#f4efe4] px-4 py-3">
                  <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Last Updated</div>
                  <div className="mt-1 text-sm font-semibold text-gray-900">{formatDateTime(connection.updated_at)}</div>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-[1.8rem] border border-black/10 bg-white/80 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)] md:p-7">
              <div className="mb-5 flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f3ecde] p-2.5">
                  <Server className="h-[18px] w-[18px] text-[#171717]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Connection Details</h2>
                  <p className="text-sm text-gray-500">Core host and credential information</p>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-[1.2rem] border border-black/10 bg-[#fcfaf5] p-4">
                  <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Host</div>
                  <div className="mt-2 flex items-start gap-2">
                    <p className="min-w-0 flex-1 break-all font-mono text-sm font-semibold text-gray-900">{connection.host}</p>
                    <button
                      onClick={() => copyToClipboard(connection.host)}
                      className="rounded-full border border-black/10 p-2 text-gray-500 transition-colors hover:bg-white hover:text-[#171717]"
                    >
                      <Copy className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="rounded-[1.2rem] border border-black/10 bg-[#fcfaf5] p-4">
                  <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Port</div>
                  <div className="mt-2 font-mono text-sm font-semibold text-gray-900">{connection.port}</div>
                </div>

                <div className="rounded-[1.2rem] border border-black/10 bg-[#eef7f1] p-4">
                  <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Database</div>
                  <div className="mt-2 font-mono text-sm font-semibold text-gray-900">{connection.database || 'Not configured'}</div>
                </div>

                <div className="rounded-[1.2rem] border border-black/10 bg-[#f4efe4] p-4">
                  <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Username</div>
                  <div className="mt-2 font-mono text-sm font-semibold text-gray-900">{connection.username || 'Not configured'}</div>
                </div>
              </div>
            </div>

            <div className="rounded-[1.8rem] border border-black/10 bg-white/80 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)] md:p-7">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Connection String</h2>
                  <p className="text-sm text-gray-500">Quick copy reference for this connection</p>
                </div>
                <button
                  onClick={() => copyToClipboard(connectionString)}
                  className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-[#fcfaf5] px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:bg-white hover:text-[#171717]"
                >
                  <Copy className="h-4 w-4" />
                  Copy
                </button>
              </div>

              <div className="rounded-[1.3rem] border border-black/10 bg-[#fcfaf5] p-4">
                <p className="break-all font-mono text-sm leading-6 text-gray-900">{connectionString}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {deleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.18)]">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-[1rem] bg-red-50 p-2.5">
                <Trash2 className="h-6 w-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Delete Connection</h3>
            </div>

            <p className="mb-6 text-gray-600">
              Are you sure you want to delete <span className="font-semibold text-gray-900">{connection.name}</span>?
              This action cannot be undone.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteModal(false)}
                disabled={deleting}
                className="rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
              >
                {deleting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
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
