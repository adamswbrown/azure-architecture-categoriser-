# Logging Module

## Overview

The logging module provides comprehensive tracking, monitoring, and quota management for the Dr.Migrate Assistant agents. It combines three core capabilities:

1. **OpenTelemetry (OTEL) Span Tracking** - Distributed tracing for debugging and performance monitoring
2. **Usage Tracking** - Token consumption tracking per user/thread with JSONL audit logs
3. **Quota Management** - Rolling window quota enforcement with persistent state across restarts

All components are initialized automatically when `agents.config` is imported and work together to provide visibility into system usage while enforcing resource limits.

---

## Architecture

### Components Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (CopilotKit)                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ AgentState: { user_id?, thread_id }                  │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP POST /api
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (DrMChatApp)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. Extract user_id, thread_id                        │   │
│  │ 2. Check quota (if enforcement enabled)              │   │
│  │ 3. Set usage metadata context (OTEL)                 │   │
│  │ 4. Run agent with streaming response                 │   │
│  │ 5. Record usage on completion                        │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────┬───────────────────────┬─────────────────────┘
                │                       │
                ▼                       ▼
    ┌───────────────────┐   ┌──────────────────────┐
    │  OTEL Exporter    │   │  Usage Aggregator    │
    │  (LocalLogfire)   │   │  + Quota Tracker     │
    └─────────┬─────────┘   └──────────┬───────────┘
              │                        │
              ▼                        ▼
    ┌───────────────────┐   ┌──────────────────────┐
    │ otel_spans.jsonl  │   │   UsageWriter        │
    │ (tracing data)    │   │   (dual-write)       │
    └───────────────────┘   └─────────┬────────────┘
                                      │
                        ┌─────────────┴─────────────┐
                        ▼                           ▼
              ┌─────────────────┐      ┌────────────────────┐
              │  usage.jsonl    │      │ Azure Blob Storage │
              │  (local file)   │      │  (append blob)     │
              └─────────────────┘      └────────────────────┘
                        │
                        │ Read on startup
                        ▼
             ┌──────────────────────┐
             │ InMemoryQuotaTracker │
             │ (rolling window)     │
             └──────────────────────┘
```

### Key Classes

- **`LocalLogfire`** - OpenTelemetry span exporter that writes to JSONL
- **`UsageAggregator`** - Tracks token usage per thread and interfaces with quota tracker
- **`QuotaTracker`** (Abstract) - Interface for quota enforcement with rolling windows
- **`InMemoryQuotaTracker`** - Default implementation (thread-safe, single-process)
- **`UsageWriter`** - Thread-safe writer for usage audit logs with dual-write support
- **`AzureBlobWriter`** - Handles Azure Blob Storage operations for usage logs

---

## Output Files

All log files are written to the directory specified in `config.toml` (default: `.logs/`). Usage logs can optionally be dual-written to Azure Blob Storage.

### otel_spans.jsonl

**Purpose**: Distributed tracing data for debugging and performance monitoring.

**Format**: One JSON object per line (JSONL)

**Schema**:
```json
{
  "start_timestamp": "2026-01-08T10:23:45.123456Z",
  "end_timestamp": "2026-01-08T10:23:47.890123Z",
  "span_name": "agent_run",
  "trace_id": "abc123...",
  "span_id": "def456...",
  "parent_span_id": null,
  "attributes": {
    "user_id": "user_12345",
    "thread_id": "thread_abc",
    "persona": "migration_engineer",
    ...
  },
  "events": [...],
  "status": "ok"
}
```

**Use Cases**:
- Performance profiling (span durations)
- Debugging agent execution flows
- Identifying bottlenecks in agent delegation or tool execution

---

### usage.jsonl

**Purpose**: Audit log of all LLM usage with token counts per user/thread.

**Format**: One JSON object per line (JSONL)

**Schema**:
```json
{
  "user_id": "user_12345",
  "thread_id": "thread_abc",
  "timestamp": "2026-01-08T10:23:47.890123Z",
  "query": "How much will the migration cost?",
  "response": "Based on your infrastructure...",
  "tokens_in": 1234,
  "tokens_out": 567,
  "provider": "anthropic",
  "model": "claude-sonnet-4.5",
  "persona": "financial_planner"
}
```

**Field Details**:
- `user_id`: User identifier (null for anonymous users)
- `thread_id`: Conversation thread identifier from CopilotKit
- `timestamp`: ISO 8601 UTC timestamp
- `query`: User's input message (last message in conversation)
- `response`: Agent's full response
- `tokens_in`: Input tokens (prompt + message history)
- `tokens_out`: Output tokens (agent response)
- `provider`: LLM provider (`anthropic`, `openai`, `bedrock`, etc.)
- `model`: Model identifier
- `persona`: Which agent persona handled the request

**Use Cases**:
- Usage analytics and reporting
- Quota restoration on application restart
- Auditing user activity
- Token consumption monitoring

**Azure Blob Storage Integration**:

Usage logs can be automatically written to both local file and Azure Blob Storage (append blob) for:
- Centralized logging across multiple instances
- Persistent cloud storage
- Long-term retention and archiving
- Integration with Azure analytics tools

See [Azure Blob Storage Configuration](#azure-blob-storage-optional) for setup details.

---

## Frontend Integration

### Required Fields in AgentState

The frontend (CopilotKit) must pass the following fields in the `state` property of AG-UI requests:

```typescript
interface AgentState {
  // REQUIRED
  thread_id: string;  // Automatically provided by CopilotKit
  
