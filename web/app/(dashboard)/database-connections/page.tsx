'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { apiClient } from '@/lib/api/client'
import {
  Database,
  Plus,
  Trash2,
  Edit,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Filter,
  AlertCircle,
  Server,
  MoreHorizontal,
  Home,
  ChevronRight,
  FolderOpen
} from 'lucide-react'

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

export default function DatabaseConnectionsPage() {
  const [connections, setConnections] = useState<DatabaseConnection[]>([])
  const [filteredConnections, setFilteredConnections] = useState<DatabaseConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; connection: DatabaseConnection | null }>({
    show: false,
    connection: null,
  })
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchConnections()
  }, [])

  useEffect(() => {
    filterConnections()
  }, [searchQuery, filterType, filterStatus, connections])

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest('[data-db-menu-root="true"]')) return
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

  const fetchConnections = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getDatabaseConnections()
      setConnections(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      toast.error('Failed to load database connections')
    } finally {
      setLoading(false)
    }
  }

  const filterConnections = () => {
    let filtered = connections

    if (searchQuery) {
      filtered = filtered.filter(conn =>
        conn.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        conn.type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        conn.host?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    if (filterType !== 'all') {
      filtered = filtered.filter(conn => conn.type === filterType)
    }

    if (filterStatus !== 'all') {
      filtered = filtered.filter(conn => conn.status === filterStatus)
    }

    setFilteredConnections(filtered)
  }

  const confirmDelete = async () => {
    if (!deleteModal.connection) return

    setDeleting(true)
    try {
      await apiClient.deleteDatabaseConnection(deleteModal.connection.id.toString())
      toast.success('Database connection deleted successfully')
      setDeleteModal({ show: false, connection: null })
      fetchConnections()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete connection')
    } finally {
      setDeleting(false)
    }
  }

  const openDeleteModal = (connection: DatabaseConnection) => {
    setDeleteModal({ show: true, connection })
  }

  const closeDeleteModal = () => {
    setDeleteModal({ show: false, connection: null })
  }

  const getTypeIcon = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'POSTGRESQL': return <Database className="w-4 h-4" />
      case 'ELASTICSEARCH': return <Server className="w-4 h-4" />
      default: return <Database className="w-4 h-4" />
    }
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

  const getStatusColor = (status: string) => {
    if (status === 'active') return 'bg-[#e8f4ee] text-[#2d8b69]'
    if (status === 'inactive') return 'bg-[#f1eadc] text-[#6e675d]'
    if (status === 'error') return 'bg-[#fbe9e7] text-[#b44736]'
    return 'bg-[#f8eed9] text-[#ad7d25]' // pending
  }

  const getStatusIcon = (status: string) => {
    if (status === 'active') return <CheckCircle className="w-3 h-3" />
    if (status === 'inactive') return <XCircle className="w-3 h-3" />
    if (status === 'error') return <AlertCircle className="w-3 h-3" />
    return <Clock className="w-3 h-3" /> // pending
  }

  const getStatusText = (status: string) => {
    if (status === 'active') return 'Active'
    if (status === 'inactive') return 'Inactive'
    if (status === 'error') return 'Error'
    return 'Pending'
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never'

    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const uniqueTypes = Array.from(new Set(connections.map(c => c.type)))

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-red-600"></div>
          <p className="text-gray-600">Loading your database connections...</p>
        </div>
      </div>
    )
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
          <span className="font-medium text-gray-900">Database Connections</span>
        </div>

        <div className="mb-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight text-gray-900 md:text-3xl">Database Connections</h1>
              <p className="mt-1 hidden text-sm text-gray-600 sm:block">
                Manage database connections for data analysis agents
              </p>
            </div>
            <Link
              href="/database-connections/create"
              className="inline-flex flex-shrink-0 items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
            >
              <Plus className="h-4 w-4 md:h-5 md:w-5" />
              <span className="hidden sm:inline">Add Connection</span>
              <span className="sm:hidden">Add</span>
            </Link>
          </div>

          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f3ecde] p-2.5">
                  <Database className="h-[18px] w-[18px] text-[#171717]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Total</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">{connections.length}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#e8f4ee] p-2.5">
                  <CheckCircle className="h-[18px] w-[18px] text-[#2d8b69]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Active</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {connections.filter(c => c.status === 'active').length}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f1eadc] p-2.5">
                  <XCircle className="h-[18px] w-[18px] text-[#5b564e]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Inactive</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {connections.filter(c => c.status === 'inactive').length}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f8eed9] p-2.5">
                  <Clock className="h-[18px] w-[18px] text-[#ad7d25]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Pending</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {connections.filter(c => c.status === 'pending').length}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-[1.3rem] border border-black/10 bg-white/80 p-3 shadow-[0_12px_28px_rgba(0,0,0,0.04)]">
            <div className="flex flex-col gap-3 lg:flex-row">
              <div className="relative flex-1">
                <Search className="absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search database connections..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] py-3 pl-11 pr-4 text-sm text-gray-900 focus:border-[#2d8b69] focus:outline-none focus:ring-2 focus:ring-[#2d8b69]/15"
                />
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">
                <div className="flex items-center gap-2 rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] px-3">
                  <Filter className="h-4 w-4 text-gray-400" />
                  <select
                    value={filterType}
                    onChange={(e) => setFilterType(e.target.value)}
                    className="min-w-[140px] bg-transparent py-3 text-sm text-gray-700 focus:outline-none"
                  >
                    <option value="all">All Types</option>
                    {uniqueTypes.map(type => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center gap-2 rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] px-3">
                  <CheckCircle className="h-4 w-4 text-gray-400" />
                  <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="min-w-[140px] bg-transparent py-3 text-sm text-gray-700 focus:outline-none"
                  >
                    <option value="all">All Status</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="pending">Pending</option>
                    <option value="error">Error</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-[1.3rem] border border-red-200 bg-red-50/90 p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-red-600" />
              <p className="text-red-700">{error}</p>
            </div>
          </div>
        )}

        {filteredConnections.length === 0 ? (
          <div className="rounded-[2rem] border border-black/10 bg-white/80 p-10 text-center shadow-[0_22px_55px_rgba(0,0,0,0.06)]">
            <div className="relative mx-auto mb-6 h-28 w-28">
              <div className="absolute inset-0 rotate-6 rounded-[1.75rem] bg-[#f3ecde]"></div>
              <div className="absolute inset-0 flex items-center justify-center rounded-[1.75rem] border border-black/10 bg-white shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
                <FolderOpen className="h-10 w-10 text-[#2d8b69]" />
              </div>
            </div>

            <h3 className="mb-2 text-xl font-semibold text-gray-900">
              {connections.length === 0 ? 'No database connections yet' : 'No results found'}
            </h3>
            <p className="mx-auto mb-6 max-w-md text-gray-600">
              {connections.length === 0
                ? 'Add your first database connection to enable data analysis.'
                : 'Try adjusting your search or filter criteria.'}
            </p>
            {connections.length === 0 && (
              <Link
                href="/database-connections/create"
                className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
              >
                <Plus className="h-5 w-5" />
                Add Connection
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredConnections.map((connection) => (
              <div
                key={connection.id}
                className="group relative flex min-h-[300px] flex-col rounded-[1.7rem] border border-black/10 bg-white/80 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-all hover:-translate-y-0.5 hover:border-black/15 hover:shadow-[0_22px_50px_rgba(0,0,0,0.08)]"
              >
                <div
                  className="absolute right-4 top-4 z-20"
                  data-db-menu-root="true"
                >
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setOpenMenuId(openMenuId === connection.id ? null : connection.id)
                    }}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-black/10 bg-white/90 text-[#5b564e] shadow-[0_8px_18px_rgba(0,0,0,0.08)] transition-colors hover:bg-white hover:text-[#171717]"
                    aria-label={`Open actions for ${connection.name}`}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </button>

                  {openMenuId === connection.id && (
                    <div className="absolute right-0 top-11 w-44 overflow-hidden rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] py-1.5 shadow-[0_20px_45px_rgba(0,0,0,0.14)]">
                      <Link
                        href={`/database-connections/${connection.id}/edit`}
                        onClick={() => setOpenMenuId(null)}
                        className="flex items-center gap-2.5 px-4 py-2.5 text-sm font-medium text-[#171717] transition-colors hover:bg-[#f3ecde]"
                      >
                        <Edit className="h-4 w-4" />
                        Edit
                      </Link>
                      <button
                        type="button"
                        onClick={() => {
                          setOpenMenuId(null)
                          openDeleteModal(connection)
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
                  href={`/database-connections/${connection.id}`}
                  className="flex flex-1 flex-col p-5 pr-16 focus:outline-none"
                  aria-label={`Open ${connection.name}`}
                >
                  <div className="mb-4 flex items-start gap-3">
                    <div className={`rounded-[1.1rem] p-3 transition-colors ${getTypeColor(connection.type)}`}>
                      {getTypeIcon(connection.type)}
                    </div>
                    <div className="min-w-0">
                      <h3 className="truncate text-[1.05rem] font-semibold text-gray-900">
                        {connection.name}
                      </h3>
                      <p className="mt-1 truncate text-sm text-gray-500">
                        {connection.host}:{connection.port}
                      </p>
                    </div>
                  </div>

                  <div className="mb-4 flex flex-wrap gap-2">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${getStatusColor(connection.status)}`}>
                      {getStatusIcon(connection.status)}
                      {getStatusText(connection.status)}
                    </span>
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] ${getTypeColor(connection.type)}`}>
                      {connection.type}
                    </span>
                  </div>

                  <p className="mb-4 line-clamp-2 text-sm text-gray-600">
                    {connection.description || 'No description added'}
                  </p>

                  <div className="grid grid-cols-3 gap-2.5">
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-3 py-3">
                      <div className="break-words text-[10px] font-medium uppercase leading-snug tracking-[0.1em] text-gray-500">Database</div>
                      <div className="mt-1 truncate text-sm font-semibold text-gray-900">
                        {connection.database || 'N/A'}
                      </div>
                    </div>
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#eef7f1] px-3 py-3">
                      <div className="break-words text-[10px] font-medium uppercase leading-snug tracking-[0.1em] text-gray-500">User</div>
                      <div className="mt-1 truncate text-sm font-semibold text-gray-900">
                        {connection.username || 'N/A'}
                      </div>
                    </div>
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#f4efe4] px-3 py-3">
                      <div className="break-words text-[10px] font-medium uppercase leading-snug tracking-[0.1em] text-gray-500">Tested</div>
                      <div className="mt-1 text-sm font-semibold text-gray-900">
                        {formatDate(connection.last_tested_at)}
                      </div>
                    </div>
                  </div>
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>

      {deleteModal.show && deleteModal.connection && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.18)]">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-[1rem] bg-red-50 p-2.5">
                <Trash2 className="h-6 w-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Delete Connection</h3>
            </div>

            <p className="mb-6 text-gray-600">
              Are you sure you want to delete <span className="font-semibold text-gray-900">"{deleteModal.connection.name}"</span>?
              This action cannot be undone and will permanently remove this database connection.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={closeDeleteModal}
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
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
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
