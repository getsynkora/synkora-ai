import { apiClient } from './http'

export type EmailTemplateType = 'BUILTIN' | 'CUSTOM_HTML' | 'SENDGRID' | 'MAILCHIMP' | 'BREVO'

export interface EmailTemplate {
  id: string
  name: string
  description?: string | null
  template_type: EmailTemplateType
  builtin_name?: string | null
  html_content?: string | null
  external_provider?: string | null
  external_template_id?: string | null
  external_config?: Record<string, any> | null
  preview_html?: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreateEmailTemplatePayload {
  name: string
  description?: string
  template_type: EmailTemplateType
  builtin_name?: string
  html_content?: string
  external_provider?: string
  external_template_id?: string
  external_config?: Record<string, any>
  preview_html?: string
}

export async function listEmailTemplates(): Promise<EmailTemplate[]> {
  const res = await apiClient.request('GET', '/api/v1/email-templates')
  return res?.data ?? res ?? []
}

export async function getEmailTemplate(id: string): Promise<EmailTemplate> {
  const res = await apiClient.request('GET', `/api/v1/email-templates/${id}`)
  return res?.data ?? res
}

export async function createEmailTemplate(payload: CreateEmailTemplatePayload): Promise<EmailTemplate> {
  const res = await apiClient.request('POST', '/api/v1/email-templates', payload)
  return res?.data ?? res
}

export async function updateEmailTemplate(id: string, payload: Partial<CreateEmailTemplatePayload> & { is_active?: boolean }): Promise<EmailTemplate> {
  const res = await apiClient.request('PUT', `/api/v1/email-templates/${id}`, payload)
  return res?.data ?? res
}

export async function deleteEmailTemplate(id: string): Promise<void> {
  await apiClient.request('DELETE', `/api/v1/email-templates/${id}`)
}

export async function getAgentEmailTemplate(agentSlug: string): Promise<EmailTemplate | null> {
  const res = await apiClient.request('GET', `/api/v1/agents/${agentSlug}/email-template`)
  return res?.data ?? null
}

export async function assignEmailTemplate(agentSlug: string, emailTemplateId: string): Promise<EmailTemplate> {
  const res = await apiClient.request('PUT', `/api/v1/agents/${agentSlug}/email-template`, { email_template_id: emailTemplateId })
  return res?.data ?? res
}

export async function removeEmailTemplate(agentSlug: string): Promise<void> {
  await apiClient.request('DELETE', `/api/v1/agents/${agentSlug}/email-template`)
}
