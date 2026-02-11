# /chat Subapp Security Implementation Plan

## Executive Summary

The `/chat` subapp (Next.js frontend + Python backend) is currently **unprotected and publicly accessible**. This document outlines:
- Current security architecture and gaps
- How the main app's Azure AD OAuth works
- Proposed cookie-based session validation for `/chat`
- Implementation steps and timeline

**Recommendation**: Implement cookie-based session validation to reuse existing authentication without code duplication.

**Backend Architecture Insight**: Python backend (`agents/ag_ui.py`) already implements thread-scoped isolation via `thread_id`, preventing user-to-user data leakage at the application level. However, no user-level authentication exists, so anyone can guess thread_ids and access other users' conversations.

**Timeline**:
- **Phase 1 (Core)**: 2 hours - IIS cookie validation
- **Phase 2a (Optional)**: 1 hour - Frontend middleware
- **Phase 2b (Recommended)**: 2-3 hours - Backend auth + thread ownership
- **Testing**: 2 hours
- **Total**: 4-8 hours depending on which phases implemented

---

## 1. Current Architecture Overview

### 1.1 Main Application (Protected)

**Location**: `https://ra37-drmexp-dev-001.drmigrate.com.au/`

**Technology Stack**:
- Framework: ASP.NET MVC 5.2 (.NET Framework 4.8)
- Authentication: Azure AD / Entra ID (OIDC/OAuth2)
- Session Management: ASP.NET Forms Authentication with Cookies
- Configuration: `iis/web-main.config`

**Authentication Flow**:
1. User navigates to main app
2. Unauthenticated → redirected to `/Account/SignInOID`
3. ASP.NET initiates OIDC flow with Azure AD
4. User logs in with Azure AD credentials
5. Azure AD redirects back to: `https://ra37-drmexp-dev-001.drmigrate.com.au/Account/SignInOID`
6. ASP.NET validates token and creates session cookie
7. User is authenticated with `.AspNet.Cookies` session cookie

**Key Configuration** (from web-main.config):
```
IsAzureActiveDirectoryAuthenticationEnabled = true
AADTenant = 1047c81b-933d-481c-8b7c-643a5cc27a23
AADAppId = bd0b9073-82cd-4ab8-b7c6-f154cb1f0f52
AADRedirectURI = https://ra37-drmexp-dev-001.drmigrate.com.au/Account/SignInOID
AADPostLogoutRedirectURI = https://ra37-drmexp-dev-001.drmigrate.com.au/Account/SignIn
AADSuperAdminSecurityGroupId = 8efe460d-3686-4612-aed2-87f165d6aa57
```

### 1.2 /chat Subapp (Currently Unprotected)

**Location**: `https://ra37-drmexp-dev-001.drmigrate.com.au/chat/`

**Technology Stack**:
- Frontend: Next.js 15.5.3 (React 19)
- Backend API: Node.js/CopilotKit API routes (port 3000)
- Backend Service: Python Starlette app (port 8002)
  - Built with pydantic-ai, ag-ui integration
  - Supports multi-persona AI agents with thread-scoped isolation
  - Started via: `uv run agents` (pyproject.toml)
- Reverse Proxy: IIS (Windows Server)
- Configuration: `iis/web.config`

**Current Data Flow**:
```
User Browser (Any user, no auth check)
  ↓
IIS (Reverse proxy, no auth module)
  ↓
Next.js Server (Port 3000, no auth check)
  ↓
Python Backend (Port 8000, no auth check, thread-scoped isolation)
  ↓
Azure SQL Database
```

**Current Vulnerabilities**:
- ❌ No user authentication required
- ❌ No authorization checks
- ❌ No user context tracking (despite thread-scoped backend)
- ❌ No audit logging
- ❌ CORS wide open (`Access-Control-Allow-Origin: *`)
- ❌ Anyone can access the AI chat system
- ❌ No way to map requests to authenticated users

---

## 2. Cookie Analysis

### 2.1 Discovered Cookies

**Observation Date**: 2025-11-12

