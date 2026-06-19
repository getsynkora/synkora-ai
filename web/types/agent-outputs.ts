/**
 * TypeScript types for Agent Output Configuration System
 */

export type OutputProvider = 'slack' | 'email' | 'webhook';

export type DeliveryStatus = 'pending' | 'delivered' | 'failed';

export interface OutputConfig {
  id: string;
  agent_id: string;
  tenant_id: string;
  name: string;
  description?: string;
  provider: OutputProvider;
  oauth_app_id?: number;
  slack_bot_id?: string;
  config: Record<string, any>;
  conditions?: Record<string, any>;
  output_template?: string;
  is_enabled: boolean;
  send_on_webhook_trigger: boolean;
  send_on_chat_completion: boolean;
  retry_on_failure: boolean;
  max_retries: number;
  created_at: string;
  updated_at: string;
  stats?: {
    total_deliveries: number;
    successful_deliveries: number;
    failed_deliveries: number;
    last_delivery_at?: string;
  };
}

export interface OutputDelivery {
  id: string;
  output_config_id: string;
  agent_id: string;
  webhook_event_id?: string;
  status: DeliveryStatus;
  provider: OutputProvider;
  formatted_output?: string;
  attempt_count: number;
  error_message?: string;
  provider_message_id?: string;
  created_at: string;
  delivered_at?: string;
}

export interface CreateOutputConfigData {
  name: string;
  description?: string;
  provider: OutputProvider;
  oauth_app_id?: number;
  slack_bot_id?: string;
  config: Record<string, any>;
  conditions?: Record<string, any>;
  output_template?: string;
  is_enabled?: boolean;
  send_on_webhook_trigger?: boolean;
  send_on_chat_completion?: boolean;
  retry_on_failure?: boolean;
  max_retries?: number;
}

export interface UpdateOutputConfigData {
  name?: string;
  description?: string;
  oauth_app_id?: number;
  slack_bot_id?: string;
  config?: Record<string, any>;
  conditions?: Record<string, any>;
  output_template?: string;
  is_enabled?: boolean;
  send_on_webhook_trigger?: boolean;
  send_on_chat_completion?: boolean;
  retry_on_failure?: boolean;
  max_retries?: number;
}

// Slack-specific config
export interface SlackOutputConfig {
  channel: string; // #channel or @user
  thread_ts?: string; // Thread timestamp for threaded messages
}

// Email-specific config
export interface EmailOutputConfig {
  to: string[];
  cc?: string[];
  bcc?: string[];
  subject: string;
}

// Webhook-specific config
export interface WebhookOutputConfig {
  url: string;
  method: 'POST' | 'PUT' | 'PATCH';
  headers?: Record<string, string>;
  timeout?: number;
}

// OAuth app for dropdowns
export interface OAuthApp {
  id: number;
  name: string;
  provider: string;
  is_active: boolean;
}

// Slack bot for dropdowns
export interface SlackBot {
  id: string;
  bot_name: string;
  slack_workspace_name?: string;
  is_active: boolean;
}
