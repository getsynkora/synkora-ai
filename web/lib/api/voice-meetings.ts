import { apiClient } from './client'

export interface PhoneSettings {
  enabled: boolean
  vapi_phone_number_id: string | null
  stt_provider: string
  tts_provider: string
  tts_voice_id: string | null
}

export interface WebCallSettings {
  enabled: boolean
  show_on_agent_card: boolean
  vapi_public_key: string | null
}

export interface MeetingBotSettings {
  enabled: boolean
  bot_name: string
  bot_avatar_url: string | null
  platforms: string[]
  auto_record: boolean
}

export interface VoiceMeetingsConfig {
  phone: PhoneSettings
  web_call: WebCallSettings
  meeting_bot: MeetingBotSettings
}

export interface MeetingBot {
  bot_id: string
  bot_name: string
  status_code: string
  meeting_url: string
  created_at: string
}

export interface MeetingTranscriptSegment {
  speaker: string
  text: string
  start_time: number | null
}

export interface MeetingTranscript {
  bot_id: string
  segments: MeetingTranscriptSegment[]
  full_text: string
  segment_count: number
}

export const DEFAULT_CONFIG: VoiceMeetingsConfig = {
  phone: {
    enabled: false,
    vapi_phone_number_id: null,
    stt_provider: 'deepgram',
    tts_provider: 'elevenlabs',
    tts_voice_id: null,
  },
  web_call: {
    enabled: false,
    show_on_agent_card: true,
    vapi_public_key: null,
  },
  meeting_bot: {
    enabled: false,
    bot_name: 'AI Assistant',
    bot_avatar_url: null,
    platforms: ['zoom', 'google_meet', 'teams', 'slack_huddle'],
    auto_record: true,
  },
}

export function getVoiceMeetingsConfig(agentSlug: string): Promise<VoiceMeetingsConfig> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/voice-meetings`)
}

export function saveVoiceMeetingsConfig(agentSlug: string, config: VoiceMeetingsConfig): Promise<VoiceMeetingsConfig> {
  return apiClient.request('PUT', `/api/v1/agents/${agentSlug}/voice-meetings`, config)
}

export function getWebCallToken(agentSlug: string): Promise<{ public_key: string; agent_id: string; agent_name: string; vapi_assistant_id: string | null }> {
  return apiClient.request('POST', `/api/v1/agents/${agentSlug}/voice-meetings/web-call-token`)
}

export function dispatchMeetingBot(agentSlug: string, url: string, scheduledAt?: string): Promise<MeetingBot> {
  return apiClient.request('POST', `/api/v1/agents/${agentSlug}/meetings/dispatch`, {
    url,
    scheduled_at: scheduledAt ?? null,
  })
}

export function listMeetings(agentSlug: string, botStatus?: string): Promise<{ bots: MeetingBot[]; total: number }> {
  const params = botStatus ? `?bot_status=${botStatus}` : ''
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/meetings${params}`)
}

export function removeMeetingBot(agentSlug: string, botId: string): Promise<{ success: boolean }> {
  return apiClient.request('DELETE', `/api/v1/agents/${agentSlug}/meetings/${botId}`)
}

export function getMeetingTranscript(agentSlug: string, botId: string): Promise<MeetingTranscript> {
  return apiClient.request('GET', `/api/v1/agents/${agentSlug}/meetings/${botId}/transcript`)
}
