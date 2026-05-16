'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  Database,
  ArrowLeft,
  Save,
  TestTube,
  AlertCircle,
  CheckCircle,
  Loader2
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { extractErrorMessage } from '@/lib/api/error'

interface ConnectionFormData {
  name: string
  description: string
  type: string
  host: string
  port: number
  database: string
  username: string
  password: string
  database_path: string
  status: string
  connection_params: Record<string, any>
}

export default function EditDatabaseConnectionPage() {
  const params = useParams()
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [formData, setFormData] = useState<ConnectionFormData>({
    name: '',
    description: '',
    type: 'POSTGRESQL',
    host: '',
    port: 5432,
    database: '',
    username: '',
    password: '',
    database_path: '',
    status: 'pending',
    connection_params: {}
  })
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchConnection()
  }, [params.id])

  const fetchConnection = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getDatabaseConnection(params.id as string)
      const connParams = data.connection_params || {}
      // For BigQuery: dataset is stored in connection_params.dataset, not username
      const usernameField = data.type === 'BIGQUERY'
        ? (connParams.dataset || '')
        : (data.username || '')
      setFormData({
        name: data.name,
        description: data.description || '',
        type: data.type,
        host: data.host || '',
        port: data.port || 5432,
        database: data.database || '',
        username: usernameField,
        password: '', // Don't populate password for security
        database_path: data.database_path || '',
        status: data.status || 'pending',
        connection_params: connParams,
      })
    } catch {
      toast.error('Failed to load connection')
      router.push('/database-connections')
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (field: keyof ConnectionFormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    setTestResult(null) // Clear test result when form changes
  }

  const handleTypeChange = (type: string) => {
    const defaultPorts: Record<string, number> = {
      POSTGRESQL: 5432,
      SUPABASE: 0,
      ELASTICSEARCH: 9200,
      MYSQL: 3306,
      MONGODB: 27017,
      SQLITE: 0,
      DUCKDB: 0,
      SQLSERVER: 1433,
      CLICKHOUSE: 8123,
      BIGQUERY: 0,
      SNOWFLAKE: 0,
      DATADOG: 0,
      DATABRICKS: 443,
      DOCKER: 0,
    }
    setFormData(prev => ({
      ...prev,
      type,
      port: defaultPorts[type] ?? 5432,
      connection_params: {}
    }))
    setTestResult(null)
  }

  const handleConnectionParamChange = (key: string, value: string) => {
    const coerced: any = value === 'true' ? true : value === 'false' ? false : value
    setFormData(prev => ({
      ...prev,
      connection_params: { ...prev.connection_params, [key]: coerced }
    }))
  }

  const isSQLite = formData.type === 'SQLITE'
  const isDuckDB = formData.type === 'DUCKDB'
  const isPathBased = isSQLite || isDuckDB
  const isBigQuery = formData.type === 'BIGQUERY'
  const isSnowflake = formData.type === 'SNOWFLAKE'
  const isSupabase = formData.type === 'SUPABASE'
  const isCloudOnly = isBigQuery || isSnowflake || isSupabase

  const buildBigQueryPayload = (data: typeof formData) => {
    if (!isBigQuery) return data
    const { password: _, connection_params: _cp, username: _u, ...rest } = data
    const newParams: Record<string, any> = {}
    // Only include service_account_json if a new one was provided
    if (data.password) {
      try {
        newParams.service_account_json = JSON.parse(data.password)
      } catch {
        // Invalid JSON — validation toast already shown before submit
      }
    }
    // Always sync dataset from the username field
    if (data.username) newParams.dataset = data.username
    return {
      ...rest,
      // Only include connection_params if there is something to update
      ...(Object.keys(newParams).length > 0 ? { connection_params: newParams } : {}),
    }
  }

  const testConnection = async () => {
    if (isPathBased && !formData.database_path) {
      toast.error('Please provide a database file path')
      return
    }
    if (isBigQuery && !formData.database) {
      toast.error('Please provide a Project ID')
      return
    }
    if (isSnowflake && (!formData.host || !formData.username)) {
      toast.error('Please provide Account and Username')
      return
    }
    if (isSupabase && !formData.host) {
      toast.error('Please provide the Project URL')
      return
    }
    if (!isPathBased && !isCloudOnly && (!formData.host || !formData.port)) {
      toast.error('Please fill in host and port')
      return
    }

    setTesting(true)
    setTestResult(null)

    try {
      const data = await apiClient.testDatabaseConnection(params.id as string)
      if (data.success) {
        setTestResult({ success: true, message: 'Connection successful!' })
        toast.success('Connection test successful')
      } else {
        setTestResult({ success: false, message: data.message || 'Connection failed' })
        toast.error('Connection test failed')
      }
    } catch (error: any) {
      const message = extractErrorMessage(error, 'Failed to test connection')
      setTestResult({ success: false, message })
      toast.error(message)
    } finally {
      setTesting(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.name) {
      toast.error('Please provide a connection name')
      return
    }

    if (isPathBased && !formData.database_path) {
      toast.error('Please provide a database file path')
      return
    }
    if (isBigQuery && !formData.database) {
      toast.error('Please provide a Project ID')
      return
    }
    if (isSnowflake && (!formData.host || !formData.username)) {
      toast.error('Please provide Account and Username')
      return
    }
    if (isSupabase && !formData.host) {
      toast.error('Please provide the Project URL')
      return
    }
    if (!isPathBased && !isCloudOnly && (!formData.host || !formData.port)) {
      toast.error('Please fill in host and port')
      return
    }

    setSaving(true)

    try {
      // Only include password if it was changed
      const { password, ...restData } = formData
      const baseData = password ? formData : restData
      let updateData: Record<string, any> = isBigQuery
        ? buildBigQueryPayload(baseData as typeof formData)
        : baseData
      // Convert port=0 (no-port types) to null so backend validation passes
      if ('port' in updateData && (updateData.port === 0 || updateData.port === null)) {
        updateData = { ...updateData, port: null }
      }
      // Don't send connection_params if it's empty — nothing to update
      if (
        updateData.connection_params != null &&
        Object.keys(updateData.connection_params).length === 0
      ) {
        const { connection_params: _, ...withoutParams } = updateData
        updateData = withoutParams
      }

      await apiClient.updateDatabaseConnection(params.id as string, updateData)
      toast.success('Database connection updated successfully')
      router.push(`/database-connections/${params.id}`)
    } catch (error: any) {
      toast.error(extractErrorMessage(error, 'Failed to update connection'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-red-600"></div>
          <p className="text-gray-600">Loading connection settings...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 overflow-hidden rounded-[2rem] border border-[#eadfce] bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.96),_rgba(247,240,231,0.94)_50%,_rgba(237,230,220,0.92)_100%)] shadow-[0_28px_80px_-42px_rgba(88,63,39,0.32)]">
          <div className="flex flex-col gap-6 p-6 md:p-8">
            <Link
              href={`/database-connections/${params.id}`}
              className="inline-flex w-fit items-center gap-2 rounded-full border border-[#dbcdb9] bg-white/80 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:border-[#cdb79d] hover:text-gray-900"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Connection
            </Link>

            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl space-y-3">
                <div className="inline-flex items-center gap-2 rounded-full border border-[#dfd1be] bg-white/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7c5d45]">
                  <Database className="h-3.5 w-3.5" />
                  Edit Connection
                </div>

                <div className="flex items-start gap-4">
                  <div className="rounded-[1.2rem] bg-[#f3ecde] p-3.5 shadow-[0_16px_30px_-24px_rgba(74,49,22,0.3)]">
                    <Database className="h-6 w-6 text-[#171717]" />
                  </div>
                  <div>
                    <h1 className="text-3xl font-semibold tracking-[-0.04em] text-gray-950 md:text-[2.6rem]">
                      Edit Database Connection
                    </h1>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
                      Update connection settings.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[1.5rem] border border-white/70 bg-white/75 px-4 py-3 shadow-[0_20px_45px_-38px_rgba(77,51,28,0.4)] backdrop-blur">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Database Type</p>
                  <p className="mt-2 text-lg font-semibold text-gray-900">{formData.type}</p>
                </div>
                <div className="rounded-[1.5rem] border border-white/70 bg-white/75 px-4 py-3 shadow-[0_20px_45px_-38px_rgba(77,51,28,0.4)] backdrop-blur">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Status</p>
                  <p className="mt-2 text-lg font-semibold text-gray-900">
                    {formData.status.charAt(0).toUpperCase() + formData.status.slice(1)}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-[2rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] p-6 shadow-[0_28px_70px_-48px_rgba(73,45,23,0.32)] md:p-8"
        >
          <div className="space-y-5">
            {/* Basic Information */}
            <div>
              <div className="mb-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Section 1</p>
                <h2 className="mt-2 text-lg font-semibold text-gray-950">Basic Information</h2>
                <p className="mt-1 text-sm text-gray-500">Update the connection name, type, and current status.</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Connection Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    placeholder="My PostgreSQL Database"
                    className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    required
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Description
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => handleInputChange('description', e.target.value)}
                    placeholder="Production database for analytics"
                    rows={3}
                    className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Database Type <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={formData.type}
                    onChange={(e) => handleTypeChange(e.target.value)}
                    className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    required
                  >
                    <optgroup label="SQL Databases">
                      <option value="POSTGRESQL">PostgreSQL</option>
                      <option value="SUPABASE">Supabase (REST API)</option>
                      <option value="MYSQL">MySQL</option>
                      <option value="SQLSERVER">SQL Server (MSSQL)</option>
                      <option value="SQLITE">SQLite</option>
                      <option value="DUCKDB">DuckDB</option>
                    </optgroup>
                    <optgroup label="NoSQL & Search">
                      <option value="MONGODB">MongoDB</option>
                      <option value="ELASTICSEARCH">Elasticsearch</option>
                      <option value="CLICKHOUSE">ClickHouse</option>
                    </optgroup>
                    <optgroup label="Cloud Data Warehouses">
                      <option value="BIGQUERY">BigQuery (Google)</option>
                      <option value="SNOWFLAKE">Snowflake</option>
                      <option value="DATABRICKS">Databricks</option>
                    </optgroup>
                    <optgroup label="Observability &amp; Infrastructure">
                      <option value="DATADOG">Datadog</option>
                      <option value="DOCKER">Docker</option>
                    </optgroup>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Status
                  </label>
                  <select
                    value={formData.status}
                    onChange={(e) => handleInputChange('status', e.target.value)}
                    className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="pending">Pending</option>
                    <option value="error">Error</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    Set to "Active" to enable this connection for use
                  </p>
                </div>
              </div>
            </div>

            {/* Connection Details */}
            <div>
              <div className="mb-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Section 2</p>
                <h2 className="mt-2 text-lg font-semibold text-gray-950">Connection Details</h2>
                <p className="mt-1 text-sm text-gray-500">Update the host, credentials, and provider-specific settings.</p>
              </div>
              
              {isPathBased ? (
                /* SQLite / DuckDB — file path */
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Database File Path <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.database_path}
                      onChange={(e) => handleInputChange('database_path', e.target.value)}
                      placeholder={isDuckDB ? '/path/to/data.duckdb or :memory:' : '/path/to/database.db'}
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      {isDuckDB ? 'Path to DuckDB file, or :memory: for an in-memory database' : 'Full path to your SQLite database file'}
                    </p>
                  </div>
                </div>
              ) : isBigQuery ? (
                /* BigQuery-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      GCP Project ID <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.database}
                      onChange={(e) => handleInputChange('database', e.target.value)}
                      placeholder="my-gcp-project"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Service Account JSON
                    </label>
                    <textarea
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder={'Leave blank to keep current credentials\n{\n  "type": "service_account",\n  ...\n}'}
                      rows={5}
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500 font-mono"
                    />
                    <p className="text-xs text-gray-500 mt-1">Leave blank to keep existing credentials. Stored encrypted.</p>
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">Default Dataset (Optional)</label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="my_dataset"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                  </div>
                </div>
              ) : isSnowflake ? (
                /* Snowflake-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Account Identifier <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="xyz12345.us-east-1"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Username <span className="text-red-500">*</span></label>
                    <input type="text" value={formData.username} onChange={(e) => handleInputChange('username', e.target.value)} placeholder="MYUSER" className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500" required />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
                    <input type="password" value={formData.password} onChange={(e) => handleInputChange('password', e.target.value)} placeholder="Leave blank to keep current" className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Database</label>
                    <input type="text" value={formData.database} onChange={(e) => handleInputChange('database', e.target.value)} placeholder="MY_DATABASE" className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Warehouse</label>
                    <input type="text" value={formData.connection_params?.warehouse || ''} onChange={(e) => handleConnectionParamChange('warehouse', e.target.value)} placeholder="COMPUTE_WH" className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Schema</label>
                    <input type="text" value={formData.connection_params?.schema || ''} onChange={(e) => handleConnectionParamChange('schema', e.target.value)} placeholder="PUBLIC" className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Role (Optional)</label>
                    <input type="text" value={formData.connection_params?.role || ''} onChange={(e) => handleConnectionParamChange('role', e.target.value)} placeholder="SYSADMIN" className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500" />
                  </div>
                </div>
              ) : formData.type === 'ELASTICSEARCH' ? (
                /* Elasticsearch-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Host <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="localhost or elasticsearch.example.com"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Port <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="number"
                      value={formData.port}
                      onChange={(e) => handleInputChange('port', parseInt(e.target.value))}
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Index Name (Optional)
                    </label>
                    <input
                      type="text"
                      value={formData.database}
                      onChange={(e) => handleInputChange('database', e.target.value)}
                      placeholder="my-index (leave blank to access all indices)"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Optional: Specify a default index name. Leave blank to access all indices.
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Username (Optional)
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="elastic"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Only required if Elasticsearch security is enabled
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Password (Optional)
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="Leave blank to keep current password"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Only required if Elasticsearch security is enabled. Leave blank to keep current password.
                    </p>
                  </div>
                </div>
              ) : isSupabase ? (
                /* Supabase — API key auth via PostgREST */
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Project URL <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="https://abcdefghij.supabase.co"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Found in Supabase Dashboard → Settings → API → Project URL
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Anon / Publishable Key <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="Leave blank to keep existing key"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Supabase Dashboard → Settings → API → Project API Keys → <code>anon</code> public key
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Service Role / Secret Key
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="Leave blank to keep existing key"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Supabase Dashboard → Settings → API → Project API Keys → <code>service_role</code> secret key. Stored encrypted.
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      id="use_service_role"
                      checked={formData.connection_params?.use_service_role !== false}
                      onChange={(e) => handleConnectionParamChange('use_service_role', e.target.checked ? 'true' : 'false')}
                      className="h-4 w-4 rounded border-gray-300 text-red-500 focus:ring-red-500"
                    />
                    <label htmlFor="use_service_role" className="text-sm text-gray-700">
                      Use service role key (bypasses Row Level Security — recommended for agents)
                    </label>
                  </div>

                  <div className="rounded-[1.2rem] border border-[#d8e5d9] bg-[#eef7f1] p-4">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-[#2d8b69]" />
                      <div className="text-xs text-[#2d6f58]">
                        <p className="font-medium mb-1">No database password needed</p>
                        <p>This connection uses Supabase's REST API (PostgREST) instead of a direct PostgreSQL connection. Only API keys are required.</p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                /* Standard database fields (PostgreSQL, MySQL, MongoDB) */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Host <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="localhost or db.example.com"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Port <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="number"
                      value={formData.port}
                      onChange={(e) => handleInputChange('port', parseInt(e.target.value))}
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Database Name
                    </label>
                    <input
                      type="text"
                      value={formData.database}
                      onChange={(e) => handleInputChange('database', e.target.value)}
                      placeholder="mydb"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Username
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="dbuser"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Password
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="Leave blank to keep current password"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Leave blank to keep the current password. Enter a new password to update it.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Test Connection Result */}
            {testResult && (
              <div className={`rounded-[1.4rem] border p-4 ${
                testResult.success 
                  ? 'border-[#d8e5d9] bg-[linear-gradient(180deg,_rgba(244,249,245,0.98),_rgba(235,245,238,0.95))]'
                  : 'border-[#e6c0b8] bg-[#fbefec]'
              }`}>
                <div className="flex items-center gap-3">
                  {testResult.success ? (
                    <CheckCircle className="h-5 w-5 text-[#2d8b69]" />
                  ) : (
                    <AlertCircle className="h-5 w-5 text-[#b44736]" />
                  )}
                  <div>
                    <p className={`font-medium ${
                      testResult.success ? 'text-gray-900' : 'text-[#7f301f]'
                    }`}>
                      {testResult.success ? 'Connection Successful' : 'Connection Failed'}
                    </p>
                    <p className={`text-sm ${
                      testResult.success ? 'text-gray-600' : 'text-[#8f3f2c]'
                    }`}>
                      {testResult.message}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-col gap-4 border-t border-[#e6ddd1] pt-6 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                onClick={testConnection}
                disabled={testing || (isPathBased && !formData.database_path) || (isBigQuery && !formData.database) || (isSnowflake && (!formData.host || !formData.username)) || (isSupabase && !formData.host) || (!isPathBased && !isCloudOnly && (!formData.host || !formData.port))}
                className="inline-flex items-center justify-center gap-2 rounded-full border border-[#d7c4aa] bg-white/80 px-5 py-3 text-sm font-semibold text-gray-700 transition-colors hover:border-[#c8b090] hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
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

              <div className="flex flex-col-reverse gap-3 sm:flex-row">
                <Link
                  href={`/database-connections/${params.id}`}
                  className="inline-flex items-center justify-center rounded-full border border-[#ddd2c2] bg-white px-5 py-3 text-sm font-semibold text-gray-700 transition-colors hover:border-[#ccb59a] hover:text-gray-900"
                >
                  Cancel
                </Link>
                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-[#171717] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4" />
                      Save Changes
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
