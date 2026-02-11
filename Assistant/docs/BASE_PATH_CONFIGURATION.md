# Configurable Base Path - Application Deployment Guide

**Document Version:** 1.0
**Last Updated:** November 14, 2024
**Status:** Implemented

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Configuration](#configuration)
4. [Environment-Specific Behavior](#environment-specific-behavior)
5. [Code Implementation](#code-implementation)
6. [Deployment Scenarios](#deployment-scenarios)
7. [Migration Guide](#migration-guide)
8. [Troubleshooting](#troubleshooting)
9. [API Reference](#api-reference)

---

## Overview

### Problem Statement

The application needed to support multiple deployment scenarios:
- **Local Development**: Running on `http://localhost:3000` without any URL prefix
- **Production (IIS)**: Deployed as a sub-application under `/chat` (e.g., `https://example.com/chat`)
- **Custom Deployments**: Flexible configuration for different reverse proxy or sub-path requirements

Previously, the `/chat` prefix was hardcoded throughout the codebase, making local development require the `/chat` prefix and preventing flexible deployments.

### Solution

Implemented a configurable base path system using:
- Environment variables (`NEXT_PUBLIC_BASE_PATH`)
- Centralized utility function (`getAssetPath()`)
- Environment-specific configuration files (`.env.development`, `.env.production`)
- Backend remains path-agnostic (IIS/reverse proxy handles routing)

### Benefits

- **Zero-config local development**: Developers run on `localhost:3000` without URL prefixes
- **Production-ready defaults**: Automatically includes `/chat` prefix for IIS deployments
- **Flexible deployments**: Easy to customize for different hosting scenarios
- **Single source of truth**: All path resolution goes through `getAssetPath()` utility
- **No backend changes**: Backend serves at root paths; routing handled by infrastructure

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Environment Configuration                 │
│  .env.development  │  .env.production  │  .env.local        │
│  BASE_PATH=""      │  BASE_PATH="/chat"│  (overrides)       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Next.js Configuration                      │
│              next.config.ts reads BASE_PATH                  │
│         Sets basePath & assetPrefix dynamically              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Application Code                           │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  getAssetPath() Utility (lib/assetPath.ts)           │  │
│  │  - Reads NEXT_PUBLIC_BASE_PATH from environment      │  │
│  │  - Prefixes all paths consistently                   │  │
│  │  - Validates input and provides warnings             │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     │                                        │
│  ┌──────────────────┴───────────────────────────────────┐  │
│  │  Used By:                                            │  │
│  │  - Static assets (images, icons, etc.)              │  │
│  │  - API routes (CopilotKit runtime)                  │  │
│  │  - Backend endpoints (API, Data)                    │  │
│  │  - Data fetching endpoints                          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Three-Tier Architecture

The application now uses a **three-tier architecture** with independent services:

```
┌────────────────────────────────────────────────────────────┐
│                    STATIC FRONTEND                         │
│                  (Next.js Static Export)                   │
│  Deployed to: S3, CDN, IIS Static, nginx, etc.            │
│                                                            │
│  • Reads NEXT_PUBLIC_COPILOT_API for runtime URL          │
│  • Reads NEXT_PUBLIC_BACKEND_PREFIX for backend routing   │
│  • Pure static files (HTML, CSS, JS, images)              │
└────────┬───────────────────────────────────┬─────────────┘
         │                                   │
         │ HTTP (Chat)                       │ HTTP (Data)
         ▼                                   ▼
┌─────────────────────────┐   ┌────────────────────────────┐
│  COPILOTKIT SERVER      │   │   PYTHON BACKEND           │
│  (Node.js - Port 8001)  │   │  (Starlette - Port 8002)   │
│                         │   │                            │
│  • Protocol Translation │   │  • Pydantic AI Agents      │
│  • CopilotKit ↔ AG-UI  │───┤  • /data endpoint          │
│  • CORS handling        │   │  • /api (AG-UI)            │
│  • Proxies to /api      │   │                            │
└─────────────────────────┘   └────────────────────────────┘
```

### Request Flow

#### Development Mode (localhost)

**CopilotKit Chat Requests**:
```
Browser: http://localhost:3000
                ↓
Frontend calls: http://localhost:8001/copilotkit
                ↓
CopilotKit Server (port 8001)
                ↓
Proxies to: http://localhost:8002/api
                ↓
Python Backend (AG-UI)
```

**Direct Backend Requests** (Data):
```
Browser: http://localhost:3000
                ↓
Frontend calls: http://localhost:8002/data
                ↓
Python Backend directly
```

#### Production Mode (IIS/Reverse Proxy)

**CopilotKit Chat Requests**:
```
Browser: https://example.com/chat
                ↓
Frontend (static): https://example.com/copilot-api/copilotkit
                ↓
Reverse Proxy routes to: http://copilotkit-server:8001/copilotkit
                ↓
CopilotKit Server proxies to: http://python-backend:8002/api
                ↓
Python Backend (AG-UI)
```

**Direct Backend Requests** (Data):
```
Browser: https://example.com/chat
                ↓
Frontend calls: /chat/backend/data
                ↓
IIS routes to: http://python-backend:8002/data
                ↓
Python Backend directly
```

---

## Configuration

### Environment Files

The application uses three environment files in the `frontend/` directory:

#### 1. `.env.development` (Development Default)

```bash
# Development environment configuration
# Used when running: pnpm run dev
NODE_ENV=development

# Base path for application (empty for localhost development)
NEXT_PUBLIC_BASE_PATH=

# Backend API prefix (empty in dev - Python backend serves at root)
# In production, IIS uses /backend prefix for routing to Python backend
NEXT_PUBLIC_BACKEND_PREFIX=

# Base URL for frontend API routes
NEXT_PUBLIC_API_BASE=http://localhost:3000

# Python backend API URL
NEXT_PUBLIC_BACKEND_API=http://127.0.0.1:8002

# Python backend port (used by Next.js API proxy)
SERVER_PORT=8002
```

**Purpose**: Zero-config local development without URL prefixes

**Key Points**:
- `BACKEND_PREFIX=""` - No prefix needed; Python backend called directly at `/api`, `/data`
- Frontend calls: `http://localhost:8002/api` (not `/backend/api`)

#### 2. `.env.production` (Production Default)

```bash
# Production environment configuration
# Used when running: pnpm run build && pnpm start
NODE_ENV=production

# Base path for application (default /chat for IIS deployment)
# Override this value for different deployment paths
NEXT_PUBLIC_BASE_PATH=/chat

# Backend API prefix (IIS routing convention to route to Python backend)
# IIS strips this prefix before forwarding to backend at port 8002
NEXT_PUBLIC_BACKEND_PREFIX=/backend

# Base URL for frontend API routes (relative in production)
NEXT_PUBLIC_API_BASE=

# Python backend API URL (handled by IIS reverse proxy in production)
NEXT_PUBLIC_BACKEND_API=

# Python backend port (used by Next.js API proxy)
SERVER_PORT=8002
```

**Purpose**: Production deployments with `/chat` prefix (IIS default)

**Key Points**:
- `BACKEND_PREFIX="/backend"` - IIS routing prefix (stripped by IIS before forwarding)
- Frontend calls: `/chat/backend/api` → IIS rewrites → `http://127.0.0.1:8002/api`
- Python backend receives: `/api` (not `/backend/api`)

#### 3. `.env.local` (Local Overrides)

```bash
# .env.local - Local development overrides
# This file is for local development overrides only and should not be committed to git
# The default configuration is in .env.development and .env.production

# Uncomment and modify any values below to override defaults for your local environment

# Override base path (defaults to "" for dev, "/chat" for production)
# NEXT_PUBLIC_BASE_PATH=/custom-path

# Override backend port if running on different port
# SERVER_PORT=8001

# Override API URLs if needed
# NEXT_PUBLIC_API_BASE=http://localhost:3000
# NEXT_PUBLIC_BACKEND_API=http://127.0.0.1:8002
```

**Purpose**: Developer-specific overrides (not committed to git)

### Next.js Configuration

**File**: `frontend/next.config.ts`

```typescript
// Use NEXT_PUBLIC_BASE_PATH from environment, default to empty string for development
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

const nextConfig = {
  basePath: basePath,
  assetPrefix: basePath,
  trailingSlash: true, // Prevent canonical redirects
};

module.exports = nextConfig;
```

**Key Points**:
- Reads `NEXT_PUBLIC_BASE_PATH` from environment
- Defaults to empty string if not set
- Applies to both `basePath` (routing) and `assetPrefix` (static assets)

### Backend Configuration

**File**: `config.toml`

```toml
[server]
PORT = 8002

# BASE_PATH: Application base path for IIS/reverse proxy deployments
#   - Frontend uses NEXT_PUBLIC_BASE_PATH environment variable for this setting
#   - Development: "" (empty, runs on http://localhost:3000)
#   - Production: "/chat" (default, runs on https://example.com/chat)
#   - Backend remains agnostic - IIS/reverse proxy handles routing
# Configuration files:
#   - frontend/.env.development (BASE_PATH="")
#   - frontend/.env.production (BASE_PATH="/chat")
#   - frontend/.env.local (local overrides)
```

**Note**: Backend code remains unchanged and path-agnostic. The configuration is documented here for reference only.

---

## Environment-Specific Behavior

### Development Environment

**Trigger**: `pnpm run dev` in `frontend/`

**Configuration**:
- Loads: `.env.development` + `.env.local` (if exists)
- `NEXT_PUBLIC_BASE_PATH=""`
- `NODE_ENV=development`

**Behavior**:
- Frontend runs on: `http://localhost:3000`
- Backend runs on: `http://localhost:8002`
- No URL prefix required
- Direct API calls to backend: `http://localhost:8002/api`, `http://localhost:8002/data`

**Example URLs**:
```
App:        http://localhost:3000/
CopilotKit: http://localhost:3000/api/copilotkit/
Data:       http://localhost:8002/data
Assets:     http://localhost:3000/logo-dark-text.svg
```

### Production Environment

**Trigger**: `pnpm run build && pnpm start` in `frontend/`

**Configuration**:
- Loads: `.env.production` + `.env.local` (if exists)
- `NEXT_PUBLIC_BASE_PATH="/chat"`
- `NODE_ENV=production`

**Behavior**:
- Frontend served via IIS on: `https://example.com/chat`
- Backend served via IIS reverse proxy
- All URLs prefixed with `/chat`
- Same-origin API calls (handled by IIS routing)

**Example URLs**:
```
App:        https://example.com/chat/
CopilotKit: https://example.com/chat/api/copilotkit/
Data:       https://example.com/chat/data
Assets:     https://example.com/chat/logo-dark-text.svg
```

**IIS Routing** (from `iis/web.config`):
- `/chat/backend/*` → `http://127.0.0.1:8002/*` (Python backend)
- `/chat/api/*` → `http://127.0.0.1:3000/chat/api/*` (Next.js API)
- `/chat/_next/*` → `http://127.0.0.1:3000/chat/_next/*` (Next.js static)
- `/chat/data` → `http://127.0.0.1:8002/data` (Data endpoint)

### Custom Deployment

**Example**: Deploy under `/custom-app` prefix

**Configuration**:
1. Create `.env.custom` or modify `.env.production`:
   ```bash
   NEXT_PUBLIC_BASE_PATH=/custom-app
   ```

2. Build with custom environment:
   ```bash
   cp .env.custom .env.production
   npm run build
   ```

3. Update IIS/reverse proxy to route `/custom-app/*` appropriately

---

## Code Implementation

### Core Utility: `getAssetPath()`

**File**: `frontend/lib/assetPath.ts`

```typescript
/**
 * Builds a path with the appropriate base path prefix for the current environment.
 * Used to support both IIS deployments (with /chat prefix) and standalone deployments.
 *
 * @param path - The path to prefix (must start with "/")
 * @returns The full path with base path prefix if configured
 *
 * @example
 * // Development (NEXT_PUBLIC_BASE_PATH="")
 * getAssetPath("/logo.svg") // Returns: "/logo.svg"
 * getAssetPath("/api/copilotkit/") // Returns: "/api/copilotkit/"
 *
 * @example
 * // Production (NEXT_PUBLIC_BASE_PATH="/chat")
 * getAssetPath("/logo.svg") // Returns: "/chat/logo.svg"
 * getAssetPath("/api/copilotkit/") // Returns: "/chat/api/copilotkit/"
 */
export function getAssetPath(path: string): string {
  // Validate that path starts with "/"
  if (!path.startsWith('/')) {
    console.warn(`[getAssetPath] Path should start with "/": ${path}`);
    path = `/${path}`;
  }

  const basePath = getBasePath();
  return `${basePath}${path}`;
}

/**
 * Gets the configured base path for the application.
 * Returns an empty string in development, and the configured prefix (e.g., "/chat") in production.
 *
 * @returns The base path prefix (e.g., "" or "/chat")
 */
export function getBasePath(): string {
  return process.env.NEXT_PUBLIC_BASE_PATH || '';
}
```

### Usage Examples

#### 1. Static Assets (`app/page.tsx`)

```typescript
import { getAssetPath } from "@/lib/assetPath";

<Image
  src={getAssetPath("/logo-dark-text.svg")}
  alt="Logo"
/>
```

#### 2. CopilotKit Runtime (`app/page.tsx`)

```typescript
import { getAssetPath } from "@/lib/assetPath";

<CopilotKit
  runtimeUrl={getAssetPath("/api/copilotkit/")}
  agent="dr_migrate_agent"
  showDevConsole={false}
>
  {/* ... */}
</CopilotKit>
```

#### 3. Backend API Calls (`components/PersonaContext.tsx`)

```typescript
import { getAssetPath } from "@/lib/assetPath";

const serverPort = process.env.SERVER_PORT || '8002';
const baseUrl = process.env.NODE_ENV === 'development'
  ? `http://localhost:${serverPort}`
  : '';

// Fetch data
const response = await fetch(`${baseUrl}${getAssetPath('/data')}`, {
  method: 'GET',
  headers: { 'Content-Type': 'application/json' }
});
```

#### 4. Data Fetching (`components/DataTableRender.tsx`)

```typescript
import { getAssetPath } from '@/lib/assetPath';

const dataUrl = getAssetPath('/data');
const response = await fetch(
  `${dataUrl}?table_name=${encodeURIComponent(tableName)}&${params}`
);
```

---

## Deployment Scenarios

### Scenario 1: Local Development

**Setup**:
```bash
cd frontend
pnpm install
pnpm run dev
```

**Configuration**: Uses `.env.development` (BASE_PATH="")

**Access**:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8002` (run separately)

**No URL prefix required** - Clean URLs for development

---

### Scenario 2: IIS Production Deployment (Default)

**Setup**:
```bash
cd frontend
pnpm install
pnpm run build
pnpm start
```

**Configuration**: Uses `.env.production` (BASE_PATH="/chat")

**IIS Setup**:
1. Create IIS Application Pool for Node.js
2. Create IIS Sub-Application at `/chat`
3. Copy `iis/web.config` to application root
4. Configure reverse proxy rules (already in web.config)

**Access**: `https://yourdomain.com/chat`

**IIS automatically routes**:
- `/chat/*` → Frontend (Next.js on port 3000)
- `/chat/backend/*` → Backend (Python on port 8002)

---

### Scenario 3: Docker Deployment with Custom Path

**Setup**:

Create `.env.docker`:
```bash
NEXT_PUBLIC_BASE_PATH=/myapp
SERVER_PORT=8002
```

Update `Dockerfile`:
```dockerfile
FROM node:20-alpine
WORKDIR /app
# Enable corepack for pnpm
RUN corepack enable pnpm
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
COPY .env.docker ./.env.production
RUN pnpm run build
EXPOSE 3000
CMD ["pnpm", "start"]
```

Build and run:
```bash
docker build -t my-chat-app .
docker run -p 3000:3000 -p 8000:8002 my-chat-app
```

**Nginx reverse proxy** configuration:
```nginx
location /myapp/ {
    proxy_pass http://localhost:3000/myapp/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /myapp/backend/ {
    proxy_pass http://localhost:8002/;
    proxy_set_header Host $host;
}
```

**Access**: `http://yourdomain.com/myapp`

---

### Scenario 4: Standalone Deployment (No Prefix)

**Setup**:

Create `.env.standalone`:
```bash
NEXT_PUBLIC_BASE_PATH=
SERVER_PORT=8002
```

Build:
```bash
cp .env.standalone frontend/.env.production
cd frontend
pnpm run build
```

**Access**: `http://yourdomain.com/` (root path)

**Ideal for**: Dedicated subdomain deployments (e.g., `chat.example.com`)

---

## Migration Guide

### From Hardcoded `/chat` to Configurable Path

If you have an existing deployment with hardcoded `/chat` references:

#### Step 1: Update Environment Files

1. Create `frontend/.env.production`:
   ```bash
   NEXT_PUBLIC_BASE_PATH=/chat
   ```

2. Create `frontend/.env.development`:
   ```bash
   NEXT_PUBLIC_BASE_PATH=
   ```

#### Step 2: Update Code References

Replace all hardcoded `/chat` references with `getAssetPath()`:

**Before**:
```typescript
<img src="/chat/logo.svg" />
runtimeUrl="/chat/api/copilotkit/"
fetch("/chat/backend/api")
```

**After**:
```typescript
import { getAssetPath } from "@/lib/assetPath";

<img src={getAssetPath("/logo.svg")} />
runtimeUrl={getAssetPath("/api/copilotkit/")}
fetch(getBackendPath("/api"))
```

#### Step 3: Update Next.js Config

**Before** (`next.config.ts`):
```typescript
const nextConfig = {
  basePath: '/chat',
  assetPrefix: '/chat',
};
```

**After**:
```typescript
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

const nextConfig = {
  basePath: basePath,
  assetPrefix: basePath,
};
```

#### Step 4: Test

```bash
# Test development (no prefix)
pnpm run dev
# Visit: http://localhost:3000

# Test production (with /chat prefix)
pnpm run build
pnpm start
# Visit: http://localhost:3000/chat
```

#### Step 5: Deploy

No IIS configuration changes needed - existing `web.config` works as-is!

---

## Troubleshooting

### Issue: 404 Errors on All Routes in Production

**Symptoms**: All pages return 404 after deployment

**Cause**: Base path mismatch between build and runtime

**Solution**:
1. Check `.env.production` has correct `NEXT_PUBLIC_BASE_PATH`
2. Rebuild: `pnpm run build`
3. Verify Next.js config reads environment variable
4. Check IIS application is configured at matching path

**Verify**:
```bash
cat frontend/.env.production | grep BASE_PATH
# Should match IIS sub-application path
```

---

### Issue: Assets Load But API Calls Fail

**Symptoms**: Page loads but API calls return 404

**Cause**: API calls not using `getAssetPath()`

**Solution**:
1. Search for hardcoded paths: `grep -r '"/chat/' frontend/`
2. Replace with `getAssetPath()`:
   ```typescript
   import { getAssetPath } from "@/lib/assetPath";
   fetch(getAssetPath('/api/endpoint'))
   ```

---

### Issue: Development Mode Requires /chat Prefix

**Symptoms**: `http://localhost:3000` doesn't work, but `http://localhost:3000/chat` does

**Cause**: `.env.development` has `NEXT_PUBLIC_BASE_PATH="/chat"`

**Solution**:
```bash
# Update frontend/.env.development
NEXT_PUBLIC_BASE_PATH=

# Restart dev server
pnpm run dev
```

---

### Issue: Custom Base Path Not Working

**Symptoms**: Custom path like `/myapp` doesn't work

**Checklist**:
1. Environment variable set: `NEXT_PUBLIC_BASE_PATH=/myapp` in `.env.production`
2. Rebuild after changing env: `pnpm run build`
3. IIS/Nginx configured to route `/myapp/*` correctly
4. No trailing slash in base path: Use `/myapp` not `/myapp/`

**Debug**:
```bash
# Check what Next.js sees
pnpm run build | grep "basePath"

# Should show: basePath: '/myapp'
```

---

### Issue: Environment Variables Not Updating

**Symptoms**: Changes to `.env` files don't take effect

**Cause**: Next.js caches environment variables at build time

**Solution**:
```bash
# Delete build cache
rm -rf frontend/.next

# Rebuild
pnpm run build

# Restart server
pnpm start
```

**Note**: `NEXT_PUBLIC_*` variables are embedded at build time, not runtime!

---

## API Reference

### `getAssetPath(path: string): string`

Builds a path with the appropriate base path prefix.

**Parameters**:
- `path` (string): The path to prefix (must start with "/")

**Returns**:
- (string): The full path with base path prefix if configured

**Examples**:
```typescript
// Development (BASE_PATH="")
getAssetPath("/api/data")        // → "/api/data"
getAssetPath("/logo.svg")        // → "/logo.svg"

// Production (BASE_PATH="/chat")
getAssetPath("/api/data")        // → "/chat/api/data"
getAssetPath("/logo.svg")        // → "/chat/logo.svg"
```

**Validation**:
- Warns if path doesn't start with "/"
- Automatically prepends "/" if missing

---

### `getBasePath(): string`

Gets the configured base path for the application.

**Parameters**: None

**Returns**:
- (string): The base path prefix (e.g., "" or "/chat")

**Examples**:
```typescript
const basePath = getBasePath();
console.log(basePath); // "" in dev, "/chat" in production
```

---

### `getBackendPrefix(): string`

Gets the configured backend API prefix for IIS routing.

**Parameters**: None

**Returns**:
- (string): The backend prefix (e.g., "" or "/backend")

**Examples**:
```typescript
const backendPrefix = getBackendPrefix();
console.log(backendPrefix); // "" in dev, "/backend" in production
```

**Important**:
- In development: Returns `""` (empty) - backend called directly
- In production: Returns `"/backend"` - IIS routing prefix (stripped by IIS)

---

### `getBackendPath(path: string): string`

Builds a path for Python backend API calls with appropriate prefixes.
Combines backend prefix + base path + route for proper routing in all environments.

**Parameters**:
- `path` (string): The backend API path (must start with "/")

**Returns**:
- (string): The full path with backend prefix and base path

**Examples**:
```typescript
// Development (BACKEND_PREFIX="", BASE_PATH="")
getBackendPath("/api")  // → "/api"
getBackendPath("/data") // → "/data"

// Production (BACKEND_PREFIX="/backend", BASE_PATH="/chat")
getBackendPath("/api")  // → "/chat/backend/api"
getBackendPath("/data") // → "/chat/backend/data"
```

**Usage**:
```typescript
import { getBackendPath } from "@/lib/assetPath";

// In development
const baseUrl = "http://localhost:8002";
fetch(`${baseUrl}${getBackendPath('/api')}`)
// → "http://localhost:8002/api"

// In production (IIS routing)
const baseUrl = "";
fetch(`${baseUrl}${getBackendPath('/data')}`)
// → "/chat/backend/data" → IIS → http://127.0.0.1:8002/data
```

**Important**:
- Use for Python backend endpoints: `/api`, `/data`
- Automatically handles both backend prefix and base path

**Validation**:
- Warns if path doesn't start with "/"
- Automatically prepends "/" if missing

---

### Environment Variables

#### `NEXT_PUBLIC_BASE_PATH`

**Type**: `string`
**Default**: `""` (empty string)
**Required**: No

The base path prefix for all application URLs.

**Valid Values**:
- `""` - No prefix (root deployment)
- `"/chat"` - IIS sub-application at /chat
- `"/any-path"` - Custom deployment path

**Usage**:
```bash
# .env.development
NEXT_PUBLIC_BASE_PATH=

# .env.production
NEXT_PUBLIC_BASE_PATH=/chat

# .env.local (override)
NEXT_PUBLIC_BASE_PATH=/custom
```

**Important**:
- Must start with "/" if not empty
- No trailing slash
- Embedded at build time (requires rebuild to change)
- Available in both client and server code

---

#### `NEXT_PUBLIC_BACKEND_PREFIX`

**Type**: `string`
**Default**: `""` (empty string)
**Required**: No

The backend API routing prefix used by IIS to route requests to the Python backend.
This prefix is stripped by IIS before forwarding to the backend server.

**Valid Values**:
- `""` - No prefix (development - direct backend access)
- `"/backend"` - IIS routing prefix (production - default)
- `"/api-backend"` - Custom IIS routing prefix

**Usage**:
```bash
# .env.development
NEXT_PUBLIC_BACKEND_PREFIX=

# .env.production
NEXT_PUBLIC_BACKEND_PREFIX=/backend

# .env.local (override)
NEXT_PUBLIC_BACKEND_PREFIX=/custom-backend
```

**Important**:
- Development: Empty - Python backend accessed directly at `localhost:8002/api`
- Production: `/backend` - IIS routes `/chat/backend/api` → `8002/api`
- Python backend always receives routes at root level (never `/backend/*`)
- Must start with "/" if not empty
- No trailing slash
- Embedded at build time (requires rebuild to change)
- Different from `BASE_PATH` - this is specifically for IIS backend routing

**IIS Routing Flow**:
```
Frontend: /chat/backend/api
         ↓
IIS matches: ^backend/api$
         ↓
IIS rewrites: http://127.0.0.1:8002/api
         ↓
Python backend receives: /api
```

---

## Best Practices

### 1. Use the Correct Path Helper Function

**For Python Backend API Calls** - Use `getBackendPath()`:
```typescript
import { getBackendPath } from "@/lib/assetPath";

// Backend API endpoints
fetch(`${baseUrl}${getBackendPath('/api')}`)
fetch(`${baseUrl}${getBackendPath('/data')}`)
```

**For Next.js API Routes, Assets, and Frontend Routes** - Use `getAssetPath()`:
```typescript
import { getAssetPath } from "@/lib/assetPath";

// Next.js API routes
<CopilotKit runtimeUrl={getAssetPath("/api/copilotkit/")} />

// Static assets
<img src={getAssetPath("/logo.svg")} />

// Data endpoint (has its own IIS rule, not under /backend)
fetch(getAssetPath("/data"))
```

**Bad** - Hardcoded paths:
```typescript
<img src="/chat/logo.svg" />           // Hardcoded - breaks in dev
fetch("/backend/api")              // Hardcoded - breaks in dev
fetch("/chat/backend/api")         // Hardcoded - not configurable
```

**Important**:
- Python backend endpoints (`/api`, `/data`) → Use `getBackendPath()`
- Everything else (assets, Next.js routes) → Use `getAssetPath()`
- Never hardcode `/chat` or `/backend` prefixes

---

### 2. Don't Commit `.env.local`

Add to `.gitignore`:
```
# Environment overrides
frontend/.env.local
```

---

### 3. Rebuild After Environment Changes

```bash
# After changing .env.production
rm -rf frontend/.next
pnpm run build
```

---

### 4. Test Both Environments

```bash
# Test development
pnpm run dev

# Test production locally
pnpm run build
pnpm start
```

---

### 5. Document Custom Deployments

If using custom base paths, document in deployment guide:
```markdown
## Deployment

This application is deployed at `/myapp` sub-path.

Environment: NEXT_PUBLIC_BASE_PATH=/myapp
```

---

## Related Documentation

- [Next.js basePath Documentation](https://nextjs.org/docs/app/api-reference/next-config-js/basePath)
- [Environment Variables in Next.js](https://nextjs.org/docs/app/building-your-application/configuring/environment-variables)
- [IIS Reverse Proxy Configuration](https://learn.microsoft.com/en-us/iis/extensions/url-rewrite-module/reverse-proxy-with-url-rewrite-v2-and-application-request-routing)

## Changelog

### Version 1.0 (November 14, 2024)
- Initial implementation of configurable base path
- Created `.env.development` and `.env.production` files
- Updated `next.config.ts` to read from environment
- Implemented `getAssetPath()` utility with validation
- Removed all hardcoded `/chat` references from codebase
- Added comprehensive documentation
- Backend remains path-agnostic (IIS handles routing)

---

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review [Best Practices](#best-practices)
3. Open an issue in the project repository
