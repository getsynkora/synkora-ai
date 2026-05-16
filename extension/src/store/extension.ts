/**
 * Zustand store for extension UI state.
 * Auth tokens are NOT stored here — they live in chrome.storage.
 * This store holds UI-layer state that drives the React components.
 */

import { create } from 'zustand';
import type { Agent, Conversation, ConversationMode, PageContextMode } from '@/types';

interface ExtensionStore {
  // Connection
  isConnected: boolean;
  synkoraUrl: string;
  setConnected: (connected: boolean, url?: string) => void;

  // Agents
  agents: Agent[];
  selectedAgentId: string | null;
  defaultAgentId: string | null;
  agentsLoading: boolean;
  agentsError: string | null;
  setAgents: (agents: Agent[]) => void;
  setAgentsLoading: (loading: boolean) => void;
  setAgentsError: (error: string | null) => void;
  selectAgent: (agentId: string) => void;
  setDefaultAgent: (agentId: string) => void;

  // Conversations
  conversations: Record<string, Conversation>;
  conversationMode: ConversationMode;
  setConversationMode: (mode: ConversationMode) => void;
  getActiveConversationKey: (agentId: string, pageUrl: string) => string;
  getOrCreateConversation: (agentId: string, pageUrl: string) => Conversation;
  appendMessage: (key: string, message: Omit<Conversation['messages'][0], 'id' | 'timestamp'> & { id?: string; timestamp?: number }) => void;
  updateLastMessage: (key: string, content: string, isStreaming: boolean) => void;
  clearConversation: (key: string) => void;

  // Page context
  pageContextEnabled: boolean;
  pageContextMode: PageContextMode;
  setPageContextEnabled: (enabled: boolean) => void;
  setPageContextMode: (mode: PageContextMode) => void;

  // Text selection (from right-click)
  pendingSelectionText: string | null;
  setPendingSelectionText: (text: string | null) => void;
}

export const useExtensionStore = create<ExtensionStore>((set, get) => ({
  // Connection
  isConnected: false,
  synkoraUrl: '',
  setConnected: (connected, url) =>
    set((s) => ({ isConnected: connected, synkoraUrl: url ?? s.synkoraUrl })),

  // Agents
  agents: [],
  selectedAgentId: null,
  defaultAgentId: null,
  agentsLoading: false,
  agentsError: null,
  setAgents: (agents) => set({ agents }),
  setAgentsLoading: (agentsLoading) => set({ agentsLoading }),
  setAgentsError: (agentsError) => set({ agentsError }),
  selectAgent: (agentId) => set({ selectedAgentId: agentId }),
  setDefaultAgent: (agentId) => {
    set({ defaultAgentId: agentId });
    // Persist to local storage
    chrome.storage.local.set({ snkr_default_agent: agentId });
  },

  // Conversations
  conversations: {},
  conversationMode: 'per-page',
  setConversationMode: (conversationMode) => set({ conversationMode }),

  getActiveConversationKey: (agentId, pageUrl) => {
    const { conversationMode } = get();
    return conversationMode === 'persistent' ? agentId : `${agentId}::${pageUrl}`;
  },

  getOrCreateConversation: (agentId, pageUrl) => {
    const key = get().getActiveConversationKey(agentId, pageUrl);
    const existing = get().conversations[key];
    if (existing) return existing;
    const conv: Conversation = { id: key, agentId, messages: [] };
    set((s) => ({ conversations: { ...s.conversations, [key]: conv } }));
    return conv;
  },

  appendMessage: (key, msg) => {
    const id = msg.id ?? crypto.randomUUID();
    const timestamp = msg.timestamp ?? Date.now();
    const message = { ...msg, id, timestamp };
    set((s) => {
      const conv = s.conversations[key];
      if (!conv) return s;
      return {
        conversations: {
          ...s.conversations,
          [key]: { ...conv, messages: [...conv.messages, message] },
        },
      };
    });
  },

  updateLastMessage: (key, content, isStreaming) => {
    set((s) => {
      const conv = s.conversations[key];
      if (!conv || conv.messages.length === 0) return s;
      const messages = [...conv.messages];
      messages[messages.length - 1] = { ...messages[messages.length - 1], content, isStreaming };
      return { conversations: { ...s.conversations, [key]: { ...conv, messages } } };
    });
  },

  clearConversation: (key) => {
    set((s) => {
      const { [key]: _, ...rest } = s.conversations;
      return { conversations: rest };
    });
  },

  // Page context
  pageContextEnabled: true,
  pageContextMode: 'viewport',
  setPageContextEnabled: (pageContextEnabled) => set({ pageContextEnabled }),
  setPageContextMode: (pageContextMode) => set({ pageContextMode }),

  // Text selection
  pendingSelectionText: null,
  setPendingSelectionText: (pendingSelectionText) => set({ pendingSelectionText }),
}));
