import { useCallback, useRef, useState } from 'react';
import { streamChat, parseSseLine } from '@/lib/api';
import { loadAccessToken, loadSynkoraUrl, loadApiUrl } from '@/lib/auth';
import { useExtensionStore } from '@/store/extension';

export function useChat(agentSlug: string, pageUrl: string) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const {
    getActiveConversationKey,
    getOrCreateConversation,
    appendMessage,
    updateLastMessage,
    conversations,
    pageContextEnabled,
    isConnected,
  } = useExtensionStore();

  const send = useCallback(async (userMessage: string, pageContextText?: string) => {
    if (!isConnected || !agentSlug || isStreaming) return;

    const synkoraUrl = await loadSynkoraUrl();
    if (!synkoraUrl) { setError('Not connected to Synkora'); return; }

    const tokenData = await loadAccessToken();
    if (!tokenData) { setError('Session expired — please reconnect'); return; }

    const key = getActiveConversationKey(agentSlug, pageUrl);
    const conv = getOrCreateConversation(agentSlug, pageUrl);

    appendMessage(key, { role: 'user', content: userMessage });
    appendMessage(key, { role: 'assistant', content: '', isStreaming: true });

    setIsStreaming(true);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    const history = conv.messages
      .slice(-20)
      .filter((m) => m.content)
      .map((m) => ({ role: m.role, content: m.content }));

    const apiUrl = await loadApiUrl() ?? synkoraUrl;

    try {
      const reader = await streamChat(
        {
          synkoraUrl: apiUrl,
          accessToken: tokenData.token,
          agentSlug,
          message: userMessage,
          conversationId: conv.id,
          conversationHistory: history,
          systemContext: pageContextEnabled && pageContextText ? pageContextText : undefined,
        },
        controller.signal
      );

      let accumulated = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += value;
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          const chunk = parseSseLine(line);
          if (chunk) {
            accumulated += chunk;
            updateLastMessage(key, accumulated, true);
          }
        }
      }

      updateLastMessage(key, accumulated || '(no response)', false);
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        const current = conversations[key]?.messages.at(-1)?.content ?? '';
        updateLastMessage(key, current || '_(stopped)_', false);
      } else {
        const msg = err instanceof Error ? err.message : 'Stream error';
        setError(msg);
        updateLastMessage(key, `Error: ${msg}`, false);
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [
    isConnected, agentSlug, isStreaming, pageUrl,
    getOrCreateConversation, getActiveConversationKey,
    appendMessage, updateLastMessage, conversations,
    pageContextEnabled,
  ]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { send, stop, isStreaming, error };
}