  // OPTIONAL - for quota tracking
  user_id?: string;   // Unique user identifier (omit for anonymous)
  
  // Other state fields...
  persona?: string;
  auto_specialist?: boolean;
}
```

### Anonymous vs Identified Users

**Anonymous Users** (`user_id` not provided or `null`):
- Usage is tracked in session only
- No quota limits enforced
- Usage still written to `usage.jsonl` with `user_id: null`
- Good for demos, public access, or development

**Identified Users** (`user_id` provided):
- Full quota tracking enabled
- Rolling window enforcement
- Usage persisted across sessions
- Required for production multi-tenant deployments

### Example Frontend Payload

```json
{
  "messages": [
    {"role": "user", "content": "What's the cost estimate?"}
  ],
  "state": {
    "user_id": "user_12345",
    "thread_id": "ckpt_abc123",
    "persona": "core",
    "auto_specialist": true
  },
  "thread_id": "ckpt_abc123"
}
```

---

## Backend Usage

### Initialization

The logging module is **automatically initialized** when you import `agents.config`:

```python
from agents import config  # Initializes logging automatically

# Logging is now active:
# - OTEL exporter writing to .logs/otel_spans.jsonl
# - UsageWriter writing to .logs/usage.jsonl
# - QuotaTracker loaded with historical usage
```

**What happens during initialization** (`agents/config/__init__.py`):

```python
# 1. Initialize OTEL exporter
initialize(otel_log_file=logging.OTEL_LOG_FILE, service_name="agents")

# 2. Initialize usage JSONL writer (with optional Azure Blob Storage)
initialize_usage_writer(
    file_path=logging.USAGE_LOG_FILE,
    storage_account=logging.AZURE_STORAGE_ACCOUNT,  # Optional
    container_name=logging.AZURE_CONTAINER_NAME,    # Optional
    blob_name=logging.AZURE_BLOB_NAME               # Optional
)

# 3. Setup Python logging
setup_logging(level=logging.LOG_LEVEL)

# 4. Restore historical usage from usage.jsonl
records_restored = initialize_quota_tracker(file_path=logging.USAGE_LOG_FILE)

# 5. Configure default quota limits
tracker = get_quota_tracker()
tracker.set_default_limits(QuotaLimits(
    daily_token_limit=quota.DAILY_TOKEN_LIMIT,
    window_hours=quota.QUOTA_WINDOW_HOURS
))
```

### Setting Usage Metadata (OTEL Context)

Usage metadata is attached to OTEL spans for correlation:

```python
from agents.logging import set_usage_metadata, UsageMetadata

# In your request handler
metadata = UsageMetadata(
    user_id=user_id,      # Can be None for anonymous
    thread_id=thread_id
)
set_usage_metadata(metadata)

# Now all OTEL spans will include these attributes
# Run your agent...

