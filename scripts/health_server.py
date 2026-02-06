#!/usr/bin/env python3
"""
health_server.py — Ultra-lightweight health check server for RunPod

This server runs on PORT_HEALTH (separate from the main gateway) and provides
a minimal health check endpoint that doesn't interact with the backend.

This prevents RunPod's periodic health checks from keeping the worker "active"
and allows proper scale-to-zero behavior in serverless environments.

Environment Variables:
    PORT_HEALTH - Port to listen on (default: 8001)
"""

import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


PORT = int(os.environ.get("PORT_HEALTH", "8001"))


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal health check handler - just returns 200 OK."""

    def do_GET(self):
        """Handle GET requests - all paths return 200."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress request logging to reduce noise."""
        pass


def main():
    """Start the health server."""
    print(f"[health] Starting health server on 0.0.0.0:{PORT}", file=sys.stderr, flush=True)

    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[health] Interrupted", file=sys.stderr)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
