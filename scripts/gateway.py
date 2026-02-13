#!/usr/bin/env python3
"""
gateway.py – Async HTTP gateway for llama.cpp llama-server

Features:
- API key authentication with health endpoint exemption
- Proper SSE/streaming support for chat completions
- /ping and /health endpoints (no auth required)
- Request timeout handling
- Basic metrics tracking
- Graceful error handling
- Per-key access logging
- Configurable CORS headers
- Prometheus text exposition format for /metrics

Note: /ping and /health return 200 immediately without backend checks
or authentication to enable scale-to-zero in serverless environments.

Environment Variables:
    GATEWAY_PORT    - Port to listen on (default: 8000)
    BACKEND_HOST    - llama-server host (default: 127.0.0.1)
    PORT_BACKEND    - llama-server port (default: 8080)
    BACKEND_API_KEY - API key for backend authentication (optional)
    REQUEST_TIMEOUT - Max request time in seconds (default: 300)
    HEALTH_TIMEOUT  - Health check timeout in seconds (default: 2)
    AUTH_ENABLED    - Enable API key authentication (default: true)
    AUTH_KEYS_FILE  - Path to API keys file (default: $DATA_DIR/api_keys.txt)
    CORS_ORIGINS    - Comma-separated allowed CORS origins (default: empty = disabled)
    MAX_CONCURRENT_REQUESTS - Max requests proxied simultaneously (default: 1)
    MAX_QUEUE_SIZE  - Max requests waiting in queue; 0 = unlimited (default: 0)
"""

import asyncio
import json
import os
import re
import signal
import socket
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

# Import authentication module
try:
    from auth import api_validator, authenticate_request, log_access

    AUTH_AVAILABLE = True
except ImportError:
    print("[gateway] Warning: auth.py not found, authentication disabled")
    AUTH_AVAILABLE = False


def log(msg: str):
    """Simple logging to stderr."""
    print(f"[gateway] {msg}", file=sys.stderr, flush=True)


# Configuration
GATEWAY_HOST = "0.0.0.0"  # nosec B104 - intentional bind-all for container networking
GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", os.environ.get("PORT", "8000")))
BACKEND_HOST = os.environ.get("BACKEND_HOST", "127.0.0.1")
# Support both PORT_BACKEND (new) and BACKEND_PORT (old, deprecated)
if "BACKEND_PORT" in os.environ:
    print("[gateway] WARNING: BACKEND_PORT is deprecated, use PORT_BACKEND instead")
    BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8080"))
else:
    BACKEND_PORT = int(os.environ.get("PORT_BACKEND", "8080"))
REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "300"))
HEALTH_TIMEOUT = float(os.environ.get("HEALTH_TIMEOUT", "2"))

# Concurrency and queue configuration
MAX_CONCURRENT_REQUESTS = int(os.environ.get("MAX_CONCURRENT_REQUESTS", "1"))
MAX_QUEUE_SIZE = int(os.environ.get("MAX_QUEUE_SIZE", "0"))

# Concurrency semaphore — limits parallel proxy calls to llama-server
_proxy_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# Queue depth tracking (manual counter — not in Metrics because it's managed inline)
_queue_depth: int = 0

# Backend authentication
BACKEND_API_KEY = os.environ.get("BACKEND_API_KEY")
if BACKEND_API_KEY:
    # Validate key format: "gateway-" + 43 base64url characters
    # Total length should be 51 characters (8 + 43)
    if not re.match(r"^gateway-[A-Za-z0-9_-]{43}$", BACKEND_API_KEY):
        log("ERROR: BACKEND_API_KEY has invalid format (expected: gateway-{43 base64url chars})")
        log(f"ERROR: Received length: {len(BACKEND_API_KEY)}, expected: 51")
        sys.exit(1)
    if len(BACKEND_API_KEY) != 51:
        log(f"ERROR: BACKEND_API_KEY has invalid length: {len(BACKEND_API_KEY)} (expected: 51)")
        sys.exit(1)
    log("Backend key format validated successfully")
