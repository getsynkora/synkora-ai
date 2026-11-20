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
        <div className="h-8 w-8 motion-safe:animate-spin rounded-full border-b-2 border-ink"></div>
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
            className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
          >
            <MessageCircle size={18} />
            Add WhatsApp Bot
          </button>
          <button
            onClick={() => router.push(`/agents/${agentName}/messaging-bots/teams/create`)}
            className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-white/80 px-4 py-3 text-sm font-semibold text-ink transition-colors hover:bg-white"
          >
            <Users size={18} />
            Add Teams Bot
          </button>
        </>
      }
    >

        {/* Setup Guide */}
        <div className="mb-5 rounded-[1.45rem] border border-black/10 bg-cream p-4">
          <div className="flex items-start">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[0.95rem] bg-sand-deep">
              <ExternalLink className="h-4 w-4 text-ink" />
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-xs font-semibold text-bark">Need help setting up messaging bots?</h3>
              <p className="mt-1 text-xs leading-6 text-ink-soft">
                Follow our guides to configure WhatsApp Business API or Microsoft Teams Bot Framework.
              </p>
              <div className="mt-2 flex gap-4">
                <a
                  href="https://developers.facebook.com/docs/whatsapp/cloud-api"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-xs font-semibold text-ink hover:text-black"
                >
                  WhatsApp Setup Guide
                  <ExternalLink className="ml-1 h-3 w-3" />
                </a>
                <a
                  href="https://dev.botframework.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-xs font-semibold text-ink hover:text-black"
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
          <div className="mb-5 rounded-[1.2rem] border border-blush-wash bg-blush-wash p-3">
            <p className="text-xs text-plum">{error || whatsappError || teamsError}</p>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6">
          <div className="rounded-[1.35rem] border border-black/10 bg-white/85 p-4 shadow-soft">
            <div className="text-ink-soft text-xs">Total Bots</div>
            <div className="text-2xl font-bold text-ink mt-1">{totalBots}</div>
          </div>
          <div className="rounded-[1.35rem] border border-leaf-wash bg-leaf-wash p-4 shadow-soft">
            <div className="text-ink-soft text-xs">Active Bots</div>
            <div className="mt-1 text-2xl font-bold text-leaf">{activeBots}</div>
          </div>
          <div className="rounded-[1.35rem] border border-blush-wash bg-blush-wash p-4 shadow-soft">
            <div className="text-ink-soft text-xs">WhatsApp</div>
            <div className="mt-1 text-2xl font-bold text-plum">{whatsappBots.length}</div>
          </div>
          <div className="rounded-[1.35rem] border border-sky-wash bg-leaf-wash p-4 shadow-soft">
            <div className="text-ink-soft text-xs">Teams</div>
            <div className="mt-1 text-2xl font-bold text-steel">{teamsBots.length}</div>
          </div>
        </div>

        {/* No Bots State */}
        {totalBots === 0 ? (
          <div className="rounded-[1.75rem] border border-dashed border-black/10 bg-white/85 py-10 text-center shadow-soft">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-[1.2rem] bg-sand-deep">
              <MessageCircle className="h-7 w-7 text-ink" />
            </div>
            <h3 className="mt-3 text-base font-semibold text-ink">No messaging bots</h3>
            <p className="mt-1 text-sm text-ink-mute">Get started by creating your first WhatsApp or Teams bot.</p>
            <div className="mt-5 flex gap-2 justify-center">
              <button
                onClick={() => router.push(`/agents/${agentName}/messaging-bots/whatsapp/create`)}
                className="inline-flex items-center rounded-[1rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
              >
                <MessageCircle className="h-4 w-4 mr-2" />
                Add WhatsApp Bot
              </button>
              <button
                onClick={() => router.push(`/agents/${agentName}/messaging-bots/teams/create`)}
                className="inline-flex items-center rounded-[1rem] border border-black/10 bg-white px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-cream"
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
              <div className="overflow-hidden rounded-[1.75rem] border border-black/10 bg-white/85 shadow-soft">
                <div className="border-b border-black/10 bg-blush-wash px-5 py-4">
                  <div className="flex items-center gap-2">
                    <MessageCircle className="text-plum" size={20} />
                    <h2 className="text-base font-semibold text-ink">WhatsApp Bots</h2>
                    <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-plum">
                      {whatsappBots.length}
                    </span>
                  </div>
                </div>
                <div className="divide-y divide-black/10">
                  {whatsappBots.map((bot: WhatsAppBot) => (
                    <div key={bot.bot_id} className="p-5 transition-colors hover:bg-cream">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center space-x-2">
                            <h3 className="text-sm font-medium text-ink truncate">{bot.bot_name}</h3>
                            {bot.is_active ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-leaf-wash text-forest">
                                Active
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-sand text-ink">
                                Inactive
                              </span>
                            )}
                          </div>
                          <div className="mt-1.5 flex flex-col sm:flex-row sm:flex-wrap sm:space-x-3 text-xs text-ink-mute gap-0.5">
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
                              className="rounded-lg p-2 text-plum transition-colors hover:bg-sand-deep disabled:opacity-50"
                              title="Deactivate"
                            >
                              <PowerOff size={16} />
                            </button>
                          ) : (
                            <button
                              onClick={() => handleToggleActive("whatsapp", bot)}
                              disabled={actionLoading === bot.bot_id}
                              className="rounded-lg p-2 text-leaf transition-colors hover:bg-leaf-wash disabled:opacity-50"
                              title="Activate"
                            >
                              <Power size={16} />
                            </button>
                          )}
                          <button
                            onClick={() =>
                              router.push(`/agents/${agentName}/messaging-bots/whatsapp/${bot.bot_id}/edit`)
                            }
                            className="rounded-lg p-2 text-ink-soft transition-colors hover:bg-cream"
                            title="Edit"
                          >
                            <Settings size={16} />
                          </button>
                          <button
                            onClick={() => handleDelete("whatsapp", bot)}
                            disabled={actionLoading === bot.bot_id}
                            className="rounded-lg p-2 text-plum transition-colors hover:bg-sand-deep disabled:opacity-50"
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
              <div className="overflow-hidden rounded-[1.75rem] border border-black/10 bg-white/85 shadow-soft">
                <div className="border-b border-black/10 bg-leaf-wash px-5 py-4">
                  <div className="flex items-center gap-2">
                    <Users className="text-steel" size={20} />
                    <h2 className="text-base font-semibold text-ink">Microsoft Teams Bots</h2>
                    <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-steel">
                      {teamsBots.length}
                    </span>
                  </div>
                </div>
                <div className="divide-y divide-black/10">
                  {teamsBots.map((bot: TeamsBot) => (
                    <div key={bot.bot_id} className="p-5 transition-colors hover:bg-cream">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center space-x-2">
                            <h3 className="text-sm font-medium text-ink truncate">{bot.bot_name}</h3>
                            {bot.is_active ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-leaf-wash text-forest">
                                Active
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-sand text-ink">
                                Inactive
                              </span>
                            )}
                          </div>
                          <div className="mt-1.5 flex flex-col sm:flex-row sm:flex-wrap sm:space-x-3 text-xs text-ink-mute gap-0.5">
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
                              className="rounded-lg p-2 text-plum transition-colors hover:bg-sand-deep disabled:opacity-50"
                              title="Deactivate"
                            >
                              <PowerOff size={16} />
                            </button>
                          ) : (
                            <button
                              onClick={() => handleToggleActive("teams", bot)}
                              disabled={actionLoading === bot.bot_id}
                              className="rounded-lg p-2 text-leaf transition-colors hover:bg-leaf-wash disabled:opacity-50"
                              title="Activate"
                            >
                              <Power size={16} />
                            </button>
                          )}
                          <button
                            onClick={() =>
                              router.push(`/agents/${agentName}/messaging-bots/teams/${bot.bot_id}/edit`)
                            }
                            className="rounded-lg p-2 text-ink-soft transition-colors hover:bg-cream"
                            title="Edit"
                          >
                            <Settings size={16} />
                          </button>
                          <button
                            onClick={() => handleDelete("teams", bot)}
                            disabled={actionLoading === bot.bot_id}
                            className="rounded-lg p-2 text-plum transition-colors hover:bg-sand-deep disabled:opacity-50"
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
