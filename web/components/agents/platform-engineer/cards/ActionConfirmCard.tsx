'use client'

import { Loader2, X, Check, Wrench, KeyRound, Sparkles } from 'lucide-react'

export interface AgentCreateConfig {
  name: string
  description: string
  system_prompt: string
  llm_provider?: string
  llm_model?: string
  image_llm_provider?: string
  image_llm_model?: string
  tools_list?: string[]
  category?: string
  tags?: string[]
}

export type ActionCardStatus = 'pending' | 'creating' | 'created' | 'cancelled'

interface Props {
  config: AgentCreateConfig
  status: ActionCardStatus
  onConfirm: (config: AgentCreateConfig) => void
  onCancel: () => void
}

export function ActionConfirmCard({ config, status, onConfirm, onCancel }: Props) {
  const modelSummary = config.llm_model
    ? [config.llm_provider, config.llm_model].filter(Boolean).join(' / ')
    : 'Inherited from Platform Engineer config'
  const imageModelSummary = config.image_llm_model
    ? [config.image_llm_provider, config.image_llm_model].filter(Boolean).join(' / ')
    : (config.tools_list?.includes('image_generation') ? 'OpenAI / gpt-image-2' : null)

  const detailItems = [
    { label: 'Category', value: config.category || 'Custom agent' },
    { label: 'Model', value: modelSummary },
    { label: 'Tools', value: config.tools_list?.length ? `${config.tools_list.length} enabled` : 'No tools selected' },
    ...(imageModelSummary ? [{ label: 'Image Model', value: imageModelSummary }] : []),
  ]

  if (status === 'cancelled') {
    return (
      <p className="text-sm italic text-[#9a8f84]">Agent creation cancelled.</p>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-[1.9rem] border border-[#d9ccb9] bg-[linear-gradient(180deg,_rgba(251,247,240,0.98),_rgba(243,236,225,0.96))] p-5 shadow-[0_28px_70px_-42px_rgba(42,28,15,0.34)]">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-[radial-gradient(circle_at_top_left,_rgba(125,229,193,0.24),_transparent_62%)]" />
      <div className="pointer-events-none absolute -right-10 top-8 h-28 w-28 rounded-full bg-[#171717]/[0.035] blur-3xl" />

      <div className="relative space-y-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-3">
            <span className="inline-flex w-fit items-center gap-2 rounded-full border border-[#d7cab9] bg-white/85 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em] text-[#695f54]">
              <Sparkles className="h-3.5 w-3.5 text-[#2d8b69]" />
              Ready To Launch
            </span>

            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[1rem] bg-[#171717] text-white shadow-[0_18px_34px_-22px_rgba(0,0,0,0.5)]">
                <Wrench className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="text-[1.15rem] font-semibold tracking-[-0.04em] text-[#171717]">
                  Create Agent: {config.name}
                </p>
                <p className="mt-1 text-sm leading-6 text-[#5b564e]">
                  {config.description || 'This agent is ready to be created with the current platform engineer setup.'}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-[1.1rem] border border-[#d7cab9] bg-white/80 px-3 py-2 text-right shadow-[0_16px_34px_-30px_rgba(42,28,15,0.34)]">
            <div className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#8a8378]">Status</div>
            <div className="mt-1 text-sm font-semibold text-[#171717]">
              {status === 'creating' ? 'Provisioning agent' : 'Awaiting confirmation'}
            </div>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {detailItems.map((item) => (
            <div
              key={item.label}
              className="rounded-[1.2rem] border border-[#ddd1c2] bg-white/78 px-4 py-3 shadow-[0_18px_38px_-32px_rgba(42,28,15,0.34)]"
            >
              <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#8a8378]">
                {item.label}
              </div>
              <div className="mt-2 text-sm font-semibold leading-6 text-[#171717]">
                {item.value}
              </div>
            </div>
          ))}
        </div>

        {config.tools_list && config.tools_list.length > 0 && (
          <div>
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.24em] text-[#8a8378]">
              Tool Access
            </div>
            <div className="flex flex-wrap gap-2">
              {config.tools_list.map((tool) => (
                <span
                  key={tool}
                  className="rounded-full border border-[#d8ccbc] bg-white/92 px-3 py-1.5 text-xs font-medium text-[#3f3a34] shadow-[0_14px_28px_-24px_rgba(42,28,15,0.3)]"
                >
                  {tool}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 rounded-[1.15rem] border border-[#d8ccbc] bg-[#fffaf3]/90 px-4 py-3 text-xs text-[#5b564e]">
          <KeyRound className="h-3.5 w-3.5 shrink-0 text-[#2d8b69]" />
          <span>API key inherited from your Platform Engineer configuration</span>
        </div>
      </div>

      {status === 'pending' && (
        <div className="relative mt-5 flex flex-col gap-3 sm:flex-row">
          <button
            onClick={() => onConfirm(config)}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-[1.15rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-[#faf5ea] transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#0f0f0f] shadow-[0_22px_44px_-28px_rgba(0,0,0,0.52)]"
          >
            <Check className="h-4 w-4" />
            Confirm &amp; Create
          </button>
          <button
            onClick={onCancel}
            className="inline-flex items-center justify-center gap-2 rounded-[1.15rem] border border-[#d7cab9] bg-white/88 px-4 py-3 text-sm font-semibold text-[#3f3a34] transition-all duration-200 hover:-translate-y-0.5 hover:bg-white"
          >
            <X className="h-4 w-4" />
            Cancel
          </button>
        </div>
      )}

      {status === 'creating' && (
        <div className="relative mt-5 rounded-[1.25rem] border border-[#d8ccbc] bg-white/86 p-4 shadow-[0_16px_34px_-30px_rgba(42,28,15,0.3)]">
          <div className="flex items-center gap-2 text-sm font-medium text-[#171717]">
            <Loader2 className="h-4 w-4 animate-spin text-[#2d8b69]" />
            Creating agent...
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#ebe1d3]">
            <div className="h-full w-2/3 animate-pulse rounded-full bg-[linear-gradient(90deg,#171717,#2d8b69)]" />
          </div>
        </div>
      )}
    </div>
  )
}
