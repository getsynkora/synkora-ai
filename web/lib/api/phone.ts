import { apiClient } from './http'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PhoneNumber {
  id: string
  agent_id: string
  provider: string
  phone_number: string
  is_provisioned: boolean
  is_active: boolean
  created_at: string | null
}

export interface PhoneCallMessage {
  role: string
  content: string
  created_at: string | null
}

export interface PhoneCall {
  id: string
  agent_id: string
  phone_number_id: string | null
  conversation_id: string | null
  provider: string
  provider_call_id: string
  caller_number: string | null
  status: 'ringing' | 'active' | 'completed' | 'failed' | 'no_answer'
  started_at: string | null
  answered_at: string | null
  ended_at: string | null
  duration_seconds: number | null
  recording_url: string | null
  cost_cents: number | null
  messages?: PhoneCallMessage[]
  created_at: string | null
}

export interface PhoneConfig {
  enabled: boolean
  provider: string
  greeting: string
  end_call_message: string
  voice_provider: string | null
  voice_id: string | null
  language: string
  max_duration_seconds: number
  record_calls: boolean
  vapi_assistant_id?: string
  webhook_secret?: string
}

// ---------------------------------------------------------------------------
// Phone numbers
// ---------------------------------------------------------------------------

export function getPhoneNumbers(): Promise<PhoneNumber[]> {
  return apiClient.request('GET', '/api/v1/phone/numbers')
}

export function addPhoneNumber(data: {
  phone_number: string
  provider?: string
  agent_id: string
}): Promise<PhoneNumber> {
  return apiClient.request('POST', '/api/v1/phone/numbers', data)
}

export function removePhoneNumber(numberId: string): Promise<void> {
  return apiClient.request('DELETE', `/api/v1/phone/numbers/${numberId}`)
}

// ---------------------------------------------------------------------------
// Calls
// ---------------------------------------------------------------------------

export function getPhoneCalls(params?: {
  agent_id?: string
  page?: number
  page_size?: number
}): Promise<PhoneCall[]> {
  const qs = params
    ? '?' + new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]))).toString()
    : ''
  return apiClient.request('GET', `/api/v1/phone/calls${qs}`)
}

export function getPhoneCall(callId: string): Promise<PhoneCall> {
  return apiClient.request('GET', `/api/v1/phone/calls/${callId}`)
}

// ---------------------------------------------------------------------------
// Credentials
// ---------------------------------------------------------------------------

export function saveVapiCredential(apiKey: string): Promise<void> {
  return apiClient.request('POST', '/api/v1/phone/credentials', { provider: 'vapi', api_key: apiKey })
}

export function checkCredential(provider = 'vapi'): Promise<{ provider: string; configured: boolean }> {
  return apiClient.request('GET', `/api/v1/phone/credentials?provider=${provider}`)
}

// ---------------------------------------------------------------------------
// Agent phone config
// ---------------------------------------------------------------------------

export function getPhoneConfig(agentSlug: string): Promise<Partial<PhoneConfig>> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/phone-config`)
}

export function savePhoneConfig(agentSlug: string, config: PhoneConfig): Promise<PhoneConfig> {
  return apiClient.request('PUT', `/api/v1/agents/${agentSlug}/phone-config`, config)
}