else:
    log("WARNING: BACKEND_API_KEY not set - backend will not require authentication")

# CORS configuration
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "")
_cors_origins_list: list[str] = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
CORS_ENABLED = len(_cors_origins_list) > 0
CORS_WILDCARD = "*" in _cors_origins_list

if CORS_ENABLED:
    if CORS_WILDCARD:
        log("CORS: enabled for all origins (*)")
    else:
        log(f"CORS: enabled for {len(_cors_origins_list)} origin(s)")


def get_cors_headers(request_origin: str = "") -> list[str]:
    """Return CORS response header lines for the given request origin.

    Returns an empty list if CORS is not enabled or the origin is not allowed.
    """
    if not CORS_ENABLED:
        return []

    if CORS_WILDCARD:
        allowed_origin = "*"
    elif request_origin in _cors_origins_list:
        allowed_origin = request_origin
    else:
        return []

    headers = [
        f"Access-Control-Allow-Origin: {allowed_origin}",
        "Access-Control-Allow-Methods: GET, POST, OPTIONS",
        "Access-Control-Allow-Headers: Authorization, Content-Type",
        "Access-Control-Max-Age: 86400",
    ]
    # Vary: Origin needed for allowlist mode so caches distinguish responses (SEC-02)
    if not CORS_WILDCARD:
        headers.append("Vary: Origin")
    return headers


def build_cors_header_str(request_origin: str = "") -> str:
    """Return CORS headers as a joined string ready for HTTP response injection.

    Returns empty string if CORS is not enabled or the origin is not allowed.
    """
    headers = get_cors_headers(request_origin)
    if not headers:
        return ""
    return "\r\n".join(headers) + "\r\n"


async def handle_options(writer: asyncio.StreamWriter, request_origin: str = ""):
    """Handle OPTIONS preflight request with CORS headers.

    Returns 204 No Content with appropriate CORS headers.
    No authentication required.
    """
    cors = build_cors_header_str(request_origin)
    response = (
        f"HTTP/1.1 204 No Content\r\n"
        f"{cors}"
        f"Content-Length: 0\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    writer.write(response.encode())
    await writer.drain()


# Metrics (simple in-memory counters)
@dataclass
class Metrics:
    requests_total: int = 0
    requests_success: int = 0
    requests_error: int = 0
    requests_active: int = 0
    requests_authenticated: int = 0
    requests_unauthorized: int = 0
    bytes_sent: int = 0
    queue_rejections: int = 0
    queue_wait_seconds_total: float = 0.0
    start_time: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "requests_total": self.requests_total,
            "requests_success": self.requests_success,
            "requests_error": self.requests_error,
            "requests_active": self.requests_active,
            "requests_authenticated": self.requests_authenticated,
            "requests_unauthorized": self.requests_unauthorized,
            "bytes_sent": self.bytes_sent,
            "queue_depth": _queue_depth,
            "queue_rejections": self.queue_rejections,
            "queue_wait_seconds_total": round(self.queue_wait_seconds_total, 3),
            "uptime_seconds": int(time.time() - self.start_time),
        }

    def to_prometheus(self) -> str:
        """Return metrics in Prometheus text exposition format."""
        uptime = int(time.time() - self.start_time)
        lines = [
            "# HELP gateway_requests_total Total requests handled",
            "# TYPE gateway_requests_total counter",
            f"gateway_requests_total {self.requests_total}",
            "# HELP gateway_requests_success Total successful requests",
            "# TYPE gateway_requests_success counter",
            f"gateway_requests_success {self.requests_success}",
            "# HELP gateway_requests_error Total failed requests",
            "# TYPE gateway_requests_error counter",
            f"gateway_requests_error {self.requests_error}",
            "# HELP gateway_requests_active Currently active requests",
            "# TYPE gateway_requests_active gauge",
            f"gateway_requests_active {self.requests_active}",
            "# HELP gateway_requests_authenticated Total authenticated requests",
            "# TYPE gateway_requests_authenticated counter",
            f"gateway_requests_authenticated {self.requests_authenticated}",
            "# HELP gateway_requests_unauthorized Total unauthorized requests",
            "# TYPE gateway_requests_unauthorized counter",
            f"gateway_requests_unauthorized {self.requests_unauthorized}",
            "# HELP gateway_bytes_sent Total bytes sent to clients",
            "# TYPE gateway_bytes_sent counter",
            f"gateway_bytes_sent {self.bytes_sent}",
            "# HELP gateway_queue_depth Current requests waiting for semaphore",
            "# TYPE gateway_queue_depth gauge",
            f"gateway_queue_depth {_queue_depth}",
            "# HELP gateway_queue_rejections Total requests rejected due to full queue",
            "# TYPE gateway_queue_rejections counter",
            f"gateway_queue_rejections {self.queue_rejections}",
            "# HELP gateway_queue_wait_seconds_total Cumulative queue wait time in seconds",
            "# TYPE gateway_queue_wait_seconds_total counter",
            f"gateway_queue_wait_seconds_total {round(self.queue_wait_seconds_total, 3)}",
            "# HELP gateway_uptime_seconds Gateway uptime in seconds",
            "# TYPE gateway_uptime_seconds gauge",
            f"gateway_uptime_seconds {uptime}",
        ]
        return "\n".join(lines) + "\n"


