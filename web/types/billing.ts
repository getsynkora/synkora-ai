// Billing and Pricing Types

// Plan tiers enum
export type PlanTier = 'FREE' | 'HOBBY' | 'STARTER' | 'PROFESSIONAL' | 'ENTERPRISE';

export interface SubscriptionPlan {
  id: string;
  name: string;
  tier: PlanTier;
  description: string | null;
  price_monthly: number;
  price_yearly: number | null;
  credits_monthly: number;
  credits_rollover: boolean;
  // Resource limits (null = unlimited)
  max_agents: number | null;
  max_team_members: number | null;
  max_api_calls_per_month: number | null;
  max_knowledge_bases: number | null;
  max_data_sources: number | null;
  max_custom_tools: number | null;
  max_database_connections: number | null;
  max_mcp_servers: number | null;
  max_scheduled_tasks: number | null;
  max_widgets: number | null;
  max_slack_bots: number | null;
  // Feature flags and overage settings
  features: PlanFeatureFlags | null;
  is_active: boolean;
  stripe_product_id: string | null;
  stripe_price_id: string | null;
  paddle_product_id: string | null;
  paddle_price_id: string | null;
  created_at: string;
  updated_at: string;
}

// Feature flags stored in the features JSON column
export interface PlanFeatureFlags {
  // Conversation limits
  max_conversations?: number; // -1 = unlimited
  max_messages_per_conversation?: number; // -1 = unlimited
  // Boolean feature flags
  knowledge_bases?: boolean;
  custom_tools?: boolean;
  mcp_servers?: boolean;
  api_access?: boolean;
  priority_support?: boolean;
  advanced_analytics?: boolean;
  custom_domains?: boolean;
  webhooks?: boolean;
  white_label?: boolean;
  sso?: boolean;
  audit_logs?: boolean;
  dedicated_support?: boolean;
  custom_integrations?: boolean;
  sla_guarantee?: boolean;
  // Overage settings
  overage_allowed?: boolean;
  overage_rate_per_credit?: number;
  grace_period_days?: number;
  max_rollover_credits?: number;
}

