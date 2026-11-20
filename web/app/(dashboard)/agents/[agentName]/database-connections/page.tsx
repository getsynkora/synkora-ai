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
      description={<>Select which databases <span className="font-semibold text-ink">{agentName}</span> can access.</>}
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
          className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-4 h-4 motion-safe:animate-spin" /> : <Save className="w-4 h-4" />}
          Save
        </button>
      }
    >
      <AgentPagePanel className="overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-8 h-8 text-leaf motion-safe:animate-spin" />
            </div>
          ) : connections.length === 0 ? (
            <div className="text-center py-16 px-6">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-sand rounded-full mb-4">
                <Database className="w-8 h-8 text-ash" />
              </div>
              <h3 className="text-lg font-semibold text-ink mb-2">No Database Connections</h3>
              <p className="text-ink-mute text-sm mb-4">
                Create database connections first to attach them to this agent.
              </p>
              <button
                onClick={() => router.push('/database-connections')}
                className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-sand-deep px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-line"
              >
                Go to Database Connections
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between border-b border-black/10 bg-cream px-5 py-3.5">
                <span className="text-sm text-ink-soft">
                  {attachedCount} of {connections.length} attached
                </span>
                <span className="text-xs text-ash">
                  Only attached connections are accessible to the agent
                </span>
              </div>
              <div className="divide-y divide-black/5">
                {connections.map(conn => (
                  <div key={conn.id} className="flex items-center justify-between px-5 py-4 transition-colors hover:bg-cream">
                    <div className="flex items-center gap-3">
                      <div className="rounded-[0.95rem] bg-sand p-2.5">
                        <Database className="w-4 h-4 text-ink" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-ink">{conn.name}</p>
                        <p className="text-xs text-ink-mute">
                          {conn.type}
                          {conn.host ? `, ${conn.host}:${conn.port}/${conn.database}` : ''}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => toggle(conn.id)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        conn.attached ? 'bg-ink' : 'bg-line'
                      }`}
                    >
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform motion-reduce:transition-none ${
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
