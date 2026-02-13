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
    key_id:api_key

Example:
    production:sk-prod-abc123def456
    alice-laptop:sk-alice-xyz789
    development:sk-dev-test123
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
    - File-based configuration (key_id:api_key format)
    - Rate limiting per key_id
    - Key format validation
    - Audit trail with key_id tracking
    """

    def __init__(self):
        self.enabled = os.environ.get("AUTH_ENABLED", "true").lower() == "true"
        self.keys_file = os.environ.get(
            "AUTH_KEYS_FILE",
            f"{os.environ.get('DATA_DIR', '/data')}/api_keys.txt",
        )
        self.keys = self._load_keys()  # Maps api_key -> key_id
        self.rate_limiter = defaultdict(list)  # Maps key_id -> [timestamps]
        self.max_requests_per_minute = int(os.environ.get("MAX_REQUESTS_PER_MINUTE", "100"))

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
            key_id:api_key
            # Comments allowed

        Returns:
            dict mapping api_key -> key_id for reverse lookup
            Example: {"sk-prod-abc123": "production", "sk-alice-xyz": "alice-laptop"}
        """
        if not self.enabled:
            return {}

        if not os.path.exists(self.keys_file):
            print(f"⚠️  AUTH_ENABLED=true but keys file not found: {self.keys_file}")
            print("    Create file with format: key_id:api_key")
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

                    # Parse key_id:api_key
                    if ":" not in line:
                        print(f"⚠️  Line {line_num}: Invalid format (missing ':'), skipping")
                        continue

                    parts = line.split(":", 1)
                    if len(parts) != 2:
                        print(f"⚠️  Line {line_num}: Invalid format, skipping")
                        continue

                    key_id = parts[0].strip()
                    api_key = parts[1].strip()

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

                    # Check for duplicate keys
                    if api_key in keys:
                        print(
                            f"⚠️  Line {line_num}: Duplicate api_key for '{key_id}' "
                            f"(already used by '{keys[api_key]}'), skipping"
                        )
                        continue

                    keys[api_key] = key_id

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

        # Check rate limit
        if not self._check_rate_limit(key_id):
            return False, "rate_limit_exceeded"

        # Record successful request
        self._record_request(key_id)

        return True, key_id

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

        Returns True if under limit, False if exceeded.
        """
        now = time.time()
        minute_ago = now - 60

        # Clean old requests (older than 1 minute)
        self.rate_limiter[key_id] = [ts for ts in self.rate_limiter[key_id] if ts > minute_ago]

        # Check if under limit
        if len(self.rate_limiter[key_id]) >= self.max_requests_per_minute:
            return False

        return True

    def _record_request(self, key_id: str):
        """Record a request timestamp for rate limiting."""
        self.rate_limiter[key_id].append(time.time())

    def get_metrics(self) -> dict:
        """
        Get current rate limiter metrics per key_id.

        Returns:
            dict with request counts and limits per key_id
        """
        now = time.time()
        minute_ago = now - 60

        metrics = {}
        for key_id, timestamps in self.rate_limiter.items():
            # Count recent requests
            recent = [ts for ts in timestamps if ts > minute_ago]
            metrics[key_id] = {
                "requests_last_minute": len(recent),
                "rate_limit": self.max_requests_per_minute,
            }

        return metrics


# Global validator instance
api_validator = APIKeyValidator()


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


async def log_access(method: str, path: str, key_id: str, status_code: int):
    """
    Log API access for auditing.

    Logs to: /data/logs/api_access.log

    Format: ISO8601_timestamp | key_id | method path | status_code
    Example: 2024-02-06T14:30:22.123456 | production | POST /v1/chat/completions | 200

    Args:
        method: HTTP method
        path: Request path
        key_id: The key identifier (e.g., "production", "alice-laptop")
        status_code: HTTP status code
    """
    timestamp = datetime.datetime.now().isoformat()

    log_entry = f"{timestamp} | {key_id} | {method} {path} | {status_code}"

    # Log to file
    log_file = "/data/logs/api_access.log"
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        # Don't fail request if logging fails, but print warning
        print(f"Warning: Failed to log access: {e}")
