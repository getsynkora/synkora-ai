"use client";

import { useState, useEffect } from "react";
import { extractErrorMessage } from '@/lib/api/error'
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, AlertCircle, ExternalLink, Copy, Check, Info } from "lucide-react";
import { apiClient } from "@/lib/api/client";

interface SlackBot {
  id: string;
  bot_name: string;
  slack_app_id: string;
  slack_workspace_id: string | null;
  slack_workspace_name: string | null;
  connection_mode: string;
  connection_status: string;
  webhook_url: string | null;
  is_active: boolean;
  allow_external_shared_channels: boolean;
}

export default function EditSlackBotPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;
  const botId = params.botId as string;

  const [bot, setBot] = useState<SlackBot | null>(null);
  const [formData, setFormData] = useState({
    bot_name: "",
    slack_bot_token: "",
    slack_app_token: "",
    signing_secret: "",
    allow_external_shared_channels: false,
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadBot();
  }, [botId]);

  const loadBot = async () => {
    try {
      setLoading(true);
      setError(null);
      const botData = await apiClient.getSlackBot(botId);
      setBot(botData);

      setFormData({
        bot_name: botData.bot_name || "",
        slack_bot_token: "", // Don't populate for security
        slack_app_token: "", // Don't populate for security
        signing_secret: "", // Don't populate for security
        allow_external_shared_channels: botData.allow_external_shared_channels ?? false,
      });
    } catch (err: any) {
      console.error("Error loading bot:", err);
      setError(extractErrorMessage(err, "Failed to load bot"))
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      // Only include fields that have values
      const updateData: any = {
        bot_name: formData.bot_name,
        allow_external_shared_channels: formData.allow_external_shared_channels,
      };

      // Only update tokens if they were changed
      if (formData.slack_bot_token) {
        updateData.slack_bot_token = formData.slack_bot_token;
      }
      if (formData.slack_app_token) {
        updateData.slack_app_token = formData.slack_app_token;
      }
      if (formData.signing_secret) {
        updateData.signing_secret = formData.signing_secret;
      }

      await apiClient.updateSlackBot(botId, updateData);

      // Redirect back to bots list
      router.push(`/agents/${agentName}/slack-bots`);
    } catch (err: any) {
      console.error("Error updating bot:", err);
      setError(extractErrorMessage(err, "Failed to update bot"))
      setSaving(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.checked,
    });
  };

  const handleCopyWebhookUrl = async () => {
    if (bot?.webhook_url) {
      await navigator.clipboard.writeText(bot.webhook_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-600"></div>
      </div>
    );
  }

  const isEventMode = bot?.connection_mode === "event";

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50/60 via-white to-rose-50/40 p-4 md:p-6">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={() => router.back()}
            className="p-2 hover:bg-white/80 rounded-lg transition-colors border border-gray-200"
          >
            <ArrowLeft className="h-5 w-5 text-gray-600" />
          </button>
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Edit Slack Bot</h1>
            <p className="text-sm text-gray-600">
              Update configuration for <span className="font-medium">{bot?.bot_name}</span>
            </p>
          </div>
        </div>

        {/* Bot Info Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-6">
          <div className="flex items-start justify-between">
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span className={`px-2.5 py-1 text-xs rounded-full font-medium ${
                  isEventMode
                    ? "bg-blue-100 text-blue-700"
                    : "bg-emerald-100 text-emerald-700"
                }`}>
                  {isEventMode ? "Event Mode" : "Socket Mode"}
                </span>
                {/* Event Mode bots are always "connected" when active */}
                <span className={`px-2.5 py-1 text-xs rounded-full font-medium ${
                  isEventMode || bot?.connection_status === "connected"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-gray-100 text-gray-600"
                }`}>
                  {isEventMode ? "connected" : (bot?.connection_status || "disconnected")}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">App ID:</span>
                  <span className="ml-2 font-mono text-gray-900">{bot?.slack_app_id}</span>
                </div>
                <div>
                  <span className="text-gray-500">Workspace:</span>
                  <span className="ml-2 text-gray-900">{bot?.slack_workspace_name || bot?.slack_workspace_id || "Not connected"}</span>
                </div>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-500">
                {isEventMode ? "HTTP webhooks" : "WebSocket connection"}
              </p>
            </div>
          </div>
        </div>

        {/* Webhook URL for Event Mode */}
        {isEventMode && bot?.webhook_url && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 mb-6">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <ExternalLink className="h-5 w-5 text-blue-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-blue-900 mb-1">
                  Webhook URL
                </h3>
                <p className="text-xs text-blue-700 mb-3">
                  Add this URL to your Slack app's Event Subscriptions settings
                </p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs bg-white px-3 py-2.5 rounded-lg border border-blue-200 font-mono text-blue-900 break-all">
                    {bot.webhook_url}
                  </code>
                  <button
                    onClick={handleCopyWebhookUrl}
                    className="flex-shrink-0 p-2.5 bg-white hover:bg-blue-100 rounded-lg transition-colors border border-blue-200"
                    title="Copy webhook URL"
                  >
                    {copied ? (
                      <Check className="h-4 w-4 text-emerald-600" />
                    ) : (
                      <Copy className="h-4 w-4 text-blue-600" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
              <p className="text-sm text-red-800">{error}</p>
            </div>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white shadow-sm rounded-xl border border-gray-200">
          <div className="p-6 space-y-5">
            {/* Security Notice */}
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <Info className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-medium text-amber-900">Security Notice</h4>
                  <p className="text-xs text-amber-700 mt-0.5">
                    Existing tokens are not displayed. Leave token fields empty to keep current values.
                  </p>
                </div>
              </div>
            </div>

            {/* Bot Name */}
            <div>
              <label htmlFor="bot_name" className="block text-sm font-medium text-gray-700 mb-1.5">
                Bot Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="bot_name"
                name="bot_name"
                value={formData.bot_name}
                onChange={handleChange}
                required
                className="block w-full px-3 py-2.5 rounded-lg border border-gray-300 shadow-sm focus:border-red-500 focus:ring-1 focus:ring-red-500 text-sm"
                placeholder="My Agent Bot"
              />
              <p className="mt-1.5 text-xs text-gray-500">
                A friendly name to identify this bot
              </p>
            </div>

            {/* Bot Token */}
            <div>
              <label htmlFor="slack_bot_token" className="block text-sm font-medium text-gray-700 mb-1.5">
                Bot User OAuth Token
              </label>
              <input
                type="password"
                id="slack_bot_token"
                name="slack_bot_token"
                value={formData.slack_bot_token}
                onChange={handleChange}
                className="block w-full px-3 py-2.5 rounded-lg border border-gray-300 shadow-sm focus:border-red-500 focus:ring-1 focus:ring-red-500 text-sm font-mono"
                placeholder="Leave empty to keep current token"
              />
              <p className="mt-1.5 text-xs text-gray-500">
                Enter a new token to update it (starts with xoxb-)
              </p>
            </div>

            {/* Socket Mode: App-Level Token */}
            {!isEventMode && (
              <div>
                <label htmlFor="slack_app_token" className="block text-sm font-medium text-gray-700 mb-1.5">
                  App-Level Token
                </label>
                <input
                  type="password"
                  id="slack_app_token"
                  name="slack_app_token"
                  value={formData.slack_app_token}
                  onChange={handleChange}
                  className="block w-full px-3 py-2.5 rounded-lg border border-gray-300 shadow-sm focus:border-red-500 focus:ring-1 focus:ring-red-500 text-sm font-mono"
                  placeholder="Leave empty to keep current token"
                />
                <p className="mt-1.5 text-xs text-gray-500">
                  Enter a new token to update it (starts with xapp-)
                </p>
              </div>
            )}

            {/* Event Mode: Signing Secret */}
            {isEventMode && (
              <div>
                <label htmlFor="signing_secret" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Signing Secret
                </label>
                <input
                  type="password"
                  id="signing_secret"
                  name="signing_secret"
                  value={formData.signing_secret}
                  onChange={handleChange}
                  className="block w-full px-3 py-2.5 rounded-lg border border-gray-300 shadow-sm focus:border-red-500 focus:ring-1 focus:ring-red-500 text-sm font-mono"
                  placeholder="Leave empty to keep current secret"
                />
                <p className="mt-1.5 text-xs text-gray-500">
                  Enter a new signing secret to update it
                </p>
              </div>
            )}

            {/* External Shared Channels Toggle */}
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  name="allow_external_shared_channels"
                  checked={formData.allow_external_shared_channels}
                  onChange={handleCheckboxChange}
                  className="mt-0.5 h-4 w-4 rounded border-gray-300 text-red-600 focus:ring-red-500"
                />
                <div>
                  <span className="text-sm font-medium text-gray-900">
                    Allow in externally-shared channels (Slack Connect)
                  </span>
                  <p className="mt-1 text-xs text-gray-500">
                    When off (recommended), the bot won't respond in channels shared with another
                    company's Slack workspace. Turn this on only if you intentionally want this bot
                    available to external Slack Connect members.
                  </p>
                </div>
              </label>
            </div>

            {/* Help Link */}
            <div className="pt-2">
              <a
                href="https://api.slack.com/apps"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-red-600 hover:text-red-700 font-medium"
              >
                <ExternalLink className="h-4 w-4" />
                Open Slack App Settings
              </a>
            </div>
          </div>

          {/* Form Actions */}
          <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-end gap-3 rounded-b-xl">
            <button
              type="button"
              onClick={() => router.back()}
              className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg hover:from-red-600 hover:to-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm font-medium"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
