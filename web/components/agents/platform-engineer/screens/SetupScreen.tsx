'use client'

import { useState, useEffect } from 'react'
import { Wrench } from 'lucide-react'
import toast from 'react-hot-toast'
import LLMConfigForm from '@/components/agents/llm-configs/LLMConfigForm'
import { getPlatformAgentLLMConfig, upsertPlatformAgentLLMConfig } from '@/lib/api/platformEngineerApi'
import type { AgentLLMConfig, AgentLLMConfigCreate, AgentLLMConfigUpdate } from '@/types/agent-llm-config'
import type { PlatformAgentLLMConfigUpsert } from '@/lib/api/platformEngineerApi'

interface Props {
  onConfigured: () => void
}

export function SetupScreen({ onConfigured }: Props) {
  const [existingConfig, setExistingConfig] = useState<AgentLLMConfig | undefined>(undefined)
  const [loading, setLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const cfg = await getPlatformAgentLLMConfig()
        if (cfg) setExistingConfig(cfg)
      } catch {
        // no config yet — create mode
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleSubmit = async (data: AgentLLMConfigCreate | AgentLLMConfigUpdate) => {
    setIsSubmitting(true)
    try {
      // Build upsert payload — omit api_key when blank (keep existing key on update)
      const payload: PlatformAgentLLMConfigUpsert = {
        name: (data as AgentLLMConfigCreate).name,
        provider: (data as AgentLLMConfigCreate).provider,
        model_name: (data as AgentLLMConfigCreate).model_name,
        api_base: data.api_base ?? undefined,
        temperature: data.temperature ?? undefined,
        max_tokens: data.max_tokens ?? undefined,
        top_p: data.top_p ?? undefined,
        enabled: data.enabled ?? true,
      }
      const apiKey = (data as AgentLLMConfigCreate).api_key
      if (apiKey && apiKey.trim()) payload.api_key = apiKey.trim()
      await upsertPlatformAgentLLMConfig(payload)
      toast.success(existingConfig ? 'LLM configuration updated' : 'LLM configuration saved')
      onConfigured()
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to save configuration'
      toast.error(detail)
      throw err
    } finally {
      setIsSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="h-8 w-8 motion-safe:animate-spin rounded-full border-b-2 border-ink" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="relative overflow-hidden rounded-[2.2rem] border border-line bg-paper p-6 shadow-soft md:p-8">
        <div className="pointer-events-none absolute inset-0 opacity-[0.17]" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-20 opacity-70" />

        <div className="relative flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-[1.15rem] bg-ink text-white shadow-soft">
              <Wrench className="h-5 w-5" />
            </div>
            <div className="max-w-2xl">
              <p className="text-[11px] font-semibold text-ash">
                Platform Engineer Setup
              </p>
              <h3 className="mt-3 text-[clamp(2rem,4vw,3.25rem)] font-light leading-[0.94] tracking-[-0.065em] text-ink">
                {existingConfig ? (
                  <>
                    <span className="block">Update LLM</span>
                    <span className="editorial-highlight mt-2 inline-block">Configuration</span>
                  </>
                ) : (
                  <>
                    <span className="block">Configure LLM</span>
                    <span className="editorial-highlight mt-2 inline-block">Provider</span>
                  </>
                )}
              </h3>
              <p className="mt-4 max-w-xl text-sm leading-6 text-ink-soft">
                {existingConfig
                  ? 'Update the provider or API key used by the Platform Engineer.'
                  : 'Choose a provider and enter your API key to get started. Your key is encrypted at rest.'}
              </p>
            </div>
          </div>
          <div className="rounded-full border border-black/10 bg-white/72 px-4 py-2 text-[11px] font-semibold text-ink-soft shadow-soft">
            Secure configuration
          </div>
        </div>
      </div>

      <div className="rounded-[2rem] border border-line bg-white p-5 shadow-soft md:p-7">
        <LLMConfigForm
          config={existingConfig}
          onSubmit={handleSubmit}
          onCancel={onConfigured}
          isSubmitting={isSubmitting}
        />
      </div>
    </div>
  )
}
