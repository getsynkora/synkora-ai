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
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#171717]" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="relative overflow-hidden rounded-[2.2rem] border border-[#e0d2c0] bg-[linear-gradient(180deg,_rgba(251,246,238,0.98),_rgba(244,237,227,0.95))] p-6 shadow-[0_28px_70px_-46px_rgba(88,63,39,0.32)] md:p-8">
        <div className="pointer-events-none absolute inset-0 opacity-[0.17] [background-image:repeating-linear-gradient(90deg,transparent_0,transparent_12%,rgba(72,51,34,0.08)_12.2%,transparent_12.5%)]" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-20 bg-[radial-gradient(circle_at_50%_0%,rgba(30,24,20,0.15),transparent_72%)] opacity-70" />

        <div className="relative flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-[1.15rem] bg-[#171717] text-white shadow-[0_24px_48px_-28px_rgba(0,0,0,0.48)]">
              <Wrench className="h-5 w-5" />
            </div>
            <div className="max-w-2xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-[#8b8174]">
                Platform Engineer Setup
              </p>
              <h3 className="mt-3 text-[clamp(2rem,4vw,3.25rem)] font-light leading-[0.94] tracking-[-0.065em] text-gray-950">
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
              <p className="mt-4 max-w-xl text-sm leading-6 text-gray-600">
                {existingConfig
                  ? 'Update the provider or API key used by the Platform Engineer.'
                  : 'Choose a provider and enter your API key to get started. Your key is encrypted at rest.'}
              </p>
            </div>
          </div>
          <div className="rounded-full border border-black/10 bg-white/72 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.28em] text-[#5c544a] shadow-[0_18px_36px_-28px_rgba(28,20,12,0.46)]">
            Secure configuration
          </div>
        </div>
      </div>

      <div className="rounded-[2rem] border border-[#e3d7c7] bg-[linear-gradient(180deg,_rgba(255,255,255,0.82),_rgba(250,245,238,0.92))] p-5 shadow-[0_22px_52px_-40px_rgba(30,22,14,0.46)] backdrop-blur-sm md:p-7">
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
