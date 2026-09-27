export interface Webhook {
  id: string
  agent_id: string
  name: string
  provider: 'github' | 'clickup' | 'jira' | 'slack' | 'custom'
  webhook_url: string
  is_active: boolean
  event_types: string[] | null
  config: Record<string, any> | null
  success_count: number
  failure_count: number
  last_triggered_at: string | null
  created_at: string
  updated_at: string
}

export interface WebhookCreate {
  name: string
  provider: 'github' | 'clickup' | 'jira' | 'slack' | 'custom'
  event_types?: string[]
  config?: Record<string, any>
  retry_config?: Record<string, any>
}

export interface WebhookUpdate {
  name?: string
  is_active?: boolean
  event_types?: string[]
  config?: Record<string, any>
  retry_config?: Record<string, any>
}

export interface WebhookEvent {
  id: string
  webhook_id: string
  event_id: string | null
  event_type: string
  payload: Record<string, any>
  status: 'pending' | 'processing' | 'completed' | 'success' | 'failed' | 'retrying' | 'retry' | 'skipped'
  parsed_data: Record<string, any> | null
  error_message: string | null
  retry_count: number
  agent_execution_id: string | null
  processing_started_at: string | null
  processing_completed_at: string | null
  created_at: string
  updated_at: string
}

export interface WebhookStats {
  webhook_id: string
  success_count: number
  failure_count: number
  last_triggered_at: string | null
  event_status_counts: Record<string, number>
}

/** Stored in webhook.config.jev_gate. */
export interface JevGateConfig {
  enabled: boolean
  mode: 'shadow' | 'enforce'
  min_actionable: number
  instructions?: string
}

/** Stored in event.parsed_data.jev_gate when the gate was enabled. */
export interface JevGateVerdict {
  action: 'run' | 'skip'
  mode: 'shadow' | 'enforce'
  actionable: number | null
  reason: string
  latency_ms: number | null
}
