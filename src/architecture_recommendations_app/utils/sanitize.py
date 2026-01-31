"""Security sanitization utilities.

Provides functions for safely handling user input in HTML contexts,
validating URLs, and secure temporary file handling.

Security audit: 2024 - Addresses XSS, SSRF, and temp file vulnerabilities.
"""

import html
import ipaddress
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional
from urllib.parse import urlparse


# Allowed domains for external URL fetching (SSRF protection)
ALLOWED_URL_DOMAINS = frozenset([
    # Microsoft documentation and assets
    'microsoft.com',
    'azure.com',
    'learn.microsoft.com',
    'docs.microsoft.com',
    'azure.microsoft.com',
    # Microsoft CDN domains
    'azureedge.net',
    'akamaized.net',
    'msecnd.net',
    # GitHub (for architecture diagrams)
    'github.com',
    'githubusercontent.com',
    'raw.githubusercontent.com',
])

# Blocked IP ranges (RFC 1918, loopback, link-local, etc.)
BLOCKED_IP_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),  # Link-local
    ipaddress.ip_network('::1/128'),  # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),  # IPv6 private
    ipaddress.ip_network('fe80::/10'),  # IPv6 link-local
]

# Cloud metadata endpoints to block
BLOCKED_HOSTNAMES = frozenset([
    'metadata.google.internal',
    'metadata.goog',
    '169.254.169.254',  # AWS/Azure/GCP metadata
    '100.100.100.200',  # Alibaba Cloud metadata
])


def safe_html(value: Any) -> str:
    """Escape a value for safe interpolation into HTML.

    Use this function whenever inserting user-controlled data into HTML
    that will be rendered with unsafe_allow_html=True.

    Args:
        value: Any value to escape. Will be converted to string first.

    Returns:
        HTML-escaped string safe for interpolation.

    Example:
        >>> safe_html("<script>alert('xss')</script>")
        '&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;'
    """
    return html.escape(str(value), quote=True)


def safe_html_attr(value: Any) -> str:
    """Escape a value for safe use in an HTML attribute.

    This is stricter than safe_html() - also escapes quotes for
    use inside attribute values.

    Args:
        value: Any value to escape.

    Returns:
        String safe for use in HTML attributes.
    """
    # html.escape with quote=True handles this
    return html.escape(str(value), quote=True)


def _is_ip_blocked(hostname: str) -> bool:
    """Check if a hostname resolves to a blocked IP range."""
    try:
        # Try to parse as IP address directly
        ip = ipaddress.ip_address(hostname)
        return any(ip in network for network in BLOCKED_IP_RANGES)
    except ValueError:
        # Not an IP address, hostname will be checked against domain list
        return False


def _get_domain_suffix(hostname: str) -> str:
    """Extract the registrable domain from a hostname.

    Examples:
        docs.microsoft.com -> microsoft.com
        sub.example.azure.com -> azure.com
    """
    parts = hostname.lower().split('.')
    if len(parts) >= 2:
        # Return last two parts (e.g., microsoft.com)
        return '.'.join(parts[-2:])
    return hostname.lower()


def validate_url(
    url: str,
    allowed_domains: Optional[frozenset[str]] = None,
    allow_http: bool = False,
) -> tuple[bool, str]:
    """Validate a URL for safe fetching (SSRF protection).

    Checks:
    - URL scheme is HTTPS (or HTTP if explicitly allowed)
    - Hostname is not a blocked IP or metadata endpoint
    - Domain is in the allowed list

    Args:
        url: The URL to validate.
        allowed_domains: Set of allowed domain suffixes. Defaults to ALLOWED_URL_DOMAINS.
        allow_http: If True, allow HTTP in addition to HTTPS. Default False.

    Returns:
        Tuple of (is_valid, error_message). Error message is empty if valid.

    Example:
        >>> validate_url("https://docs.microsoft.com/image.png")
        (True, "")
        >>> validate_url("http://169.254.169.254/latest/meta-data/")
        (False, "URL hostname is blocked")
    """
    if allowed_domains is None:
        allowed_domains = ALLOWED_URL_DOMAINS

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    # Check scheme
    allowed_schemes = {'https'}
    if allow_http:
        allowed_schemes.add('http')

    if parsed.scheme.lower() not in allowed_schemes:
        return False, f"URL scheme must be {'HTTPS' if not allow_http else 'HTTPS or HTTP'}"

    # Check for hostname
    if not parsed.netloc:
        return False, "URL must have a hostname"

    hostname = parsed.netloc.lower()
    # Strip port if present
    if ':' in hostname:
        hostname = hostname.split(':')[0]

    # Check blocked hostnames
    if hostname in BLOCKED_HOSTNAMES:
        return False, "URL hostname is blocked"

    # Check blocked IP ranges
    if _is_ip_blocked(hostname):
        return False, "URL points to a private/internal IP address"

    # Check domain allowlist
    domain_suffix = _get_domain_suffix(hostname)
    if domain_suffix not in allowed_domains and hostname not in allowed_domains:
        return False, f"URL domain '{hostname}' is not in the allowed list"

    return True, ""


