'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  BookOpen,
  ArrowLeft,
  Settings,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  AlertCircle,
  Loader2,
  Save,
  Bot,
  Hexagon,
  Orbit,
  Palette,
  Search,
  Sparkles,
  TreePine,
  Zap
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

// Provider configurations (kept for advanced options)
const VECTOR_DB_PROVIDERS = [
  {
    value: 'QDRANT',
    label: 'Qdrant',
    description: 'High-performance vector search engine',
    icon: Search,
    fields: ['url', 'collection_name', 'api_key'],
    defaults: { url: 'http://localhost:6333' },
  },
  {
    value: 'PINECONE',
    label: 'Pinecone',
    description: 'Managed vector database',
    icon: TreePine,
    fields: ['api_key', 'environment', 'index_name'],
    defaults: { environment: 'us-east-1-aws' },
  },
  {
    value: 'WEAVIATE',
    label: 'Weaviate',
    description: 'Open-source vector database',
    icon: Hexagon,
    fields: ['url', 'api_key'],
    defaults: { url: 'http://localhost:8080' },
  },
  {
    value: 'CHROMA',
    label: 'Chroma',
    description: 'AI-native embedding database',
    icon: Palette,
    fields: ['url', 'collection_name'],
    defaults: { url: 'http://localhost:8000' },
  },
  {
    value: 'MILVUS',
    label: 'Milvus',
    description: 'Open-source vector database',
    icon: Zap,
    fields: ['url', 'collection_name'],
    defaults: { url: 'http://localhost:19530' },
  },
]

const EMBEDDING_PROVIDERS = [
  {
    value: 'SENTENCE_TRANSFORMERS',
    label: 'Sentence Transformers',
    icon: Bot,
    description: 'Open-source, runs locally',
    models: [
      { value: 'all-MiniLM-L6-v2', label: 'all-MiniLM-L6-v2', dimension: 384 },
      { value: 'all-mpnet-base-v2', label: 'all-mpnet-base-v2', dimension: 768 },
    ],
  },
  {
    value: 'OPENAI',
    label: 'OpenAI',
    icon: Sparkles,
    description: 'Powerful, requires API key',
    models: [
      { value: 'text-embedding-ada-002', label: 'text-embedding-ada-002', dimension: 1536 },
      { value: 'text-embedding-3-small', label: 'text-embedding-3-small', dimension: 1536 },
    ],
  },
  {
    value: 'COHERE',
    label: 'Cohere',
    icon: Orbit,
    description: 'High-quality embeddings',
    models: [
      { value: 'embed-english-v3.0', label: 'embed-english-v3.0', dimension: 1024 },
      { value: 'embed-multilingual-v3.0', label: 'embed-multilingual-v3.0', dimension: 1024 },
    ],
  },
  {
    value: 'LITELLM',
    label: 'LiteLLM',
    icon: Zap,
    description: 'Universal API - supports 100+ providers',
    models: [
      { value: 'openai/text-embedding-ada-002', label: 'OpenAI - text-embedding-ada-002', dimension: 1536 },
      { value: 'openai/text-embedding-3-small', label: 'OpenAI - text-embedding-3-small', dimension: 1536 },
      { value: 'openai/text-embedding-3-large', label: 'OpenAI - text-embedding-3-large', dimension: 3072 },
      { value: 'cohere/embed-english-v3.0', label: 'Cohere - embed-english-v3.0', dimension: 1024 },
      { value: 'cohere/embed-multilingual-v3.0', label: 'Cohere - embed-multilingual-v3.0', dimension: 1024 },
    ],
  },
]

const CHUNKING_STRATEGIES = [
  { value: 'SEMANTIC', label: 'Automatic (Recommended)', description: 'Best for most documents' },
  { value: 'DOCUMENT', label: 'Document-aware', description: 'Keeps sections together' },
  { value: 'CODE', label: 'Code-optimized', description: 'Best for source code' },
  { value: 'FIXED', label: 'Fixed size', description: 'Traditional chunking' },
]

