"""Tests for the security sanitization utilities."""

import os
import tempfile
from pathlib import Path

import pytest

from architecture_recommendations_app.utils.sanitize import (
    safe_html,
    safe_html_attr,
    validate_url,
    safe_url,
    secure_temp_file,
    secure_temp_directory,
    sanitize_filename,
    ALLOWED_URL_DOMAINS,
    BLOCKED_IP_RANGES,
    BLOCKED_HOSTNAMES,
)


class TestSafeHtml:
    """Tests for HTML escaping functions."""

    def test_safe_html_escapes_script_tags(self):
        """Test that script tags are escaped."""
        malicious = "<script>alert('xss')</script>"
        result = safe_html(malicious)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_safe_html_escapes_img_onerror(self):
        """Test that img onerror payloads are escaped."""
        malicious = '<img src=x onerror="alert(1)">'
        result = safe_html(malicious)
        assert "onerror" not in result or "&quot;" in result
        assert "<img" not in result

    def test_safe_html_escapes_quotes(self):
        """Test that quotes are escaped."""
        malicious = '"><script>alert(1)</script>'
        result = safe_html(malicious)
        assert "&quot;" in result
        assert '"><script>' not in result

    def test_safe_html_preserves_normal_text(self):
        """Test that normal text is preserved."""
        normal = "Hello World 123"
        result = safe_html(normal)
        assert result == normal

    def test_safe_html_handles_unicode(self):
        """Test that unicode is handled correctly."""
        unicode_text = "Hello \u4e16\u754c"  # Hello World in Chinese
        result = safe_html(unicode_text)
        assert result == unicode_text

    def test_safe_html_handles_none(self):
        """Test that None is converted to string."""
        result = safe_html(None)
        assert result == "None"

    def test_safe_html_handles_numbers(self):
        """Test that numbers are converted to string."""
        result = safe_html(42)
        assert result == "42"

    def test_safe_html_attr_escapes_quotes(self):
        """Test that attribute values have quotes escaped."""
        malicious = '" onclick="alert(1)'
        result = safe_html_attr(malicious)
        assert '"' not in result or "&quot;" in result


class TestValidateUrl:
    """Tests for URL validation (SSRF protection)."""

    def test_valid_microsoft_url(self):
        """Test that Microsoft URLs are allowed."""
        url = "https://learn.microsoft.com/azure/architecture/example"
        is_valid, error = validate_url(url)
        assert is_valid is True
        assert error == ""

    def test_valid_azure_url(self):
        """Test that Azure URLs are allowed."""
        url = "https://docs.azure.com/image.png"
        is_valid, error = validate_url(url)
        assert is_valid is True

    def test_valid_github_url(self):
        """Test that GitHub URLs are allowed."""
        url = "https://raw.githubusercontent.com/user/repo/main/image.png"
        is_valid, error = validate_url(url)
        assert is_valid is True

    def test_blocks_http_by_default(self):
        """Test that HTTP is blocked by default."""
        url = "http://learn.microsoft.com/image.png"
        is_valid, error = validate_url(url)
        assert is_valid is False
        assert "HTTPS" in error

    def test_allows_http_when_enabled(self):
        """Test that HTTP can be allowed explicitly."""
        url = "http://learn.microsoft.com/image.png"
        is_valid, error = validate_url(url, allow_http=True)
        assert is_valid is True

    def test_blocks_aws_metadata_endpoint(self):
        """Test that AWS metadata endpoint is blocked."""
        url = "http://169.254.169.254/latest/meta-data/"
        is_valid, error = validate_url(url, allow_http=True)
        assert is_valid is False
        assert "blocked" in error.lower() or "private" in error.lower()

    def test_blocks_localhost(self):
        """Test that localhost is blocked."""
        url = "http://localhost/admin"
        is_valid, error = validate_url(url, allow_http=True)
        assert is_valid is False

    def test_blocks_127_0_0_1(self):
        """Test that 127.0.0.1 is blocked."""
        url = "http://127.0.0.1:8080/secret"
        is_valid, error = validate_url(url, allow_http=True)
        assert is_valid is False

    def test_blocks_private_ip_10(self):
        """Test that 10.x.x.x range is blocked."""
        url = "http://10.0.0.1/internal"
        is_valid, error = validate_url(url, allow_http=True)
        assert is_valid is False

    def test_blocks_private_ip_172(self):
        """Test that 172.16.x.x range is blocked."""
        url = "http://172.16.0.1/internal"
        is_valid, error = validate_url(url, allow_http=True)
        assert is_valid is False

    def test_blocks_private_ip_192(self):
        """Test that 192.168.x.x range is blocked."""
        url = "http://192.168.1.1/router"
        is_valid, error = validate_url(url, allow_http=True)
        assert is_valid is False

    def test_blocks_unknown_domain(self):
        """Test that unknown domains are blocked."""
        url = "https://evil.com/malware.exe"
        is_valid, error = validate_url(url)
        assert is_valid is False
        assert "not in the allowed list" in error.lower()

    def test_blocks_file_protocol(self):
        """Test that file:// protocol is blocked."""
        url = "file:///etc/passwd"
        is_valid, error = validate_url(url)
        assert is_valid is False

    def test_handles_invalid_url(self):
        """Test that invalid URLs are rejected."""
        url = "not-a-valid-url"
        is_valid, error = validate_url(url)
        assert is_valid is False

    def test_handles_empty_url(self):
        """Test that empty URLs are rejected."""
        url = ""
        is_valid, error = validate_url(url)
        assert is_valid is False

    def test_safe_url_returns_url_if_valid(self):
        """Test that safe_url returns URL when valid."""
        url = "https://learn.microsoft.com/image.png"
        result = safe_url(url)
        assert result == url

    def test_safe_url_returns_none_if_invalid(self):
        """Test that safe_url returns None when invalid."""
        url = "http://evil.com/malware"
        result = safe_url(url)
        assert result is None


