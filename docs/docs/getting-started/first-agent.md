---
sidebar_position: 4
---

# Create Your First Agent

This walkthrough follows the current dashboard flow in `web/app/(dashboard)/agents/create/page.tsx` and the follow-up agent workspace in `web/app/(dashboard)/agents/[agentName]/view/page.tsx`.

## Before You Start

Make sure you have:

- the web app running at `http://localhost:3005`
- a working account that can access the dashboard
- at least one LLM provider key ready

The current create flow will not let you finish without:

- `name`
- `description`
- `llm_provider`
- `llm_model`
- `llm_api_key`
- `system_prompt`

## Step 1: Open the Create Flow

1. Sign in to Synkora.
2. Open **Agents**.
3. Click **Create Agent**.

The create screen is a four-step wizard:

1. **Basics**
2. **AI Model**
3. **Personality**
4. **Review**

## Step 2: Complete Basics

On the **Basics** step, fill in the agent identity first:

1. Enter the agent name.
2. Add a short description of the job it should do.
3. Optionally upload an avatar.
4. Optionally choose a template or public-facing settings if they fit your use case.

Keep the first version narrow. Good first agents are usually one of these:

- support assistant
- documentation assistant
- internal operations helper
- research assistant

If the name already exists, the create flow returns you to **Basics** and shows the conflict there.

## Step 3: Configure the AI Model

On the **AI Model** step:

1. Select the provider.
2. Select the model.
3. Paste the provider API key.
4. Adjust optional fields only if you need them, such as API base, temperature, max tokens, or `top_p`.

This is the minimum model configuration the current UI enforces before you can continue.

## Step 4: Set Personality and Instructions

On the **Personality** step:

1. Choose one of the built-in presets:
   - Friendly
   - Professional
   - Expert
   - Custom
2. Review the generated system prompt.
3. Replace it with your own prompt if needed.

The wizard requires a non-empty system prompt before it will move forward.

## Step 5: Review and Create

On **Review**, confirm the configuration and create the agent.

The current create flow does two things:

1. Creates the agent record and its initial LLM config.
2. If you selected capabilities, enables them in bulk after the agent is created.

On success, Synkora redirects to:

```text
/agents/{createdAgentSlug}/edit?tab=llm-models
```

## Step 6: Validate the Agent

After creation, use this order instead of configuring every feature at once.

### 1. Test the core behavior

Open:

```text
/agents/{agentName}/chat
```

Send a few prompts and confirm the response quality before adding knowledge or tools.

### 2. Review the model config

Open:

```text
/agents/{agentName}/llm-configs
```

Use this page when you need to change provider, model, or model settings after the initial setup.

### 3. Attach knowledge

Open:

```text
/agents/{agentName}/knowledge-bases
```

Use this when the agent needs grounded answers from your documents or site content.

See [Create a RAG Agent](/docs/guides/agents/create-rag-agent).

### 4. Add tools

Open:

```text
/agents/{agentName}/tools
```

This is where you turn the agent from “answers questions” into “takes action”.

See [Add Tools](/docs/guides/agents/add-tools).

### 5. Pick delivery surfaces

The current agent workspace exposes these deployment and delivery paths:

- `landing-page`
- `widgets`
- `domains`
- `api-keys`
- `slack-bots`
- `messaging-bots`
- `telegram-bots`
- `webhooks`
- `voice`

Pick one surface first. Do not configure everything on day one.

### 6. Turn on advanced features only when needed

The current UI also exposes:

- `autonomous`
- `sub-agents`
- `mcp-servers`
- `outputs`
- `chat-customization`
- `lens`
- `database-connections`
- `compute`
- `subscriptions`

These are useful, but they should come after the base agent behavior is stable.

## Recommended First-Agent Sequence

For most teams, the cleanest path is:

1. Create the agent.
2. Test it in chat.
3. Attach one knowledge base if it needs context.
4. Add one or two tools.
5. Expose it through a widget, API key, or one messaging channel.
6. Watch usage and quality in Lens.

## Related Pages

- [Agents](/docs/concepts/agents)
- [Knowledge Bases](/docs/concepts/knowledge-bases)
- [Embed the Web Widget](/docs/guides/integrations/embed-widget)