def safe_url(
    url: str,
    allowed_domains: Optional[frozenset[str]] = None,
) -> Optional[str]:
    """Validate and return a URL, or None if invalid.

    Convenience wrapper around validate_url() that returns the URL
    if valid, or None if not.

    Args:
        url: The URL to validate.
        allowed_domains: Set of allowed domain suffixes.

    Returns:
        The URL if valid, None otherwise.
    """
    is_valid, _ = validate_url(url, allowed_domains)
    return url if is_valid else None


@contextmanager
def secure_temp_file(
    suffix: str = '',
    prefix: str = 'tmp_',
    mode: str = 'w',
    encoding: str = 'utf-8',
) -> Generator[tuple[Any, Path], None, None]:
    """Create a secure temporary file with automatic cleanup.

    Uses a random filename and restrictive permissions. The file is
    automatically deleted when the context manager exits.

    Args:
        suffix: File suffix (e.g., '.json')
        prefix: File prefix
        mode: File open mode ('w' for text, 'wb' for binary)
        encoding: Text encoding (ignored for binary mode)

    Yields:
        Tuple of (file_handle, Path to file)

    Example:
        >>> with secure_temp_file(suffix='.json') as (f, path):
        ...     json.dump(data, f)
        ...     # File is automatically deleted after this block
    """
    fd = None
    temp_path = None
    try:
        # Create with restrictive permissions (0o600 = owner read/write only)
        fd, temp_path_str = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        temp_path = Path(temp_path_str)

        # Set restrictive permissions explicitly
        os.chmod(temp_path, 0o600)

        # Open the file with the requested mode
        if 'b' in mode:
            f = os.fdopen(fd, mode)
        else:
            f = os.fdopen(fd, mode, encoding=encoding)
        fd = None  # os.fdopen takes ownership of the fd

        try:
            yield f, temp_path
        finally:
            if not f.closed:
                f.close()
    finally:
        # Clean up the file descriptor if it wasn't consumed
        if fd is not None:
            os.close(fd)
        # Always try to delete the temp file
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass  # Best effort cleanup


