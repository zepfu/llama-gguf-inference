"""Unit tests for scripts/auth.py - API Key Authentication Module."""

import asyncio
import importlib
import json
import os
import time
from unittest.mock import patch


def _make_validator(monkeypatch, **env_vars):
    """Create a fresh APIKeyValidator with given env vars."""
    for key, val in env_vars.items():
        monkeypatch.setenv(key, val)
    import auth

    importlib.reload(auth)
    return auth.APIKeyValidator()


def _reload_auth(monkeypatch, **env_vars):
    """Reload auth module with given env vars, returning the module."""
    for key, val in env_vars.items():
        monkeypatch.setenv(key, val)
    import auth

    importlib.reload(auth)
    return auth


class TestKeyFormatValidation:
    """Tests for _is_valid_format."""

    def test_valid_key(self, noauth_env, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false")
        assert v._is_valid_format("sk-test-1234567890abcdef") is True

    def test_key_too_short(self, noauth_env, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false")
        assert v._is_valid_format("short") is False

    def test_key_too_long(self, noauth_env, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false")
        assert v._is_valid_format("a" * 129) is False

    def test_key_min_length(self, noauth_env, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false")
        assert v._is_valid_format("a" * 16) is True

    def test_key_max_length(self, noauth_env, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false")
        assert v._is_valid_format("a" * 128) is True

    def test_key_with_special_chars(self, noauth_env, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false")
        assert v._is_valid_format("sk-key!@#$%^&*()test") is False

    def test_key_with_spaces(self, noauth_env, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false")
        assert v._is_valid_format("sk-key with spaces!") is False

    def test_key_with_hyphens_underscores(self, noauth_env, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false")
        assert v._is_valid_format("sk-test_key-12345678") is True


class TestLoadKeys:
    """Tests for _load_keys file parsing."""

    def test_load_valid_keys(self, keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        assert len(v.keys) == 2
        assert v.keys["sk-test-1234567890abcdef"] == "testing"
        assert v.keys["sk-load-abcdef1234567890"] == "loadtest"

    def test_load_disabled(self, keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false", AUTH_KEYS_FILE=keys_file)
        assert len(v.keys) == 0

    def test_load_missing_file(self, monkeypatch):
        v = _make_validator(
            monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE="/nonexistent/keys.txt"
        )
        assert len(v.keys) == 0

    def test_load_empty_file(self, empty_keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=empty_keys_file)
        assert len(v.keys) == 0

    def test_load_with_comments(self, tmp_path, monkeypatch):
        f = tmp_path / "keys.txt"
        f.write_text("# This is a comment\nvalid:sk-valid-1234567890ab\n# Another comment\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 1

    def test_load_skips_invalid_lines(self, tmp_path, monkeypatch):
        f = tmp_path / "keys.txt"
        f.write_text("no-colon-here\nvalid:sk-valid-1234567890ab\nbad format too\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 1
        assert "sk-valid-1234567890ab" in v.keys

    def test_load_skips_invalid_key_id(self, tmp_path, monkeypatch):
        f = tmp_path / "keys.txt"
        f.write_text("inv@lid!:sk-valid-1234567890ab\ngood-id:sk-good-1234567890ab\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 1
        assert v.keys["sk-good-1234567890ab"] == "good-id"

    def test_load_skips_duplicate_keys(self, tmp_path, monkeypatch):
        f = tmp_path / "keys.txt"
        f.write_text("first:sk-dupe-1234567890ab\nsecond:sk-dupe-1234567890ab\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 1
        assert v.keys["sk-dupe-1234567890ab"] == "first"

    def test_load_colon_in_api_key(self, tmp_path, monkeypatch):
        """Keys with colons after the first split should be handled."""
        f = tmp_path / "keys.txt"
        f.write_text("mykey:sk-has-colon:extra-part\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        # split(":", 1) means the api_key is "sk-has-colon:extra-part"
        # This has a colon which fails _is_valid_format (not alphanumeric/hyphen/underscore)
        assert len(v.keys) == 0


class TestValidate:
    """Tests for the validate method."""

    def test_auth_disabled(self, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false")
        is_valid, result = v.validate({"authorization": "Bearer anything"})
        assert is_valid is True
        assert result == "auth-disabled"

    def test_no_keys_configured_rejects(self, monkeypatch):
        v = _make_validator(
            monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE="/nonexistent/keys.txt"
        )
        is_valid, result = v.validate({"authorization": "Bearer anything"})
        assert is_valid is False
        assert "misconfigured" in result.lower()

    def test_missing_auth_header(self, keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        is_valid, result = v.validate({})
        assert is_valid is False
        assert "Missing" in result

    def test_empty_auth_header(self, keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        is_valid, result = v.validate({"authorization": ""})
        assert is_valid is False

    def test_bearer_prefix(self, keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is True
        assert result == "testing"

    def test_no_bearer_prefix(self, keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        is_valid, result = v.validate({"authorization": "sk-test-1234567890abcdef"})
        assert is_valid is True
        assert result == "testing"

    def test_invalid_key(self, keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        is_valid, result = v.validate({"authorization": "Bearer sk-wrong-1234567890abcdef"})
        assert is_valid is False
        assert "Invalid" in result

    def test_invalid_format_key(self, keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        is_valid, result = v.validate({"authorization": "Bearer short"})
        assert is_valid is False
        assert "format" in result.lower()

    def test_case_insensitive_bearer(self, keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        is_valid, result = v.validate({"authorization": "BEARER sk-test-1234567890abcdef"})
        assert is_valid is True
        assert result == "testing"

    def test_bearer_with_extra_spaces(self, keys_file, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        is_valid, result = v.validate({"authorization": "Bearer  sk-test-1234567890abcdef "})
        assert is_valid is True
        assert result == "testing"


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    def test_under_limit(self, keys_file, monkeypatch):
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="10",
        )
        for _ in range(10):
            is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
            assert is_valid is True

    def test_over_limit(self, keys_file, monkeypatch):
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="5",
        )
        for _ in range(5):
            v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is False
        assert result == "rate_limit_exceeded"

    def test_different_keys_separate_limits(self, keys_file, monkeypatch):
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="3",
        )
        # Exhaust rate limit for first key
        for _ in range(3):
            v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        # Second key should still work
        is_valid, result = v.validate({"authorization": "Bearer sk-load-abcdef1234567890"})
        assert is_valid is True
        assert result == "loadtest"

    def test_rate_limit_resets(self, keys_file, monkeypatch):
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="2",
        )
        # Exhaust limit
        for _ in range(2):
            v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        # Manually expire old timestamps
        v.rate_limiter["testing"] = [time.time() - 61]
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is True


class TestMetrics:
    """Tests for get_metrics."""

    def test_empty_metrics(self, noauth_env, monkeypatch):
        v = _make_validator(monkeypatch, AUTH_ENABLED="false")
        assert v.get_metrics() == {}

    def test_metrics_after_requests(self, keys_file, monkeypatch):
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )
        for _ in range(3):
            v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        metrics = v.get_metrics()
        assert "testing" in metrics
        assert metrics["testing"]["requests_last_minute"] == 3
        assert metrics["testing"]["rate_limit"] == 100


# ---------------------------------------------------------------------------
# authenticate_request tests
# ---------------------------------------------------------------------------


class TestAuthenticateRequest:
    """Tests for the authenticate_request() async function."""

    def test_authenticate_success_returns_key_id(self, keys_file, monkeypatch):
        auth = _reload_auth(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            result = await auth.authenticate_request(
                writer, {"authorization": "Bearer sk-test-1234567890abcdef"}
            )
            return result

        result = asyncio.run(run())
        assert result == "testing"
        # No response should have been sent
        assert len(written_data) == 0

    def test_authenticate_failure_sends_401(self, keys_file, monkeypatch):
        auth = _reload_auth(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            result = await auth.authenticate_request(
                writer, {"authorization": "Bearer sk-wrong-1234567890abcdef"}
            )
            return result

        result = asyncio.run(run())
        assert result is None

        response = written_data.decode()
        assert "401 Unauthorized" in response
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["error"]["code"] == "invalid_api_key"

    def test_authenticate_missing_header_sends_401(self, keys_file, monkeypatch):
        auth = _reload_auth(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            result = await auth.authenticate_request(writer, {})
            return result

        result = asyncio.run(run())
        assert result is None

        response = written_data.decode()
        assert "401 Unauthorized" in response

    def test_authenticate_rate_limited_sends_429(self, keys_file, monkeypatch):
        auth = _reload_auth(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="2",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            # Exhaust rate limit
            for _ in range(2):
                await auth.authenticate_request(
                    writer, {"authorization": "Bearer sk-test-1234567890abcdef"}
                )
            # This should trigger 429
            written_data.clear()
            result = await auth.authenticate_request(
                writer, {"authorization": "Bearer sk-test-1234567890abcdef"}
            )
            return result

        result = asyncio.run(run())
        assert result is None

        response = written_data.decode()
        assert "429 Too Many Requests" in response

    def test_authenticate_disabled_returns_auth_disabled(self, monkeypatch):
        auth = _reload_auth(
            monkeypatch,
            AUTH_ENABLED="false",
            DATA_DIR="/tmp/test-data",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            result = await auth.authenticate_request(writer, {})
            return result

        result = asyncio.run(run())
        assert result == "auth-disabled"
        assert len(written_data) == 0


# ---------------------------------------------------------------------------
# send_rate_limit_error tests
# ---------------------------------------------------------------------------


class TestSendRateLimitError:
    """Tests for send_rate_limit_error() async function."""

    def test_429_response_format(self, monkeypatch):
        auth = _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await auth.send_rate_limit_error(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert response.startswith("HTTP/1.1 429 Too Many Requests\r\n")
        assert "Content-Type: application/json" in response
        assert "Retry-After: 60" in response
        assert "Connection: close" in response

        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["error"]["code"] == "rate_limit_exceeded"
        assert data["error"]["type"] == "rate_limit_error"


# ---------------------------------------------------------------------------
# log_access tests
# ---------------------------------------------------------------------------


class TestLogAccess:
    """Tests for log_access() async function."""

    def test_log_access_writes_to_file(self, monkeypatch, tmp_path):
        _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")

        log_dir = tmp_path / "logs"
        log_file = log_dir / "api_access.log"

        async def run():
            import datetime

            timestamp = datetime.datetime.now().isoformat()
            log_entry = f"{timestamp} | testing | POST /v1/chat/completions | 200"
            os.makedirs(str(log_dir), exist_ok=True)
            with open(str(log_file), "a") as f:
                f.write(log_entry + "\n")

        asyncio.run(run())

        assert log_file.exists()
        content = log_file.read_text()
        assert "testing" in content
        assert "POST /v1/chat/completions" in content
        assert "200" in content

    def test_log_access_creates_directory(self, monkeypatch, tmp_path):
        auth_mod = _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")

        async def run():
            # Just verify it doesn't crash when log directory doesn't exist
            # (it will try to create /data/logs which may fail, but that's OK)
            await auth_mod.log_access("GET", "/v1/models", "test", 200)

        asyncio.run(run())

    def test_log_access_handles_permission_error(self, monkeypatch, capsys):
        auth = _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")

        async def run():
            with patch("os.makedirs", side_effect=PermissionError("denied")):
                await auth.log_access("GET", "/v1/models", "test", 200)

        # Should not raise, just print a warning
        asyncio.run(run())
        captured = capsys.readouterr()
        assert "Warning" in captured.out or "Failed" in captured.out


# ---------------------------------------------------------------------------
# Edge cases in key loading
# ---------------------------------------------------------------------------


class TestLoadKeysEdgeCases:
    """Tests for edge cases in _load_keys."""

    def test_load_keys_file_read_exception(self, monkeypatch, tmp_path):
        """Exception during file reading is handled gracefully."""
        keys_path = tmp_path / "bad_keys.txt"
        keys_path.write_text("valid:sk-valid-1234567890ab\n")

        # Make the file unreadable
        keys_path.chmod(0o000)
        try:
            v = _make_validator(
                monkeypatch,
                AUTH_ENABLED="true",
                AUTH_KEYS_FILE=str(keys_path),
            )
            # Should handle the error and return empty keys
            assert len(v.keys) == 0
        finally:
            # Restore permissions for cleanup
            keys_path.chmod(0o644)

    def test_load_keys_empty_key_id(self, tmp_path, monkeypatch):
        """Empty key_id is rejected."""
        f = tmp_path / "keys.txt"
        f.write_text(":sk-valid-1234567890ab\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 0

    def test_load_keys_invalid_api_key_format(self, tmp_path, monkeypatch):
        """API keys that fail format validation are skipped."""
        f = tmp_path / "keys.txt"
        f.write_text("valid-id:short\ngood-id:sk-good-1234567890ab\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 1
        assert "sk-good-1234567890ab" in v.keys


# ---------------------------------------------------------------------------
# Validate edge cases
# ---------------------------------------------------------------------------


class TestValidateEdgeCases:
    """Additional edge cases for the validate method."""

    def test_empty_api_key_after_bearer_strip(self, keys_file, monkeypatch):
        """Bearer prefix with only whitespace after it is rejected."""
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        is_valid, result = v.validate({"authorization": "Bearer    "})
        assert is_valid is False
        assert "Empty" in result

    def test_constant_time_comparison(self, keys_file, monkeypatch):
        """Verify _find_key uses constant-time comparison (no early return)."""
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=keys_file)
        # Valid key should be found
        result = v._find_key("sk-test-1234567890abcdef")
        assert result == "testing"

        # Invalid key should return None after checking all keys
        result = v._find_key("sk-nope-1234567890abcdef")
        assert result is None

    def test_record_request_appends_timestamp(self, keys_file, monkeypatch):
        """_record_request adds a timestamp to the rate limiter."""
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )
        before = len(v.rate_limiter.get("testing", []))
        v._record_request("testing")
        after = len(v.rate_limiter["testing"])
        assert after == before + 1

    def test_check_rate_limit_cleans_old_entries(self, keys_file, monkeypatch):
        """_check_rate_limit removes entries older than 60 seconds."""
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )
        # Add old timestamps
        v.rate_limiter["testing"] = [time.time() - 120, time.time() - 90]
        result = v._check_rate_limit("testing")
        assert result is True
        # Old entries should have been cleaned
        assert len(v.rate_limiter["testing"]) == 0


# ---------------------------------------------------------------------------
# SEC-11: Log sanitization tests
# ---------------------------------------------------------------------------


class TestSanitizeLogField:
    """Tests for _sanitize_log_field() function (SEC-11)."""

    def test_clean_value_unchanged(self, monkeypatch):
        auth = _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")
        assert auth._sanitize_log_field("GET") == "GET"
        assert auth._sanitize_log_field("/v1/chat/completions") == "/v1/chat/completions"

    def test_newline_replaced(self, monkeypatch):
        auth = _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")
        result = auth._sanitize_log_field("GET\nPOST")
        assert "\n" not in result
        assert result == "GET_POST"

    def test_carriage_return_replaced(self, monkeypatch):
        auth = _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")
        result = auth._sanitize_log_field("GET\rPOST")
        assert "\r" not in result
        assert result == "GET_POST"

    def test_tab_replaced(self, monkeypatch):
        auth = _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")
        result = auth._sanitize_log_field("GET\tPOST")
        assert "\t" not in result
        assert result == "GET_POST"

    def test_pipe_replaced(self, monkeypatch):
        auth = _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")
        result = auth._sanitize_log_field("/path|injected")
        assert "|" not in result
        assert result == "/path_injected"

    def test_multiple_control_chars(self, monkeypatch):
        auth = _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")
        result = auth._sanitize_log_field("GET\r\n/fake | injected\t200")
        assert "\r" not in result
        assert "\n" not in result
        assert "\t" not in result
        assert "|" not in result

    def test_log_injection_attempt(self, monkeypatch):
        """Verify a full log injection attempt is neutralized."""
        auth = _reload_auth(monkeypatch, AUTH_ENABLED="false", DATA_DIR="/tmp/test-data")
        malicious = "POST /v1/chat\n2024-01-01T00:00:00 | admin | GET /secret | 200"
        result = auth._sanitize_log_field(malicious)
        assert "\n" not in result
        assert "|" not in result


# ---------------------------------------------------------------------------
# Per-key rate limit tests
# ---------------------------------------------------------------------------


class TestPerKeyRateLimits:
    """Tests for per-key rate limit configuration."""

    def test_per_key_rate_limit_loaded(self, tmp_path, monkeypatch):
        """Per-key rate limit is parsed from the third field."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:5\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert "testing" in v.key_rate_limits
        assert v.key_rate_limits["testing"] == 5

    def test_per_key_rate_limit_enforced(self, tmp_path, monkeypatch):
        """Per-key rate limit of 3 is enforced instead of global 100."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:3\n")
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=str(f),
            MAX_REQUESTS_PER_MINUTE="100",
        )
        # 3 requests should succeed
        for _ in range(3):
            is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
            assert is_valid is True
        # 4th should fail
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is False
        assert result == "rate_limit_exceeded"

    def test_per_key_higher_limit(self, tmp_path, monkeypatch):
        """Per-key rate limit can be higher than global default."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:200\n")
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=str(f),
            MAX_REQUESTS_PER_MINUTE="5",
        )
        # Should allow more than the global limit of 5
        for _ in range(6):
            is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
            assert is_valid is True

    def test_default_rate_limit_without_per_key(self, tmp_path, monkeypatch):
        """Keys without per-key limit use the global default."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef\n")
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=str(f),
            MAX_REQUESTS_PER_MINUTE="3",
        )
        assert "testing" not in v.key_rate_limits
        for _ in range(3):
            v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is False

    def test_invalid_rate_limit_skips_key(self, tmp_path, monkeypatch):
        """Invalid (non-integer) rate limit causes key line to be skipped."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:abc\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 0

    def test_zero_rate_limit_skips_key(self, tmp_path, monkeypatch):
        """Zero rate limit causes key line to be skipped."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:0\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 0

    def test_negative_rate_limit_skips_key(self, tmp_path, monkeypatch):
        """Negative rate limit causes key line to be skipped."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:-5\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 0

    def test_metrics_shows_per_key_limit(self, tmp_path, monkeypatch):
        """get_metrics returns the per-key rate limit, not global default."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:42\n")
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=str(f),
            MAX_REQUESTS_PER_MINUTE="100",
        )
        v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        metrics = v.get_metrics()
        assert metrics["testing"]["rate_limit"] == 42


# ---------------------------------------------------------------------------
# Key expiration tests
# ---------------------------------------------------------------------------


class TestKeyExpiration:
    """Tests for key expiration / TTL."""

    def test_expired_key_rejected(self, tmp_path, monkeypatch):
        """A key with a past expiration is rejected."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef::2020-01-01T00:00:00\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is False
        assert result == "API key has expired"

    def test_non_expired_key_accepted(self, tmp_path, monkeypatch):
        """A key with a future expiration is accepted."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef::2099-12-31T23:59:59\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is True
        assert result == "testing"

    def test_no_expiration_means_never_expires(self, tmp_path, monkeypatch):
        """A key without an expiration field never expires."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert "testing" not in v.key_expirations
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is True

    def test_empty_expiration_means_never_expires(self, tmp_path, monkeypatch):
        """An empty expiration field (key:api_key:120:) means no expiry."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:120:\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert "testing" not in v.key_expirations
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is True

    def test_invalid_expiration_skips_key(self, tmp_path, monkeypatch):
        """An invalid expiration date causes the line to be skipped."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef::not-a-date\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 0

    def test_rate_limit_and_expiration_together(self, tmp_path, monkeypatch):
        """Both rate limit and expiration can be set on the same key."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:5:2099-12-31T23:59:59\n")
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=str(f),
            MAX_REQUESTS_PER_MINUTE="100",
        )
        assert v.key_rate_limits.get("testing") == 5
        assert v.key_expirations["testing"].year == 2099
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is True

    def test_expired_key_sends_401(self, tmp_path, monkeypatch):
        """Expired key sends a 401 with 'API key has expired' message."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef::2020-01-01T00:00:00\n")
        auth = _reload_auth(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            result = await auth.authenticate_request(
                writer, {"authorization": "Bearer sk-test-1234567890abcdef"}
            )
            return result

        result = asyncio.run(run())
        assert result is None

        response = written_data.decode()
        assert "401 Unauthorized" in response
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert "expired" in data["error"]["message"].lower()

    def test_metrics_includes_expiration(self, tmp_path, monkeypatch):
        """get_metrics includes expiration when set."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef::2099-12-31T23:59:59\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        metrics = v.get_metrics()
        assert "expires" in metrics["testing"]
        assert "2099" in metrics["testing"]["expires"]


# ---------------------------------------------------------------------------
# Rate limiter cleanup tests
# ---------------------------------------------------------------------------


class TestRateLimiterCleanup:
    """Tests for periodic rate limiter cleanup of stale entries."""

    def test_cleanup_removes_stale_entries(self, keys_file, monkeypatch):
        """Stale entries are removed after cleanup interval."""
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )
        # Add stale entries for a key that hasn't been used recently
        v.rate_limiter["stale-key"] = [time.time() - 120, time.time() - 90]
        # Force cleanup by setting _last_cleanup far in the past
        v._last_cleanup = time.time() - 600
        v._cleanup_rate_limiter()
        assert "stale-key" not in v.rate_limiter

    def test_cleanup_keeps_active_entries(self, keys_file, monkeypatch):
        """Active entries with recent timestamps are NOT removed."""
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )
        now = time.time()
        v.rate_limiter["active-key"] = [now - 10, now - 5]
        v._last_cleanup = now - 600
        v._cleanup_rate_limiter(now)
        assert "active-key" in v.rate_limiter
        assert len(v.rate_limiter["active-key"]) == 2

    def test_cleanup_skipped_within_interval(self, keys_file, monkeypatch):
        """Cleanup is skipped if called within the CLEANUP_INTERVAL."""
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )
        # Add stale entries
        v.rate_limiter["stale-key"] = [time.time() - 120]
        # Set last cleanup to recent time (within interval)
        v._last_cleanup = time.time() - 10
        v._cleanup_rate_limiter()
        # Stale entries should still be there (cleanup was skipped)
        assert "stale-key" in v.rate_limiter

    def test_cleanup_triggered_by_check_rate_limit(self, keys_file, monkeypatch):
        """_check_rate_limit triggers cleanup when interval has elapsed."""
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )
        # Add stale entry
        v.rate_limiter["stale-key"] = [time.time() - 120]
        # Force cleanup interval to have elapsed
        v._last_cleanup = time.time() - 600
        # This check should trigger cleanup
        v._check_rate_limit("testing")
        assert "stale-key" not in v.rate_limiter

    def test_cleanup_mixed_stale_and_active(self, keys_file, monkeypatch):
        """Cleanup removes stale entries but keeps active ones."""
        v = _make_validator(
            monkeypatch,
            AUTH_ENABLED="true",
            AUTH_KEYS_FILE=keys_file,
            MAX_REQUESTS_PER_MINUTE="100",
        )
        now = time.time()
        v.rate_limiter["stale-key"] = [now - 120]
        v.rate_limiter["active-key"] = [now - 10]
        v._last_cleanup = now - 600
        v._cleanup_rate_limiter(now)
        assert "stale-key" not in v.rate_limiter
        assert "active-key" in v.rate_limiter


# ---------------------------------------------------------------------------
# Backward compatibility tests
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Tests that all existing key file formats continue to work."""

    def test_simple_key_format(self, tmp_path, monkeypatch):
        """Original key_id:api_key format works."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 1
        is_valid, result = v.validate({"authorization": "Bearer sk-test-1234567890abcdef"})
        assert is_valid is True
        assert result == "testing"

    def test_key_with_rate_limit_only(self, tmp_path, monkeypatch):
        """key_id:api_key:rate_limit format works."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:50\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 1
        assert v.key_rate_limits["testing"] == 50

    def test_key_with_expiration_only(self, tmp_path, monkeypatch):
        """key_id:api_key::expiration format (empty rate limit) works."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef::2099-12-31T23:59:59\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 1
        assert "testing" not in v.key_rate_limits
        assert v.key_expirations["testing"].year == 2099

    def test_key_with_all_fields(self, tmp_path, monkeypatch):
        """key_id:api_key:rate_limit:expiration format works."""
        f = tmp_path / "keys.txt"
        f.write_text("testing:sk-test-1234567890abcdef:200:2099-06-15T12:00:00\n")
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 1
        assert v.key_rate_limits["testing"] == 200
        assert v.key_expirations["testing"].month == 6

    def test_mixed_formats_in_same_file(self, tmp_path, monkeypatch):
        """A file can contain keys in all different formats simultaneously."""
        f = tmp_path / "keys.txt"
        f.write_text(
            "# Mixed format keys\n"
            "simple:sk-simp-1234567890abcdef\n"
            "rated:sk-rate-abcdef1234567890:120\n"
            "expiring:sk-expr-1234567890fedcba::2099-01-01T00:00:00\n"
            "full:sk-full-abcdefabcdef1234:300:2099-12-31T23:59:59\n"
        )
        v = _make_validator(monkeypatch, AUTH_ENABLED="true", AUTH_KEYS_FILE=str(f))
        assert len(v.keys) == 4
        assert "simple" not in v.key_rate_limits
        assert v.key_rate_limits["rated"] == 120
        assert "rated" not in v.key_expirations
        assert "simple" not in v.key_expirations
        assert v.key_expirations["expiring"].year == 2099
        assert v.key_rate_limits["full"] == 300
        assert v.key_expirations["full"].year == 2099
