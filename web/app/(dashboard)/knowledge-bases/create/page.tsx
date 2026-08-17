'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  BookOpen,
  ArrowLeft,
  Upload,
  FileText,
  Globe,
  Plus,
  ChevronDown,
  ChevronUp,
  Settings,
  Sparkles,
  CheckCircle,
  AlertCircle,
  Loader2
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

// Provider configurations (kept for advanced options)
const VECTOR_DB_PROVIDERS = [
  {
    value: 'QDRANT',
    label: 'Qdrant',
    description: 'High-performance vector search engine',
    icon: '🔍',
    fields: ['url', 'collection_name', 'api_key'],
    defaults: { url: 'http://localhost:6333' },
  },
  {
    value: 'PINECONE',
    label: 'Pinecone',
    description: 'Managed vector database',
    icon: '🌲',
    fields: ['api_key', 'environment', 'index_name'],
    defaults: { environment: 'us-east-1-aws' },
  },
  {
    value: 'WEAVIATE',
    label: 'Weaviate',
    description: 'Open-source vector database',
    icon: '🔷',
    fields: ['url', 'api_key'],
    defaults: { url: 'http://localhost:8080' },
  },
  {
    value: 'CHROMA',
    label: 'Chroma',
    description: 'AI-native embedding database',
    icon: '🎨',
    fields: ['url', 'collection_name'],
    defaults: { url: 'http://localhost:8000' },
  },
  {
    value: 'MILVUS',
    label: 'Milvus',
    description: 'Open-source vector database',
    icon: '⚡',
    fields: ['url', 'collection_name'],
    defaults: { url: 'http://localhost:19530' },
  },
]

const EMBEDDING_PROVIDERS = [
  {
    value: 'SENTENCE_TRANSFORMERS',
    label: 'Sentence Transformers',
    icon: '🤖',
    description: 'Open-source, runs locally',
    models: [
      { value: 'all-MiniLM-L6-v2', label: 'all-MiniLM-L6-v2', dimension: 384 },
      { value: 'all-mpnet-base-v2', label: 'all-mpnet-base-v2', dimension: 768 },
    ],
  },
  {
    value: 'OPENAI',
    label: 'OpenAI',
    icon: '🔮',
    description: 'Powerful, requires API key',
    models: [
      { value: 'text-embedding-ada-002', label: 'text-embedding-ada-002', dimension: 1536 },
      { value: 'text-embedding-3-small', label: 'text-embedding-3-small', dimension: 1536 },
    ],
  },
  {
    value: 'COHERE',
    label: 'Cohere',
    icon: '🌐',
    description: 'High-quality embeddings',
    models: [
      { value: 'embed-english-v3.0', label: 'embed-english-v3.0', dimension: 1024 },
      { value: 'embed-multilingual-v3.0', label: 'embed-multilingual-v3.0', dimension: 1024 },
    ],
  },
  {
    value: 'LITELLM',
    label: 'LiteLLM',
    icon: '⚡',
    description: 'Universal API - supports 100+ providers',
    models: [
      { value: 'openai/text-embedding-ada-002', label: 'OpenAI - text-embedding-ada-002', dimension: 1536 },
      { value: 'openai/text-embedding-3-small', label: 'OpenAI - text-embedding-3-small', dimension: 1536 },
      { value: 'openai/text-embedding-3-large', label: 'OpenAI - text-embedding-3-large', dimension: 3072 },
      { value: 'cohere/embed-english-v3.0', label: 'Cohere - embed-english-v3.0', dimension: 1024 },
      { value: 'cohere/embed-multilingual-v3.0', label: 'Cohere - embed-multilingual-v3.0', dimension: 1024 },
      { value: 'voyage/voyage-01', label: 'Voyage AI - voyage-01', dimension: 1024 },
      { value: 'voyage/voyage-02', label: 'Voyage AI - voyage-02', dimension: 1024 },
      { value: 'mistral/mistral-embed', label: 'Mistral AI - mistral-embed', dimension: 1024 },
      { value: 'azure/text-embedding-ada-002', label: 'Azure OpenAI - text-embedding-ada-002', dimension: 1536 },
      { value: 'bedrock/amazon.titan-embed-text-v1', label: 'AWS Bedrock - Titan Embed', dimension: 1536 },
      { value: 'vertex_ai/textembedding-gecko@003', label: 'Google Vertex AI - gecko@003', dimension: 768 },
    ],
  },
]

