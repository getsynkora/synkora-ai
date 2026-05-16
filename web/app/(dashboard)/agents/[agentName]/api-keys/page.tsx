'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import toast from 'react-hot-toast';
import { KeyRound } from 'lucide-react';
import { useAgentApiKeys } from '@/hooks/useAgentApiKeys';
import type { AgentApiKey, CreateApiKeyRequest } from '@/types/agent-api';
import AgentPageShell, { AgentPagePanel, AgentPageTabs } from '@/components/agents/AgentPageShell';

const warmInputClass =
  'w-full rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]';
const warmSecondaryButtonClass =
  'rounded-[1rem] border border-black/10 bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 transition-colors hover:bg-[#fcfaf5]';
const warmPrimaryButtonClass =
  'rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50';
const warmDangerButtonClass =
  'rounded-[1rem] border border-[#ead8e1] bg-white px-4 py-2.5 text-sm font-semibold text-[#8b5a74] transition-colors hover:bg-[#f8ecef]';
const modalFieldClass =
  'w-full rounded-[1.1rem] border border-[#ddd3c6] bg-white px-4 py-3 text-sm text-gray-900 placeholder:text-[#a3988a] shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]';
const modalEyebrowClass =
  'block text-[11px] font-semibold uppercase tracking-[0.26em] text-[#8d6c51]';
const modalSubLabelClass =
  'block text-sm font-semibold text-[#4f463d]';

