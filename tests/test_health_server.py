"""Unit tests for scripts/health_server.py -- Health check server."""

import io
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import health_server  # noqa: E402


class TestHealthHandler:
    """Tests for the HealthHandler HTTP request handler."""

    def _make_handler(self):
        """Create a HealthHandler instance with mocked socket infrastructure."""
        handler = health_server.HealthHandler.__new__(health_server.HealthHandler)
        handler.rfile = io.BytesIO(b"")
        handler.wfile = io.BytesIO()
        handler.requestline = "GET / HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.command = "GET"
        handler.client_address = ("127.0.0.1", 12345)
        handler.server = MagicMock()
        handler.headers = {}
        handler._headers_buffer = []
        handler.responses = {200: ("OK", "Request fulfilled")}
        return handler

    def test_do_get_returns_200(self):
        """GET request returns 200 OK with empty body."""
        handler = self._make_handler()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.do_GET()
        handler.send_response.assert_called_once_with(200)
        handler.send_header.assert_any_call("Content-Type", "text/plain")
        handler.send_header.assert_any_call("Content-Length", "0")
        handler.end_headers.assert_called_once()

    def test_do_get_content_type(self):
        """GET response Content-Type is text/plain."""
        handler = self._make_handler()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.do_GET()
        calls = handler.send_header.call_args_list
        content_type_calls = [c for c in calls if c[0][0] == "Content-Type"]
        assert len(content_type_calls) == 1
        assert content_type_calls[0][0][1] == "text/plain"

    def test_do_get_content_length_zero(self):
        """GET response Content-Length is 0."""
        handler = self._make_handler()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.do_GET()
        calls = handler.send_header.call_args_list
        cl_calls = [c for c in calls if c[0][0] == "Content-Length"]
        assert len(cl_calls) == 1
        assert cl_calls[0][0][1] == "0"

    def test_log_message_suppressed(self):
        """Log_message is a no-op (suppress logging)."""
        handler = self._make_handler()
        handler.log_message("GET / HTTP/1.1 200 -")
        handler.log_message("%s %s", "test", "message")


class TestHealthServerMain:
    """Tests for the main() function."""

    def test_main_starts_server(self):
        """Main creates and starts an HTTPServer."""
        with patch("health_server.HTTPServer") as mock_server_cls:
            mock_server = MagicMock()
            mock_server_cls.return_value = mock_server
            mock_server.serve_forever.side_effect = KeyboardInterrupt()
            health_server.main()
            mock_server_cls.assert_called_once_with(
                ("0.0.0.0", health_server.PORT), health_server.HealthHandler
            )
            mock_server.serve_forever.assert_called_once()
            mock_server.server_close.assert_called_once()

    def test_main_prints_startup_message(self, capsys):
        """Main prints startup message to stderr."""
        with patch("health_server.HTTPServer") as mock_server_cls:
            mock_server = MagicMock()
            mock_server_cls.return_value = mock_server
            mock_server.serve_forever.side_effect = KeyboardInterrupt()
            health_server.main()
            captured = capsys.readouterr()
            assert "[health] Starting health server" in captured.err

    def test_main_handles_keyboard_interrupt(self, capsys):
        """Main handles KeyboardInterrupt gracefully."""
        with patch("health_server.HTTPServer") as mock_server_cls:
            mock_server = MagicMock()
            mock_server_cls.return_value = mock_server
            mock_server.serve_forever.side_effect = KeyboardInterrupt()
            health_server.main()
            captured = capsys.readouterr()
            assert "[health] Interrupted" in captured.err
            mock_server.server_close.assert_called_once()

    def test_main_always_closes_server(self):
        """Server_close is called even if serve_forever raises."""
        with patch("health_server.HTTPServer") as mock_server_cls:
            mock_server = MagicMock()
            mock_server_cls.return_value = mock_server
            mock_server.serve_forever.side_effect = KeyboardInterrupt()
            health_server.main()
            mock_server.server_close.assert_called_once()


class TestHealthServerModuleConfig:
    """Tests for module-level configuration."""

    def test_default_port(self, monkeypatch):
        """Default PORT is 8001 when PORT_HEALTH is not set."""
        monkeypatch.delenv("PORT_HEALTH", raising=False)
        assert int(os.environ.get("PORT_HEALTH", "8001")) == 8001

    def test_custom_port_from_env(self, monkeypatch):
        """PORT is configurable via PORT_HEALTH env var."""
        monkeypatch.setenv("PORT_HEALTH", "9999")
        assert int(os.environ.get("PORT_HEALTH", "8001")) == 9999
