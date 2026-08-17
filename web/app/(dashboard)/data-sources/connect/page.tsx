'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, AlertCircle, CheckCircle, Database } from 'lucide-react'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import { apiClient } from '@/lib/api/client'

interface KnowledgeBase {
  id: number
  name: string
}

interface OAuthApp {
  id: number
  app_name: string
  provider: string
  client_id: string
  is_active: boolean
  is_default: boolean
}

interface SlackBot {
  id: string
  bot_name: string
  slack_workspace_name: string | null
  connection_status: string
}

const SOURCE_TYPES = [
  {
    value: 'SLACK',
    label: 'Slack',
    description: 'Sync messages, threads, and files from Slack channels',
    icon: '💬',
    color: 'bg-[#f4ebe2] text-[#6f4f36]',
    authLabel: 'OAuth Required',
  },
  {
    value: 'GMAIL',
    label: 'Gmail',
    description: 'Sync emails from Gmail using labels and filters',
    icon: '📧',
    color: 'bg-[#f8e4dd] text-[#9f4b31]',
    authLabel: 'OAuth Required',
  },
  {
    value: 'GITHUB',
    label: 'GitHub',
    description: 'Sync repositories, issues, pull requests, and discussions',
    icon: '🐙',
    color: 'bg-[#e6f0ea] text-[#2f6a51]',
    authLabel: 'OAuth Required',
  },
  {
    value: 'JIRA',
    label: 'Jira',
    description: 'Sync issues, comments, and project activity from Jira',
    icon: '📋',
    color: 'bg-[#e7edfb] text-[#31489f]',
    authLabel: 'OAuth Required',
  },
  {
    value: 'CLICKUP',
    label: 'ClickUp',
    description: 'Sync tasks and docs across ClickUp spaces and lists',
    icon: '✅',
    color: 'bg-[#f0e9fb] text-[#6a3f9f]',
    authLabel: 'OAuth Required',
  },
  {
    value: 'NOTION',
    label: 'Notion',
    description: 'Sync pages and databases using a Notion internal integration token',
    icon: '📓',
    color: 'bg-[#eceaea] text-[#3a3a3a]',
    authLabel: 'API Token',
  },
  {
    value: 'CONFLUENCE',
    label: 'Confluence',
    description: 'Sync spaces and pages using an API token or personal access token',
    icon: '📚',
    color: 'bg-[#e6f0ea] text-[#2f6a51]',
    authLabel: 'API Token',
  },
  {
    value: 'LINEAR',
    label: 'Linear',
    description: 'Sync issues and project activity using a Linear personal API key',
    icon: '📐',
    color: 'bg-[#e7edfb] text-[#31489f]',
    authLabel: 'API Token',
  },
]

// Types that authenticate with a directly-pasted API token/PAT instead of an OAuth app.
const DIRECT_AUTH_TYPES = new Set(['NOTION', 'CONFLUENCE', 'LINEAR'])

function ConnectDataSourceContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const kbIdParam = searchParams.get('kb_id')
  const hasPresetKb = Boolean(kbIdParam)

  const [step, setStep] = useState<'select-type' | 'select-kb' | 'configure'>('select-type')
  const [selectedType, setSelectedType] = useState<string>('')
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [selectedKbId, setSelectedKbId] = useState<number | null>(kbIdParam ? parseInt(kbIdParam) : null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dataSourceName, setDataSourceName] = useState<string>('')
  const [oauthApps, setOauthApps] = useState<OAuthApp[]>([])
  const [selectedOAuthAppId, setSelectedOAuthAppId] = useState<number | null>(null)
  const [checkingOAuth, setCheckingOAuth] = useState(false)
  const [slackBots, setSlackBots] = useState<SlackBot[]>([])
  const [selectedSlackBotId, setSelectedSlackBotId] = useState<string | null>(null)
  const [useExistingSlackBot, setUseExistingSlackBot] = useState(false)
  const [repositories, setRepositories] = useState<any[]>([])
  const [loadingRepos, setLoadingRepos] = useState(false)
  const [selectedRepos, setSelectedRepos] = useState<Set<string>>(new Set())

  // Slack config
  const [slackConfig, setSlackConfig] = useState({
    channels: '',
    sync_frequency: 3600,
    include_threads: true,
    include_files: true,
  })

  // Gmail config
  const [gmailConfig, setGmailConfig] = useState({
    labels: '',
    query: '',
    sync_frequency: 3600,
  })

  // GitHub config
  const [githubConfig, setGithubConfig] = useState({
    repositories: '',
    sync_frequency: 3600,
    include_issues: true,
    include_pull_requests: true,
    include_discussions: false,
    create_wiki: false,
  })

  // Notion config (direct-auth: internal integration token)
  const [notionConfig, setNotionConfig] = useState({
    internal_token: '',
    sync_frequency: 3600,
  })

  // Confluence config (direct-auth: PAT or email + API token)
  const [confluenceConfig, setConfluenceConfig] = useState({
    pat: '',
    email: '',
    api_token: '',
    sync_frequency: 3600,
  })

  // Linear config (direct-auth: personal API key)
  const [linearConfig, setLinearConfig] = useState({
    api_key: '',
    sync_frequency: 3600,
  })

  const currentStep = step === 'select-type' ? 1 : step === 'select-kb' ? 2 : 3
  const steps = [
    { id: 1, label: 'Select Type' },
    { id: 2, label: 'Select KB' },
    { id: 3, label: 'Configure' },
  ]
  const fieldClass = 'w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500'
  const labelClass = 'mb-2 block text-sm font-semibold text-gray-700'
  const compactLabelClass = 'mb-1.5 block text-sm font-semibold text-gray-700'
  const helpClass = 'mt-2 text-xs leading-relaxed text-gray-500'
  const selectedSource = SOURCE_TYPES.find((type) => type.value === selectedType)
  const selectedKnowledgeBase = knowledgeBases.find((kb) => kb.id === selectedKbId)
  const isDirectAuth = DIRECT_AUTH_TYPES.has(selectedType)

  useEffect(() => {
    fetchKnowledgeBases()
    if (kbIdParam) {
      setStep('select-type')
    }
  }, [])

  const fetchKnowledgeBases = async () => {
    try {
      const data = await apiClient.getKnowledgeBases()
      setKnowledgeBases(Array.isArray(data) ? data : [])
    } catch (err) {
      console.error('Failed to fetch knowledge bases:', err)
    }
  }

  const fetchOAuthApps = async (provider: string) => {
    setCheckingOAuth(true)
    try {
      const data = await apiClient.getOAuthApps(provider)
      const apps = Array.isArray(data) ? data : []
      setOauthApps(apps)

      // Auto-select if only one app
      if (apps.length === 1) {
        setSelectedOAuthAppId(apps[0].id)
      }

      let hasSlackBots = false
      if (provider === 'SLACK') {
        const bots = await apiClient.getSlackBots()
        const activeBots = (Array.isArray(bots) ? bots : []).filter(
          (b: SlackBot) => b.connection_status === 'connected'
        )
        setSlackBots(activeBots)
        hasSlackBots = activeBots.length > 0
        if (activeBots.length === 1) {
          setSelectedSlackBotId(activeBots[0].id)
          setUseExistingSlackBot(true)
        }
      }

      return apps.length > 0 || hasSlackBots
    } catch (err) {
      console.error('Failed to fetch OAuth apps:', err)
      return false
    } finally {
      setCheckingOAuth(false)
    }
  }

  const fetchGitHubRepositories = async (oauthAppId: number) => {
    setLoadingRepos(true)
    setError(null)
    try {
      const data = await apiClient.getGitHubRepositories(oauthAppId)
      setRepositories(data.repositories || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch repositories')
      setRepositories([])
    } finally {
      setLoadingRepos(false)
    }
  }

  const handleOAuthAppChange = async (appId: number) => {
    setSelectedOAuthAppId(appId)
    setRepositories([])
    setSelectedRepos(new Set())
    
    if (selectedType === 'GITHUB' && appId) {
      await fetchGitHubRepositories(appId)
    }
  }

  const toggleRepository = (repoFullName: string) => {
    const newSelected = new Set(selectedRepos)
    if (newSelected.has(repoFullName)) {
      newSelected.delete(repoFullName)
    } else {
      newSelected.add(repoFullName)
    }
    setSelectedRepos(newSelected)
    
    // Update the repositories config
    setGithubConfig({
      ...githubConfig,
      repositories: Array.from(newSelected).join(', ')
    })
  }

  const toggleAllRepositories = () => {
    if (selectedRepos.size === repositories.length) {
      setSelectedRepos(new Set())
      setGithubConfig({ ...githubConfig, repositories: '' })
    } else {
      const allRepos = new Set(repositories.map(r => r.full_name))
      setSelectedRepos(allRepos)
      setGithubConfig({ ...githubConfig, repositories: Array.from(allRepos).join(', ') })
    }
  }

  const handleTypeSelect = async (type: string) => {
    setSelectedType(type)
    // Set default name based on type
    const defaultName = `${type.charAt(0).toUpperCase() + type.slice(1)} Data Source`
    setDataSourceName(defaultName)

    if (selectedKbId) {
      if (DIRECT_AUTH_TYPES.has(type)) {
        setStep('configure')
        return
      }
      // Check OAuth apps / Slack bots before proceeding
      const hasCredentials = await fetchOAuthApps(type)
      if (hasCredentials) {
        setStep('configure')
      } else {
        setError(
          `No connected ${type} account found. Please connect an OAuth app (or a Slack bot) for ${type} first.`
        )
      }
    } else {
      setStep('select-kb')
    }
  }

  const handleKbSelect = async (kbId: number) => {
    setSelectedKbId(kbId)

    if (DIRECT_AUTH_TYPES.has(selectedType)) {
      setStep('configure')
      return
    }

    // Check OAuth apps / Slack bots before proceeding
    const hasCredentials = await fetchOAuthApps(selectedType)
    if (hasCredentials) {
      setStep('configure')
    } else {
      setError(
        `No connected ${selectedType} account found. Please connect an OAuth app (or a Slack bot) for ${selectedType} first.`
      )
    }
  }

  const handleConfigureBack = () => {
    setStep(hasPresetKb ? 'select-type' : 'select-kb')
  }

  const handleConnect = async () => {
    if (!selectedType || !selectedKbId || !dataSourceName.trim()) {
      setError('Please provide a name for the data source')
      return
    }

    const usingSlackBot = selectedType === 'SLACK' && useExistingSlackBot && selectedSlackBotId
    if (!isDirectAuth && !usingSlackBot && !selectedOAuthAppId) {
      setError('Please select an OAuth app or an existing Slack bot')
      return
    }

    if (selectedType === 'NOTION' && !notionConfig.internal_token.trim()) {
      setError('Please provide a Notion internal integration token')
      return
    }
    if (
      selectedType === 'CONFLUENCE' &&
      !confluenceConfig.pat.trim() &&
      !(confluenceConfig.email.trim() && confluenceConfig.api_token.trim())
    ) {
      setError('Please provide a Confluence personal access token, or an email + API token')
      return
    }
    if (selectedType === 'LINEAR' && !linearConfig.api_key.trim()) {
      setError('Please provide a Linear personal API key')
      return
    }

    setLoading(true)
    setError(null)

    try {
      let sourceConfig
      if (selectedType === 'SLACK') {
        sourceConfig = slackConfig
      } else if (selectedType === 'GMAIL') {
        sourceConfig = gmailConfig
      } else if (selectedType === 'GITHUB') {
        sourceConfig = githubConfig
      } else if (selectedType === 'NOTION') {
        sourceConfig = notionConfig
      } else if (selectedType === 'CONFLUENCE') {
        sourceConfig = confluenceConfig
      } else if (selectedType === 'LINEAR') {
        sourceConfig = linearConfig
      }

      // Create data source with selected OAuth app or linked Slack bot
      await apiClient.createDataSource({
        name: dataSourceName.trim(),
        type: selectedType,
        knowledge_base_id: selectedKbId,
        config: sourceConfig,
        oauth_app_id: usingSlackBot ? null : selectedOAuthAppId,
        slack_bot_id: usingSlackBot ? selectedSlackBotId : null,
      })

      // Redirect back to data sources list
      router.push('/data-sources')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setLoading(false)
    }
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="overflow-hidden rounded-[2rem] border border-[#eadfce] bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.96),_rgba(247,240,231,0.94)_50%,_rgba(237,230,220,0.92)_100%)] shadow-[0_28px_80px_-42px_rgba(88,63,39,0.32)]">
          <div className="flex flex-col gap-6 p-6 md:p-8">
            <Link
              href="/data-sources"
              className="inline-flex w-fit items-center gap-2 rounded-full border border-[#dbcdb9] bg-white/80 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:border-[#cdb79d] hover:text-gray-900"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Data Sources
            </Link>

            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl space-y-3">
                <div className="inline-flex items-center gap-2 rounded-full border border-[#dfd1be] bg-white/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7c5d45]">
                  <Database className="h-3.5 w-3.5" />
                  Data Source Setup
                </div>
                <div className="space-y-2">
                  <h1 className="text-3xl font-semibold tracking-[-0.04em] text-gray-950 md:text-[2.6rem]">
                    Connect Data Source
                  </h1>
                  <p className="max-w-xl text-sm leading-6 text-gray-600 md:text-[15px]">
                    Connect a data source to sync documents to your knowledge base.
                  </p>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[1.5rem] border border-white/70 bg-white/75 px-4 py-3 shadow-[0_20px_45px_-38px_rgba(77,51,28,0.4)] backdrop-blur">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Current Step</p>
                  <p className="mt-2 text-lg font-semibold text-gray-900">{steps[currentStep - 1].label}</p>
                </div>
                <div className="rounded-[1.5rem] border border-white/70 bg-white/75 px-4 py-3 shadow-[0_20px_45px_-38px_rgba(77,51,28,0.4)] backdrop-blur">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Selection</p>
                  <div className="mt-2 space-y-1">
                    <p className="text-lg font-semibold text-gray-900">
                      {selectedSource?.label || 'Choose source'}
                    </p>
                    <p className="text-sm text-gray-500">
                      {selectedKnowledgeBase?.name || (hasPresetKb ? 'Knowledge base selected' : 'Choose knowledge base')}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-[1.75rem] border border-[#e7dccd] bg-white/95 p-4 shadow-[0_24px_60px_-42px_rgba(76,48,23,0.28)]">
          <div className="grid gap-3 md:grid-cols-3">
            {steps.map((stepItem) => {
              const isActive = stepItem.id === currentStep
              const isComplete = stepItem.id < currentStep

              return (
                <div
                  key={stepItem.id}
                  className={`rounded-[1.35rem] border px-4 py-4 transition-all ${
                    isActive
                      ? 'border-[#d7bea3] bg-[#f6ede4] shadow-[0_18px_36px_-28px_rgba(104,72,46,0.3)]'
                      : isComplete
                        ? 'border-[#d9e6dc] bg-[#eef6f1]'
                        : 'border-gray-200 bg-gray-50/90'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold ${
                        isActive
                          ? 'bg-gray-950 text-white'
                          : isComplete
                            ? 'bg-[#2f6a51] text-white'
                            : 'bg-white text-gray-500'
                      }`}
                    >
                      {isComplete ? <CheckCircle className="h-4 w-4" /> : stepItem.id}
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500">
                        Step {stepItem.id}
                      </p>
                      <p className="text-sm font-semibold text-gray-900">{stepItem.label}</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {error && (
          <div className="rounded-[1.6rem] border border-[#e6c0b8] bg-[#fbefec] px-5 py-4 text-sm text-[#8f3f2c] shadow-[0_16px_40px_-34px_rgba(152,64,42,0.28)]">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
              <div className="flex-1">
                <p className="font-semibold text-[#7f301f]">Unable to continue</p>
                <p className="mt-1 leading-6">{error}</p>
              </div>
              <button
                onClick={() => setError(null)}
                className="rounded-full border border-[#e1b5aa] px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#8f3f2c] transition-colors hover:bg-white/70"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {step === 'select-type' && (
          <div className="space-y-5">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#9a7a5e]">Step 1</p>
              <h2 className="text-2xl font-semibold tracking-[-0.03em] text-gray-950">Select Data Source Type</h2>
              <p className="text-sm leading-6 text-gray-600">
                Select the type of data source you want to connect.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {SOURCE_TYPES.map((type) => (
                <button
                  key={type.value}
                  onClick={() => handleTypeSelect(type.value)}
                  className="group rounded-[1.75rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(247,242,236,0.94))] p-5 text-left shadow-[0_20px_50px_-40px_rgba(73,45,23,0.28)] transition-all duration-200 hover:-translate-y-0.5 hover:border-[#d4baa1] hover:shadow-[0_26px_60px_-36px_rgba(73,45,23,0.34)]"
                >
                  <div className="space-y-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex h-14 w-14 items-center justify-center rounded-[1.3rem] bg-white text-3xl shadow-[inset_0_1px_0_rgba(255,255,255,0.7),0_16px_30px_-24px_rgba(74,49,22,0.45)]">
                        {type.icon}
                      </div>
                      <span className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${type.color}`}>
                        {type.authLabel}
                      </span>
                    </div>

                    <div className="space-y-2">
                      <h3 className="text-lg font-semibold text-gray-950">{type.label}</h3>
                      <p className="text-sm leading-6 text-gray-600">{type.description}</p>
                    </div>

                    <div className="flex items-center justify-between border-t border-[#ebe1d6] pt-4">
                      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Connect securely</span>
                      <span className="text-sm font-semibold text-gray-900 transition-transform duration-200 group-hover:translate-x-0.5">
                        Continue
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 'select-kb' && (
          <div className="space-y-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#9a7a5e]">Step 2</p>
                <h2 className="text-2xl font-semibold tracking-[-0.03em] text-gray-950">Select Knowledge Base</h2>
                <p className="text-sm leading-6 text-gray-600">
                  Choose which knowledge base should receive this data source.
                </p>
              </div>
              <button
                onClick={() => setStep('select-type')}
                className="inline-flex items-center gap-2 rounded-full border border-[#ddd2c2] bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:border-[#ccb59a] hover:text-gray-900"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </button>
            </div>

            {knowledgeBases.length > 0 ? (
              <div className="grid gap-3">
                {knowledgeBases.map((kb) => (
                  <button
                    key={kb.id}
                    onClick={() => handleKbSelect(kb.id)}
                    className={`rounded-[1.5rem] border px-5 py-4 text-left shadow-[0_18px_44px_-38px_rgba(68,43,19,0.22)] transition-all ${
                      selectedKbId === kb.id
                        ? 'border-[#cfae8b] bg-[#f8efe5]'
                        : 'border-[#e4d9cb] bg-white hover:border-[#cfb69c] hover:bg-[#fcfaf7]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#9a7a5e]">Knowledge Base</p>
                        <h3 className="mt-1 text-base font-semibold text-gray-950">{kb.name}</h3>
                      </div>
                      <span className={`text-sm font-semibold ${selectedKbId === kb.id ? 'text-[#8f5a2d]' : 'text-gray-900'}`}>
                        {selectedKbId === kb.id ? 'Selected' : 'Select'}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="rounded-[1.75rem] border border-[#e5d9ca] bg-white px-6 py-10 text-center shadow-[0_18px_48px_-40px_rgba(70,43,22,0.25)]">
                <p className="text-lg font-semibold text-gray-900">No knowledge bases found.</p>
                <p className="mt-2 text-sm text-gray-600">Create a knowledge base first, then return here to connect your source.</p>
                <Link
                  href="/knowledge-bases/create"
                  className="mt-5 inline-flex items-center rounded-full bg-gray-950 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-gray-800"
                >
                  Create knowledge base
                </Link>
              </div>
            )}
          </div>
        )}

        {checkingOAuth && (
          <div className="rounded-[1.85rem] border border-[#e7dccd] bg-white px-6 py-12 shadow-[0_24px_60px_-42px_rgba(76,48,23,0.28)]">
            <div className="flex flex-col items-center justify-center text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[#f6ede4]">
                <LoadingSpinner />
              </div>
              <h3 className="mt-5 text-lg font-semibold text-gray-900">Checking OAuth configuration</h3>
              <p className="mt-2 max-w-md text-sm leading-6 text-gray-600">
                Checking available OAuth apps for {selectedSource?.label || 'this source'}.
              </p>
            </div>
          </div>
        )}

        {!checkingOAuth &&
          !isDirectAuth &&
          oauthApps.length === 0 &&
          !(selectedType === 'SLACK' && slackBots.length > 0) &&
          selectedType &&
          selectedKbId && (
          <div className="rounded-[1.9rem] border border-[#ead8aa] bg-[linear-gradient(180deg,_rgba(255,251,237,0.98),_rgba(251,244,217,0.96))] p-6 shadow-[0_24px_60px_-44px_rgba(126,89,25,0.25)]">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
              <div className="flex h-14 w-14 items-center justify-center rounded-[1.25rem] bg-white/85 text-[#9d6a1e] shadow-[0_16px_32px_-24px_rgba(126,89,25,0.28)]">
                <AlertCircle className="h-6 w-6" />
              </div>

              <div className="flex-1 space-y-5">
                <div className="space-y-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#a1722a]">OAuth Required</p>
                  <h3 className="text-2xl font-semibold tracking-[-0.03em] text-[#4e3415]">OAuth app not configured</h3>
                  <p className="max-w-3xl text-sm leading-6 text-[#725433]">
                    You need to configure a {selectedSource?.label || 'data source'} OAuth app before you can connect this integration. OAuth apps let Synkora securely access your account on your behalf.
                  </p>
                </div>

                <div className="rounded-[1.5rem] border border-[#eadbb4] bg-white/75 p-5">
                  <p className="text-sm font-semibold text-gray-900">What you need to do</p>
                  <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-gray-700">
                    <li>Create a {selectedSource?.label || 'provider'} OAuth app in the provider developer console.</li>
                    <li>Configure the required scopes and callback URL.</li>
                    <li>Add the OAuth credentials to Synkora.</li>
                    <li>Return here and continue the connection flow.</li>
                  </ol>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Link
                    href="/oauth-apps/create"
                    className="inline-flex items-center rounded-full bg-gray-950 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-gray-800"
                  >
                    Configure OAuth App
                  </Link>
                  <button
                    onClick={handleConfigureBack}
                    className="inline-flex items-center rounded-full border border-[#d7c4aa] bg-white/75 px-5 py-2.5 text-sm font-semibold text-gray-700 transition-colors hover:border-[#c8b090] hover:text-gray-900"
                  >
                    Go Back
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {!checkingOAuth &&
          step === 'configure' &&
          (isDirectAuth || oauthApps.length > 0 || (selectedType === 'SLACK' && slackBots.length > 0)) && (
          <div className="space-y-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#9a7a5e]">Step 3</p>
                <h2 className="text-2xl font-semibold tracking-[-0.03em] text-gray-950">
                  Configure {selectedSource?.label || 'Data Source'}
                </h2>
                <p className="text-sm leading-6 text-gray-600">
                  Configure the connection and sync settings.
                </p>
              </div>
              <button
                onClick={handleConfigureBack}
                className="inline-flex items-center gap-2 rounded-full border border-[#ddd2c2] bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:border-[#ccb59a] hover:text-gray-900"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </button>
            </div>

            <div className="rounded-[2rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] p-6 shadow-[0_28px_70px_-48px_rgba(73,45,23,0.32)] md:p-8">
              <div className="space-y-8">
                {selectedType === 'SLACK' && slackBots.length > 0 && (
                  <div className="mb-5 space-y-3">
                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => setUseExistingSlackBot(true)}
                        className={`flex-1 rounded-[1.1rem] border px-4 py-3 text-sm font-semibold transition-all ${
                          useExistingSlackBot
                            ? 'border-[#d7bea3] bg-[#f6ede4] text-gray-900'
                            : 'border-gray-200 bg-white text-gray-600'
                        }`}
                      >
                        Use existing Slack bot
                      </button>
                      <button
                        type="button"
                        onClick={() => setUseExistingSlackBot(false)}
                        className={`flex-1 rounded-[1.1rem] border px-4 py-3 text-sm font-semibold transition-all ${
                          !useExistingSlackBot
                            ? 'border-[#d7bea3] bg-[#f6ede4] text-gray-900'
                            : 'border-gray-200 bg-white text-gray-600'
                        }`}
                      >
                        Set up new OAuth app
                      </button>
                    </div>

                    {useExistingSlackBot && (
                      <select
                        value={selectedSlackBotId || ''}
                        onChange={(e) => setSelectedSlackBotId(e.target.value)}
                        className="w-full rounded-[1rem] border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900"
                      >
                        <option value="" disabled>
                          Select a Slack bot
                        </option>
                        {slackBots.map((bot) => (
                          <option key={bot.id} value={bot.id}>
                            {bot.bot_name} {bot.slack_workspace_name ? `(${bot.slack_workspace_name})` : ''}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                )}

                <div className="grid gap-4 md:grid-cols-2">
                  {!isDirectAuth && !(selectedType === 'SLACK' && useExistingSlackBot) && (
                  <div>
                    <label className={labelClass}>
                      Select OAuth App <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={selectedOAuthAppId || ''}
                      onChange={(e) => handleOAuthAppChange(parseInt(e.target.value))}
                      className={fieldClass}
                      required
                    >
                      <option value="">Choose an OAuth app...</option>
                      {oauthApps.map((app) => (
                        <option key={app.id} value={app.id}>
                          {app.app_name}
                        </option>
                      ))}
                    </select>
                    <p className={helpClass}>
                      Select which {selectedSource?.label || 'source'} account should power this connection.
                    </p>
                  </div>
                  )}

                  <div>
                    <label className={labelClass}>
                      Data Source Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={dataSourceName}
                      onChange={(e) => setDataSourceName(e.target.value)}
                      className={fieldClass}
                      placeholder={`e.g., My ${selectedSource?.label || 'Data'} Source`}
                      required
                    />
                    <p className={helpClass}>Give this source a clear internal name so it is easy to recognize later.</p>
                  </div>
                </div>

                {selectedType === 'SLACK' && (
                  <div className="rounded-[1.5rem] border border-[#ebe1d5] bg-white/70 p-5 md:p-6">
                    <div className="mb-5">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Slack Settings</p>
                      <h3 className="mt-2 text-lg font-semibold text-gray-950">Workspace sync configuration</h3>
                    </div>

                    <div className="grid gap-5 md:grid-cols-2">
                      <div>
                        <label className={labelClass}>Channels (comma-separated)</label>
                        <input
                          type="text"
                          value={slackConfig.channels}
                          onChange={(e) => setSlackConfig({ ...slackConfig, channels: e.target.value })}
                          className={fieldClass}
                          placeholder="e.g., general, engineering, support"
                        />
                        <p className={helpClass}>Leave empty to sync all channels you have access to.</p>
                      </div>

                      <div>
                        <label className={labelClass}>Sync Frequency (seconds)</label>
                        <input
                          type="number"
                          value={slackConfig.sync_frequency}
                          onChange={(e) => setSlackConfig({ ...slackConfig, sync_frequency: parseInt(e.target.value) })}
                          className={fieldClass}
                          min="60"
                        />
                        <p className={helpClass}>How often to check for new Slack content. Minimum 60 seconds.</p>
                      </div>
                    </div>

                    <div className="mt-5 grid gap-3 md:grid-cols-2">
                      <label className="flex items-center gap-3 rounded-[1.1rem] border border-[#ebe1d5] bg-[#faf7f2] px-4 py-3">
                        <input
                          type="checkbox"
                          checked={slackConfig.include_threads}
                          onChange={(e) => setSlackConfig({ ...slackConfig, include_threads: e.target.checked })}
                          className="h-4 w-4 rounded border-gray-300 text-gray-950 focus:ring-red-500"
                        />
                        <div>
                          <p className="text-sm font-semibold text-gray-900">Include thread replies</p>
                          <p className="text-xs text-gray-500">Keep conversation context connected.</p>
                        </div>
                      </label>

                      <label className="flex items-center gap-3 rounded-[1.1rem] border border-[#ebe1d5] bg-[#faf7f2] px-4 py-3">
                        <input
                          type="checkbox"
                          checked={slackConfig.include_files}
                          onChange={(e) => setSlackConfig({ ...slackConfig, include_files: e.target.checked })}
                          className="h-4 w-4 rounded border-gray-300 text-gray-950 focus:ring-red-500"
                        />
                        <div>
                          <p className="text-sm font-semibold text-gray-900">Include file attachments</p>
                          <p className="text-xs text-gray-500">Bring uploaded files into the sync flow.</p>
                        </div>
                      </label>
                    </div>
                  </div>
                )}

                {selectedType === 'GMAIL' && (
                  <div className="rounded-[1.5rem] border border-[#ebe1d5] bg-white/70 p-5 md:p-6">
                    <div className="mb-5">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Gmail Settings</p>
                      <h3 className="mt-2 text-lg font-semibold text-gray-950">Mailbox sync configuration</h3>
                    </div>

                    <div className="grid gap-5 md:grid-cols-2">
                      <div>
                        <label className={labelClass}>Labels (comma-separated)</label>
                        <input
                          type="text"
                          value={gmailConfig.labels}
                          onChange={(e) => setGmailConfig({ ...gmailConfig, labels: e.target.value })}
                          className={fieldClass}
                          placeholder="e.g., INBOX, IMPORTANT"
                        />
                        <p className={helpClass}>Leave empty to sync all emails.</p>
                      </div>

                      <div>
                        <label className={labelClass}>Search Query (optional)</label>
                        <input
                          type="text"
                          value={gmailConfig.query}
                          onChange={(e) => setGmailConfig({ ...gmailConfig, query: e.target.value })}
                          className={fieldClass}
                          placeholder="e.g., from:example@gmail.com"
                        />
                        <p className={helpClass}>Use Gmail search syntax to filter the synced messages.</p>
                      </div>
                    </div>

                    <div className="mt-5 max-w-sm">
                      <label className={labelClass}>Sync Frequency (seconds)</label>
                      <input
                        type="number"
                        value={gmailConfig.sync_frequency}
                        onChange={(e) => setGmailConfig({ ...gmailConfig, sync_frequency: parseInt(e.target.value) })}
                        className={fieldClass}
                        min="60"
                      />
                      <p className={helpClass}>How often to check for new emails. Minimum 60 seconds.</p>
                    </div>
                  </div>
                )}

                {selectedType === 'GITHUB' && (
                  <div className="space-y-6 rounded-[1.5rem] border border-[#ebe1d5] bg-white/70 p-5 md:p-6">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">GitHub Settings</p>
                      <h3 className="mt-2 text-lg font-semibold text-gray-950">Repository sync configuration</h3>
                    </div>

                    {selectedOAuthAppId && (
                      <div className="space-y-3">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <div>
                            <label className={compactLabelClass}>Select Repositories</label>
                            <p className="text-xs text-gray-500">Choose specific repositories, or leave all unchecked to sync all accessible repositories.</p>
                          </div>
                          {repositories.length > 0 && (
                            <button
                              onClick={toggleAllRepositories}
                              className="inline-flex items-center rounded-full border border-[#d9c8b3] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-gray-700 transition-colors hover:border-[#c8b090] hover:text-gray-900"
                            >
                              {selectedRepos.size === repositories.length ? 'Deselect All' : 'Select All'}
                            </button>
                          )}
                        </div>

                        {loadingRepos ? (
                          <div className="flex items-center justify-center rounded-[1.25rem] border border-[#e5d9ca] bg-[#faf7f2] py-10">
                            <LoadingSpinner size="sm" />
                            <span className="ml-3 text-sm text-gray-600">Loading repositories...</span>
                          </div>
                        ) : repositories.length > 0 ? (
                          <div className="max-h-72 overflow-y-auto rounded-[1.35rem] border border-[#e5d9ca] bg-[#faf7f2]">
                            {repositories.map((repo) => (
                              <label
                                key={repo.id}
                                className="flex cursor-pointer items-start gap-3 border-b border-[#ebe1d5] px-4 py-3.5 transition-colors hover:bg-white last:border-b-0"
                              >
                                <input
                                  type="checkbox"
                                  checked={selectedRepos.has(repo.full_name)}
                                  onChange={() => toggleRepository(repo.full_name)}
                                  className="mt-1 h-4 w-4 rounded border-gray-300 text-gray-950 focus:ring-red-500"
                                />
                                <div className="min-w-0 flex-1">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="font-semibold text-gray-900">{repo.full_name}</span>
                                    {repo.private && (
                                      <span className="inline-flex items-center rounded-full bg-[#f6ead8] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#8d5d16]">
                                        Private
                                      </span>
                                    )}
                                    {repo.has_wiki && (
                                      <span className="inline-flex items-center rounded-full bg-[#e7f0ff] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#335e9f]">
                                        Wiki
                                      </span>
                                    )}
                                  </div>
                                  {repo.description && (
                                    <p className="mt-1 truncate text-sm text-gray-600">{repo.description}</p>
                                  )}
                                  <p className="mt-1 text-xs text-gray-400">
                                    Updated: {new Date(repo.updated_at).toLocaleDateString()}
                                  </p>
                                </div>
                              </label>
                            ))}
                          </div>
                        ) : (
                          <div className="rounded-[1.25rem] border border-[#e5d9ca] bg-[#faf7f2] px-5 py-8 text-center text-sm text-gray-500">
                            No repositories found for this account.
                          </div>
                        )}

                        <p className={helpClass}>
                          {selectedRepos.size > 0
                            ? `${selectedRepos.size} repositor${selectedRepos.size === 1 ? 'y' : 'ies'} selected`
                            : 'Select repositories to sync, or leave empty to sync all accessible repositories'}
                        </p>
                      </div>
                    )}

                    <div className="grid gap-5 md:grid-cols-[minmax(0,280px)_1fr]">
                      <div>
                        <label className={labelClass}>Sync Frequency (seconds)</label>
                        <input
                          type="number"
                          value={githubConfig.sync_frequency}
                          onChange={(e) => setGithubConfig({ ...githubConfig, sync_frequency: parseInt(e.target.value) })}
                          className={fieldClass}
                          min="60"
                        />
                        <p className={helpClass}>How often to check for new content. Minimum 60 seconds.</p>
                      </div>

                      <div>
                        <label className={labelClass}>Content to Sync</label>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <label className="flex items-center gap-3 rounded-[1.1rem] border border-[#ebe1d5] bg-[#faf7f2] px-4 py-3">
                            <input
                              type="checkbox"
                              checked={githubConfig.include_issues}
                              onChange={(e) => setGithubConfig({ ...githubConfig, include_issues: e.target.checked })}
                              className="h-4 w-4 rounded border-gray-300 text-gray-950 focus:ring-red-500"
                            />
                            <span className="text-sm font-semibold text-gray-800">Include Issues</span>
                          </label>

                          <label className="flex items-center gap-3 rounded-[1.1rem] border border-[#ebe1d5] bg-[#faf7f2] px-4 py-3">
                            <input
                              type="checkbox"
                              checked={githubConfig.include_pull_requests}
                              onChange={(e) => setGithubConfig({ ...githubConfig, include_pull_requests: e.target.checked })}
                              className="h-4 w-4 rounded border-gray-300 text-gray-950 focus:ring-red-500"
                            />
                            <span className="text-sm font-semibold text-gray-800">Include Pull Requests</span>
                          </label>

                          <label className="flex items-center gap-3 rounded-[1.1rem] border border-[#ebe1d5] bg-[#faf7f2] px-4 py-3">
                            <input
                              type="checkbox"
                              checked={githubConfig.include_discussions}
                              onChange={(e) => setGithubConfig({ ...githubConfig, include_discussions: e.target.checked })}
                              className="h-4 w-4 rounded border-gray-300 text-gray-950 focus:ring-red-500"
                            />
                            <span className="text-sm font-semibold text-gray-800">Include Discussions</span>
                          </label>

                          <label className="flex items-center gap-3 rounded-[1.1rem] border border-[#ebe1d5] bg-[#faf7f2] px-4 py-3">
                            <input
                              type="checkbox"
                              checked={githubConfig.create_wiki}
                              onChange={(e) => setGithubConfig({ ...githubConfig, create_wiki: e.target.checked })}
                              className="h-4 w-4 rounded border-gray-300 text-gray-950 focus:ring-red-500"
                            />
                            <span className="text-sm font-semibold text-gray-800">Create Repository Wiki</span>
                          </label>
                        </div>
                        <p className={helpClass}>
                          When enabled, a wiki will be created for each repository to document its structure and purpose.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {selectedType === 'NOTION' && (
                  <div className="rounded-[1.5rem] border border-[#ebe1d5] bg-white/70 p-5 md:p-6">
                    <div className="mb-5">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Notion Settings</p>
                      <h3 className="mt-2 text-lg font-semibold text-gray-950">Internal integration token</h3>
                    </div>

                    <div className="grid gap-5 md:grid-cols-2">
                      <div>
                        <label className={labelClass}>
                          Internal Integration Token <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="password"
                          value={notionConfig.internal_token}
                          onChange={(e) => setNotionConfig({ ...notionConfig, internal_token: e.target.value })}
                          className={fieldClass}
                          placeholder="secret_..."
                          required
                        />
                        <p className={helpClass}>
                          Create an internal integration at notion.so/my-integrations, share the pages/databases with
                          it, then paste the token here.
                        </p>
                      </div>

                      <div>
                        <label className={labelClass}>Sync Frequency (seconds)</label>
                        <input
                          type="number"
                          value={notionConfig.sync_frequency}
                          onChange={(e) => setNotionConfig({ ...notionConfig, sync_frequency: parseInt(e.target.value) })}
                          className={fieldClass}
                          min="60"
                        />
                        <p className={helpClass}>How often to check for new content. Minimum 60 seconds.</p>
                      </div>
                    </div>
                  </div>
                )}

                {selectedType === 'CONFLUENCE' && (
                  <div className="rounded-[1.5rem] border border-[#ebe1d5] bg-white/70 p-5 md:p-6">
                    <div className="mb-5">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Confluence Settings</p>
                      <h3 className="mt-2 text-lg font-semibold text-gray-950">Authenticate with a PAT or API token</h3>
                    </div>

                    <div className="grid gap-5 md:grid-cols-2">
                      <div>
                        <label className={labelClass}>Personal Access Token</label>
                        <input
                          type="password"
                          value={confluenceConfig.pat}
                          onChange={(e) => setConfluenceConfig({ ...confluenceConfig, pat: e.target.value })}
                          className={fieldClass}
                          placeholder="Confluence Data Center PAT"
                        />
                        <p className={helpClass}>
                          Use this for self-hosted Confluence Data Center, or leave empty and use email + API token
                          for Confluence Cloud instead.
                        </p>
                      </div>

                      <div>
                        <label className={labelClass}>Sync Frequency (seconds)</label>
                        <input
                          type="number"
                          value={confluenceConfig.sync_frequency}
                          onChange={(e) => setConfluenceConfig({ ...confluenceConfig, sync_frequency: parseInt(e.target.value) })}
                          className={fieldClass}
                          min="60"
                        />
                        <p className={helpClass}>How often to check for new content. Minimum 60 seconds.</p>
                      </div>

                      <div>
                        <label className={labelClass}>Email (Confluence Cloud)</label>
                        <input
                          type="email"
                          value={confluenceConfig.email}
                          onChange={(e) => setConfluenceConfig({ ...confluenceConfig, email: e.target.value })}
                          className={fieldClass}
                          placeholder="you@company.com"
                        />
                      </div>

                      <div>
                        <label className={labelClass}>API Token (Confluence Cloud)</label>
                        <input
                          type="password"
                          value={confluenceConfig.api_token}
                          onChange={(e) => setConfluenceConfig({ ...confluenceConfig, api_token: e.target.value })}
                          className={fieldClass}
                          placeholder="Generated from id.atlassian.com/manage-profile/security/api-tokens"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {selectedType === 'LINEAR' && (
                  <div className="rounded-[1.5rem] border border-[#ebe1d5] bg-white/70 p-5 md:p-6">
                    <div className="mb-5">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Linear Settings</p>
                      <h3 className="mt-2 text-lg font-semibold text-gray-950">Personal API key</h3>
                    </div>

                    <div className="grid gap-5 md:grid-cols-2">
                      <div>
                        <label className={labelClass}>
                          Personal API Key <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="password"
                          value={linearConfig.api_key}
                          onChange={(e) => setLinearConfig({ ...linearConfig, api_key: e.target.value })}
                          className={fieldClass}
                          placeholder="lin_api_..."
                          required
                        />
                        <p className={helpClass}>
                          Generate this from Linear Settings &gt; API &gt; Personal API keys.
                        </p>
                      </div>

                      <div>
                        <label className={labelClass}>Sync Frequency (seconds)</label>
                        <input
                          type="number"
                          value={linearConfig.sync_frequency}
                          onChange={(e) => setLinearConfig({ ...linearConfig, sync_frequency: parseInt(e.target.value) })}
                          className={fieldClass}
                          min="60"
                        />
                        <p className={helpClass}>How often to check for new content. Minimum 60 seconds.</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-[1.6rem] border border-[#d8e5d9] bg-[linear-gradient(180deg,_rgba(244,249,245,0.98),_rgba(235,245,238,0.95))] p-5 shadow-[0_18px_45px_-38px_rgba(37,86,59,0.25)]">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-[#2f6a51]">
                  <CheckCircle className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">Connect Data Source</p>
                  <p className="mt-1 text-sm leading-6 text-gray-600">
                    This will link your {selectedSource?.label || 'data source'} to the selected knowledge base{' '}
                    {isDirectAuth
                      ? 'using the API token provided above'
                      : 'using the authorized OAuth app'}
                    . Syncing will begin using the frequency you configured above.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <Link
                href="/data-sources"
                className="inline-flex items-center justify-center rounded-full border border-[#ddd2c2] bg-white px-5 py-3 text-sm font-semibold text-gray-700 transition-colors hover:border-[#ccb59a] hover:text-gray-900"
              >
                Cancel
              </Link>
              <button
                onClick={handleConnect}
                disabled={loading}
                className="inline-flex min-w-[220px] items-center justify-center rounded-full bg-gray-950 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <LoadingSpinner size="sm" />
                    Connecting...
                  </span>
                ) : (
                  'Connect Data Source'
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ConnectDataSourcePage() {
  return (
    <Suspense fallback={
      <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
        <div className="mx-auto max-w-5xl">
          <div className="rounded-[1.85rem] border border-[#e7dccd] bg-white px-6 py-14 shadow-[0_24px_60px_-42px_rgba(76,48,23,0.28)]">
            <div className="flex flex-col items-center justify-center text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[#f6ede4]">
                <LoadingSpinner />
              </div>
              <p className="mt-4 text-sm font-medium text-gray-600">Loading data source setup...</p>
            </div>
          </div>
        </div>
      </div>
    }>
      <ConnectDataSourceContent />
    </Suspense>
  )
}
