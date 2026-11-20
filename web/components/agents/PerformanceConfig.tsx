'use client'

import { Lock } from 'lucide-react'

type ExecutionBackend = 'celery' | 'lambda' | 'cloud_run' | 'do_functions'

interface PerformanceConfig {
  rag: {
    enabled: boolean
    min_query_length: number
  }
  context_files: {
    enabled: boolean
    always_include: boolean
    max_size_chars: number
  }
  caching: {
    enabled: boolean
    ttl_seconds: number
  }
}

interface AgenticConfig {
  max_iterations: number
  tool_retry_attempts: number
  parallel_tools: boolean
}

interface PerformanceConfigProps {
  config: PerformanceConfig | null
  setConfig: (config: PerformanceConfig) => void
  agenticConfig?: AgenticConfig
  setAgenticConfig?: (config: AgenticConfig) => void
  executionBackend?: ExecutionBackend
  setExecutionBackend?: (backend: ExecutionBackend) => void
  hasServerlessExecution?: boolean
}

const DEFAULT_CONFIG: PerformanceConfig = {
  rag: {
    enabled: true,
    min_query_length: 15
  },
  context_files: {
    enabled: true,
    always_include: false,
    max_size_chars: 50000
  },
  caching: {
    enabled: true,
    ttl_seconds: 300
  }
}

const DEFAULT_AGENTIC_CONFIG: AgenticConfig = {
  max_iterations: 100,
  tool_retry_attempts: 2,
  parallel_tools: true,
}

