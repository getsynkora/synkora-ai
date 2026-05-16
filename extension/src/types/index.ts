export interface Agent {
  id: string;
  name: string;
  slug: string;
  avatar_url: string | null;
  accent_color: string | null;
  description: string | null;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  isStreaming?: boolean;
}

export interface Conversation {
  id: string;
  agentId: string;
  messages: Message[];
}

export type ConversationMode = 'per-page' | 'persistent';
export type PageContextMode = 'viewport' | 'full';

export interface PageContext {
  text: string;
  url: string;
  title: string;
  mode: PageContextMode;
}

export interface ExtensionState {
  // Auth
  isConnected: boolean;
  synkoraUrl: string;

  // Agent selection
  agents: Agent[];
  selectedAgentId: string | null;
  defaultAgentId: string | null;

  // Chat
  conversations: Record<string, Conversation>; // keyed by agentId or URL
  conversationMode: ConversationMode;

  // Page context
  pageContextEnabled: boolean;
  pageContextMode: PageContextMode;

  // UI
  pendingSelectionText: string | null; // text pre-filled from right-click
}

// Messages between extension parts
export type ExtensionMessage =
  | { type: 'GET_PAGE_CONTEXT'; mode: PageContextMode }
  | { type: 'PAGE_CONTEXT_RESPONSE'; context: PageContext }
  | { type: 'SELECTION_TEXT'; text: string }
  | { type: 'OPEN_SIDEPANEL' }
  | { type: 'TOKEN_REFRESH_NEEDED' };

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // Unix ms
}