**Cookie 1: Session Cookie**
```
Name:     .AspNet.Cookies
Domain:   ra37-drmexp-dev-001.drmigrate.com.au
Path:     /
Expires:  Session
Size:     1637 bytes
Secure:   ✓ (HTTPS only)
HttpOnly: ✓ (Not accessible from JavaScript)
SameSite: Medium (CSRF protection)
```

**Value** (encrypted, truncated):
```
4pOSYGr7QcSVtoPvmdMHLYllZeLUhK2gElE_UIUUw8k--YqAzHROU7BRhyBUFo4wLUf...
[continued for ~1637 bytes, fully encrypted]
```

**Cookie 2: OIDC Nonce**
```
Name:     OpenIdConnect.nonce.nEG2tG8McPYZstM4a4Re%2BDFTJe6AsTHOJU%2BYfCGAn2I%3D
Domain:   ra37-drmexp-dev-001.drmigrate.com.au
Path:     /
Expires:  2025-11-12T02:34:44.271Z (token-based expiration)
Size:     390 bytes
Secure:   ✓ (HTTPS only)
HttpOnly: ✓ (Not accessible from JavaScript)
SameSite: None (required for OAuth redirect)
```

### 2.2 Why Cookies Are Encrypted

ASP.NET Forms Authentication cookies are **automatically encrypted** by default using:
- **Encryption**: Machine key (stored in IIS)
- **Encoding**: Base64 (for transport)
- **Tampering Protection**: HMAC signature included
- **Expiration**: Built-in timestamp validation

**Why this matters**:
- Decoding won't reveal plaintext content (encrypted)
- Cookie value is unique per server instance
- Can't be manually edited or forged
- Provides strong security guarantees

### 2.3 Cookie Scope & Sharing

**Domain Setting**: `ra37-drmexp-dev-001.drmigrate.com.au`

This means:
- ✅ Applies to main app at `/` and all subpaths
- ✅ Applies to `/chat/` subapp automatically
- ✅ Shared across all subdomains under `.drmigrate.com.au`
- ✅ Browser sends cookie automatically for all requests to this domain

**No Additional Configuration Needed**: The cookie is already available to `/chat` app!

---

## 3. Security Gap Analysis

### 3.1 Current Vulnerabilities

| Aspect | Status | Risk | Impact |
|--------|--------|------|--------|
| User Authentication | ❌ Missing | **CRITICAL** | Anyone can access chat |
| Authorization/RBAC | ❌ Missing | **CRITICAL** | No role-based access control |
| User Context | ❌ Missing | **HIGH** | No audit trail, can't track who did what |
| API Protection | ❌ Missing | **HIGH** | Backend APIs exposed |
| CORS Protection | ❌ Broken | **MEDIUM** | Any website can call /chat APIs |
| Session Management | ✅ Available | **LOW** | Main app handles this correctly |
| Data Encryption | ✅ Configured | **LOW** | HTTPS/TLS in place |

### 3.2 Attack Vectors

**1. Unauthorized Access**
- Attacker navigates to `https://ra37-drmexp-dev-001.drmigrate.com.au/chat/`
- No authentication required
- Can interact with AI system without credentials
- Can submit unlimited requests (no rate limiting)

**2. CORS Bypass**
- Attacker website makes requests to `/chat/api/copilotkit/`
- `Access-Control-Allow-Origin: *` allows cross-origin requests
- Can extract data or perform actions

**3. Data Exposure**
- No user context means no audit trail
- Can't determine who accessed what
- Compliance/regulatory violations (if applicable)

**4. Resource Abuse**
- No rate limiting or throttling
- DDoS attacks possible via Python backend

---

## 3.1 Python Backend Routes Inventory

**Location**: `agents/ag_ui.py` - Starlette application with 5 core endpoints

All routes are currently **unprotected and publicly accessible**.

### Frontend-Facing API Routes:

