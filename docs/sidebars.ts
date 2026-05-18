import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Getting Started',
      collapsed: false,
      items: [
        'getting-started/quick-start',
        'getting-started/installation',
        'getting-started/configuration',
        'getting-started/first-agent',
        'getting-started/authentication',
      ],
    },
    {
      type: 'category',
      label: 'Core Concepts',
      items: [
        'concepts/agents',
        'concepts/knowledge-bases',
        'concepts/tools',
        'concepts/conversations',
        'concepts/multi-tenancy',
        'concepts/billing',
        'concepts/security',
      ],
    },
    {
      type: 'category',
      label: 'API Reference',
      items: [
        'api-reference/overview',
        'api-reference/agents/index',
        'api-reference/knowledge-bases/index',
        'api-reference/billing/usage',
        'api-reference/integrations/oauth',
        'api-reference/webhooks',
        'api-reference/rate-limits',
        'api-reference/errors',
      ],
    },
    {
      type: 'category',
      label: 'Guides',
      items: [
        {
          type: 'category',
          label: 'Agents',
          items: [
            'guides/agents/add-tools',
            'guides/agents/create-rag-agent',
            'guides/agents/custom-tools',
            'guides/agents/mcp-servers',
          ],
        },
        {
          type: 'category',
          label: 'Integrations',
          items: [
            'guides/integrations/embed-widget',
            'guides/integrations/slack-bot',
            'guides/integrations/teams-bot',
            'guides/integrations/telegram-bot',
            'guides/integrations/whatsapp-bot',
            'guides/integrations/chrome-extension',
          ],
        },
        {
          type: 'category',
          label: 'Knowledge Base',
          items: [
            'guides/knowledge-base/document-processing',
            'guides/knowledge-base/advanced-rag',
            'guides/knowledge-base/setup-qdrant',
            'guides/knowledge-base/setup-pinecone',
          ],
        },
        {
          type: 'category',
          label: 'Authentication',
          items: [
            'guides/auth/api-keys',
            'guides/auth/oauth-providers',
            'guides/auth/sso-okta',
          ],
        },
        {
          type: 'category',
          label: 'Deployment',
          items: [
            'guides/deployment/docker',
            'guides/deployment/kubernetes',
            'guides/deployment/production',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'SDK',
      items: [
        {
          type: 'category',
          label: 'Flutter',
          items: [
            'sdk/flutter/chat-sdk',
            'sdk/flutter/push-notifications',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'Architecture',
      items: [
        'architecture/overview',
        'architecture/backend',
        'architecture/frontend',
        'architecture/database',
        'architecture/caching',
        'architecture/background-jobs',
        'architecture/streaming',
        'architecture/multi-tenancy',
        'architecture/security-and-reliability',
      ],
    },
  ],
};

export default sidebars;