# Cleanup after request completes
from agents.logging.otel import clear_usage_metadata
clear_usage_metadata()
```

### Recording Usage

Usage is typically recorded automatically by `DrMChatApp` after each agent run, but you can also record it manually:

```python
from agents.logging.usage import UsageAggregator, UsageItem, UsageMetadata
from pydantic_ai import RunUsage

# Create aggregator for the user/thread
metadata = UsageMetadata(
    user_id="user_12345",
    thread_id="thread_xyz"
)
aggregator = UsageAggregator(metadata=metadata)

# After an agent run
run_result = await agent.run(...)
usage = run_result.usage()

# Create usage item
item = UsageItem(
    usage=usage,
    provider_id="anthropic",
    model_ref="claude-sonnet-4.5"
)

# Record usage (checks quota, updates tracker, logs session)
aggregator.add_usage_item(item, enforce_quota=True)

# Access usage metrics
print(f"Total tokens: {aggregator.total_tokens}")
print(f"Remaining tokens: {aggregator.remaining_tokens}")
```

### Writing to usage.jsonl

Usage records are written automatically when usage is recorded, but you can also write directly:

```python
from agents.logging import get_usage_writer, UsageRecord
from datetime import datetime, timezone

writer = get_usage_writer()
if writer:
    record = UsageRecord(
        user_id="user_12345",
        thread_id="thread_abc",
        timestamp=datetime.now(timezone.utc).isoformat(),
        query="What is the migration timeline?",
        response="The migration will take approximately...",
        tokens_in=500,
        tokens_out=200,
        provider="anthropic",
        model="claude-sonnet-4.5",
        persona="project_manager"
    )
    writer.write(record)
```

---

## Quota System

### How It Works (Rolling Windows)

The quota system enforces limits using **24-hour rolling windows** (configurable):

```
Current Time: Jan 8, 10:00 AM
Window: 24 hours
Cutoff: Jan 7, 10:00 AM

Timeline:
─────────────────────────────────────────────────────────
  Jan 7              Jan 8              Jan 9
  10 AM              10 AM              10 AM
    ↑                  ↑
    └──── Window ──────┘
          (24 hrs)

Records from Jan 7 9:00 AM: ❌ Excluded (too old)
Records from Jan 7 11:00 AM: ✅ Included (within window)
Records from Jan 8 9:00 AM: ✅ Included (within window)
```

**Key Features**:
- **Time-based**: Records naturally expire as they fall outside the window
- **Continuous**: No daily reset at midnight - window rolls continuously
- **Per-user**: Each user has independent quota tracking
- **Persistent**: Usage restored from `usage.jsonl` on startup

### Configuration

Edit `config.toml` to configure quotas:

```toml
[quota]
# Token limit per rolling window (null = unlimited)
DAILY_TOKEN_LIMIT = 1000000  # 1M tokens

# Rolling window size in hours
QUOTA_WINDOW_HOURS = 24

# Whether to enforce quotas
ENFORCE_QUOTA = true
```

**Configuration Options**:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `DAILY_TOKEN_LIMIT` | int or null | null | Max tokens per window (null = unlimited) |
| `QUOTA_WINDOW_HOURS` | int | 24 | Rolling window size in hours |
| `ENFORCE_QUOTA` | bool | false | Enable/disable quota enforcement |

### Quota Enforcement Flow

```python
# In DrMChatApp.handle_request()

# 1. Check quota BEFORE processing
if config.quota.ENFORCE_QUOTA and user_id is not None:
    tracker = get_quota_tracker()
    is_within_quota, error = tracker.check_quota(user_id)
    
    if not is_within_quota:
        # Return 429 Too Many Requests
        return JSONResponse(
            content=error.to_response_dict(),
            status_code=HTTPStatus.TOO_MANY_REQUESTS
        )

# 2. Process request
run_result = await agent.run(...)

