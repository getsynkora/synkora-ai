/**
 * Typed Synkora API client for the Chrome extension.
 *
 * Calls the existing console API endpoints:
 * - GET  /api/v1/agents           — list all agents
 * - POST /api/v1/agents/chat/stream — SSE chat stream (agent_slug in body)
 * - POST /console/api/auth/refresh  — refresh token
 *
 * Auth: Bearer JWT in Authorization header.
 * All calls assert https:// unless running in development.
 */

import type { Agent } from '@/types';

function assertHttps(url: string): void {
  if (!url.startsWith('https://') && !url.startsWith('http://localhost') && !url.startsWith('http://127.')) {
    throw new Error(`Insecure URL rejected: ${url}`);
  }
}

async function apiFetch(
  synkoraUrl: string,
  path: string,
  accessToken: string,
  options: RequestInit = {}
): Promise<Response> {
  const url = `${synkoraUrl}${path}`;
  assertHttps(url);

  const resp = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
      ...options.headers,
    },
  });

  return resp;
}

// ── Agents ────────────────────────────────────────────────────────────────────

interface AgentsListResponse {
  data: {
    agents_list?: Array<{
      id: string;
      agent_name: string;
      slug?: string;
      avatar?: string | null;
      description?: string | null;
    }>;
  };
}

export async function fetchAgents(synkoraUrl: string, accessToken: string): Promise<Agent[]> {
  const resp = await apiFetch(synkoraUrl, '/api/v1/agents/', accessToken);
  if (!resp.ok) throw new Error(`Failed to fetch agents: ${resp.status}`);

  const json = await resp.json() as AgentsListResponse;
  const list = json.data?.agents_list ?? [];

  return list.map((a) => ({
    id: a.id,
    name: a.agent_name,
    slug: a.slug ?? a.agent_name.toLowerCase().replace(/\s+/g, '-'),
    avatar_url: a.avatar ?? null,
    accent_color: null,
    description: a.description ?? null,
  }));
}

// ── Chat streaming ────────────────────────────────────────────────────────────

export interface ChatStreamParams {
  synkoraUrl: string;
  accessToken: string;
  agentSlug: string;
  message: string;
  conversationId?: string;
  conversationHistory?: Array<{ role: string; content: string }>;
  systemContext?: string; // page context prepended
}

/**
 * Opens an SSE stream to /api/v1/agents/chat/stream.
 * Returns a ReadableStream<string> of text chunks.
 * The caller is responsible for closing the reader on abort/unmount.
 */
export async function streamChat(
  params: ChatStreamParams,
  signal: AbortSignal
): Promise<ReadableStreamDefaultReader<string>> {
  const {
    synkoraUrl, accessToken, agentSlug, message,
    conversationId, conversationHistory, systemContext,
  } = params;

  const url = `${synkoraUrl}/api/v1/agents/chat/stream`;
  assertHttps(url);

  // Prepend page context as the first history entry if provided
  const history = conversationHistory ? [...conversationHistory] : [];
  if (systemContext) {
    history.unshift({
      role: 'system',
      content: `Current page context:\n\n${systemContext}`,
    });
  }

  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({
      agent_slug: agentSlug,
      message,
      conversation_id: conversationId,
      conversation_history: history.length > 0 ? history : undefined,
    }),
    signal,
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({})) as { detail?: unknown };
    const detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
    throw new Error(detail ?? `Chat stream failed: ${resp.status}`);
  }

  if (!resp.body) throw new Error('No response body from chat stream');

  const reader = resp.body
    .pipeThrough(new TextDecoderStream())
    .getReader();

  return reader;
}

/**
 * Parse a single SSE line and return the text chunk if it's a data event.
 */
export function parseSseLine(line: string): string | null {
  if (!line.startsWith('data: ')) return null;
  const data = line.slice(6).trim();
  if (data === '[DONE]') return null;
  try {
    const parsed = JSON.parse(data) as { text?: string; content?: string; delta?: string };
    return parsed.text ?? parsed.content ?? parsed.delta ?? null;
  } catch {
    // Plain text SSE (not JSON)
    return data || null;
  }
}