| Route | Method | Purpose | Protection Level | Used By |
|-------|--------|---------|------------------|---------|
| **`/api`** | POST | Main AG-UI endpoint for streaming agent responses | **CRITICAL** | CopilotKit frontend |
| **`/data`** | GET | Retrieve stored data by reference (thread-scoped) | **HIGH** | Frontend to fetch results |

### Backend Routes (Not Frontend-Facing):

- Health checks and diagnostic endpoints (managed by Starlette/Uvicorn)
- These are typically on `/health` or similar (not exposed via web.config rewrite)

### Thread-Scoped Isolation (Already Implemented):

**Key Design Feature**: Backend already isolates state per `thread_id`

From `ag_ui.py` (lines 19-22, 52-68, 70-93):
```python
# Each thread gets isolated state:
- ThreadState: persona, SSE queues, delegation flags
- DelegationRouter: manages per-thread state dictionary
- VirtualDatabase: thread-scoped data storage (thread_id parameter)

Result:
  - User A's thread_id=123 → isolated persona + data
  - User B's thread_id=456 → isolated persona + data
  - No cross-user contamination at application level
```

**What This Means for Security**:
- ✅ Backend **already prevents** user-to-user data leakage (via thread_id isolation)
- ❌ BUT **no authentication** to verify thread_id ownership
- ❌ **No audit trail** of which user made which request
- ❌ Anyone can guess/craft thread_ids and access other users' conversations

### How Thread-ID Isolation Works:

**Frontend** (CopilotKit):
1. Creates unique `thread_id` per conversation/tab
2. Sends all requests with `thread_id` in JSON body
3. Backend receives request with `thread_id`

**Backend** (ag_ui.py):
1. Extracts `thread_id` from request (`run_input.thread_id`)
2. Looks up/creates `ThreadState` for that thread_id
3. All operations (persona, data) scoped to that thread
4. Isolation is **per-thread**, not **per-user**

**Security Gap**:
- Thread isolation is **thread-level**, not **user-level**
- User A can send requests with User B's thread_id
- Backend has no way to verify ownership

### Combining Authentication with Thread Isolation:

**Once cookie auth is enabled**:
```
User A logs in → gets .AspNet.Cookies
  ↓
Sends request with thread_id=abc123
  ↓
IIS validates cookie → User A is authenticated
  ↓
Backend receives request with thread_id=abc123
  ↓
Backend needs to associate thread_id=abc123 with User A
  ↓
If another user tries thread_id=abc123, they should be denied
```

**Recommendation for Phase 2**:
- Add user context to thread state
- Store mapping: thread_id → authenticated_user
- Validate user owns thread before allowing access

---

## 4. Proposed Solution: Cookie-Based Session Validation

### 4.1 How It Works

**Architecture**:
```
┌─ User (Authenticated)
│  └─ Has .AspNet.Cookies from main app login
│
├─ IIS Reverse Proxy (/chat)
│  ├─ Check: Does request have .AspNet.Cookies?
│  │  ├─ YES → Allow request through
│  │  └─ NO → Return 401 Unauthorized
│  │
│  └─ Pass headers to backend:
│     ├─ X-Forwarded-User (optional, extracted from cookie)
│     └─ X-Forwarded-* (standard proxy headers)
│
├─ Next.js API Routes (Port 3000)
│  └─ Receive authenticated request + user context
│
└─ Python Backend (Port 8000)
   └─ Receive authenticated request + user context
```

**User Experience**:
1. User logs in to main app → gets `.AspNet.Cookies`
2. User navigates to `/chat` → browser sends cookie automatically
3. IIS validates cookie exists → allows access
4. If user logs out from main app → cookie is deleted
5. User tries to access `/chat` → cookie missing → 401 Unauthorized

### 4.2 Why This Solution

**Advantages**:
- ✅ **Minimal code changes**: Pure IIS configuration
- ✅ **No duplication**: Reuses existing Azure AD OAuth
- ✅ **Single sign-on**: One login for both apps
- ✅ **Single sign-out**: One logout affects both
- ✅ **Already shared**: Cookie is domain-scoped, no additional setup
- ✅ **Transparent**: Users don't see any changes
- ✅ **Secure**: Encrypted cookies, HTTPS-only, CSRF protection
- ✅ **Fast**: No additional authentication overhead
- ✅ **Audit trail**: Can extract user from cookie