metrics = Metrics()


def backend_tcp_ready() -> bool:
    """Check if backend is accepting TCP connections."""
    try:
        with socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=0.5):
            return True
    except (OSError, socket.timeout):
        return False


async def backend_health_check() -> dict:
    """Check backend health via /health endpoint.

    Returns health status dict or error.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(BACKEND_HOST, BACKEND_PORT), timeout=HEALTH_TIMEOUT
        )

        request = (
            f"GET /health HTTP/1.1\r\n"
            f"Host: {BACKEND_HOST}:{BACKEND_PORT}\r\n"
            f"Connection: close\r\n\r\n"
        )
        writer.write(request.encode())
        await writer.drain()

        response = await asyncio.wait_for(reader.read(4096), timeout=HEALTH_TIMEOUT)
        writer.close()
        await writer.wait_closed()

        # Parse response
        response_str = response.decode("utf-8", errors="replace")

        # Extract status code
        first_line = response_str.split("\r\n")[0]
        status_code = int(first_line.split()[1]) if len(first_line.split()) > 1 else 0

        # Extract body (after \r\n\r\n)
        if "\r\n\r\n" in response_str:
            body = response_str.split("\r\n\r\n", 1)[1]
            try:
                return {
                    "status": "ok",
                    "code": status_code,
                    "backend": json.loads(body),
                }
            except json.JSONDecodeError:
                return {
                    "status": "ok",
                    "code": status_code,
                    "backend_raw": body[:200],
                }

        return {"status": "ok", "code": status_code}

    except asyncio.TimeoutError:
        return {"status": "timeout", "error": "Backend health check timed out"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def handle_ping(writer: asyncio.StreamWriter, request_origin: str = ""):
    """Handle /ping endpoint for RunPod health checks.

    Always returns 200 OK without authentication or backend checks.
    For detailed backend status, use /health endpoint instead.
    """
    cors = build_cors_header_str(request_origin)
    response = (
        f"HTTP/1.1 200 OK\r\n" f"{cors}" f"Content-Length: 0\r\n" f"Connection: close\r\n" f"\r\n"
    )
    writer.write(response.encode())
    await writer.drain()


async def handle_health(writer: asyncio.StreamWriter, request_origin: str = ""):
    """Handle /health endpoint with detailed backend status.

    No authentication required.
    """
    health = await backend_health_check()
    health["gateway"] = {
        "status": "ok",
        "metrics": metrics.to_dict(),
    }

    # Queue status
    health["queue"] = {
        "max_concurrent": MAX_CONCURRENT_REQUESTS,
        "max_queue_size": MAX_QUEUE_SIZE,
        "active": MAX_CONCURRENT_REQUESTS - _proxy_semaphore._value,
        "waiting": _queue_depth,
    }

    # Auth status (no sensitive details on unauthenticated endpoint)
    if AUTH_AVAILABLE:
        health["authentication"] = {"enabled": api_validator.enabled}

    body = json.dumps(health, indent=2)
    cors = build_cors_header_str(request_origin)
    response = (
        f"HTTP/1.1 200 OK\r\n"
        f"Content-Type: application/json\r\n"
        f"{cors}"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{body}"
    )
    writer.write(response.encode())
    await writer.drain()


def _wants_prometheus(accept_header: str) -> bool:
    """Check if the Accept header requests Prometheus text format."""
    if not accept_header:
        return False
    accept_lower = accept_header.lower()
    return "text/plain" in accept_lower or "application/openmetrics-text" in accept_lower


async def handle_metrics(
    writer: asyncio.StreamWriter,
    request_origin: str = "",
    accept_header: str = "",
):
    """Handle /metrics endpoint.

    No authentication required.
    Returns Prometheus text format if Accept header contains text/plain
    or application/openmetrics-text, otherwise returns JSON.
    """
    cors = build_cors_header_str(request_origin)

    if _wants_prometheus(accept_header):
        body = metrics.to_prometheus()
        content_type = "text/plain; version=0.0.4; charset=utf-8"
    else:
        metrics_data = {"gateway": metrics.to_dict()}

        # Auth metrics excluded from unauthenticated /metrics endpoint
        # to prevent key_id disclosure (SEC-01). Per-key metrics are
        # available via authenticated endpoints only.

        body = json.dumps(metrics_data, indent=2)
        content_type = "application/json"

    response = (
        f"HTTP/1.1 200 OK\r\n"
        f"Content-Type: {content_type}\r\n"
        f"{cors}"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{body}"
    )
    writer.write(response.encode())
    await writer.drain()


async def send_queue_full_response(
    writer: asyncio.StreamWriter,
    request_origin: str = "",
) -> None:
    """Send a 503 Service Unavailable response when the request queue is full.

    Includes a Retry-After header and a JSON error body matching the OpenAI
    error format used elsewhere in the gateway.
    """
    body = json.dumps(
        {
            "error": {
                "message": "Server busy, try again later",
                "type": "server_error",
                "code": "queue_full",
            }
        }
    )
    cors = build_cors_header_str(request_origin)
    response = (
        f"HTTP/1.1 503 Service Unavailable\r\n"
        f"Content-Type: application/json\r\n"
        f"Retry-After: 5\r\n"
        f"{cors}"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{body}"
    )
    writer.write(response.encode())
    await writer.drain()


def _inject_cors_into_headers(response_headers: bytes, request_origin: str) -> bytes:
    r"""Inject CORS headers into raw HTTP response headers.

    Inserts CORS header lines before the final \r\n separator.
    Returns the original headers unchanged if CORS is not applicable.
    """
    cors_str = build_cors_header_str(request_origin)
    if cors_str and response_headers.endswith(b"\r\n"):
        return response_headers[:-2] + cors_str.encode() + b"\r\n"
    return response_headers


async def proxy_request(
    method: str,
    path: str,
    headers: dict,
    body: Optional[bytes],
    writer: asyncio.StreamWriter,
    key_id: str = "unknown",
    request_origin: str = "",
):
    """Proxy a request to the backend with streaming support.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path to forward to backend
        headers: Request headers dict (lowercase keys)
        body: Request body bytes, or None for bodyless requests
        writer: asyncio StreamWriter for the client connection
        key_id: The authenticated key_id for logging
        request_origin: The Origin header value for CORS header injection
    """
    metrics.requests_total += 1
    metrics.requests_active += 1

    try:
        # Connect to backend
        try:
            backend_reader, backend_writer = await asyncio.wait_for(
                asyncio.open_connection(BACKEND_HOST, BACKEND_PORT), timeout=5.0
            )
        except (asyncio.TimeoutError, OSError):
            metrics.requests_error += 1
            error_response = (
                "HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            writer.write(error_response.encode())
            await writer.drain()
            # Log failed request
            if AUTH_AVAILABLE:
                await log_access(method, path, key_id, 502)
            return

        # Build request to backend
        request_line = f"{method} {path} HTTP/1.1\r\n"

        # Forward headers, adjusting Host
        header_lines = [f"Host: {BACKEND_HOST}:{BACKEND_PORT}"]
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in (
                "host",
                "connection",
                "keep-alive",
                "transfer-encoding",
                "authorization",
            ):
                continue  # Skip user's authorization header
            header_lines.append(f"{key}: {value}")

        # Add backend authentication if configured
        if BACKEND_API_KEY:
            header_lines.append(f"Authorization: Bearer {BACKEND_API_KEY}")

        header_lines.append("Connection: close")

        request = request_line + "\r\n".join(header_lines) + "\r\n\r\n"
        backend_writer.write(request.encode())

        if body:
            backend_writer.write(body)

        await backend_writer.drain()

        # Read and forward response headers
        response_headers = b""
        while True:
            line = await asyncio.wait_for(backend_reader.readline(), timeout=REQUEST_TIMEOUT)
            response_headers += line
            if line == b"\r\n" or line == b"":
                break

        # Inject CORS headers into the response before sending to client
        response_headers = _inject_cors_into_headers(response_headers, request_origin)

        # Send headers to client
        writer.write(response_headers)
        await writer.drain()

        # Stream response body
        bytes_sent = 0
        try:
            while True:
                chunk = await asyncio.wait_for(backend_reader.read(8192), timeout=REQUEST_TIMEOUT)
                if not chunk:
                    break
                writer.write(chunk)
                await writer.drain()
                bytes_sent += len(chunk)
        except asyncio.TimeoutError:
            pass  # Connection closed or timeout

        metrics.bytes_sent += bytes_sent
        metrics.requests_success += 1

        backend_writer.close()
        await backend_writer.wait_closed()

        # Log successful request
        if AUTH_AVAILABLE:
            await log_access(method, path, key_id, 200)

    except Exception as e:
        metrics.requests_error += 1
        log(f"Proxy error: {e}")
        try:
            error_response = (
                "HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            writer.write(error_response.encode())
            await writer.drain()
        except Exception:
            log("Cleanup: failed to send error response to client")
        # Log error
        if AUTH_AVAILABLE:
            await log_access(method, path, key_id, 502)

    finally:
        metrics.requests_active -= 1


async def _queued_proxy(
    method: str,
    path: str,
    headers: dict,
    body: Optional[bytes],
    writer: asyncio.StreamWriter,
    key_id: str,
    request_origin: str,
) -> None:
    """Proxy a request through the concurrency-limited queue.

    Checks the bounded queue, waits on the semaphore, then forwards to
    ``proxy_request``.  Returns immediately with 503 when the queue is full.
    """
    global _queue_depth

    # Check bounded queue before waiting on the semaphore
    if MAX_QUEUE_SIZE > 0 and _queue_depth >= MAX_QUEUE_SIZE:
        metrics.queue_rejections += 1
        await send_queue_full_response(writer, request_origin)
        return

    _queue_depth += 1
    wait_start = time.monotonic()
    try:
        await _proxy_semaphore.acquire()
    except BaseException:
        _queue_depth -= 1
        raise

    wait_elapsed = time.monotonic() - wait_start
    metrics.queue_wait_seconds_total += wait_elapsed
    _queue_depth -= 1
    try:
        await proxy_request(method, path, headers, body, writer, key_id, request_origin)
    finally:
        _proxy_semaphore.release()


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle an incoming client connection."""
    try:
        # Read request line
        request_line_raw = await asyncio.wait_for(reader.readline(), timeout=30)
        if not request_line_raw:
            return

        request_line = request_line_raw.decode("utf-8", errors="replace").strip()
        parts = request_line.split()
        if len(parts) < 2:
            return

        method = parts[0]
        path = parts[1]

        # Read headers
        headers: dict[str, str] = {}
        content_length = 0
        while True:
            header_line_raw = await asyncio.wait_for(reader.readline(), timeout=30)
            if header_line_raw == b"\r\n" or header_line_raw == b"":
                break
            header_line = header_line_raw.decode("utf-8", errors="replace").strip()
            if ":" in header_line:
                key, value = header_line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
                if key.lower() == "content-length":
                    content_length = int(value.strip())

        # Read body if present
        body = None
        if content_length > 0:
            body = await asyncio.wait_for(reader.readexactly(content_length), timeout=30)

        # Extract origin for CORS
        request_origin = headers.get("origin", "")
        accept_header = headers.get("accept", "")

        # Handle OPTIONS preflight (no auth required)
        if method == "OPTIONS":
            await handle_options(writer, request_origin)
            return

        # Route request - health endpoints bypass auth
        if path in ("/ping", "/health", "/metrics"):
            if path == "/ping":
                await handle_ping(writer, request_origin)
            elif path == "/health":
                await handle_health(writer, request_origin)
            elif path == "/metrics":
                await handle_metrics(writer, request_origin, accept_header)
            return

        # All other endpoints require authentication
        if AUTH_AVAILABLE:
            key_id = await authenticate_request(writer, headers)
            if key_id is None:
                # 401 response already sent by authenticate_request
                metrics.requests_unauthorized += 1
                return

            metrics.requests_authenticated += 1
        else:
            # Auth not available, allow request
            key_id = "auth-disabled"

        # Proxy to backend with concurrency control
        await _queued_proxy(method, path, headers, body, writer, key_id, request_origin)

    except asyncio.TimeoutError:
        pass
    except Exception as e:
        log(f"Client handler error: {e}")

    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            log("Cleanup: failed to close client writer")


