/**
 * Types for Agent LLM Configuration
 */

export type RoutingMode = 'fixed' | 'round_robin' | 'cost_opt' | 'intent' | 'latency_opt' | 'jev'

export const ROUTING_MODE_LABELS: Record<RoutingMode, string> = {
  fixed: 'Fixed',
  round_robin: 'Round Robin',
  cost_opt: 'Cost Optimized',
  intent: 'Intent-Based',
  latency_opt: 'Latency Optimized',
  jev: 'JEV (AI-Routed)',
}

export const ROUTING_MODE_DESCRIPTIONS: Record<RoutingMode, string> = {
  fixed: 'Always use the default model. No routing overhead.',
  round_robin: 'Distribute requests across models by weight. Good for load balancing and A/B testing.',
  cost_opt: 'Use the cheapest model that can handle the query complexity. Best for cost reduction.',
  intent: 'Match the model to the query type (code, math, creative, etc.). Best for quality per task.',
  latency_opt: 'Always prefer the fastest model. Best for real-time chat.',
  jev: 'An AI router picks the model tier and trims the tool list each turn. Adds one API call per turn.',
}

export type JevTier = 'fast' | 'standard' | 'heavy'

export const JEV_TIERS: { value: JevTier; label: string; hint: string }[] = [
  { value: 'fast', label: 'Fast', hint: 'Simple, low-effort queries' },
  { value: 'standard', label: 'Standard', hint: 'Typical queries' },
  { value: 'heavy', label: 'Heavy', hint: 'Complex queries; always used for "expert" complexity' },
]

export interface JevRoutingConfig {
  model?: string
  features?: { model_routing?: boolean; tool_filtering?: boolean }
  model_tier_map?: Partial<Record<JevTier, string>>
  tool_filtering_threshold?: 'yes' | 'unclear'
}

export const INTENT_OPTIONS = [
  { value: 'code', label: 'Code' },
  { value: 'math', label: 'Math' },
  { value: 'research', label: 'Research' },
  { value: 'creative', label: 'Creative Writing' },
  { value: 'data_analysis', label: 'Data Analysis' },
  { value: 'simple_qa', label: 'Simple Q&A' },
  { value: 'reasoning', label: 'Complex Reasoning' },
  { value: 'general', label: 'General' },
]

export interface RoutingRules {
  intents?: string[]
  min_complexity?: number
  max_complexity?: number
  cost_per_1k_input?: number
  cost_per_1k_output?: number
  priority?: number
  is_fallback?: boolean
}

export interface AgentLLMConfig {
  id: string;
  agent_id: string;
  tenant_id: string;
  name: string;
  provider: string;
  model_name: string;
  api_base?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  additional_params?: Record<string, any>;
  is_default: boolean;
  display_order: number;
  enabled: boolean;
  routing_rules?: RoutingRules;
  routing_weight?: number;
  created_at: string;
  updated_at: string;
}

export interface AgentLLMConfigCreate {
  name: string;
  provider: string;
  model_name: string;
  api_key: string;
  api_base?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  additional_params?: Record<string, any>;
  is_default?: boolean;
  display_order?: number;
  enabled?: boolean;
  routing_rules?: RoutingRules;
  routing_weight?: number;
}

export interface AgentLLMConfigUpdate {
  name?: string;
  provider?: string;
  model_name?: string;
  api_key?: string;
  api_base?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  additional_params?: Record<string, any>;
  is_default?: boolean;
  display_order?: number;
  enabled?: boolean;
  routing_rules?: RoutingRules;
  routing_weight?: number;
}

export interface AgentLLMConfigReorder {
  config_orders: Array<{
    config_id: string;
    display_order: number;
  }>;
}

// Note: Provider and model lists are now fetched dynamically from the API
// See web/lib/api/llm-providers.ts for API client functions

/**
 * Helper function to get a readable model label
 * @param provider - The LLM provider name
 * @param modelName - The model identifier
 * @returns A formatted model label
 */
export function getModelLabel(provider: string, modelName: string): string {
  // Return the model name as-is, or format it if needed
  return modelName || 'Unknown Model'
}
