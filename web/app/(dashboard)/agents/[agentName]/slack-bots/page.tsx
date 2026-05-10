"use client";

import { useState, useEffect } from "react";
import { extractErrorMessage } from '@/lib/api/error'
import { useParams, useRouter } from "next/navigation";
import { Plus, Power, PowerOff, RefreshCw, Trash2, Settings, ExternalLink, Copy, Check, ChevronRight, Download } from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/lib/api/client";

interface SlackBot {
  id: string;
  agent_id: string;
  tenant_id: string;
  bot_name: string;
  slack_app_id: string;
  slack_workspace_id: string;
  slack_workspace_name: string | null;
  is_active: boolean;
  connection_status: string;
  connection_mode: string;
  webhook_url: string | null;
  last_connected_at: string | null;
  created_at: string;
  updated_at: string;
}

export default function SlackBotsPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;

  const [bots, setBots] = useState<SlackBot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [manifestLoading, setManifestLoading] = useState(false);

  const handleDownloadManifest = async () => {
    if (!agentId) return;
    try {
      setManifestLoading(true);
      const blob = await apiClient.downloadSlackManifest(agentId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `slack-manifest-${agentName}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success("Manifest downloaded!");
    } catch {
      toast.error("Failed to download manifest");
    } finally {
      setManifestLoading(false);
    }
  };

  const handleCopyWebhookUrl = async (botId: string, webhookUrl: string) => {
    try {
      await navigator.clipboard.writeText(webhookUrl);
      setCopiedId(botId);
      toast.success("Webhook URL copied!");
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      toast.error("Failed to copy URL");
    }
  };

  useEffect(() => {
    loadBots();
  }, [agentName]);

  const loadBots = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // First get the agent to get its ID
      const agent = await apiClient.getAgent(agentName);
      setAgentId(agent.id);

      // Then get bots for this agent
      const botsData = await apiClient.getSlackBots(agent.id);
      setBots(botsData);
    } catch (err: any) {
      console.error("Error loading Slack bots:", err);
      setError(err.response?.data?.message || "Failed to load Slack bots");
    } finally {
      setLoading(false);
    }
  };

  // Helper to wait for status change with polling
  const waitForStatusChange = async (botId: string, expectedStatus: string, maxWait = 5000): Promise<boolean> => {
    const startTime = Date.now();
    while (Date.now() - startTime < maxWait) {
      await new Promise(resolve => setTimeout(resolve, 500));
      try {
        const status = await apiClient.getSlackBotStatus(botId);
        if (status.connection_status === expectedStatus) {
          return true;
        }
      } catch {
        // Ignore errors during polling
      }
    }
    return false;
  };

  const handleStartBot = async (botId: string) => {
    try {
      setActionLoading(botId);
      await apiClient.startSlackBot(botId);
      toast.success("Bot starting...");
      // Wait for worker to update status
      const success = await waitForStatusChange(botId, "connected");
      if (success) {
        toast.success("Bot connected!");
      }
      await loadBots();
    } catch (err: any) {
      console.error("Error starting bot:", err);
      toast.error(extractErrorMessage(err, "Failed to start bot"))
    } finally {
      setActionLoading(null);
    }
  };

  const handleStopBot = async (botId: string) => {
    try {
      setActionLoading(botId);
      await apiClient.stopSlackBot(botId);
      toast.success("Bot stopping...");
      // Wait for worker to update status
      await waitForStatusChange(botId, "disconnected");
      await loadBots();
    } catch (err: any) {
      console.error("Error stopping bot:", err);
      toast.error(extractErrorMessage(err, "Failed to stop bot"))
    } finally {
      setActionLoading(null);
    }
  };

  const handleRestartBot = async (botId: string) => {
    try {
      setActionLoading(botId);
      await apiClient.restartSlackBot(botId);
      toast.success("Bot restarting...");
      // Wait for worker to update status
      await waitForStatusChange(botId, "connected");
      await loadBots();
    } catch (err: any) {
      console.error("Error restarting bot:", err);
      toast.error(extractErrorMessage(err, "Failed to restart bot"))
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
      await apiClient.deleteSlackBot(botId);
      toast.success("Bot deleted successfully");
      await loadBots();
    } catch (err: any) {
      console.error("Error deleting bot:", err);
      toast.error(extractErrorMessage(err, "Failed to delete bot"))
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "connected":
        return "text-emerald-600 bg-emerald-50";
      case "disconnected":
        return "text-red-600 bg-red-50";
      case "connecting":
        return "text-red-600 bg-red-50";
      default:
        return "text-gray-600 bg-gray-50";
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50/60 via-white to-rose-50/40 p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 text-sm mb-4">
          <button
            onClick={() => router.push("/agents")}
            className="text-gray-500 hover:text-primary-600 transition-colors"
          >
            Agents
          </button>
          <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
          <button
            onClick={() => router.push(`/agents/${encodeURIComponent(agentName)}/view`)}
            className="text-gray-500 hover:text-primary-600 transition-colors"
          >
            {agentName}
          </button>
          <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-gray-900 font-medium">Slack Bots</span>
        </div>

        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Slack Bots</h1>
            <p className="text-gray-600 mt-1 text-sm">
              Connect your agent <span className="font-semibold">{agentName}</span> to Slack workspaces
            </p>
          </div>
          <button
            onClick={() => router.push(`/agents/${agentName}/slack-bots/create`)}
            className="flex items-center gap-2 bg-gradient-to-r from-red-500 to-red-600 text-white px-3 py-2 rounded-lg hover:from-red-600 hover:to-red-700 transition-all text-xs font-medium shadow-sm"
          >
            <Plus size={16} />
            Add Slack Bot
          </button>
        </div>

        {/* Setup Guide */}
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 flex-1">
              <ExternalLink className="h-4 w-4 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-xs font-medium text-red-800">
                  Quick setup: create a Slack app from manifest
                </h3>
                <p className="mt-1 text-xs text-red-700">
                  Download the pre-configured manifest for this agent, then go to the Slack API Dashboard
                  → <strong>Create New App</strong> → <strong>From a manifest</strong> and paste it in.
                  All scopes and settings will be configured automatically.
                </p>
                <a
                  href="https://api.slack.com/apps"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center text-xs font-medium text-red-600 hover:text-red-700"
                >
                  Go to Slack API Dashboard
                  <ExternalLink className="ml-1 h-3 w-3" />
                </a>
              </div>
            </div>
            <button
              onClick={handleDownloadManifest}
              disabled={!agentId || manifestLoading}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {manifestLoading ? (
                <div className="h-3.5 w-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <Download className="h-3.5 w-3.5" />
              )}
              Download Manifest
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-6">
          <p className="text-xs text-red-800">{error}</p>
        </div>
      )}

        {/* Bots List */}
        {bots.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl shadow-sm border border-gray-200">
          <Power className="mx-auto h-10 w-10 text-red-400" />
          <h3 className="mt-3 text-base font-medium text-gray-900">No Slack bots</h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by creating a new Slack bot.
          </p>
          <div className="mt-5">
            <button
              onClick={() => router.push(`/agents/${agentName}/slack-bots/create`)}
              className="inline-flex items-center px-3 py-2 border border-transparent rounded-lg shadow-sm text-xs font-medium text-white bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 transition-all"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Slack Bot
            </button>
          </div>
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-200">
              <h2 className="text-base font-semibold text-gray-900">Your Slack Bots</h2>
            </div>
            <div className="divide-y divide-gray-200">
              {bots.map((bot) => (
                <div key={bot.id} className="p-5 hover:bg-red-50/50 transition-colors">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <h3 className="text-base font-medium text-gray-900 truncate">
                          {bot.bot_name}
                        </h3>
                        {/* Event Mode bots are always "connected" when active */}
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            bot.connection_mode === "event"
                              ? "text-emerald-600 bg-emerald-50"
                              : getStatusColor(bot.connection_status)
                          }`}
                        >
                          {bot.connection_mode === "event" ? "connected" : bot.connection_status}
                        </span>
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center text-xs text-gray-500 gap-x-3 gap-y-1">
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          bot.connection_mode === "event"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-gray-100 text-gray-600"
                        }`}>
                          {bot.connection_mode === "event" ? "Event Mode" : "Socket Mode"}
                        </span>
                        <span>•</span>
                        <span>
                          Workspace: {bot.slack_workspace_name || bot.slack_workspace_id || "Not connected"}
                        </span>
                        <span>•</span>
                        <span>App ID: {bot.slack_app_id}</span>
                        <span>•</span>
                        <span>Last connected: {formatDate(bot.last_connected_at)}</span>
                      </div>

                      {/* Webhook URL for Event Mode */}
                      {bot.connection_mode === "event" && bot.webhook_url && (
                        <div className="mt-3 flex items-center gap-2 p-2.5 bg-blue-50 border border-blue-100 rounded-lg">
                          <ExternalLink className="h-4 w-4 text-blue-600 flex-shrink-0" />
                          <code className="flex-1 text-xs font-mono text-blue-800 truncate" title={bot.webhook_url}>
                            {bot.webhook_url}
                          </code>
                          <button
                            onClick={() => handleCopyWebhookUrl(bot.id, bot.webhook_url!)}
                            className="flex-shrink-0 p-1.5 hover:bg-blue-100 rounded transition-colors"
                            title="Copy webhook URL"
                          >
                            {copiedId === bot.id ? (
                              <Check className="h-4 w-4 text-emerald-600" />
                            ) : (
                              <Copy className="h-4 w-4 text-blue-600" />
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 ml-4">
                      {/* Socket Mode bots need start/stop/restart controls */}
                      {bot.connection_mode === "socket" && (
                        <>
                          {bot.connection_status === "connected" ? (
                            <button
                              onClick={() => handleStopBot(bot.id)}
                              disabled={actionLoading === bot.id}
                              className="p-2 text-red-600 hover:bg-red-100 rounded-lg transition-colors disabled:opacity-50"
                              title="Stop bot"
                            >
                              <PowerOff size={16} />
                            </button>
                          ) : (
                            <button
                              onClick={() => handleStartBot(bot.id)}
                              disabled={actionLoading === bot.id}
                              className="p-2 text-emerald-600 hover:bg-emerald-100 rounded-lg transition-colors disabled:opacity-50"
                              title="Start bot"
                            >
                              <Power size={16} />
                            </button>
                          )}
                          <button
                            onClick={() => handleRestartBot(bot.id)}
                            disabled={actionLoading === bot.id}
                            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
                            title="Restart bot"
                          >
                            <RefreshCw size={16} />
                          </button>
                        </>
                      )}
                      {/* Event Mode bots are always "on" - show active indicator */}
                      {bot.connection_mode === "event" && (
                        <span className="px-2 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 rounded-lg border border-emerald-200">
                          Active
                        </span>
                      )}
                      <button
                        onClick={() =>
                          router.push(`/agents/${agentName}/slack-bots/${bot.id}/edit`)
                        }
                        className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                        title="Edit bot"
                      >
                        <Settings size={16} />
                      </button>
                      <button
                        onClick={() => handleDeleteBot(bot.id, bot.bot_name)}
                        disabled={actionLoading === bot.id}
                        className="p-2 text-red-600 hover:bg-red-100 rounded-lg transition-colors disabled:opacity-50"
                        title="Delete bot"
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
    </div>
  );
}
