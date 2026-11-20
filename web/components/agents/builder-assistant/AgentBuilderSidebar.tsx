'use client';

import { useState, useRef, useEffect } from 'react';
import { ClipboardList, Maximize2, Minimize2, PenLine, Send, Settings, Sparkles, Wrench, X, type LucideIcon } from 'lucide-react';
import toast from 'react-hot-toast';
import { secureStorage } from '@/lib/auth/secure-storage';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface SuggestionPrompt {
  title: string;
  description: string;
  prompt: string;
  icon: LucideIcon;
}

interface AgentBuilderSidebarProps {
  onInsertContent?: (content: string, field?: 'system_prompt' | 'name' | 'description') => void;
  currentContext?: {
    agentType?: string;
    useCase?: string;
    tools?: string[];
  };
}

export function AgentBuilderSidebar({ onInsertContent, currentContext }: AgentBuilderSidebarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const suggestionPrompts: SuggestionPrompt[] = [
    {
      title: 'Generate System Prompt',
      description: 'Create a tailored system prompt',
      prompt: 'Help me generate a system prompt for a [type] agent that [purpose]',
      icon: PenLine
    },
    {
      title: 'Recommend Tools',
      description: 'Get tool suggestions',
      prompt: 'Which tools should I enable for [use case]?',
      icon: Wrench
    },
    {
      title: 'Optimize Settings',
      description: 'LLM configuration advice',
      prompt: 'What LLM settings should I use for [task type]?',
      icon: Settings
    },
    {
      title: 'Format JSON',
      description: 'Help with JSON formatting',
      prompt: 'Help me format suggestion prompts in JSON for [use case]',
      icon: ClipboardList
    }
  ];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async (messageContent: string) => {
    if (!messageContent.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: messageContent,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    const assistantMessage: Message = {
      role: 'assistant',
      content: '',
      timestamp: new Date()
    };

    setMessages((prev) => [...prev, assistantMessage]);

    try {
      // Add context if available
      let contextualMessage = messageContent;
      if (currentContext && Object.keys(currentContext).length > 0) {
        const contextInfo = [];
        if (currentContext.agentType) contextInfo.push(`Agent type: ${currentContext.agentType}`);
        if (currentContext.useCase) contextInfo.push(`Use case: ${currentContext.useCase}`);
        if (currentContext.tools && currentContext.tools.length > 0) {
          contextInfo.push(`Selected tools: ${currentContext.tools.join(', ')}`);
        }
        if (contextInfo.length > 0) {
          contextualMessage = `${messageContent}\n\nContext: ${contextInfo.join('; ')}`;
        }
      }

      // Get the access token from secure storage (same as chat interface)
      const token = secureStorage.getAccessToken();
      
      // Use the standard streaming chat endpoint with agent_builder_assistant
      const response = await fetch(`${API_URL}/api/v1/agents/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
        body: JSON.stringify({
          agent_slug: 'agent_builder_assistant',
          message: contextualMessage,
          conversation_id: conversationId,
          conversation_history: messages.slice(-10).map((msg) => ({
            role: msg.role,
            content: msg.content,
          })),
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullResponse = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim() || !line.startsWith('data: ')) continue;

          const jsonStr = line.slice(6).trim();
          if (jsonStr === '[DONE]') continue;

          let data: Record<string, unknown>;
          try {
            data = JSON.parse(jsonStr);
          } catch {
            continue; // skip malformed JSON
          }

          if (data.type === 'error') {
            throw new Error((data.error as string) || 'Something went wrong');
          }

          if (data.type === 'chunk') {
            fullResponse += data.content;
            setMessages((prev: Message[]) => {
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;
              if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                newMessages[lastIndex] = {
                  ...newMessages[lastIndex],
                  content: fullResponse,
                };
              }
              return newMessages;
            });
          }

          if (data.type === 'done') {
            // Server generates/reuses the real conversation on first message and
            // returns it here — capture it so subsequent messages continue the
            // same conversation server-side instead of silently starting a new
            // one each time (which surfaces later as "Conversation X not found").
            const metadata = data.metadata as { conversation_id?: string } | undefined;
            if (metadata?.conversation_id) {
              setConversationId(metadata.conversation_id);
            }
          }
        }
      }
    } catch (error: any) {
      console.error('Error sending message:', error);
      const msg = error?.message || 'Failed to get response';
      setMessages(prev => {
        const newMessages = [...prev];
        const last = newMessages[newMessages.length - 1];
        if (last?.role === 'assistant') {
          const existing = last.content ? `${last.content}\n\n` : '';
          newMessages[newMessages.length - 1] = { ...last, content: `${existing}⚠ ${msg}` };
        }
        return newMessages;
      });
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestionClick = (prompt: string) => {
    setInput(prompt);
  };

  const handleInsertContent = (content: string) => {
    if (onInsertContent) {
      onInsertContent(content);
      toast.success('Content copied to clipboard!');
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 rounded-full h-14 w-14 shadow-lg bg-leaf hover:bg-forest text-white transition-colors flex items-center justify-center z-50"
      >
        <Sparkles className="h-6 w-6" />
      </button>
    );
  }

  return (
    <div 
      className={`fixed bottom-6 right-6 bg-white border border-line rounded-lg shadow-2xl transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-300 z-50 flex flex-col ${
        isMinimized ? 'w-80 h-16' : 'w-[500px] h-[600px]'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-line flex-shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-leaf" />
          <h3 className="font-semibold text-ink">Agent Builder Assistant</h3>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="h-8 w-8 flex items-center justify-center hover:bg-sand rounded transition-colors"
          >
            {isMinimized ? <Maximize2 className="h-4 w-4" /> : <Minimize2 className="h-4 w-4" />}
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="h-8 w-8 flex items-center justify-center hover:bg-sand rounded transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Messages */}
          <div className="flex-1 p-4 overflow-y-auto" ref={scrollRef}>
            {messages.length === 0 ? (
              <div className="space-y-4">
                <p className="text-sm text-ink-soft text-center mb-4">
                  Hi! I'm your Agent Builder Assistant. I can help you create effective agents. Try one of these:
                </p>
                <div className="grid gap-2">
                  {suggestionPrompts.map((suggestion, index) => (
                    <button
                      key={index}
                      onClick={() => handleSuggestionClick(suggestion.prompt)}
                      className="text-left p-3 rounded-lg border border-line bg-white hover:bg-cream hover:border-taupe transition-colors"
                    >
                      <div className="flex items-start gap-2">
                        <suggestion.icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                        <div className="flex-1">
                          <p className="font-medium text-sm text-ink">{suggestion.title}</p>
                          <p className="text-xs text-ink-soft mt-0.5">{suggestion.description}</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((message, index) => (
                  <div
                    key={index}
                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg p-3 ${
                        message.role === 'user'
                          ? 'bg-leaf text-white'
                          : 'bg-sand text-ink'
                      }`}
                    >
                      <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                      {message.role === 'assistant' && message.content && (
                        <button
                          onClick={() => handleInsertContent(message.content)}
                          className="mt-2 px-3 py-1 text-xs bg-white text-leaf rounded hover:bg-cream transition-colors"
                        >
                          Insert
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="bg-sand rounded-lg p-3">
                      <div className="flex gap-1">
                        <div className="w-2 h-2 rounded-full bg-ash motion-safe:animate-bounce" />
                        <div className="w-2 h-2 rounded-full bg-ash motion-safe:animate-bounce" style={{ animationDelay: '0.1s' }} />
                        <div className="w-2 h-2 rounded-full bg-ash motion-safe:animate-bounce" style={{ animationDelay: '0.2s' }} />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Input */}
          <div className="p-4 border-t border-line flex-shrink-0">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                sendMessage(input);
              }}
              className="flex gap-2"
            >
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask me anything about creating your agent…"
                className="flex-1 px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent resize-none min-h-[60px] max-h-[120px]"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage(input);
                  }
                }}
              />
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="h-[60px] w-[60px] flex items-center justify-center bg-leaf text-white rounded-lg hover:bg-forest transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
              >
                <Send className="h-5 w-5" />
              </button>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
