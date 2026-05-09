import { apiClient } from './http'

export interface AgentLandingData {
  slug: string
  agent_name: string
  tagline?: string
  long_description?: string
  hero_image_url?: string
  preview_video_url?: string
  gallery_images?: Array<{ url: string; caption?: string; order?: number }>
  example_conversations?: Array<{ title: string; messages: Array<{ role: string; content: string }> }>
  creator_bio?: string
  creator_display_name?: string
  seo_title?: string
  seo_description?: string
  og_image_url?: string
  cta_label?: string
  accent_color?: string
  view_count?: number
  pricing?: {
    id: string
    pricing_model: string
    session_credits?: number
    daily_credits?: number
    weekly_credits?: number
    monthly_credits?: number
    trial_messages?: number
  }
  creator?: {
    username: string
    display_name?: string
    bio?: string
    avatar_url?: string
    website_url?: string
    twitter_url?: string
    linkedin_url?: string
    github_url?: string
  }
}

export interface CreatorProfileData {
  username: string
  display_name?: string
  bio?: string
  avatar_url?: string
  banner_image_url?: string
  website_url?: string
  twitter_url?: string
  linkedin_url?: string
  github_url?: string
  stripe_onboarding_complete?: boolean
  total_earnings_credits?: number
  agents?: Array<{
    slug: string
    agent_name?: string
    tagline?: string
    hero_image_url?: string
    cta_label?: string
  }>
}

export interface DiscountValidation {
  valid: boolean
  discount_type?: string
  discount_value?: number
}

export interface AgentUserSubscription {
  id: string
  agent_id: string
  pricing_tier: string
  status: string
  started_at: string
  expires_at?: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

export async function getAgentLanding(slug: string): Promise<AgentLandingData | null> {
  try {
    const res = await fetch(`${API_URL}/api/public/agents/${slug}`)
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function updateAgentLandingProfile(agentName: string, data: Partial<AgentLandingData>): Promise<void> {
  await apiClient.request('PUT', `/api/v1/agents/${agentName}/public-profile`, data)
}

export async function publishAgentLandingPage(agentName: string): Promise<{ published: boolean; slug: string }> {
  const res = await apiClient.request('POST', `/api/v1/agents/${agentName}/public-profile/publish`)
  return res
}

export async function validateDiscountCode(code: string, agentPricingId: string): Promise<DiscountValidation> {
  const res = await fetch(`${API_URL}/api/public/discount-codes/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, agent_pricing_id: agentPricingId }),
  })
  return res.json()
}

export async function subscribeToAgent(
  agentSlug: string,
  pricingId: string,
  tier: string,
  discountCode?: string
): Promise<AgentUserSubscription> {
  const res = await apiClient.request('POST', `/api/public/agents/${agentSlug}/subscribe`, {
    pricing_id: pricingId,
    tier,
    discount_code: discountCode,
  })
  return res
}

export async function getCreatorProfile(username: string): Promise<CreatorProfileData | null> {
  try {
    const res = await fetch(`${API_URL}/creators/${username}`)
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function updateMyCreatorProfile(data: Partial<CreatorProfileData>): Promise<CreatorProfileData> {
  const res = await apiClient.request('PUT', '/api/v1/creator-profile', data)
  return res.profile
}