class TestSecureTempFile:
    """Tests for secure temporary file handling."""

    def test_creates_temp_file(self):
        """Test that temp file is created."""
        with secure_temp_file(suffix='.json') as (f, path):
            assert path.exists()
            f.write('{"test": true}')

    def test_temp_file_has_random_name(self):
        """Test that temp file has random name."""
        paths = []
        for _ in range(3):
            with secure_temp_file(suffix='.json') as (f, path):
                paths.append(path.name)
        # All names should be different
        assert len(set(paths)) == 3

    def test_temp_file_is_deleted_after_context(self):
        """Test that temp file is deleted after context manager exits."""
        temp_path = None
        with secure_temp_file(suffix='.json') as (f, path):
            temp_path = path
            f.write('test')
        assert not temp_path.exists()

    def test_temp_file_has_restrictive_permissions(self):
        """Test that temp file has 0600 permissions (owner only)."""
        with secure_temp_file(suffix='.json') as (f, path):
            mode = path.stat().st_mode & 0o777
            assert mode == 0o600

    def test_temp_file_with_custom_prefix(self):
        """Test that custom prefix is used."""
        with secure_temp_file(prefix='test_') as (f, path):
            assert 'test_' in path.name


class TestSecureTempDirectory:
    """Tests for secure temporary directory handling."""

    def test_creates_temp_directory(self):
        """Test that temp directory is created."""
        with secure_temp_directory() as temp_dir:
            assert temp_dir.exists()
            assert temp_dir.is_dir()

    def test_temp_directory_is_deleted_after_context(self):
        """Test that temp directory is deleted after context manager exits."""
        temp_path = None
        with secure_temp_directory() as temp_dir:
            temp_path = temp_dir
            # Create a file inside
            (temp_dir / "test.txt").write_text("test")
        assert not temp_path.exists()

    def test_temp_directory_has_restrictive_permissions(self):
        """Test that temp directory has 0700 permissions."""
        with secure_temp_directory() as temp_dir:
            mode = temp_dir.stat().st_mode & 0o777
            assert mode == 0o700


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_removes_path_separators(self):
        """Test that path separators are removed."""
        result = sanitize_filename("../../../etc/passwd")
        assert "/" not in result
        assert ".." not in result or result.startswith("_")

    def test_removes_backslashes(self):
        """Test that backslashes are removed."""
        result = sanitize_filename("..\\..\\windows\\system32")
        assert "\\" not in result

    def test_removes_null_bytes(self):
        """Test that null bytes are removed."""
        result = sanitize_filename("file\x00.txt")
        assert "\x00" not in result

    def test_removes_leading_dots(self):
        """Test that leading dots are removed."""
        result = sanitize_filename("...hidden")
        assert not result.startswith(".")

    def test_truncates_long_filenames(self):
        """Test that long filenames are truncated."""
        long_name = "a" * 500
        result = sanitize_filename(long_name, max_length=100)
        assert len(result) <= 100

    def test_returns_unnamed_for_empty(self):
        """Test that empty input returns 'unnamed'."""
        result = sanitize_filename("")
        assert result == "unnamed"

    def test_preserves_normal_filename(self):
        """Test that normal filenames are preserved."""
        result = sanitize_filename("document.pdf")
        assert result == "document.pdf"


class TestAllowedDomains:
    """Tests for domain allowlist configuration.

    Note: CodeQL flags domain string checks as incomplete URL sanitization,
    but these are set membership tests, not URL handling.
    """

    def test_microsoft_domains_included(self):
        """Test that Microsoft domains are in allowlist."""
        assert "microsoft.com" in ALLOWED_URL_DOMAINS  # codeql[py/incomplete-url-substring-sanitization]
        assert "azure.com" in ALLOWED_URL_DOMAINS  # codeql[py/incomplete-url-substring-sanitization]

    def test_github_domains_included(self):
        """Test that GitHub domains are in allowlist."""
        assert "github.com" in ALLOWED_URL_DOMAINS  # codeql[py/incomplete-url-substring-sanitization]
        assert "githubusercontent.com" in ALLOWED_URL_DOMAINS  # codeql[py/incomplete-url-substring-sanitization]


class TestBlockedEndpoints:
    """Tests for blocked endpoint configuration."""

    def test_metadata_endpoint_blocked(self):
        """Test that cloud metadata endpoints are blocked."""
        assert "169.254.169.254" in BLOCKED_HOSTNAMES

    def test_private_ranges_configured(self):
        """Test that private IP ranges are configured."""
        # Check that we have RFC 1918 ranges
        range_strs = [str(r) for r in BLOCKED_IP_RANGES]
        assert any("10.0.0.0" in r for r in range_strs)
        assert any("172.16.0.0" in r for r in range_strs)
        assert any("192.168.0.0" in r for r in range_strs)