# 3. Record usage (updates quota tracker)
aggregator.add_usage_item(usage_item, enforce_quota=True)
```

**Quota Exceeded Response** (HTTP 429):
```json
{
  "error": "quota_exceeded",
  "message": "You have exceeded your daily Assistant quota. You will be able to continue at 2026-01-09 10:23:45 UTC.",
  "current_usage": 1050000,
  "limit": 1000000,
  "resume_time": "2026-01-09T10:23:45+00:00"
}
```

### Persistence & Restoration

**On Application Startup**:

1. `initialize_quota_tracker()` reads `usage.jsonl`
2. Parses all usage records with valid JSON
3. Filters records within each user's rolling window
4. Populates `InMemoryQuotaTracker` with historical usage
5. Logs: `"Restored 1234 usage records from .logs/usage.jsonl (2000 total records read, 766 expired)"`

**Benefits**:
- ✅ Quota state survives restarts
- ✅ Users cannot bypass quotas by restarting the service
- ✅ Expired records automatically excluded
- ✅ Corrupted records skipped with warnings

**Implementation**: See `InMemoryQuotaTracker.load_from_file()` in [usage.py](usage.py#L418).

### Anonymous vs Identified Users

| Feature | Anonymous (`user_id=None`) | Identified (`user_id` provided) |
|---------|---------------------------|--------------------------------|
| Session usage tracking | ✅ Yes | ✅ Yes |
| Quota enforcement | ❌ No (unlimited) | ✅ Yes |
| Global quota tracker | ❌ Skipped | ✅ Updated |
| Written to `usage.jsonl` | ✅ Yes (with `user_id: null`) | ✅ Yes |
| Restored on startup | ❌ No | ✅ Yes |

---

## Configuration (config.toml)

### Logging Settings

```toml
[logging]
# Directory for all log files
LOGGING_DIR = "./.logs"

# Python logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = "INFO"

# Output files (automatically derived):
# - otel_spans.jsonl: {LOGGING_DIR}/otel_spans.jsonl
# - usage.jsonl: {LOGGING_DIR}/usage.jsonl
```

### Azure Blob Storage (Optional)

Usage logs can be dual-written to Azure Blob Storage for centralized logging:

```toml
[logging]
# Azure Blob Storage configuration (optional)
# If configured, usage logs will be written to both local file and Azure Blob Storage
# Requires Azure CLI login (az login) or Managed Identity in production

AZURE_STORAGE_ACCOUNT = "yourstorageaccount"
AZURE_CONTAINER_NAME = "usage-logs"  # Default: "usage-logs"
AZURE_BLOB_NAME = "usage.jsonl"      # Default: "usage.jsonl"
```

**Authentication**:
- **Development**: Uses Azure CLI credentials (`az login`)
- **Production**: Uses Managed Identity (no credentials needed)

**Required Permissions**:
- **Storage Blob Data Contributor** (recommended)
- Or **Storage Blob Data Owner**

**How It Works**:
1. On first write, `AzureBlobWriter` initializes connection
2. Container is created if it doesn't exist
3. Append blob is created if it doesn't exist
4. Each usage record is appended to both local file and blob
5. Blob write failures are logged but don't stop local file writes

**Setup Example**:

```bash
# Development: Login to Azure
az login

# Production: Assign Managed Identity permission
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee <managed-identity-principal-id> \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account>
```

For detailed documentation, see [AZURE_BLOB_USAGE_LOGGING.md](../../AZURE_BLOB_USAGE_LOGGING.md).

### Quota Settings

```toml
[quota]
# Token limit per rolling window (null = unlimited)
DAILY_TOKEN_LIMIT = 1000000

# Rolling window size in hours
QUOTA_WINDOW_HOURS = 24

# Enable/disable quota enforcement
ENFORCE_QUOTA = true
```

**Environment-Specific Configs**:
- `config.toml` - Local development (git-ignored)
- `config.infra-dev.toml` - Development environment
- `config.infra-prod.toml` - Production environment

---

## Extending the System

### Adding New Metadata Fields

To add custom metadata fields to OTEL spans and usage tracking:

**1. Update `UsageMetadata` dataclass** ([usage.py](usage.py#L541)):

```python
@dataclass
class UsageMetadata:
    """Metadata for usage tracking."""
    user_id: Optional[str]
    thread_id: str
    
    # NEW FIELDS
    organization_id: Optional[str] = None
    session_id: Optional[str] = None
    client_version: Optional[str] = None