export default function PerformanceConfig({
  config,
  setConfig,
  agenticConfig,
  setAgenticConfig,
  executionBackend = 'celery',
  setExecutionBackend,
  hasServerlessExecution = false,
}: PerformanceConfigProps) {
  const currentConfig = config || DEFAULT_CONFIG
  const currentAgenticConfig = agenticConfig || DEFAULT_AGENTIC_CONFIG

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h3 className="text-lg font-semibold text-ink mb-2">
          Performance Optimization
        </h3>
        <p className="text-sm text-ink-soft mb-4">
          Configure performance settings to optimize response times and resource usage for your agent.
        </p>
      </div>

      <div className="bg-sand-deep border border-honey rounded-lg p-4">
        <h4 className="text-sm font-medium text-gold mb-2">Performance Features</h4>
        <ul className="text-sm text-gold space-y-1 list-disc list-inside">
          <li><strong>Redis Caching:</strong> Cache agent configuration for faster loading</li>
          <li><strong>Parallel Loading:</strong> Load resources (KBs, tools) in parallel</li>
          <li><strong>Smart RAG:</strong> Skip RAG queries for simple questions</li>
          <li><strong>Skills:</strong> Control when skills are included</li>
        </ul>
      </div>

      {/* Execution Backend */}
      {setExecutionBackend && (
        <div className="bg-white border border-line rounded-lg p-5">
          <div className="mb-4">
            <h4 className="text-base font-semibold text-ink">Execution Backend</h4>
            <p className="text-sm text-ink-soft mt-1">
              Choose where scheduled agent tasks run. Credentials are configured by the platform operator via environment variables.
            </p>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-ink-soft mb-2">Backend</label>
            <select
              value={executionBackend}
              onChange={(e) => {
                const val = e.target.value as ExecutionBackend
                if (val !== 'celery' && !hasServerlessExecution) return
                setExecutionBackend(val)
              }}
              className="w-full border border-taupe rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-honey focus:border-transparent"
            >
              <option value="celery">Celery Workers (Default)</option>
              <option value="do_functions" disabled={!hasServerlessExecution}>
                DigitalOcean Functions (native, &lt;15 min){!hasServerlessExecution ? ', Professional+ required' : ''}
              </option>
              <option value="lambda" disabled={!hasServerlessExecution}>
                AWS Lambda (&lt;15 min){!hasServerlessExecution ? ', Professional+ required' : ''}
              </option>
              <option value="cloud_run" disabled={!hasServerlessExecution}>
                Google Cloud Run (all task types, no time limit){!hasServerlessExecution ? ', Professional+ required' : ''}
              </option>
            </select>
            {!hasServerlessExecution && (
              <div className="flex items-center gap-2 mt-2 text-sm text-ink-mute">
                <Lock className="w-4 h-4 flex-shrink-0" />
                <span>Serverless execution (Cloud Run, Lambda) is available on Professional and Enterprise plans. <a href="/settings/billing" className="text-warn hover:underline">Upgrade your plan</a> to enable it.</span>
              </div>
            )}
          </div>

          {executionBackend === 'do_functions' && (
            <div className="bg-sky-wash border border-sky-wash rounded-lg p-3">
              <p className="text-sm text-azure">
                DigitalOcean Functions are the native serverless option since your platform runs on DigitalOcean.
                Maximum execution time is 15 minutes, not suitable for <strong>autonomous_agent</strong> tasks.
                Configure via <code className="bg-sky-wash px-1 rounded">DO_API_TOKEN</code> and <code className="bg-sky-wash px-1 rounded">DO_FUNCTIONS_ENDPOINT</code> environment variables.
              </p>
            </div>
          )}

          {executionBackend === 'lambda' && (
            <div className="bg-sand-deep border border-honey rounded-lg p-3">
              <p className="text-sm text-gold">
                AWS Lambda has a 15-minute hard execution limit. Not supported for <strong>autonomous_agent</strong> tasks, use Google Cloud Run instead.
                Platform credentials (ARN, region, keys) must be configured via <code className="bg-sand-deep px-1 rounded">AWS_*</code> environment variables.
              </p>
            </div>
          )}

          {executionBackend === 'cloud_run' && (
            <div className="bg-leaf-wash border border-mint rounded-lg p-3">
              <p className="text-sm text-forest">
                Google Cloud Run Jobs have no execution time limit, recommended for <strong>autonomous_agent</strong> tasks.
                Platform credentials (project, region, service account) must be configured via <code className="bg-leaf-wash px-1 rounded">GCP_*</code> environment variables.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Caching Settings */}
      <div className="bg-white border border-line rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h4 className="text-base font-semibold text-ink">Redis Caching</h4>
            <p className="text-sm text-ink-soft mt-1">
              Cache agent configuration to reduce database queries
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={currentConfig.caching.enabled}
              onChange={(e) => setConfig({
                ...currentConfig,
                caching: { ...currentConfig.caching, enabled: e.target.checked }
              })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-line peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-honey rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-taupe after:border after:rounded-full after:h-5 after:w-5 after:transition-[color,background-color,border-color,box-shadow,opacity,transform] peer-checked:bg-warn"></div>
          </label>
        </div>

        {currentConfig.caching.enabled && (
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-2">
              Cache TTL: {currentConfig.caching.ttl_seconds} seconds
            </label>
            <input
              type="range"
              min="60"
              max="3600"
              step="60"
              value={currentConfig.caching.ttl_seconds}
              onChange={(e) => setConfig({
                ...currentConfig,
                caching: { ...currentConfig.caching, ttl_seconds: parseInt(e.target.value) }
              })}
              className="w-full h-2 bg-line rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-ink-mute mt-1">
              <span>1 min</span>
              <span>30 min</span>
              <span>1 hour</span>
            </div>
            <p className="text-xs text-ink-soft mt-2">
              How long to cache agent configuration before refreshing from database
            </p>
          </div>
        )}
      </div>

      {/* RAG Settings */}
      <div className="bg-white border border-line rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h4 className="text-base font-semibold text-ink">RAG (Knowledge Base Search)</h4>
            <p className="text-sm text-ink-soft mt-1">
              Control when to search knowledge bases
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={currentConfig.rag.enabled}
              onChange={(e) => setConfig({
                ...currentConfig,
                rag: { ...currentConfig.rag, enabled: e.target.checked }
              })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-line peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-honey rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-taupe after:border after:rounded-full after:h-5 after:w-5 after:transition-[color,background-color,border-color,box-shadow,opacity,transform] peer-checked:bg-warn"></div>
          </label>
        </div>

        {currentConfig.rag.enabled && (
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-2">
              Minimum Query Length: {currentConfig.rag.min_query_length} characters
            </label>
            <input
              type="range"
              min="5"
              max="50"
              step="5"
              value={currentConfig.rag.min_query_length}
              onChange={(e) => setConfig({
                ...currentConfig,
                rag: { ...currentConfig.rag, min_query_length: parseInt(e.target.value) }
              })}
              className="w-full h-2 bg-line rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-ink-mute mt-1">
              <span>5</span>
              <span>25</span>
              <span>50</span>
            </div>
            <p className="text-xs text-ink-soft mt-2">
              Skip RAG search for queries shorter than this (e.g., "hi", "thanks"). Saves time on simple messages.
            </p>
          </div>
        )}

        {!currentConfig.rag.enabled && (
          <div className="bg-sand-deep border border-honey rounded-lg p-3">
            <p className="text-sm text-gold">
              RAG is disabled. Knowledge bases will not be searched during chat.
            </p>
          </div>
        )}
      </div>

      {/* Skills Settings */}
      <div className="bg-white border border-line rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h4 className="text-base font-semibold text-ink">Skills</h4>
            <p className="text-sm text-ink-soft mt-1">
              Control how uploaded context files are included
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={currentConfig.context_files.enabled}
              onChange={(e) => setConfig({
                ...currentConfig,
                context_files: { ...currentConfig.context_files, enabled: e.target.checked }
              })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-line peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-honey rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-taupe after:border after:rounded-full after:h-5 after:w-5 after:transition-[color,background-color,border-color,box-shadow,opacity,transform] peer-checked:bg-warn"></div>
          </label>
        </div>

        {currentConfig.context_files.enabled && (
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-cream rounded-lg">
              <div>
                <label className="text-sm font-medium text-ink">
                  Always Include Files
                </label>
                <p className="text-xs text-ink-soft mt-1">
                  Include context files in every request (slower but more context)
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={currentConfig.context_files.always_include}
                  onChange={(e) => setConfig({
                    ...currentConfig,
                    context_files: { ...currentConfig.context_files, always_include: e.target.checked }
                  })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-line peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-honey rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-taupe after:border after:rounded-full after:h-5 after:w-5 after:transition-[color,background-color,border-color,box-shadow,opacity,transform] peer-checked:bg-warn"></div>
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium text-ink-soft mb-2">
                Max File Size: {(currentConfig.context_files.max_size_chars / 1000).toFixed(0)}K characters
              </label>
              <input
                type="range"
                min="10000"
                max="200000"
                step="10000"
                value={currentConfig.context_files.max_size_chars}
                onChange={(e) => setConfig({
                  ...currentConfig,
                  context_files: { ...currentConfig.context_files, max_size_chars: parseInt(e.target.value) }
                })}
                className="w-full h-2 bg-line rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-ink-mute mt-1">
                <span>10K</span>
                <span>100K</span>
                <span>200K</span>
              </div>
              <p className="text-xs text-ink-soft mt-2">
                Truncate context files larger than this to save tokens and improve response time
              </p>
            </div>
          </div>
        )}

        {!currentConfig.context_files.enabled && (
          <div className="bg-sand-deep border border-honey rounded-lg p-3">
            <p className="text-sm text-gold">
              Context files are disabled. Uploaded files will not be included in the system prompt.
            </p>
          </div>
        )}
      </div>

      {/* Execution Settings */}
      {setAgenticConfig && (
        <div className="bg-white border border-line rounded-lg p-5">
          <div className="mb-4">
            <h4 className="text-base font-semibold text-ink">Execution Limits</h4>
            <p className="text-sm text-ink-soft mt-1">
              Control how the agent's tool-calling loop behaves
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-ink-soft mb-2">
                Max Iterations: {currentAgenticConfig.max_iterations}
              </label>
              <input
                type="range"
                min="10"
                max="200"
                step="10"
                value={currentAgenticConfig.max_iterations}
                onChange={(e) => setAgenticConfig({ ...currentAgenticConfig, max_iterations: parseInt(e.target.value) })}
                className="w-full h-2 bg-line rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-ink-mute mt-1">
                <span>10</span>
                <span>100</span>
                <span>200</span>
              </div>
              <p className="text-xs text-ink-soft mt-2">
                Maximum number of tool-calling iterations per chat request. Lower values stop runaway agents faster; higher values allow more complex multi-step tasks.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-ink-soft mb-2">
                Tool Retry Attempts: {currentAgenticConfig.tool_retry_attempts}
              </label>
              <input
                type="range"
                min="0"
                max="5"
                step="1"
                value={currentAgenticConfig.tool_retry_attempts}
                onChange={(e) => setAgenticConfig({ ...currentAgenticConfig, tool_retry_attempts: parseInt(e.target.value) })}
                className="w-full h-2 bg-line rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-ink-mute mt-1">
                <span>0</span>
                <span>2</span>
                <span>5</span>
              </div>
              <p className="text-xs text-ink-soft mt-2">
                How many times to retry a failed tool call before giving up (with exponential backoff). Does not retry permanent errors like 4xx HTTP responses.
              </p>
            </div>

            <div className="flex items-center justify-between p-3 bg-cream rounded-lg">
              <div>
                <label className="text-sm font-medium text-ink">
                  Parallel Tool Execution
                </label>
                <p className="text-xs text-ink-soft mt-1">
                  Run independent tool calls concurrently for faster responses
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={currentAgenticConfig.parallel_tools}
                  onChange={(e) => setAgenticConfig({ ...currentAgenticConfig, parallel_tools: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-line peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-honey rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-taupe after:border after:rounded-full after:h-5 after:w-5 after:transition-[color,background-color,border-color,box-shadow,opacity,transform] peer-checked:bg-warn"></div>
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Performance Impact Info */}
      <div className="bg-sand-deep border border-honey rounded-lg p-4">
        <h4 className="text-sm font-medium text-gold mb-2">Expected Performance Impact</h4>
        <div className="text-sm text-gold space-y-2">
          <div className="flex justify-between">
            <span>Cache Enabled:</span>
            <span className="font-semibold">90-95% faster loading (14.9s → 0.5s)</span>
          </div>
          <div className="flex justify-between">
            <span>Parallel Loading:</span>
            <span className="font-semibold">60-70% faster resource loading</span>
          </div>
          <div className="flex justify-between">
            <span>Smart RAG (min_query_length):</span>
            <span className="font-semibold">Skip 3-5s for simple queries</span>
          </div>
          <div className="flex justify-between">
            <span>Skills Control:</span>
            <span className="font-semibold">Save tokens and improve speed</span>
          </div>
        </div>
      </div>

      {/* Best Practices */}
      <div className="bg-blush-wash border border-blush rounded-lg p-4">
        <h4 className="text-sm font-medium text-wine mb-2">Best Practices</h4>
        <ul className="text-sm text-wine space-y-1 list-disc list-inside">
          <li><strong>Enable caching</strong> for production agents (huge speed improvement)</li>
          <li><strong>Set min_query_length to 15</strong> to skip RAG for greetings and simple responses</li>
          <li><strong>Disable "always include files"</strong> unless files are critical to every response</li>
          <li><strong>Lower cache TTL (60-120s)</strong> during development for faster config updates</li>
          <li><strong>Higher cache TTL (300-600s)</strong> for stable production agents</li>
        </ul>
      </div>

      {/* Warning about changes */}
      <div className="bg-sand-deep border border-honey rounded-lg p-4">
        <h4 className="text-sm font-medium text-gold mb-2">Important Notes</h4>
        <ul className="text-sm text-gold space-y-1 list-disc list-inside">
          <li>Changes take effect immediately on next chat request</li>
          <li>Cached agent data will be invalidated when you save</li>
          <li>Disabling RAG may reduce answer quality for knowledge-based questions</li>
          <li>Monitor performance metrics in the chat UI to optimize settings</li>
        </ul>
      </div>
    </div>
  )
}
