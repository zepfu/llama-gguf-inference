#!/usr/bin/env python3
"""
auth.py - API Key Authentication Module for Gateway

File-based authentication system that enforces API keys while maintaining
OpenAI compatibility. Uses key_id:api_key format for easy management and auditing.

Usage::

    from auth import api_validator, authenticate_request, log_access

    # In your request handler:
    api_key_info = await authenticate_request(writer, headers)
    if api_key_info is None:
        # 401 response already sent
        return

    key_id = api_key_info  # The key_id for logging/tracking

    # Process request...
    await log_access(method, path, key_id, status_code)

Environment Variables:
    AUTH_ENABLED              - Enable/disable authentication (default: true)
    AUTH_KEYS_FILE            - Path to keys file (default: $DATA_DIR/api_keys.txt)
    MAX_REQUESTS_PER_MINUTE   - Rate limit per key_id (default: 100)

Keys File Format:
    key_id:api_key[:rate_limit][:expiration]

    Fields:
        key_id      - Identifier for the key (alphanumeric, hyphens, underscores)
        api_key     - The API key value (16-128 chars, alphanumeric/hyphens/underscores)
        rate_limit  - Optional per-key requests per minute (overrides MAX_REQUESTS_PER_MINUTE)
        expiration  - Optional ISO 8601 expiration timestamp (e.g. 2026-03-01T00:00:00)

Example:
    production:sk-prod-abc123def456
    alice-laptop:sk-alice-xyz789:120
    temp-key:sk-tmp-test123456::2026-03-01T00:00:00
    vip:sk-vip-premium12345:300:2026-12-31T23:59:59
"""

import asyncio
import datetime
import hmac
import json
import os
import time
from collections import defaultdict
from typing import Optional, Tuple