export default function AgentApiKeysPage() {
  const params = useParams();
  const agentName = params.agentName as string;
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001';
  
  const [agent, setAgent] = useState<any>(null);
  const [apiKeys, setApiKeys] = useState<AgentApiKey[]>([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [activeTab, setActiveTab] = useState<'keys' | 'docs'>('keys');
  const [newKeyResponse, setNewKeyResponse] = useState<{ key: string; name: string } | null>(null);
  const [loadingAgent, setLoadingAgent] = useState(true);

  const {
    loading,
    getApiKeys,
    createApiKey,
    deleteApiKey,
    regenerateApiKey,
  } = useAgentApiKeys();

  useEffect(() => {
    const loadAgent = async () => {
      try {
        setLoadingAgent(true);
        const { apiClient } = await import('@/lib/api/client');
        const agentData = await apiClient.getAgent(agentName);
        setAgent(agentData);
        const keys = await getApiKeys({ agent_id: agentData.id });
        setApiKeys(keys);
      } catch (err: any) {
        console.error('Failed to load agent:', err);
        const detail = err?.response?.data?.detail;
        toast.error(typeof detail === 'string' ? detail : 'Failed to load agent');
      } finally {
        setLoadingAgent(false);
      }
    };

    loadAgent();
  }, [agentName, getApiKeys]);

  const loadApiKeys = async (agentId: string) => {
    const keys = await getApiKeys({ agent_id: agentId });
    setApiKeys(keys);
  };

  const handleCreateApiKey = async (data: CreateApiKeyRequest) => {
    if (!agent) return;
    const response = await createApiKey(data);
    if (response) {
      toast.success('API key created — copy it now, it won\'t be shown again');
      setNewKeyResponse({ key: response.api_key, name: data.key_name });
      setShowCreateForm(false);
      await loadApiKeys(agent.id);
    }
  };

  const handleDeleteKey = async (keyId: string) => {
    if (!agent) return;
    
    // Show confirmation toast with action buttons
    toast((t: { id: string }) => (
      <div className="flex flex-col gap-3">
        <p className="font-semibold text-gray-900">Delete API Key?</p>
        <p className="text-sm text-gray-600">This action cannot be undone.</p>
        <div className="flex gap-2">
          <button
            onClick={async () => {
              toast.dismiss(t.id);
              const success = await deleteApiKey(keyId);
              if (success) {
                await loadApiKeys(agent.id);
              }
            }}
            className={warmDangerButtonClass}
          >
            Delete
          </button>
          <button
            onClick={() => toast.dismiss(t.id)}
            className={warmSecondaryButtonClass}
          >
            Cancel
          </button>
        </div>
      </div>
    ), {
      duration: Infinity,
      position: 'top-center',
    });
  };

  const handleRegenerateKey = async (keyId: string) => {
    if (!agent) return;
    
    // Show confirmation toast with action buttons
    toast((t: { id: string }) => (
      <div className="flex flex-col gap-3">
        <p className="font-semibold text-gray-900">Regenerate API Key?</p>
        <p className="text-sm text-gray-600">The old key will stop working immediately.</p>
        <div className="flex gap-2">
          <button
            onClick={async () => {
              toast.dismiss(t.id);
              const response = await regenerateApiKey(keyId);
              if (response) {
                setNewKeyResponse({ key: response.api_key, name: response.key_name });
                await loadApiKeys(agent.id);
              }
            }}
            className={warmPrimaryButtonClass}
          >
            Regenerate
          </button>
          <button
            onClick={() => toast.dismiss(t.id)}
            className={warmSecondaryButtonClass}
          >
            Cancel
          </button>
        </div>
      </div>
    ), {
      duration: Infinity,
      position: 'top-center',
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard!');
  };

  if (loadingAgent || (loading && apiKeys.length === 0)) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-[#e5d9ca] border-t-[#171717]"></div>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-[#8b5a74]">Failed to load agent</div>
      </div>
    );
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="API Keys"
      description={<>Manage API keys for programmatic access to <span className="font-semibold text-gray-900">{agentName}</span>.</>}
      icon={KeyRound}
      badge="Developer Access"
      actions={!showCreateForm ? (
        <button
          onClick={() => setShowCreateForm(true)}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Create API Key
        </button>
      ) : undefined}
    >

        {/* New Key Display */}
        {newKeyResponse && (
          <AgentPagePanel className="mb-6 overflow-hidden p-5">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-[1rem] bg-[#e8f4ee]">
                <svg className="h-5 w-5 text-[#2d8b69]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-base font-semibold text-gray-950">Save your API key</h3>
                <p className="mb-3 text-xs text-gray-600">
                  Make sure to copy your API key now. You won't be able to see it again!
                </p>
                <div className="mb-3 rounded-[1.25rem] border border-black/10 bg-[#171717] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <code className="flex-1 break-all text-xs font-mono text-[#f7f2e7]">{newKeyResponse.key}</code>
                    <button
                      onClick={() => copyToClipboard(newKeyResponse.key)}
                      className="flex-shrink-0 rounded-[0.9rem] bg-[#f7f2e7] px-3 py-1.5 text-xs font-semibold text-[#171717] transition-colors hover:bg-white"
                    >
                      Copy
                    </button>
                  </div>
                </div>
                <button
                  onClick={() => setNewKeyResponse(null)}
                  className="text-xs font-semibold text-gray-600 underline underline-offset-4 transition-colors hover:text-gray-900"
                >
                  I've saved my key ✓
                </button>
              </div>
            </div>
          </AgentPagePanel>
        )}

        {/* Create Form Modal */}
        {showCreateForm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(28,22,16,0.28)] p-4 backdrop-blur-[8px]">
            <div className="max-h-[88vh] w-full max-w-4xl overflow-y-auto rounded-[1.6rem] border border-[#ddd3c5] bg-[linear-gradient(180deg,_rgba(250,247,241,0.98),_rgba(241,236,229,0.98))] shadow-[0_32px_90px_-34px_rgba(17,14,10,0.42)]">
              <div className="sticky top-0 rounded-t-[1.6rem] border-b border-[#e7ded2] bg-[linear-gradient(180deg,_rgba(253,250,245,0.98),_rgba(246,241,234,0.98))] px-5 py-5 sm:px-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[#8d6c51]">Developer Access</p>
                    <h2 className="mt-1 text-[1.9rem] font-semibold tracking-[-0.04em] text-gray-950">Create New API Key</h2>
                  </div>
                  <button
                    onClick={() => setShowCreateForm(false)}
                    className="rounded-full p-2 text-[#9a8f81] transition-colors hover:bg-white/80 hover:text-[#5f564c]"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
              <div className="px-5 py-5 sm:px-6">
                <ApiKeyForm
                  agentId={agent.id}
                  onSubmit={handleCreateApiKey}
                  onCancel={() => setShowCreateForm(false)}
                  isLoading={loading}
                />
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="mb-5">
          <AgentPageTabs
            activeId={activeTab}
            onChange={(id) => setActiveTab(id as 'keys' | 'docs')}
            items={[
              { id: 'keys', label: 'API Keys' },
              { id: 'docs', label: 'Documentation' },
            ]}
            className="inline-flex"
          />
        </div>

        {/* Tab Content */}
        {activeTab === 'keys' && (
          <div className="space-y-3">
            {apiKeys.length === 0 ? (
              <AgentPagePanel className="border-dashed p-12 text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-[1.4rem] bg-[#f1eadc]">
                  <svg className="h-8 w-8 text-[#171717]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                  </svg>
                </div>
                <h3 className="mb-2 text-base font-semibold text-gray-950">
                  No API keys yet
                </h3>
                <p className="mb-5 text-sm text-gray-600">
                  Create your first API key to start using the API
                </p>
                <button
                  onClick={() => setShowCreateForm(true)}
                  className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Create API Key
                </button>
              </AgentPagePanel>
            ) : (
              apiKeys.map((key) => (
                <div
                  key={key.id}
                  className="rounded-[1.6rem] border border-black/10 bg-white/85 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-0.5 hover:border-black/15 hover:shadow-[0_24px_56px_rgba(0,0,0,0.08)]"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-3">
                        <h3 className="text-base font-bold text-gray-900">
                          {key.key_name}
                        </h3>
                        <span
                          className={`px-2 py-0.5 text-xs font-semibold rounded-full ${
                            key.is_active
                              ? 'bg-emerald-100 text-emerald-700'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {key.is_active ? '✓ Active' : '○ Inactive'}
                        </span>
                      </div>

                      <div className="space-y-2 text-xs">
                        <div className="flex items-center gap-2 text-gray-600">
                          <div className="flex h-8 w-8 items-center justify-center rounded-[0.9rem] bg-[#f1eadc]">
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                            </svg>
                          </div>
                          <code className="font-mono text-sm font-semibold text-gray-900">
                            {key.key_prefix}••••••••
                          </code>
                        </div>
                        <div className="flex items-center gap-2 text-gray-600">
                          <div className="flex h-8 w-8 items-center justify-center rounded-[0.9rem] bg-[#edf4f6]">
                            <svg className="h-3.5 w-3.5 text-[#486c77]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                          </div>
                          <span className="font-medium">
                            <span className="font-bold text-[#486c77]">{key.rate_limit_per_minute}</span>/min ·
                            <span className="font-bold text-[#486c77]"> {key.rate_limit_per_hour}</span>/hr ·
                            <span className="font-bold text-[#486c77]"> {key.rate_limit_per_day}</span>/day
                          </span>
                        </div>
                        {key.expires_at && (
                          <div className="flex items-center gap-2 text-gray-600">
                            <div className="flex h-8 w-8 items-center justify-center rounded-[0.9rem] bg-[#f6edf1]">
                              <svg className="h-3.5 w-3.5 text-[#8b5a74]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            </div>
                            <span>Expires: {new Date(key.expires_at).toLocaleDateString()}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleRegenerateKey(key.id)}
                        className="rounded-full p-2 text-gray-500 transition-colors hover:bg-[#fcfaf5] hover:text-gray-900"
                        title="Regenerate key"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                      </button>
                      <button
                        onClick={() => handleDeleteKey(key.id)}
                        className="rounded-full p-2 text-[#8b5a74] transition-colors hover:bg-[#f8ecef] hover:text-[#6f435b]"
                        title="Delete key"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'docs' && (
          <AgentPagePanel className="space-y-6 p-6">
            <div className="flex items-center gap-3 border-b border-black/10 pb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-[1rem] bg-[#f1eadc]">
                <svg className="h-5 w-5 text-[#171717]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-gray-950">API Documentation</h3>
            </div>

            {/* Quick Start */}
            <div>
              <h4 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
                <span className="text-xl">🚀</span> Quick Start
              </h4>
              <div className="space-y-4 rounded-[1.35rem] border border-black/10 bg-[#fcfaf5] p-5">
                <div>
                  <p className="font-semibold text-gray-900 mb-1 text-sm">1. Get your API key</p>
                  <p className="text-gray-700 text-xs">
                    Create an API key from the "API Keys" tab above
                  </p>
                </div>
                <div>
                  <p className="font-semibold text-gray-900 mb-2 text-sm">2. Make your first request</p>
                  <pre className="bg-gray-900 text-gray-100 p-3 rounded-lg text-xs overflow-x-auto">
{`curl -X POST ${apiBaseUrl}/api/v1/public/agents/${agent.id}/chat/stream \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Hello, agent!",
    "conversation_id": null
  }'`}
                  </pre>
                </div>
              </div>
            </div>

            {/* Endpoints */}
            <div>
              <h4 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
                <span className="text-xl">🔌</span> Available Endpoints
              </h4>
              <div className="space-y-3">
                <div className="rounded-[1.25rem] border border-black/10 bg-[#fcfaf5] p-4 transition-shadow hover:shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="rounded-md bg-[#171717] px-2 py-0.5 text-xs font-bold text-[#f7f2e7]">POST</span>
                    <code className="font-mono text-xs font-semibold text-gray-900">/api/v1/public/agents/:agent_id/chat/stream</code>
                  </div>
                  <p className="text-gray-700 mb-3 text-xs">
                    Stream responses from the agent in real-time using Server-Sent Events (SSE)
                  </p>
                  <div className="rounded-[1rem] bg-white p-3">
                    <p className="font-semibold text-gray-900 mb-2 text-xs">Request Body:</p>
                    <pre className="text-xs overflow-x-auto text-gray-800 mb-2">
{`{
  "message": "Your message here",
  "conversation_id": "optional-conversation-id"
}`}
                    </pre>
                    <p className="text-xs text-gray-600 italic">
                      💡 Conversation history is automatically managed by the conversation_id. You don't need to send previous messages.
                    </p>
                  </div>
                </div>

                <div className="rounded-[1.25rem] border border-black/10 bg-[#fcfaf5] p-4 transition-shadow hover:shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="rounded-md bg-[#e8f4ee] px-2 py-0.5 text-xs font-bold text-[#2d8b69]">GET</span>
                    <code className="font-mono text-xs font-semibold text-gray-900">/api/v1/public/agents/:agent_id/conversations</code>
                  </div>
                  <p className="text-gray-700 text-xs">
                    List all conversations for this agent
                  </p>
                </div>

                <div className="rounded-[1.25rem] border border-black/10 bg-[#fcfaf5] p-4 transition-shadow hover:shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="rounded-md bg-[#e8f4ee] px-2 py-0.5 text-xs font-bold text-[#2d8b69]">GET</span>
                    <code className="font-mono text-xs font-semibold text-gray-900">/api/v1/public/agents/:agent_id/conversations/:conversation_id</code>
                  </div>
                  <p className="text-gray-700 text-xs">
                    Retrieve a specific conversation with its message history
                  </p>
                </div>

                <div className="rounded-[1.25rem] border border-black/10 bg-[#fcfaf5] p-4 transition-shadow hover:shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="rounded-md bg-[#f6edf1] px-2 py-0.5 text-xs font-bold text-[#8b5a74]">DELETE</span>
                    <code className="font-mono text-xs font-semibold text-gray-900">/api/v1/public/agents/:agent_id/conversations/:conversation_id</code>
                  </div>
                  <p className="text-gray-700 text-xs">
                    Delete a conversation and its message history
                  </p>
                </div>
              </div>
            </div>

            {/* Security */}
            <div>
              <h4 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
                <span className="text-xl">🔒</span> Security Best Practices
              </h4>
              <div className="rounded-[1.35rem] border border-black/10 bg-[#fcfaf5] p-5">
                <ul className="space-y-2 text-gray-800">
                  <li className="flex items-start gap-2 text-xs">
                    <span className="font-bold text-[#2d8b69]">✓</span>
                    <span>Never commit API keys to version control</span>
                  </li>
                  <li className="flex items-start gap-2 text-xs">
                    <span className="font-bold text-[#2d8b69]">✓</span>
                    <span>Use environment variables to store keys</span>
                  </li>
                  <li className="flex items-start gap-2 text-xs">
                    <span className="font-bold text-[#2d8b69]">✓</span>
                    <span>Rotate keys regularly</span>
                  </li>
                  <li className="flex items-start gap-2 text-xs">
                    <span className="font-bold text-[#2d8b69]">✓</span>
                    <span>Set IP whitelists when possible</span>
                  </li>
                  <li className="flex items-start gap-2 text-xs">
                    <span className="font-bold text-[#2d8b69]">✓</span>
                    <span>Use the minimum required permissions</span>
                  </li>
                </ul>
              </div>
            </div>
          </AgentPagePanel>
        )}
    </AgentPageShell>
  );
}

// Modern API Key Form Component
function ApiKeyForm({
  agentId,
  onSubmit,
  onCancel,
  isLoading,
}: {
  agentId: string;
  onSubmit: (data: CreateApiKeyRequest) => Promise<void>;
  onCancel: () => void;
  isLoading: boolean;
}) {
  const [formData, setFormData] = useState<CreateApiKeyRequest>({
    agent_id: agentId,
    key_name: '',
    rate_limit_per_minute: 60,
    rate_limit_per_hour: 1000,
    rate_limit_per_day: 10000,
    allowed_ips: [],
    allowed_origins: [],
    permissions: ['chat', 'conversations'],
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="space-y-2.5">
        <label className={modalEyebrowClass}>
          Key Name *
        </label>
        <input
          type="text"
          value={formData.key_name}
          onChange={(e) => setFormData({ ...formData, key_name: e.target.value })}
          className={modalFieldClass}
          placeholder="e.g., Production API Key"
          required
        />
      </div>

      <div className="space-y-3.5 rounded-[1.25rem] border border-[#e4dbcf] bg-[rgba(255,255,255,0.55)] p-4">
        <label className={modalEyebrowClass}>
          Rate Limits
        </label>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="space-y-2">
            <label className={modalSubLabelClass}>
              Per Minute
            </label>
            <input
              type="number"
              value={formData.rate_limit_per_minute}
              onChange={(e) =>
                setFormData({ ...formData, rate_limit_per_minute: parseInt(e.target.value) })
              }
              className={modalFieldClass}
              min="1"
              required
            />
          </div>
          <div className="space-y-2">
            <label className={modalSubLabelClass}>
              Per Hour
            </label>
            <input
              type="number"
              value={formData.rate_limit_per_hour}
              onChange={(e) =>
                setFormData({ ...formData, rate_limit_per_hour: parseInt(e.target.value) })
              }
              className={modalFieldClass}
              min="1"
              required
            />
          </div>
          <div className="space-y-2">
            <label className={modalSubLabelClass}>
              Per Day
            </label>
            <input
              type="number"
              value={formData.rate_limit_per_day}
              onChange={(e) =>
                setFormData({ ...formData, rate_limit_per_day: parseInt(e.target.value) })
              }
              className={modalFieldClass}
              min="1"
              required
            />
          </div>
        </div>
      </div>

      <div className="flex flex-col-reverse gap-3 border-t border-[#e6ddd2] pt-4 sm:flex-row sm:items-center">
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex min-w-[8rem] items-center justify-center rounded-[1rem] border border-[#ddd7ce] bg-white px-4 py-2.5 text-sm font-semibold text-[#5f564c] transition-colors hover:bg-[#fcfaf5]"
          disabled={isLoading}
        >
          Cancel
        </button>
        <button
          type="submit"
          className="inline-flex flex-1 items-center justify-center rounded-[1rem] bg-[#171717] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isLoading}
        >
          {isLoading ? 'Creating...' : 'Create API Key'}
        </button>
      </div>
    </form>
  );
}
