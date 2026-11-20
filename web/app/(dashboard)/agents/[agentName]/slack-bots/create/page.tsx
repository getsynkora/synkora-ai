"use client";

import { useState } from "react";
import { extractErrorMessage } from '@/lib/api/error'
import { useParams, useRouter } from "next/navigation";
import { AlertCircle, ExternalLink, Slack } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

export default function CreateSlackBotPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;

  const [formData, setFormData] = useState({
    bot_name: "",
    slack_app_id: "",
    slack_bot_token: "",
    slack_app_token: "",
    slack_workspace_id: "",
    slack_workspace_name: "",
    connection_mode: "socket",
    signing_secret: "",
    allow_external_shared_channels: false,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Get agent ID
      const agent = await apiClient.getAgent(agentName);

      // Prepare data based on connection mode
      const botData: any = {
        agent_id: agent.id,
        bot_name: formData.bot_name,
        slack_app_id: formData.slack_app_id,
        slack_bot_token: formData.slack_bot_token,
        connection_mode: formData.connection_mode,
        allow_external_shared_channels: formData.allow_external_shared_channels,
      };

      // Add mode-specific fields
      if (formData.connection_mode === "socket") {
        botData.slack_app_token = formData.slack_app_token;
      } else {
        botData.signing_secret = formData.signing_secret;
      }

      // Create bot
      await apiClient.createSlackBot(botData);

      // Redirect back to bots list
      router.push(`/agents/${agentName}/slack-bots`);
    } catch (err: any) {
      console.error("Error creating Slack bot:", err);
      setError(extractErrorMessage(err, "Failed to create Slack bot"))
      setLoading(false);
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

  const fieldClass =
    "w-full rounded-[1.15rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint";
  const radioCardClass = (active: boolean) =>
    `flex cursor-pointer flex-col rounded-[1.25rem] border px-4 py-3 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
      active
        ? "border-ink bg-white shadow-soft"
        : "border-black/10 bg-cream hover:border-black/20 hover:bg-white"
    }`;

  return (
    <AgentPageShell
      agentName={agentName}
      title="Create Slack Bot"
      description={<>Connect your agent <span className="font-semibold text-ink">{agentName}</span> to a Slack workspace.</>}
      icon={Slack}
      backHref={`/agents/${agentName}/slack-bots`}
      backLabel="Back to Slack Bots"
      badge="Slack Setup"
      maxWidthClassName="max-w-[90rem]"
    >

        {/* Setup Instructions */}
        <AgentPagePanel className="mb-5 p-5">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[1rem] border border-black/10 bg-sand-deep">
              <AlertCircle className="h-4 w-4 text-ink" />
            </div>
            <div className="flex-1">
              <h3 className="mb-2 text-sm font-semibold text-ink">
                Before you begin
              </h3>
              <div className="space-y-2 text-xs leading-6 text-ink-soft">
                <p>To create a Slack bot, you need to:</p>
                <ol className="list-decimal list-inside space-y-1 ml-2">
                  <li>Create a Slack app at <a href="https://api.slack.com/apps" target="_blank" rel="noopener noreferrer" className="font-semibold text-ink underline">api.slack.com/apps</a></li>
                  <li>
                    {formData.connection_mode === "socket"
                      ? "Enable Socket Mode in your app settings"
                      : "Enable Event Subscriptions in your app settings"}
                  </li>
                  <li>Add the following bot token scopes:
                    <ul className="list-disc list-inside ml-4 mt-1">
                      <li><code className="rounded bg-blush-wash px-1.5 py-0.5 text-plum">app_mentions:read</code></li>
                      <li><code className="rounded bg-blush-wash px-1.5 py-0.5 text-plum">chat:write</code></li>
                      <li><code className="rounded bg-blush-wash px-1.5 py-0.5 text-plum">im:history</code></li>
                      <li><code className="rounded bg-blush-wash px-1.5 py-0.5 text-plum">im:read</code></li>
                      <li><code className="rounded bg-blush-wash px-1.5 py-0.5 text-plum">im:write</code></li>
                    </ul>
                  </li>
                  <li>Install the app to your workspace</li>
                  <li>
                    {formData.connection_mode === "socket"
                      ? "Copy the Bot User OAuth Token and App-Level Token"
                      : "Copy the Bot User OAuth Token and Signing Secret"}
                  </li>
                </ol>
                <a
                  href="https://api.slack.com/apps"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-ink transition-colors hover:text-black"
                >
                  Open Slack API Dashboard
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>
        </AgentPagePanel>

        {/* Error Message */}
        {error && (
          <div className="mb-5 flex items-start gap-3 rounded-[1.25rem] border border-blush-wash bg-blush-wash px-4 py-4">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-plum" />
            <div>
              <h3 className="text-sm font-semibold text-plum">Error</h3>
              <p className="mt-1 text-xs text-plum">{error}</p>
            </div>
          </div>
        )}

        {/* Form */}
        <AgentPagePanel className="overflow-hidden">
        <form onSubmit={handleSubmit}>
          <div className="p-6 space-y-5">
            {/* Bot Name */}
            <div>
              <label htmlFor="bot_name" className="mb-1.5 block text-xs font-semibold text-bark">
                Bot Name <span className="text-plum">*</span>
              </label>
              <input
                type="text"
                id="bot_name"
                name="bot_name"
                value={formData.bot_name}
                onChange={handleChange}
                required
                className={fieldClass}
                placeholder="My Agent Bot"
              />
              <p className="text-xs text-ink-mute mt-1">
                A friendly name to identify this bot
              </p>
            </div>

            {/* Connection Mode */}
            <div>
              <label className="mb-2 block text-xs font-semibold text-bark">
                Connection Mode
              </label>
              <div className="grid gap-3 md:grid-cols-2">
                <label className={radioCardClass(formData.connection_mode === "socket")}>
                  <input
                    type="radio"
                    name="connection_mode"
                    value="socket"
                    checked={formData.connection_mode === "socket"}
                    onChange={handleChange}
                    className="sr-only"
                  />
                  <span className="text-sm font-semibold text-ink">Socket Mode</span>
                  <span className="mt-1 text-xs text-ink-soft">Recommended. Uses WebSocket connections and does not require a public URL.</span>
                </label>
                <label className={radioCardClass(formData.connection_mode === "event")}>
                  <input
                    type="radio"
                    name="connection_mode"
                    value="event"
                    checked={formData.connection_mode === "event"}
                    onChange={handleChange}
                    className="sr-only"
                  />
                  <span className="text-sm font-semibold text-ink">Event Mode</span>
                  <span className="mt-1 text-xs text-ink-soft">Uses HTTP webhooks and requires a reachable public callback URL.</span>
                </label>
              </div>
              <p className="text-xs text-ink-mute mt-1">
                {formData.connection_mode === "socket"
                  ? "Socket Mode uses WebSocket connections (no public URL needed)"
                  : "Event Mode uses HTTP webhooks (requires public URL)"}
              </p>
            </div>

            {/* Slack App ID */}
            <div>
              <label htmlFor="slack_app_id" className="mb-1.5 block text-xs font-semibold text-bark">
                Slack App ID <span className="text-plum">*</span>
              </label>
              <input
                type="text"
                id="slack_app_id"
                name="slack_app_id"
                value={formData.slack_app_id}
                onChange={handleChange}
                required
                className={`${fieldClass} font-mono`}
                placeholder="A1234567890"
              />
              <p className="text-xs text-ink-mute mt-1">
                Found in your Slack app's Basic Information page
              </p>
            </div>

            {/* Bot Token */}
            <div>
              <label htmlFor="slack_bot_token" className="mb-1.5 block text-xs font-semibold text-bark">
                Bot User OAuth Token <span className="text-plum">*</span>
              </label>
              <input
                type="password"
                id="slack_bot_token"
                name="slack_bot_token"
                value={formData.slack_bot_token}
                onChange={handleChange}
                required
                className={`${fieldClass} font-mono`}
                placeholder="xoxb-..."
              />
              <p className="text-xs text-ink-mute mt-1">
                Found in OAuth & Permissions → Bot User OAuth Token (starts with xoxb-)
              </p>
            </div>

            {/* Socket Mode: App-Level Token */}
            {formData.connection_mode === "socket" && (
              <div>
                <label htmlFor="slack_app_token" className="mb-1.5 block text-xs font-semibold text-bark">
                  App-Level Token <span className="text-plum">*</span>
                </label>
                <input
                  type="password"
                  id="slack_app_token"
                  name="slack_app_token"
                  value={formData.slack_app_token}
                  onChange={handleChange}
                  required
                  className={`${fieldClass} font-mono`}
                  placeholder="xapp-..."
                />
                <p className="text-xs text-ink-mute mt-1">
                  Found in Basic Information → App-Level Tokens (starts with xapp-). Required for Socket Mode.
                </p>
              </div>
            )}

            {/* Event Mode: Signing Secret */}
            {formData.connection_mode === "event" && (
              <div>
                <label htmlFor="signing_secret" className="mb-1.5 block text-xs font-semibold text-bark">
                  Signing Secret <span className="text-plum">*</span>
                </label>
                <input
                  type="password"
                  id="signing_secret"
                  name="signing_secret"
                  value={formData.signing_secret}
                  onChange={handleChange}
                  required
                  className={`${fieldClass} font-mono`}
                  placeholder="Enter your signing secret"
                />
                <p className="text-xs text-ink-mute mt-1">
                  Found in Basic Information → App Credentials → Signing Secret
                </p>
              </div>
            )}

            {/* Event Mode Notice */}
            {formData.connection_mode === "event" && (
              <div className="rounded-[1.2rem] border border-sky-wash bg-leaf-wash p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-steel" />
                  <div className="flex-1">
                    <h4 className="mb-1 text-sm font-semibold text-steel">
                      Webhook URL Required
                    </h4>
                    <p className="text-xs text-steel">
                      After creating this bot, you'll receive a webhook URL. Add this URL to your Slack app's Event Subscriptions settings to receive events.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* External Shared Channels Toggle */}
            <div className="rounded-[1.2rem] border border-black/10 bg-cream p-4">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  name="allow_external_shared_channels"
                  checked={formData.allow_external_shared_channels}
                  onChange={handleCheckboxChange}
                  className="mt-0.5 h-4 w-4 rounded border-taupe text-ink focus:ring-mint"
                />
                <div>
                  <span className="text-sm font-semibold text-ink">
                    Allow in externally-shared channels (Slack Connect)
                  </span>
                  <p className="mt-1 text-xs text-ink-soft">
                    When off (recommended), the bot won't respond in channels shared with another
                    company's Slack workspace. Turn this on only if you intentionally want this bot
                    available to external Slack Connect members.
                  </p>
                </div>
              </label>
            </div>

            {/* Auto-detection notice */}
            <div className="rounded-[1.2rem] border border-leaf-wash bg-leaf-wash p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h4 className="mb-1 text-sm font-semibold text-forest">
                    Workspace Auto-Detection
                  </h4>
                  <p className="text-xs text-leaf">
                    The workspace ID and name will be automatically detected when the bot connects to Slack for the first time.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Form Actions */}
          <div className="flex justify-end gap-3 border-t border-black/10 bg-cream px-6 py-4">
            <button
              type="button"
              onClick={() => router.back()}
              className="rounded-[1rem] border border-black/10 bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:bg-cream"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded-[1rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
            >
              {loading ? "Creating…" : "Create Bot"}
            </button>
          </div>
        </form>
        </AgentPagePanel>
    </AgentPageShell>
  );
}
