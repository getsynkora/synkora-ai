"use client";

import { useState, useEffect } from "react";
import { extractErrorMessage } from "@/lib/api/error";
import { useParams, useRouter } from "next/navigation";
import {
  MessageCircle,
  ExternalLink,
  CheckCircle,
  AlertCircle,
  Send,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import AgentPageShell, { AgentPagePanel } from "@/components/agents/AgentPageShell";

interface TokenValidation {
  valid: boolean;
  message: string;
  bot_info?: {
    bot_id: number;
    username: string;
    name: string;
    can_join_groups: boolean;
    can_read_all_group_messages: boolean;
  };
}

const fieldClass =
  "w-full rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]";
const sectionTitleClass =
  "mb-1.5 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]";
const helperTextClass = "mt-1 text-xs text-gray-500";
const secondaryButtonClass =
  "rounded-[1rem] border border-black/10 bg-white/85 px-4 py-3 text-sm font-semibold text-gray-700 transition-colors hover:bg-white hover:text-[#171717]";
const primaryButtonClass =
  "inline-flex items-center justify-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50";

export default function CreateTelegramBotPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;

  const [formData, setFormData] = useState({
    bot_name: "",
    bot_token: "",
    use_webhook: false,
    webhook_url: "",
  });

  const [agentId, setAgentId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [tokenValidation, setTokenValidation] = useState<TokenValidation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAgent();
  }, [agentName]);

  const loadAgent = async () => {
    try {
      setPageLoading(true);
      const agent = await apiClient.getAgent(agentName);
      setAgentId(agent.id);
    } catch (err: any) {
      console.error("Error loading agent:", err);
      setError("Failed to load agent");
    } finally {
      setPageLoading(false);
    }
  };

  const handleValidateToken = async () => {
    if (!formData.bot_token.trim()) {
      setError("Please enter a bot token");
      return;
    }

    try {
      setValidating(true);
      setError(null);
      setTokenValidation(null);

      const result = await apiClient.validateTelegramToken(formData.bot_token);
      setTokenValidation(result);

      if (result.valid && result.bot_info?.name && !formData.bot_name) {
        setFormData((prev) => ({
          ...prev,
          bot_name: result.bot_info!.name,
        }));
      }
    } catch (err: any) {
      console.error("Error validating token:", err);
      setError(extractErrorMessage(err, "Failed to validate token"));
    } finally {
      setValidating(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!agentId) {
      setError("Agent not loaded");
      return;
    }

    if (!tokenValidation?.valid) {
      setError("Please validate your bot token first");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await apiClient.createTelegramBot({
        agent_id: agentId,
        bot_name: formData.bot_name,
        bot_token: formData.bot_token,
        use_webhook: formData.use_webhook,
        webhook_url: formData.use_webhook ? formData.webhook_url : undefined,
      });

      router.push(`/agents/${agentName}/telegram-bots`);
    } catch (err: any) {
      console.error("Error creating bot:", err);
      setError(extractErrorMessage(err, "Failed to create Telegram bot"));
    } finally {
      setLoading(false);
    }
  };

  if (pageLoading) {
    return (
      <div className="dashboard-resource-page flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#171717]"></div>
      </div>
    );
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Add Telegram Bot"
      description={
        <>
          Connect your agent <span className="font-semibold text-gray-900">{agentName}</span> to Telegram with a BotFather token.
        </>
      }
      icon={Send}
      badge="Telegram Setup"
      maxWidthClassName="max-w-[90rem]"
    >
      <AgentPagePanel className="mb-5 p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[1rem] border border-black/10 bg-[#f1eadc]">
            <MessageCircle className="h-4 w-4 text-[#171717]" />
          </div>
          <div className="flex-1">
            <h3 className="mb-2 text-sm font-semibold text-gray-950">
              How to create a Telegram bot
            </h3>
            <ol className="ml-2 list-inside list-decimal space-y-1 text-xs leading-6 text-gray-600">
              <li>Open Telegram and search for @BotFather</li>
              <li>Send `/newbot` and follow the prompts</li>
              <li>Copy the bot token provided</li>
              <li>Paste it below and validate the token</li>
            </ol>
            <a
              href="https://core.telegram.org/bots#botfather"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-[#171717] transition-colors hover:text-black"
            >
              View BotFather documentation
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </AgentPagePanel>

      {error && (
        <div className="mb-5 flex items-start gap-3 rounded-[1.25rem] border border-[#ead8e1] bg-[#f8ecef] px-4 py-4">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#8b5a74]" />
          <div>
            <h3 className="text-sm font-semibold text-[#6f435b]">Error</h3>
            <p className="mt-1 text-xs text-[#8b5a74]">{error}</p>
          </div>
        </div>
      )}

      <AgentPagePanel className="overflow-hidden">
        <form onSubmit={handleSubmit}>
          <div className="space-y-6 p-6 md:p-7">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Bot Configuration</h2>
              <p className="mt-1 text-sm text-gray-500">
                Validate your Telegram token first, then finish the bot settings.
              </p>
            </div>

            <div>
              <label className={sectionTitleClass}>
                Bot Token <span className="text-[#8b5a74]">*</span>
              </label>
              <div className="flex flex-col gap-3 md:flex-row">
                <input
                  type="password"
                  value={formData.bot_token}
                  onChange={(e) => {
                    setFormData({ ...formData, bot_token: e.target.value });
                    setTokenValidation(null);
                  }}
                  placeholder="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
                  className={`${fieldClass} flex-1 font-mono`}
                  required
                />
                <button
                  type="button"
                  onClick={handleValidateToken}
                  disabled={validating || !formData.bot_token.trim()}
                  className="inline-flex min-w-[11rem] items-center justify-center rounded-[1rem] border border-[#cfe6d9] bg-[#e8f4ee] px-4 py-3 text-sm font-semibold text-[#2d8b69] transition-colors hover:bg-[#def1e7] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {validating ? "Validating..." : "Validate Token"}
                </button>
              </div>
              <p className={helperTextClass}>Get this from @BotFather on Telegram.</p>
            </div>

            {tokenValidation && (
              <div
                className={`rounded-[1.25rem] border px-4 py-4 ${
                  tokenValidation.valid
                    ? "border-[#cfe6d9] bg-[#e8f4ee]"
                    : "border-[#ead8e1] bg-[#f8ecef]"
                }`}
              >
                <div className="flex items-start gap-3">
                  {tokenValidation.valid ? (
                    <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#2d8b69]" />
                  ) : (
                    <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#8b5a74]" />
                  )}
                  <div>
                    <p
                      className={`text-sm font-semibold ${
                        tokenValidation.valid ? "text-[#246f54]" : "text-[#6f435b]"
                      }`}
                    >
                      {tokenValidation.message}
                    </p>
                    {tokenValidation.valid && tokenValidation.bot_info && (
                      <div className="mt-2 space-y-1 text-xs text-gray-700">
                        <p>Username: @{tokenValidation.bot_info.username}</p>
                        <p>Bot ID: {tokenValidation.bot_info.bot_id}</p>
                        <p>
                          Can join groups:{" "}
                          {tokenValidation.bot_info.can_join_groups ? "Yes" : "No"}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div>
              <label className={sectionTitleClass}>
                Display Name <span className="text-[#8b5a74]">*</span>
              </label>
              <input
                type="text"
                value={formData.bot_name}
                onChange={(e) => setFormData({ ...formData, bot_name: e.target.value })}
                placeholder="My Support Bot"
                className={fieldClass}
                required
              />
              <p className={helperTextClass}>A friendly name for this bot inside Synkora.</p>
            </div>

            <div className="border-t border-black/10 pt-5">
              <h3 className="mb-3 text-sm font-semibold text-gray-900">Advanced Settings</h3>

              <label className="flex items-start gap-3 rounded-[1.2rem] border border-black/10 bg-[#fcfaf5] px-4 py-4">
                <input
                  type="checkbox"
                  checked={formData.use_webhook}
                  onChange={(e) =>
                    setFormData({ ...formData, use_webhook: e.target.checked })
                  }
                  className="mt-0.5 h-4 w-4 rounded border-black/20 text-[#2d8b69] focus:ring-[#79dfbc]"
                />
                <div>
                  <span className="block text-sm font-semibold text-gray-900">
                    Use webhook instead of long polling
                  </span>
                  <span className="mt-1 block text-xs text-gray-600">
                    Long polling is recommended for most use cases. Webhook requires a public HTTPS endpoint.
                  </span>
                </div>
              </label>

              {formData.use_webhook && (
                <div className="mt-4">
                  <label className={sectionTitleClass}>Webhook URL</label>
                  <input
                    type="url"
                    value={formData.webhook_url}
                    onChange={(e) =>
                      setFormData({ ...formData, webhook_url: e.target.value })
                    }
                    placeholder="https://your-domain.com/webhook/telegram"
                    className={fieldClass}
                  />
                </div>
              )}
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-black/10 pt-5 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => router.push(`/agents/${agentName}/telegram-bots`)}
                className={secondaryButtonClass}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !tokenValidation?.valid}
                className={primaryButtonClass}
              >
                {loading ? "Creating..." : "Create Telegram Bot"}
              </button>
            </div>
          </div>
        </form>
      </AgentPagePanel>
    </AgentPageShell>
  );
}
