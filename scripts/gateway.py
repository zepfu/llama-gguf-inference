#!/usr/bin/env python3
"""
gateway.py — Async HTTP gateway for llama.cpp llama-server

Features:
- Proper SSE/streaming support for chat completions
- /ping and /health endpoints for RunPod health checks
- Request timeout handling
- Basic metrics tracking
- Graceful error handling

Environment Variables:
    GATEWAY_PORT    - Port to listen on (default: 8000)
    BACKEND_HOST    - llama-server host (default: 127.0.0.1)
    BACKEND_PORT    - llama-server port (default: 8080)
    REQUEST_TIMEOUT - Max request time in seconds (default: 300)
    HEALTH_TIMEOUT  - Health check timeout in seconds (default: 2)
"""

import asyncio
import json
import os
import signal
import socket
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

# Configuration
GATEWAY_HOST = "0.0.0.0"
GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", os.environ.get("PORT", "8000")))
BACKEND_HOST = os.environ.get("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8080"))
REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "300"))
HEALTH_TIMEOUT = float(os.environ.get("HEALTH_TIMEOUT", "2"))

# Metrics (simple in-memory counters)
@dataclass
class Metrics:
    requests_total: int = 0
    requests_success: int = 0
    requests_error: int = 0
    requests_active: int = 0
    bytes_sent: int = 0
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self):
        return {
            "requests_total": self.requests_total,
            "requests_success": self.requests_success,
            "requests_error": self.requests_error,
            "requests_active": self.requests_active,
            "bytes_sent": self.bytes_sent,
            "uptime_seconds": int(time.time() - self.start_time),
        }

metrics = Metrics()


def log(msg: str):
    """Simple logging to stderr."""
    print(f"[gateway] {msg}", file=sys.stderr, flush=True)


def backend_tcp_ready() -> bool:
    """Check if backend is accepting TCP connections."""
    try:
        with socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=0.5):
            return True
    except (OSError, socket.timeout):
        return False


