# Design: SEO, Competitor Positioning & Technical SEO

**Date:** 2026-05-08
**Domain:** https://synkora.ai
**Status:** Approved

---

## Overview

Synkora is currently misclassified by search engines as a "role-based AI SaaS tool" rather than an
"open-source multitenant LLM application platform." This work fixes technical SEO gaps, corrects
remaining copy, and creates honest competitor comparison pages targeting high-intent searches like
"dify alternative open source" and "crewai no code alternative."

---

## Section 1 — Technical SEO Foundation

### 1.1 `web/app/sitemap.ts`

Next.js App Router sitemap generator. Returns `MetadataRoute.Sitemap`.

**Include (with priorities):**

| Route | Priority | Change Freq |
|-------|----------|-------------|
| `/` | 1.0 | weekly |
| `/about` | 0.8 | monthly |
| `/pricing` | 0.9 | weekly |
| `/how-it-works` | 0.8 | monthly |
| `/use-cases` | 0.8 | monthly |
| `/alternatives` | 0.8 | monthly |
| `/alternatives/dify` | 0.9 | monthly |
| `/alternatives/crewai` | 0.9 | monthly |
| `/alternatives/langchain` | 0.9 | monthly |
| `/alternatives/flowise` | 0.9 | monthly |
| `/alternatives/openclaw` | 0.9 | monthly |
| `/contact` | 0.5 | yearly |
| `/terms` | 0.3 | yearly |
| `/privacy` | 0.3 | yearly |
| `/security` | 0.4 | yearly |

**Exclude:** everything under `/(auth)/`, `/(dashboard)/`, `/api/`, `/war-room/`, `/live-lab/`

Base URL from `process.env.NEXT_PUBLIC_APP_URL || 'https://synkora.ai'`.

### 1.2 `web/app/robots.ts`

```
User-agent: *
Allow: /
Disallow: /dashboard/
Disallow: /api/
Disallow: /war-room/
Disallow: /live-lab/
Disallow: /signup
Disallow: /signin
Disallow: /verify-email
Disallow: /reset-password
Disallow: /forgot-password
Disallow: /accept-invite
Sitemap: https://synkora.ai/sitemap.xml
```

### 1.3 `metadataBase` in `web/app/layout.tsx`

Add `metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'https://synkora.ai')` to the
existing `metadata` export. Required for relative OG image URL resolution.

### 1.4 JSON-LD Structured Data in `web/app/layout.tsx`

Add a `<script type="application/ld+json">` block inside `<body>` with `SoftwareApplication` schema:

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Synkora",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web",
  "description": "Multitenant, API-first open-source LLM application platform for building, deploying, and managing AI agents.",
  "url": "https://synkora.ai",
  "softwareVersion": "latest",
  "license": "https://opensource.org/licenses/MIT",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD",
    "description": "Free tier available. Self-hostable."
  }
}
```

---

## Section 2 — Meta Fixes on Existing Pages

### 2.1 `/use-cases/page.tsx`

Current description: "automate roles across your organization"
New title: `"Use Cases – Synkora LLM Platform"`
New description: `"See what you can build on Synkora — AI agents for product management, engineering, customer support, marketing, and more. API-first, multitenant, self-hostable."`

### 2.2 `/pricing/page.tsx`

Currently `'use client'` — cannot export `metadata` directly.
Fix: Create a thin server wrapper `pricing/layout.tsx` that exports `metadata`. Inner `page.tsx` stays client component unchanged.

New title: `"Pricing – Synkora LLM Platform"`
New description: `"Flexible pricing for the open-source LLM application platform. Free tier available. Self-host for free or use Synkora Cloud."`

### 2.3 `/how-it-works/page.tsx`

Feature card "No Code Required" renamed to "Visual Builder".
Description updated to: "Build and configure AI agents through an intuitive web interface — or go straight to the API."
This is accurate (the UI exists) without signaling it's a non-developer tool.

### 2.4 `/contact/page.tsx`, `/terms/page.tsx`, `/privacy/page.tsx`, `/security/page.tsx`

Add proper `export const metadata` to each:
- Contact: "Contact Synkora – Open-Source LLM Platform"
- Terms: "Terms of Service – Synkora"
- Privacy: "Privacy Policy – Synkora"
- Security: "Security – Synkora"

All with canonical descriptions to avoid thin-content penalties.

---

## Section 3 — Competitor Comparison Pages

### Architecture

All pages live under `web/app/alternatives/`.

```
web/app/alternatives/
  layout.tsx          ← shared metadata base + nav
  page.tsx            ← index: "Synkora Alternatives & Comparisons"
  dify/page.tsx
  crewai/page.tsx
  langchain/page.tsx
  flowise/page.tsx
  openclaw/page.tsx