```

**2. Update `AgentState` in `deps.py`** (if coming from frontend):

```python
class AgentState(BaseModel):
    user_id: Optional[str] = None
    # ... existing fields ...
    
    # NEW FIELDS
    organization_id: Optional[str] = None
    session_id: Optional[str] = None
    client_version: Optional[str] = None
```

**3. Extract in `DrMChatApp.handle_request()`** ([app.py](app.py)):

```python
user_id = state.user_id
organization_id = state.organization_id  # NEW
session_id = state.session_id            # NEW

metadata = UsageMetadata(
    user_id=user_id,
    thread_id=thread_id,
    organization_id=organization_id,      # NEW
    session_id=session_id,                # NEW
    client_version=state.client_version   # NEW
)
```

**4. Update `UsageRecord` if logging to JSONL** ([usage.py](usage.py#L710)):

```python
@dataclass
class UsageRecord:
    user_id: Optional[str]
    thread_id: str
    # ... existing fields ...
    
    # NEW FIELDS
    organization_id: Optional[str] = None
    session_id: Optional[str] = None
```

**5. Update frontend to pass new fields**:

```typescript
const state = {
  user_id: user.id,
  thread_id: threadId,
  organization_id: user.organizationId,  // NEW
  session_id: sessionId,                 // NEW
  client_version: "1.2.3"                // NEW
};
```

### Custom Quota Backends

The default `InMemoryQuotaTracker` is suitable for single-process deployments. For distributed systems, implement a custom backend:

**1. Implement the `QuotaTracker` abstract class**:

```python
from agents.logging.usage import QuotaTracker, QuotaLimits, QuotaExceededError, UsageSnapshot
import redis

class RedisQuotaTracker(QuotaTracker):
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def set_limits(self, user_id: str, limits: QuotaLimits) -> None:
        # Store in Redis
        key = f"quota:limits:{user_id}"
        self.redis.hset(key, mapping={
            "token_limit": limits.daily_token_limit or -1,
            "window_hours": limits.window_hours
        })
    
    def record_usage(self, user_id: str, tokens: int, thread_id: str = "") -> None:
        # Store timestamped record in Redis sorted set
        key = f"quota:usage:{user_id}"
        timestamp = time.time()
        record = json.dumps({"tokens": tokens, "thread_id": thread_id})
        self.redis.zadd(key, {record: timestamp})
    
    def get_usage_in_window(self, user_id: str, window_hours: Optional[int] = None) -> UsageSnapshot:
        # Query Redis sorted set within time window
        # ...
    
    # Implement remaining abstract methods...
```

**2. Swap the global tracker** (in `agents/config/__init__.py`):

```python
from agents.logging import set_quota_tracker
from your_module import RedisQuotaTracker
import redis

# Initialize Redis connection
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Replace the default tracker
tracker = RedisQuotaTracker(redis_client)
set_quota_tracker(tracker)

# Configure limits
tracker.set_default_limits(QuotaLimits(...))
```

### Adding New Log Outputs

To add additional log outputs (e.g., Elasticsearch, S3, database):

**1. Create a custom writer**:

```python
from agents.logging import UsageRecord
import elasticsearch

class ElasticsearchUsageWriter:
    def __init__(self, es_client: elasticsearch.Elasticsearch, index: str):
        self.es = es_client
        self.index = index
    
    def write(self, record: UsageRecord) -> None:
        doc = {
            "user_id": record.user_id,
            "thread_id": record.thread_id,
            "timestamp": record.timestamp,
            # ... all fields ...
        }
        self.es.index(index=self.index, document=doc)
```

**2. Initialize and use in parallel with existing writer**:

```python
# In DrMChatApp._increment_usage() callback
from your_module import ElasticsearchUsageWriter

es_writer = ElasticsearchUsageWriter(es_client, index="usage-logs")

# Write to both JSONL and Elasticsearch
writer = get_usage_writer()
if writer:
    writer.write(usage_record)

es_writer.write(usage_record)
```

---

## Examples

### Complete Flow Example

```python
from agents.logging import (
    UsageAggregator, UsageItem, UsageMetadata,
    set_usage_metadata, get_usage_writer, UsageRecord
)
from datetime import datetime, timezone