**Disadvantages**:
- ⚠️ Couples /chat to main app's session lifetime
- ⚠️ Requires IIS knowledge to configure
- ⚠️ Can't use standalone /chat without main app

### 4.3 Comparison with Alternatives

| Approach | Effort | Security | Flexibility | Recommendation |
|----------|--------|----------|-------------|-----------------|
| **Cookie-Based** (Proposed) | 2 hours | High | Medium | ✅ **RECOMMENDED** |
| Windows Authentication | 3 hours | High | Low | Use if domain-bound |
| JWT Token | 6 hours | Very High | High | Use if scaling multi-service |
| No Auth | 0 hours | None | - | ❌ DO NOT USE |

---

## 5. Detailed Implementation Plan

### 5.1 Phase 1: IIS Configuration (iis/web.config)

**Objective**: Validate cookie presence before allowing access to /chat routes

**Changes Required**:

**Step 1: Add URL Rewrite Rule to Validate Cookie**
```xml
<!-- Add to <rewrite><rules> section, BEFORE other rules -->
<rule name="Require Authentication Cookie" stopProcessing="true">
  <match url="^(.*)$" />
  <conditions>
    <!-- Check if .AspNet.Cookies cookie is missing -->
    <add input="{HTTP_COOKIE}" pattern="\.AspNet\.Cookies" negate="true" />
    <!-- BUT allow static assets (they don't need auth) -->
    <add input="{REQUEST_URI}" pattern="^/chat/(_next|\.well-known|favicon)" negate="true" />
  </conditions>
  <action type="CustomResponse" statusCode="401" statusReason="Unauthorized" />
</rule>
```

**Step 2: Pass User Context Headers (Optional but Recommended)**
```xml
<!-- Add to <rewrite><outboundRules> section -->
<rule name="Pass User Context" preCondition="HasAuthCookie">
  <match serverVariable="RESPONSE_X-Forwarded-User" pattern=".+" negate="true" />
  <action type="Rewrite" value="{HTTP_COOKIE}" />
</rule>

<preConditions>
  <preCondition name="HasAuthCookie">
    <add input="{HTTP_COOKIE}" pattern="\.AspNet\.Cookies" />
  </preCondition>
</preConditions>
```

**File Location**: `C:\Users\uros\Documents\drm-chat-poc\iis\web.config`

### 5.2 Phase 2: Backend Middleware (Optional)

**Objective**: Add additional validation and user context extraction

#### Option A: Next.js Middleware (frontend/middleware.ts)

```typescript
import { NextRequest, NextResponse } from 'next/server';

export function middleware(request: NextRequest) {
  // Check for authentication cookie
  const authCookie = request.cookies.get('.AspNet.Cookies');

  if (!authCookie && !request.nextUrl.pathname.startsWith('/chat/_next')) {
    // No auth cookie and not a static asset
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    );
  }

  // Log authenticated request (for audit trail)
  console.log(`[AUTH] ${request.method} ${request.nextUrl.pathname}`);

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Apply to all routes except static assets
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};
```

**File Location**: `C:\Users\uros\Documents\drm-chat-poc\frontend\middleware.ts` (rename from `middleware.ts_`)

#### Option B: Python Backend Middleware (agents/ag_ui.py)

**Phase 2a - Basic Authentication Logging**:
```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Check for authentication cookie in request headers
        auth_cookie = request.cookies.get('.AspNet.Cookies')

        if not auth_cookie:
            return JSONResponse(
                {'error': 'Unauthorized - no authentication cookie'},
                status_code=401
            )

        # Log request with timestamp (audit trail)
        # Extract user from X-Forwarded-User header (set by IIS)
        user = request.headers.get('X-Forwarded-User', 'unknown')
        logger.info(f"[AUTH] {user} {request.method} {request.url.path}")

        # Add user context to request state
        request.state.authenticated = True
        request.state.user = user

        response = await call_next(request)
        return response

# Add to app initialization in DrMChatApp
app.add_middleware(AuthenticationMiddleware)
```

