# Synkora Frontend - Quick Start Guide

## Prerequisites

- Node.js 18+ installed
- pnpm installed (`npm install -g pnpm`)
- Backend API running at http://localhost:5001

## Installation & Setup

### 1. Install Dependencies

```bash
cd synkora-rebuild/web
pnpm install
```

This will install all required packages:
- Next.js 15.1.0
- React 19.0.0
- TypeScript 5.6.0
- Tailwind CSS 3.4.0
- Zustand 4.5.0
- Axios 1.7.0
- React Hook Form 7.53.0
- And more...

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env.local

# Edit .env.local if needed
# NEXT_PUBLIC_API_URL=http://localhost:5001
```

### 3. Start Development Server

```bash
pnpm dev
```

The application will start at **http://localhost:3000**

## Available Scripts

```bash
# Development server with hot reload
pnpm dev

# Build for production
pnpm build

# Start production server
pnpm start

# Run linter
pnpm lint

# Type checking
pnpm type-check
```

## Project Structure

```
web/
├── app/                    # Next.js 15 App Router
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Landing page
│   ├── (auth)/            # Auth pages (to be implemented)
│   ├── (dashboard)/       # Dashboard pages (to be implemented)
│   └── chat/              # Chat interface (to be implemented)
├── components/            # React components
│   ├── ui/                # Base UI components
│   ├── layout/            # Layout components (to be implemented)
│   ├── chat/              # Chat components (to be implemented)
│   ├── app/               # App components (to be implemented)
│   └── dataset/           # Dataset components (to be implemented)
├── lib/                   # Core utilities
│   ├── api/               # API client ✅
│   ├── hooks/             # Custom hooks ✅
│   ├── store/             # State management ✅
│   ├── types/             # TypeScript types ✅
│   └── utils/             # Utility functions ✅
├── styles/                # Global styles ✅
└── public/                # Static assets
```

## What's Currently Working

### ✅ Implemented (15 files)
1. **Configuration** - All config files ready
2. **Landing Page** - Welcome page at `/`
3. **API Client** - Complete REST API integration
4. **Auth Store** - Zustand state management
5. **Type Definitions** - Full TypeScript support
6. **Styling** - Tailwind CSS configured
7. **Button Component** - Reusable UI component

### 📋 To Be Implemented (23 files)
- Auth pages (signin, signup)
- Dashboard layout
- Apps management
- Chat interface
- Dataset management
- Settings page

## Current Features

### API Integration ✅
The API client (`lib/api/client.ts`) provides:
- Authentication (login, signup, logout)
- Apps CRUD operations
- Conversations management
- Messages handling
- Datasets operations
- File uploads

### State Management ✅
Zustand store (`lib/store/authStore.ts`) handles:
- User authentication state
- JWT token management
- Auto-fetch user on mount
- Sign in/out operations

### Type Safety ✅
Complete TypeScript interfaces for:
- User
- App
- Conversation
- Message
- Dataset
- Document

## Testing the Current Implementation

### 1. View Landing Page
```bash
pnpm dev
# Open http://localhost:3000
```

You should see the welcome page with "Get Started" and "Sign Up" buttons.

### 2. Test API Client (in browser console)
```javascript
import { apiClient } from '@/lib/api/client'

// Test API connection
apiClient.getCurrentUser()
  .then(user => console.log('User:', user))
  .catch(err => console.log('Not authenticated'))
```

### 3. Test Auth Store
```javascript
import { useAuthStore } from '@/lib/store/authStore'