# 1. Create usage metadata for the request
metadata = UsageMetadata(
    user_id="user_12345",
    thread_id="thread_abc123"
)

# 2. Set OTEL context
set_usage_metadata(metadata)

# 3. Create usage aggregator
aggregator = UsageAggregator(metadata=metadata)

# 4. Run agent
run_result = await agent.run(
    "What's the migration cost?",
    deps=deps,
    model=model
)

# 5. Extract usage
usage = run_result.usage()
item = UsageItem(
    usage=usage,
    provider_id="anthropic",
    model_ref="claude-sonnet-4.5"
)

# 6. Record usage (checks quota, updates tracker)
try:
    aggregator.add_usage_item(item, enforce_quota=True)
except QuotaExceededError as e:
    print(f"Quota exceeded: {e}")
    # Return 429 to frontend

# 7. Write to usage.jsonl
writer = get_usage_writer()
if writer:
    record = UsageRecord(
        user_id=metadata.user_id,
        thread_id=metadata.thread_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        query="What's the migration cost?",
        response=run_result.output,
        tokens_in=usage.input_tokens,
        tokens_out=usage.output_tokens,
        provider="anthropic",
        model="claude-sonnet-4.5",
        persona="financial_planner"
    )
    writer.write(record)

# 8. Check remaining quota
print(f"Remaining tokens: {aggregator.remaining_tokens}")
```

### Testing Quota Limits

```python
from agents.logging import get_quota_tracker, QuotaLimits

# Set a low quota for testing
tracker = get_quota_tracker()
tracker.set_limits("test_user", QuotaLimits(
    daily_token_limit=1000,      # Only 1000 tokens
    window_hours=24
))

# Simulate usage
tracker.record_usage("test_user", tokens=800, thread_id="test_thread")

# Check quota before next request
ok, error = tracker.check_quota("test_user", additional_tokens=300)
if not ok:
    print(f"Would exceed quota: {error}")
    print(f"Resume time: {error.resume_time}")

# Check remaining
remaining_tokens = tracker.get_remaining("test_user")
print(f"Remaining: {remaining_tokens} tokens")
```

### Anonymous User Tracking

```python
# Create aggregator without user_id
metadata = UsageMetadata(
    user_id=None,        # Anonymous
    thread_id="thread_xyz"
)

aggregator = UsageAggregator(metadata=metadata)

# Usage is tracked in session
item = UsageItem(usage=usage, provider_id="anthropic", model_ref="claude-sonnet-4.5")
aggregator.add_usage_item(item)  # No quota check, always succeeds

# Session metrics still available
print(f"Session tokens: {aggregator.total_tokens}")

# Quota methods return "unlimited"
print(f"Remaining tokens: {aggregator.remaining_tokens}")  # None (unlimited)
print(f"Below quota: {aggregator.below_quota}")            # True (always)
```

---

## Troubleshooting

### Issue: Quota not persisting across restarts

**Symptom**: Users can exceed quota by restarting the application.

**Solution**: Verify quota tracker initialization is working:

```python
from agents.logging import initialize_quota_tracker
from pathlib import Path

records = initialize_quota_tracker(Path(".logs/usage.jsonl"))
print(f"Restored {records} records")
```

Check logs for:
```
INFO - Restored 1234 usage records from .logs/usage.jsonl
```

If `0` records restored:
1. Check `usage.jsonl` exists and is not empty
2. Check records have valid timestamps
3. Check records are within the window (24 hours by default)

---

### Issue: usage.jsonl not being written

**Symptom**: File is empty or not created.

**Solution**:

1. Check initialization:
```python
from agents.logging import get_usage_writer

writer = get_usage_writer()
print(f"Writer initialized: {writer is not None}")
```

2. Check directory exists:
```python
from agents.config import logging
print(f"Logging directory: {logging.LOGGING_DIR}")
print(f"Exists: {logging.LOGGING_DIR.exists()}")
```

3. Check permissions:
```bash
ls -la .logs/
# Should be writable by current user
```

---

### Issue: OTEL spans missing user_id

**Symptom**: `otel_spans.jsonl` has spans without user attribution.

**Solution**: Ensure `set_usage_metadata()` is called before agent execution:

```python
from agents.logging import set_usage_metadata, UsageMetadata

