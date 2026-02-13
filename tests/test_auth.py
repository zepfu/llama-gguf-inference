"""Unit tests for scripts/auth.py - API Key Authentication Module."""

import importlib
import time


def _make_validator(monkeypatch, **env_vars):
    """Create a fresh APIKeyValidator with given env vars."""
    for key, val in env_vars.items():
        monkeypatch.setenv(key, val)
    import auth

    importlib.reload(auth)
    return auth.APIKeyValidator()


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