```

### Page Structure (each comparison page)

1. **Breadcrumb nav** — Home > Alternatives > [Competitor]
2. **Hero** — "Synkora vs [Competitor]" H1. One accurate sentence about each.
3. **What is [Competitor]?** — 2-3 honest sentences. No strawmanning.
4. **What is Synkora?** — 2-3 sentences leading with platform/infrastructure.
5. **Feature comparison table** — Only real, verifiable features. Three states: yes / no / partial.
6. **When to choose Synkora** — Specific, honest use cases.
7. **When to choose [Competitor]** — Honest. Don't disparage competitors.
8. **CTA** — "Try Synkora free · Self-host in minutes"

### Competitor Data (verified)

#### Dify
- Open-source, self-hostable, has RAG, multi-tenant, LLM routing
- Has visual workflow DAG editor (more mature than Synkora's)
- Large community, more polished no-code experience
- Synkora advantages: stronger API-first design (SSE/WebSocket), Slack/WhatsApp/Teams/Telegram multi-channel, MCP server support, HITL approval gates, sub-agents, agent API keys, scheduled tasks

#### CrewAI
- Python framework only — no web UI, no deployment, no multi-tenancy
- Code-first role-based agent definitions
- Large developer community, flexible Python API
- Synkora advantages: full web UI, multi-tenant, deployment channels, RAG, billing, scheduling, monitoring
- CrewAI advantages: full Python flexibility, role definitions are explicit in code

#### LangChain
- Library/framework, not a platform — requires significant custom code
- No built-in UI, no multi-tenancy, no deployment infrastructure
- Huge ecosystem of integrations and community
- Synkora advantages: complete platform — UI, deployment, RAG, billing, monitoring, multi-tenancy
- LangChain advantages: maximum flexibility, massive integration ecosystem, embeddable in any Python app

#### Flowise
- Visual drag-and-drop LLM flow builder
- Single-user focused, local-first
- Good for prototyping and simple flows
- Synkora advantages: multi-tenant, production-grade deployment, API-first, billing, scheduling, MCP, sub-agents, WhatsApp/Slack/Teams channels
- Flowise advantages: very visual, easier for non-technical prototyping

#### OpenClaw
- Local-first personal AI assistant — runs as a daemon on Mac/Windows/Linux
- Single-user by design, Node.js
- Multi-channel inbox for personal messaging (WhatsApp, Telegram, Discord, iMessage, Signal)
- Supports local models, voice, browser control, shell execution
- **Key distinction:** OpenClaw is for individuals. Synkora is for teams/companies building AI products.
- Not really direct competitors — different use cases entirely. Page frames this honestly.
- Synkora advantages: multi-tenant, team management, API-first for product deployment, billing, RAG for company data
- OpenClaw advantages: personal-use, local privacy, voice, iMessage/Signal, shell/browser access

### `/alternatives` Index Page

Lists all 5 comparisons with one-line summaries. Also includes:
- Brief "How Synkora fits in the ecosystem" paragraph
- Accurate classification note: platform vs framework vs personal assistant

---

## Section 4 — `NEXT_PUBLIC_APP_URL` env var

Add to `web/.env.example`:
```
NEXT_PUBLIC_APP_URL=https://synkora.ai
```

Used by: sitemap.ts, robots.ts, JSON-LD, metadataBase.

---

## Key Constraints

- **No fake data.** All feature claims must be verifiable in the codebase or competitor docs.
- **No disparagement.** Competitor "cons" are framed as "better for X use case" not "bad at Y."
- **No "no code required" as primary claim.** Use "visual builder" or "UI or API."
- **All pages static-renderable** — comparison pages use no client-side data fetching.
- **Canonical URLs** resolve through `metadataBase` set in root layout.

---

## Files Changed / Created

### New files
- `web/app/sitemap.ts`
- `web/app/robots.ts`
- `web/app/alternatives/layout.tsx`
- `web/app/alternatives/page.tsx`
- `web/app/alternatives/dify/page.tsx`
- `web/app/alternatives/crewai/page.tsx`
- `web/app/alternatives/langchain/page.tsx`
- `web/app/alternatives/flowise/page.tsx`
- `web/app/alternatives/openclaw/page.tsx`
- `web/app/pricing/layout.tsx` (server wrapper for metadata)

### Modified files
- `web/app/layout.tsx` — add `metadataBase`, JSON-LD script
- `web/app/use-cases/page.tsx` — update metadata
- `web/app/how-it-works/page.tsx` — rename "No Code Required" feature card
- `web/app/contact/page.tsx` — add metadata
- `web/app/terms/page.tsx` — add metadata
- `web/app/privacy/page.tsx` — add metadata
- `web/app/security/page.tsx` — add metadata
- `web/.env.example` — add `NEXT_PUBLIC_APP_URL`