export default function EditKnowledgeBasePage() {
  const router = useRouter()
  const params = useParams()
  const id = params.id as string

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState(1)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    vector_db_provider: 'QDRANT',
    vector_db_config: {} as Record<string, string>,
    embedding_config: {
      provider: 'SENTENCE_TRANSFORMERS',
      model_name: 'all-MiniLM-L6-v2',
      dimension: 384,
      api_key: '',
      api_base: '',
    },
    chunking_strategy: 'SEMANTIC',
    chunk_size: 1500,
    chunk_overlap: 150,
    min_chunk_size: 500,
    max_chunk_size: 3000,
    chunking_config: {} as Record<string, any>,
  })

  const selectedVectorDB = VECTOR_DB_PROVIDERS.find(p => p.value === formData.vector_db_provider)
  const selectedEmbedding = EMBEDDING_PROVIDERS.find(p => p.value === formData.embedding_config.provider)
  const fieldClass = 'w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink'
  const compactFieldClass = 'w-full rounded-[1rem] border border-line bg-cream px-4 py-3 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink'
  const textareaClass = `${fieldClass} resize-none`
  const labelClass = 'mb-2 block text-sm font-semibold text-ink-soft'
  const compactLabelClass = 'mb-1.5 block text-sm font-semibold text-ink-soft'
  const helpClass = 'mt-2 text-xs leading-relaxed text-ink-mute'

  useEffect(() => {
    fetchKnowledgeBase()
  }, [id])

  const fetchKnowledgeBase = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getKnowledgeBase(id)
      setFormData({
        name: data.name || '',
        description: data.description || '',
        vector_db_provider: data.vector_db_provider || 'QDRANT',
        vector_db_config: data.vector_db_config || {},
        embedding_config: {
          provider: data.embedding_provider || 'SENTENCE_TRANSFORMERS',
          model_name: data.embedding_model || 'all-MiniLM-L6-v2',
          dimension: data.embedding_config?.dimension || 384,
          api_key: '',
          api_base: data.embedding_config?.api_base || '',
        },
        chunking_strategy: data.chunking_strategy || 'SEMANTIC',
        chunk_size: data.chunk_size || 1500,
        chunk_overlap: data.chunk_overlap || 150,
        min_chunk_size: data.min_chunk_size || 500,
        max_chunk_size: data.max_chunk_size || 3000,
        chunking_config: data.chunking_config || {},
      })
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
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
      }

      await apiClient.updateKnowledgeBase(id, payload)
      toast.success('Knowledge base updated successfully!')
      router.push(`/knowledge-bases/${id}`)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred'
      setError(errorMessage)
      toast.error(`Failed to update: ${errorMessage}`)
    } finally {
      setSaving(false)
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
    if (provider !== formData.vector_db_provider) {
      setFormData(prev => ({
        ...prev,
        vector_db_provider: provider,
        vector_db_config: selected?.defaults || {},
      }))
    }
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
    { num: 1, label: 'Edit', description: 'Update details' },
    { num: 2, label: 'Review', description: 'Save changes' },
  ]

  if (loading) {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center p-6">
        <div className="rounded-[2rem] border border-black/10 bg-white/85 px-8 py-10 text-center shadow-soft">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-sand">
            <Loader2 className="h-5 w-5 motion-safe:animate-spin text-ink" />
          </div>
          <p className="text-sm font-semibold text-ink">Loading knowledge base…</p>
          <p className="mt-1 text-sm text-ink-mute">Preparing your existing configuration.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-8">
          <Link
            href={`/knowledge-bases/${id}`}
            className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-ink-soft transition-colors hover:text-ink"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Knowledge Base
          </Link>

          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-ink md:text-3xl">
                Edit Knowledge Base
              </h1>
              <p className="mt-2 max-w-2xl text-ink-soft">
                Update the settings and processing details for your existing knowledge base.
              </p>
            </div>
            <div className="rounded-full border border-black/10 bg-white/65 px-4 py-2 text-sm font-medium text-ink-mute">
              Step {currentStep} of {steps.length}
            </div>
          </div>
        </div>

        <div className="mb-8">
          <div className="flex items-center gap-3 rounded-[1.75rem] border border-black/10 bg-white/70 p-4 shadow-soft">
            {steps.map((step, idx) => (
              <div key={step.num} className="flex flex-1 items-center">
                <div className="flex flex-1 items-center gap-3">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-full font-semibold transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                      currentStep >= step.num
                        ? 'bg-ink text-white'
                        : 'bg-sand-deep text-ash'
                    }`}
                  >
                    {currentStep > step.num ? (
                      <CheckCircle className="h-5 w-5" />
                    ) : (
                      step.num
                    )}
                  </div>
                  <div className="hidden sm:block">
                    <p className={`text-sm font-semibold ${currentStep >= step.num ? 'text-ink' : 'text-ink-mute'}`}>
                      {step.label}
                    </p>
                    <p className="text-xs text-ink-mute">{step.description}</p>
                  </div>
                </div>
                {idx < steps.length - 1 && (
                  <div className={`mx-4 h-1 flex-1 rounded-full ${currentStep > step.num ? 'bg-ink' : 'bg-line'}`} />
                )}
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-[1.35rem] border border-blush bg-blush-wash/90 p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-danger" />
              <p className="text-danger">{error}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {currentStep === 1 && (
            <div className="rounded-[2rem] border border-black/10 bg-white/78 p-6 shadow-soft sm:p-8">
              <div className="mb-6 flex items-center gap-3">
                <div className="rounded-[1rem] bg-sand p-3">
                  <BookOpen className="h-5 w-5 text-ink" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-ink">Basic Information</h2>
                  <p className="text-sm text-ink-mute">Update the name and description your team sees first.</p>
                </div>
              </div>

              <div className="space-y-5">
                <div>
                  <label className={labelClass}>
                    Name <span className="text-leaf">*</span>
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
                    Description <span className="text-ash">(optional)</span>
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                    rows={3}
                    className={textareaClass}
                    placeholder="Briefly describe what kind of information is stored here…"
                  />
                </div>
              </div>

              <div className="mt-8 flex justify-end">
                <button
                  type="button"
                  onClick={() => setCurrentStep(2)}
                  disabled={!formData.name}
                  className="rounded-[1.15rem] bg-ink px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Continue
                </button>
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div className="space-y-6">
              <div className="rounded-[2rem] border border-black/10 bg-white/78 p-6 shadow-soft sm:p-8">
                <div className="mb-6 flex items-center gap-3">
                  <div className="rounded-[1rem] bg-leaf-wash p-3">
                    <CheckCircle className="h-5 w-5 text-leaf" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-ink">Review Changes</h2>
                    <p className="text-sm text-ink-mute">Confirm your updates before saving.</p>
                  </div>
                </div>

                <div className="mb-6 rounded-[1.5rem] border border-black/10 bg-paper p-5">
                  <div className="flex items-start gap-4">
                    <div className="rounded-[1.15rem] bg-white p-3 shadow-soft">
                      <BookOpen className="h-8 w-8 text-ink" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-ink">{formData.name}</h3>
                      <p className="mt-1 text-ink-soft">
                        {formData.description || 'No description provided'}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className="inline-flex items-center rounded-full bg-ink px-2.5 py-1 text-xs font-medium text-white">
                          {formData.vector_db_provider}
                        </span>
                        <span className="inline-flex items-center rounded-full bg-leaf-wash px-2.5 py-1 text-xs font-medium text-leaf">
                          {formData.embedding_config.model_name}
                        </span>
                        <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 text-xs font-medium text-ink-mute shadow-soft">
                          Ready to save
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="border-t border-black/10 pt-5">
                  <h4 className="mb-3 font-medium text-ink">Changes overview</h4>
                  <div className="space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-sand-deep">
                        <span className="text-xs font-semibold text-ink">1</span>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-ink">Basic details</p>
                        <p className="text-sm text-ink-mute">Name and description are updated without changing your existing content.</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-sand-deep">
                        <span className="text-xs font-semibold text-ink">2</span>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-ink">Advanced configuration</p>
                        <p className="text-sm text-ink-mute">Review vector storage, embedding model, and chunking only if you need to adjust them.</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-sand-deep">
                        <span className="text-xs font-semibold text-ink">3</span>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-ink">Save changes</p>
                        <p className="text-sm text-ink-mute">Apply your updates and return to the knowledge base detail page.</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="overflow-hidden rounded-[2rem] border border-black/10 bg-white/78 shadow-soft">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex w-full items-center justify-between px-6 py-5 transition-colors hover:bg-cream"
                >
                  <div className="flex items-center gap-3">
                    <div className="rounded-[0.95rem] bg-sand p-2.5">
                      <Settings className="h-5 w-5 text-ink" />
                    </div>
                    <div className="text-left">
                      <p className="font-semibold text-ink">Advanced Settings</p>
                      <p className="text-sm text-ink-mute">Configure storage and processing options.</p>
                    </div>
                  </div>
                  {showAdvanced ? (
                    <ChevronUp className="h-5 w-5 text-ash" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-ash" />
                  )}
                </button>

                {showAdvanced && (
                  <div className="border-t border-black/10 px-6 pb-6">
                    <div className="border-b border-black/10 py-5">
                      <h3 className="mb-4 font-semibold text-ink">Vector Database</h3>
                      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                        {VECTOR_DB_PROVIDERS.map((provider) => (
                          <button
                            key={provider.value}
                            type="button"
                            onClick={() => handleProviderChange(provider.value)}
                            className={`rounded-[1.1rem] border p-3 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                              formData.vector_db_provider === provider.value
                                ? 'border-black/10 bg-paper shadow-soft'
                                : 'border-black/10 bg-white hover:bg-cream'
                            }`}
                          >
                            <provider.icon className="mb-1 h-5 w-5" aria-hidden="true" />
                            <div className="text-sm font-medium text-ink">{provider.label}</div>
                          </button>
                        ))}
                      </div>

                      {selectedVectorDB && (
                        <div className="mt-4 space-y-3">
                          {selectedVectorDB.fields.includes('url') && (
                            <div>
                              <label className={compactLabelClass}>Database URL</label>
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
                                API Key {selectedVectorDB.value === 'PINECONE' && <span className="text-leaf">*</span>}
                              </label>
                              <input
                                type="password"
                                value={formData.vector_db_config.api_key || ''}
                                onChange={(e) => updateVectorDBConfig('api_key', e.target.value)}
                                className={compactFieldClass}
                                placeholder="Enter API key (leave blank to keep existing)"
                              />
                            </div>
                          )}
                          {selectedVectorDB.fields.includes('environment') && (
                            <div>
                              <label className={compactLabelClass}>Environment</label>
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
                              <label className={compactLabelClass}>Collection Name</label>
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
                              <label className={compactLabelClass}>Index Name</label>
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

                    <div className="border-b border-black/10 py-5">
                      <h3 className="mb-4 font-semibold text-ink">Embedding Model</h3>
                      <div className="mb-4 grid grid-cols-2 gap-3">
                        {EMBEDDING_PROVIDERS.map((provider) => (
                          <button
                            key={provider.value}
                            type="button"
                            onClick={() => handleEmbeddingProviderChange(provider.value)}
                            className={`rounded-[1.1rem] border p-3 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                              formData.embedding_config.provider === provider.value
                                ? 'border-black/10 bg-paper shadow-soft'
                                : 'border-black/10 bg-white hover:bg-cream'
                            }`}
                          >
                            <provider.icon className="mb-1 h-5 w-5" aria-hidden="true" />
                            <div className="text-sm font-medium text-ink">{provider.label}</div>
                            <div className="text-xs text-ink-mute">{provider.description}</div>
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
                              <label className={compactLabelClass}>API Key</label>
                              <input
                                type="password"
                                value={formData.embedding_config.api_key}
                                onChange={(e) => updateEmbeddingConfig('api_key', e.target.value)}
                                className={compactFieldClass}
                                placeholder="Enter API key (leave blank to keep existing)"
                              />
                            </div>
                          )}

                          {formData.embedding_config.provider === 'LITELLM' && (
                            <div>
                              <label className={compactLabelClass}>Custom Base URL (Optional)</label>
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

                    <div className="pt-5">
                      <h3 className="mb-4 font-semibold text-ink">Text Processing</h3>
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

                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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

              <div className="flex justify-between">
                <button
                  type="button"
                  onClick={() => setCurrentStep(1)}
                  className="rounded-[1.15rem] border border-black/10 bg-sand-deep px-6 py-3 text-sm font-semibold text-ink transition-colors hover:bg-line"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-2 rounded-[1.15rem] bg-ink px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving ? (
                    <>
                      <Loader2 className="h-5 w-5 motion-safe:animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-5 w-5" />
                      Save Changes
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
