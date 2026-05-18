import { useState } from 'react';
import { ChevronDown, Pin, Check } from 'lucide-react';
import type { Agent } from '@/types';

interface Props {
  agents: Agent[];
  selectedAgentId: string | null;
  defaultAgentId: string | null;
  onSelect: (agentId: string) => void;
  onSetDefault: (agentId: string) => void;
}

export function AgentPicker({ agents, selectedAgentId, defaultAgentId, onSelect, onSetDefault }: Props) {
  const [open, setOpen] = useState(false);
  const selected = agents.find((a) => a.id === selectedAgentId);

  if (!selected && agents.length === 0) {
    return (
      <div className="flex items-center gap-2 px-3 py-2">
        <div className="w-7 h-7 rounded-full bg-gray-200 animate-pulse" />
        <div className="h-3 w-24 bg-gray-200 rounded animate-pulse" />
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-3 px-3 py-2.5 rounded-2xl hover:bg-brand-surface transition-colors w-full text-left group"
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <AgentAvatar agent={selected ?? null} size={30} />
        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-semibold text-brand-ink truncate leading-tight">
            {selected?.name ?? 'Select agent'}
          </p>
          {selected?.description && (
            <p className="text-[11px] text-brand-muted/80 truncate leading-tight mt-0.5">
              {selected.description}
            </p>
          )}
        </div>
        <ChevronDown
          size={14}
          className={`text-brand-muted/70 transition-transform duration-200 flex-shrink-0 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div
            role="listbox"
            className="absolute left-2 right-2 top-full mt-2 bg-brand-panel border border-brand-line rounded-[22px] shadow-card z-20 py-1.5 max-h-64 overflow-y-auto animate-slide-up"
          >
            {agents.map((agent) => (
              <div
                key={agent.id}
                role="option"
                aria-selected={agent.id === selectedAgentId}
                className="flex items-center gap-2.5 px-3 py-2.5 hover:bg-brand-surface cursor-pointer group transition-colors"
                onClick={() => { onSelect(agent.id); setOpen(false); }}
              >
                <AgentAvatar agent={agent} size={26} />
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-medium text-brand-ink truncate">{agent.name}</p>
                  {agent.description && (
                    <p className="text-[11px] text-brand-muted/80 truncate">{agent.description}</p>
                  )}
                </div>
                {agent.id === selectedAgentId && (
                  <Check size={13} className="text-synkora-700 flex-shrink-0" />
                )}
                <button
                  title={agent.id === defaultAgentId ? 'Default agent' : 'Set as default'}
                  onClick={(e) => { e.stopPropagation(); onSetDefault(agent.id); }}
                  className={`flex-shrink-0 p-1 rounded-lg transition-all ${
                    agent.id === defaultAgentId
                      ? 'text-synkora-700 bg-synkora-100'
                      : 'text-brand-muted/40 opacity-0 group-hover:opacity-100 hover:text-brand-muted'
                  }`}
                >
                  <Pin size={12} />
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

interface AvatarProps {
  agent: Agent | null;
  size: number;
}

export function AgentAvatar({ agent, size }: AvatarProps) {
  const accentColor = agent?.accent_color ?? '#79dfbc';
  const initials = agent?.name
    ? agent.name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : '?';

  if (agent?.avatar_url) {
    return (
      <img
        src={agent.avatar_url}
        alt={agent.name}
        width={size}
        height={size}
        className="rounded-full object-cover flex-shrink-0"
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <div
      className="rounded-full flex items-center justify-center text-brand-ink font-semibold flex-shrink-0 ring-1 ring-brand-line/80"
      style={{
        width: size,
        height: size,
        backgroundColor: accentColor,
        fontSize: size * 0.38,
      }}
    >
      {initials}
    </div>
  );
}
