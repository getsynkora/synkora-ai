"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Power, PowerOff, Settings, Trash2, ExternalLink, MessageCircle, Users, ChevronRight } from "lucide-react";
import { useWhatsAppBots, useTeamsBots } from "@/hooks/useMessagingBots";
import type { WhatsAppBot, TeamsBot } from "@/types/messaging-bots";
import { apiClient } from "@/lib/api/client";
import AgentPageShell from '@/components/agents/AgentPageShell'

export default function MessagingBotsPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;
  
  const [agentId, setAgentId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load agent ID first
  useEffect(() => {
    const loadAgent = async () => {
      try {
        const agent = await apiClient.getAgent(agentName);
        setAgentId(agent.id);
      } catch (err: any) {
        console.error("Error loading agent:", err);
        setError(err.response?.data?.message || "Failed to load agent");
      } finally {
        setLoading(false);
      }
    };
    loadAgent();
  }, [agentName]);

  const {
    bots: whatsappBots,
    loading: whatsappLoading,
    error: whatsappError,
    toggleActive: toggleWhatsApp,
    deleteBot: deleteWhatsApp,
  } = useWhatsAppBots(agentId || undefined);

  const {
    bots: teamsBots,
    loading: teamsLoading,
    error: teamsError,
    toggleActive: toggleTeams,
    deleteBot: deleteTeams,
  } = useTeamsBots(agentId || undefined);

  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleToggleActive = async (type: "whatsapp" | "teams", bot: WhatsAppBot | TeamsBot) => {
    try {
      setActionLoading(bot.bot_id);
      if (type === "whatsapp") {
        await toggleWhatsApp(bot as WhatsAppBot);
      } else {
        await toggleTeams(bot as TeamsBot);
      }
    } catch (err: any) {
      alert(err.message || "Failed to toggle bot status");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (type: "whatsapp" | "teams", bot: WhatsAppBot | TeamsBot) => {
    if (
      !confirm(
        `Are you sure you want to delete the ${type === "whatsapp" ? "WhatsApp" : "Teams"} bot "${bot.bot_name}"? This action cannot be undone.`
      )
    ) {
      return;
    }

    try {
      setActionLoading(bot.bot_id);
      if (type === "whatsapp") {
        await deleteWhatsApp(bot.bot_id);
      } else {
        await deleteTeams(bot.bot_id);
      }
    } catch (err: any) {
      alert(err.message || "Failed to delete bot");
    } finally {
      setActionLoading(null);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleString();
  };

  if (loading || whatsappLoading || teamsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#171717]"></div>
      </div>
    );
  }

  const totalBots = whatsappBots.length + teamsBots.length;
  const activeBots = whatsappBots.filter((b: WhatsAppBot) => b.is_active).length + teamsBots.filter((b: TeamsBot) => b.is_active).length;

  return (
    <AgentPageShell
      agentName={agentName}
      title="Messaging Bots"
      description="Connect your agent to WhatsApp and Microsoft Teams."
      icon={MessageCircle}
      badge="Messaging Channels"
      actions={
        <>
          <button
            onClick={() => router.push(`/agents/${agentName}/messaging-bots/whatsapp/create`)}
            className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
          >
            <MessageCircle size={18} />
            Add WhatsApp Bot
          </button>
          <button
            onClick={() => router.push(`/agents/${agentName}/messaging-bots/teams/create`)}
            className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-white/80 px-4 py-3 text-sm font-semibold text-[#171717] transition-colors hover:bg-white"
          >
            <Users size={18} />
            Add Teams Bot
          </button>
        </>
      }
    >

        {/* Setup Guide */}
        <div className="mb-5 rounded-[1.45rem] border border-black/10 bg-[#fcfaf5] p-4">
          <div className="flex items-start">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[0.95rem] bg-[#f1eadc]">
              <ExternalLink className="h-4 w-4 text-[#171717]" />
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">Need help setting up messaging bots?</h3>
              <p className="mt-1 text-xs leading-6 text-gray-600">
                Follow our guides to configure WhatsApp Business API or Microsoft Teams Bot Framework.
              </p>
              <div className="mt-2 flex gap-4">
                <a
                  href="https://developers.facebook.com/docs/whatsapp/cloud-api"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-xs font-semibold text-[#171717] hover:text-black"
                >
                  WhatsApp Setup Guide
                  <ExternalLink className="ml-1 h-3 w-3" />
                </a>
                <a
                  href="https://dev.botframework.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-xs font-semibold text-[#171717] hover:text-black"
                >
                  Teams Bot Framework
                  <ExternalLink className="ml-1 h-3 w-3" />
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Error Messages */}
        {(error || whatsappError || teamsError) && (
          <div className="mb-5 rounded-[1.2rem] border border-[#ead8e1] bg-[#f8ecef] p-3">
            <p className="text-xs text-[#8b5a74]">{error || whatsappError || teamsError}</p>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6">
          <div className="rounded-[1.35rem] border border-black/10 bg-white/85 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.04)]">
            <div className="text-gray-600 text-xs">Total Bots</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">{totalBots}</div>
          </div>
          <div className="rounded-[1.35rem] border border-[#cfe6d9] bg-[#e8f4ee] p-4 shadow-[0_18px_40px_rgba(0,0,0,0.03)]">
            <div className="text-gray-600 text-xs">Active Bots</div>
            <div className="mt-1 text-2xl font-bold text-[#2d8b69]">{activeBots}</div>
          </div>
          <div className="rounded-[1.35rem] border border-[#ead8e1] bg-[#f6edf1] p-4 shadow-[0_18px_40px_rgba(0,0,0,0.03)]">
            <div className="text-gray-600 text-xs">WhatsApp</div>
            <div className="mt-1 text-2xl font-bold text-[#8b5a74]">{whatsappBots.length}</div>
          </div>
          <div className="rounded-[1.35rem] border border-[#d7e6ea] bg-[#edf4f6] p-4 shadow-[0_18px_40px_rgba(0,0,0,0.03)]">
            <div className="text-gray-600 text-xs">Teams</div>
            <div className="mt-1 text-2xl font-bold text-[#486c77]">{teamsBots.length}</div>
          </div>
        </div>

        {/* No Bots State */}
        {totalBots === 0 ? (
          <div className="rounded-[1.75rem] border border-dashed border-black/10 bg-white/85 py-10 text-center shadow-[0_18px_40px_rgba(0,0,0,0.04)]">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-[1.2rem] bg-[#f1eadc]">
              <MessageCircle className="h-7 w-7 text-[#171717]" />
            </div>
            <h3 className="mt-3 text-base font-semibold text-gray-950">No messaging bots</h3>
            <p className="mt-1 text-sm text-gray-500">Get started by creating your first WhatsApp or Teams bot.</p>
            <div className="mt-5 flex gap-2 justify-center">
              <button
                onClick={() => router.push(`/agents/${agentName}/messaging-bots/whatsapp/create`)}
                className="inline-flex items-center rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
              >
                <MessageCircle className="h-4 w-4 mr-2" />
                Add WhatsApp Bot
              </button>
              <button
                onClick={() => router.push(`/agents/${agentName}/messaging-bots/teams/create`)}
                className="inline-flex items-center rounded-[1rem] border border-black/10 bg-white px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#fcfaf5]"
              >
                <Users className="h-4 w-4 mr-2" />
                Add Teams Bot
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            {/* WhatsApp Bots */}
            {whatsappBots.length > 0 && (
              <div className="overflow-hidden rounded-[1.75rem] border border-black/10 bg-white/85 shadow-[0_18px_40px_rgba(0,0,0,0.04)]">
                <div className="border-b border-black/10 bg-[#f6edf1] px-5 py-4">
                  <div className="flex items-center gap-2">
                    <MessageCircle className="text-[#8b5a74]" size={20} />
                    <h2 className="text-base font-semibold text-gray-900">WhatsApp Bots</h2>
                    <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-[#8b5a74]">
                      {whatsappBots.length}
                    </span>
                  </div>
                </div>
                <div className="divide-y divide-black/10">
                  {whatsappBots.map((bot: WhatsAppBot) => (
                    <div key={bot.bot_id} className="p-5 transition-colors hover:bg-[#fcfaf5]">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center space-x-2">
                            <h3 className="text-sm font-medium text-gray-900 truncate">{bot.bot_name}</h3>
                            {bot.is_active ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                                Active
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                Inactive
                              </span>
                            )}
                          </div>
                          <div className="mt-1.5 flex flex-col sm:flex-row sm:flex-wrap sm:space-x-3 text-xs text-gray-500 gap-0.5">
                            <span>Phone: {bot.phone_number_id}</span>
                            <span className="hidden sm:inline">•</span>
                            <span>Created: {formatDate(bot.created_at)}</span>
                            {bot.last_message_at && (
                              <>
                                <span className="hidden sm:inline">•</span>
                                <span>Last message: {formatDate(bot.last_message_at)}</span>
                              </>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 ml-4">
                          {bot.is_active ? (
                            <button
                              onClick={() => handleToggleActive("whatsapp", bot)}
                              disabled={actionLoading === bot.bot_id}
                              className="rounded-lg p-2 text-[#8b5a74] transition-colors hover:bg-[#f8ecef] disabled:opacity-50"
                              title="Deactivate"
                            >
                              <PowerOff size={16} />
                            </button>
                          ) : (
                            <button
                              onClick={() => handleToggleActive("whatsapp", bot)}
                              disabled={actionLoading === bot.bot_id}
                              className="rounded-lg p-2 text-emerald-600 transition-colors hover:bg-emerald-50 disabled:opacity-50"
                              title="Activate"
                            >
                              <Power size={16} />
                            </button>
                          )}
                          <button
                            onClick={() =>
                              router.push(`/agents/${agentName}/messaging-bots/whatsapp/${bot.bot_id}/edit`)
                            }
                            className="rounded-lg p-2 text-gray-600 transition-colors hover:bg-[#fcfaf5]"
                            title="Edit"
                          >
                            <Settings size={16} />
                          </button>
                          <button
                            onClick={() => handleDelete("whatsapp", bot)}
                            disabled={actionLoading === bot.bot_id}
                            className="rounded-lg p-2 text-[#8b5a74] transition-colors hover:bg-[#f8ecef] disabled:opacity-50"
                            title="Delete"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Teams Bots */}
            {teamsBots.length > 0 && (
              <div className="overflow-hidden rounded-[1.75rem] border border-black/10 bg-white/85 shadow-[0_18px_40px_rgba(0,0,0,0.04)]">
                <div className="border-b border-black/10 bg-[#edf4f6] px-5 py-4">
                  <div className="flex items-center gap-2">
                    <Users className="text-[#486c77]" size={20} />
                    <h2 className="text-base font-semibold text-gray-900">Microsoft Teams Bots</h2>
                    <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-[#486c77]">
                      {teamsBots.length}
                    </span>
                  </div>
                </div>
                <div className="divide-y divide-black/10">
                  {teamsBots.map((bot: TeamsBot) => (
                    <div key={bot.bot_id} className="p-5 transition-colors hover:bg-[#fcfaf5]">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center space-x-2">
                            <h3 className="text-sm font-medium text-gray-900 truncate">{bot.bot_name}</h3>
                            {bot.is_active ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                                Active
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                Inactive
                              </span>
                            )}
                          </div>
                          <div className="mt-1.5 flex flex-col sm:flex-row sm:flex-wrap sm:space-x-3 text-xs text-gray-500 gap-0.5">
                            <span>App ID: {bot.app_id.substring(0, 20)}...</span>
                            <span className="hidden sm:inline">•</span>
                            <span>Created: {formatDate(bot.created_at)}</span>
                            {bot.last_message_at && (
                              <>
                                <span className="hidden sm:inline">•</span>
                                <span>Last message: {formatDate(bot.last_message_at)}</span>
                              </>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 ml-4">
                          {bot.is_active ? (
                            <button
                              onClick={() => handleToggleActive("teams", bot)}
                              disabled={actionLoading === bot.bot_id}
                              className="rounded-lg p-2 text-[#8b5a74] transition-colors hover:bg-[#f8ecef] disabled:opacity-50"
                              title="Deactivate"
                            >
                              <PowerOff size={16} />
                            </button>
                          ) : (
                            <button
                              onClick={() => handleToggleActive("teams", bot)}
                              disabled={actionLoading === bot.bot_id}
                              className="rounded-lg p-2 text-emerald-600 transition-colors hover:bg-emerald-50 disabled:opacity-50"
                              title="Activate"
                            >
                              <Power size={16} />
                            </button>
                          )}
                          <button
                            onClick={() =>
                              router.push(`/agents/${agentName}/messaging-bots/teams/${bot.bot_id}/edit`)
                            }
                            className="rounded-lg p-2 text-gray-600 transition-colors hover:bg-[#fcfaf5]"
                            title="Edit"
                          >
                            <Settings size={16} />
                          </button>
                          <button
                            onClick={() => handleDelete("teams", bot)}
                            disabled={actionLoading === bot.bot_id}
                            className="rounded-lg p-2 text-[#8b5a74] transition-colors hover:bg-[#f8ecef] disabled:opacity-50"
                            title="Delete"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
    </AgentPageShell>
  );
}