# BEFORE running agent
metadata = UsageMetadata(user_id="user_123", thread_id="...")
set_usage_metadata(metadata)

# Run agent
run_result = await agent.run(...)

# AFTER completion (cleanup)
from agents.logging.otel import clear_usage_metadata
clear_usage_metadata()
```

---

### Issue: Quota errors for anonymous users

**Symptom**: Anonymous users getting 429 errors.

**Solution**: Ensure `user_id` is `None` (not empty string):

```python
# WRONG
metadata = UsageMetadata(user_id="", thread_id="...")

# CORRECT
metadata = UsageMetadata(user_id=None, thread_id="...")
```

Also verify enforcement is not applied to anonymous:
```python
# In DrMChatApp.handle_request()
if config.quota.ENFORCE_QUOTA and user_id is not None:  # Check for 'is not None'
    # Enforce quota
```

---

### Issue: High memory usage from quota tracker

**Symptom**: Memory grows over time with many users.

**Solution**: The `InMemoryQuotaTracker` automatically cleans up old records:

- Every 100 records per user triggers cleanup
- Removes records older than `window_hours + 1`

For heavy usage or distributed systems, consider implementing `RedisQuotaTracker` (see [Custom Quota Backends](#custom-quota-backends)).

---

### Issue: Corrupted usage.jsonl causing startup failures

**Symptom**: Application fails to start with JSON parsing errors.

**Solution**: The quota tracker skips corrupted lines gracefully:

```python
# In InMemoryQuotaTracker.load_from_file()
try:
    data = json.loads(line)
    # Process...
except json.JSONDecodeError as e:
    logger.warning(f"Skipping line {line_num}: invalid JSON: {e}")
    continue
```

To repair manually:
```bash
# Find corrupted lines
jq . .logs/usage.jsonl > /dev/null

# Or remove corrupted lines
jq -c . .logs/usage.jsonl > .logs/usage.jsonl.clean
mv .logs/usage.jsonl.clean .logs/usage.jsonl
```

---

### Issue: Azure Blob Storage not writing

**Symptom**: Usage logs written to local file but not appearing in Azure Blob Storage.

**Solution**:

1. Check if Azure SDK is installed:
```bash
pip list | grep azure
# Should show: azure-identity, azure-storage-blob
```

2. Check configuration in logs:
```
INFO | agents.logging.azure_blob_writer | Azure Blob Storage initialized: account/container/blob
```

If you see:
```
DEBUG | agents.logging.azure_blob_writer | Azure SDK not available
```
Install the SDK:
```bash
pip install azure-identity azure-storage-blob
```

3. Check authentication:
```bash
# Development: Verify Azure CLI login
az account show

# Production: Verify Managed Identity has permissions
az role assignment list --assignee <managed-identity-id>
```

4. Check for write failures in logs:
```
WARNING | agents.logging.azure_blob_writer | Failed to append to blob: <error>
```

Common errors:
- "AuthenticationError": Run `az login` or check Managed Identity
- "AuthorizationPermissionMismatch": Add "Storage Blob Data Contributor" role
- "ContainerNotFound": Container should be auto-created; check permissions

---

## API Reference

### Core Functions

#### `initialize(otel_log_file: Path, service_name: str) -> None`
Initialize OTEL exporter with LocalLogfire backend. Called once at startup.

#### `initialize_usage_writer(file_path: Path, storage_account: Optional[str] = None, container_name: Optional[str] = None, blob_name: Optional[str] = None) -> UsageWriter`
Initialize the global usage JSONL writer with optional Azure Blob Storage. Called once at startup.

**Parameters**:
- `file_path`: Path to local usage.jsonl file
- `storage_account`: Azure Storage account name (optional)
- `container_name`: Container name (default: "usage-logs")
- `blob_name`: Blob name (default: "usage.jsonl")

#### `initialize_quota_tracker(file_path: Path) -> int`
Load historical usage from JSONL file into quota tracker. Returns number of records restored.

#### `set_usage_metadata(metadata: UsageMetadata) -> None`
Set usage metadata in OTEL context for current request. All spans created within this context will include the metadata as attributes.

#### `clear_usage_metadata() -> None`
Clear usage metadata from OTEL context. Should be called after request completes.

#### `get_usage_writer() -> Optional[UsageWriter]`
Get the global UsageWriter instance.

#### `get_quota_tracker() -> QuotaTracker`
Get the global QuotaTracker instance (default: InMemoryQuotaTracker).

#### `set_quota_tracker(tracker: QuotaTracker) -> None`
Replace the global quota tracker (for custom implementations).

---

### Key Classes

#### `UsageMetadata`
```python
@dataclass
class UsageMetadata:
    user_id: Optional[str]      # User identifier (None for anonymous)
    thread_id: str              # Thread/conversation identifier
