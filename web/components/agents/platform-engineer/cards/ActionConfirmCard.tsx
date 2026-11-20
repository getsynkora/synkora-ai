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
      <p className="text-sm italic text-ash">Agent creation cancelled.</p>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-[1.9rem] border border-line bg-cream p-5 shadow-soft">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-24" />

      <div className="relative space-y-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-3">
            <span className="inline-flex w-fit items-center gap-2 rounded-full border border-paper-dim bg-white/85 px-3 py-1 text-[10px] font-semibold text-ink-soft">
              <Sparkles className="h-3.5 w-3.5 text-leaf" />
              Ready To Launch
            </span>

            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[1rem] bg-ink text-white shadow-soft">
                <Wrench className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="text-[1.15rem] font-semibold tracking-[-0.04em] text-ink">
                  Create Agent: {config.name}
                </p>
                <p className="mt-1 text-sm leading-6 text-ink-soft">
                  {config.description || 'This agent is ready to be created with the current platform engineer setup.'}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-[1.1rem] border border-paper-dim bg-white/80 px-3 py-2 text-right shadow-soft">
            <div className="text-[10px] font-semibold text-ash">Status</div>
            <div className="mt-1 text-sm font-semibold text-ink">
              {status === 'creating' ? 'Provisioning agent' : 'Awaiting confirmation'}
            </div>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {detailItems.map((item) => (
            <div
              key={item.label}
              className="rounded-[1.2rem] border border-line bg-white/78 px-4 py-3 shadow-soft"
            >
              <div className="text-[10px] font-semibold text-ash">
                {item.label}
              </div>
              <div className="mt-2 text-sm font-semibold leading-6 text-ink">
                {item.value}
              </div>
            </div>
          ))}
        </div>

        {config.tools_list && config.tools_list.length > 0 && (
          <div>
            <div className="mb-2 text-[10px] font-semibold text-ash">
              Tool Access
            </div>
            <div className="flex flex-wrap gap-2">
              {config.tools_list.map((tool) => (
                <span
                  key={tool}
                  className="rounded-full border border-paper-dim bg-white/92 px-3 py-1.5 text-xs font-medium text-night shadow-soft"
                >
                  {tool}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 rounded-[1.15rem] border border-paper-dim bg-cream/90 px-4 py-3 text-xs text-ink-soft">
          <KeyRound className="h-3.5 w-3.5 shrink-0 text-leaf" />
          <span>API key inherited from your Platform Engineer configuration</span>
        </div>
      </div>

      {status === 'pending' && (
        <div className="relative mt-5 flex flex-col gap-3 sm:flex-row">
          <button
            onClick={() => onConfirm(config)}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-[1.15rem] bg-ink px-4 py-3 text-sm font-semibold text-paper transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-200 hover:-translate-y-0.5 hover:bg-ink shadow-soft"
          >
            <Check className="h-4 w-4" />
            Confirm &amp; Create
          </button>
          <button
            onClick={onCancel}
            className="inline-flex items-center justify-center gap-2 rounded-[1.15rem] border border-paper-dim bg-white/88 px-4 py-3 text-sm font-semibold text-night transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-200 hover:-translate-y-0.5 hover:bg-white"
          >
            <X className="h-4 w-4" />
            Cancel
          </button>
        </div>
      )}

      {status === 'creating' && (
        <div className="relative mt-5 rounded-[1.25rem] border border-paper-dim bg-white/86 p-4 shadow-soft">
          <div className="flex items-center gap-2 text-sm font-medium text-ink">
            <Loader2 className="h-4 w-4 motion-safe:animate-spin text-leaf" />
            Creating agent...
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-sand-deep">
            <div className="bg-forest h-full w-2/3 motion-safe:animate-pulse rounded-full" />
          </div>
        </div>
      )}
    </div>
  )
}