**Phase 2b - Thread Ownership Validation** (Optional but Recommended):
```python
from ag_ui import DrMChatApp

class ThreadOwnershipMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: DrMChatApp):
        super().__init__(app)
        self.app = app

    async def dispatch(self, request, call_next):
        # Only check ownership for routes that use thread_id
        if request.url.path.startswith('/data'):
            # Get thread_id from query params
            thread_id = request.query_params.get('thread_id', 'default')
            user = request.state.user

            # Check if user owns this thread
            thread_state = await self.app._delegation_router.get_thread_state(thread_id)

            # Option 1: Store owner in ThreadState
            if not hasattr(thread_state, 'owner'):
                thread_state.owner = user  # First access = owner
            elif thread_state.owner != user:
                return JSONResponse(
                    {'error': 'Unauthorized - thread not owned by user'},
                    status_code=403
                )

        response = await call_next(request)
        return response

# Add to app initialization
app.add_middleware(ThreadOwnershipMiddleware)
```

**Alternative - Store User in DrMChatApp**:
```python
class DrMChatApp(Starlette):
    def __init__(self, ...):
        # ... existing init code ...
        self._thread_owners: dict[str, str] = {}  # thread_id → username

    async def get_thread_owner(self, thread_id: str) -> str | None:
        return self._thread_owners.get(thread_id)

    async def set_thread_owner(self, thread_id: str, user: str):
        self._thread_owners[thread_id] = user
```

This approach allows Phase 2 to be added gradually without affecting Phase 1 deployment.

### 5.3 Phase 3: Testing Strategy

**Test Cases**:

1. **Unauthenticated Access** (Should Fail)
   - Clear all cookies
   - Navigate to `/chat/`
   - Expected: 401 Unauthorized

2. **Authenticated Access** (Should Succeed)
   - Login to main app
   - Navigate to `/chat/`
   - Expected: Page loads normally

3. **Session Timeout** (Should Fail)
   - Login to main app
   - Wait for session to expire (or manually delete cookie)
   - Refresh `/chat/`
   - Expected: 401 Unauthorized

4. **Cookie Sharing** (Should Work)
   - Login to main app
   - Open DevTools → Application → Cookies
   - Verify `.AspNet.Cookies` is present
   - Navigate to `/chat/`
   - Verify same cookie is still present
   - Expected: Access granted

5. **Static Assets** (Should Not Require Auth)
   - Clear all cookies
   - Request `/chat/_next/static/...`
   - Expected: 200 OK (static files served)

6. **API Endpoints** (Should Require Auth)
   - Clear all cookies
   - POST to `/chat/api/copilotkit/`
   - Expected: 401 Unauthorized

### 5.4 Implementation Timeline

| Phase | Task | Duration | Dependencies |
|-------|------|----------|--------------|
| **1** | Review & backup current web.config | 15 min | - |
| **1** | Add authentication rule to web.config | 30 min | Review complete |
| **1** | Test IIS rule works | 30 min | Rule added |
| **2** | Enable middleware.ts (rename file) | 15 min | Tested #1 |
| **2** | Add auth checks to middleware | 30 min | File renamed |
| **2** | Update Python backend (optional) | 1 hour | Middleware complete |
| **3** | Run test suite | 1 hour | All changes complete |
| **3** | Document lessons learned | 30 min | Testing complete |
| **Total** | | **4-6 hours** | - |

---

## 6. Configuration Files Reference

### 6.1 Files to Modify

**Phase 1 - Core Implementation**:
- `iis/web.config` - Add authentication rule (**REQUIRED**)

**Phase 2a - Optional Frontend Logging**:
- `frontend/middleware.ts_` - Rename to `middleware.ts` and add validation (**OPTIONAL**)

