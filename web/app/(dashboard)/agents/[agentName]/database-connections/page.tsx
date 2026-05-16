'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { ArrowLeft, Database, Save, Loader2 } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

interface DbConnection {
  id: string
  name: string
  type: string
  host: string | null
  port: number | null
  database: string | null
  attached: boolean
}

export default function AgentDatabaseConnectionsPage() {
  const params = useParams()
  const router = useRouter()
  const agentName = decodeURIComponent(params?.agentName as string || '')

  const [connections, setConnections] = useState<DbConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadConnections()
  }, [agentName])

  const loadConnections = async () => {
    try {
      setLoading(true)
      const data = await apiClient.request('GET', `/api/v1/agents/${agentName}/database-connections`)
      setConnections(Array.isArray(data) ? data : [])
    } catch (error) {
      toast.error('Failed to load database connections')
    } finally {
      setLoading(false)
    }
  }

  const toggle = (id: string) => {
    setConnections(prev => prev.map(c => c.id === id ? { ...c, attached: !c.attached } : c))
  }

  const save = async () => {
    setSaving(true)
    try {
      const attached = connections.filter(c => c.attached).map(c => c.id)
      await apiClient.request('PUT', `/api/v1/agents/${agentName}/database-connections`, { connection_ids: attached })
      toast.success('Database connections saved')
    } catch (error) {
      toast.error('Failed to save database connections')
    } finally {
      setSaving(false)
    }
  }

  const attachedCount = connections.filter(c => c.attached).length

  return (
    <AgentPageShell
      agentName={agentName}
      title="Database Connections"
      description={<>Select which databases <span className="font-semibold text-gray-900">{agentName}</span> can access.</>}
      icon={Database}
      backHref={`/agents/${encodeURIComponent(agentName)}/view`}
      backLabel="Back to Agent"
      badge="Data Access"
      maxWidthClassName="max-w-[90rem]"
      stats={[
        { label: 'Attached', value: attachedCount },
        { label: 'Available', value: connections.length },
      ]}
      actions={
        <button
          onClick={save}
          disabled={saving || loading}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save
        </button>
      }
    >
      <AgentPagePanel className="overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-8 h-8 text-red-500 animate-spin" />
            </div>
          ) : connections.length === 0 ? (
            <div className="text-center py-16 px-6">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
                <Database className="w-8 h-8 text-gray-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No Database Connections</h3>
              <p className="text-gray-500 text-sm mb-4">
                Create database connections first to attach them to this agent.
              </p>
              <button
                onClick={() => router.push('/database-connections')}
                className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8]"
              >
                Go to Database Connections
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between border-b border-black/10 bg-[#fcfaf5] px-5 py-3.5">
                <span className="text-sm text-gray-600">
                  {attachedCount} of {connections.length} attached
                </span>
                <span className="text-xs text-gray-400">
                  Only attached connections are accessible to the agent
                </span>
              </div>
              <div className="divide-y divide-black/5">
                {connections.map(conn => (
                  <div key={conn.id} className="flex items-center justify-between px-5 py-4 transition-colors hover:bg-[#fcfaf5]">
                    <div className="flex items-center gap-3">
                      <div className="rounded-[0.95rem] bg-[#f3ecde] p-2.5">
                        <Database className="w-4 h-4 text-[#171717]" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">{conn.name}</p>
                        <p className="text-xs text-gray-500">
                          {conn.type}
                          {conn.host ? ` · ${conn.host}:${conn.port}/${conn.database}` : ''}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => toggle(conn.id)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        conn.attached ? 'bg-[#171717]' : 'bg-gray-200'
                      }`}
                    >
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                        conn.attached ? 'translate-x-6' : 'translate-x-1'
                      }`} />
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}
      </AgentPagePanel>
    </AgentPageShell>
  )
}