@contextmanager
def secure_temp_directory(
    prefix: str = 'tmp_',
) -> Generator[Path, None, None]:
    """Create a secure temporary directory with automatic cleanup.

    Args:
        prefix: Directory name prefix

    Yields:
        Path to the temporary directory

    Example:
        >>> with secure_temp_directory() as temp_dir:
        ...     temp_file = temp_dir / "data.json"
        ...     # Directory and contents deleted after this block
    """
    temp_dir = None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
        # Set restrictive permissions
        os.chmod(temp_dir, 0o700)
        yield temp_dir
    finally:
        if temp_dir is not None and temp_dir.exists():
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except OSError:
                pass  # Best effort cleanup


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize a filename to prevent path traversal attacks.

    Removes directory separators and other dangerous characters.

    Args:
        filename: The filename to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized filename
    """
    # Remove path separators and null bytes
    sanitized = filename.replace('/', '_').replace('\\', '_').replace('\x00', '')
    # Remove leading dots (hidden files, parent directory)
    sanitized = sanitized.lstrip('.')
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    # Ensure we have something
    return sanitized or 'unnamed'


class PathValidationError(Exception):
    """Raised when path validation fails."""
    pass


def safe_path(
    user_path: str,
    allowed_base: Optional[Path] = None,
    must_exist: bool = False,
    allow_creation: bool = True,
) -> Path:
    """Validate and resolve a user-provided path safely.

    Protects against path traversal attacks by:
    - Rejecting paths with null bytes
    - Resolving to absolute path
    - Optionally ensuring path stays within allowed_base directory
    - Optionally checking existence

    Args:
        user_path: The user-provided path string to validate.
        allowed_base: If provided, the resolved path must be within this directory.
                     Use this to prevent path traversal outside allowed directories.
        must_exist: If True, raises error if path doesn't exist.
        allow_creation: If True, allows paths that don't exist yet (for file creation).

    Returns:
        Resolved, validated Path object.

    Raises:
        PathValidationError: If the path is invalid or violates security constraints.

    Example:
        >>> safe_path("/tmp/data.json")
        PosixPath('/tmp/data.json')
        >>> safe_path("../../../etc/passwd", allowed_base=Path("/app"))
        PathValidationError: Path escapes allowed directory
    """
    if not user_path or not isinstance(user_path, str):
        raise PathValidationError("Path must be a non-empty string")

    # Check for null bytes (can bypass security checks in some systems)
    if '\x00' in user_path:
        raise PathValidationError("Path contains null bytes")

    # Check for obviously malicious patterns before resolution
    # These checks are redundant with the allowed_base check but provide defense in depth
    normalized = user_path.replace('\\', '/')
    if '/..' in normalized or '../' in normalized or normalized.startswith('..'):
        # Only raise if no allowed_base is set (if allowed_base is set, we'll check containment)
        if allowed_base is None:
            raise PathValidationError("Path contains traversal sequences")

    try:
        # Convert to Path and resolve to absolute
        path = Path(user_path).expanduser()

        # For existence checks, resolve symlinks
        if must_exist:
            path = path.resolve(strict=True)
        else:
            path = path.resolve(strict=False)

    except OSError as e:
        raise PathValidationError(f"Invalid path: {e}")

    # Check if path is within allowed base directory
    if allowed_base is not None:
        try:
            allowed_base_resolved = allowed_base.resolve(strict=False)
            # Use is_relative_to for Python 3.9+, or check manually
            try:
                path.relative_to(allowed_base_resolved)
            except ValueError:
                raise PathValidationError(
                    f"Path must be within {allowed_base_resolved}"
                )
        except OSError as e:
            raise PathValidationError(f"Invalid base path: {e}")

    # Check existence if required
    if must_exist and not path.exists():
        raise PathValidationError(f"Path does not exist: {path}")

    # If not allowing creation, path or parent must exist
    if not allow_creation and not path.exists() and not path.parent.exists():
        raise PathValidationError(f"Parent directory does not exist: {path.parent}")

    return path


def validate_repo_path(repo_path: str) -> tuple[bool, str, Optional[Path]]:
    """Validate a repository path for the catalog builder.

    Checks that the path:
    - Is a valid, safe path
    - Exists and is a directory
    - Contains expected repository structure (docs folder)

    Args:
        repo_path: User-provided path to validate.

    Returns:
        Tuple of (is_valid, message, resolved_path or None).

    Example:
        >>> validate_repo_path("/path/to/architecture-center")
        (True, "Valid repository", PosixPath('/path/to/architecture-center'))
    """
    if not repo_path:
        return False, "Repository path is required", None

    try:
        path = safe_path(repo_path, must_exist=True)
    except PathValidationError as e:
        return False, str(e), None

    if not path.is_dir():
        return False, "Path is not a directory", None

    # Check for expected structure
    docs_path = path / 'docs'
    if not docs_path.exists():
        return False, "Repository missing 'docs' folder - is this the Azure Architecture Center?", None

    return True, "Valid repository", path


def validate_output_path(output_path: str, base_dir: Optional[Path] = None) -> tuple[bool, str, Optional[Path]]:
    """Validate an output file path for writing.

    Checks that the path:
    - Is a valid, safe path
    - Parent directory exists or can be created
    - Optionally stays within base_dir

    Args:
        output_path: User-provided output path to validate.
        base_dir: Optional base directory to restrict output to.

    Returns:
        Tuple of (is_valid, message, resolved_path or None).

    Example:
        >>> validate_output_path("./output/catalog.json")
        (True, "Valid output path", PosixPath('/current/dir/output/catalog.json'))
    """
    if not output_path:
        return False, "Output path is required", None

    try:
        path = safe_path(output_path, allowed_base=base_dir, allow_creation=True)
    except PathValidationError as e:
        return False, str(e), None

    # Ensure parent directory exists
    if not path.parent.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, f"Cannot create parent directory: {e}", None

    return True, "Valid output path", path
