import { apiClient } from './client';
import type {
  SubscriptionPlan,
  TenantSubscription,
  CreditBalance,
  CreditTransaction,
  CreditTopup,
  AgentPricing,
  AgentRevenue,
  UsageAnalytics,
  CreateSubscriptionRequest,
  UpgradeSubscriptionRequest,
  TopupCreditsRequest,
  TopupCreditsResponse,
  SetAgentPricingRequest,
  TransactionFilters,
  UsageFilters,
  UsageSummary,
  UsageTrend,
  AgentUsageBreakdown,
  ActionUsageBreakdown,
  PeakUsageTime,
} from '@/types/billing';

// Subscription Plans
export const getSubscriptionPlans = async (): Promise<SubscriptionPlan[]> => {
  const data = await apiClient.request('GET', '/api/v1/billing/plans');
  return data;
};

export const getSubscriptionPlan = async (planId: string): Promise<SubscriptionPlan> => {
  return await apiClient.request('GET', `/api/v1/billing/plans/${planId}`);
};

// Tenant Subscription
export const getCurrentSubscription = async (): Promise<TenantSubscription> => {
  return await apiClient.request('GET', '/api/v1/billing/subscription');
};

export const createSubscription = async (
  data: CreateSubscriptionRequest
): Promise<TenantSubscription> => {
  return await apiClient.request('POST', '/api/v1/billing/subscription/create', data);
};

export const upgradeSubscription = async (
  data: UpgradeSubscriptionRequest
): Promise<TenantSubscription> => {
  return await apiClient.request('POST', '/api/v1/billing/subscription/upgrade', data);
};

export const cancelSubscription = async (immediate: boolean = false): Promise<void> => {
  await apiClient.request('POST', '/api/v1/billing/subscription/cancel', { immediate });
};

export const reactivateSubscription = async (): Promise<TenantSubscription> => {
  return await apiClient.request('POST', '/api/v1/billing/subscription/reactivate');
};

export const verifyCheckoutSession = async (sessionId: string): Promise<{ status: string; message: string }> => {
  return await apiClient.request('POST', '/api/v1/billing/subscription/verify-checkout', undefined, {
    params: { session_id: sessionId },
  });
};

// Credit Balance
export const getCreditBalance = async (): Promise<CreditBalance> => {
  return await apiClient.request('GET', '/api/v1/billing/credits/balance');
};

// Credit Transactions
export const getCreditTransactions = async (
  filters?: TransactionFilters
): Promise<CreditTransaction[]> => {
  return await apiClient.request('GET', '/api/v1/billing/credits/transactions', undefined, {
    params: filters,
  });
};

export const getCreditTransaction = async (
  transactionId: string
): Promise<CreditTransaction> => {
  return await apiClient.request('GET', `/api/v1/billing/credits/transactions/${transactionId}`);
};

// Credit Top-ups
export const createCreditTopup = async (
  data: TopupCreditsRequest
): Promise<TopupCreditsResponse> => {
  return await apiClient.request('POST', '/api/v1/billing/credits/topup', data);
};

export const getCreditTopups = async (): Promise<CreditTopup[]> => {
  const response = await apiClient.request('GET', '/api/v1/billing/credits/topups');
  return response.topups || [];
};

export const getCreditTopup = async (topupId: string): Promise<CreditTopup> => {
  return await apiClient.request('GET', `/api/v1/billing/credits/topups/${topupId}`);
};

// Usage Analytics
export const getUsageSummary = async (filters?: UsageFilters): Promise<UsageSummary> => {
  return await apiClient.request('GET', '/api/v1/billing/usage/summary', undefined, {
    params: filters,
  });
};

export const getUsageTrends = async (filters?: UsageFilters): Promise<UsageTrend[]> => {
  const response = await apiClient.request('GET', '/api/v1/billing/usage/trends', undefined, {
    params: filters,
  });
  return response.trend || [];
};

export const getAgentUsageBreakdown = async (
  filters?: UsageFilters
): Promise<AgentUsageBreakdown[]> => {
  const response = await apiClient.request('GET', '/api/v1/billing/usage/by-agent', undefined, {
    params: filters,
  });
  return response.breakdown || [];
};

export const getActionUsageBreakdown = async (
  filters?: UsageFilters
): Promise<ActionUsageBreakdown[]> => {
  const response = await apiClient.request('GET', '/api/v1/billing/usage/by-action', undefined, {
    params: filters,
  });
  
  // Convert object breakdown to array format
  // API returns: { "action_type": { "count": number, "total_credits": number }, ... }
  if (response.breakdown && typeof response.breakdown === 'object' && !Array.isArray(response.breakdown)) {
    const totalCount = Object.values(response.breakdown).reduce((sum: number, item: any) => {
      const count = typeof item === 'object' ? (item.count || 0) : (typeof item === 'number' ? item : 0);
      return sum + count;
    }, 0);

    return Object.entries(response.breakdown).map(([action_type, item]: [string, any]) => {
      const numCount = typeof item === 'object' ? (item.count || 0) : (typeof item === 'number' ? item : 0);
      const creditsUsed = typeof item === 'object' ? (item.total_credits || 0) : 0;
      return {
        action_type,
        credits_used: creditsUsed,
        count: numCount,
        percentage: totalCount > 0 ? (numCount / totalCount) * 100 : 0,
      };
    });
  }
  
  return Array.isArray(response.breakdown) ? response.breakdown : [];
};

