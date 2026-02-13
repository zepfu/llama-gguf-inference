"""Unit tests for scripts/gateway.py - Gateway module (CORS, Prometheus metrics)."""

import importlib
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
        assert len(headers) == 4
        assert "Access-Control-Allow-Origin: https://app.example.com" in headers

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
        assert len(headers_a) == 4
        assert "Access-Control-Allow-Origin: https://a.com" in headers_a

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
        assert len(headers) == 4

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
        # 8 metrics * 3 lines = 24 lines
        assert len(lines) == 24

        # Verify pattern: HELP, TYPE, value
        for i in range(0, len(lines), 3):
            assert lines[i].startswith("# HELP gateway_")
            assert lines[i + 1].startswith("# TYPE gateway_")
            # Value line should be metric_name followed by space and number
            parts = lines[i + 2].split(" ")
            assert len(parts) == 2
            assert parts[0].startswith("gateway_")
            assert parts[1].isdigit()

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
