'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Plus, X, Users, Zap, Globe, ExternalLink, Info, GitPullRequest, FileCode, ChevronDown, ChevronUp, AlertTriangle, Loader2, Link, Swords } from 'lucide-react'
import toast from 'react-hot-toast'
import { createDebate, updateDebate, getDebate, getDebateTemplates, fetchPRInfo } from '@/lib/api/war-room'
import { apiClient } from '@/lib/api/client'
import type { DebateTemplate, DebateContext, PRInfo } from '@/lib/api/war-room'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

interface AgentOption {
  id: string
  agent_name: string
}

interface ParticipantRow {
  agent_id: string
  role: string
}

const warmFieldClass =
  'w-full rounded-[1.1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint'
const warmCardClass = (active: boolean) =>
  `rounded-[1.25rem] border p-4 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
    active
      ? 'border-tan bg-cream shadow-soft'
      : 'border-black/10 bg-white/80 hover:border-line hover:bg-cream'
  }`

export default function CreateDebatePage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const editId = searchParams.get('edit')
  const isEditMode = !!editId

  const [templates, setTemplates] = useState<DebateTemplate[]>([])
  const [agents, setAgents] = useState<AgentOption[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingData, setLoadingData] = useState(!!editId)

  const [topic, setTopic] = useState('')
  const [debateType, setDebateType] = useState<'structured' | 'freeform'>('structured')
  const [rounds, setRounds] = useState(3)
  const [participants, setParticipants] = useState<ParticipantRow[]>([
    { agent_id: '', role: '' },
    { agent_id: '', role: '' },
  ])
  const [synthesizerAgentId, setSynthesizerAgentId] = useState('')
  const [isPublic, setIsPublic] = useState(false)
  const [allowExternal, setAllowExternal] = useState(false)
  const [contextType, setContextType] = useState<'none' | 'github_pr' | 'text'>('none')
  const [prUrl, setPrUrl] = useState('')
  const [prInfo, setPrInfo] = useState<PRInfo | null>(null)
  const [prLoading, setPrLoading] = useState(false)
  const [prError, setPrError] = useState<string | null>(null)
  const [textContext, setTextContext] = useState('')
  const [showDiff, setShowDiff] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const [tmpl, agentData] = await Promise.all([
          getDebateTemplates(),
          apiClient.getAgents(1, 100),
        ])
        setTemplates(tmpl.templates || [])
        setAgents((agentData.agents_list || agentData.agents || []).map((a: any) => ({
          id: a.id,
          agent_name: a.agent_name,
        })))

        // Load existing debate data for edit mode
        if (editId) {
          try {
            const debate = await getDebate(editId)
            setTopic(debate.topic)
            setDebateType(debate.debate_type as 'structured' | 'freeform')
            setRounds(debate.rounds)
            setIsPublic(debate.is_public)
            setAllowExternal(debate.allow_external)
            if (debate.participants.length > 0) {
              setParticipants(
                debate.participants
                  .filter((p) => !p.is_external)
                  .map((p) => ({
                    agent_id: p.agent_id || '',
                    role: p.role || '',
                  }))
              )
            }
            // Restore context if present
            const ctx = debate.debate_metadata?.context
            if (ctx?.type === 'github_pr') {
              setContextType('github_pr')
              setPrUrl(ctx.github_url || '')
              setPrInfo({
                repo_full_name: ctx.repo_full_name || '',
                pr_number: ctx.pr_number || 0,
                pr_title: ctx.pr_title || '',
                pr_description: ctx.pr_description || '',
                pr_author: ctx.pr_author || '',
                pr_base_branch: ctx.pr_base_branch || '',
                pr_head_branch: ctx.pr_head_branch || '',
                pr_diff: ctx.pr_diff || '',
                pr_files_changed: ctx.pr_files_changed || [],
                additions: 0,
                deletions: 0,
                changed_files: ctx.pr_files_changed?.length || 0,
                state: '',
                mergeable: null,
                html_url: ctx.github_url || '',
              })
            } else if (ctx?.type === 'text') {
              setContextType('text')
              setTextContext(ctx.text || '')
            }
          } catch (err) {
            console.error('Failed to load debate:', err)
            toast.error('Failed to load debate for editing')
            router.push('/war-room')
          } finally {
            setLoadingData(false)
          }
        }
      } catch (err) {
        console.error('Failed to load:', err)
      }
    }
    load()
  }, [editId, router])

  const applyTemplate = (template: DebateTemplate) => {
    setTopic(template.topic_template.replace('{topic}', ''))
    const newParticipants = template.suggested_roles.map((role) => ({
      agent_id: '',
      role,
    }))
    setParticipants(newParticipants.length >= 2 ? newParticipants : [...newParticipants, { agent_id: '', role: '' }])
    // Set context type if template specifies it
    if (template.context_type === 'github_pr') {
      setContextType('github_pr')
    }
    toast.success(`Template "${template.name}" applied!`)
  }

  const handleFetchPR = async () => {
    if (!prUrl.trim()) return
    setPrLoading(true)
    setPrError(null)
    try {
      const info = await fetchPRInfo(prUrl.trim())
      setPrInfo(info)
      // Auto-set topic if empty
      if (!topic) {
        setTopic(`Review PR #${info.pr_number}: ${info.pr_title}`)
      }
    } catch (err) {
      setPrError(err instanceof Error ? err.message : 'Failed to fetch PR info')
      setPrInfo(null)
    } finally {
      setPrLoading(false)
    }
  }

  const addParticipant = () => {
    if (participants.length >= 8) return
    setParticipants([...participants, { agent_id: '', role: '' }])
  }

  const removeParticipant = (index: number) => {
    if (participants.length <= 2) return
    setParticipants(participants.filter((_, i) => i !== index))
  }

  const updateParticipant = (index: number, field: keyof ParticipantRow, value: string) => {
    const updated = [...participants]
    updated[index] = { ...updated[index], [field]: value }
    setParticipants(updated)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!topic.trim() || participants.some((p) => !p.agent_id)) return

    setLoading(true)
    try {
      // Build context
      let context: DebateContext | undefined
      if (contextType === 'github_pr' && prInfo) {
        context = {
          type: 'github_pr',
          github_url: prUrl,
          repo_full_name: prInfo.repo_full_name,
          pr_number: prInfo.pr_number,
          pr_title: prInfo.pr_title,
          pr_description: prInfo.pr_description,
          pr_diff: prInfo.pr_diff,
          pr_files_changed: prInfo.pr_files_changed,
          pr_author: prInfo.pr_author,
          pr_base_branch: prInfo.pr_base_branch,
          pr_head_branch: prInfo.pr_head_branch,
        }
      } else if (contextType === 'text' && textContext.trim()) {
        context = { type: 'text', text: textContext.trim() }
      }

      const payload = {
        topic: topic.trim(),
        debate_type: debateType,
        rounds,
        participants: participants.map((p) => ({
          agent_id: p.agent_id,
          role: p.role || undefined,
        })),
        synthesizer_agent_id: synthesizerAgentId || undefined,
        is_public: isPublic,
        allow_external: allowExternal,
        context,
      }

      if (isEditMode && editId) {
        const debate = await updateDebate(editId, payload)
        toast.success('Debate updated!')
        router.push(`/war-room/${debate.id}`)
      } else {
        const debate = await createDebate(payload)
        toast.success('Debate created!')
        router.push(`/war-room/${debate.id}`)
      }
    } catch (err) {
      console.error(`Failed to ${isEditMode ? 'update' : 'create'} debate:`, err)
      toast.error(`Failed to ${isEditMode ? 'update' : 'create'} debate`)
    } finally {
      setLoading(false)
    }
  }

  if (loadingData) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="h-12 w-12 motion-safe:animate-spin rounded-full border-b-2 border-ink" />
      </div>
    )
  }

  return (
    <DashboardPageShell
      title={isEditMode ? 'Edit Debate' : 'Create Debate'}
      description={isEditMode
        ? 'Update the debate topic, participants, and context before starting the session.'
        : 'Set up a multi-agent debate with participants, context, and sharing options.'}
      icon={Swords}
      badge="War Room"
      maxWidthClassName="max-w-5xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'War Room', href: '/war-room' },
        { label: isEditMode ? 'Edit Debate' : 'Create Debate' },
      ]}
    >
        {/* Templates (hidden in edit mode) */}
        {!isEditMode && templates.length > 0 && (
          <DashboardPagePanel className="mb-8 p-6">
            <div className="mb-4">
              <p className="text-xs font-semibold text-clay">Quick Start</p>
              <h2 className="text-lg font-bold text-ink">Choose a Template</h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {templates.map((t) => (
                <button
                  key={t.id}
                  onClick={() => applyTemplate(t)}
                  className={warmCardClass(false)}
                >
                  <Zap className="mb-2 h-5 w-5 text-ink" />
                  <div className="font-bold text-sm text-ink">{t.name}</div>
                  <div className="text-xs text-ink-mute mt-0.5">{t.description}</div>
                </button>
              ))}
            </div>
          </DashboardPagePanel>
        )}

        <form id="war-room-debate-form" onSubmit={handleSubmit}>
          {/* Main Form Card */}
          <DashboardPagePanel className="overflow-hidden">
            <div className="p-5 md:p-8">
              {/* Section Header */}
              <div className="mb-8">
                <h2 className="text-2xl font-semibold tracking-[-0.04em] text-ink">
                  Debate Setup
                </h2>
                <p className="mt-2 text-sm leading-6 text-ink-soft">
                  Choose the debate topic, context, participants, and verdict options.
                </p>
              </div>

              <div className="space-y-8">
                {/* Topic */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-bold text-ink">
                      Debate Topic *
                    </label>
                    <span className={`text-xs font-medium ${topic.length > 200 ? 'text-leaf' : 'text-ash'}`}>
                      {topic.length}/200
                    </span>
                  </div>
                  <textarea
                    value={topic}
                    onChange={(e) => setTopic(e.target.value.slice(0, 200))}
                    placeholder="e.g., Should we adopt microservices or stay with a monolith?"
                    rows={3}
                    className={`${warmFieldClass} resize-none text-base`}
                    required
                  />
                  <p className="mt-2 text-sm text-ink-mute flex items-center gap-2">
                    <Info size={14} className="text-ash" />
                    Be specific for better debate quality
                  </p>
                </div>

                {/* Context */}
                <div>
                  <label className="block text-sm font-bold text-ink mb-3">
                    Context (Optional)
                  </label>
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <button
                      type="button"
                      onClick={() => { setContextType('none'); setPrInfo(null); setPrError(null) }}
                      className={warmCardClass(contextType === 'none')}
                    >
                      <div className={`font-bold text-sm ${contextType === 'none' ? 'text-gold' : 'text-ink'}`}>
                        No Context
                      </div>
                      <div className="text-xs text-ink-mute">Topic only</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setContextType('github_pr')}
                      className={warmCardClass(contextType === 'github_pr')}
                    >
                      <GitPullRequest className={`w-5 h-5 mb-1 ${contextType === 'github_pr' ? 'text-leaf' : 'text-ash'}`} />
                      <div className={`font-bold text-sm ${contextType === 'github_pr' ? 'text-gold' : 'text-ink'}`}>
                        GitHub PR
                      </div>
                      <div className="text-xs text-ink-mute">Review a pull request</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setContextType('text')}
                      className={warmCardClass(contextType === 'text')}
                    >
                      <FileCode className={`w-5 h-5 mb-1 ${contextType === 'text' ? 'text-leaf' : 'text-ash'}`} />
                      <div className={`font-bold text-sm ${contextType === 'text' ? 'text-gold' : 'text-ink'}`}>
                        Custom Text
                      </div>
                      <div className="text-xs text-ink-mute">Paste any context</div>
                    </button>
                  </div>

                  {/* GitHub PR Input */}
                  {contextType === 'github_pr' && (
                    <div className="space-y-3">
                      <div className="flex gap-2">
                        <div className="flex-1 relative">
                          <Link className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ash" />
                          <input
                            type="url"
                            value={prUrl}
                            onChange={(e) => setPrUrl(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleFetchPR())}
                            placeholder="https://github.com/owner/repo/pull/123"
                            className={`${warmFieldClass} pl-10 pr-4`}
                          />
                        </div>
                        <button
                          type="button"
                          onClick={handleFetchPR}
                          disabled={prLoading || !prUrl.trim()}
                          className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
                        >
                          {prLoading ? <Loader2 className="w-4 h-4 motion-safe:animate-spin" /> : <GitPullRequest className="w-4 h-4" />}
                          Fetch
                        </button>
                      </div>

                      {prError && (
                        <div className="flex items-center gap-2 p-3 bg-blush-wash border border-blush rounded-lg text-sm text-danger">
                          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                          {prError}
                        </div>
                      )}

                      {prInfo && (
                        <div className="space-y-3 rounded-[1.2rem] border border-leaf-wash bg-leaf-wash p-4">
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <GitPullRequest className="w-4 h-4 text-leaf" />
                                <span className="text-sm font-bold text-ink">
                                  #{prInfo.pr_number} {prInfo.pr_title}
                                </span>
                              </div>
                              <div className="flex items-center gap-3 text-xs text-ink-mute">
                                <span>{prInfo.repo_full_name}</span>
                                <span>by {prInfo.pr_author}</span>
                                <span>{prInfo.pr_head_branch} → {prInfo.pr_base_branch}</span>
                              </div>
                            </div>
                            <a
                              href={prInfo.html_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs font-semibold text-leaf hover:text-leaf"
                            >
                              View on GitHub
                            </a>
                          </div>

                          <div className="flex items-center gap-4 text-xs">
                            <span className="px-2 py-1 bg-leaf-wash text-forest rounded-md font-medium">
                              +{prInfo.additions}
                            </span>
                            <span className="px-2 py-1 bg-blush-wash text-wine rounded-md font-medium">
                              -{prInfo.deletions}
                            </span>
                            <span className="text-ink-mute">{prInfo.changed_files} files changed</span>
                          </div>

                          {prInfo.pr_files_changed.length > 0 && (
                            <div>
                              <p className="text-xs font-semibold text-ink-soft mb-1">Files:</p>
                              <div className="flex flex-wrap gap-1">
                                {prInfo.pr_files_changed.slice(0, 10).map((f) => (
                                  <span key={f} className="text-[11px] px-2 py-0.5 bg-white border border-line rounded text-ink-soft font-mono">
                                    {f.split('/').pop()}
                                  </span>
                                ))}
                                {prInfo.pr_files_changed.length > 10 && (
                                  <span className="text-[11px] text-ash">
                                    +{prInfo.pr_files_changed.length - 10} more
                                  </span>
                                )}
                              </div>
                            </div>
                          )}

                          {prInfo.pr_diff && (
                            <div>
                              <button
                                type="button"
                                onClick={() => setShowDiff(!showDiff)}
                                className="flex items-center gap-1 text-xs text-ink-mute hover:text-ink-soft font-medium"
                              >
                                {showDiff ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                {showDiff ? 'Hide' : 'Show'} diff preview
                              </button>
                              {showDiff && (
                                <pre className="mt-2 p-3 bg-ink text-taupe text-[11px] rounded-lg overflow-x-auto max-h-64 overflow-y-auto font-mono leading-relaxed">
                                  {prInfo.pr_diff.slice(0, 5000)}
                                  {prInfo.pr_diff.length > 5000 && '\n\n… (truncated for preview)'}
                                </pre>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Text Context Input */}
                  {contextType === 'text' && (
                    <textarea
                      value={textContext}
                      onChange={(e) => setTextContext(e.target.value)}
                      placeholder="Paste any context here, code snippets, documents, requirements, etc."
                      rows={6}
                      className={`${warmFieldClass} resize-none font-mono`}
                    />
                  )}
                </div>

                {/* Type & Rounds */}
                <div>
                  <label className="block text-sm font-bold text-ink mb-3">
                    Debate Format
                  </label>
                  <div className="grid grid-cols-2 gap-4">
                    {/* Debate Type Cards */}
                    <button
                      type="button"
                      onClick={() => setDebateType('structured')}
                      className={warmCardClass(debateType === 'structured')}
                    >
                      <Users className={`w-6 h-6 mb-2 ${debateType === 'structured' ? 'text-leaf' : 'text-ash'}`} />
                      <div className={`font-bold text-sm ${debateType === 'structured' ? 'text-gold' : 'text-ink'}`}>
                        Structured
                      </div>
                      <div className="text-xs text-ink-mute">Fixed rounds, each agent speaks in order</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setDebateType('freeform')}
                      className={warmCardClass(debateType === 'freeform')}
                    >
                      <Zap className={`w-6 h-6 mb-2 ${debateType === 'freeform' ? 'text-leaf' : 'text-ash'}`} />
                      <div className={`font-bold text-sm ${debateType === 'freeform' ? 'text-gold' : 'text-ink'}`}>
                        Freeform
                      </div>
                      <div className="text-xs text-ink-mute">Open discussion, agents respond freely</div>
                    </button>
                  </div>
                </div>

                {/* Rounds Slider */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-bold text-ink">
                      Number of Rounds
                    </label>
                    <span className="text-sm font-bold text-leaf">{rounds}</span>
                  </div>
                  <input
                    type="range"
                    value={rounds}
                    onChange={(e) => setRounds(parseInt(e.target.value))}
                    min={1}
                    max={10}
                    className="h-2 w-full cursor-pointer appearance-none rounded-full bg-line accent-leaf"
                  />
                  <div className="flex justify-between text-xs text-ash mt-1">
                    <span>1</span>
                    <span>5</span>
                    <span>10</span>
                  </div>
                </div>

                {/* Participants */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label className="block text-sm font-bold text-ink">
                      Participants *
                    </label>
                    {participants.length < 8 && (
                      <button
                        type="button"
                        onClick={addParticipant}
                        className="flex items-center gap-1.5 rounded-[0.9rem] px-3 py-1.5 text-sm font-semibold text-leaf transition-colors hover:bg-paper"
                      >
                        <Plus size={16} />
                        Add Participant
                      </button>
                    )}
                  </div>
                  <div className="space-y-3">
                    {participants.map((p, i) => (
                      <div key={i} className="flex items-center gap-3 rounded-[1.15rem] border border-black/10 bg-cream p-4">
                        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-ink text-xs font-bold text-white">
                          {i + 1}
                        </div>
                        <select
                          value={p.agent_id}
                          onChange={(e) => updateParticipant(i, 'agent_id', e.target.value)}
                          className={`flex-1 ${warmFieldClass}`}
                          required
                        >
                          <option value="">Select agent…</option>
                          {agents.map((a) => (
                            <option key={a.id} value={a.id}>{a.agent_name}</option>
                          ))}
                        </select>
                        <input
                          type="text"
                          value={p.role}
                          onChange={(e) => updateParticipant(i, 'role', e.target.value)}
                          placeholder="Role (e.g., Advocate, Critic)"
                          className={`w-48 ${warmFieldClass}`}
                        />
                        {participants.length > 2 && (
                          <button
                            type="button"
                            onClick={() => removeParticipant(i)}
                            className="rounded-lg p-2 text-ash transition-colors hover:bg-paper hover:text-danger"
                          >
                            <X size={18} />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Synthesizer */}
                <div>
                  <label className="block text-sm font-bold text-ink mb-2">
                    Verdict Synthesizer
                  </label>
                  <select
                    value={synthesizerAgentId}
                    onChange={(e) => setSynthesizerAgentId(e.target.value)}
                    className={`${warmFieldClass} text-base`}
                  >
                    <option value="">No synthesizer (optional)</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>{a.agent_name}</option>
                    ))}
                  </select>
                  <p className="mt-2 text-sm text-ink-mute flex items-center gap-2">
                    <Info size={14} className="text-ash" />
                    This agent will analyze all arguments and deliver the final verdict
                  </p>
                </div>

                {/* Options */}
                <div>
                  <label className="block text-sm font-bold text-ink mb-3">
                    Options
                  </label>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setIsPublic(!isPublic)}
                      className={warmCardClass(isPublic)}
                    >
                      <Globe className={`w-6 h-6 mb-2 ${isPublic ? 'text-leaf' : 'text-ash'}`} />
                      <div className={`font-bold text-sm ${isPublic ? 'text-gold' : 'text-ink'}`}>
                        Public Debate
                      </div>
                      <div className="text-xs text-ink-mute">Generate a shareable link anyone can watch</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setAllowExternal(!allowExternal)}
                      className={warmCardClass(allowExternal)}
                    >
                      <ExternalLink className={`w-6 h-6 mb-2 ${allowExternal ? 'text-leaf' : 'text-ash'}`} />
                      <div className={`font-bold text-sm ${allowExternal ? 'text-gold' : 'text-ink'}`}>
                        External Agents
                      </div>
                      <div className="text-xs text-ink-mute">Allow any external agent to join via API</div>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between border-t border-sand-deep bg-paper px-8 py-4">
              <div />
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => router.push('/war-room')}
                  className="rounded-[1rem] border border-black/10 bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:bg-cream"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading || !topic.trim() || participants.some((p) => !p.agent_id)}
                  className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full motion-safe:animate-spin" />
                      {isEditMode ? 'Saving…' : 'Creating…'}
                    </>
                  ) : (
                    isEditMode ? 'Save Changes' : 'Create Debate'
                  )}
                </button>
              </div>
            </div>
          </DashboardPagePanel>
        </form>
    </DashboardPageShell>
  )
}
