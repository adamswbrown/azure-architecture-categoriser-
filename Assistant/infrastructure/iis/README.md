# IIS Configuration Files

This directory contains IIS configuration files for different deployment scenarios.

## Configuration Files

### Development Configurations (with Node.js server on port 3000)

#### `web.config`
- **Use for**: Development/Testing without authentication
- **Requirements**:
  - Node.js server running on port 3000 (`cd frontend && pnpm run start`)
  - Python backend on port 8002
  - CopilotKit server on port 8001
- **Behavior**: IIS proxies all frontend requests to Node.js server

#### `web-auth.config`
- **Use for**: Development/Testing with authentication
- **Requirements**: Same as `web.config` plus:
  - `.AspNet.Cookies` authentication from main app
- **Behavior**: Same as `web.config` but requires authentication cookie

### Production Configurations (static file serving)

#### `web-static.config` ⭐ Recommended for Production
- **Use for**: Production deployment without authentication
- **Requirements**:
  - Static files in IIS directory (copy `frontend/out/` to `C:\inetpub\wwwroot\chat\`)
  - Python backend on port 8002
  - CopilotKit server on port 8001
  - NO Node.js server needed
- **Behavior**: IIS serves static files directly, proxies API calls to backends

#### `web-auth-static.config` ⭐ Recommended for Authenticated Production
- **Use for**: Production deployment with authentication
- **Requirements**: Same as `web-static.config` plus:
  - `.AspNet.Cookies` authentication from main app
- **Behavior**: Same as `web-static.config` but requires authentication cookie

## Quick Reference

| Scenario | Config File | Node.js Server | Auth Required |
|----------|-------------|----------------|---------------|
| Local dev testing | `web.config` | ✅ Port 3000 | ❌ |
| Dev with auth | `web-auth.config` | ✅ Port 3000 | ✅ |
| **Production** | `web-static.config` | ❌ | ❌ |
| **Production + Auth** | `web-auth-static.config` | ❌ | ✅ |

## Deployment Instructions

### Development Deployment

```bash
# 1. Build frontend
cd frontend
pnpm run build

# 2. Start Node.js server
pnpm run start  # Runs: serve out -p 3000

# 3. Copy config to IIS
copy iis\web.config C:\inetpub\wwwroot\chat\web.config
# OR for auth:
copy iis\web-auth.config C:\inetpub\wwwroot\chat\web.config

# 4. Restart IIS
iisreset
```

### Production Deployment (Static Files)

```bash
# 1. Build frontend
cd frontend
pnpm run build

# 2. Deploy static files
xcopy /E /Y out\* C:\inetpub\wwwroot\chat\

# 3. Copy config to IIS
copy iis\web-static.config C:\inetpub\wwwroot\chat\web.config
# OR for auth:
copy iis\web-auth-static.config C:\inetpub\wwwroot\chat\web.config

# 4. Restart IIS
iisreset
```

## Key Differences

### Development Configs vs Production Configs

**Development** (`web.config`, `web-auth.config`):
- ✅ Proxies `_next/*` to Node.js server
- ✅ Proxies `api/*` to Node.js server
- ✅ Proxies all requests to Node.js server
- ⚠️ Requires Node.js server running on port 3000

**Production** (`web-static.config`, `web-auth-static.config`):
- ❌ No `_next/*` proxy rule (files served directly from IIS)
- ❌ No `api/*` proxy rule (static export doesn't support API routes)
- ❌ No catch-all proxy to Node.js
- ✅ SPA fallback serves `index.html` for client-side routing
- ✅ Static files served directly by IIS
- ⚠️ NO Node.js server needed

### Backend Proxying (All Configs)

All configurations include these backend proxy rules:
- `/chat/copilotkit-api/*` → CopilotKit server port 8001
- `/chat/backend/*` → Python backend port 8002 (includes /api endpoint)
- `/chat/data*` → Python backend port 8002

## Architecture

### Development Architecture
```
Browser
  ↓
IIS (/chat)
  ├── /backend/* → Python Backend (8000)
  ├── /copilotkit-api/* → CopilotKit Server (8001)
  ├── /data* → Python Backend (8000)
  └── /* → Node.js Server (3000) [serves static files]
```

### Production Architecture
```
Browser
  ↓
IIS (/chat)
  ├── /backend/* → Python Backend (8000)
  ├── /copilotkit-api/* → CopilotKit Server (8001)
  ├── /data* → Python Backend (8000)
  └── /* → Static Files [served directly by IIS]
```

## Troubleshooting

### Problem: 404 errors for static files
- **Cause**: Using development config but Node.js server isn't running
- **Solution**: Either start Node.js server or switch to static config

### Problem: CORS errors
- **Cause**: CopilotKit server not running or misconfigured
- **Solution**: Ensure CopilotKit server is running on port 8001

### Problem: 401 Unauthorized
- **Cause**: Using auth config without authentication cookie
- **Solution**: Login to main app first or use non-auth config

### Problem: Backend API errors
- **Cause**: Python backend not running
- **Solution**: Ensure Python backend is running on port 8002

## Testing

### Test Static File Serving
```powershell
# Should return 200 and HTML
Invoke-WebRequest http://localhost/chat/

# Should return 200 and JavaScript
Invoke-WebRequest http://localhost/chat/_next/static/...
```

### Test Backend Proxying
```powershell
# Should proxy to Python backend
Invoke-WebRequest http://localhost/chat/backend/persona

# Should proxy to CopilotKit
Invoke-WebRequest http://localhost/chat/copilotkit-api/health
```

## Support

For more information about the application architecture, see:
- `/README.md` - Main project documentation
- `/docs/BASE_PATH_CONFIGURATION.md` - Base path and routing details
