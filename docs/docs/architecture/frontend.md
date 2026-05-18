---
sidebar_position: 3
---

# Frontend Architecture

The frontend lives in `web/` and is built as one Next.js application. It does not only power the dashboard. The same app also serves the public marketing site, docs, blog, pricing pages, share flows, and public agent pages.

## Frontend Diagram

![Synkora frontend high-level architecture diagram.](/images/docs/architecture/frontend-hld.svg)

## Route Structure

| Area | Example Paths | Purpose |
| --- | --- | --- |
| `app/(auth)` | `/signin`, `/signup`, `/forgot-password`, `/verify-email` | Authentication flows |
| `app/(dashboard)` | `/agents`, `/knowledge-bases`, `/billing`, `/mcp-servers`, `/settings` | Authenticated operator workspace |
| `app/(public)` | `/a/*`, `/creators/*` | Public-facing app surfaces |
| Top-level public routes | `/blog`, `/docs`, `/pricing`, `/integrations`, `/about`, `/contact` | Marketing, content, and docs pages |

This means docs and blog are already part of the main product application, not separate apps.

## Main Frontend Directories

| Path | Responsibility |
| --- | --- |
| `web/app` | Route files and layouts |
| `web/components` | Reusable and domain-specific UI |
| `web/components/agents` | Agent creation, editing, integrations, model config |
| `web/components/chat` | Chat UI, markdown rendering, streaming-facing components |
| `web/components/public` | Public site surfaces |
| `web/lib/api` | Domain-specific API modules plus the compatibility barrel export |
| `web/lib/auth` | Token and session helpers |
| `web/lib/store` | Zustand stores |
| `web/lib/data` | Frontend data/config helpers |
| `web/lib/types` | Shared TypeScript types |
| `web/hooks` and `web/lib/hooks` | Reusable hooks |

## Frontend Data Flow

The current frontend is organized around domain-specific API modules.

1. Route files in `web/app` render page shells.
2. Pages compose domain components from `web/components`.
3. Components call API helpers from `web/lib/api/*`.
4. `web/lib/api/http.ts` provides the shared Axios client.
5. The client talks to FastAPI with `withCredentials: true` and attaches the in-memory access token when present.

## Authentication Model

The auth model in `web/lib/auth/secure-storage.ts` and `web/lib/store/authStore.ts` is worth calling out because it changed from a simpler local-storage model:

- access token is kept in memory
- refresh token lives in an HttpOnly cookie managed by the backend
- the Axios client retries `401` responses after a refresh attempt
- Zustand stores the authenticated user state and loading state

That design keeps long-lived tokens out of browser storage while still supporting SPA navigation.

## UI and Content Capabilities

The frontend is also responsible for several rich-content surfaces:

- markdown rendering with `react-markdown` and `remark-gfm`
- Mermaid diagram rendering in chat and document viewers
- rich text editing with Tiptap
- charts and analytics with Chart.js, Recharts, and Plotly
- motion and animation with `motion` and `gsap`

## Current Frontend Stack

| Area | Current Stack |
| --- | --- |
| Framework | Next `16.2.6` with App Router |
| UI runtime | React `19` |
| Styling | Tailwind CSS `3.4.14`, `tailwind-merge`, `clsx` |
| State | Zustand |
| Server data | `@tanstack/react-query`, SWR |
| HTTP | Axios |
| Forms and validation | React Hook Form, Zod |
| Monitoring | `@sentry/nextjs` |
| Content | `react-markdown`, `remark-gfm`, Mermaid, Tiptap |
| Testing | Vitest, Testing Library, ESLint, TypeScript |

## Why This Structure Matters

Because the dashboard, docs, blog, public pages, and embedded-product surfaces all live in one Next.js app, changes to the product architecture can be reflected in one frontend codebase instead of being copied across separate sites.
