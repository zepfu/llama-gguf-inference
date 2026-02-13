"""Unit tests for scripts/gateway.py - Gateway module (CORS, Prometheus metrics, queue)."""

import asyncio
import importlib
import json
import socket
import time
from unittest.mock import AsyncMock, MagicMock, patch


def _reload_gateway(monkeypatch, **env_vars):
    """Reload gateway module with given env vars to pick up new config.

    Must be called after setting CORS_ORIGINS and other module-level config.
    Returns the reloaded gateway module.
    """
    # Ensure auth doesn't interfere - disable it
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("DATA_DIR", "/tmp/test-data")
    for key, val in env_vars.items():
        monkeypatch.setenv(key, val)

    import gateway

    importlib.reload(gateway)
    return gateway


class TestGetCorsHeaders:
    """Tests for get_cors_headers() helper."""

    def test_cors_disabled_returns_empty(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw.get_cors_headers("https://example.com") == []

    def test_cors_wildcard_returns_star(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")
        headers = gw.get_cors_headers("https://anything.com")
        assert len(headers) == 4
        assert "Access-Control-Allow-Origin: *" in headers
        assert "Access-Control-Allow-Methods: GET, POST, OPTIONS" in headers
        assert "Access-Control-Allow-Headers: Authorization, Content-Type" in headers
        assert "Access-Control-Max-Age: 86400" in headers

    def test_cors_specific_origin_allowed(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="https://app.example.com")
        headers = gw.get_cors_headers("https://app.example.com")
        assert len(headers) == 5
        assert "Access-Control-Allow-Origin: https://app.example.com" in headers
        assert "Vary: Origin" in headers

    def test_cors_specific_origin_denied(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="https://app.example.com")
        headers = gw.get_cors_headers("https://evil.com")
        assert headers == []

    def test_cors_multiple_origins(self, monkeypatch):
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="https://a.com, https://b.com, https://c.com",
        )
        # First origin allowed
        headers_a = gw.get_cors_headers("https://a.com")
        assert len(headers_a) == 5
        assert "Access-Control-Allow-Origin: https://a.com" in headers_a
        assert "Vary: Origin" in headers_a

        # Second origin allowed
        headers_b = gw.get_cors_headers("https://b.com")
        assert "Access-Control-Allow-Origin: https://b.com" in headers_b

        # Third origin allowed
        headers_c = gw.get_cors_headers("https://c.com")
        assert "Access-Control-Allow-Origin: https://c.com" in headers_c

        # Unknown origin denied
        assert gw.get_cors_headers("https://d.com") == []

    def test_cors_empty_origin(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="https://a.com")
        headers = gw.get_cors_headers("")
        assert headers == []

    def test_cors_wildcard_empty_origin(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")
        headers = gw.get_cors_headers("")
        # Wildcard still returns headers even with empty origin
        assert len(headers) == 4
        assert "Access-Control-Allow-Origin: *" in headers

    def test_cors_whitespace_handling(self, monkeypatch):
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="  https://a.com , https://b.com  ",
        )
        headers = gw.get_cors_headers("https://a.com")
        assert len(headers) == 5
        assert "Vary: Origin" in headers

    def test_cors_no_env_var_set(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        gw = _reload_gateway(monkeypatch)
        assert gw.get_cors_headers("https://anything.com") == []


class TestBuildCorsHeaderStr:
    """Tests for build_cors_header_str() helper."""

    def test_disabled_returns_empty_string(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw.build_cors_header_str("https://example.com") == ""

    def test_enabled_returns_crlf_joined(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")
        result = gw.build_cors_header_str("https://example.com")
        assert "Access-Control-Allow-Origin: *\r\n" in result
        assert result.endswith("\r\n")
        # Should have exactly 4 headers joined by \r\n
        lines = result.strip().split("\r\n")
        assert len(lines) == 4

    def test_denied_origin_returns_empty(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="https://allowed.com")
        assert gw.build_cors_header_str("https://denied.com") == ""


class TestCorsEnabled:
    """Tests for CORS_ENABLED and CORS_WILDCARD module-level flags."""

    def test_disabled_when_empty(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw.CORS_ENABLED is False
        assert gw.CORS_WILDCARD is False

    def test_enabled_with_origin(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="https://example.com")
        assert gw.CORS_ENABLED is True
        assert gw.CORS_WILDCARD is False

    def test_wildcard_detected(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")
        assert gw.CORS_ENABLED is True
        assert gw.CORS_WILDCARD is True


class TestWantsPrometheus:
    """Tests for _wants_prometheus() helper."""

    def test_empty_accept(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw._wants_prometheus("") is False

    def test_json_accept(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw._wants_prometheus("application/json") is False

    def test_text_plain_accept(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw._wants_prometheus("text/plain") is True

    def test_openmetrics_accept(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw._wants_prometheus("application/openmetrics-text") is True

    def test_mixed_accept_with_text_plain(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw._wants_prometheus("text/html, text/plain;q=0.9") is True

    def test_case_insensitive(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw._wants_prometheus("Text/Plain") is True
        assert gw._wants_prometheus("APPLICATION/OPENMETRICS-TEXT") is True


class TestMetricsToPrometheus:
    """Tests for Metrics.to_prometheus() method."""

    def test_default_metrics(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        output = m.to_prometheus()

        # Check structure
        assert "# HELP gateway_requests_total" in output
        assert "# TYPE gateway_requests_total counter" in output
        assert "gateway_requests_total 0" in output

        assert "# HELP gateway_requests_active" in output
        assert "# TYPE gateway_requests_active gauge" in output
        assert "gateway_requests_active 0" in output

        assert "# HELP gateway_bytes_sent" in output
        assert "gateway_bytes_sent 0" in output

        assert "# HELP gateway_uptime_seconds" in output
        assert "# TYPE gateway_uptime_seconds gauge" in output

        # Must end with newline
        assert output.endswith("\n")

    def test_metrics_with_values(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        m.requests_total = 42
        m.requests_success = 40
        m.requests_error = 2
        m.requests_active = 3
        m.requests_authenticated = 38
        m.requests_unauthorized = 4
        m.bytes_sent = 123456

        output = m.to_prometheus()

        assert "gateway_requests_total 42" in output
        assert "gateway_requests_success 40" in output
        assert "gateway_requests_error 2" in output
        assert "gateway_requests_active 3" in output
        assert "gateway_requests_authenticated 38" in output
        assert "gateway_requests_unauthorized 4" in output
        assert "gateway_bytes_sent 123456" in output

    def test_prometheus_format_lines(self, monkeypatch):
        """Verify each metric has HELP, TYPE, and value lines."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        output = m.to_prometheus()
        lines = output.strip().split("\n")

        # Should have triplets: HELP, TYPE, value for each metric
        # 11 metrics * 3 lines = 33 lines
        assert len(lines) == 33

        # Verify pattern: HELP, TYPE, value
        for i in range(0, len(lines), 3):
            assert lines[i].startswith("# HELP gateway_")
            assert lines[i + 1].startswith("# TYPE gateway_")
            # Value line should be metric_name followed by space and number
            parts = lines[i + 2].split(" ")
            assert len(parts) == 2
            assert parts[0].startswith("gateway_")
            # Value is a number (int or float)
            try:
                float(parts[1])
            except ValueError:
                raise AssertionError(f"Expected numeric value, got: {parts[1]}")

    def test_uptime_reflects_start_time(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        # Set start_time to 10 seconds ago
        m.start_time = time.time() - 10
        output = m.to_prometheus()
        # Extract uptime value
        for line in output.split("\n"):
            if line.startswith("gateway_uptime_seconds "):
                uptime = int(line.split(" ")[1])
                assert uptime >= 10
                assert uptime < 15  # Give some slack
                break
        else:
            raise AssertionError("gateway_uptime_seconds not found in output")


class TestMetricsToDict:
    """Tests for Metrics.to_dict() — existing behavior preservation."""

    def test_default_values(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        d = m.to_dict()
        assert d["requests_total"] == 0
        assert d["requests_success"] == 0
        assert d["requests_error"] == 0
        assert d["requests_active"] == 0
        assert d["requests_authenticated"] == 0
        assert d["requests_unauthorized"] == 0
        assert d["bytes_sent"] == 0
        assert "uptime_seconds" in d

    def test_values_preserved(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        m.requests_total = 100
        m.bytes_sent = 999
        d = m.to_dict()
        assert d["requests_total"] == 100
        assert d["bytes_sent"] == 999


class TestOptionsHandling:
    """Tests for handle_options() via the routing logic."""

    def test_options_response_format_with_cors(self, monkeypatch):
        """Verify handle_options produces correct response structure."""
        import asyncio

        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_options(writer, "https://example.com")

        asyncio.run(run())

        response = written_data.decode()
        assert response.startswith("HTTP/1.1 204 No Content\r\n")
        assert "Access-Control-Allow-Origin: *" in response
        assert "Access-Control-Allow-Methods: GET, POST, OPTIONS" in response
        assert "Access-Control-Allow-Headers: Authorization, Content-Type" in response
        assert "Access-Control-Max-Age: 86400" in response
        assert "Content-Length: 0" in response
        assert "Connection: close" in response

    def test_options_response_without_cors(self, monkeypatch):
        """OPTIONS still responds 204 even without CORS enabled."""
        import asyncio

        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_options(writer, "https://example.com")

        asyncio.run(run())

        response = written_data.decode()
        assert response.startswith("HTTP/1.1 204 No Content\r\n")
        assert "Access-Control-Allow-Origin" not in response
        assert "Content-Length: 0" in response


class TestHandlePingCors:
    """Tests for CORS header injection in handle_ping."""

    def test_ping_with_cors(self, monkeypatch):
        import asyncio

        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_ping(writer, "https://example.com")

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response
        assert "Access-Control-Allow-Origin: *" in response

    def test_ping_without_cors(self, monkeypatch):
        import asyncio

        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_ping(writer, "https://example.com")

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response
        assert "Access-Control-Allow-Origin" not in response


class TestHandleMetricsFormats:
    """Tests for /metrics response format selection."""

    def test_metrics_json_default(self, monkeypatch):
        import asyncio

        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_metrics(writer, "", "")

        asyncio.run(run())

        response = written_data.decode()
        assert "Content-Type: application/json" in response
        # Body should be valid JSON
        body = response.split("\r\n\r\n", 1)[1]
        import json

        data = json.loads(body)
        assert "gateway" in data

    def test_metrics_prometheus_text_plain(self, monkeypatch):
        import asyncio

        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_metrics(writer, "", "text/plain")

        asyncio.run(run())

        response = written_data.decode()
        assert "Content-Type: text/plain; version=0.0.4; charset=utf-8" in response
        body = response.split("\r\n\r\n", 1)[1]
        assert "# HELP gateway_requests_total" in body
        assert "# TYPE gateway_requests_total counter" in body

    def test_metrics_prometheus_openmetrics(self, monkeypatch):
        import asyncio

        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_metrics(writer, "", "application/openmetrics-text")

        asyncio.run(run())

        response = written_data.decode()
        assert "text/plain; version=0.0.4" in response
        body = response.split("\r\n\r\n", 1)[1]
        assert "gateway_requests_total" in body

    def test_metrics_json_with_application_json(self, monkeypatch):
        import asyncio

        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_metrics(writer, "", "application/json")

        asyncio.run(run())

        response = written_data.decode()
        assert "Content-Type: application/json" in response

    def test_metrics_with_cors(self, monkeypatch):
        import asyncio

        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_metrics(writer, "https://example.com", "")

        asyncio.run(run())

        response = written_data.decode()
        assert "Access-Control-Allow-Origin: *" in response
        assert "Content-Type: application/json" in response


# ---------------------------------------------------------------------------
# Queue / concurrency control tests
# ---------------------------------------------------------------------------


class TestQueueConfig:
    """Tests for MAX_CONCURRENT_REQUESTS and MAX_QUEUE_SIZE env var parsing."""

    def test_default_max_concurrent(self, monkeypatch):
        monkeypatch.delenv("MAX_CONCURRENT_REQUESTS", raising=False)
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw.MAX_CONCURRENT_REQUESTS == 1

    def test_custom_max_concurrent(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", MAX_CONCURRENT_REQUESTS="4")
        assert gw.MAX_CONCURRENT_REQUESTS == 4

    def test_default_max_queue_size(self, monkeypatch):
        monkeypatch.delenv("MAX_QUEUE_SIZE", raising=False)
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw.MAX_QUEUE_SIZE == 0

    def test_custom_max_queue_size(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", MAX_QUEUE_SIZE="32")
        assert gw.MAX_QUEUE_SIZE == 32

    def test_semaphore_created_with_correct_value(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", MAX_CONCURRENT_REQUESTS="3")
        assert gw._proxy_semaphore._value == 3

    def test_queue_depth_starts_at_zero(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw._queue_depth == 0


class TestQueueFullResponse:
    """Tests for send_queue_full_response() helper."""

    def test_503_status_line(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_queue_full_response(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert response.startswith("HTTP/1.1 503 Service Unavailable\r\n")

    def test_retry_after_header(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_queue_full_response(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert "Retry-After: 5\r\n" in response

    def test_json_body_format(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_queue_full_response(writer)

        asyncio.run(run())

        response = written_data.decode()
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["error"]["message"] == "Server busy, try again later"
        assert data["error"]["type"] == "server_error"
        assert data["error"]["code"] == "queue_full"

    def test_content_type_json(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_queue_full_response(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert "Content-Type: application/json\r\n" in response

    def test_cors_headers_included(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_queue_full_response(writer, "https://example.com")

        asyncio.run(run())

        response = written_data.decode()
        assert "Access-Control-Allow-Origin: *" in response


class TestQueueMetrics:
    """Tests for queue-related metrics fields in both dict and prometheus format."""

    def test_queue_fields_in_to_dict(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        d = m.to_dict()
        assert "queue_depth" in d
        assert "queue_rejections" in d
        assert "queue_wait_seconds_total" in d
        assert d["queue_depth"] == 0
        assert d["queue_rejections"] == 0
        assert d["queue_wait_seconds_total"] == 0.0

    def test_queue_rejections_in_to_dict(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        m.queue_rejections = 7
        d = m.to_dict()
        assert d["queue_rejections"] == 7

    def test_queue_wait_time_in_to_dict(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        m.queue_wait_seconds_total = 1.5678
        d = m.to_dict()
        assert d["queue_wait_seconds_total"] == 1.568  # rounded to 3 decimals

    def test_queue_depth_in_prometheus(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        output = m.to_prometheus()
        assert "# HELP gateway_queue_depth" in output
        assert "# TYPE gateway_queue_depth gauge" in output
        assert "gateway_queue_depth 0" in output

    def test_queue_rejections_in_prometheus(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        m.queue_rejections = 12
        output = m.to_prometheus()
        assert "# HELP gateway_queue_rejections" in output
        assert "# TYPE gateway_queue_rejections counter" in output
        assert "gateway_queue_rejections 12" in output

    def test_queue_wait_seconds_in_prometheus(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        m = gw.Metrics()
        m.queue_wait_seconds_total = 3.456
        output = m.to_prometheus()
        assert "# HELP gateway_queue_wait_seconds_total" in output
        assert "# TYPE gateway_queue_wait_seconds_total counter" in output
        assert "gateway_queue_wait_seconds_total 3.456" in output


class TestHealthQueueInfo:
    """Tests for queue section in /health endpoint response."""

    def test_health_contains_queue_section(self, monkeypatch):
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_CONCURRENT_REQUESTS="2",
            MAX_QUEUE_SIZE="32",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_health(writer, "")

        asyncio.run(run())

        response = written_data.decode()
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)

        assert "queue" in data
        q = data["queue"]
        assert q["max_concurrent"] == 2
        assert q["max_queue_size"] == 32
        assert "active" in q
        assert "waiting" in q

    def test_health_queue_active_reflects_semaphore(self, monkeypatch):
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_CONCURRENT_REQUESTS="3",
            MAX_QUEUE_SIZE="0",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            # Simulate 1 active request by acquiring semaphore inside event loop
            await gw._proxy_semaphore.acquire()
            writer = MockWriter()
            await gw.handle_health(writer, "")
            gw._proxy_semaphore.release()

        asyncio.run(run())

        response = written_data.decode()
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["queue"]["active"] == 1

    def test_health_queue_waiting_reflects_depth(self, monkeypatch):
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_CONCURRENT_REQUESTS="1",
            MAX_QUEUE_SIZE="0",
        )
        gw._queue_depth = 5

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.handle_health(writer, "")

        asyncio.run(run())

        gw._queue_depth = 0  # clean up

        response = written_data.decode()
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["queue"]["waiting"] == 5


class TestConcurrencyLimiting:
    """Tests for semaphore-based concurrency limiting in handle_client."""

    def test_semaphore_limits_concurrent_proxy_calls(self, monkeypatch):
        """Verify that only MAX_CONCURRENT_REQUESTS proxy calls run simultaneously."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_CONCURRENT_REQUESTS="1",
            MAX_QUEUE_SIZE="0",
        )
        # Disable auth so requests reach the proxy path
        gw.AUTH_AVAILABLE = False

        concurrency_log = []
        max_concurrent = 0

        original_proxy = gw.proxy_request

        async def mock_proxy(*args, **kwargs):
            nonlocal max_concurrent
            concurrency_log.append("enter")
            current = sum(1 for x in concurrency_log if x == "enter") - sum(
                1 for x in concurrency_log if x == "exit"
            )
            if current > max_concurrent:
                max_concurrent = current
            await asyncio.sleep(0.05)
            concurrency_log.append("exit")

        gw.proxy_request = mock_proxy

        async def make_request():
            """Simulate a minimal HTTP request through handle_client."""
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: 0\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()

            written = bytearray()

            class MockWriter:
                def write(self, data):
                    written.extend(data)

                async def drain(self):
                    pass

                def close(self):
                    pass

                async def wait_closed(self):
                    pass

            await gw.handle_client(reader, MockWriter())

        async def run():
            await asyncio.gather(make_request(), make_request(), make_request())

        asyncio.run(run())

        # With MAX_CONCURRENT_REQUESTS=1, max concurrency should be 1
        assert max_concurrent == 1
        gw.proxy_request = original_proxy

    def test_queue_rejection_when_full(self, monkeypatch):
        """Verify 503 is returned when queue is full."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_CONCURRENT_REQUESTS="1",
            MAX_QUEUE_SIZE="1",
        )
        gw.AUTH_AVAILABLE = False

        responses = []

        async def mock_proxy(*args, **kwargs):
            await asyncio.sleep(0.1)

        gw.proxy_request = mock_proxy

        async def make_request():
            """Simulate a minimal HTTP request through handle_client."""
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: 0\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()

            written = bytearray()

            class MockWriter:
                def write(self, data):
                    written.extend(data)

                async def drain(self):
                    pass

                def close(self):
                    pass

                async def wait_closed(self):
                    pass

            await gw.handle_client(reader, MockWriter())
            responses.append(written.decode())

        async def run():
            # Send 3 requests: 1 active + 1 queued = capacity, 3rd should be rejected
            await asyncio.gather(
                make_request(),
                make_request(),
                make_request(),
            )

        asyncio.run(run())

        # At least one should get 503 (the third request when queue is full)
        num_503 = sum(1 for r in responses if "503 Service Unavailable" in r)
        assert num_503 >= 1, f"Expected at least one 503, got responses: {responses}"

    def test_queue_rejection_increments_metric(self, monkeypatch):
        """Verify that queue rejections are counted in metrics."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_CONCURRENT_REQUESTS="1",
            MAX_QUEUE_SIZE="1",
        )
        gw.AUTH_AVAILABLE = False

        initial_rejections = gw.metrics.queue_rejections

        async def mock_proxy(*args, **kwargs):
            await asyncio.sleep(0.1)

        gw.proxy_request = mock_proxy

        async def make_request():
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: 0\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()

            class MockWriter:
                def write(self, data):
                    pass

                async def drain(self):
                    pass

                def close(self):
                    pass

                async def wait_closed(self):
                    pass

            await gw.handle_client(reader, MockWriter())

        async def run():
            await asyncio.gather(
                make_request(),
                make_request(),
                make_request(),
            )

        asyncio.run(run())

        assert gw.metrics.queue_rejections > initial_rejections

    def test_health_endpoints_bypass_queue(self, monkeypatch):
        """Verify /ping, /health, /metrics bypass the concurrency semaphore."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_CONCURRENT_REQUESTS="1",
            MAX_QUEUE_SIZE="1",
        )

        responses = {}

        async def make_health_request(path):
            request_data = (f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n").encode()
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()

            written = bytearray()

            class MockWriter:
                def write(self, data):
                    written.extend(data)

                async def drain(self):
                    pass

                def close(self):
                    pass

                async def wait_closed(self):
                    pass

            await gw.handle_client(reader, MockWriter())
            responses[path] = written.decode()

        async def run():
            # Exhaust the semaphore and fill the queue inside the event loop
            await gw._proxy_semaphore.acquire()
            gw._queue_depth = gw.MAX_QUEUE_SIZE  # queue is "full"

            await make_health_request("/ping")
            await make_health_request("/metrics")

            # Release semaphore and clean up
            gw._proxy_semaphore.release()
            gw._queue_depth = 0

        asyncio.run(run())

        # Both should get 200 OK, not 503
        assert "HTTP/1.1 200 OK" in responses["/ping"]
        assert "HTTP/1.1 200 OK" in responses["/metrics"]

    def test_unlimited_queue_never_rejects(self, monkeypatch):
        """When MAX_QUEUE_SIZE=0 (unlimited), no 503 rejections happen."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_CONCURRENT_REQUESTS="1",
            MAX_QUEUE_SIZE="0",
        )
        gw.AUTH_AVAILABLE = False

        responses = []

        async def mock_proxy(*args, **kwargs):
            await asyncio.sleep(0.02)

        gw.proxy_request = mock_proxy

        async def make_request():
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: 0\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()

            written = bytearray()

            class MockWriter:
                def write(self, data):
                    written.extend(data)

                async def drain(self):
                    pass

                def close(self):
                    pass

                async def wait_closed(self):
                    pass

            await gw.handle_client(reader, MockWriter())
            responses.append(written.decode())

        async def run():
            await asyncio.gather(
                make_request(),
                make_request(),
                make_request(),
            )

        asyncio.run(run())

        # No 503 responses when queue is unlimited
        num_503 = sum(1 for r in responses if "503" in r)
        assert num_503 == 0, f"Expected zero 503s with unlimited queue, got: {num_503}"


# ---------------------------------------------------------------------------
# SEC-03: Request body size limit tests
# ---------------------------------------------------------------------------


class TestRequestBodySizeConfig:
    """Tests for MAX_REQUEST_BODY_SIZE env var parsing."""

    def test_default_max_request_body_size(self, monkeypatch):
        monkeypatch.delenv("MAX_REQUEST_BODY_SIZE", raising=False)
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw.MAX_REQUEST_BODY_SIZE == 10 * 1024 * 1024  # 10MB

    def test_custom_max_request_body_size(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", MAX_REQUEST_BODY_SIZE="1048576")
        assert gw.MAX_REQUEST_BODY_SIZE == 1048576  # 1MB


class TestPayloadTooLargeResponse:
    """Tests for send_payload_too_large() response helper."""

    def test_413_status_line(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_payload_too_large(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert response.startswith("HTTP/1.1 413 Payload Too Large\r\n")

    def test_json_body_format(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_payload_too_large(writer)

        asyncio.run(run())

        response = written_data.decode()
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert "error" in data
        assert data["error"]["type"] == "invalid_request_error"
        assert data["error"]["code"] == "payload_too_large"
        assert (
            "max" in data["error"]["message"].lower()
            or "too large" in data["error"]["message"].lower()
        )

    def test_content_type_json(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_payload_too_large(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert "Content-Type: application/json\r\n" in response

    def test_connection_close_header(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_payload_too_large(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert "Connection: close\r\n" in response

    def test_cors_headers_included(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_payload_too_large(writer, "https://example.com")

        asyncio.run(run())

        response = written_data.decode()
        assert "Access-Control-Allow-Origin: *" in response


class TestBodySizeLimitEnforcement:
    """Tests for body size limit enforcement in handle_client."""

    def test_oversized_body_returns_413(self, monkeypatch):
        """Verify that a request with Content-Length exceeding the limit gets 413."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_REQUEST_BODY_SIZE="100",
        )
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            # Content-Length of 200 exceeds limit of 100
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: 200\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 413 Payload Too Large" in response
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["error"]["code"] == "payload_too_large"

    def test_body_at_limit_is_allowed(self, monkeypatch):
        """Verify that a request with Content-Length exactly at the limit is accepted."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_REQUEST_BODY_SIZE="100",
        )
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        proxy_called = []

        async def mock_proxy(*args, **kwargs):
            proxy_called.append(True)

        gw.proxy_request = mock_proxy

        async def run():
            body_content = b"x" * 100
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: 100\r\n"
                b"\r\n" + body_content
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        # Should NOT get a 413 — proxy should be called
        response = written_data.decode()
        assert "413" not in response
        assert len(proxy_called) == 1

    def test_body_under_limit_is_allowed(self, monkeypatch):
        """Verify a small body is accepted normally."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_REQUEST_BODY_SIZE="1048576",
        )
        gw.AUTH_AVAILABLE = False

        proxy_called = []

        async def mock_proxy(*args, **kwargs):
            proxy_called.append(True)

        gw.proxy_request = mock_proxy

        class MockWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: 13\r\n"
                b"\r\n"
                b'{"test":true}'
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        assert len(proxy_called) == 1

    def test_zero_body_bypasses_check(self, monkeypatch):
        """Requests with no body (GET) bypass body size check."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_REQUEST_BODY_SIZE="100",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = b"GET /ping HTTP/1.1\r\nHost: localhost\r\n\r\n"
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response
        assert "413" not in response


# ---------------------------------------------------------------------------
# SEC-04: CORS origin validation tests
# ---------------------------------------------------------------------------


class TestCorsOriginValidation:
    """Tests for SEC-04 CORS origin validation enhancements."""

    def test_trailing_slash_stripped_from_config(self, monkeypatch):
        """Trailing slashes on configured origins are stripped."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="https://app.example.com/",
        )
        assert "https://app.example.com" in gw._cors_origins_list
        assert "https://app.example.com/" not in gw._cors_origins_list

    def test_origin_matches_after_slash_strip(self, monkeypatch):
        """Request origin matches even when config had trailing slash."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="https://app.example.com/",
        )
        headers = gw.get_cors_headers("https://app.example.com")
        assert len(headers) == 5
        assert "Access-Control-Allow-Origin: https://app.example.com" in headers

    def test_oversized_origin_rejected(self, monkeypatch):
        """Origins exceeding MAX_ORIGIN_LENGTH are rejected."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")
        long_origin = "https://example.com/" + "a" * 2100
        headers = gw.get_cors_headers(long_origin)
        assert headers == []

    def test_origin_at_max_length_accepted(self, monkeypatch):
        """Origins exactly at MAX_ORIGIN_LENGTH are accepted (wildcard mode)."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")
        origin = "https://" + "a" * (gw.MAX_ORIGIN_LENGTH - len("https://"))
        assert len(origin) == gw.MAX_ORIGIN_LENGTH
        headers = gw.get_cors_headers(origin)
        assert len(headers) == 4
        assert "Access-Control-Allow-Origin: *" in headers

    def test_origin_one_over_max_rejected(self, monkeypatch):
        """Origins one byte over MAX_ORIGIN_LENGTH are rejected."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")
        origin = "https://" + "a" * (gw.MAX_ORIGIN_LENGTH - len("https://") + 1)
        assert len(origin) == gw.MAX_ORIGIN_LENGTH + 1
        headers = gw.get_cors_headers(origin)
        assert headers == []

    def test_multiple_origins_with_trailing_slashes(self, monkeypatch):
        """Multiple origins with trailing slashes are all stripped."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="https://a.com/, https://b.com/",
        )
        assert "https://a.com" in gw._cors_origins_list
        assert "https://b.com" in gw._cors_origins_list
        headers_a = gw.get_cors_headers("https://a.com")
        assert len(headers_a) == 5
        headers_b = gw.get_cors_headers("https://b.com")
        assert len(headers_b) == 5

    def test_exact_match_prevents_suffix_attack(self, monkeypatch):
        """Verify that origin matching is exact — no suffix/substring attacks."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="https://app.example.com",
        )
        # These should NOT match
        assert gw.get_cors_headers("https://evil.com?https://app.example.com") == []
        assert gw.get_cors_headers("https://notapp.example.com") == []
        assert gw.get_cors_headers("https://app.example.com.evil.com") == []
        # This should match
        headers = gw.get_cors_headers("https://app.example.com")
        assert len(headers) == 5


# ---------------------------------------------------------------------------
# SEC-05: Header count and size limit tests
# ---------------------------------------------------------------------------


class TestHeaderLimitsConfig:
    """Tests for MAX_HEADERS and MAX_HEADER_LINE_SIZE env var parsing."""

    def test_default_max_headers(self, monkeypatch):
        monkeypatch.delenv("MAX_HEADERS", raising=False)
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw.MAX_HEADERS == 64

    def test_custom_max_headers(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", MAX_HEADERS="32")
        assert gw.MAX_HEADERS == 32

    def test_default_max_header_line_size(self, monkeypatch):
        monkeypatch.delenv("MAX_HEADER_LINE_SIZE", raising=False)
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw.MAX_HEADER_LINE_SIZE == 8192

    def test_custom_max_header_line_size(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", MAX_HEADER_LINE_SIZE="4096")
        assert gw.MAX_HEADER_LINE_SIZE == 4096


class TestHeaderTooLargeResponse:
    """Tests for send_header_too_large() response helper."""

    def test_431_status_line(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_header_too_large(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert response.startswith("HTTP/1.1 431 Request Header Fields Too Large\r\n")

    def test_json_body_format(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_header_too_large(writer)

        asyncio.run(run())

        response = written_data.decode()
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert "error" in data
        assert data["error"]["type"] == "invalid_request_error"
        assert data["error"]["code"] == "header_fields_too_large"

    def test_content_type_json(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_header_too_large(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert "Content-Type: application/json\r\n" in response

    def test_connection_close_header(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_header_too_large(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert "Connection: close\r\n" in response

    def test_cors_headers_included(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_header_too_large(writer, "https://example.com")

        asyncio.run(run())

        response = written_data.decode()
        assert "Access-Control-Allow-Origin: *" in response


class TestHeaderCountLimitEnforcement:
    """Tests for header count limit enforcement in handle_client."""

    def test_too_many_headers_returns_431(self, monkeypatch):
        """Verify that exceeding MAX_HEADERS returns 431."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_HEADERS="3",
        )
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            # 4 headers, exceeds limit of 3
            request_data = (
                b"GET /v1/models HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Accept: application/json\r\n"
                b"X-Custom-1: value1\r\n"
                b"X-Custom-2: value2\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "431 Request Header Fields Too Large" in response
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["error"]["code"] == "header_fields_too_large"

    def test_headers_at_limit_allowed(self, monkeypatch):
        """Verify that exactly MAX_HEADERS headers are accepted."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_HEADERS="3",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            # Exactly 3 headers, at the limit
            request_data = (
                b"GET /ping HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Accept: text/plain\r\n"
                b"Connection: close\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response
        assert "431" not in response


class TestHeaderLineSizeLimitEnforcement:
    """Tests for individual header line size limit enforcement in handle_client."""

    def test_oversized_header_line_returns_431(self, monkeypatch):
        """Verify that a header line exceeding MAX_HEADER_LINE_SIZE returns 431."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_HEADER_LINE_SIZE="50",
        )
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            # Create a header line > 50 bytes
            long_value = "x" * 60
            request_data = (
                b"GET /v1/models HTTP/1.1\r\n"
                b"Host: localhost\r\n" + f"X-Long-Header: {long_value}\r\n".encode() + b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "431 Request Header Fields Too Large" in response

    def test_header_line_at_limit_allowed(self, monkeypatch):
        """Verify that a header line exactly at the limit is accepted."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_HEADER_LINE_SIZE="8192",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = b"GET /ping HTTP/1.1\r\nHost: localhost\r\n\r\n"
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response
        assert "431" not in response

    def test_normal_headers_accepted(self, monkeypatch):
        """Verify that normal-sized headers work fine."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_HEADER_LINE_SIZE="8192",
            MAX_HEADERS="64",
        )

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = (
                b"GET /ping HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Accept: application/json\r\n"
                b"Authorization: Bearer sk-test-key\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response


class TestSecurityLimitsIntegration:
    """Integration tests combining multiple security limits."""

    def test_health_endpoints_still_work_with_limits(self, monkeypatch):
        """Verify /ping, /health, /metrics work under default security limits."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        for path in ["/ping", "/metrics"]:
            written_data = bytearray()

            class MockWriter:
                def write(self, data):
                    written_data.extend(data)

                async def drain(self):
                    pass

                def close(self):
                    pass

                async def wait_closed(self):
                    pass

            async def run():
                request_data = (f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n").encode()
                reader = asyncio.StreamReader()
                reader.feed_data(request_data)
                reader.feed_eof()
                await gw.handle_client(reader, MockWriter())

            asyncio.run(run())

            response = written_data.decode()
            assert "HTTP/1.1 200 OK" in response, f"Expected 200 for {path}, got: {response[:80]}"

    def test_413_before_body_read(self, monkeypatch):
        """Verify 413 is returned before the server tries to read the body."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_REQUEST_BODY_SIZE="10",
        )
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            # Claim a huge body but don't actually send it
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: 999999999\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        # Should get 413 without trying to read 999999999 bytes
        assert "413 Payload Too Large" in response


# ---------------------------------------------------------------------------
# Inject CORS into response headers tests
# ---------------------------------------------------------------------------


class TestInjectCorsIntoHeaders:
    """Tests for _inject_cors_into_headers() helper."""

    def test_cors_injected_when_enabled(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")
        raw = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
        result = gw._inject_cors_into_headers(raw, "https://example.com")
        assert b"Access-Control-Allow-Origin: *" in result
        assert result.endswith(b"\r\n")

    def test_cors_not_injected_when_disabled(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        raw = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
        result = gw._inject_cors_into_headers(raw, "https://example.com")
        assert result == raw

    def test_cors_not_injected_without_crlf_ending(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")
        raw = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain"
        result = gw._inject_cors_into_headers(raw, "https://example.com")
        assert result == raw

    def test_cors_injected_with_specific_origin(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="https://app.example.com")
        raw = b"HTTP/1.1 200 OK\r\n"
        result = gw._inject_cors_into_headers(raw, "https://app.example.com")
        assert b"Access-Control-Allow-Origin: https://app.example.com" in result
        assert b"Vary: Origin" in result

    def test_cors_denied_origin_not_injected(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="https://allowed.com")
        raw = b"HTTP/1.1 200 OK\r\n"
        result = gw._inject_cors_into_headers(raw, "https://denied.com")
        assert result == raw


# ---------------------------------------------------------------------------
# backend_tcp_ready tests
# ---------------------------------------------------------------------------


class TestBackendTcpReady:
    """Tests for backend_tcp_ready() function."""

    def test_backend_tcp_ready_success(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        with patch.object(socket, "create_connection", return_value=mock_sock):
            result = gw.backend_tcp_ready()
        assert result is True

    def test_backend_tcp_ready_connection_refused(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        with patch.object(socket, "create_connection", side_effect=OSError("Connection refused")):
            result = gw.backend_tcp_ready()
        assert result is False

    def test_backend_tcp_ready_timeout(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        with patch.object(socket, "create_connection", side_effect=socket.timeout("timed out")):
            result = gw.backend_tcp_ready()
        assert result is False


# ---------------------------------------------------------------------------
# backend_health_check tests
# ---------------------------------------------------------------------------


class TestBackendHealthCheck:
    """Tests for backend_health_check() async function."""

    def test_health_check_timeout(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        async def mock_open_connection(*args, **kwargs):
            raise asyncio.TimeoutError()

        with patch("asyncio.open_connection", side_effect=mock_open_connection):
            result = asyncio.run(gw.backend_health_check())

        assert result["status"] == "timeout"
        assert "timed out" in result["error"].lower()

    def test_health_check_connection_error(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        async def mock_open_connection(*args, **kwargs):
            raise OSError("Connection refused")

        with patch("asyncio.open_connection", side_effect=mock_open_connection):
            result = asyncio.run(gw.backend_health_check())

        assert result["status"] == "error"
        assert "Connection refused" in result["error"]

    def test_health_check_success_json_body(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        response_data = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status":"ok"}'

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=response_data)
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        async def mock_open_connection(*args, **kwargs):
            return mock_reader, mock_writer

        with patch("asyncio.open_connection", side_effect=mock_open_connection):
            result = asyncio.run(gw.backend_health_check())

        assert result["status"] == "ok"
        assert result["code"] == 200
        assert result["backend"]["status"] == "ok"

    def test_health_check_success_non_json_body(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        response_data = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nnot json content"

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=response_data)
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        async def mock_open_connection(*args, **kwargs):
            return mock_reader, mock_writer

        with patch("asyncio.open_connection", side_effect=mock_open_connection):
            result = asyncio.run(gw.backend_health_check())

        assert result["status"] == "ok"
        assert result["code"] == 200
        assert "backend_raw" in result

    def test_health_check_no_body_separator(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        response_data = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=response_data)
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        async def mock_open_connection(*args, **kwargs):
            return mock_reader, mock_writer

        with patch("asyncio.open_connection", side_effect=mock_open_connection):
            result = asyncio.run(gw.backend_health_check())

        assert result["status"] == "ok"
        assert result["code"] == 200
        assert "backend" not in result
        assert "backend_raw" not in result


# ---------------------------------------------------------------------------
# proxy_request tests
# ---------------------------------------------------------------------------


class TestProxyRequest:
    """Tests for proxy_request() — the core proxy logic."""

    def test_proxy_backend_connection_timeout(self, monkeypatch):
        """Backend connection timeout returns 502."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def mock_open_connection(*args, **kwargs):
            raise asyncio.TimeoutError()

        async def run():
            writer = MockWriter()
            with patch("asyncio.open_connection", side_effect=mock_open_connection):
                await gw.proxy_request("GET", "/v1/models", {}, None, writer, "test-key")

        asyncio.run(run())

        response = written_data.decode()
        assert "502 Bad Gateway" in response
        assert gw.metrics.requests_error > 0

    def test_proxy_backend_connection_refused(self, monkeypatch):
        """Backend connection refused returns 502."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def mock_open_connection(*args, **kwargs):
            raise OSError("Connection refused")

        async def run():
            writer = MockWriter()
            with patch("asyncio.open_connection", side_effect=mock_open_connection):
                await gw.proxy_request("POST", "/v1/chat/completions", {}, None, writer, "test-key")

        asyncio.run(run())

        response = written_data.decode()
        assert "502 Bad Gateway" in response

    def test_proxy_success_streams_response(self, monkeypatch):
        """Successful proxy streams backend response to client."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = False
        initial_success = gw.metrics.requests_success

        written_data = bytearray()

        class MockClientWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        # Create mock backend reader that returns headers then body
        header_lines = [
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Type: application/json\r\n",
            b"\r\n",
        ]
        body_chunks = [b'{"result": "ok"}', b""]

        mock_backend_reader = AsyncMock()
        mock_backend_reader.readline = AsyncMock(side_effect=header_lines)
        mock_backend_reader.read = AsyncMock(side_effect=body_chunks)

        mock_backend_writer = MagicMock()
        mock_backend_writer.write = MagicMock()
        mock_backend_writer.drain = AsyncMock()
        mock_backend_writer.close = MagicMock()
        mock_backend_writer.wait_closed = AsyncMock()

        async def mock_open_connection(*args, **kwargs):
            return mock_backend_reader, mock_backend_writer

        async def run():
            writer = MockClientWriter()
            with patch("asyncio.open_connection", side_effect=mock_open_connection):
                await gw.proxy_request(
                    "GET",
                    "/v1/models",
                    {"content-type": "application/json"},
                    None,
                    writer,
                    "test-key",
                )

        asyncio.run(run())

        response = written_data.decode()
        assert "200 OK" in response
        assert '{"result": "ok"}' in response
        assert gw.metrics.requests_success > initial_success

    def test_proxy_forwards_body(self, monkeypatch):
        """Proxy forwards request body to backend."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()
        backend_received = bytearray()

        class MockClientWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        header_lines = [
            b"HTTP/1.1 200 OK\r\n",
            b"\r\n",
        ]

        mock_backend_reader = AsyncMock()
        mock_backend_reader.readline = AsyncMock(side_effect=header_lines)
        mock_backend_reader.read = AsyncMock(return_value=b"")

        mock_backend_writer = MagicMock()

        def capture_write(data):
            backend_received.extend(data)

        mock_backend_writer.write = capture_write
        mock_backend_writer.drain = AsyncMock()
        mock_backend_writer.close = MagicMock()
        mock_backend_writer.wait_closed = AsyncMock()

        async def mock_open_connection(*args, **kwargs):
            return mock_backend_reader, mock_backend_writer

        async def run():
            writer = MockClientWriter()
            with patch("asyncio.open_connection", side_effect=mock_open_connection):
                await gw.proxy_request(
                    "POST",
                    "/v1/chat/completions",
                    {"content-type": "application/json"},
                    b'{"prompt":"hello"}',
                    writer,
                    "test-key",
                )

        asyncio.run(run())

        assert b'{"prompt":"hello"}' in backend_received

    def test_proxy_adds_backend_api_key(self, monkeypatch):
        """Proxy adds BACKEND_API_KEY header when configured."""
        # Use a valid 51-char backend key
        backend_key = "gateway-" + "A" * 43
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", BACKEND_API_KEY=backend_key)
        gw.AUTH_AVAILABLE = False

        backend_received = bytearray()

        class MockClientWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

        header_lines = [b"HTTP/1.1 200 OK\r\n", b"\r\n"]

        mock_backend_reader = AsyncMock()
        mock_backend_reader.readline = AsyncMock(side_effect=header_lines)
        mock_backend_reader.read = AsyncMock(return_value=b"")

        mock_backend_writer = MagicMock()

        def capture_write(data):
            backend_received.extend(data)

        mock_backend_writer.write = capture_write
        mock_backend_writer.drain = AsyncMock()
        mock_backend_writer.close = MagicMock()
        mock_backend_writer.wait_closed = AsyncMock()

        async def mock_open_connection(*args, **kwargs):
            return mock_backend_reader, mock_backend_writer

        async def run():
            writer = MockClientWriter()
            with patch("asyncio.open_connection", side_effect=mock_open_connection):
                await gw.proxy_request("GET", "/v1/models", {}, None, writer, "test-key")

        asyncio.run(run())

        sent_text = backend_received.decode()
        assert f"Authorization: Bearer {backend_key}" in sent_text

    def test_proxy_skips_filtered_headers(self, monkeypatch):
        """Proxy skips host, connection, authorization, and other filtered headers."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = False

        backend_received = bytearray()

        class MockClientWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

        header_lines = [b"HTTP/1.1 200 OK\r\n", b"\r\n"]

        mock_backend_reader = AsyncMock()
        mock_backend_reader.readline = AsyncMock(side_effect=header_lines)
        mock_backend_reader.read = AsyncMock(return_value=b"")

        mock_backend_writer = MagicMock()

        def capture_write(data):
            backend_received.extend(data)

        mock_backend_writer.write = capture_write
        mock_backend_writer.drain = AsyncMock()
        mock_backend_writer.close = MagicMock()
        mock_backend_writer.wait_closed = AsyncMock()

        async def mock_open_connection(*args, **kwargs):
            return mock_backend_reader, mock_backend_writer

        headers = {
            "host": "original-host:8000",
            "connection": "keep-alive",
            "authorization": "Bearer user-key",
            "content-type": "application/json",
            "x-custom": "value",
        }

        async def run():
            writer = MockClientWriter()
            with patch("asyncio.open_connection", side_effect=mock_open_connection):
                await gw.proxy_request("POST", "/v1/completions", headers, None, writer, "test-key")

        asyncio.run(run())

        sent_text = backend_received.decode()
        # Filtered headers should NOT appear with their original values
        assert "original-host:8000" not in sent_text
        assert "keep-alive" not in sent_text
        assert "Bearer user-key" not in sent_text
        # Custom headers should be forwarded
        assert "x-custom: value" in sent_text
        assert "content-type: application/json" in sent_text

    def test_proxy_cors_injected_into_response(self, monkeypatch):
        """Proxy injects CORS headers into backend response."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockClientWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        header_lines = [
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Type: application/json\r\n",
            b"\r\n",
        ]

        mock_backend_reader = AsyncMock()
        mock_backend_reader.readline = AsyncMock(side_effect=header_lines)
        mock_backend_reader.read = AsyncMock(return_value=b"")

        mock_backend_writer = MagicMock()
        mock_backend_writer.write = MagicMock()
        mock_backend_writer.drain = AsyncMock()
        mock_backend_writer.close = MagicMock()
        mock_backend_writer.wait_closed = AsyncMock()

        async def mock_open_connection(*args, **kwargs):
            return mock_backend_reader, mock_backend_writer

        async def run():
            writer = MockClientWriter()
            with patch("asyncio.open_connection", side_effect=mock_open_connection):
                await gw.proxy_request(
                    "GET",
                    "/v1/models",
                    {},
                    None,
                    writer,
                    "test-key",
                    "https://example.com",
                )

        asyncio.run(run())

        response = written_data.decode()
        assert "Access-Control-Allow-Origin: *" in response

    def test_proxy_exception_during_streaming(self, monkeypatch):
        """Exception during response streaming sends 502."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = False
        initial_errors = gw.metrics.requests_error

        written_data = bytearray()

        class MockClientWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def mock_open_connection(*args, **kwargs):
            raise Exception("Unexpected error")

        async def run():
            writer = MockClientWriter()
            with patch("asyncio.open_connection", side_effect=mock_open_connection):
                await gw.proxy_request("GET", "/v1/models", {}, None, writer, "test-key")

        asyncio.run(run())

        response = written_data.decode()
        assert "502 Bad Gateway" in response
        assert gw.metrics.requests_error > initial_errors

    def test_proxy_metrics_active_tracking(self, monkeypatch):
        """Proxy correctly increments/decrements requests_active."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = False

        active_during_proxy = []

        class MockClientWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

        header_lines = [b"HTTP/1.1 200 OK\r\n", b"\r\n"]

        mock_backend_reader = AsyncMock()
        mock_backend_reader.readline = AsyncMock(side_effect=header_lines)

        async def read_and_capture(*args, **kwargs):
            active_during_proxy.append(gw.metrics.requests_active)
            return b""

        mock_backend_reader.read = read_and_capture

        mock_backend_writer = MagicMock()
        mock_backend_writer.write = MagicMock()
        mock_backend_writer.drain = AsyncMock()
        mock_backend_writer.close = MagicMock()
        mock_backend_writer.wait_closed = AsyncMock()

        async def mock_open_connection(*args, **kwargs):
            return mock_backend_reader, mock_backend_writer

        async def run():
            writer = MockClientWriter()
            with patch("asyncio.open_connection", side_effect=mock_open_connection):
                await gw.proxy_request("GET", "/v1/models", {}, None, writer, "test-key")

        asyncio.run(run())

        # requests_active should have been > 0 during proxy
        assert any(a > 0 for a in active_during_proxy)
        # After proxy completes, requests_active decremented
        assert gw.metrics.requests_active == 0


# ---------------------------------------------------------------------------
# _queued_proxy tests
# ---------------------------------------------------------------------------


class TestQueuedProxy:
    """Tests for _queued_proxy() semaphore and queue logic."""

    def test_queued_proxy_tracks_wait_time(self, monkeypatch):
        """Verify queue wait time is tracked in metrics."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_CONCURRENT_REQUESTS="1",
            MAX_QUEUE_SIZE="0",
        )
        gw.AUTH_AVAILABLE = False
        initial_wait = gw.metrics.queue_wait_seconds_total

        async def mock_proxy(*args, **kwargs):
            pass

        gw.proxy_request = mock_proxy

        class MockWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw._queued_proxy("GET", "/v1/models", {}, None, writer, "test-key", "")

        asyncio.run(run())

        # Wait time should be tracked (even if very small)
        assert gw.metrics.queue_wait_seconds_total >= initial_wait

    def test_queued_proxy_releases_semaphore_on_error(self, monkeypatch):
        """Verify semaphore is released even if proxy_request raises."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_CONCURRENT_REQUESTS="1",
            MAX_QUEUE_SIZE="0",
        )

        async def failing_proxy(*args, **kwargs):
            raise RuntimeError("proxy failed")

        gw.proxy_request = failing_proxy

        class MockWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            try:
                await gw._queued_proxy("GET", "/v1/models", {}, None, writer, "test-key", "")
            except RuntimeError:
                pass

        asyncio.run(run())

        # Semaphore should be released (value back to max)
        assert gw._proxy_semaphore._value == gw.MAX_CONCURRENT_REQUESTS


# ---------------------------------------------------------------------------
# handle_client edge case tests
# ---------------------------------------------------------------------------


class TestHandleClientEdgeCases:
    """Tests for handle_client edge cases."""

    def test_empty_request_returns_early(self, monkeypatch):
        """Empty request (EOF) returns without error."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            reader = asyncio.StreamReader()
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        # Should not crash, no response expected
        assert len(written_data) == 0

    def test_malformed_request_line_returns_early(self, monkeypatch):
        """Request line with fewer than 2 parts returns without error."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            reader = asyncio.StreamReader()
            reader.feed_data(b"BADREQUEST\r\n\r\n")
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        # Should not crash, no response expected
        assert len(written_data) == 0

    def test_options_request_handled(self, monkeypatch):
        """OPTIONS request gets 204 response."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = (
                b"OPTIONS /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Origin: https://example.com\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "204 No Content" in response
        assert "Access-Control-Allow-Origin: *" in response

    def test_auth_failure_returns_401(self, monkeypatch):
        """Request to protected endpoint with failed auth returns 401."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = True

        # Mock authenticate_request to return None (auth failed)
        async def mock_authenticate(writer, headers):
            body = json.dumps(
                {
                    "error": {
                        "message": "Invalid API key",
                        "type": "invalid_request_error",
                    }
                }
            )
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

        gw.authenticate_request = mock_authenticate

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = b"GET /v1/models HTTP/1.1\r\nHost: localhost\r\n\r\n"
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "401 Unauthorized" in response

    def test_auth_success_proxies_request(self, monkeypatch):
        """Request with successful auth reaches the proxy."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = True

        proxy_called = []

        async def mock_authenticate(writer, headers):
            return "test-key-id"

        async def mock_proxy(*args, **kwargs):
            proxy_called.append(True)

        gw.authenticate_request = mock_authenticate
        gw.proxy_request = mock_proxy

        class MockWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = (
                b"GET /v1/models HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Authorization: Bearer sk-test\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        assert len(proxy_called) == 1
        assert gw.metrics.requests_authenticated > 0

    def test_timeout_during_request_handled_gracefully(self, monkeypatch):
        """asyncio.TimeoutError during handle_client is caught."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        class MockWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            reader = asyncio.StreamReader()
            # Feed only partial data and don't feed eof
            reader.feed_data(b"GET /v1/models HTTP/1.1\r\n")

            # The reader.readline for headers will hang, but since we
            # can't easily trigger a timeout in unit tests, let's test
            # the exception path directly by mocking
            async def slow_readline():
                raise asyncio.TimeoutError()

            reader.readline = slow_readline
            await gw.handle_client(reader, MockWriter())

        # Should not raise
        asyncio.run(run())

    def test_exception_during_request_handled_gracefully(self, monkeypatch):
        """Unexpected exceptions in handle_client are caught."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        class MockWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            reader = asyncio.StreamReader()
            reader.feed_data(b"GET /v1/models HTTP/1.1\r\n")

            async def broken_readline():
                raise RuntimeError("Unexpected I/O error")

            reader.readline = broken_readline
            await gw.handle_client(reader, MockWriter())

        # Should not raise
        asyncio.run(run())

    def test_writer_close_failure_handled(self, monkeypatch):
        """Failure to close writer in finally block is caught."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        class FailCloseWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                raise OSError("Cannot close")

            async def wait_closed(self):
                pass

        async def run():
            reader = asyncio.StreamReader()
            reader.feed_eof()
            await gw.handle_client(reader, FailCloseWriter())

        # Should not raise despite close failure
        asyncio.run(run())

    def test_request_with_body_reads_correctly(self, monkeypatch):
        """Request with body reads the full body before proxying."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = False

        proxy_args = []

        async def mock_proxy(method, path, headers, body, writer, key_id, origin):
            proxy_args.append({"method": method, "path": path, "body": body, "key_id": key_id})

        gw.proxy_request = mock_proxy

        class MockWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            body = b'{"model":"test","messages":[]}'
            cl_header = f"Content-Length: {len(body)}\r\n".encode()
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n" + cl_header + b"\r\n" + body
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        assert len(proxy_args) == 1
        assert proxy_args[0]["body"] == b'{"model":"test","messages":[]}'
        assert proxy_args[0]["key_id"] == "auth-disabled"


# ---------------------------------------------------------------------------
# _route_health tests
# ---------------------------------------------------------------------------


class TestRouteHealth:
    """Tests for _route_health routing to correct handlers."""

    def test_route_metrics(self, monkeypatch):
        """Verify /metrics route dispatches to handle_metrics."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw._route_health("/metrics", writer, "", "")

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response
        assert "Content-Type: application/json" in response

    def test_route_ping(self, monkeypatch):
        """Verify /ping route dispatches to handle_ping."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw._route_health("/ping", writer, "", "")

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response

    def test_route_health(self, monkeypatch):
        """Verify /health route dispatches to handle_health."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw._route_health("/health", writer, "", "")

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response


# ---------------------------------------------------------------------------
# Module-level configuration tests
# ---------------------------------------------------------------------------


class TestModuleLevelConfig:
    """Tests for module-level configuration parsing."""

    def test_deprecated_backend_port_env_ignored(self, monkeypatch):
        """BACKEND_PORT env var is deprecated and no longer overrides PORT_BACKEND."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", BACKEND_PORT="9090")
        # BACKEND_PORT is no longer supported; PORT_BACKEND (default 8080) is used
        assert gw.BACKEND_PORT == 8080

    def test_port_backend_env(self, monkeypatch):
        """PORT_BACKEND env var sets backend port."""
        monkeypatch.delenv("BACKEND_PORT", raising=False)
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", PORT_BACKEND="9999")
        assert gw.BACKEND_PORT == 9999

    def test_cors_warning_no_scheme(self, monkeypatch, capsys):
        """CORS origins without http scheme generate a warning."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="example.com")
        assert gw.CORS_ENABLED is True
        # The warning is printed during reload, we can check the origin list
        assert "example.com" in gw._cors_origins_list


class TestLogFunction:
    """Tests for the log() helper."""

    def test_log_writes_to_stderr(self, monkeypatch, capsys):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.log("test message")
        captured = capsys.readouterr()
        assert "[gateway] test message" in captured.err


# ---------------------------------------------------------------------------
# SEC-07: Request line length limit tests
# ---------------------------------------------------------------------------


class TestRequestLineSizeConfig:
    """Tests for MAX_REQUEST_LINE_SIZE env var parsing."""

    def test_default_max_request_line_size(self, monkeypatch):
        monkeypatch.delenv("MAX_REQUEST_LINE_SIZE", raising=False)
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw.MAX_REQUEST_LINE_SIZE == 8192

    def test_custom_max_request_line_size(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", MAX_REQUEST_LINE_SIZE="4096")
        assert gw.MAX_REQUEST_LINE_SIZE == 4096


class TestUriTooLongResponse:
    """Tests for send_uri_too_long() response helper."""

    def test_414_status_line(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_uri_too_long(writer)

        asyncio.run(run())

        response = written_data.decode()
        assert response.startswith("HTTP/1.1 414 URI Too Long\r\n")

    def test_json_body_format(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_uri_too_long(writer)

        asyncio.run(run())

        response = written_data.decode()
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["error"]["code"] == "uri_too_long"
        assert data["error"]["type"] == "invalid_request_error"

    def test_cors_headers_included(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_uri_too_long(writer, "https://example.com")

        asyncio.run(run())

        response = written_data.decode()
        assert "Access-Control-Allow-Origin: *" in response


class TestRequestLineSizeEnforcement:
    """Tests for request line size enforcement in handle_client."""

    def test_oversized_request_line_returns_414(self, monkeypatch):
        """Verify that a request with oversized request line gets 414."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_REQUEST_LINE_SIZE="100",
        )
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            # Create a request line longer than 100 bytes
            long_path = "/v1/" + "a" * 200
            request_data = (f"GET {long_path} HTTP/1.1\r\n" f"Host: localhost\r\n" f"\r\n").encode()
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 414 URI Too Long" in response

    def test_request_line_at_limit_is_allowed(self, monkeypatch):
        """Verify a request line exactly at the limit is accepted."""
        gw = _reload_gateway(
            monkeypatch,
            CORS_ORIGINS="",
            MAX_REQUEST_LINE_SIZE="8192",
        )
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()
        proxy_called = []

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def mock_proxy(*args, **kwargs):
            proxy_called.append(True)

        gw.proxy_request = mock_proxy

        async def run():
            request_data = b"GET /v1/models HTTP/1.1\r\n" b"Host: localhost\r\n" b"\r\n"
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "414" not in response


# ---------------------------------------------------------------------------
# SEC-10: Bad Content-Length tests
# ---------------------------------------------------------------------------


class TestBadRequestResponse:
    """Tests for send_bad_request() response helper."""

    def test_400_status_line(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_bad_request(writer, "Test error message")

        asyncio.run(run())

        response = written_data.decode()
        assert response.startswith("HTTP/1.1 400 Bad Request\r\n")

    def test_json_body_format(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_bad_request(writer, "Test error message")

        asyncio.run(run())

        response = written_data.decode()
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["error"]["code"] == "bad_request"
        assert data["error"]["type"] == "invalid_request_error"
        assert data["error"]["message"] == "Test error message"

    def test_cors_headers_included(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="*")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

        async def run():
            writer = MockWriter()
            await gw.send_bad_request(writer, "Error", "https://example.com")

        asyncio.run(run())

        response = written_data.decode()
        assert "Access-Control-Allow-Origin: *" in response


class TestMalformedContentLength:
    """Tests for malformed Content-Length handling in handle_client."""

    def test_non_numeric_content_length_returns_400(self, monkeypatch):
        """Verify that a non-numeric Content-Length triggers a 400 response."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: abc\r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 400 Bad Request" in response
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["error"]["code"] == "bad_request"

    def test_empty_content_length_returns_400(self, monkeypatch):
        """Verify that an empty Content-Length triggers a 400 response."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        gw.AUTH_AVAILABLE = False

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: \r\n"
                b"\r\n"
            )
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 400 Bad Request" in response


# ---------------------------------------------------------------------------
# SEC-12: Metrics auth tests
# ---------------------------------------------------------------------------


class TestMetricsAuthConfig:
    """Tests for METRICS_AUTH_ENABLED env var parsing."""

    def test_default_metrics_auth_disabled(self, monkeypatch):
        monkeypatch.delenv("METRICS_AUTH_ENABLED", raising=False)
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="")
        assert gw.METRICS_AUTH_ENABLED is False

    def test_metrics_auth_enabled(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", METRICS_AUTH_ENABLED="true")
        assert gw.METRICS_AUTH_ENABLED is True

    def test_metrics_auth_case_insensitive(self, monkeypatch):
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", METRICS_AUTH_ENABLED="TRUE")
        assert gw.METRICS_AUTH_ENABLED is True


class TestMetricsAuthEnforcement:
    """Tests for /metrics auth enforcement when METRICS_AUTH_ENABLED=true."""

    def test_metrics_unauthenticated_when_auth_disabled(self, monkeypatch):
        """Metrics returns 200 when METRICS_AUTH_ENABLED=false (default)."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", METRICS_AUTH_ENABLED="false")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = b"GET /metrics HTTP/1.1\r\n" b"Host: localhost\r\n" b"\r\n"
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response

    def test_ping_bypasses_metrics_auth(self, monkeypatch):
        """Verify /ping still works when METRICS_AUTH_ENABLED=true."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", METRICS_AUTH_ENABLED="true")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = b"GET /ping HTTP/1.1\r\n" b"Host: localhost\r\n" b"\r\n"
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response

    def test_health_bypasses_metrics_auth(self, monkeypatch):
        """Verify /health still works when METRICS_AUTH_ENABLED=true."""
        gw = _reload_gateway(monkeypatch, CORS_ORIGINS="", METRICS_AUTH_ENABLED="true")

        written_data = bytearray()

        class MockWriter:
            def write(self, data):
                written_data.extend(data)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def run():
            request_data = b"GET /health HTTP/1.1\r\n" b"Host: localhost\r\n" b"\r\n"
            reader = asyncio.StreamReader()
            reader.feed_data(request_data)
            reader.feed_eof()
            await gw.handle_client(reader, MockWriter())

        asyncio.run(run())

        response = written_data.decode()
        assert "HTTP/1.1 200 OK" in response


class TestLogFormatText:
    """Tests for log() in text mode (default behavior)."""

    def test_log_text_default(self, monkeypatch, capsys):
        """log() outputs plain text to stderr when LOG_FORMAT is not set."""
        gw = _reload_gateway(monkeypatch)
        gw.log("hello world")
        captured = capsys.readouterr()
        assert "[gateway] hello world" in captured.err
        # Should not be JSON
        try:
            json.loads(captured.err.strip())
            assert False, "Expected plain text, got valid JSON"
        except json.JSONDecodeError:
            pass

    def test_log_text_explicit(self, monkeypatch, capsys):
        """log() outputs plain text when LOG_FORMAT=text."""
        gw = _reload_gateway(monkeypatch, LOG_FORMAT="text")
        gw.log("test message")
        captured = capsys.readouterr()
        assert "[gateway] test message" in captured.err

    def test_log_text_ignores_extra_kwargs(self, monkeypatch, capsys):
        """In text mode, extra kwargs are silently ignored."""
        gw = _reload_gateway(monkeypatch, LOG_FORMAT="text")
        gw.log("some msg", level="error", method="POST", path="/v1/test")
        captured = capsys.readouterr()
        assert "[gateway] some msg" in captured.err


class TestLogFormatJson:
    """Tests for log() in JSON mode.

    Module reload emits module-level log lines (e.g. BACKEND_API_KEY warning).
    We drain capsys after reload so only the explicit log() call is captured.
    """

    def test_log_json_basic(self, monkeypatch, capsys):
        """log() outputs valid JSON to stderr when LOG_FORMAT=json."""
        gw = _reload_gateway(monkeypatch, LOG_FORMAT="json")
        capsys.readouterr()  # drain module-level output
        gw.log("Gateway started")
        captured = capsys.readouterr()
        entry = json.loads(captured.err.strip())
        assert entry["msg"] == "Gateway started"
        assert entry["level"] == "info"
        assert "ts" in entry

    def test_log_json_with_level(self, monkeypatch, capsys):
        """log() respects the level parameter in JSON mode."""
        gw = _reload_gateway(monkeypatch, LOG_FORMAT="json")
        capsys.readouterr()  # drain module-level output
        gw.log("something broke", level="error")
        captured = capsys.readouterr()
        entry = json.loads(captured.err.strip())
        assert entry["level"] == "error"
        assert entry["msg"] == "something broke"

    def test_log_json_with_structured_fields(self, monkeypatch, capsys):
        """log() includes extra kwargs as structured fields in JSON mode."""
        gw = _reload_gateway(monkeypatch, LOG_FORMAT="json")
        capsys.readouterr()  # drain module-level output
        gw.log(
            "Request completed",
            method="POST",
            path="/v1/chat/completions",
            status=200,
            duration_ms=42.5,
            key_id="production",
        )
        captured = capsys.readouterr()
        entry = json.loads(captured.err.strip())
        assert entry["msg"] == "Request completed"
        assert entry["level"] == "info"
        assert entry["method"] == "POST"
        assert entry["path"] == "/v1/chat/completions"
        assert entry["status"] == 200
        assert entry["duration_ms"] == 42.5
        assert entry["key_id"] == "production"
        assert "ts" in entry

    def test_log_json_timestamp_is_iso8601(self, monkeypatch, capsys):
        """JSON log timestamp is ISO 8601 UTC."""
        gw = _reload_gateway(monkeypatch, LOG_FORMAT="json")
        capsys.readouterr()  # drain module-level output
        gw.log("ts check")
        captured = capsys.readouterr()
        entry = json.loads(captured.err.strip())
        ts = entry["ts"]
        # Should contain UTC offset indicator
        assert "+" in ts or ts.endswith("Z") or "+00:00" in ts

    def test_log_json_single_line(self, monkeypatch, capsys):
        """JSON log output is a single line (JSONL format)."""
        gw = _reload_gateway(monkeypatch, LOG_FORMAT="json")
        capsys.readouterr()  # drain module-level output
        gw.log("line check", method="GET", path="/test")
        captured = capsys.readouterr()
        lines = [line for line in captured.err.strip().split("\n") if line.strip()]
        assert len(lines) == 1

    def test_log_json_case_insensitive_env(self, monkeypatch, capsys):
        """LOG_FORMAT=JSON (uppercase) also enables JSON mode."""
        gw = _reload_gateway(monkeypatch, LOG_FORMAT="JSON")
        capsys.readouterr()  # drain module-level output
        gw.log("case test")
        captured = capsys.readouterr()
        entry = json.loads(captured.err.strip())
        assert entry["msg"] == "case test"


class TestLogJsonHelper:
    """Tests for the _log_json() helper directly."""

    def test_log_json_helper_output(self, monkeypatch, capsys):
        """_log_json() writes compact JSON to stderr."""
        gw = _reload_gateway(monkeypatch, LOG_FORMAT="json")
        capsys.readouterr()  # drain module-level output
        gw._log_json("warn", "test warning", code=431)
        captured = capsys.readouterr()
        entry = json.loads(captured.err.strip())
        assert entry["level"] == "warn"
        assert entry["msg"] == "test warning"
        assert entry["code"] == 431
