"""Unit tests for scripts/gateway.py - Gateway module (CORS, Prometheus metrics, queue)."""

import asyncio
import importlib
import json
import time


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
            request_data = (f"GET {path} HTTP/1.1\r\n" f"Host: localhost\r\n" f"\r\n").encode()
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