```

#### `UsageAggregator`
Tracks usage for a user/thread with quota integration.

**Key Methods**:
- `add_usage_item(item, enforce_quota=True)` - Record usage, check quota
- `check_quota(additional_tokens)` - Pre-check if usage would exceed quota
- `initialize_quota(daily_token_limit, window_hours)` - Set user-specific limits

**Key Properties**:
- `total_tokens` - Session token usage
- `remaining_tokens` - Tokens left in quota window
- `usage_in_window` - UsageSnapshot for rolling window
- `below_quota` - Boolean: is user under limits?

#### `QuotaTracker` (Abstract)
Interface for quota tracking implementations.

**Key Methods**:
- `set_limits(user_id, limits)` - Configure limits for a user
- `record_usage(user_id, tokens, thread_id)` - Record consumption
- `check_quota(user_id, additional_tokens)` - Check if usage would exceed
- `get_usage_in_window(user_id, window_hours)` - Get usage within window
- `get_remaining(user_id)` - Get remaining allowance

#### `UsageRecord`
Single record for usage.jsonl audit log.

```python
@dataclass
class UsageRecord:
    user_id: Optional[str]
    thread_id: str
    timestamp: str              # ISO 8601
    query: str
    response: str
    tokens_in: int
    tokens_out: int
    provider: str
    model: str
    persona: str
```

#### `QuotaLimits`
Configuration for user quota limits.

```python
@dataclass
class QuotaLimits:
    daily_token_limit: Optional[int] = None    # None = unlimited
    window_hours: int = 24                     # Rolling window size
```

#### `QuotaExceededError`
Exception raised when quota is exceeded.

**Attributes**:
- `user_id` - User who exceeded
- `current_usage` - Current consumption (tokens)
- `limit` - Configured limit (tokens)
- `resume_time` - When user can resume (datetime)

**Methods**:
- `to_response_dict()` - Convert to JSON response for frontend

#### `AzureBlobWriter`
Handles Azure Blob Storage operations for usage logs.

**Constructor**:
```python
AzureBlobWriter(
    storage_account: str,
    container_name: str,
    blob_name: str,
    logger: Optional[logging.Logger] = None
)
```

**Key Methods**:
- `initialize() -> bool` - Set up blob client, create container/blob if needed
- `append(data: str) -> bool` - Append string data to blob
- `close() -> None` - Clean up resources

**Key Properties**:
- `is_available` - Check if Azure SDK is installed
- `is_initialized` - Check if successfully initialized

**Example**:
```python
from agents.logging import AzureBlobWriter

writer = AzureBlobWriter(
    storage_account="myaccount",
    container_name="usage-logs",
    blob_name="usage.jsonl"
)

if writer.is_available:
    if writer.initialize():
        writer.append("log line\n")
    writer.close()
```

---

## See Also

- [OTEL Module](otel.py) - OpenTelemetry span exporter implementation
- [Usage Module](usage.py) - Usage tracking and quota management
- [Azure Blob Writer Module](azure_blob_writer.py) - Azure Blob Storage integration
- [Logger Module](logger.py) - Python logging configuration
- [Config Module](../config/) - Configuration management
- [App Module](../ag_ui/app.py) - Main application integration
- [Azure Blob Usage Logging Guide](../../AZURE_BLOB_USAGE_LOGGING.md) - Detailed Azure setup

---

**Version**: 1.0  
**Last Updated**: January 8, 2026  
**Maintainer**: Dr.Migrate Team