export interface TenantSubscription {
  id: string;
  tenant_id: string;
  plan_id: string;
  plan_name?: string;
  plan?: SubscriptionPlan;
  status: 'active' | 'cancelled' | 'expired' | 'trial';
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  payment_provider: 'stripe' | 'paddle';
  stripe_subscription_id: string | null;
  stripe_customer_id: string | null;
  paddle_subscription_id: string | null;
  paddle_customer_id: string | null;
  trial_end: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreditBalance {
  id: string;
  tenant_id: string;
  total_credits: number;
  used_credits: number;
  available_credits: number;
  last_reset_at: string | null;
  next_reset_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreditTransaction {
  id: string;
  tenant_id: string;
  user_id: string | null;
  agent_id: string | null;
  transaction_type: 'purchase' | 'usage' | 'refund' | 'bonus';
  credits_amount: number;
  balance_before: number;
  balance_after: number;
  action_type: string | null;
  action_metadata: Record<string, any> | null;
  description: string | null;
  created_at: string;
}

export interface CreditTopup {
  id: string;
  tenant_id: string;
  credits_amount: number;
  price_paid: number;
  payment_method: string | null;
  stripe_payment_intent_id: string | null;
  status: 'pending' | 'completed' | 'failed';
  created_at: string;
  completed_at: string | null;
}

export interface AgentPricing {
  id: string;
  agent_id: string;
  tenant_id: string;
  pricing_model: 'FREE' | 'PER_USE' | 'SUBSCRIPTION' | 'SESSION' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
  credits_per_use: number | null;
  session_credits: number | null;
  daily_credits: number | null;
  weekly_credits: number | null;
  monthly_subscription_credits: number | null;
  trial_messages: number | null;
  revenue_share_percentage: number;
  is_active: boolean;
  total_uses: number;
  total_revenue_credits: number;
  email_subscription_model: string;
  email_subscription_price_cents: number | null;
  email_subscription_trial_emails: number;
  created_at: string;
  updated_at: string;
}

export interface AgentRevenue {
  id: string;
  agent_pricing_id: string;
  tenant_id: string;
  transaction_id: string | null;
  credits_used: number;
  revenue_amount: number;
  platform_fee: number;
  creator_earnings: number;
  revenue_share_percentage: number;
  status: 'pending' | 'processing' | 'paid' | 'failed';
  payout_date: string | null;
  payout_reference: string | null;
  created_at: string;
  updated_at: string;
}

export interface UsageAnalytics {
  id: string;
  tenant_id: string;
  agent_id: string | null;
  date: string;
  total_interactions: number;
  total_credits_used: number;
  chat_messages: number;
  file_uploads: number;
  api_calls: number;
  unique_users: number;
  created_at: string;
}

export interface UsageSummary {
  total_interactions: number;
  total_credits_used: number;
  breakdown: Record<string, number>;
  avg_daily_users: number;
}

export interface UsageTrend {
  date: string;
  credits_used: number;
  interactions: number;
}

export interface AgentUsageBreakdown {
  agent_id: string;
  agent_name: string;
  credits_used: number;
  interactions: number;
  percentage: number;
}

export interface ActionUsageBreakdown {
  action_type: string;
  credits_used: number;
  count: number;
  percentage: number;
}

export interface PeakUsageTime {
  hour: number;
  credits_used: number;
  interactions: number;
}

// Request/Response Types
export interface CreateSubscriptionRequest {
  plan_id: string;
  payment_method_id?: string;
  payment_provider?: 'stripe' | 'paddle';
}

export interface CreateSubscriptionResponse {
  checkout_url?: string;
  session_id?: string;
  provider?: string;
}

export interface UpgradeSubscriptionRequest {
  plan_id: string;
  payment_provider?: 'stripe' | 'paddle';
}

export interface UpgradeSubscriptionResponse {
  checkout_url?: string;
  provider?: string;
  session_id?: string;
}

export interface TopupCreditsRequest {
  topup_id: string;
  payment_provider?: 'stripe' | 'paddle';
}

export interface TopupCreditsResponse {
  checkout_url?: string;
  session_id?: string;
  client_secret?: string;
  topup_id?: string;
  provider?: string;
}

export interface SetAgentPricingRequest {
  agent_id: string;
  pricing_model: 'FREE' | 'PER_USE' | 'SUBSCRIPTION' | 'SESSION' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
  credits_per_use?: number | null;
  session_credits?: number | null;
  daily_credits?: number | null;
  weekly_credits?: number | null;
  monthly_subscription_credits?: number | null;
  trial_messages?: number | null;
  revenue_share_percentage?: number | null;
  email_subscription_model?: string | null;
  email_subscription_price_cents?: number | null;
  email_subscription_trial_emails?: number | null;
}

// Filter Types
export interface TransactionFilters {
  limit?: number;
  offset?: number;
  transaction_type?: 'purchase' | 'usage' | 'refund' | 'bonus';
  start_date?: string;
  end_date?: string;
}

export interface UsageFilters {
  start_date?: string;
  end_date?: string;
  agent_id?: string;
  days?: number;
}

// Credit Cost Configuration
export const CREDIT_COSTS = {
  CHAT_GPT35: 1,
  CHAT_GPT4: 5,
  CHAT_CLAUDE: 4,
  STREAMING: 0.5,
  FILE_UPLOAD: 2,
  IMAGE_ANALYSIS: 3,
  VOICE_TTS_PER_MINUTE: 2,
  VOICE_STT_PER_MINUTE: 1,
  KNOWLEDGE_BASE_QUERY: 1,
  CUSTOM_TOOL: 2,
  DATABASE_QUERY: 1,
  CHART_GENERATION: 2,
  API_CALL: 3,
} as const;

// Subscription Status Badge Colors
export const SUBSCRIPTION_STATUS_COLORS = {
  active: 'green',
  trial: 'blue',
  cancelled: 'yellow',
  expired: 'red',
} as const;

// Transaction Type Colors
export const TRANSACTION_TYPE_COLORS = {
  purchase: 'green',
  usage: 'blue',
  refund: 'yellow',
  bonus: 'purple',
} as const;

// Plan tier colors for UI
export const PLAN_TIER_COLORS: Record<PlanTier, string> = {
  FREE: 'gray',
  HOBBY: 'blue',
  STARTER: 'green',
  PROFESSIONAL: 'purple',
  ENTERPRISE: 'gold',
} as const;

// Plan tier badges
export const PLAN_TIER_BADGES: Record<PlanTier, { label: string; color: string }> = {
  FREE: { label: 'Free', color: 'gray' },
  HOBBY: { label: 'Hobby', color: 'blue' },
  STARTER: { label: 'Starter', color: 'green' },
  PROFESSIONAL: { label: 'Pro', color: 'purple' },
  ENTERPRISE: { label: 'Enterprise', color: 'gold' },
} as const;

// Default plan pricing for display
export const PLAN_PRICING = {
  FREE: { monthly: 0, yearly: 0, credits: 100 },
  HOBBY: { monthly: 9, yearly: 90, credits: 500 },
  STARTER: { monthly: 19, yearly: 190, credits: 1500 },
  PROFESSIONAL: { monthly: 79, yearly: 790, credits: 7500 },
  ENTERPRISE: { monthly: 299, yearly: 2990, credits: 50000 },
} as const;

// Usage stats response type
export interface UsageStats {
  plan_name: string;
  plan_tier: PlanTier;
  credits_monthly: number;
  credits_rollover: boolean;
  overage_allowed: boolean;
  overage_rate_per_credit: number;
  grace_period_days: number;
  usage: {
    agents: UsageItem;
    team_members: UsageItem;
    knowledge_bases: UsageItem;
    mcp_servers: UsageItem;
    custom_tools: UsageItem;
    database_connections: UsageItem;
    data_sources: UsageItem;
    scheduled_tasks: UsageItem;
    widgets: UsageItem;
    slack_bots: UsageItem;
    api_calls_per_month: UsageItem;
  };
  features: PlanFeatureFlags;
}

export interface UsageItem {
  current: number;
  limit: number | null;
  unlimited: boolean;
}

// Overage summary type
export interface OverageSummary {
  total_overage_credits: number;
  total_overage_charge: number;
  transaction_count: number;
}
