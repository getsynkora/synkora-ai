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
        className="flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-gray-50 transition-colors w-full text-left group"
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <AgentAvatar agent={selected ?? null} size={30} />
        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-semibold text-gray-900 truncate leading-tight">
            {selected?.name ?? 'Select agent'}
          </p>
          {selected?.description && (
            <p className="text-[11px] text-gray-400 truncate leading-tight mt-0.5">
              {selected.description}
            </p>
          )}
        </div>
        <ChevronDown
          size={14}
          className={`text-gray-400 transition-transform duration-200 flex-shrink-0 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div
            role="listbox"
            className="absolute left-2 right-2 top-full mt-1 bg-white border border-gray-200 rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.1)] z-20 py-1.5 max-h-64 overflow-y-auto animate-slide-up"
          >
            {agents.map((agent) => (
              <div
                key={agent.id}
                role="option"
                aria-selected={agent.id === selectedAgentId}
                className="flex items-center gap-2.5 px-3 py-2 hover:bg-gray-50 cursor-pointer group transition-colors"
                onClick={() => { onSelect(agent.id); setOpen(false); }}
              >
                <AgentAvatar agent={agent} size={26} />
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-medium text-gray-900 truncate">{agent.name}</p>
                  {agent.description && (
                    <p className="text-[11px] text-gray-400 truncate">{agent.description}</p>
                  )}
                </div>
                {agent.id === selectedAgentId && (
                  <Check size={13} className="text-synkora-600 flex-shrink-0" />
                )}
                <button
                  title={agent.id === defaultAgentId ? 'Default agent' : 'Set as default'}
                  onClick={(e) => { e.stopPropagation(); onSetDefault(agent.id); }}
                  className={`flex-shrink-0 p-1 rounded-lg transition-all ${
                    agent.id === defaultAgentId
                      ? 'text-synkora-500'
                      : 'text-gray-300 opacity-0 group-hover:opacity-100 hover:text-gray-500'
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
  const accentColor = agent?.accent_color ?? '#4f6ef7';
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
      className="rounded-full flex items-center justify-center text-white font-semibold flex-shrink-0"
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
