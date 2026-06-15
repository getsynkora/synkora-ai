import { apiClient } from './http';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface EvalDataset {
  dataset_id: string;
  agent_id: string;
  tenant_id: string;
  name: string;
  description: string;
  case_count: number;
  doc_type: 'dataset';
}

export interface EvalCase {
  case_id: string;
  dataset_id: string;
  agent_id: string;
  tenant_id: string;
  input: string;
  expected_criteria: string;
  tags: string[];
  doc_type: 'case';
}

export interface EvalRun {
  run_id: string;
  dataset_id: string;
  agent_id: string;
  tenant_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  total_cases: number;
  passed: number;
  failed: number;
  pass_rate: number;
  avg_score: number;
  avg_latency_ms: number;
  ran_at: string;
}

export interface EvalResult {
  result_id: string;
  run_id: string;
  case_id: string;
  dataset_id: string;
  input: string;
  expected_criteria: string;
  actual_output: string;
  score: number;
  passed: number; // 1 or 0
  reasoning: string;
  latency_ms: number;
}

// ---------------------------------------------------------------------------
// Feedback & Outcome
// ---------------------------------------------------------------------------

export async function postFeedback(
  agentSlug: string,
  messageId: string,
  rating: 1 | -1,
  channel = 'console',
  comment?: string,
): Promise<void> {
  await apiClient.request('POST', `/api/v1/agents/${agentSlug}/feedback`, {
    message_id: messageId,
    rating,
    channel,
    ...(comment ? { comment } : {}),
  });
}

export async function postOutcome(
  agentSlug: string,
  conversationId: string,
  helpful: boolean,
): Promise<void> {
  await apiClient.request('POST', `/api/v1/agents/${agentSlug}/outcome`, {
    conversation_id: conversationId,
    helpful,
  });
}

// ---------------------------------------------------------------------------
// Datasets
// ---------------------------------------------------------------------------

export async function listDatasets(agentSlug: string): Promise<{ datasets: EvalDataset[]; total: number }> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/eval/datasets`);
}

export async function createDataset(
  agentSlug: string,
  name: string,
  description = '',
): Promise<EvalDataset> {
  return apiClient.request('POST', `/api/v1/agents/${agentSlug}/eval/datasets`, { name, description });
}

export async function deleteDataset(agentSlug: string, datasetId: string): Promise<void> {
  await apiClient.request('DELETE', `/api/v1/agents/${agentSlug}/eval/datasets/${datasetId}`);
}

// ---------------------------------------------------------------------------
// Cases
// ---------------------------------------------------------------------------

export async function listCases(
  agentSlug: string,
  datasetId: string,
): Promise<{ cases: EvalCase[]; total: number }> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/eval/datasets/${datasetId}/cases`);
}

export async function createCase(
  agentSlug: string,
  datasetId: string,
  input: string,
  expectedCriteria: string,
  tags: string[] = [],
): Promise<EvalCase> {
  return apiClient.request('POST', `/api/v1/agents/${agentSlug}/eval/datasets/${datasetId}/cases`, {
    input,
    expected_criteria: expectedCriteria,
    tags,
  });
}

export async function deleteCase(
  agentSlug: string,
  datasetId: string,
  caseId: string,
): Promise<void> {
  await apiClient.request('DELETE', `/api/v1/agents/${agentSlug}/eval/datasets/${datasetId}/cases/${caseId}`);
}

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

export async function triggerEvalRun(
  agentSlug: string,
  datasetId: string,
): Promise<{ run_id: string; status: string; dataset_id: string }> {
  return apiClient.request('POST', `/api/v1/agents/${agentSlug}/eval/datasets/${datasetId}/run`);
}

export async function listRuns(agentSlug: string): Promise<{ runs: EvalRun[]; total: number }> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/eval/runs`);
}

export async function getRun(agentSlug: string, runId: string): Promise<EvalRun> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/eval/runs/${runId}`);
}

export async function getRunResults(
  agentSlug: string,
  runId: string,
): Promise<{ results: EvalResult[]; total: number }> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/eval/runs/${runId}/results`);
}
