import { apiClient } from './http';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface LensStatCard {
  total_sessions: number;
  total_requests: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  avg_latency_ms: number;
  total_cost_usd: number;
  avg_cost_per_session: number;
  failure_rate: number;
  total_tool_calls: number;
  failed_tool_calls: number;
  avg_tool_duration_ms: number;
}

export interface LensOverviewResponse {
  stats: LensStatCard;
  period_start: string;
  period_end: string;
}

export interface LensSessionRow {
  id: string;
  name: string;
  status: string;
  model_name: string | null;
  total_tokens: number;
  cost_usd: number;
  message_count: number;
  created_at: string | null;
}

export interface LensSessionsResponse {
  sessions: LensSessionRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LensTimelineEvent {
  event_type: 'user_message' | 'llm_call' | 'tool_call' | 'assistant_message';
  id: string;
  timestamp: string | null;
  sequence?: number;
  // user_message / assistant_message fields
  role?: string;
  content?: string;
  content_preview?: string;
  token_count?: number;
  input_tokens?: number;
  output_tokens?: number;
  latency_ms?: number;
  total_latency_ms?: number;
  total_cost_usd?: number;
  status?: string;
  error?: string;
  // llm_call fields
  model?: string;
  call_index?: number;
  cost_usd?: number;
  response_preview?: string;
  // llm_call input inspection fields
  system_prompt_preview?: string;
  messages_json?: string;  // JSON string: list of chat messages sent to LLM
  tools_json?: string;     // JSON string: list of tool definitions sent to LLM
  // tool call fields
  tool_name?: string;
  tool_args?: string;  // JSON string stored in ES text field
  tool_result?: string;  // JSON string stored in ES text field
  success?: boolean;
  duration_ms?: number;
  retry_count?: number;
  error_message?: string;
}

export interface LensSessionDetailResponse {
  conversation_id: string;
  name: string;
  status: string;
  created_at: string | null;
  timeline: LensTimelineEvent[];
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number;
  total_tool_calls: number;
  failed_tool_calls: number;
  message_count: number;
}

export interface LensModelBreakdown {
  model_name: string | null;
  tokens: number;
  cost_usd: number;
  calls: number;
}

export interface LensTokenDistributionResponse {
  by_model: LensModelBreakdown[];
  prompt_vs_completion: {
    input_tokens: number;
    output_tokens: number;
  };
}

export interface AlertResponse {
  id: string;
  agent_id: string;
  name: string;
  metric: string;
  condition: string;
  threshold: number;
  window_minutes: number;
  notify_method: string;
  notify_config: Record<string, unknown> | null;
  is_active: boolean;
  last_triggered_at: string | null;
  created_at: string | null;
}

export interface LensToolStat {
  tool_name: string;
  total_calls: number;
  success_count: number;
  failure_count: number;
  success_rate: number;  // 0.0 – 1.0
  avg_duration_ms: number;
  max_duration_ms: number;
  total_retries: number;
}

export interface LensToolAnalyticsResponse {
  tools: LensToolStat[];
  total_calls: number;
  total_failures: number;
  overall_success_rate: number;
}

export interface LensToolROIStat {
  tool_name: string;
  total_calls: number;
  calls_per_session: number;
  sessions_with: number;
  sessions_without: number;
  error_rate: number;
  avg_cost_with: number;
  avg_cost_without: number;
  cost_impact_pct: number;        // positive = adds cost
  avg_llm_calls_with: number;
  avg_llm_calls_without: number;
  completion_rate_with: number;   // 0.0–1.0
  completion_rate_without: number;
  completion_lift: number;        // positive = tool helps resolution
  verdict: 'keep' | 'review' | 'remove' | 'neutral';
}

export interface LensToolROIResponse {
  tools: LensToolROIStat[];
  total_sessions: number;
  period_start: string;
  period_end: string;
}

export interface AlertCreateBody {
  name: string;
  metric: 'failure_rate' | 'cost_per_session' | 'avg_latency_ms' | 'total_cost_usd' | 'token_count';
  condition: 'gt' | 'lt';
  threshold: number;
  window_minutes?: number;
  notify_method?: 'email' | 'webhook';
  notify_config?: Record<string, unknown>;
  is_active?: boolean;
}

export type AlertUpdateBody = Partial<AlertCreateBody>;

export type LensRange = '24h' | '7d' | '30d' | '90d';

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function getLensOverview(agentSlug: string, range: LensRange = '7d'): Promise<LensOverviewResponse> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/lens/overview?range=${range}`);
}

export async function getLensTokenDistribution(
  agentSlug: string,
  range: LensRange = '7d'
): Promise<LensTokenDistributionResponse> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/lens/token-distribution?range=${range}`);
}

export async function getLensSessions(
  agentSlug: string,
  range: LensRange = '7d',
  page = 1,
  pageSize = 20
): Promise<LensSessionsResponse> {
  return apiClient.request(
    'GET',
    `/api/v1/agents/${agentSlug}/lens/sessions?range=${range}&page=${page}&page_size=${pageSize}`
  );
}

export async function getLensSessionDetail(
  agentSlug: string,
  sessionId: string
): Promise<LensSessionDetailResponse> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/lens/sessions/${sessionId}`);
}

export async function getLensToolAnalytics(
  agentSlug: string,
  range: LensRange = '7d'
): Promise<LensToolAnalyticsResponse> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/lens/tool-analytics?range=${range}`);
}

export async function getLensAlerts(agentSlug: string): Promise<AlertResponse[]> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/lens/alerts`);
}

export async function createLensAlert(agentSlug: string, body: AlertCreateBody): Promise<AlertResponse> {
  return apiClient.request('POST', `/api/v1/agents/${agentSlug}/lens/alerts`, body);
}

export async function updateLensAlert(
  agentSlug: string,
  alertId: string,
  body: AlertUpdateBody
): Promise<AlertResponse> {
  return apiClient.request('PUT', `/api/v1/agents/${agentSlug}/lens/alerts/${alertId}`, body);
}

export async function deleteLensAlert(agentSlug: string, alertId: string): Promise<void> {
  return apiClient.request('DELETE', `/api/v1/agents/${agentSlug}/lens/alerts/${alertId}`);
}

export async function getLensToolROI(
  agentSlug: string,
  range: LensRange = '7d'
): Promise<LensToolROIResponse> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/lens/tool-roi?range=${range}`);
}
