import { useState, useRef, useCallback, useEffect } from 'react';
import { Send, Square, Trash2, Sparkles, Globe, FileText } from 'lucide-react';
import { useChat } from '@/hooks/useChat';
import { usePageContext } from '@/hooks/usePageContext';
import { useExtensionStore } from '@/store/extension';
import { MessageList } from './MessageList';
import type { Agent } from '@/types';

interface Props {
  agent: Agent;
  pageUrl: string;
  contextAvailable: boolean;
}

const SUGGESTIONS = [
  { icon: '✦', label: 'Summarize this page' },
  { icon: '?', label: 'What is this about?' },
  { icon: '→', label: 'Key takeaways' },
  { icon: '✉', label: 'Draft a reply' },
];

export function ChatPanel({ agent, pageUrl, contextAvailable }: Props) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);

  const { send, stop, isStreaming, error } = useChat(agent.slug, pageUrl);
  const { getContext } = usePageContext();
  const {
    getActiveConversationKey, conversations,
    clearConversation,
    pendingSelectionText, setPendingSelectionText,
  } = useExtensionStore();

  const convKey = getActiveConversationKey(agent.slug, pageUrl);
  const messages = conversations[convKey]?.messages ?? [];
  const isEmpty = messages.length === 0;

  useEffect(() => {
    if (pendingSelectionText) {
      setInput(pendingSelectionText);
      setPendingSelectionText(null);
      textareaRef.current?.focus();
    }
  }, [pendingSelectionText, setPendingSelectionText]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [input]);

  const handleSend = useCallback(async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || isStreaming) return;
    setInput('');
    const ctx = await getContext();
    await send(msg, ctx?.text);
  }, [input, isStreaming, getContext, send]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hostname = (() => {
    try { return new URL(pageUrl).hostname.replace(/^www\./, ''); } catch { return ''; }
  })();

  return (
    <div className="flex flex-col flex-1 min-h-0 bg-white">

      {/* Messages / Welcome */}
      <div ref={messagesRef} className="flex-1 min-h-0 overflow-y-auto scroll-smooth">
        {isEmpty ? (
          <WelcomeScreen
            agent={agent}
            hostname={hostname}
            contextAvailable={contextAvailable}
            onSuggestion={(s) => handleSend(s)}
            isStreaming={isStreaming}
          />
        ) : (
          <MessageList messages={messages} agent={agent} />
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mx-3 mb-2 px-3 py-2 bg-red-50 border border-red-100 rounded-xl text-xs text-red-600 flex items-center justify-between animate-fade-in">
          <span>{error}</span>
          <button onClick={() => handleSend()} className="font-semibold underline ml-2 hover:text-red-700">Retry</button>
        </div>
      )}

      {/* Bottom bar */}
      <div className="border-t border-gray-100 bg-white px-3 pt-2.5 pb-3">
        {/* Toolbar row */}
        <div className="flex items-center gap-2 mb-2">
          {/* Context indicator */}
          {hostname && (
            <div className={`flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border ${
              contextAvailable
                ? 'border-synkora-200 text-synkora-600 bg-synkora-50'
                : 'border-gray-200 text-gray-400 bg-white'
            }`}>
              {contextAvailable ? <Globe size={10} /> : <FileText size={10} />}
              <span className="truncate max-w-[100px]">{hostname}</span>
            </div>
          )}
          <div className="flex-1" />
          {!isEmpty && (
            <button
              onClick={() => clearConversation(convKey)}
              className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-red-400 transition-colors"
            >
              <Trash2 size={11} />
              Clear
            </button>
          )}
        </div>

        {/* Input */}
        <div className={`flex items-end gap-2 bg-gray-50 border rounded-2xl px-3.5 py-2.5 transition-all duration-150 ${
          isStreaming
            ? 'border-synkora-300 bg-synkora-50/30'
            : 'border-gray-200 focus-within:border-synkora-400 focus-within:bg-white focus-within:shadow-[0_0_0_3px_rgba(59,92,230,0.08)]'
        }`}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${agent.name}…`}
            rows={1}
            disabled={isStreaming}
            className="flex-1 resize-none bg-transparent text-[14px] text-gray-900 placeholder-gray-400 outline-none leading-relaxed min-h-[20px] font-sans"
          />
          <button
            onClick={isStreaming ? stop : () => handleSend()}
            disabled={!isStreaming && !input.trim()}
            className={`flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150 ${
              isStreaming
                ? 'bg-red-500 text-white hover:bg-red-600 shadow-sm'
                : input.trim()
                ? 'bg-synkora-600 text-white hover:bg-synkora-700 shadow-sm active:scale-95'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
            }`}
          >
            {isStreaming
              ? <Square size={11} fill="currentColor" />
              : <Send size={12} strokeWidth={2.5} />
            }
          </button>
        </div>
        <p className="text-[10px] text-gray-300 mt-1.5 text-center tracking-tight">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

function WelcomeScreen({
  agent, hostname, contextAvailable, onSuggestion, isStreaming,
}: {
  agent: Agent;
  hostname: string;
  contextAvailable: boolean;
  onSuggestion: (text: string) => void;
  isStreaming: boolean;
}) {
  const suggestions = contextAvailable
    ? SUGGESTIONS
    : [{ icon: '✦', label: `What can you help me with?` }, { icon: '?', label: 'What are your capabilities?' }];

  return (
    <div className="flex flex-col items-center px-5 pt-10 pb-4 text-center animate-fade-in">
      {/* Agent icon */}
      <div className="relative mb-4">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-synkora-500 to-synkora-700 flex items-center justify-center shadow-card">
          {agent.avatar_url ? (
            <img src={agent.avatar_url} alt={agent.name} className="w-full h-full rounded-2xl object-cover" />
          ) : (
            <Sparkles size={28} className="text-white" strokeWidth={1.5} />
          )}
        </div>
        <span className="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-400 rounded-full border-2 border-white" />
      </div>

      {/* Heading */}
      <h2 className="text-[16px] font-semibold text-gray-900 mb-1 tracking-tight">
        Hi, I'm {agent.name}
      </h2>
      <p className="text-[13px] text-gray-500 leading-relaxed mb-1">
        {agent.description
          ? agent.description
          : 'Your AI assistant — ask me anything.'}
      </p>
      {hostname && (
        <p className="text-[11px] text-gray-400 mb-6 flex items-center gap-1">
          {contextAvailable ? (
            <><Globe size={10} className="text-synkora-400" /> I can see <span className="font-medium text-gray-500">{hostname}</span></>
          ) : (
            <><FileText size={10} /> No page context on this tab</>
          )}
        </p>
      )}

      {/* Suggestion chips */}
      <div className="w-full grid grid-cols-2 gap-2">
        {suggestions.map((s) => (
          <button
            key={s.label}
            onClick={() => onSuggestion(s.label)}
            disabled={isStreaming}
            className="flex flex-col items-start gap-1.5 p-3 bg-gray-50 hover:bg-synkora-50 border border-gray-100 hover:border-synkora-200 rounded-xl text-left transition-all duration-150 active:scale-[0.97] disabled:opacity-50 group"
          >
            <span className="text-base leading-none">{s.icon}</span>
            <span className="text-[12px] text-gray-600 group-hover:text-synkora-700 font-medium leading-tight">{s.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
