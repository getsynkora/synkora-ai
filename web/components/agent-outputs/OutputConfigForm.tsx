'use client';

import { useState } from 'react';
import { Save, Loader2 } from 'lucide-react';
import { useOAuthApps } from '@/hooks/useAgentOutputs';
import type {
  OutputConfig,
  CreateOutputConfigData,
  OutputProvider,
  SlackOutputConfig,
  EmailOutputConfig,
  WebhookOutputConfig,
} from '@/types/agent-outputs';

interface OutputConfigFormProps {
  output?: OutputConfig;
  onSubmit: (data: CreateOutputConfigData) => Promise<void>;
  onCancel: () => void;
}

/**
 * Encode the selected connection into a single string value.
 * Slack bots use "bot:<uuid>", OAuth apps use "oauth:<id>".
 */
function encodeConnectionValue(output?: OutputConfig): string {
  if (output?.slack_bot_id) return `bot:${output.slack_bot_id}`;
  if (output?.oauth_app_id) return `oauth:${output.oauth_app_id}`;
  return '';
}

export function OutputConfigForm({ output, onSubmit, onCancel }: OutputConfigFormProps) {
  const { slackBots, getAppsByProvider } = useOAuthApps();
  const [loading, setLoading] = useState(false);
  const [provider, setProvider] = useState<OutputProvider>(output?.provider || 'slack');

  // Form fields
  const [name, setName] = useState(output?.name || '');
  const [description, setDescription] = useState(output?.description || '');
  // Combined connection value: "bot:<uuid>" or "oauth:<id>"
  const [connectionValue, setConnectionValue] = useState<string>(encodeConnectionValue(output));
  const [isEnabled, setIsEnabled] = useState(output?.is_enabled ?? true);
  const [sendOnWebhook, setSendOnWebhook] = useState(output?.send_on_webhook_trigger ?? true);
  const [sendOnChat, setSendOnChat] = useState(output?.send_on_chat_completion ?? false);
  const [retryOnFailure, setRetryOnFailure] = useState(output?.retry_on_failure ?? true);
  const [maxRetries, setMaxRetries] = useState(output?.max_retries || 3);
  const [outputTemplate, setOutputTemplate] = useState(output?.output_template || '');

  // Provider-specific config
  const [slackChannelId, setSlackChannelId] = useState<string>(
    (output?.config as any)?.channel_id || ''
  );
  const [slackChannelName, setSlackChannelName] = useState<string>(
    (output?.config as any)?.channel_name || ''
  );
  const [emailTo, setEmailTo] = useState<string>(
    (output?.config as EmailOutputConfig)?.to?.join(', ') || ''
  );
  const [emailSubject, setEmailSubject] = useState<string>(
    (output?.config as EmailOutputConfig)?.subject || 'Agent Output'
  );
  const [webhookUrl, setWebhookUrl] = useState<string>(
    (output?.config as WebhookOutputConfig)?.url || ''
  );
  const [webhookMethod, setWebhookMethod] = useState<'POST' | 'PUT' | 'PATCH'>(
    (output?.config as WebhookOutputConfig)?.method || 'POST'
  );
  const [webhookHeaders, setWebhookHeaders] = useState<string>(
    JSON.stringify((output?.config as WebhookOutputConfig)?.headers || {}, null, 2)
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      let config: any = {};

      if (provider === 'slack') {
        config = { channel_id: slackChannelId, channel_name: slackChannelName };
      } else if (provider === 'email') {
        config = {
          recipients: emailTo.split(',').map((e) => e.trim()).filter(Boolean),
          subject_template: emailSubject,
        };
      } else if (provider === 'webhook') {
        config = {
          url: webhookUrl,
          method: webhookMethod,
          headers: webhookHeaders ? JSON.parse(webhookHeaders) : {},
        };
      }

      // Parse connection value
      let oauthAppId: number | undefined;
      let slackBotId: string | undefined;
      if (connectionValue.startsWith('bot:')) {
        slackBotId = connectionValue.slice(4);
      } else if (connectionValue.startsWith('oauth:')) {
        oauthAppId = parseInt(connectionValue.slice(6), 10);
      }

      const data: CreateOutputConfigData = {
        name,
        description: description || undefined,
        provider,
        oauth_app_id: oauthAppId,
        slack_bot_id: slackBotId,
        config,
        output_template: outputTemplate || undefined,
        is_enabled: isEnabled,
        send_on_webhook_trigger: sendOnWebhook,
        send_on_chat_completion: sendOnChat,
        retry_on_failure: retryOnFailure,
        max_retries: maxRetries,
      };

      await onSubmit(data);
    } catch (error) {
      console.error('Error submitting output config:', error);
    } finally {
      setLoading(false);
    }
  };

  const slackOAuthApps = getAppsByProvider('slack');
  const emailApps = getAppsByProvider('email');

  return (
    <form onSubmit={handleSubmit} className="p-6">
      <div className="space-y-6">
        {/* Basic Info */}
        <div>
          <h3 className="text-base font-semibold text-gray-900 mb-4">Basic Information</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Slack Notifications"
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                rows={2}
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
              />
            </div>
          </div>
        </div>

        {/* Provider Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Provider <span className="text-red-500">*</span>
          </label>
          <select
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value as OutputProvider);
              setConnectionValue('');
            }}
            disabled={!!output}
            className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
            required
          >
            <option value="slack">Slack</option>
            <option value="email">Email</option>
            <option value="webhook">Webhook</option>
          </select>
          {!!output && (
            <p className="text-xs text-gray-600 mt-1">
              Provider cannot be changed after creation
            </p>
          )}
        </div>

        {/* Connection Selection for Slack */}
        {provider === 'slack' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Slack Connection <span className="text-red-500">*</span>
            </label>
            <select
              value={connectionValue}
              onChange={(e) => setConnectionValue(e.target.value)}
              className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
              required
            >
              <option value="">Select Slack connection</option>
              {slackBots.length > 0 && (
                <optgroup label="Slack Bots (Bot Token)">
                  {slackBots.map((bot) => (
                    <option key={bot.id} value={`bot:${bot.id}`}>
                      {bot.bot_name}{bot.slack_workspace_name ? ` — ${bot.slack_workspace_name}` : ''}
                    </option>
                  ))}
                </optgroup>
              )}
              {slackOAuthApps.length > 0 && (
                <optgroup label="OAuth Apps (User Token)">
                  {slackOAuthApps.map((app) => (
                    <option key={app.id} value={`oauth:${app.id}`}>
                      {app.name}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
            {slackBots.length === 0 && slackOAuthApps.length === 0 && (
              <p className="text-xs text-gray-600 mt-1">
                No Slack connections found. Add a Slack Bot or OAuth App first.
              </p>
            )}
          </div>
        )}

        {/* Connection Selection for Email */}
        {provider === 'email' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Email Configuration <span className="text-red-500">*</span>
            </label>
            <select
              value={connectionValue}
              onChange={(e) => setConnectionValue(e.target.value)}
              className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
              required
            >
              <option value="">Select email app</option>
              {emailApps.map((app) => (
                <option key={app.id} value={`oauth:${app.id}`}>
                  {app.name}
                </option>
              ))}
            </select>
            {emailApps.length === 0 && (
              <p className="text-xs text-gray-600 mt-1">
                No email apps configured. Please set up an OAuth app first.
              </p>
            )}
          </div>
        )}

        {/* Provider-Specific Configuration */}
        {provider === 'slack' && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Channel ID <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={slackChannelId}
                onChange={(e) => setSlackChannelId(e.target.value)}
                placeholder="C0123456789"
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                required
              />
              <p className="text-xs text-gray-600 mt-1">
                Slack channel ID (starts with C). Right-click a channel in Slack → Copy link to find it.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Channel Name (optional)
              </label>
              <input
                type="text"
                value={slackChannelName}
                onChange={(e) => setSlackChannelName(e.target.value)}
                placeholder="#general"
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
              />
            </div>
          </div>
        )}

        {provider === 'email' && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Recipients <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={emailTo}
                onChange={(e) => setEmailTo(e.target.value)}
                placeholder="user@example.com, another@example.com"
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                required
              />
              <p className="text-xs text-gray-600 mt-1">
                Comma-separated email addresses
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Subject <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={emailSubject}
                onChange={(e) => setEmailSubject(e.target.value)}
                placeholder="Agent Output"
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                required
              />
            </div>
          </>
        )}

        {provider === 'webhook' && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Webhook URL <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://api.example.com/webhook"
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                HTTP Method
              </label>
              <select
                value={webhookMethod}
                onChange={(e) => setWebhookMethod(e.target.value as 'POST' | 'PUT' | 'PATCH')}
                className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
              >
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Custom Headers (JSON)
              </label>
              <textarea
                value={webhookHeaders}
                onChange={(e) => setWebhookHeaders(e.target.value)}
                placeholder='{"Authorization": "Bearer token"}'
                rows={4}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent font-mono"
              />
            </div>
          </>
        )}

        {/* Output Template */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Output Template (Optional)
          </label>
          <textarea
            value={outputTemplate}
            onChange={(e) => setOutputTemplate(e.target.value)}
            placeholder="Use {response} for agent output, {event_type} for trigger type, etc."
            rows={4}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
          />
          <p className="text-xs text-gray-600 mt-1">
            Leave empty to use default formatting. Variables: {'{response}'}, {'{agent_name}'}, {'{event_type}'}
          </p>
        </div>

        {/* Trigger Configuration */}
        <div>
          <h3 className="text-base font-semibold text-gray-900 mb-3">When to Send</h3>
          <div className="space-y-3">
            <label className="flex items-center gap-2.5 p-3 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-gray-300 transition-all">
              <input
                type="checkbox"
                checked={sendOnWebhook}
                onChange={(e) => setSendOnWebhook(e.target.checked)}
                className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500"
              />
              <span className="text-sm font-medium text-gray-900">Send on webhook trigger</span>
            </label>
            <label className="flex items-center gap-2.5 p-3 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-gray-300 transition-all">
              <input
                type="checkbox"
                checked={sendOnChat}
                onChange={(e) => setSendOnChat(e.target.checked)}
                className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500"
              />
              <span className="text-sm font-medium text-gray-900">Send on chat completion</span>
            </label>
          </div>
        </div>

        {/* Retry Configuration */}
        <div>
          <h3 className="text-base font-semibold text-gray-900 mb-3">Retry Settings</h3>
          <div className="space-y-3">
            <label className="flex items-center gap-2.5 p-3 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-gray-300 transition-all">
              <input
                type="checkbox"
                checked={retryOnFailure}
                onChange={(e) => setRetryOnFailure(e.target.checked)}
                className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500"
              />
              <span className="text-sm font-medium text-gray-900">Retry on failure</span>
            </label>
            {retryOnFailure && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Max Retries
                </label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={maxRetries}
                  onChange={(e) => setMaxRetries(parseInt(e.target.value))}
                  className="w-full px-3 py-2 text-sm text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
              </div>
            )}
          </div>
        </div>

        {/* Enable/Disable */}
        <div>
          <label className="flex items-center gap-2.5 p-3 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-gray-300 transition-all">
            <input
              type="checkbox"
              checked={isEnabled}
              onChange={(e) => setIsEnabled(e.target.checked)}
              className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500"
            />
            <span className="text-sm font-medium text-gray-900">Enable this output</span>
          </label>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-5 border-t border-gray-200">
          <button
            type="button"
            onClick={onCancel}
            className="px-5 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 rounded-lg transition-all shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                {output ? 'Update' : 'Create'} Output
              </>
            )}
          </button>
        </div>
      </div>
    </form>
  );
}