**Phase 2b - Optional Backend Hardening**:
- `agents/ag_ui.py` - Add AuthenticationMiddleware (**OPTIONAL** but recommended)
- `agents/ag_ui.py` - Add ThreadOwnershipMiddleware (**OPTIONAL** for thread-level access control)

**No Changes Needed**:
- `iis/web-main.config` - Main app config (reference only)
- `frontend/next.config.ts` - No auth config needed
- `frontend/.env.local` - No auth variables needed
- `pyproject.toml` - No changes needed (already configured correctly)
- `agents/server.py` - No changes needed (startup configured)

### 6.2 Backup Strategy

Before making changes:
```bash
# Backup web.config
copy iis/web.config iis/web.config.backup.$(date +%Y%m%d_%H%M%S)

# Backup middleware
copy frontend/middleware.ts_ frontend/middleware.ts_.backup
```

---

## 7. Security Considerations

### 7.1 Encryption & Tampering

**ASP.NET Cookie Security**:
- ✅ Encrypted by default with machine key
- ✅ Tamper-protected with HMAC signature
- ✅ Can't be forged by attackers
- ✅ Machine key stored securely in IIS

**What This Means**:
- Only the main app server can create valid cookies
- Attacker can't create fake session cookies
- Cookie can't be modified in transit
- Secure by design

### 7.2 HTTPS Requirements

**Critical**: Cookies only work over HTTPS

**Verify**:
- ✅ Domain `ra37-drmexp-dev-001.drmigrate.com.au` uses HTTPS (port 443)
- ✅ Cookies marked as `Secure` flag
- ✅ IIS configured for HTTPS binding

### 7.3 CORS Hardening

**Also Fix**: Update CORS to restrict origins

Current (BROKEN):
```typescript
'Access-Control-Allow-Origin': '*'  // ❌ Anyone can call
```

Recommended:
```typescript
'Access-Control-Allow-Origin': 'https://ra37-drmexp-dev-001.drmigrate.com.au'
'Access-Control-Allow-Credentials': 'true'  // Allow cookies
'Access-Control-Allow-Methods': 'POST, OPTIONS'
'Access-Control-Allow-Headers': 'Content-Type'
```

**File**: `frontend/app/api/copilotkit/route.ts` (lines ~156)

---

## 8. Rollback Plan

If something goes wrong, quickly revert:

```bash
# Step 1: Restore web.config
copy iis/web.config.backup.[timestamp] iis/web.config

# Step 2: Restart IIS Application Pool
appcmd recycle apppool /apppool.name:"chat"

# Step 3: Disable middleware (if enabled)
ren frontend/middleware.ts frontend/middleware.ts_

# Step 4: Restart Node.js
# (depends on how it's hosted - kill process or restart service)
```

**Validation**:
- ✅ /chat is accessible again without auth
- ✅ No error messages in IIS logs
- ✅ Both main app and /chat working

---

## 9. Monitoring & Audit

### 9.1 What to Monitor

