'use client'

import type { ParsedMessage } from './types'
import { ActionConfirmCard } from './cards/ActionConfirmCard'
import { IntegrationPromptCard } from './cards/IntegrationPromptCard'
import { AgentCreatedCard } from './cards/AgentCreatedCard'
import type { AgentCreateConfig } from './cards/ActionConfirmCard'

interface Props {
  message: ParsedMessage
  onConfirm: (config: AgentCreateConfig) => void
  onCancelAction: () => void
}

export function MessageRenderer({ message, onConfirm, onCancelAction }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] space-y-2 ${isUser ? 'items-end flex flex-col' : ''}`}>
        {/* Text content */}
        {message.content?.trim() && (
          <div
            className={`rounded-xl px-3 py-2.5 text-sm whitespace-pre-wrap leading-relaxed ${
              isUser
                ? 'bg-primary-500 text-white'
                : 'bg-gray-100 text-gray-900'
            }`}
          >
            {message.content}
          </div>
        )}

        {/* Action cards (agent creation confirmations) */}
        {message.actionCards?.map((card, i) =>
          card.status === 'created' && card.createdAgentName ? (
            <AgentCreatedCard
              key={i}
              agentName={card.createdAgentName}
              agentSlug={card.createdAgentSlug}
            />
          ) : (
            <ActionConfirmCard
              key={i}
              config={card.config}
              status={card.status}
              onConfirm={onConfirm}
              onCancel={onCancelAction}
            />
          )
        )}

        {/* Integration required card */}
        {message.integrationCard && (
          <IntegrationPromptCard
            provider={message.integrationCard.provider}
            message={message.integrationCard.message}
            connect_url={message.integrationCard.connect_url}
            type={message.integrationCard.type}
            compact
          />
        )}
      </div>
    </div>
  )
}
