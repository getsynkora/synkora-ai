import type { AgentCreateConfig, ActionCardStatus } from './cards/ActionConfirmCard'

export type { AgentCreateConfig, ActionCardStatus }

export interface ActionCard {
  type: 'create_agent'
  config: AgentCreateConfig
  status: ActionCardStatus
  createdAgentName?: string
  createdAgentSlug?: string
}

export interface IntegrationCard {
  provider: string
  message: string
  connect_url: string
  type?: 'oauth' | 'api_key'
}

export interface AgentCreatedInfo {
  name: string
  slug?: string
}

export interface ParsedMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  actionCard?: ActionCard
  integrationCard?: IntegrationCard
}

export function parseActionMarkers(text: string): {
  displayText: string
  actionCard: ActionCard | null
  integrationCard: IntegrationCard | null
  agentCreated: AgentCreatedInfo | null
} {
  let displayText = text
  let actionCard: ActionCard | null = null
  let integrationCard: IntegrationCard | null = null
  let agentCreated: AgentCreatedInfo | null = null

  // Parse __ACTION__....__ACTION__
  const actionMatch = text.match(/__ACTION__([\s\S]*?)__ACTION__/)
  if (actionMatch) {
    try {
      const parsed = JSON.parse(actionMatch[1].trim())
      if (parsed.type === 'create_agent' && parsed.config) {
        actionCard = {
          type: 'create_agent',
          config: parsed.config,
          status: 'pending',
        }
      }
    } catch {
      // ignore malformed JSON
    }
    displayText = displayText.replace(/__ACTION__[\s\S]*?__ACTION__/g, '').trim()
  }

  // Parse __INTEGRATION__....__INTEGRATION__
  const integrationMatch = text.match(/__INTEGRATION__([\s\S]*?)__INTEGRATION__/)
  if (integrationMatch) {
    try {
      const parsed = JSON.parse(integrationMatch[1].trim())
      if (parsed.provider) {
        integrationCard = {
          provider: parsed.provider,
          message: parsed.message || `Connect ${parsed.provider} to continue.`,
          connect_url: parsed.connect_url || '/settings/integrations',
          type: parsed.type || 'oauth',
        }
      }
    } catch {
      // ignore malformed JSON
    }
    displayText = displayText.replace(/__INTEGRATION__[\s\S]*?__INTEGRATION__/g, '').trim()
  }

  // Parse __AGENT_CREATED__....__AGENT_CREATED__
  const createdMatch = text.match(/__AGENT_CREATED__([\s\S]*?)__AGENT_CREATED__/)
  if (createdMatch) {
    try {
      const parsed = JSON.parse(createdMatch[1].trim())
      if (parsed.name) {
        agentCreated = { name: parsed.name, slug: parsed.slug }
      }
    } catch {
      // ignore malformed JSON
    }
    displayText = displayText.replace(/__AGENT_CREATED__[\s\S]*?__AGENT_CREATED__/g, '').trim()
  }

  return { displayText, actionCard, integrationCard, agentCreated }
}