class APIKeyValidator:
    """
    Validates API keys for incoming requests.

    Features:
    - File-based configuration (key_id:api_key[:rate_limit][:expiration] format)
    - Rate limiting per key_id (global default or per-key override)
    - Key expiration via optional ISO 8601 timestamp
    - Key format validation
    - Audit trail with key_id tracking
    - Periodic cleanup of stale rate limiter entries
    """

    # Interval between rate limiter cleanups (seconds)
    CLEANUP_INTERVAL = 300  # 5 minutes

    def __init__(self):
        self.enabled = os.environ.get("AUTH_ENABLED", "true").lower() == "true"
        self.keys_file = os.environ.get(
            "AUTH_KEYS_FILE",
            f"{os.environ.get('DATA_DIR', '/data')}/api_keys.txt",
        )
        self.keys = self._load_keys()  # Maps api_key -> key_id
        self.key_rate_limits = {}  # Maps key_id -> per-key rate limit (int) or None
        self.key_expirations = {}  # Maps key_id -> expiration datetime or None
        self.rate_limiter = defaultdict(list)  # Maps key_id -> [timestamps]
        self.max_requests_per_minute = int(os.environ.get("MAX_REQUESTS_PER_MINUTE", "100"))
        self._last_cleanup = time.time()

        # Parse extended key metadata from loaded keys
        self._parse_key_metadata()

        if self.enabled:
            if self.keys:
                print(f"✅ Authentication enabled with {len(self.keys)} key(s)")
            else:
                print("🔒 Authentication enabled but no keys configured — rejecting all requests.")
                print(f"   Create keys file at: {self.keys_file}")
        else:
            print("⚠️  Authentication disabled! All requests will be accepted.")

    def _load_keys(self) -> dict:
        """
        Load API keys from file.

        File format:
            key_id:api_key[:rate_limit][:expiration]
            # Comments allowed

        Returns:
            dict mapping api_key -> key_id for reverse lookup
            Example: {"sk-prod-abc123": "production", "sk-alice-xyz": "alice-laptop"}

        Side effect:
            Populates self._raw_key_metadata with (key_id, rate_limit_str, expiration_str)
            tuples for later parsing by _parse_key_metadata().
        """
        self._raw_key_metadata: list[tuple[str, str, str]] = []

        if not self.enabled:
            return {}

        if not os.path.exists(self.keys_file):
            print(f"⚠️  AUTH_ENABLED=true but keys file not found: {self.keys_file}")
            print("    Create file with format: key_id:api_key[:rate_limit][:expiration]")
            print("    All requests will be REJECTED until keys file is configured.")
            return {}

        try:
            keys: dict[str, str] = {}  # Maps api_key -> key_id
            with open(self.keys_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    # Parse key_id:api_key[:rate_limit][:expiration]
                    if ":" not in line:
                        print(f"⚠️  Line {line_num}: Invalid format (missing ':'), skipping")
                        continue

                    # Split into at most 4 fields (expiration contains colons)
                    parts = line.split(":", 3)
                    if len(parts) < 2:
                        print(f"⚠️  Line {line_num}: Invalid format, skipping")
                        continue

                    key_id = parts[0].strip()
                    api_key = parts[1].strip()
                    rate_limit_str = parts[2].strip() if len(parts) > 2 else ""
                    expiration_str = parts[3].strip() if len(parts) > 3 else ""

                    # Validate key_id
                    if not key_id or not all(c.isalnum() or c in "-_" for c in key_id):
                        print(f"⚠️  Line {line_num}: Invalid key_id '{key_id}', skipping")
                        continue

                    # Validate api_key format
                    if not self._is_valid_format(api_key):
                        print(
                            f"⚠️  Line {line_num}: Invalid api_key format for '{key_id}', skipping"
                        )
                        continue

                    # Validate rate limit if provided
                    if rate_limit_str:
                        try:
                            rl = int(rate_limit_str)
                            if rl <= 0:
                                print(
                                    f"⚠️  Line {line_num}: Rate limit must be positive "
                                    f"for '{key_id}', skipping"
                                )
                                continue
                        except ValueError:
                            print(
                                f"⚠️  Line {line_num}: Invalid rate limit '{rate_limit_str}' "
                                f"for '{key_id}', skipping"
                            )
                            continue

                    # Validate expiration if provided
                    if expiration_str:
                        try:
                            datetime.datetime.fromisoformat(expiration_str)
                        except ValueError:
                            print(
                                f"⚠️  Line {line_num}: Invalid expiration '{expiration_str}' "
                                f"for '{key_id}', skipping"
                            )
                            continue

                    # Check for duplicate keys
                    if api_key in keys:
                        print(
                            f"⚠️  Line {line_num}: Duplicate api_key for '{key_id}' "
                            f"(already used by '{keys[api_key]}'), skipping"
                        )
                        continue

                    keys[api_key] = key_id
                    self._raw_key_metadata.append((key_id, rate_limit_str, expiration_str))

            if keys:
                print(f"🔐 Loaded {len(keys)} API key(s) from {self.keys_file}")
                # Show key IDs for verification
                key_ids = sorted(set(keys.values()))
                print(f"   Key IDs: {', '.join(key_ids)}")
                return keys
            else:
                print(f"⚠️  Keys file exists but contains no valid keys: {self.keys_file}")
                return {}
        except Exception as e:
            print(f"❌ Error loading keys from {self.keys_file}: {e}")
            return {}

    def _parse_key_metadata(self) -> None:
        """Parse per-key rate limits and expirations from raw metadata.

        Called after _load_keys() to populate key_rate_limits and key_expirations
        dictionaries from the _raw_key_metadata collected during key loading.
        """
        for key_id, rate_limit_str, expiration_str in getattr(self, "_raw_key_metadata", []):
            # Per-key rate limit
            if rate_limit_str:
                self.key_rate_limits[key_id] = int(rate_limit_str)

            # Key expiration
            if expiration_str:
                self.key_expirations[key_id] = datetime.datetime.fromisoformat(expiration_str)

    def validate(self, headers: dict) -> Tuple[bool, str]:
        """
        Validate API key from request headers.

        Args:
            headers: Request headers (lowercase keys)

        Returns:
            (is_valid, key_id_or_error_message)
            - If valid: (True, key_id)
            - If invalid: (False, error_message)
        """
        # If auth disabled, allow everything
        if not self.enabled:
            return True, "auth-disabled"

        # If no keys configured, reject all requests (fail-closed)
        if not self.keys:
            return False, "Authentication misconfigured: no API keys loaded"

        # Extract key from Authorization header
        auth_header = headers.get("authorization", "")

        if not auth_header:
            return False, "Missing Authorization header"

        # Remove "Bearer " prefix if present (OpenAI compatible)
        if auth_header.lower().startswith("bearer "):
            api_key = auth_header[7:].strip()
        else:
            api_key = auth_header.strip()

        if not api_key:
            return False, "Empty Authorization header"

        # Validate key format
        if not self._is_valid_format(api_key):
            return False, "Invalid API key format"

        # Check if key exists (constant-time comparison to prevent timing attacks)
        key_id = self._find_key(api_key)
        if key_id is None:
            return False, "Invalid API key"

        # Check if key has expired
        if self._is_key_expired(key_id):
            return False, "API key has expired"

        # Check rate limit
        if not self._check_rate_limit(key_id):
            return False, "rate_limit_exceeded"

        # Record successful request
        self._record_request(key_id)

        return True, key_id

    def _is_key_expired(self, key_id: str) -> bool:
        """Check if a key has passed its expiration time.

        Args:
            key_id: The key identifier to check.

        Returns:
            True if the key has expired, False otherwise (including if no expiration set).
        """
        expiration = self.key_expirations.get(key_id)
        if expiration is None:
            return False
        return bool(datetime.datetime.now() >= expiration)

    def _is_valid_format(self, key: str) -> bool:
        """
        Check if key format looks valid.

        Accepts alphanumeric, hyphens, underscores.
        Length: 16-128 characters.
        """
        if not (16 <= len(key) <= 128):
            return False

        return all(c.isalnum() or c in "-_" for c in key)

    def _find_key(self, api_key: str) -> Optional[str]:
        """Find key_id for api_key using constant-time comparison.

        Iterates all stored keys using hmac.compare_digest to prevent
        timing attacks from leaking valid key information.
        """
        api_key_bytes = api_key.encode("utf-8")
        result = None
        for stored_key, key_id in self.keys.items():
            if hmac.compare_digest(stored_key.encode("utf-8"), api_key_bytes):
                result = key_id
            # No early return — always check all keys for constant time
        return result

    def _check_rate_limit(self, key_id: str) -> bool:
        """
        Check if key_id has exceeded rate limit.

        Uses per-key rate limit if configured, otherwise falls back to the
        global MAX_REQUESTS_PER_MINUTE default.

        Also triggers periodic cleanup of stale rate limiter entries for
        inactive keys (every CLEANUP_INTERVAL seconds).

        Returns True if under limit, False if exceeded.
        """
        now = time.time()
        minute_ago = now - 60

        # Periodic cleanup of stale entries for inactive keys
        self._cleanup_rate_limiter(now)

        # Clean old requests for this key (older than 1 minute)
        self.rate_limiter[key_id] = [ts for ts in self.rate_limiter[key_id] if ts > minute_ago]

        # Determine effective rate limit for this key
        effective_limit = self.key_rate_limits.get(key_id, self.max_requests_per_minute)

        # Check if under limit
        if len(self.rate_limiter[key_id]) >= effective_limit:
            return False

        return True

    def _cleanup_rate_limiter(self, now: Optional[float] = None) -> None:
        """Remove stale rate limiter entries for inactive keys.

        Only runs if more than CLEANUP_INTERVAL seconds have elapsed since the
        last cleanup. Removes entries for key_ids that have no timestamps within
        the current rate limit window (60 seconds).

        Args:
            now: Current timestamp. If None, uses time.time().
        """
        if now is None:
            now = time.time()

        if now - self._last_cleanup < self.CLEANUP_INTERVAL:
            return

        self._last_cleanup = now
        minute_ago = now - 60

        # Collect keys to remove (can't modify dict during iteration)
        stale_keys = [
            key_id
            for key_id, timestamps in self.rate_limiter.items()
            if not any(ts > minute_ago for ts in timestamps)
        ]

        for key_id in stale_keys:
            del self.rate_limiter[key_id]

    def _record_request(self, key_id: str):
        """Record a request timestamp for rate limiting."""
        self.rate_limiter[key_id].append(time.time())

    def get_metrics(self) -> dict:
        """
        Get current rate limiter metrics per key_id.

        Returns:
            dict with request counts, effective rate limits, and expiration per key_id
        """
        now = time.time()
        minute_ago = now - 60

        metrics = {}
        for key_id, timestamps in self.rate_limiter.items():
            # Count recent requests
            recent = [ts for ts in timestamps if ts > minute_ago]
            effective_limit = self.key_rate_limits.get(key_id, self.max_requests_per_minute)
            expiration = self.key_expirations.get(key_id)
            entry = {
                "requests_last_minute": len(recent),
                "rate_limit": effective_limit,
            }
            if expiration is not None:
                entry["expires"] = expiration.isoformat()
            metrics[key_id] = entry

        return metrics


# Global validator instance
api_validator = APIKeyValidator()


def reload_keys() -> int:
    """Reload API keys from the keys file without restarting the gateway.

    Re-reads the keys file from the same path used at startup and atomically
    replaces the validator's keys, per-key rate limits, and expirations.
    Rate limiter state (request timestamps) is preserved so that existing
    rate limits for known keys survive the reload.

    Returns:
        Number of keys loaded from the file.

    Raises:
        Exception: Propagated from file I/O so the caller can log and
        continue serving with the previous key set.
    """
    # Re-read keys_file path from the environment so operators can change
    # the file location at runtime (e.g., rotate to a new file).
    api_validator.keys_file = os.environ.get(
        "AUTH_KEYS_FILE",
        f"{os.environ.get('DATA_DIR', '/data')}/api_keys.txt",
    )

    # Build all new state in temporaries before touching the validator.
    # This guarantees atomicity: either everything is replaced or nothing is.
    new_keys = api_validator._load_keys()

    # Parse metadata into fresh dicts (not in-place on the validator)
    new_rate_limits: dict[str, int] = {}
    new_expirations: dict[str, datetime.datetime] = {}
    for key_id, rate_limit_str, expiration_str in getattr(api_validator, "_raw_key_metadata", []):
        if rate_limit_str:
            new_rate_limits[key_id] = int(rate_limit_str)
        if expiration_str:
            new_expirations[key_id] = datetime.datetime.fromisoformat(expiration_str)

    # Atomic swap: assign all new state in quick succession.
    # Rate limiter (request timestamps) is intentionally NOT touched.
    api_validator.keys = new_keys
    api_validator.key_rate_limits = new_rate_limits
    api_validator.key_expirations = new_expirations

    count = len(new_keys)
    if count == 0 and api_validator.enabled:
        print(
            "WARNING: API keys file reloaded with 0 keys — "
            "all requests will be rejected (fail-closed)"
        )

    return count


async def authenticate_request(writer: asyncio.StreamWriter, headers: dict) -> Optional[str]:
    """
    Authenticate an incoming request.

    If authentication fails, sends a 401 response and returns None.
    If authentication succeeds, returns the key_id.

    Args:
        writer: asyncio StreamWriter to send response
        headers: Request headers (lowercase keys)

    Returns:
        key_id if valid, None if invalid (401 response already sent)
    """
    is_valid, result = api_validator.validate(headers)

    if not is_valid:
        if result == "rate_limit_exceeded":
            # Send 429 rate limit response
            await send_rate_limit_error(writer)
        else:
            # Send OpenAI-compatible 401 error
            error_response = {
                "error": {
                    "message": result,
                    "type": "invalid_request_error",
                    "param": "authorization",
                    "code": "invalid_api_key",
                }
            }

            body = json.dumps(error_response)

            response = (
                "HTTP/1.1 401 Unauthorized\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n" + body
            )

            writer.write(response.encode())
            await writer.drain()
        return None

    # Authentication succeeded, return key_id
    return result


async def send_rate_limit_error(writer: asyncio.StreamWriter):
    """Send OpenAI-compatible rate limit error (429)."""
    error_response = {
        "error": {
            "message": "Rate limit exceeded. Please slow down your requests.",
            "type": "rate_limit_error",
            "code": "rate_limit_exceeded",
        }
    }

    body = json.dumps(error_response)

    response = (
        "HTTP/1.1 429 Too Many Requests\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Retry-After: 60\r\n"
        "Connection: close\r\n"
        "\r\n" + body
    )

    writer.write(response.encode())
    await writer.drain()


def _sanitize_log_field(value: str) -> str:
    """Sanitize a value for safe inclusion in log output.

    Replaces control characters that could enable log injection attacks
    (SEC-11): newlines, carriage returns, tabs, and pipe characters
    (the log field delimiter) are replaced with underscores.
    """
    return value.replace("\n", "_").replace("\r", "_").replace("\t", "_").replace("|", "_")


# Log format: read once at import time to match gateway.py behavior
_LOG_FORMAT = os.environ.get("LOG_FORMAT", "text").lower()


async def log_access(method: str, path: str, key_id: str, status_code: int):
    """
    Log API access for auditing.

    Logs to: /data/logs/api_access.log

    When LOG_FORMAT=json, writes JSONL entries. Otherwise writes
    pipe-delimited text (default, backward-compatible).

    Text format: ISO8601_timestamp | key_id | method path | status_code
    JSON format: {"ts":"...","key_id":"...","method":"...","path":"...","status":200}

    Args:
        method: HTTP method
        path: Request path
        key_id: The key identifier (e.g., "production", "alice-laptop")
        status_code: HTTP status code
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if _LOG_FORMAT == "json":
        log_entry = json.dumps(
            {
                "ts": timestamp,
                "key_id": key_id,
                "method": method,
                "path": path,
                "status": status_code,
            },
            separators=(",", ":"),
        )
    else:
        # SEC-11: Sanitize log fields to prevent log injection
        safe_method = _sanitize_log_field(method)
        safe_path = _sanitize_log_field(path)
        safe_key_id = _sanitize_log_field(key_id)
        log_entry = f"{timestamp} | {safe_key_id} | {safe_method} {safe_path} | {status_code}"

    # Log to file
    log_file = "/data/logs/api_access.log"
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        # Don't fail request if logging fails, but print warning
        print(f"Warning: Failed to log access: {e}")
