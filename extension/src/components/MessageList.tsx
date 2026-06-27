import { useEffect, useRef, useState } from 'react';
import { CheckCircle, AlertCircle, Sparkles } from 'lucide-react';
import type { Message, Agent } from '@/types';
import { AgentAvatar } from './AgentPicker';
import { fillFormOnPage, splitContentSegments } from '@/lib/form-filler';

interface Props {
  messages: Message[];
  agent: Agent | null;
}

export function MessageList({ messages, agent }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="px-4 py-4 space-y-5">
      {messages.map((msg, i) => (
        <div key={msg.id} className="animate-fade-in" style={{ animationDelay: `${i * 0.03}s` }}>
          <MessageBubble message={msg} agent={agent} />
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

function MessageBubble({ message, agent }: { message: Message; agent: Agent | null }) {
  const isUser = message.role === 'user';

  if (isUser) {
    // Strip the injected [Current page context] block before displaying
    const display = message.content.replace(/^\[Current page context\][\s\S]*?---\n/, '').trim();
    return (
      <div className="flex justify-end">
        <div className="max-w-[82%] bg-brand-ink text-brand-panel rounded-2xl rounded-tr-md px-4 py-3 text-[14px] leading-relaxed shadow-soft">
          {display}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2.5">
      <div className="flex-shrink-0 mt-0.5">
        <AgentAvatar agent={agent} size={26} />
      </div>
      <div className="flex-1 min-w-0 pt-0.5">
        {message.isStreaming && !message.content ? (
          <TypingIndicator />
        ) : (
          <AssistantContent content={message.content} isStreaming={message.isStreaming} />
        )}
      </div>
    </div>
  );
}

function AssistantContent({ content, isStreaming }: { content: string; isStreaming?: boolean }) {
  const [fillState, setFillState] = useState<'idle' | 'filling' | 'done' | 'error'>('idle');
  const [fillError, setFillError] = useState('');

  const segments = splitContentSegments(content);
  const hasFillBlock = segments.some((s) => s.type === 'fill');

  const handleFill = async () => {
    if (fillState !== 'idle') return;
    const fillSegment = segments.find((s) => s.type === 'fill');
    if (!fillSegment || fillSegment.type !== 'fill') return;

    setFillState('filling');
    try {
      const result = await fillFormOnPage(fillSegment.fields);
      if (result.errors.length > 0 && result.filled === 0) {
        setFillError(result.errors[0]);
        setFillState('error');
      } else {
        setFillState('done');
      }
    } catch (e) {
      setFillError(e instanceof Error ? e.message : 'Fill failed');
      setFillState('error');
    }
  };

  return (
    <div className="text-[14px] text-brand-ink leading-relaxed">
      {segments.map((seg, i) =>
        seg.type === 'text' ? (
          <MarkdownContent key={i} content={seg.content} />
        ) : (
          <FillFormBlock
            key={i}
            fieldCount={seg.fields.length}
            state={fillState}
            error={fillError}
            onFill={handleFill}
          />
        )
      )}
      {isStreaming && !hasFillBlock && (
        <span className="inline-block w-[2px] h-[14px] bg-brand-muted ml-0.5 align-middle animate-blink" />
      )}
    </div>
  );
}

function FillFormBlock({
  fieldCount,
  state,
  error,
  onFill,
}: {
  fieldCount: number;
  state: 'idle' | 'filling' | 'done' | 'error';
  error: string;
  onFill: () => void;
}) {
  return (
    <div className="my-3 rounded-2xl border border-synkora-200 bg-synkora-50 px-4 py-3 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2 min-w-0">
        <Sparkles size={14} className="text-synkora-600 flex-shrink-0" />
        <span className="text-[13px] text-brand-ink font-medium truncate">
          {state === 'done'
            ? `${fieldCount} field${fieldCount !== 1 ? 's' : ''} filled`
            : `Fill ${fieldCount} field${fieldCount !== 1 ? 's' : ''}`}
        </span>
      </div>

      {state === 'idle' && (
        <button
          onClick={onFill}
          className="flex-shrink-0 text-[12px] font-semibold bg-synkora-500 hover:bg-synkora-400 text-brand-ink px-3 py-1.5 rounded-xl transition-colors shadow-soft active:scale-95"
        >
          Fill Form
        </button>
      )}

      {state === 'filling' && (
        <div className="flex-shrink-0 w-4 h-4 border-2 border-synkora-500 border-t-transparent rounded-full animate-spin" />
      )}

      {state === 'done' && (
        <CheckCircle size={16} className="flex-shrink-0 text-synkora-600" />
      )}

      {state === 'error' && (
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <AlertCircle size={14} className="text-[#b35630]" />
          <span className="text-[11px] text-[#b35630] max-w-[100px] truncate" title={error}>
            {error || 'Failed'}
          </span>
          <button
            onClick={onFill}
            className="text-[11px] font-semibold text-[#b35630] underline underline-offset-2"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-synkora-500 animate-bounce-dot"
          style={{ animationDelay: `${i * 0.18}s` }}
        />
      ))}
    </div>
  );
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <div
      className="
        [&_p]:my-1.5 first:[&_p]:mt-0
        [&_strong]:font-semibold [&_em]:italic
        [&_h1]:text-[17px] [&_h1]:font-bold [&_h1]:mt-4 [&_h1]:mb-1
        [&_h2]:text-[15px] [&_h2]:font-bold [&_h2]:mt-3 [&_h2]:mb-1
        [&_h3]:text-[14px] [&_h3]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1
        [&_h4]:text-[13px] [&_h4]:font-semibold [&_h4]:mt-2 [&_h4]:mb-0.5
        [&_code]:bg-brand-surface [&_code]:border [&_code]:border-brand-line [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-[11px] [&_code]:font-mono
        [&_pre]:bg-brand-ink [&_pre]:text-brand-panel [&_pre]:rounded-xl [&_pre]:p-3 [&_pre]:overflow-x-auto [&_pre]:text-[11px] [&_pre]:my-2
        [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:my-1.5
        [&_ol]:list-decimal [&_ol]:pl-4 [&_ol]:my-1.5
        [&_li]:my-0.5
        [&_a]:text-synkora-700 [&_a]:underline [&_a]:underline-offset-2
        [&_blockquote]:border-l-2 [&_blockquote]:border-synkora-400 [&_blockquote]:pl-3 [&_blockquote]:my-2 [&_blockquote]:text-brand-muted [&_blockquote]:italic
        [&_hr]:border-brand-line [&_hr]:my-3
        [&_table]:w-full [&_table]:border-collapse [&_table]:text-[12px] [&_table]:my-2
        [&_th]:text-left [&_th]:px-2.5 [&_th]:py-1.5 [&_th]:font-semibold [&_th]:border-b-2 [&_th]:border-brand-line [&_th]:bg-brand-surface [&_th]:whitespace-nowrap
        [&_td]:px-2.5 [&_td]:py-1.5 [&_td]:border-b [&_td]:border-brand-line/60 [&_td]:align-top
        [&_.table-wrap]:overflow-x-auto [&_.table-wrap]:my-2 [&_.table-wrap]:rounded-lg [&_.table-wrap]:border [&_.table-wrap]:border-brand-line
      "
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function applyInline(s: string): string {
  s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  s = s.replace(/\*\*\*([^*\n]+)\*\*\*/g, '<strong><em>$1</em></strong>');
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return s;
}

function renderTable(rows: string[]): string {
  const parseRow = (r: string) => r.split('|').slice(1, -1).map(c => c.trim());
  const isSep = (r: string) => /^\|[-:| ]+\|$/.test(r.trim());

  const sepIdx = rows.findIndex(isSep);
  if (sepIdx < 1) return rows.join('\n');

  const headers = parseRow(rows[0]);
  const dataRows = rows.slice(sepIdx + 1).filter(r => r.trim() && !isSep(r));

  let html = '<div class="table-wrap"><table><thead><tr>';
  html += headers.map(h => `<th>${applyInline(h)}</th>`).join('');
  html += '</tr></thead><tbody>';
  dataRows.forEach((row) => {
    const cells = parseRow(row);
    html += '<tr>' + cells.map(c => `<td>${applyInline(c)}</td>`).join('') + '</tr>';
  });
  html += '</tbody></table></div>';
  return html;
}

function renderMarkdown(raw: string): string {
  if (!raw) return '';

  const blocks: string[] = [];
  const ph = (html: string) => { const i = blocks.length; blocks.push(html); return `\x00B${i}\x00`; };

  let s = escapeHtml(raw);

  // 1. Fenced code blocks (protect before everything else)
  s = s.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, code) =>
    ph(`<pre><code>${code.trim()}</code></pre>`)
  );

  // 2. Tables — must be processed before \n→<br> conversion
  s = s.replace(/^(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|?\n?)*)/gm, (match) =>
    ph(renderTable(match.trim().split('\n').filter(Boolean)))
  );

  // 3. Headings H1–H4
  s = s.replace(/^(#{1,4}) (.+)$/gm, (_, h, content) =>
    `<h${h.length}>${applyInline(content)}</h${h.length}>`
  );

  // 4. Horizontal rule
  s = s.replace(/^([-*_]){3,}$/gm, '<hr>');

  // 5. Blockquotes (&gt; because > was escaped)
  s = s.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

  // 6. Inline: bold, italic, code, links
  s = applyInline(s);

  // 7. Lists
  s = s.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  s = s.replace(/^\d+\. (.+)$/gm, '<li>$2</li>');
  s = s.replace(/(<li>.*?<\/li>(\n|$))+/gs, m => `<ul>${m}</ul>`);

  // 8. Paragraphs / line breaks
  s = s.replace(/\n\n+/g, '</p><p>');
  s = s.replace(/\n/g, '<br>');
  s = `<p>${s}</p>`;

  // 9. Restore protected blocks
  s = s.replace(/\x00B(\d+)\x00/g, (_, i) => blocks[parseInt(i)] ?? '');

  return s;
}
