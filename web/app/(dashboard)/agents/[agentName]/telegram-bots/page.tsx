"use client";

import { useState, useEffect } from "react";
import { extractErrorMessage } from "@/lib/api/error";
import { useParams, useRouter } from "next/navigation";
import {
  Plus,
  Power,
  PowerOff,
  RefreshCw,
  Trash2,
  Settings,
  ExternalLink,
  MessageCircle,
  Send,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/lib/api/client";
import AgentPageShell, { AgentPagePanel } from "@/components/agents/AgentPageShell";

interface TelegramBot {
  id: string;
  agent_id: string;
  bot_name: string;
  bot_username: string | null;
  telegram_bot_id: number | null;
  use_webhook: boolean;
  is_active: boolean;
  connection_status: string;
  last_connected_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export default function TelegramBotsPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;

  const [bots, setBots] = useState<TelegramBot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    loadBots();
  }, [agentName]);

  const loadBots = async () => {
    try {
      setLoading(true);
      setError(null);

      const agent = await apiClient.getAgent(agentName);
      const agentId = agent.id;
      const botsData = await apiClient.getTelegramBots(agentId);
      setBots(botsData);
    } catch (err: any) {
      console.error("Error loading Telegram bots:", err);
      setError(err?.response?.data?.message || "Failed to load Telegram bots");
    } finally {
      setLoading(false);
    }
  };

  const handleStartBot = async (botId: string) => {
    try {
      setActionLoading(botId);
      await apiClient.startTelegramBot(botId);
      toast.success("Bot started");
      await loadBots();
    } catch (err: any) {
      console.error("Error starting bot:", err);
      toast.error(extractErrorMessage(err, "Failed to start bot"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleStopBot = async (botId: string) => {
    try {
      setActionLoading(botId);
      await apiClient.stopTelegramBot(botId);
      toast.success("Bot stopped");
      await loadBots();
    } catch (err: any) {
      console.error("Error stopping bot:", err);
      toast.error(extractErrorMessage(err, "Failed to stop bot"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleRestartBot = async (botId: string) => {
    try {
      setActionLoading(botId);
      await apiClient.restartTelegramBot(botId);
      toast.success("Bot restarted");
      await loadBots();
    } catch (err: any) {
      console.error("Error restarting bot:", err);
      toast.error(extractErrorMessage(err, "Failed to restart bot"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteBot = async (botId: string, botName: string) => {
    if (!confirm(`Are you sure you want to delete the bot "${botName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setActionLoading(botId);
      await apiClient.deleteTelegramBot(botId);
      toast.success("Bot deleted");
      await loadBots();
    } catch (err: any) {
      console.error("Error deleting bot:", err);
      toast.error(extractErrorMessage(err, "Failed to delete bot"));
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusClasses = (status: string) => {
    switch (status) {
      case "connected":
        return "border-[#cfe6d9] bg-[#e8f4ee] text-[#2d8b69]";
      case "error":
        return "border-[#ead8e1] bg-[#f6edf1] text-[#8b5a74]";
      case "disconnected":
      default:
        return "border-black/10 bg-white/80 text-gray-600";
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#171717]"></div>
      </div>
    );
  }

  const connectedBots = bots.filter((bot) => bot.connection_status === "connected").length;
  const webhookBots = bots.filter((bot) => bot.use_webhook).length;

  return (
    <AgentPageShell
      agentName={agentName}
      title="Telegram Bots"
      description={
        <>
          Connect your agent <span className="font-semibold text-gray-900">{agentName}</span> to Telegram conversations and channels.
        </>
      }
      icon={Send}
      badge="Telegram Channel"
      actions={
        <button
          onClick={() => router.push(`/agents/${agentName}/telegram-bots/create`)}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
        >
          <Plus size={16} />
          Add Telegram Bot
        </button>
      }
    >
      <AgentPagePanel className="mb-5 p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[1rem] border border-black/10 bg-[#f1eadc]">
            <MessageCircle className="h-4 w-4 text-[#171717]" />
          </div>
          <div className="flex-1">
            <h3 className="mb-2 text-sm font-semibold text-gray-950">
              Need help setting up a Telegram bot?
            </h3>
            <div className="space-y-2 text-xs leading-6 text-gray-600">
              <p>
                Create a bot with <strong className="text-gray-900">BotFather</strong> on Telegram to get your bot token and username.
              </p>
              <a
                href="https://core.telegram.org/bots#botfather"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-semibold text-[#171717] transition-colors hover:text-black"
              >
                View BotFather documentation
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
        </div>
      </AgentPagePanel>

      {error && (
        <div className="mb-5 rounded-[1.25rem] border border-[#ead8e1] bg-[#f8ecef] px-4 py-4">
          <p className="text-xs text-[#8b5a74]">{error}</p>
        </div>
      )}

      <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-[1.35rem] border border-black/10 bg-white/85 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.04)]">
          <div className="text-xs text-gray-600">Total Bots</div>
          <div className="mt-1 text-2xl font-bold text-gray-900">{bots.length}</div>
        </div>
        <div className="rounded-[1.35rem] border border-[#cfe6d9] bg-[#e8f4ee] p-4 shadow-[0_18px_40px_rgba(0,0,0,0.03)]">
          <div className="text-xs text-gray-600">Connected</div>
          <div className="mt-1 text-2xl font-bold text-[#2d8b69]">{connectedBots}</div>
        </div>
        <div className="rounded-[1.35rem] border border-[#d7e6ea] bg-[#edf4f6] p-4 shadow-[0_18px_40px_rgba(0,0,0,0.03)]">
          <div className="text-xs text-gray-600">Webhook Mode</div>
          <div className="mt-1 text-2xl font-bold text-[#486c77]">{webhookBots}</div>
        </div>
      </div>

      {bots.length === 0 ? (
        <AgentPagePanel className="border-dashed py-12 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.4rem] bg-[#f1eadc]">
            <Send className="h-8 w-8 text-[#171717]" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-gray-950">No Telegram bots</h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by creating your first Telegram bot.
          </p>
          <button
            onClick={() => router.push(`/agents/${agentName}/telegram-bots/create`)}
            className="mt-5 inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
          >
            <Plus className="h-4 w-4" />
            Add Telegram Bot
          </button>
        </AgentPagePanel>
      ) : (
        <div className="space-y-4">
          {bots.map((bot) => (
            <AgentPagePanel key={bot.id} className="p-5 transition-shadow hover:shadow-[0_24px_56px_rgba(0,0,0,0.08)]">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-semibold text-gray-900">{bot.bot_name}</h3>
                    {bot.bot_username && (
                      <span className="text-sm text-gray-500">@{bot.bot_username}</span>
                    )}
                    <span
                      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${getStatusClasses(bot.connection_status)}`}
                    >
                      {bot.connection_status}
                    </span>
                  </div>

                  <div className="space-y-2 text-xs text-gray-600">
                    <div className="flex flex-wrap items-center gap-2">
                      {bot.telegram_bot_id && <span>Bot ID: {bot.telegram_bot_id}</span>}
                      {bot.telegram_bot_id && <span className="text-black/20">•</span>}
                      <span>Mode: {bot.use_webhook ? "Webhook" : "Long Polling"}</span>
                      <span className="text-black/20">•</span>
                      <span>Last connected: {formatDate(bot.last_connected_at)}</span>
                    </div>
                    {bot.last_error && (
                      <p className="text-[#8b5a74]">Error: {bot.last_error}</p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  {bot.connection_status === "connected" ? (
                    <button
                      onClick={() => handleStopBot(bot.id)}
                      disabled={actionLoading === bot.id}
                      className="rounded-full p-2 text-[#8b5a74] transition-colors hover:bg-[#f8ecef] hover:text-[#6f435b] disabled:opacity-50"
                      title="Stop bot"
                    >
                      <PowerOff size={16} />
                    </button>
                  ) : (
                    <button
                      onClick={() => handleStartBot(bot.id)}
                      disabled={actionLoading === bot.id}
                      className="rounded-full p-2 text-[#2d8b69] transition-colors hover:bg-[#e8f4ee] hover:text-[#246f54] disabled:opacity-50"
                      title="Start bot"
                    >
                      <Power size={16} />
                    </button>
                  )}
                  <button
                    onClick={() => handleRestartBot(bot.id)}
                    disabled={actionLoading === bot.id}
                    className="rounded-full p-2 text-[#486c77] transition-colors hover:bg-[#edf4f6] hover:text-[#36535c] disabled:opacity-50"
                    title="Restart bot"
                  >
                    <RefreshCw size={16} />
                  </button>
                  <button
                    onClick={() => router.push(`/agents/${agentName}/telegram-bots/${bot.id}/edit`)}
                    className="rounded-full p-2 text-gray-500 transition-colors hover:bg-[#fcfaf5] hover:text-gray-900"
                    title="Edit bot"
                  >
                    <Settings size={16} />
                  </button>
                  <button
                    onClick={() => handleDeleteBot(bot.id, bot.bot_name)}
                    disabled={actionLoading === bot.id}
                    className="rounded-full p-2 text-[#8b5a74] transition-colors hover:bg-[#f8ecef] hover:text-[#6f435b] disabled:opacity-50"
                    title="Delete bot"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </AgentPagePanel>
          ))}
        </div>
      )}
    </AgentPageShell>
  );
}