export const getPeakUsageTimes = async (
  filters?: UsageFilters
): Promise<PeakUsageTime[]> => {
  return await apiClient.request('GET', '/api/v1/billing/usage/peak-times', undefined, {
    params: filters,
  });
};

export const getUsageAnalytics = async (
  filters?: UsageFilters
): Promise<UsageAnalytics[]> => {
  return await apiClient.request('GET', '/api/v1/billing/usage/analytics', undefined, {
    params: filters,
  });
};

// Agent Pricing
export const getAgentPricing = async (agentId: string): Promise<AgentPricing> => {
  const res = await apiClient.request('GET', `/api/v1/billing/agents/${agentId}/pricing`);
  return res?.pricing ?? res;
};

export const setAgentPricing = async (
  agentId: string,
  data: SetAgentPricingRequest
): Promise<AgentPricing> => {
  const res = await apiClient.request('PUT', `/api/v1/billing/agents/${agentId}/pricing`, data);
  return res?.pricing ?? res;
};

// Agent Revenue
export const getAgentRevenue = async (
  agentId: string,
  filters?: { start_date?: string; end_date?: string }
): Promise<AgentRevenue[]> => {
  const res = await apiClient.request('GET', `/api/v1/billing/agents/${agentId}/revenue`, undefined, {
    params: filters,
  });
  return res?.revenue ?? res ?? [];
};

export const getAgentEarnings = async (
  agentId: string,
  period: 'daily' | 'weekly' | 'monthly' | 'yearly' = 'monthly'
): Promise<{
  total_earnings: number;
  total_revenue: number;
  platform_fees: number;
  pending_payout: number;
  paid_out: number;
}> => {
  const res = await apiClient.request('GET', `/api/v1/billing/agents/${agentId}/earnings`, undefined, {
    params: { period },
  });
  return res?.earnings ?? res;
};

export const getCreatorRevenue = async (filters?: {
  start_date?: string;
  end_date?: string;
}): Promise<AgentRevenue[]> => {
  return await apiClient.request('GET', '/api/v1/billing/revenue/creator', undefined, {
    params: filters,
  });
};

export const getCreatorEarnings = async (
  period: 'daily' | 'weekly' | 'monthly' | 'yearly' = 'monthly'
): Promise<{
  total_earnings: number;
  total_revenue: number;
  platform_fees: number;
  pending_payout: number;
  paid_out: number;
  agents_count: number;
}> => {
  return await apiClient.request('GET', '/api/v1/billing/revenue/creator/summary', undefined, {
    params: { period },
  });
};

// Stripe Payment Methods
export const getPaymentMethods = async (): Promise<any[]> => {
  return await apiClient.request('GET', '/api/v1/billing/payment-methods');
};

export const addPaymentMethod = async (paymentMethodId: string): Promise<any> => {
  return await apiClient.request('POST', '/api/v1/billing/payment-methods', {
    payment_method_id: paymentMethodId,
  });
};

export const removePaymentMethod = async (paymentMethodId: string): Promise<void> => {
  await apiClient.request('DELETE', `/api/v1/billing/payment-methods/${paymentMethodId}`);
};

export const setDefaultPaymentMethod = async (paymentMethodId: string): Promise<void> => {
  await apiClient.request('PUT', '/api/v1/billing/payment-methods/default', {
    payment_method_id: paymentMethodId,
  });
};

// Invoices
export const getInvoices = async (): Promise<any[]> => {
  return await apiClient.request('GET', '/api/v1/billing/invoices');
};

export const getInvoice = async (invoiceId: string): Promise<any> => {
  return await apiClient.request('GET', `/api/v1/billing/invoices/${invoiceId}`);
};

export const downloadInvoice = async (invoiceId: string): Promise<Blob> => {
  return await apiClient.request('GET', `/api/v1/billing/invoices/${invoiceId}/download`, undefined, {
    responseType: 'blob',
  });
};

// Billing Portal
export const createBillingPortalSession = async (): Promise<{ url: string }> => {
  return await apiClient.request('POST', '/api/v1/billing/portal-session');
};

// Export Usage Report
export const exportUsageReport = async (
  filters?: UsageFilters,
  format: 'csv' | 'pdf' = 'csv'
): Promise<Blob> => {
  return await apiClient.request('GET', '/api/v1/billing/usage/export', undefined, {
    params: { ...filters, format },
    responseType: 'blob',
  });
};

// Payment Provider Configuration
export interface PaymentProviderConfig {
  provider: string;
  client_token: string | null;
  environment: string | null;
  is_configured: boolean;
}

export const getPaymentProviderConfig = async (): Promise<PaymentProviderConfig> => {
  return await apiClient.request('GET', '/api/v1/billing/payment-provider/config');
};