async def backend_health_check() -> dict:
    """
    Check backend health via /health endpoint.
    Returns health status dict or error.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(BACKEND_HOST, BACKEND_PORT),
            timeout=HEALTH_TIMEOUT
        )
        
        request = f"GET /health HTTP/1.1\r\nHost: {BACKEND_HOST}:{BACKEND_PORT}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        
        response = await asyncio.wait_for(reader.read(4096), timeout=HEALTH_TIMEOUT)
        writer.close()
        await writer.wait_closed()
        
        # Parse response
        response_str = response.decode('utf-8', errors='replace')
        
        # Extract status code
        first_line = response_str.split('\r\n')[0]
        status_code = int(first_line.split()[1]) if len(first_line.split()) > 1 else 0
        
        # Extract body (after \r\n\r\n)
        if '\r\n\r\n' in response_str:
            body = response_str.split('\r\n\r\n', 1)[1]
            try:
                return {"status": "ok", "code": status_code, "backend": json.loads(body)}
            except json.JSONDecodeError:
                return {"status": "ok", "code": status_code, "backend_raw": body[:200]}
        
        return {"status": "ok", "code": status_code}
        
    except asyncio.TimeoutError:
        return {"status": "timeout", "error": "Backend health check timed out"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def handle_ping(writer: asyncio.StreamWriter):
    """
    Handle /ping endpoint for RunPod health checks.
    Returns 200 if backend is ready, 204 if still initializing.
    """
    if backend_tcp_ready():
        response = "HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    else:
        response = "HTTP/1.1 204 No Content\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    
    writer.write(response.encode())
    await writer.drain()


async def handle_health(writer: asyncio.StreamWriter):
    """Handle /health endpoint with detailed backend status."""
    health = await backend_health_check()
    health["gateway"] = {
        "status": "ok",
        "metrics": metrics.to_dict(),
    }
    
    body = json.dumps(health, indent=2)
    response = (
        f"HTTP/1.1 200 OK\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{body}"
    )
    writer.write(response.encode())
    await writer.drain()


async def handle_metrics(writer: asyncio.StreamWriter):
    """Handle /metrics endpoint."""
    body = json.dumps(metrics.to_dict(), indent=2)
    response = (
        f"HTTP/1.1 200 OK\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{body}"
    )
    writer.write(response.encode())
    await writer.drain()


async def proxy_request(
    method: str,
    path: str,
    headers: dict,
    body: Optional[bytes],
    writer: asyncio.StreamWriter
):
    """
    Proxy a request to the backend with streaming support.
    """
    metrics.requests_total += 1
    metrics.requests_active += 1
    
    try:
        # Connect to backend
        try:
            backend_reader, backend_writer = await asyncio.wait_for(
                asyncio.open_connection(BACKEND_HOST, BACKEND_PORT),
                timeout=5.0
            )
        except (asyncio.TimeoutError, OSError) as e:
            metrics.requests_error += 1
            error_response = "HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            writer.write(error_response.encode())
            await writer.drain()
            return
        
        # Build request to backend
        request_line = f"{method} {path} HTTP/1.1\r\n"
        
        # Forward headers, adjusting Host
        header_lines = [f"Host: {BACKEND_HOST}:{BACKEND_PORT}"]
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in ('host', 'connection', 'keep-alive', 'transfer-encoding'):
                continue
            header_lines.append(f"{key}: {value}")
        header_lines.append("Connection: close")
        
        request = request_line + "\r\n".join(header_lines) + "\r\n\r\n"
        backend_writer.write(request.encode())
        
        if body:
            backend_writer.write(body)
        
        await backend_writer.drain()
        
        # Read and forward response headers
        response_headers = b""
        while True:
            line = await asyncio.wait_for(
                backend_reader.readline(),
                timeout=REQUEST_TIMEOUT
            )
            response_headers += line
            if line == b"\r\n" or line == b"":
                break
        
        # Send headers to client
        writer.write(response_headers)
        await writer.drain()
        
        # Stream response body
        bytes_sent = 0
        try:
            while True:
                chunk = await asyncio.wait_for(
                    backend_reader.read(8192),
                    timeout=REQUEST_TIMEOUT
                )
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
        
    except Exception as e:
        metrics.requests_error += 1
        log(f"Proxy error: {e}")
        try:
            error_response = "HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            writer.write(error_response.encode())
            await writer.drain()
        except:
            pass
    
    finally:
        metrics.requests_active -= 1


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle an incoming client connection."""
    try:
        # Read request line
        request_line = await asyncio.wait_for(reader.readline(), timeout=30)
        if not request_line:
            return
        
        request_line = request_line.decode('utf-8', errors='replace').strip()
        parts = request_line.split()
        if len(parts) < 2:
            return
        
        method = parts[0]
        path = parts[1]
        
        # Read headers
        headers = {}
        content_length = 0
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=30)
            if line == b"\r\n" or line == b"":
                break
            line = line.decode('utf-8', errors='replace').strip()
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
                if key.lower() == 'content-length':
                    content_length = int(value.strip())
        
        # Read body if present
        body = None
        if content_length > 0:
            body = await asyncio.wait_for(
                reader.readexactly(content_length),
                timeout=30
            )
        
        # Route request
        if path == "/ping":
            await handle_ping(writer)
        elif path == "/health":
            await handle_health(writer)
        elif path == "/metrics":
            await handle_metrics(writer)
        else:
            # Proxy to backend
            await proxy_request(method, path, headers, body, writer)
    
    except asyncio.TimeoutError:
        pass
    except Exception as e:
        log(f"Client handler error: {e}")
    
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass


async def main():
    """Start the gateway server."""
    log(f"Starting gateway on {GATEWAY_HOST}:{GATEWAY_PORT}")
    log(f"Backend: {BACKEND_HOST}:{BACKEND_PORT}")
    log(f"Request timeout: {REQUEST_TIMEOUT}s")
    
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
    log("Endpoints: /ping, /health, /metrics, /v1/*")
    
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
