import { useEffect, useRef } from 'react';
import type { Message, Agent } from '@/types';
import { AgentAvatar } from './AgentPicker';

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
    return (
      <div className="flex justify-end">
        <div className="max-w-[82%] bg-gray-950 text-white/95 rounded-2xl rounded-tr-md px-4 py-3 text-[14px] leading-relaxed shadow-sm">
          {message.content}
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
          <div className="text-[14px] text-gray-800 leading-relaxed">
            <MarkdownContent content={message.content} />
            {message.isStreaming && (
              <span className="inline-block w-[2px] h-[14px] bg-gray-500 ml-0.5 align-middle animate-blink" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-gray-400 animate-bounce-dot"
          style={{ animationDelay: `${i * 0.18}s` }}
        />
      ))}
    </div>
  );
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <div
      className="[&_strong]:font-semibold [&_em]:italic [&_code]:bg-gray-100 [&_code]:border [&_code]:border-gray-200 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-[12px] [&_code]:font-mono [&_code]:text-gray-700 [&_pre]:bg-gray-950 [&_pre]:text-gray-100 [&_pre]:rounded-xl [&_pre]:p-3 [&_pre]:overflow-x-auto [&_pre]:text-[12px] [&_pre]:my-2 [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:my-2 [&_ol]:list-decimal [&_ol]:pl-4 [&_ol]:my-2 [&_li]:my-1 [&_a]:text-synkora-600 [&_a]:underline [&_a]:underline-offset-2 [&_h3]:font-semibold [&_h3]:text-gray-900 [&_h3]:mt-3 [&_h3]:mb-1 [&_p]:my-1.5 first:[&_p]:mt-0"
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  );
}

function renderMarkdown(text: string): string {
  if (!text) return '';
  let s = escapeHtml(text);
  // Code blocks (must come before inline code)
  s = s.replace(/```[\w]*\n?([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  // Inline code
  s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  // Bold
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  // Italic
  s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
  // H3
  s = s.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  // Links
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  // Lists
  s = s.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  s = s.replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>');
  s = s.replace(/(<li>.*?<\/li>(\n|$))+/gs, (m) => `<ul>${m}</ul>`);
  // Paragraphs — split on double newline
  s = s.replace(/\n\n+/g, '</p><p>');
  // Single newlines
  s = s.replace(/\n/g, '<br>');
  return `<p>${s}</p>`;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