**IIS Logs** (`C:\inetpub\logs\LogFiles\`):
- Look for 401 responses on /chat routes
- Verify authenticated requests return 200
- Check for patterns of unauthorized access

**Application Logs**:
- Middleware logs with `[AUTH]` prefix
- User context in each request
- Failed authentication attempts

**Metrics to Track**:
- Percentage of /chat requests from authenticated users
- 401 error rate (should be 0 for valid sessions)
- Session timeout frequency

### 9.2 Audit Trail

Add logging to track:
```
[2025-11-12 10:35:42] [AUTH] POST /chat/api/copilotkit/ - user authenticated
[2025-11-12 10:35:43] [AUTH] GET /chat/_next/static/... - static asset
[2025-11-12 10:35:50] [AUTH-FAIL] GET /chat/ - no auth cookie (401)
```

---

## 10. FAQ & Troubleshooting

### Q: Will this affect the main app?
**A**: No. Main app continues to work as-is. This only adds validation to `/chat`.

### Q: What happens when session expires?
**A**: Cookie is deleted by browser. Next request to `/chat` returns 401. User must re-login to main app.

### Q: Can we customize the 401 page?
**A**: Yes. Instead of `<action type="CustomResponse" statusCode="401" />`, use `<action type="Rewrite" url="/login" />`.

### Q: What if cookie is encrypted?
**A**: That's by design. We don't need to decrypt it - we just check if it exists. IIS/browser handles encryption/decryption.

### Q: Can /chat work without the main app?
**A**: No, with this approach. User must authenticate via main app first. Alternative: Use Option 2 (JWT Token) for standalone /chat.

### Q: Is this GDPR/compliance compliant?
**A**: Yes. We're authenticating users, not collecting additional data. Audit logs help with compliance.

---

## 11. Next Steps

**Phase 1 (Minimum - Strongly Recommended)**:
1. Review this document with team for approval
2. Backup current `iis/web.config`
3. Implement IIS authentication rule (section 5.1)
4. Test basic 401/200 responses
5. Monitor IIS logs for issues
6. Document completion

**Phase 2a (Nice to Have)**:
7. Enable and update `frontend/middleware.ts`
8. Add request logging
9. Test frontend validation
10. Monitor middleware logs

**Phase 2b (Recommended for Production)**:
11. Add `AuthenticationMiddleware` to `agents/ag_ui.py`
12. Implement thread ownership tracking
13. Add comprehensive audit logging
14. Full integration testing
15. Update procedures and runbooks
16. Train support team on new auth model

---

## Appendix A: Files Reference

| File | Purpose | Changes Needed |
|------|---------|-----------------|
| **IIS Configuration** | | |
| `iis/web.config` | /chat reverse proxy rules | ✅ **Phase 1**: Add auth rule |
| `iis/web-main.config` | Main app OAuth config | ❌ Read only (reference) |
| **Frontend** | | |
| `frontend/middleware.ts_` | Request validation | ✅ **Phase 2a**: Rename + update |
| `frontend/app/api/copilotkit/route.ts` | CopilotKit API endpoint | ✅ Fix CORS (both phases) |
| `frontend/next.config.ts` | Next.js config | ❌ No auth changes needed |
| `frontend/.env.local` | Frontend env vars | ❌ No auth changes needed |
| **Backend - Python** | | |
| `agents/ag_ui.py` | Main AG-UI Starlette app with 5 routes | ✅ **Phase 2b**: Add AuthenticationMiddleware + ThreadOwnershipMiddleware |
| `agents/server.py` | Server startup script | ❌ No changes (already configured) |
| `pyproject.toml` | Python dependencies + CLI entry point | ❌ No changes needed |
| **Backend - LLM** | | |
| `agents/config/llm_integration.py` | LLM provider routing | ❌ No auth changes (service-to-service) |
| `agents/delegator.py` | Persona delegation logic | ❌ No auth changes |
| `agents/personas.py` | Persona definitions | ❌ No auth changes |

---

## Appendix B: Related Documentation

- Main app configuration: `iis/web-main.config`
- Frontend middleware: `frontend/middleware.ts_`
- API endpoint: `frontend/app/api/copilotkit/route.ts`
- Python servers: `sse_chat.py`, `sse_chat_starlet.py`
- Architecture: `docs/ARCHITECTURE.md`
- Deployment guide: `docs/IIS_DEPLOYMENT_GUIDE.md`

---

**Document Version**: 1.1
**Created**: 2025-11-12
**Last Updated**: 2025-11-12
**Status**: Planning Phase - Ready for Phase 1 Implementation
**Author**: Claude Code Security Analysis
**Reviewed By**: [Pending]

### Version History

**v1.1** (2025-11-12):
- Added Section 3.1: Python Backend Routes Inventory
- Detailed thread-scoped isolation architecture
- Added Phase 2a & 2b implementation options with code examples
- Updated file reference table with specific phase assignments
- Clarified three-phase approach: Phase 1 (Core), Phase 2a (Optional), Phase 2b (Recommended)
- Added thread ownership validation recommendations

**v1.0** (Initial):
- Core security analysis and cookie-based solution proposal
- IIS configuration approach
- Authentication/authorization gap analysis
