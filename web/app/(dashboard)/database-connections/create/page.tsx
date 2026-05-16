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
                  New Connection
                </div>

                <div className="flex items-start gap-4">
                  <div className="rounded-[1.2rem] bg-[#f3ecde] p-3.5 shadow-[0_16px_30px_-24px_rgba(74,49,22,0.3)]">
                    <Database className="h-6 w-6 text-[#171717]" />
                  </div>
                  <div>
                    <h1 className="text-3xl font-semibold tracking-[-0.04em] text-gray-950 md:text-[2.6rem]">
                      Create Database Connection
                    </h1>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
                      Add a new database connection for data analysis.
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
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Access</p>
                  <p className="mt-2 text-lg font-semibold text-gray-900">{formData.is_global ? 'Global' : 'Private'}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-[2rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] p-6 shadow-[0_28px_70px_-48px_rgba(73,45,23,0.32)] md:p-8 [&_input[type='text']]:!w-full [&_input[type='text']]:!rounded-[1.15rem] [&_input[type='text']]:!border [&_input[type='text']]:!border-gray-200 [&_input[type='text']]:!bg-gray-50 [&_input[type='text']]:!px-4 [&_input[type='text']]:!py-4 [&_input[type='text']]:!text-sm [&_input[type='text']]:!text-gray-900 [&_input[type='text']]:!placeholder-gray-400 [&_input[type='text']]:!transition-all [&_input[type='text']]:focus:!border-transparent [&_input[type='text']]:focus:!outline-none [&_input[type='text']]:focus:!ring-2 [&_input[type='text']]:focus:!ring-red-500 [&_input[type='text']]:focus-visible:!border-transparent [&_input[type='text']]:focus-visible:!outline-none [&_input[type='text']]:focus-visible:!ring-2 [&_input[type='text']]:focus-visible:!ring-red-500 [&_input[type='password']]:!w-full [&_input[type='password']]:!rounded-[1.15rem] [&_input[type='password']]:!border [&_input[type='password']]:!border-gray-200 [&_input[type='password']]:!bg-gray-50 [&_input[type='password']]:!px-4 [&_input[type='password']]:!py-4 [&_input[type='password']]:!text-sm [&_input[type='password']]:!text-gray-900 [&_input[type='password']]:!placeholder-gray-400 [&_input[type='password']]:!transition-all [&_input[type='password']]:focus:!border-transparent [&_input[type='password']]:focus:!outline-none [&_input[type='password']]:focus:!ring-2 [&_input[type='password']]:focus:!ring-red-500 [&_input[type='password']]:focus-visible:!border-transparent [&_input[type='password']]:focus-visible:!outline-none [&_input[type='password']]:focus-visible:!ring-2 [&_input[type='password']]:focus-visible:!ring-red-500 [&_input[type='number']]:!w-full [&_input[type='number']]:!rounded-[1.15rem] [&_input[type='number']]:!border [&_input[type='number']]:!border-gray-200 [&_input[type='number']]:!bg-gray-50 [&_input[type='number']]:!px-4 [&_input[type='number']]:!py-4 [&_input[type='number']]:!text-sm [&_input[type='number']]:!text-gray-900 [&_input[type='number']]:!transition-all [&_input[type='number']]:focus:!border-transparent [&_input[type='number']]:focus:!outline-none [&_input[type='number']]:focus:!ring-2 [&_input[type='number']]:focus:!ring-red-500 [&_input[type='number']]:focus-visible:!border-transparent [&_input[type='number']]:focus-visible:!outline-none [&_input[type='number']]:focus-visible:!ring-2 [&_input[type='number']]:focus-visible:!ring-red-500 [&_select]:!w-full [&_select]:!rounded-[1.15rem] [&_select]:!border [&_select]:!border-gray-200 [&_select]:!bg-gray-50 [&_select]:!px-4 [&_select]:!py-4 [&_select]:!text-sm [&_select]:!text-gray-900 [&_select]:!transition-all [&_select]:focus:!border-transparent [&_select]:focus:!outline-none [&_select]:focus:!ring-2 [&_select]:focus:!ring-red-500 [&_select]:focus-visible:!border-transparent [&_select]:focus-visible:!outline-none [&_select]:focus-visible:!ring-2 [&_select]:focus-visible:!ring-red-500 [&_textarea]:!w-full [&_textarea]:!rounded-[1.15rem] [&_textarea]:!border [&_textarea]:!border-gray-200 [&_textarea]:!bg-gray-50 [&_textarea]:!px-4 [&_textarea]:!py-4 [&_textarea]:!text-sm [&_textarea]:!text-gray-900 [&_textarea]:!placeholder-gray-400 [&_textarea]:!transition-all [&_textarea]:focus:!border-transparent [&_textarea]:focus:!outline-none [&_textarea]:focus:!ring-2 [&_textarea]:focus:!ring-red-500 [&_textarea]:focus-visible:!border-transparent [&_textarea]:focus-visible:!outline-none [&_textarea]:focus-visible:!ring-2 [&_textarea]:focus-visible:!ring-red-500 [&_label]:!mb-1.5 [&_label]:!block [&_label]:!text-sm [&_label]:!font-semibold [&_label]:!text-gray-700"
        >
          <div className="space-y-5">
            {/* Basic Information */}
            <div>
              <div className="mb-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Section 1</p>
                <h2 className="mt-2 text-lg font-semibold text-gray-950">Basic Information</h2>
                <p className="mt-1 text-sm text-gray-500">Define the connection name, type, and visibility.</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                  <label className="flex min-h-[60px] w-full cursor-pointer items-center gap-4 rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-5 py-4 transition-all hover:border-[#dcc7ac]">
                    <input
                      type="checkbox"
                      checked={formData.is_global}
                      onChange={(e) => handleInputChange('is_global', e.target.checked)}
                      className="h-5 w-5 shrink-0 rounded border-gray-300 text-red-500 focus:ring-red-500"
                    />
                    <span className="block pl-0.5 text-base font-semibold leading-none text-gray-700">
                      Global Connection (Available to all agents)
                    </span>
                  </label>
                </div>
              </div>
            </div>

            {/* Connection Details */}
            <div>
              <div className="mb-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Section 2</p>
                <h2 className="mt-2 text-lg font-semibold text-gray-950">Connection Details</h2>
                <p className="mt-1 text-sm text-gray-500">Provide the host, credentials, and provider-specific settings.</p>
              </div>
              
              {formData.type === 'DATADOG' ? (
                /* Datadog-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      API Key <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="••••••••••••••••••••••••••••••••"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Get from Datadog → Integrations → APIs → API Keys
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Application Key <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="••••••••••••••••••••••••••••••••"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Generate in Datadog → Organization Settings → Application Keys
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Site <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    >
                      <option value="">Select Datadog Site...</option>
                      <option value="datadoghq.com">US1 (datadoghq.com)</option>
                      <option value="us3.datadoghq.com">US3 (us3.datadoghq.com)</option>
                      <option value="us5.datadoghq.com">US5 (us5.datadoghq.com)</option>
                      <option value="datadoghq.eu">EU (datadoghq.eu)</option>
                      <option value="ap1.datadoghq.com">AP1 (ap1.datadoghq.com)</option>
                      <option value="ddog-gov.com">US1-FED (ddog-gov.com)</option>
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      Select your Datadog site region
                    </p>
                  </div>
                </div>
              ) : formData.type === 'DATABRICKS' ? (
                /* Databricks-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Server Hostname <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="your-workspace.cloud.databricks.com"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Found in your Databricks workspace URL
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      HTTP Path <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.database_path}
                      onChange={(e) => handleInputChange('database_path', e.target.value)}
                      placeholder="/sql/1.0/warehouses/xxxxxxxxxxxxx"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      SQL Warehouse → Connection Details → HTTP Path
                    </p>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Access Token <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="••••••••••••••••••••••••••••••••"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      User Settings → Access Tokens → Generate New Token
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Catalog
                    </label>
                    <input
                      type="text"
                      value={formData.database}
                      onChange={(e) => handleInputChange('database', e.target.value)}
                      placeholder="main"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Default catalog name (e.g., 'main')
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Schema
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="default"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Default schema name (e.g., 'default')
                    </p>
                  </div>
                </div>
              ) : formData.type === 'DOCKER' ? (
                /* Docker-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Docker Host <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.host}
                      onChange={(e) => handleInputChange('host', e.target.value)}
                      placeholder="unix://var/run/docker.sock or tcp://host:2375"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Local: unix://var/run/docker.sock | Remote: tcp://hostname:2375
                    </p>
                  </div>

                  <div className="md:col-span-2 rounded-[1.2rem] border border-[#d8e5d9] bg-[#eef7f1] p-4">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#2d8b69]" />
                      <div className="text-xs text-[#2d6f58]">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <p className="text-xs text-gray-500 mt-1">Your Google Cloud project ID</p>
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Service Account JSON <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder={'{\n  "type": "service_account",\n  "project_id": "my-project",\n  ...\n}'}
                      rows={6}
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500 font-mono"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Paste the full contents of your service account key JSON file. Stored encrypted.
                    </p>
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Default Dataset (Optional)
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="my_dataset"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">Optional default dataset to query</p>
                  </div>
                </div>
              ) : isSnowflake ? (
                /* Snowflake-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <p className="text-xs text-gray-500 mt-1">
                      Found in your Snowflake URL: <code>account.region.snowflakecomputing.com</code>
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Username <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="MYUSER"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Password <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="••••••••"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Database
                    </label>
                    <input
                      type="text"
                      value={formData.database}
                      onChange={(e) => handleInputChange('database', e.target.value)}
                      placeholder="MY_DATABASE"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Warehouse
                    </label>
                    <input
                      type="text"
                      value={formData.connection_params?.warehouse || ''}
                      onChange={(e) => handleConnectionParamChange('warehouse', e.target.value)}
                      placeholder="COMPUTE_WH"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Schema
                    </label>
                    <input
                      type="text"
                      value={formData.connection_params?.schema || ''}
                      onChange={(e) => handleConnectionParamChange('schema', e.target.value)}
                      placeholder="PUBLIC"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Role (Optional)
                    </label>
                    <input
                      type="text"
                      value={formData.connection_params?.role || ''}
                      onChange={(e) => handleConnectionParamChange('role', e.target.value)}
                      placeholder="SYSADMIN"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                  </div>
                </div>
              ) : formData.type === 'ELASTICSEARCH' ? (
                /* Elasticsearch-specific fields */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Password (Optional)
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="••••••••"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Only required if Elasticsearch security is enabled. Password will be encrypted and stored securely.
                    </p>
                  </div>
                </div>
              ) : isSupabase ? (
                /* Supabase — API key auth via PostgREST */
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Anon / Publishable Key <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Supabase Dashboard → Settings → API → Project API Keys → <code>anon</code> public key
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Service Role / Secret Key <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                      required
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
                      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#2d8b69]" />
                      <div className="text-xs text-[#2d6f58]">
                        <p className="font-medium mb-1">No database password needed</p>
                        <p>This connection uses Supabase's REST API (PostgREST) instead of a direct PostgreSQL connection. Only API keys are required — no host port, no database password.</p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                /* Standard database fields (PostgreSQL, MySQL, MongoDB) */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Password
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="••••••••"
                      className="w-full rounded-[1.15rem] border border-[#e2d6c6] bg-gray-50 px-4 py-4 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
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
                disabled={testing || (isPathBased && !formData.database_path) || (isBigQuery && (!formData.database || !formData.password)) || (isSnowflake && (!formData.host || !formData.username)) || (isSupabase && (!formData.host || !formData.username || !formData.password)) || (!isPathBased && !isCloudOnly && (!formData.host || !formData.port))}
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
                  href="/database-connections"
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
