# SentraAura — Frontend Documentation

## Overview

The SentraAura frontend is a thin Carbon Slate control plane. It never performs AI reasoning, rendering, clipping, or scoring client-side. All heavy computation happens on the backend.

## Architecture Principles

1. **Thin Client**: The frontend is a presentation layer only
2. **Server-Side Intelligence**: All AI operations run in backend services
3. **Real-Time Updates**: WebSocket/SSE for live status updates
4. **Tenant Isolation**: UI components respect tenant boundaries
5. **Accessibility**: WCAG 2.1 AA compliance

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | React | 18+ |
| Language | TypeScript | 5.3+ |
| Styling | Tailwind CSS | 3.4+ |
| State Management | Zustand | 4.5+ |
| Data Fetching | TanStack Query | 5.0+ |
| Routing | React Router | 6.2+ |
| Charts | Recharts | 2.1+ |
| UI Components | Radix UI + shadcn/ui | latest |
| Build Tool | Vite | 5.0+ |

## Project Structure

```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── ui/              # shadcn/ui primitives
│   │   ├── layout/          # Layout components
│   │   └── features/        # Feature-specific components
│   ├── pages/               # Route pages
│   ├── hooks/               # Custom React hooks
│   ├── stores/              # Zustand state stores
│   ├── api/                 # API client & queries
│   ├── types/               # TypeScript types
│   ├── utils/               # Utility functions
│   └── styles/              # Global styles
├── public/                  # Static assets
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

## API Integration

### REST Client
```typescript
// api/client.ts
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

### GraphQL Client
```typescript
// api/graphql.ts
import { GraphQLClient } from 'graphql-request';

export const graphqlClient = new GraphQLClient(
  import.meta.env.VITE_GRAPHQL_URL,
  {
    headers: () => ({
      Authorization: `Bearer ${useAuthStore.getState().token}`,
    }),
  }
);
```

### TanStack Query Hooks
```typescript
// hooks/useChannels.ts
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';

export function useChannels() {
  return useQuery({
    queryKey: ['channels'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/v1/channels');
      return data;
    },
  });
}
```

## State Management

### Zustand Stores
```typescript
// stores/authStore.ts
import { create } from 'zustand';

interface AuthState {
  token: string | null;
  user: User | null;
  tenant: Tenant | null;
  setToken: (token: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  tenant: null,
  setToken: (token) => set({ token }),
  setUser: (user) => set({ user }),
  logout: () => set({ token: null, user: null, tenant: null }),
}));
```

## Real-Time Updates

### WebSocket Connection
```typescript
// hooks/useWebSocket.ts
import { useEffect, useRef } from 'react';

export function useWebSocket(url: string, onMessage: (data: any) => void) {
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    ws.current = new WebSocket(url);
    ws.current.onmessage = (event) => {
      onMessage(JSON.parse(event.data));
    };
    return () => ws.current?.close();
  }, [url, onMessage]);

  return ws.current;
}
```

## Key Pages

### Configure
- Channel management
- Topic/Theme configuration
- Agent settings
- Integration setup

### Observe
- Real-time dashboard
- Agent status monitoring
- Pipeline progress tracking
- System health overview

### Inspect
- Content asset browser
- Asset detail view
- Version history
- Audit trail

### Override
- Human-in-the-loop approvals
- Emergency stop controls
- Manual agent intervention
- Rollback operations

### Analyze
- Performance metrics
- Cost attribution
- Quality scores
- Trend analysis

## Security

### XSS Prevention
- React's built-in escaping
- DOMPurify for HTML content
- CSP headers

### CSRF Protection
- SameSite cookies
- CSRF tokens for state-changing requests

### Input Validation
- Zod schemas for form validation
- Server-side validation for all inputs

## Performance

### Code Splitting
- Route-based lazy loading
- Component-level code splitting

### Caching
- TanStack Query caching
- Service Worker for offline support

### Optimization
- Image optimization
- Font subsetting
- Tree shaking

## Accessibility

- Semantic HTML
- ARIA labels
- Keyboard navigation
- Focus management
- Screen reader testing

## Build & Deploy

```bash
# Development
npm run dev

# Build
npm run build

# Preview production build
npm run preview

# Type check
npm run typecheck

# Lint
npm run lint

# Test
npm run test
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `VITE_API_URL` | REST API base URL | Yes |
| `VITE_GRAPHQL_URL` | GraphQL endpoint | Yes |
| `VITE_WS_URL` | WebSocket URL | Yes |
| `VITE_SENTRY_DSN` | Error tracking | No |
| `VITE_ENVIRONMENT` | Environment name | Yes |