const CHUNKING_STRATEGIES = [
  { value: 'SEMANTIC', label: 'Automatic (Recommended)', description: 'Best for most documents' },
  { value: 'DOCUMENT', label: 'Document-aware', description: 'Keeps sections together' },
  { value: 'CODE', label: 'Code-optimized', description: 'Best for source code' },
  { value: 'FIXED', label: 'Fixed size', description: 'Traditional chunking' },
]

export default function CreateKnowledgeBasePage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState(1)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Form data with sensible defaults
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    // Default to Qdrant with local defaults
    vector_db_provider: 'QDRANT',
    vector_db_config: { url: 'http://localhost:6333' } as Record<string, string>,
    // Default to Sentence Transformers (no API key needed)
    embedding_config: {
      provider: 'SENTENCE_TRANSFORMERS',
      model_name: 'all-MiniLM-L6-v2',
      dimension: 384,
      api_key: '',
      api_base: '',
    },
    // Default chunking settings
    chunking_strategy: 'SEMANTIC',
    chunk_size: 1500,
    chunk_overlap: 150,
    min_chunk_size: 500,
    max_chunk_size: 3000,
    chunking_config: {} as Record<string, any>,
    ingestion_mode: 'standard',
  })

  const selectedVectorDB = VECTOR_DB_PROVIDERS.find(p => p.value === formData.vector_db_provider)
  const selectedEmbedding = EMBEDDING_PROVIDERS.find(p => p.value === formData.embedding_config.provider)
  const fieldClass = 'w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500'
  const compactFieldClass = 'w-full rounded-[1rem] border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500'
  const textareaClass = `${fieldClass} resize-none`
  const labelClass = 'mb-2 block text-sm font-semibold text-gray-700'
  const compactLabelClass = 'mb-1.5 block text-sm font-semibold text-gray-700'
  const helpClass = 'mt-2 text-xs leading-relaxed text-gray-500'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const payload = {
        name: formData.name,
        description: formData.description,
        vector_db_provider: formData.vector_db_provider,
        vector_db_config: formData.vector_db_config,
        embedding_provider: formData.embedding_config.provider,
        embedding_model: formData.embedding_config.model_name,
        embedding_config: {
          ...(formData.embedding_config.api_key && { api_key: formData.embedding_config.api_key }),
          ...(formData.embedding_config.api_base && { api_base: formData.embedding_config.api_base }),
          dimension: formData.embedding_config.dimension,
        },
        chunking_strategy: formData.chunking_strategy,
        chunk_size: formData.chunk_size,
        chunk_overlap: formData.chunk_overlap,
        min_chunk_size: formData.min_chunk_size,
        max_chunk_size: formData.max_chunk_size,
        chunking_config: formData.chunking_config,
        ingestion_mode: formData.ingestion_mode,
      }

      const data = await apiClient.createKnowledgeBase(payload)
      toast.success('Knowledge base created successfully!')
      router.push(`/knowledge-bases/${data.id}`)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred'
      setError(errorMessage)
      toast.error(`Failed to create knowledge base: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  const updateVectorDBConfig = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      vector_db_config: { ...prev.vector_db_config, [field]: value },
    }))
  }

  const handleProviderChange = (provider: string) => {
    const selected = VECTOR_DB_PROVIDERS.find(p => p.value === provider)
    setFormData(prev => ({
      ...prev,
      vector_db_provider: provider,
      vector_db_config: selected?.defaults || {},
    }))
  }

  const handleEmbeddingProviderChange = (provider: string) => {
    const selected = EMBEDDING_PROVIDERS.find(p => p.value === provider)
    const firstModel = selected?.models[0]
    setFormData(prev => ({
      ...prev,
      embedding_config: {
        provider,
        model_name: firstModel?.value || '',
        dimension: firstModel?.dimension || 384,
        api_key: '',
        api_base: '',
      },
    }))
  }

  const handleModelChange = (modelValue: string) => {
    const model = selectedEmbedding?.models.find(m => m.value === modelValue)
    setFormData(prev => ({
      ...prev,
      embedding_config: {
        ...prev.embedding_config,
        model_name: modelValue,
        dimension: model?.dimension || prev.embedding_config.dimension,
      },
    }))
  }

  const updateEmbeddingConfig = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      embedding_config: { ...prev.embedding_config, [field]: value },
    }))
  }

  const steps = [
    { num: 1, label: 'Name', description: 'Give it a name' },
    { num: 2, label: 'Review', description: 'Review & create' },
  ]

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/knowledge-bases"
            className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-gray-600 transition-colors hover:text-[#171717]"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Knowledge
          </Link>

          <div className="flex items-start justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#6e675d]">
                <BookOpen className="h-3.5 w-3.5 text-[#2d8b69]" />
                Knowledge Base
              </div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Create Knowledge Base</h1>
              <p className="mt-2 text-gray-600">
                Set up a place to store information your AI agents can use
              </p>
            </div>
            <div className="rounded-full border border-black/10 bg-white/65 px-4 py-2 text-sm font-medium text-gray-500">
              Step {currentStep} of {steps.length}
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center gap-3 rounded-[1.75rem] border border-black/10 bg-white/70 p-4 shadow-[0_18px_44px_rgba(0,0,0,0.05)]">
            {steps.map((step, idx) => (
              <div key={step.num} className="flex items-center flex-1">
                <div className="flex items-center gap-3 flex-1">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-full font-semibold transition-all ${
                      currentStep >= step.num
                        ? 'bg-[#171717] text-white'
                        : 'bg-[#ece4d3] text-[#8a8378]'
                    }`}
                  >
                    {currentStep > step.num ? (
                      <CheckCircle className="w-5 h-5" />
                    ) : (
                      step.num
                    )}
                  </div>
                  <div className="hidden sm:block">
                    <p className={`text-sm font-semibold ${currentStep >= step.num ? 'text-gray-900' : 'text-gray-500'}`}>
                      {step.label}
                    </p>
                    <p className="text-xs text-gray-500">{step.description}</p>
                  </div>
                </div>
                {idx < steps.length - 1 && (
                  <div className={`mx-4 h-1 flex-1 rounded-full ${currentStep > step.num ? 'bg-[#171717]' : 'bg-[#e7decb]'}`} />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Form */}
          <div className="lg:col-span-2">
            {/* Error Message */}
            {error && (
              <div className="mb-6 rounded-[1.35rem] border border-red-200 bg-red-50/90 p-4">
                <div className="flex items-center gap-3">
                  <AlertCircle className="w-5 h-5 text-red-600" />
                  <p className="text-red-700">{error}</p>
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit}>
              {/* Step 1: Name and Description */}
              {currentStep === 1 && (
                <div className="rounded-[2rem] border border-black/10 bg-white/78 p-6 shadow-[0_24px_60px_rgba(0,0,0,0.06)] sm:p-8">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="rounded-[1rem] bg-[#f3ecde] p-3">
                      <BookOpen className="h-5 w-5 text-[#171717]" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-gray-900">Name Your Knowledge Base</h2>
                      <p className="text-sm text-gray-500">Choose a name that describes what information it contains</p>
                    </div>
                  </div>

                  <div className="space-y-5">
                    <div>
                      <label className={labelClass}>
                        Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.name}
                        onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                        className={fieldClass}
                        placeholder="e.g., Product Documentation, Support Articles, Company Policies"
                      />
                    </div>

                    <div>
                      <label className={labelClass}>
                        Description <span className="text-gray-400">(optional)</span>
                      </label>
                      <textarea
                        value={formData.description}
                        onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                        rows={3}
                        className={textareaClass}
                        placeholder="Briefly describe what kind of information you'll store here..."
                      />
                    </div>
                  </div>

                  <div className="flex justify-end mt-8">
                    <button
                      type="button"
                      onClick={() => setCurrentStep(2)}
                      disabled={!formData.name}
                      className="rounded-[1.15rem] bg-[#171717] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Continue
                    </button>
                  </div>
                </div>
              )}

              {/* Step 2: Review & Create */}
              {currentStep === 2 && (
                <div className="space-y-6">
                  {/* Summary Card */}
                  <div className="rounded-[2rem] border border-black/10 bg-white/78 p-6 shadow-[0_24px_60px_rgba(0,0,0,0.06)] sm:p-8">
                    <div className="flex items-center gap-3 mb-6">
                      <div className="rounded-[1rem] bg-[#e8f4ee] p-3">
                        <CheckCircle className="h-5 w-5 text-[#2d8b69]" />
                      </div>
                      <div>
                        <h2 className="text-lg font-semibold text-gray-900">Review Your Knowledge Base</h2>
                        <p className="text-sm text-gray-500">Make sure everything looks good before creating</p>
                      </div>
                    </div>

                    {/* Summary */}
                    <div className="mb-6 rounded-[1.5rem] border border-black/10 bg-[#f7f2e7] p-5">
                      <div className="flex items-start gap-4">
                        <div className="rounded-[1.15rem] bg-white p-3 shadow-[0_12px_28px_rgba(0,0,0,0.05)]">
                          <BookOpen className="w-8 h-8 text-[#171717]" />
                        </div>
                        <div className="flex-1">
                          <h3 className="text-lg font-semibold text-gray-900">{formData.name}</h3>
                          <p className="text-gray-600 mt-1">
                            {formData.description || 'No description provided'}
                          </p>
                          <div className="flex flex-wrap gap-2 mt-3">
                            <span className="inline-flex items-center rounded-full bg-[#e8f4ee] px-2.5 py-1 text-xs font-medium text-[#2d8b69]">
                              Ready to add content
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* What happens next */}
                    <div className="border-t border-black/10 pt-5">
                      <h4 className="font-medium text-gray-900 mb-3">What happens next?</h4>
                      <div className="space-y-3">
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#f1eadc]">
                            <span className="text-xs font-semibold text-[#171717]">1</span>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-900">Create knowledge base</p>
                            <p className="text-sm text-gray-500">We'll set up your knowledge base with optimal settings</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#f1eadc]">
                            <span className="text-xs font-semibold text-[#171717]">2</span>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-900">Add your content</p>
                            <p className="text-sm text-gray-500">Upload documents, paste text, or add website URLs</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#f1eadc]">
                            <span className="text-xs font-semibold text-[#171717]">3</span>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-900">Connect to agents</p>
                            <p className="text-sm text-gray-500">Your AI agents will use this knowledge to answer questions</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Advanced Options (Collapsible) */}
                  <div className="overflow-hidden rounded-[2rem] border border-black/10 bg-white/78 shadow-[0_24px_60px_rgba(0,0,0,0.06)]">
                    <button
                      type="button"
                      onClick={() => setShowAdvanced(!showAdvanced)}
                      className="flex w-full items-center justify-between px-6 py-5 transition-colors hover:bg-[#fcfaf5]"
                    >
                      <div className="flex items-center gap-3">
                        <div className="rounded-[0.95rem] bg-[#f3ecde] p-2.5">
                          <Settings className="h-5 w-5 text-[#171717]" />
                        </div>
                        <div className="text-left">
                          <p className="font-semibold text-gray-900">Advanced Settings</p>
                          <p className="text-sm text-gray-500">Configure storage and processing options (optional)</p>
                        </div>
                      </div>
                      {showAdvanced ? (
                        <ChevronUp className="w-5 h-5 text-gray-400" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-gray-400" />
                      )}
                    </button>

                    {showAdvanced && (
                      <div className="border-t border-black/10 px-6 pb-6">
                        {/* Ingestion Mode Section */}
                        <div className="border-b border-black/10 py-5">
                          <h3 className="mb-4 font-semibold text-gray-900">Ingestion Mode</h3>
                          <div className="flex gap-3">
                            <button
                              type="button"
                              onClick={() => setFormData(prev => ({ ...prev, ingestion_mode: 'standard' }))}
                              className={`flex-1 rounded-[1.1rem] border p-3 text-left transition-all ${
                                formData.ingestion_mode === 'standard'
                                  ? 'border-black/10 bg-[#f7f2e7] shadow-[0_12px_28px_rgba(0,0,0,0.04)]'
                                  : 'border-black/10 bg-white hover:bg-[#fcfaf5]'
                              }`}
                            >
                              <div className="font-medium text-sm text-gray-900">Standard</div>
                              <div className="text-xs text-gray-500">Direct document upload and vector search.</div>
                            </button>
                            <button
                              type="button"
                              onClick={() => setFormData(prev => ({ ...prev, ingestion_mode: 'advanced' }))}
                              className={`flex-1 rounded-[1.1rem] border p-3 text-left transition-all ${
                                formData.ingestion_mode === 'advanced'
                                  ? 'border-black/10 bg-[#f7f2e7] shadow-[0_12px_28px_rgba(0,0,0,0.04)]'
                                  : 'border-black/10 bg-white hover:bg-[#fcfaf5]'
                              }`}
                            >
                              <div className="font-medium text-sm text-gray-900">Advanced (Company Brain)</div>
                              <div className="text-xs text-gray-500">
                                Continuous multi-source ingestion with hybrid search and tiered storage.
                              </div>
                            </button>
                          </div>
                        </div>

                        {/* Vector Database Section */}
                        <div className="border-b border-black/10 py-5">
                          <h3 className="mb-4 font-semibold text-gray-900">Vector Database</h3>
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
                            {VECTOR_DB_PROVIDERS.map((provider) => (
                              <button
                                key={provider.value}
                                type="button"
                                onClick={() => handleProviderChange(provider.value)}
                                className={`rounded-[1.1rem] border p-3 text-left transition-all ${
                                  formData.vector_db_provider === provider.value
                                    ? 'border-black/10 bg-[#f7f2e7] shadow-[0_12px_28px_rgba(0,0,0,0.04)]'
                                    : 'border-black/10 bg-white hover:bg-[#fcfaf5]'
                                }`}
                              >
                                <div className="text-xl mb-1">{provider.icon}</div>
                                <div className="font-medium text-sm text-gray-900">{provider.label}</div>
                              </button>
                            ))}
                          </div>

                          {/* Dynamic Vector DB Fields */}
                          {selectedVectorDB && (
                            <div className="space-y-3 mt-4">
                              {selectedVectorDB.fields.includes('url') && (
                                <div>
                                  <label className={compactLabelClass}>
                                    Database URL
                                  </label>
                                  <input
                                    type="text"
                                    value={formData.vector_db_config.url || ''}
                                    onChange={(e) => updateVectorDBConfig('url', e.target.value)}
                                    className={compactFieldClass}
                                    placeholder={selectedVectorDB.defaults?.url || 'http://localhost:6333'}
                                  />
                                </div>
                              )}
                              {selectedVectorDB.fields.includes('api_key') && (
                                <div>
                                  <label className={compactLabelClass}>
                                    API Key {selectedVectorDB.value === 'PINECONE' && <span className="text-red-500">*</span>}
                                  </label>
                                  <input
                                    type="password"
                                    required={selectedVectorDB.value === 'PINECONE'}
                                    value={formData.vector_db_config.api_key || ''}
                                    onChange={(e) => updateVectorDBConfig('api_key', e.target.value)}
                                    className={compactFieldClass}
                                    placeholder="Enter your API key"
                                  />
                                </div>
                              )}
                              {selectedVectorDB.fields.includes('environment') && (
                                <div>
                                  <label className={compactLabelClass}>
                                    Environment
                                  </label>
                                  <input
                                    type="text"
                                    value={formData.vector_db_config.environment || ''}
                                    onChange={(e) => updateVectorDBConfig('environment', e.target.value)}
                                    className={compactFieldClass}
                                    placeholder="e.g., us-east-1-aws"
                                  />
                                </div>
                              )}
                              {selectedVectorDB.fields.includes('collection_name') && (
                                <div>
                                  <label className={compactLabelClass}>
                                    Collection Name
                                  </label>
                                  <input
                                    type="text"
                                    value={formData.vector_db_config.collection_name || ''}
                                    onChange={(e) => updateVectorDBConfig('collection_name', e.target.value)}
                                    className={compactFieldClass}
                                    placeholder="Auto-generated if not provided"
                                  />
                                </div>
                              )}
                              {selectedVectorDB.fields.includes('index_name') && (
                                <div>
                                  <label className={compactLabelClass}>
                                    Index Name
                                  </label>
                                  <input
                                    type="text"
                                    value={formData.vector_db_config.index_name || ''}
                                    onChange={(e) => updateVectorDBConfig('index_name', e.target.value)}
                                    className={compactFieldClass}
                                    placeholder="Enter index name"
                                  />
                                </div>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Embedding Model Section */}
                        <div className="border-b border-black/10 py-5">
                          <h3 className="mb-4 font-semibold text-gray-900">Embedding Model</h3>
                          <div className="grid grid-cols-2 gap-3 mb-4">
                            {EMBEDDING_PROVIDERS.map((provider) => (
                              <button
                                key={provider.value}
                                type="button"
                                onClick={() => handleEmbeddingProviderChange(provider.value)}
                                className={`rounded-[1.1rem] border p-3 text-left transition-all ${
                                  formData.embedding_config.provider === provider.value
                                    ? 'border-black/10 bg-[#f7f2e7] shadow-[0_12px_28px_rgba(0,0,0,0.04)]'
                                    : 'border-black/10 bg-white hover:bg-[#fcfaf5]'
                                }`}
                              >
                                <div className="text-xl mb-1">{provider.icon}</div>
                                <div className="font-medium text-sm text-gray-900">{provider.label}</div>
                                <div className="text-xs text-gray-500">{provider.description}</div>
                              </button>
                            ))}
                          </div>

                          {selectedEmbedding && (
                            <div className="space-y-3">
                              <div>
                                <label className={compactLabelClass}>Model</label>
                                <select
                                  value={formData.embedding_config.model_name}
                                  onChange={(e) => handleModelChange(e.target.value)}
                                  className={compactFieldClass}
                                >
                                  {selectedEmbedding.models.map((model) => (
                                    <option key={model.value} value={model.value}>
                                      {model.label} ({model.dimension}d)
                                    </option>
                                  ))}
                                </select>
                              </div>

                              {(formData.embedding_config.provider === 'OPENAI' ||
                                formData.embedding_config.provider === 'COHERE' ||
                                formData.embedding_config.provider === 'LITELLM') && (
                                <div>
                                  <label className={compactLabelClass}>
                                    API Key <span className="text-red-500">*</span>
                                  </label>
                                  <input
                                    type="password"
                                    required
                                    value={formData.embedding_config.api_key}
                                    onChange={(e) => updateEmbeddingConfig('api_key', e.target.value)}
                                    className={compactFieldClass}
                                    placeholder="Enter your API key"
                                  />
                                </div>
                              )}

                              {formData.embedding_config.provider === 'LITELLM' && (
                                <div>
                                  <label className={compactLabelClass}>
                                    Custom Base URL (Optional)
                                  </label>
                                  <input
                                    type="text"
                                    value={formData.embedding_config.api_base}
                                    onChange={(e) => updateEmbeddingConfig('api_base', e.target.value)}
                                    className={compactFieldClass}
                                    placeholder="e.g., https://api.openai.com/v1"
                                  />
                                </div>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Chunking Settings Section */}
                        <div className="pt-5">
                          <h3 className="mb-4 font-semibold text-gray-900">Text Processing</h3>
                          <div className="space-y-4">
                            <div>
                              <label className={compactLabelClass}>Processing Strategy</label>
                              <select
                                value={formData.chunking_strategy}
                                onChange={(e) => {
                                  const strategy = e.target.value
                                  setFormData(prev => ({
                                    ...prev,
                                    chunking_strategy: strategy,
                                    chunk_size: strategy === 'CODE' ? 2000 : 1500,
                                    chunk_overlap: strategy === 'CODE' ? 300 : 150,
                                  }))
                                }}
                                className={compactFieldClass}
                              >
                                {CHUNKING_STRATEGIES.map((strategy) => (
                                  <option key={strategy.value} value={strategy.value}>
                                    {strategy.label} - {strategy.description}
                                  </option>
                                ))}
                              </select>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <label className={compactLabelClass}>Chunk Size</label>
                                <input
                                  type="number"
                                  min="500"
                                  max="3000"
                                  value={formData.chunk_size}
                                  onChange={(e) => setFormData(prev => ({ ...prev, chunk_size: parseInt(e.target.value) }))}
                                  className={compactFieldClass}
                                />
                                <p className={helpClass}>Characters per chunk (500-3000)</p>
                              </div>
                              <div>
                                <label className={compactLabelClass}>Overlap</label>
                                <input
                                  type="number"
                                  min="0"
                                  max="500"
                                  value={formData.chunk_overlap}
                                  onChange={(e) => setFormData(prev => ({ ...prev, chunk_overlap: parseInt(e.target.value) }))}
                                  className={compactFieldClass}
                                />
                                <p className={helpClass}>Overlap between chunks (0-500)</p>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Navigation Buttons */}
                  <div className="flex justify-between">
                    <button
                      type="button"
                      onClick={() => setCurrentStep(1)}
                      className="rounded-[1.15rem] border border-black/10 bg-[#f1eadc] px-6 py-3 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8]"
                    >
                      Back
                    </button>
                    <button
                      type="submit"
                      disabled={loading}
                      className="flex items-center gap-2 rounded-[1.15rem] bg-[#171717] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="w-5 h-5 animate-spin" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <Plus className="w-5 h-5" />
                          Create Knowledge Base
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </form>
          </div>

          {/* Sidebar - Illustration & Help */}
          <div className="lg:col-span-1">
            <div className="sticky top-6 space-y-6">
              {/* Illustration Card */}
              <div className="rounded-[2rem] border border-black/10 bg-[#171717] p-6 text-center text-[#f7f2e7] shadow-[0_28px_70px_rgba(0,0,0,0.18)]">
                {/* Illustration */}
                <div className="relative w-40 h-40 mx-auto mb-6">
                  {/* Stacked cards effect */}
                  <div className="absolute top-4 left-4 right-4 h-32 rounded-xl bg-white/10 shadow-sm rotate-6"></div>
                  <div className="absolute top-2 left-2 right-2 h-32 rounded-xl bg-white/15 shadow-sm rotate-3"></div>
                  <div className="absolute inset-0 flex flex-col rounded-xl bg-[#f7f2e7] p-4 text-left shadow-md">
                    <div className="mb-2 h-2 w-3/4 rounded bg-[#d8cfc0]"></div>
                    <div className="mb-2 h-2 w-full rounded bg-[#e8ddc8]"></div>
                    <div className="mb-2 h-2 w-5/6 rounded bg-[#e8ddc8]"></div>
                    <div className="mb-2 h-2 w-full rounded bg-[#e8ddc8]"></div>
                    <div className="flex-1"></div>
                    <div className="self-end">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#e8f4ee]">
                        <Sparkles className="h-4 w-4 text-[#2d8b69]" />
                      </div>
                    </div>
                  </div>
                </div>

                <h3 className="mb-2 text-lg font-semibold text-white">
                  Knowledge Base
                </h3>
                <p className="text-sm leading-relaxed text-[#d8d0c3]">
                  Your AI agents will use this knowledge to provide accurate, relevant answers based on your content.
                </p>
              </div>

              {/* Tips Card */}
              <div className="rounded-[1.75rem] border border-black/10 bg-white/78 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
                <h4 className="mb-4 font-semibold text-gray-900">Tips for great results</h4>
                <ul className="space-y-3 text-sm">
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-600">Use a descriptive name that reflects the content</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-600">Keep related documents in the same knowledge base</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-600">Add descriptions to help organize multiple knowledge bases</span>
                  </li>
                </ul>
              </div>

              {/* Content Types Card */}
              <div className="rounded-[1.75rem] border border-black/10 bg-white/78 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
                <h4 className="mb-4 font-semibold text-gray-900">Supported content</h4>
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-[#f3ecde] p-2">
                      <Upload className="w-4 h-4 text-[#171717]" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">Documents</p>
                      <p className="text-xs text-gray-500">PDF, DOCX, TXT, MD, HTML, CSV</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-[#eef7f1] p-2">
                      <FileText className="w-4 h-4 text-[#2d8b69]" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">Text</p>
                      <p className="text-xs text-gray-500">Paste text directly</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-[#f4efe4] p-2">
                      <Globe className="w-4 h-4 text-[#5b564e]" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">Websites</p>
                      <p className="text-xs text-gray-500">Crawl content from URLs</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
