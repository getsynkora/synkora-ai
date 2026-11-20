"use client";

import { useState, useEffect } from "react";
import { extractErrorMessage } from '@/lib/api/error'
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, MessageCircle } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import Link from "next/link";

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

export default function EditTelegramBotPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;
  const botId = params.botId as string;

  const [bot, setBot] = useState<TelegramBot | null>(null);
  const [formData, setFormData] = useState({
    bot_name: "",
    bot_token: "",
    use_webhook: false,
    webhook_url: "",
    is_active: true,
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadBot();
  }, [botId]);

  const loadBot = async () => {
    try {
      setLoading(true);
      setError(null);
      const botData = await apiClient.getTelegramBot(botId);
      setBot(botData);
      setFormData({
        bot_name: botData.bot_name,
        bot_token: "", // Don't pre-fill token for security
        use_webhook: botData.use_webhook,
        webhook_url: "",
        is_active: botData.is_active,
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

    try {
      setSaving(true);
      setError(null);

      const updateData: any = {
        bot_name: formData.bot_name,
        is_active: formData.is_active,
        use_webhook: formData.use_webhook,
      };

      // Only include token if provided
      if (formData.bot_token.trim()) {
        updateData.bot_token = formData.bot_token;
      }

      if (formData.use_webhook && formData.webhook_url) {
        updateData.webhook_url = formData.webhook_url;
      }

      await apiClient.updateTelegramBot(botId, updateData);
      router.push(`/agents/${agentName}/telegram-bots`);
    } catch (err: any) {
      console.error("Error updating bot:", err);
      setError(extractErrorMessage(err, "Failed to update bot"))
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="motion-safe:animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!bot) {
    return (
      <div className="min-h-screen p-4 md:p-6">
        <div className="max-w-2xl mx-auto">
          <div className="bg-blush-wash border border-blush rounded-lg p-4">
            <p className="text-wine">Bot not found</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 md:p-6">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <Link
            href={`/agents/${agentName}/telegram-bots`}
            className="inline-flex items-center text-primary-600 hover:text-primary-700 text-sm font-medium mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Telegram Bots
          </Link>
          <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Edit Telegram Bot</h1>
          <p className="text-ink-soft mt-1 text-sm">
            Update settings for <span className="font-semibold">{bot.bot_name}</span>
            {bot.bot_username && <span className="text-ink-mute"> (@{bot.bot_username})</span>}
          </p>
        </div>

        {/* Bot Info */}
        <div className="bg-primary-50 border border-primary-200 rounded-lg p-4 mb-6">
          <div className="flex items-start gap-3">
            <MessageCircle className="h-5 w-5 text-primary-600 mt-0.5" />
            <div className="text-sm">
              <p className="text-primary-800">
                <span className="font-medium">Status:</span>{" "}
                <span className={bot.connection_status === "connected" ? "text-leaf" : "text-ink-soft"}>
                  {bot.connection_status}
                </span>
              </p>
              {bot.telegram_bot_id && (
                <p className="text-primary-700 mt-1">Bot ID: {bot.telegram_bot_id}</p>
              )}
              {bot.last_error && (
                <p className="text-danger mt-1">Last error: {bot.last_error}</p>
              )}
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-blush-wash border border-blush rounded-lg p-3 mb-6">
            <p className="text-sm text-wine">{error}</p>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-line p-6">
            <h2 className="text-lg font-semibold text-ink mb-4">Bot Settings</h2>

            {/* Bot Name */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-ink-soft mb-1">
                Display Name <span className="text-leaf">*</span>
              </label>
              <input
                type="text"
                value={formData.bot_name}
                onChange={(e) => setFormData({ ...formData, bot_name: e.target.value })}
                className="w-full px-3 py-2 border border-taupe rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                required
              />
            </div>

            {/* Bot Token (optional update) */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-ink-soft mb-1">
                New Bot Token (optional)
              </label>
              <input
                type="password"
                value={formData.bot_token}
                onChange={(e) => setFormData({ ...formData, bot_token: e.target.value })}
                placeholder="Leave empty to keep existing token"
                className="w-full px-3 py-2 border border-taupe rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
              <p className="mt-1 text-xs text-ink-mute">
                Only enter a new token if you want to change it
              </p>
            </div>

            {/* Active Status */}
            <div className="mb-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="h-4 w-4 text-primary-600 border-taupe rounded focus:ring-primary-500"
                />
                <span className="text-sm text-ink-soft">Bot is active</span>
              </label>
              <p className="mt-1 text-xs text-ink-mute ml-6">
                Inactive bots will not respond to messages
              </p>
            </div>

            {/* Webhook Mode */}
            <div className="border-t border-line pt-4 mt-4">
              <h3 className="text-sm font-medium text-ink-soft mb-2">Connection Mode</h3>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.use_webhook}
                  onChange={(e) => setFormData({ ...formData, use_webhook: e.target.checked })}
                  className="h-4 w-4 text-primary-600 border-taupe rounded focus:ring-primary-500"
                />
                <span className="text-sm text-ink-soft">Use webhook instead of long polling</span>
              </label>

              {formData.use_webhook && (
                <div className="mt-3 ml-6">
                  <label className="block text-sm font-medium text-ink-soft mb-1">
                    Webhook URL
                  </label>
                  <input
                    type="url"
                    value={formData.webhook_url}
                    onChange={(e) => setFormData({ ...formData, webhook_url: e.target.value })}
                    placeholder="https://your-domain.com/webhook/telegram"
                    className="w-full px-3 py-2 border border-taupe rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  />
                </div>
              )}
            </div>
          </div>

          {/* Submit Buttons */}
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-2 bg-ink hover:bg-ink/85 text-white rounded-lg text-sm font-medium hover:from-primary-600 hover:to-primary-700 transition-[color,background-color,border-color,box-shadow,opacity,transform] disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save Changes"}
            </button>
            <Link
              href={`/agents/${agentName}/telegram-bots`}
              className="px-4 py-2 border border-taupe text-ink-soft rounded-lg text-sm font-medium hover:bg-cream transition-colors text-center"
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
