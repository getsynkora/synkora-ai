/**
 * API client for LLM Provider Presets
 */

import { apiClient } from './client';

export interface ModelPreset {
  name: string;
  model_name: string;
  description: string;
  default_temperature: number;
  default_max_tokens: number | null;
  default_top_p: number | null;
  additional_params: Record<string, any> | null;
  max_input_tokens: number | null;
  max_output_tokens: number | null;
  // Comparison metadata (may be null if not in comparison data)
  cost_input_per_1m: number | null;
  cost_output_per_1m: number | null;
  is_open_source: boolean;
  quality_score: number | null;
  speed_tier: 'fast' | 'medium' | 'slow' | null;
  tags: string[];
}

/** Flat model entry returned by GET /api/v1/llm-providers/compare */
export interface ComparisonModelItem {
  provider_id: string;
  provider_name: string;
  name: string;
  model_name: string;
  description: string;
  max_input_tokens: number | null;
  max_output_tokens: number | null;
  default_max_tokens: number | null;
  cost_input_per_1m: number | null;
  cost_output_per_1m: number | null;
  is_open_source: boolean;
  quality_score: number | null;
  speed_tier: 'fast' | 'medium' | 'slow' | null;
  tags: string[];
  requires_api_key: boolean;
}

export interface ProviderPreset {
  provider_id: string;
  provider_name: string;
  description: string;
  requires_api_key: boolean;
  requires_api_base: boolean;
  default_api_base: string | null;
  setup_instructions: string | null;
  documentation_url: string | null;
  model_count?: number;
  models?: ModelPreset[];
}

let providersCache: ProviderPreset[] | null = null;
let providersPromise: Promise<ProviderPreset[]> | null = null;
const providerModelsCache = new Map<string, ModelPreset[]>();
const providerModelsPromises = new Map<string, Promise<ModelPreset[]>>();

/**
 * Get all available LLM provider presets
 */
export async function getLLMProviders(): Promise<ProviderPreset[]> {
  if (providersCache) {
    return providersCache;
  }
  if (!providersPromise) {
    providersPromise = apiClient
      .request('GET', '/api/v1/llm-providers')
      .then((data: ProviderPreset[]) => {
        providersCache = data;
        return data;
      })
      .finally(() => {
        providersPromise = null;
      });
  }
  return await providersPromise;
}

/**
 * Get details for a specific provider including models
 */
export async function getLLMProvider(providerId: string): Promise<ProviderPreset> {
  return await apiClient.request('GET', `/api/v1/llm-providers/${providerId}`);
}

/**
 * Get models for a specific provider
 */
export async function getProviderModels(providerId: string): Promise<ModelPreset[]> {
  if (providerModelsCache.has(providerId)) {
    return providerModelsCache.get(providerId)!;
  }
  if (!providerModelsPromises.has(providerId)) {
    providerModelsPromises.set(
      providerId,
      apiClient
        .request('GET', `/api/v1/llm-providers/${providerId}/models`)
        .then((data: ModelPreset[]) => {
          providerModelsCache.set(providerId, data);
          return data;
        })
        .finally(() => {
          providerModelsPromises.delete(providerId);
        })
    );
  }
  return await providerModelsPromises.get(providerId)!;
}

export type ComparisonFilter = 'open_source' | 'cheap' | 'fast' | 'quality' | undefined;
export type ComparisonSortBy = 'quality' | 'cost' | 'speed' | undefined;

/**
 * Get all models across all providers with comparison metadata.
 * Supports optional filter and sort_by query params.
 */
export async function getModelComparison(
  filter?: ComparisonFilter,
  sortBy?: ComparisonSortBy
): Promise<ComparisonModelItem[]> {
  const params = new URLSearchParams();
  if (filter) params.set('filter', filter);
  if (sortBy) params.set('sort_by', sortBy);
  const qs = params.toString() ? `?${params.toString()}` : '';
  return await apiClient.request('GET', `/api/v1/llm-providers/compare${qs}`);
}
