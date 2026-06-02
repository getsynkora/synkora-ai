'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  Server,
  Settings,
  Zap,
  AlertTriangle,
  Save,
  Copy,
  CheckCircle,
} from 'lucide-react'
import { createProxyConfig } from '@/lib/api/load-testing'

export default function CreateProxyConfigPage() {
  const router = useRouter()
  const [saving, setSaving] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  const [createdApiKey, setCreatedApiKey] = useState<string | null>(null)

  // Form state
  const [name, setName] = useState('')
  const [provider, setProvider] = useState('openai')
  const [rateLimit, setRateLimit] = useState(100)

  // Mock config
  const [ttftMin, setTtftMin] = useState(100)
  const [ttftMax, setTtftMax] = useState(500)
  const [interTokenMin, setInterTokenMin] = useState(10)
  const [interTokenMax, setInterTokenMax] = useState(50)
  const [minTokens, setMinTokens] = useState(50)
  const [maxTokens, setMaxTokens] = useState(500)
  const [errorRate, setErrorRate] = useState(0.01)
  const [errorTypes, setErrorTypes] = useState(['rate_limit', 'timeout'])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!name.trim()) {
      toast.error('Please enter a name')
      return
    }

    setSaving(true)
    try {
      const result = await createProxyConfig({
        name: name.trim(),
        provider,
        rate_limit: rateLimit,
        mock_config: {
          latency: {
            ttft_min_ms: ttftMin,
            ttft_max_ms: ttftMax,
            inter_token_min_ms: interTokenMin,
            inter_token_max_ms: interTokenMax,
          },
          response: {
            min_tokens: minTokens,
            max_tokens: maxTokens,
          },
          errors: {
            rate: errorRate,
            types: errorTypes,
          },
        },
      })

      setCreatedApiKey(result.api_key)
      setShowApiKey(true)
      toast.success('Proxy configuration created!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create proxy config')
    } finally {
      setSaving(false)
    }
  }

  const copyApiKey = () => {
    if (createdApiKey) {
      navigator.clipboard.writeText(createdApiKey)
      toast.success('API key copied to clipboard')
    }
  }

  const toggleErrorType = (type: string) => {
    setErrorTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    )
  }

  if (showApiKey && createdApiKey) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-primary-50/30 p-4 md:p-6">
        <div className="max-w-2xl mx-auto">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircle className="w-8 h-8 text-green-600" />
            </div>

            <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight mb-2">Proxy Configuration Created!</h1>
            <p className="text-gray-600 mb-8">
              Save your API key now - it won't be shown again.
            </p>

            <div className="bg-gray-50 rounded-xl p-6 mb-8">
              <label className="block text-sm font-medium text-gray-700 mb-2 text-left">
                Your API Key
              </label>
              <div className="flex items-center gap-2">
                <code className="flex-1 px-4 py-3 bg-white border border-gray-200 rounded-lg font-mono text-sm break-all">
                  {createdApiKey}
                </code>
                <button
                  onClick={copyApiKey}
                  className="p-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
                >
                  <Copy className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-8">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5" />
                <div className="text-left">
                  <h3 className="font-medium text-amber-900">Important</h3>
                  <p className="text-sm text-amber-700 mt-1">
                    Use this API key in your AI agent configuration during load testing.
                    Replace your real LLM API endpoint with the proxy endpoint.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-4 mb-8 text-left">
              <h4 className="font-medium text-gray-900 mb-3">Proxy Endpoints</h4>
              <div className="space-y-2 text-sm">
                {provider === 'openai' && (
                  <div>
                    <span className="text-gray-600">OpenAI:</span>{' '}
                    <code className="bg-white px-2 py-1 rounded border text-xs">
                      {process.env.NEXT_PUBLIC_API_URL}/proxy/v1/chat/completions
                    </code>
                  </div>
                )}
                {provider === 'anthropic' && (
                  <div>
                    <span className="text-gray-600">Anthropic:</span>{' '}
                    <code className="bg-white px-2 py-1 rounded border text-xs">
                      {process.env.NEXT_PUBLIC_API_URL}/proxy/v1/messages
                    </code>
                  </div>
                )}
                {provider === 'google' && (
                  <div>
                    <span className="text-gray-600">Google:</span>{' '}
                    <code className="bg-white px-2 py-1 rounded border text-xs">
                      {process.env.NEXT_PUBLIC_API_URL}/proxy/v1/models/gemini-pro:generateContent
                    </code>
                  </div>
                )}
              </div>
            </div>

            <div className="flex gap-4 justify-center">
              <button
                onClick={() => router.push('/load-testing/proxy')}
                className="px-6 py-2.5 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors font-medium"
              >
                View All Proxies
              </button>
              <button
                onClick={() => {
                  setShowApiKey(false)
                  setCreatedApiKey(null)
                  setName('')
                }}
                className="px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium"
              >
                Create Another
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-primary-50/30 p-4 md:p-6">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/load-testing/proxy"
            className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Proxy Configs
          </Link>
          <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Create Proxy Configuration</h1>
          <p className="text-gray-600 mt-1">
            Configure a mock LLM endpoint for load testing
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Basic Info */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Server className="w-5 h-5 text-primary-600" />
              Basic Configuration
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Configuration Name *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Production Load Test Proxy"
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    LLM Provider
                  </label>
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  >
                    <option value="openai">OpenAI Compatible</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="google">Google</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Rate Limit (RPS)
                  </label>
                  <input
                    type="number"
                    value={rateLimit}
                    onChange={(e) => setRateLimit(parseInt(e.target.value))}
                    min="1"
                    max="10000"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Latency Config */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary-600" />
              Latency Simulation
            </h2>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    TTFT Min (ms)
                  </label>
                  <input
                    type="number"
                    value={ttftMin}
                    onChange={(e) => setTtftMin(parseInt(e.target.value))}
                    min="0"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">Time to First Token minimum</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    TTFT Max (ms)
                  </label>
                  <input
                    type="number"
                    value={ttftMax}
                    onChange={(e) => setTtftMax(parseInt(e.target.value))}
                    min="0"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">Time to First Token maximum</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Inter-Token Delay Min (ms)
                  </label>
                  <input
                    type="number"
                    value={interTokenMin}
                    onChange={(e) => setInterTokenMin(parseInt(e.target.value))}
                    min="0"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Inter-Token Delay Max (ms)
                  </label>
                  <input
                    type="number"
                    value={interTokenMax}
                    onChange={(e) => setInterTokenMax(parseInt(e.target.value))}
                    min="0"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Response Config */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Settings className="w-5 h-5 text-primary-600" />
              Response Configuration
            </h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Min Response Tokens
                </label>
                <input
                  type="number"
                  value={minTokens}
                  onChange={(e) => setMinTokens(parseInt(e.target.value))}
                  min="1"
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Max Response Tokens
                </label>
                <input
                  type="number"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                  min="1"
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* Error Injection */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-primary-600" />
              Error Injection
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Error Rate
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    value={errorRate * 100}
                    onChange={(e) => setErrorRate(parseFloat(e.target.value) / 100)}
                    min="0"
                    max="50"
                    step="0.5"
                    className="flex-1"
                  />
                  <span className="text-sm font-medium text-gray-900 w-16">
                    {(errorRate * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Error Types to Simulate
                </label>
                <div className="flex flex-wrap gap-2">
                  {['rate_limit', 'timeout', 'server_error', 'invalid_request'].map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => toggleErrorType(type)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                        errorTypes.includes(type)
                          ? 'bg-primary-100 text-primary-700'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {type.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Submit */}
          <div className="flex justify-end gap-4">
            <Link
              href="/load-testing/proxy"
              className="px-6 py-2.5 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors font-medium"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Create Proxy
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