// Get auth state
const { user, isAuthenticated } = useAuthStore.getState()
console.log('Auth state:', { user, isAuthenticated })
```

## Next Steps to Complete Frontend

### Phase 1: UI Components (3 files)
```bash
# Create these files:
components/ui/Input.tsx
components/ui/Card.tsx
components/ui/Modal.tsx
```

### Phase 2: Auth Pages (3 files)
```bash
# Create these files:
app/(auth)/layout.tsx
app/(auth)/signin/page.tsx
app/(auth)/signup/page.tsx
```

### Phase 3: Dashboard (3 files)
```bash
# Create these files:
app/(dashboard)/layout.tsx
components/layout/Sidebar.tsx
components/layout/Header.tsx
```

### Phase 4: Apps Management (3 files)
```bash
# Create these files:
app/(dashboard)/apps/page.tsx
app/(dashboard)/apps/[id]/page.tsx
components/app/AppCard.tsx
```

### Phase 5: Chat Interface (4 files)
```bash
# Create these files:
app/chat/[appId]/page.tsx
components/chat/ChatInterface.tsx
components/chat/MessageList.tsx
components/chat/InputBox.tsx
```

### Phase 6: Datasets (3 files)
```bash
# Create these files:
app/(dashboard)/datasets/page.tsx
app/(dashboard)/datasets/[id]/page.tsx
components/dataset/DatasetCard.tsx
```

## Troubleshooting

### TypeScript Errors
If you see TypeScript errors, they should resolve after running:
```bash
pnpm install
```

### Port Already in Use
If port 3000 is busy:
```bash
# Use a different port
PORT=3001 pnpm dev
```

### API Connection Issues
Ensure the backend is running:
```bash
cd ../
docker compose ps
# API should be running on port 5001
```

### Clear Cache
If you encounter build issues:
```bash
rm -rf .next
rm -rf node_modules
pnpm install
pnpm dev
```

## Environment Variables

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:5001
NEXT_PUBLIC_APP_NAME=Synkora
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Development Tips

1. **Hot Reload**: Changes to files automatically reload the page
2. **TypeScript**: Use `pnpm type-check` to verify types
3. **Linting**: Run `pnpm lint` before committing
4. **API Testing**: Use browser DevTools Network tab to debug API calls
5. **State Debugging**: Install Redux DevTools for Zustand debugging

## Production Build

```bash
# Build for production
pnpm build

# Test production build locally
pnpm start

# The app will run at http://localhost:3000
```

## Docker Deployment (Future)

```dockerfile
# Dockerfile for frontend (to be created)
FROM node:18-alpine
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install
COPY . .
RUN pnpm build
CMD ["pnpm", "start"]
```

## Support

For issues or questions:
1. Check PHASE_8_FRONTEND_STATUS.md for implementation details
2. Review FULLSTACK_IMPLEMENTATION_COMPLETE.md for architecture
3. See FRONTEND_TODO.md for remaining tasks

## Quick Reference

**Start Frontend**: `cd synkora-rebuild/web && pnpm install && pnpm dev`
**Access App**: http://localhost:3000
**API Endpoint**: http://localhost:5001
**Docs**: See markdown files in synkora-rebuild/

## Translating the dashboard

The signed-in dashboard and the sign-in pages are translated with
[next-intl](https://next-intl.dev). English and German are available. There is no
language in the URL: the choice is kept in the `NEXT_LOCALE` cookie, saved on the
account (`interface_language`) when signed in, and starts from the browser's
language. Public marketing pages are not translated and stay statically rendered.

- Text lives in `messages/en.json` and `messages/de.json`, grouped by screen
  (`auth.signin`, `agents.list`, ...). Use it in a component with
  `const t = useTranslations('agents.list')` and `t('key')`. For links or bold
  text inside a sentence use `t.rich`; for counts use ICU plurals
  (`{count, plural, one {# agent} other {# agents}}`).
- Dates and numbers: format with the current `useLocale()`, not a fixed locale.
- Keep every language file in step. `i18n/i18n.test.ts` fails if a key or a
  `{variable}` / `<tag>` is missing in one language, or if a component uses a key
  that does not exist.
- To add a language: add its code to `i18n/config.ts` and `SUPPORTED_LANGUAGES` in
  `api/src/services/i18n/languages.py`, then add `messages/<code>.json`.
- Screens not converted yet still show English; convert one at a time.
- Messages that come from the API (validation and error text) are still English.