async def main():
    """Start the gateway server."""
    log(f"Starting gateway on {GATEWAY_HOST}:{GATEWAY_PORT}")
    log(f"Backend: {BACKEND_HOST}:{BACKEND_PORT}")
    log(f"Request timeout: {REQUEST_TIMEOUT}s")
    log(
        f"Concurrency: max_concurrent={MAX_CONCURRENT_REQUESTS}, "
        f"max_queue={'unlimited' if MAX_QUEUE_SIZE == 0 else MAX_QUEUE_SIZE}"
    )

    if AUTH_AVAILABLE:
        if api_validator.enabled:
            log(f"Authentication: ENABLED ({len(api_validator.keys)} keys configured)")
        else:
            log("Authentication: DISABLED")
    else:
        log("Authentication: NOT AVAILABLE (auth.py not found)")

    server = await asyncio.start_server(
        handle_client,
        GATEWAY_HOST,
        GATEWAY_PORT,
        reuse_address=True,
    )

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        log("Shutdown signal received")
        server.close()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    log(f"Gateway listening on http://{GATEWAY_HOST}:{GATEWAY_PORT}")
    log("Public endpoints (no auth): /ping, /health, /metrics")
    log("Protected endpoints (auth required): /v1/*")
    log(
        "Proxied endpoints: /v1/chat/completions, /v1/completions, "
        "/v1/embeddings, /v1/models, ..."
    )
    if CORS_ENABLED:
        log(f"CORS: enabled (origins: {CORS_ORIGINS})")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Interrupted")
    except Exception as e:
        log(f"Fatal error: {e}")
        sys.exit(1)
