'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { AlertTriangle, BookOpen, Plus } from 'lucide-react'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import EmptyState from '@/components/common/EmptyState'
import { apiClient } from '@/lib/api/client'
import AgentPageShell from '@/components/agents/AgentPageShell'

interface Agent {
  id: number
  name: string
  type: string
}

interface KnowledgeBase {
  id: number
  name: string
  description: string
  vector_db_provider: string
  total_documents: number
  total_chunks: number
}

interface AgentKnowledgeBase {
  id: number
  name: string
  description: string
  vector_db_provider: string
  total_documents: number
  total_chunks: number
  is_active?: boolean
  retrieval_config: {
    top_k: number
    score_threshold: number
    include_metadata: boolean
  }
  created_at: string
}

export default function AgentKnowledgeBasesPage() {
  const params = useParams()
  const agentName = params.agentName as string

  const [agent, setAgent] = useState<Agent | null>(null)
  const [attachedKBs, setAttachedKBs] = useState<AgentKnowledgeBase[]>([])
  const [availableKBs, setAvailableKBs] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAttachModal, setShowAttachModal] = useState(false)
  const [selectedKbId, setSelectedKbId] = useState<number | null>(null)
  const [detachingKb, setDetachingKb] = useState<AgentKnowledgeBase | null>(null)
  const [isDetaching, setIsDetaching] = useState(false)
  const [attachConfig, setAttachConfig] = useState({
    top_k: 5,
    score_threshold: 0.7,
    include_metadata: true,
  })

  useEffect(() => {
    fetchAgent()
    fetchAvailableKBs()
  }, [agentName])

  useEffect(() => {
    if (agent) {
      fetchAttachedKBs()
    }
  }, [agent])

  const fetchAgent = async () => {
    try {
      const data = await apiClient.getAgent(agentName)
      setAgent({
        id: data.id,
        name: data.agent_name,
        type: data.agent_type
      })
    } catch (err) {
      console.error('Failed to fetch agent:', err)
    }
  }

  const fetchAttachedKBs = async () => {
    if (!agent) return
    
    try {
      setLoading(true)
      const kbs = await apiClient.getAgentKnowledgeBases(agent.id.toString())
      setAttachedKBs(kbs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const fetchAvailableKBs = async () => {
    try {
      const data: any = await apiClient.getKnowledgeBases()
      // Handle both response formats
      const kbs = data?.data?.knowledge_bases || data?.data || data || []
      setAvailableKBs(kbs)
    } catch (err) {
      console.error('Failed to fetch knowledge bases:', err)
    }
  }

  const handleAttach = async () => {
    if (!agent || !selectedKbId) return

    try {
      await apiClient.addKnowledgeBaseToAgent(agent.id.toString(), {
        knowledge_base_id: selectedKbId,
        retrieval_config: attachConfig,
      })

      setShowAttachModal(false)
      setSelectedKbId(null)
      fetchAttachedKBs()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to attach knowledge base')
    }
  }

  const handleDetach = (kb: AgentKnowledgeBase) => {
    setDetachingKb(kb)
  }

  const confirmDetach = async () => {
    if (!agent || !detachingKb) return
    setIsDetaching(true)
    try {
      await apiClient.removeKnowledgeBaseFromAgent(agent.id.toString(), detachingKb.id.toString())
      setDetachingKb(null)
      fetchAttachedKBs()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to detach knowledge base')
    } finally {
      setIsDetaching(false)
    }
  }

  const getProviderBadgeColor = (provider?: string) => {
    const colors: Record<string, string> = {
      QDRANT: 'bg-blue-100 text-blue-800',
      PINECONE: 'bg-purple-100 text-purple-800',
      WEAVIATE: 'bg-green-100 text-green-800',
      CHROMA: 'bg-orange-100 text-orange-800',
      MILVUS: 'bg-primary-100 text-primary-800',
    }
    return colors[(provider || '').toUpperCase()] || 'bg-gray-100 text-gray-800'
  }

  const getUnattachedKBs = () => {
    const attachedIds = attachedKBs.map(akb => akb.knowledge_base_id)
    return availableKBs.filter(kb => !attachedIds.includes(kb.id))
  }

  const modalInputClass =
    'w-full rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]'
  const selectedKb = selectedKbId ? getUnattachedKBs().find((kb) => kb.id === selectedKbId) : null

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Knowledge Bases"
      description={<>Configure which knowledge bases <span className="font-semibold text-gray-900">{agent?.name || agentName}</span> can access.</>}
      icon={BookOpen}
      backHref={`/agents/${agentName}/view`}
      backLabel="Back to Agent"
      badge="Knowledge Access"
      actions={
        <button
          onClick={() => setShowAttachModal(true)}
          disabled={getUnattachedKBs().length === 0}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="w-4 h-4" />
          Attach Knowledge Base
        </button>
      }
    >

      {error && (
        <div className="mb-6">
          <ErrorAlert message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {/* Attached Knowledge Bases */}
      {attachedKBs.length === 0 ? (
        <EmptyState
          icon={
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
          }
          title="No knowledge bases attached"
          description="Attach a knowledge base to enable RAG capabilities for this agent."
          actionLabel={getUnattachedKBs().length > 0 ? "Attach Knowledge Base" : undefined}
          onAction={getUnattachedKBs().length > 0 ? () => setShowAttachModal(true) : undefined}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {attachedKBs.map((akb) => (
            <div
              key={akb.id}
              className="bg-white rounded-lg border border-gray-200 p-5 hover:border-red-300 hover:shadow-md transition-all"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <Link
                  href={`/knowledge-bases/${akb.id}`}
                  className="flex-1"
                >
                  <h3 className="text-base font-semibold text-gray-900 hover:text-primary-600 transition-colors">
                    {akb.name || 'Unknown KB'}
                  </h3>
                  <p className="text-xs text-gray-600 mt-1 line-clamp-2">
                    {akb.description || ''}
                  </p>
                </Link>
              </div>

              {/* Provider Badge */}
              <div className="mb-4">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getProviderBadgeColor(akb.vector_db_provider)}`}>
                  {akb.vector_db_provider || 'unknown'}
                </span>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3 mb-4 py-3 border-t border-b border-gray-100">
                <div>
                  <p className="text-xs text-gray-500">Documents</p>
                  <p className="text-base font-semibold text-gray-900">
                    {akb.total_documents ?? 0}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Chunks</p>
                  <p className="text-base font-semibold text-gray-900">
                    {akb.total_chunks ?? 0}
                  </p>
                </div>
              </div>

              {/* Retrieval Config */}
              <div className="mb-4">
                <p className="text-xs text-gray-500 mb-2 font-medium">Retrieval Settings</p>
                <div className="space-y-1 bg-gray-50 rounded-md p-2.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-600">Top K:</span>
                    <span className="text-gray-900 font-medium">{akb.retrieval_config?.top_k ?? '—'}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-600">Score Threshold:</span>
                    <span className="text-gray-900 font-medium">{akb.retrieval_config?.score_threshold ?? '—'}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-600">Include Metadata:</span>
                    <span className="text-gray-900 font-medium">
                      {akb.retrieval_config?.include_metadata ? 'Yes' : 'No'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <button
                onClick={() => handleDetach(akb)}
                className="w-full px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors"
              >
                Detach
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Detach Confirm Modal */}
      {detachingKb && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.18)]">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-[1rem] bg-red-50">
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Detach Knowledge Base</h3>
            </div>
            <p className="text-gray-600 mb-6">
              Are you sure you want to detach{' '}
              <span className="font-medium text-gray-900">{detachingKb.name}</span>
              {' '}from this agent? The knowledge base itself will not be deleted.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDetachingKb(null)}
                disabled={isDetaching}
                className="rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDetach}
                disabled={isDetaching}
                className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
              >
                {isDetaching && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                Detach
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Attach Modal */}
      {showAttachModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(17,17,17,0.48)] p-4 backdrop-blur-[6px]">
          <div className="w-full max-w-3xl overflow-hidden rounded-[1.9rem] border border-black/10 bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.96),_rgba(247,240,231,0.96)_55%,_rgba(239,232,223,0.96)_100%)] shadow-[0_36px_110px_rgba(0,0,0,0.24)]">
            <div className="flex items-start justify-between border-b border-black/10 bg-white/55 px-8 py-6">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#7c5d45]">Knowledge Access</p>
                <h2 className="mt-2 text-[2rem] font-semibold tracking-[-0.04em] text-gray-950">Attach Knowledge Base</h2>
                <p className="mt-2 text-sm leading-6 text-gray-600">
                  Choose an existing knowledge base and tune how this agent should retrieve content from it.
                </p>
              </div>
              <button
                onClick={() => {
                  setShowAttachModal(false)
                  setSelectedKbId(null)
                }}
                className="rounded-full p-2 text-gray-400 transition-colors hover:bg-white hover:text-gray-700"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="max-h-[calc(90vh-13rem)] overflow-y-auto px-8 py-6">
              {/* Select Knowledge Base */}
              <div className="mb-6">
                <div className="mb-3 flex items-end justify-between gap-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">
                      Select Knowledge Base
                    </label>
                    <p className="mt-1 text-sm text-gray-600">Pick one unattached knowledge base for this agent.</p>
                  </div>
                  <span className="rounded-full border border-black/10 bg-white/75 px-3 py-1 text-xs font-semibold text-gray-600">
                    {getUnattachedKBs().length} available
                  </span>
                </div>

                <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                  {getUnattachedKBs().map((kb) => (
                    <button
                      key={kb.id}
                      onClick={() => setSelectedKbId(kb.id)}
                      className={`w-full rounded-[1.35rem] border p-4 text-left transition-all ${
                        selectedKbId === kb.id
                          ? 'border-[#171717] bg-white shadow-[0_20px_48px_rgba(0,0,0,0.08)]'
                          : 'border-black/10 bg-[#fcfaf5] hover:border-black/20 hover:bg-white'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <h3 className="truncate text-[1.05rem] font-semibold tracking-[-0.02em] text-gray-950">{kb.name}</h3>
                            {selectedKbId === kb.id && (
                              <span className="rounded-full bg-[#171717] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-white">
                                Selected
                              </span>
                            )}
                          </div>
                          <p className="mt-1 text-sm leading-6 text-gray-600">
                            {kb.description || 'No description available.'}
                          </p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${getProviderBadgeColor(kb.vector_db_provider)}`}>
                              {kb.vector_db_provider}
                            </span>
                            <span className="inline-flex items-center rounded-full bg-[#edf4f6] px-2.5 py-1 text-xs font-semibold text-[#486c77]">
                              {kb.total_documents} docs
                            </span>
                            <span className="inline-flex items-center rounded-full bg-[#f1eadc] px-2.5 py-1 text-xs font-semibold text-[#7c5d45]">
                              {kb.total_chunks} chunks
                            </span>
                          </div>
                        </div>
                        <div className={`mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border ${
                          selectedKbId === kb.id
                            ? 'border-[#171717] bg-[#171717] text-white'
                            : 'border-black/15 bg-white text-transparent'
                        }`}>
                          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Retrieval Configuration */}
              {selectedKbId && (
                <div className="rounded-[1.6rem] border border-black/10 bg-white/78 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.04)]">
                  <div className="mb-4 flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-semibold tracking-[-0.02em] text-gray-950">Retrieval Configuration</h3>
                      <p className="mt-1 text-sm leading-6 text-gray-600">
                        {selectedKb ? <>Tune how <span className="font-semibold text-gray-900">{selectedKb.name}</span> should be queried for this agent.</> : 'Tune retrieval behavior for the selected knowledge base.'}
                      </p>
                    </div>
                    <div className="rounded-[1.1rem] bg-[#f1eadc] px-3 py-2 text-right">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">Current preset</p>
                      <p className="mt-1 text-sm font-semibold text-gray-900">
                        Top {attachConfig.top_k} · {attachConfig.score_threshold}
                      </p>
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">
                        Top K Results
                      </label>
                      <input
                        type="number"
                        value={attachConfig.top_k}
                        onChange={(e) => setAttachConfig({ ...attachConfig, top_k: parseInt(e.target.value) })}
                        className={modalInputClass}
                        min="1"
                        max="20"
                      />
                      <p className="mt-1.5 text-xs text-gray-500">
                        Number of relevant chunks to retrieve, from 1 to 20.
                      </p>
                    </div>

                    <div>
                      <label className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">
                        Score Threshold
                      </label>
                      <input
                        type="number"
                        value={attachConfig.score_threshold}
                        onChange={(e) => setAttachConfig({ ...attachConfig, score_threshold: parseFloat(e.target.value) })}
                        className={modalInputClass}
                        min="0"
                        max="1"
                        step="0.1"
                      />
                      <p className="mt-1.5 text-xs text-gray-500">
                        Minimum similarity score between 0.0 and 1.0.
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 rounded-[1.2rem] border border-black/10 bg-[#fcfaf5] px-4 py-3">
                    <label className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={attachConfig.include_metadata}
                        onChange={(e) => setAttachConfig({ ...attachConfig, include_metadata: e.target.checked })}
                        className="h-4 w-4 rounded border-gray-300 text-[#171717] focus:ring-[#79dfbc]"
                      />
                      <div>
                        <span className="block text-sm font-semibold text-gray-900">Include metadata in results</span>
                        <span className="text-xs text-gray-500">Return additional source context alongside retrieved content.</span>
                      </div>
                    </label>
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between gap-3 border-t border-black/10 bg-white/60 px-8 py-5">
              <p className="text-xs text-gray-500">
                {selectedKb ? `Ready to attach ${selectedKb.name}.` : 'Select a knowledge base to continue.'}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    setShowAttachModal(false)
                    setSelectedKbId(null)
                  }}
                  className="rounded-[1rem] border border-black/10 bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 transition-colors hover:bg-[#fcfaf5]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAttach}
                  disabled={!selectedKbId}
                  className="rounded-[1rem] bg-[#171717] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:bg-gray-400"
                >
                  Attach Knowledge Base
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AgentPageShell>
  )
}
