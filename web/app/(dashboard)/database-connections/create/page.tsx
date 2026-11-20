'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
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
  is_global: boolean
  connection_params: Record<string, any>
}

export default function CreateDatabaseConnectionPage() {
  const router = useRouter()
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
    is_global: false,
    connection_params: {}
  })
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [saving, setSaving] = useState(false)

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
    // Coerce 'true'/'false' strings to actual booleans for JSON serialization
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

  const buildPayload = (data: ConnectionFormData) => {
    const portOrNull = data.port > 0 ? data.port : null

    if (data.type === 'BIGQUERY') {
      let serviceAccountJson: Record<string, any> | null = null
      try {
        serviceAccountJson = JSON.parse(data.password)
      } catch {
        // Will be caught by the validation toast below
      }
      return {
        ...data,
        port: portOrNull,
        password: undefined,
        connection_params: {
          ...data.connection_params,
          ...(serviceAccountJson ? { service_account_json: serviceAccountJson } : {}),
          ...(data.username ? { dataset: data.username } : {}),
        },
      }
    }
    return { ...data, port: portOrNull }
  }

  const testConnection = async () => {
    if (isPathBased && !formData.database_path) {
      toast.error('Please provide a database file path')
      return
    }
    if (isBigQuery && (!formData.database || !formData.password)) {
      toast.error('Please provide Project ID and Service Account JSON')
      return
    }
    if (isBigQuery) {
      try {
        JSON.parse(formData.password)
      } catch {
        toast.error('Service Account JSON is not valid JSON')
        return
      }
    }
    if (isSnowflake && (!formData.host || !formData.username || !formData.password)) {
      toast.error('Please provide Account, Username and Password')
      return
    }
    if (isSupabase && (!formData.host || !formData.username || !formData.password)) {
      toast.error('Please provide Project URL, Anon Key and Service Role Key')
      return
    }
    if (!isPathBased && !isCloudOnly && (!formData.host || !formData.port)) {
      toast.error('Please fill in host and port')
      return
    }

    setTesting(true)
    setTestResult(null)

    try {
      const result = await apiClient.testDatabaseConnectionDetails(buildPayload(formData))
      
      if (result.success) {
        setTestResult({ success: true, message: result.message || 'Connection successful!' })
        toast.success('Connection test successful')
      } else {
        setTestResult({ success: false, message: result.message || 'Connection failed' })
        toast.error('Connection test failed')
      }
    } catch (error: any) {
      const errorMessage = extractErrorMessage(error, 'Failed to test connection')
      setTestResult({ success: false, message: errorMessage })
      toast.error(errorMessage)
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
    if (isBigQuery && (!formData.database || !formData.password)) {
      toast.error('Please provide Project ID and Service Account JSON')
      return
    }
    if (isBigQuery) {
      try {
        JSON.parse(formData.password)
      } catch {
        toast.error('Service Account JSON is not valid JSON')
        return
      }
    }
    if (isSnowflake && (!formData.host || !formData.username || !formData.password)) {
      toast.error('Please provide Account, Username and Password')
      return
    }
    if (isSupabase && (!formData.host || !formData.username || !formData.password)) {
      toast.error('Please provide Project URL, Anon Key and Service Role Key')
      return
    }
    if (!isPathBased && !isCloudOnly && (!formData.host || !formData.port)) {
      toast.error('Please fill in host and port')
      return
    }

    setSaving(true)

    try {
      await apiClient.createDatabaseConnection(buildPayload(formData))
      toast.success('Database connection created successfully')
      router.push('/database-connections')
    } catch (error: any) {
      toast.error(extractErrorMessage(error, 'Failed to create connection'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-5xl">
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
                  <div className="rounded-[1.2rem] bg-sand p-3.5 shadow-soft">
                    <Database className="h-6 w-6 text-ink" />
                  </div>
                  <div>
                    <h1 className="text-3xl font-semibold tracking-[-0.04em] text-ink md:text-[2.6rem]">
                      Create Database Connection
                    </h1>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-soft">
                      Add a new database connection for data analysis.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[1.5rem] border border-white/70 bg-white/75 px-4 py-3 shadow-soft">
                  <p className="text-[11px] font-semibold text-clay">Database Type</p>
                  <p className="mt-2 text-lg font-semibold text-ink">{formData.type}</p>
                </div>
                <div className="rounded-[1.5rem] border border-white/70 bg-white/75 px-4 py-3 shadow-soft">
                  <p className="text-[11px] font-semibold text-clay">Access</p>
                  <p className="mt-2 text-lg font-semibold text-ink">{formData.is_global ? 'Global' : 'Private'}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-[2rem] border border-line bg-white p-6 shadow-soft md:p-8 [&_input[type='text']]:!w-full [&_input[type='text']]:!rounded-[1.15rem] [&_input[type='text']]:!border [&_input[type='text']]:!border-line [&_input[type='text']]:!bg-cream [&_input[type='text']]:!px-4 [&_input[type='text']]:!py-4 [&_input[type='text']]:!text-sm [&_input[type='text']]:!text-ink [&_input[type='text']]:!placeholder-ash [&_input[type='text']]:!transition-[color,background-color,border-color,box-shadow,opacity,transform] [&_input[type='text']]:focus:!border-transparent [&_input[type='text']]:focus:!outline-none [&_input[type='text']]:focus:!ring-2 [&_input[type='text']]:focus:!ring-ink [&_input[type='text']]:focus-visible:!border-transparent [&_input[type='text']]:focus-visible:!outline-none [&_input[type='text']]:focus-visible:!ring-2 [&_input[type='text']]:focus-visible:!ring-ink [&_input[type='password']]:!w-full [&_input[type='password']]:!rounded-[1.15rem] [&_input[type='password']]:!border [&_input[type='password']]:!border-line [&_input[type='password']]:!bg-cream [&_input[type='password']]:!px-4 [&_input[type='password']]:!py-4 [&_input[type='password']]:!text-sm [&_input[type='password']]:!text-ink [&_input[type='password']]:!placeholder-ash [&_input[type='password']]:!transition-[color,background-color,border-color,box-shadow,opacity,transform] [&_input[type='password']]:focus:!border-transparent [&_input[type='password']]:focus:!outline-none [&_input[type='password']]:focus:!ring-2 [&_input[type='password']]:focus:!ring-ink [&_input[type='password']]:focus-visible:!border-transparent [&_input[type='password']]:focus-visible:!outline-none [&_input[type='password']]:focus-visible:!ring-2 [&_input[type='password']]:focus-visible:!ring-ink [&_input[type='number']]:!w-full [&_input[type='number']]:!rounded-[1.15rem] [&_input[type='number']]:!border [&_input[type='number']]:!border-line [&_input[type='number']]:!bg-cream [&_input[type='number']]:!px-4 [&_input[type='number']]:!py-4 [&_input[type='number']]:!text-sm [&_input[type='number']]:!text-ink [&_input[type='number']]:!transition-[color,background-color,border-color,box-shadow,opacity,transform] [&_input[type='number']]:focus:!border-transparent [&_input[type='number']]:focus:!outline-none [&_input[type='number']]:focus:!ring-2 [&_input[type='number']]:focus:!ring-ink [&_input[type='number']]:focus-visible:!border-transparent [&_input[type='number']]:focus-visible:!outline-none [&_input[type='number']]:focus-visible:!ring-2 [&_input[type='number']]:focus-visible:!ring-ink [&_select]:!w-full [&_select]:!rounded-[1.15rem] [&_select]:!border [&_select]:!border-line [&_select]:!bg-cream [&_select]:!px-4 [&_select]:!py-4 [&_select]:!text-sm [&_select]:!text-ink [&_select]:!transition-[color,background-color,border-color,box-shadow,opacity,transform] [&_select]:focus:!border-transparent [&_select]:focus:!outline-none [&_select]:focus:!ring-2 [&_select]:focus:!ring-ink [&_select]:focus-visible:!border-transparent [&_select]:focus-visible:!outline-none [&_select]:focus-visible:!ring-2 [&_select]:focus-visible:!ring-ink [&_textarea]:!w-full [&_textarea]:!rounded-[1.15rem] [&_textarea]:!border [&_textarea]:!border-line [&_textarea]:!bg-cream [&_textarea]:!px-4 [&_textarea]:!py-4 [&_textarea]:!text-sm [&_textarea]:!text-ink [&_textarea]:!placeholder-ash [&_textarea]:!transition-[color,background-color,border-color,box-shadow,opacity,transform] [&_textarea]:focus:!border-transparent [&_textarea]:focus:!outline-none [&_textarea]:focus:!ring-2 [&_textarea]:focus:!ring-ink [&_textarea]:focus-visible:!border-transparent [&_textarea]:focus-visible:!outline-none [&_textarea]:focus-visible:!ring-2 [&_textarea]:focus-visible:!ring-ink [&_label]:!mb-1.5 [&_label]:!block [&_label]:!text-sm [&_label]:!font-semibold [&_label]:!text-ink-soft"
        >
          <div className="space-y-5">
            {/* Basic Information */}
            <div>
              <div className="mb-4">
                <p className="text-[11px] font-semibold text-clay">Section 1</p>
                <h2 className="mt-2 text-lg font-semibold text-ink">Basic Information</h2>
                <p className="mt-1 text-sm text-ink-mute">Define the connection name, type, and visibility.</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-ink-soft mb-1.5">
                    Connection Name <span className="text-leaf">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    placeholder="My PostgreSQL Database"
                    className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    required
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-ink-soft mb-1.5">
                    Description
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => handleInputChange('description', e.target.value)}
                    placeholder="Production database for analytics"
                    rows={3}
                    className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-ink-soft mb-1.5">
                    Database Type <span className="text-leaf">*</span>
                  </label>
                  <select
                    value={formData.type}
                    onChange={(e) => handleTypeChange(e.target.value)}
                    className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
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
                    </optgroup>
                    <optgroup label="Data Analysis Sources">
                      <option value="DATADOG">Datadog (Metrics & Logs)</option>
                      <option value="DATABRICKS">Databricks (SQL Analytics)</option>
                      <option value="DOCKER">Docker (Container Logs)</option>
                    </optgroup>
                  </select>
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-transparent select-none">
                    Availability
                  </label>
                  <label className="flex min-h-[60px] w-full cursor-pointer items-center gap-4 rounded-[1.15rem] border border-line bg-cream px-5 py-4 transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:border-tan">
                    <input
                      type="checkbox"
                      checked={formData.is_global}
                      onChange={(e) => handleInputChange('is_global', e.target.checked)}
                      className="h-5 w-5 shrink-0 rounded border-taupe text-leaf focus:ring-ink"
                    />
                    <span className="block pl-0.5 text-base font-semibold leading-none text-ink-soft">
                      Global Connection (Available to all agents)
                    </span>
                  </label>
                </div>
              </div>
            </div>

            {/* Connection Details */}
            <div>
              <div className="mb-4">
                <p className="text-[11px] font-semibold text-clay">Section 2</p>
                <h2 className="mt-2 text-lg font-semibold text-ink">Connection Details</h2>
                <p className="mt-1 text-sm text-ink-mute">Provide the host, credentials, and provider-specific settings.</p>
              </div>
              
              {formData.type === 'DATADOG' ? (
                /* Datadog-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      API Key <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="••••••••••••••••••••••••••••••••"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Get from Datadog → Integrations → APIs → API Keys
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Application Key <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="••••••••••••••••••••••••••••••••"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Generate in Datadog → Organization Settings → Application Keys
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Site <span className="text-leaf">*</span>
                    </label>
                    <select
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    >
                      <option value="">Select Datadog Site…</option>
                      <option value="datadoghq.com">US1 (datadoghq.com)</option>
                      <option value="us3.datadoghq.com">US3 (us3.datadoghq.com)</option>
                      <option value="us5.datadoghq.com">US5 (us5.datadoghq.com)</option>
                      <option value="datadoghq.eu">EU (datadoghq.eu)</option>
                      <option value="ap1.datadoghq.com">AP1 (ap1.datadoghq.com)</option>
                      <option value="ddog-gov.com">US1-FED (ddog-gov.com)</option>
                    </select>
                    <p className="text-xs text-ink-mute mt-1">
                      Select your Datadog site region
                    </p>
                  </div>
                </div>
              ) : formData.type === 'DATABRICKS' ? (
                /* Databricks-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Server Hostname <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="your-workspace.cloud.databricks.com"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Found in your Databricks workspace URL
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      HTTP Path <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.database_path}
                      onChange={(e) => handleInputChange('database_path', e.target.value)}
                      placeholder="/sql/1.0/warehouses/xxxxxxxxxxxxx"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      SQL Warehouse → Connection Details → HTTP Path
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Access Token <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="••••••••••••••••••••••••••••••••"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      User Settings → Access Tokens → Generate New Token
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Catalog
                    </label>
                    <input
                      type="text"
                      value={formData.database}
                      onChange={(e) => handleInputChange('database', e.target.value)}
                      placeholder="main"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Default catalog name (e.g., 'main')
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Schema
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="default"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Default schema name (e.g., 'default')
                    </p>
                  </div>
                </div>
              ) : formData.type === 'DOCKER' ? (
                /* Docker-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Docker Host <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="unix://var/run/docker.sock or tcp://host:2375"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Local: unix://var/run/docker.sock | Remote: tcp://hostname:2375
                    </p>
                  </div>

                  <div className="md:col-span-2 rounded-[1.2rem] border border-leaf-wash bg-leaf-wash p-4">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-leaf" />
                      <div className="text-xs text-forest">
                        <p className="font-medium mb-1">Security Notes:</p>
                        <ul className="list-disc list-inside space-y-0.5">
                          <li>Local: Requires access to Docker socket (may need permissions)</li>
                          <li>Remote: Ensure Docker daemon is configured securely with TLS</li>
                          <li>Only connect to trusted Docker hosts</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              ) : isPathBased ? (
                /* SQLite / DuckDB — file path */
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Database Filename <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.database_path}
                      onChange={(e) => handleInputChange('database_path', e.target.value)}
                      placeholder={isDuckDB ? 'data.duckdb or :memory:' : 'database.db'}
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      {isDuckDB ? 'Use a provisioned database filename or :memory:. File, network, and extension queries are disabled.' : 'Use the filename of a read-only database provisioned for your workspace.'}
                    </p>
                  </div>
                </div>
              ) : isBigQuery ? (
                /* BigQuery-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      GCP Project ID <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.database}
                      onChange={(e) => handleInputChange('database', e.target.value)}
                      placeholder="my-gcp-project"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">Your Google Cloud project ID</p>
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Service Account JSON <span className="text-leaf">*</span>
                    </label>
                    <textarea
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder={'{\n  "type": "service_account",\n  "project_id": "my-project",\n  ...\n}'}
                      rows={6}
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink font-mono"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Paste the full contents of your service account key JSON file. Stored encrypted.
                    </p>
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Default Dataset (Optional)
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="my_dataset"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                    <p className="text-xs text-ink-mute mt-1">Optional default dataset to query</p>
                  </div>
                </div>
              ) : isSnowflake ? (
                /* Snowflake-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Account Identifier <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="xyz12345.us-east-1"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Found in your Snowflake URL: <code>account.region.snowflakecomputing.com</code>
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Username <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="MYUSER"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Password <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="••••••••"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Database
                    </label>
                    <input
                      type="text"
                      value={formData.database}
                      onChange={(e) => handleInputChange('database', e.target.value)}
                      placeholder="MY_DATABASE"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Warehouse
                    </label>
                    <input
                      type="text"
                      value={formData.connection_params?.warehouse || ''}
                      onChange={(e) => handleConnectionParamChange('warehouse', e.target.value)}
                      placeholder="COMPUTE_WH"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Schema
                    </label>
                    <input
                      type="text"
                      value={formData.connection_params?.schema || ''}
                      onChange={(e) => handleConnectionParamChange('schema', e.target.value)}
                      placeholder="PUBLIC"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Role (Optional)
                    </label>
                    <input
                      type="text"
                      value={formData.connection_params?.role || ''}
                      onChange={(e) => handleConnectionParamChange('role', e.target.value)}
                      placeholder="SYSADMIN"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                  </div>
                </div>
              ) : formData.type === 'ELASTICSEARCH' ? (
                /* Elasticsearch-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Host <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="localhost or elasticsearch.example.com"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Port <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="number"
                      value={formData.port}
                      onChange={(e) => handleInputChange('port', parseInt(e.target.value))}
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Index Name (Optional)
                    </label>
                    <input
                      type="text"
                      value={formData.database}
                      onChange={(e) => handleInputChange('database', e.target.value)}
                      placeholder="my-index (leave blank to access all indices)"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Optional: Specify a default index name. Leave blank to access all indices.
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Username (Optional)
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="elastic"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Only required if Elasticsearch security is enabled
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Password (Optional)
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="••••••••"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Only required if Elasticsearch security is enabled. Password will be encrypted and stored securely.
                    </p>
                  </div>
                </div>
              ) : isSupabase ? (
                /* Supabase — API key auth via PostgREST */
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Project URL <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="https://abcdefghij.supabase.co"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Found in Supabase Dashboard → Settings → API → Project URL
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Anon / Publishable Key <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Supabase Dashboard → Settings → API → Project API Keys → <code>anon</code> public key
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Service Role / Secret Key <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Supabase Dashboard → Settings → API → Project API Keys → <code>service_role</code> secret key. Stored encrypted.
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      id="use_service_role"
                      checked={formData.connection_params?.use_service_role !== false}
                      onChange={(e) => handleConnectionParamChange('use_service_role', e.target.checked ? 'true' : 'false')}
                      className="h-4 w-4 rounded border-taupe text-leaf focus:ring-ink"
                    />
                    <label htmlFor="use_service_role" className="text-sm text-ink-soft">
                      Use service role key (bypasses Row Level Security, recommended for agents)
                    </label>
                  </div>

                  <div className="rounded-[1.2rem] border border-leaf-wash bg-leaf-wash p-4">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-leaf" />
                      <div className="text-xs text-forest">
                        <p className="font-medium mb-1">No database password needed</p>
                        <p>This connection uses Supabase's REST API (PostgREST) instead of a direct PostgreSQL connection. Only API keys are required, no host port, no database password.</p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                /* Standard database fields (PostgreSQL, MySQL, MongoDB) */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Host <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="localhost or db.example.com"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Port <span className="text-leaf">*</span>
                    </label>
                    <input
                      type="number"
                      value={formData.port}
                      onChange={(e) => handleInputChange('port', parseInt(e.target.value))}
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Database Name
                    </label>
                    <input
                      type="text"
                      value={formData.database}
                      onChange={(e) => handleInputChange('database', e.target.value)}
                      placeholder="mydb"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Username
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="dbuser"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-ink-soft mb-1.5">
                      Password
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="••••••••"
                      className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    />
                    <p className="text-xs text-ink-mute mt-1">
                      Password will be encrypted and stored securely
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Test Connection Result */}
            {testResult && (
              <div className={`rounded-[1.4rem] border p-4 ${
                testResult.success 
                  ? 'border-leaf-wash bg-cream'
                  : 'border-paper-dim bg-paper'
              }`}>
                <div className="flex items-center gap-3">
                  {testResult.success ? (
                    <CheckCircle className="h-5 w-5 text-leaf" />
                  ) : (
                    <AlertCircle className="h-5 w-5 text-danger" />
                  )}
                  <div>
                    <p className={`font-medium ${
                      testResult.success ? 'text-ink' : 'text-danger'
                    }`}>
                      {testResult.success ? 'Connection Successful' : 'Connection Failed'}
                    </p>
                    <p className={`text-sm ${
                      testResult.success ? 'text-ink-soft' : 'text-leaf'
                    }`}>
                      {testResult.message}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-col gap-4 border-t border-line pt-6 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                onClick={testConnection}
                disabled={testing || (isPathBased && !formData.database_path) || (isBigQuery && (!formData.database || !formData.password)) || (isSnowflake && (!formData.host || !formData.username)) || (isSupabase && (!formData.host || !formData.username || !formData.password)) || (!isPathBased && !isCloudOnly && (!formData.host || !formData.port))}
                className="inline-flex items-center justify-center gap-2 rounded-full border border-tan bg-white/80 px-5 py-3 text-sm font-semibold text-ink-soft transition-colors hover:border-tan hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
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

              <div className="flex flex-col-reverse gap-3 sm:flex-row">
                <Link
                  href="/database-connections"
                  className="inline-flex items-center justify-center rounded-full border border-line bg-white px-5 py-3 text-sm font-semibold text-ink-soft transition-colors hover:border-tan hover:text-ink"
                >
                  Cancel
                </Link>
                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving ? (
                    <>
                      <Loader2 className="h-4 w-4 motion-safe:animate-spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4" />
                      Create Connection
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
