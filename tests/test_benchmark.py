"""Unit tests for scripts/benchmark.py -- Benchmark module."""

import argparse
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import benchmark  # noqa: E402


class TestPercentile:
    """Tests for the percentile() function."""

    def test_empty_data(self):
        """Empty input returns 0.0."""
        assert benchmark.percentile([], 50) == 0.0

    def test_single_value(self):
        """Single-element list returns that element for any percentile."""
        assert benchmark.percentile([5.0], 50) == 5.0
        assert benchmark.percentile([5.0], 99) == 5.0

    def test_p50_even_count(self):
        """P50 with even number of elements."""
        data = [1.0, 2.0, 3.0, 4.0]
        result = benchmark.percentile(data, 50)
        assert result in (2.0, 3.0)

    def test_p50_odd_count(self):
        """P50 with odd number of elements returns the median."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = benchmark.percentile(data, 50)
        assert result == 3.0

    def test_p95(self):
        """P95 for 1-100 is at least 95."""
        data = list(range(1, 101))
        result = benchmark.percentile([float(x) for x in data], 95)
        assert result >= 95.0

    def test_p99(self):
        """P99 for 1-100 is at least 99."""
        data = [float(x) for x in range(1, 101)]
        result = benchmark.percentile(data, 99)
        assert result >= 99.0

    def test_p0(self):
        """P0 returns minimum value."""
        data = [10.0, 20.0, 30.0]
        result = benchmark.percentile(data, 0)
        assert result == 10.0

    def test_p100(self):
        """P100 returns maximum value."""
        data = [10.0, 20.0, 30.0]
        result = benchmark.percentile(data, 100)
        assert result == 30.0

    def test_unsorted_input(self):
        """Input does not need to be pre-sorted."""
        data = [50.0, 10.0, 30.0, 20.0, 40.0]
        result = benchmark.percentile(data, 50)
        assert result == 30.0

    def test_original_unchanged(self):
        """Input list is not mutated."""
        data = [3.0, 1.0, 2.0]
        benchmark.percentile(data, 50)
        assert data == [3.0, 1.0, 2.0]


class TestComputeStats:
    """Tests for compute_stats()."""

    def test_empty_input(self):
        """Empty input returns zeroed stats."""
        stats = benchmark.compute_stats([])
        assert stats["count"] == 0
        assert stats["min"] == 0.0
        assert stats["max"] == 0.0
        assert stats["mean"] == 0.0
        assert stats["p50"] == 0.0

    def test_single_value(self):
        """Single value fills all stat fields identically."""
        stats = benchmark.compute_stats([42.0])
        assert stats["count"] == 1
        assert stats["min"] == 42.0
        assert stats["max"] == 42.0
        assert stats["mean"] == 42.0
        assert stats["p50"] == 42.0
        assert stats["p95"] == 42.0
        assert stats["p99"] == 42.0

    def test_multiple_values(self):
        """Multiple values compute correct min, max, mean, p50."""
        stats = benchmark.compute_stats([1.0, 2.0, 3.0, 4.0, 5.0])
        assert stats["count"] == 5
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["mean"] == 3.0
        assert stats["p50"] == 3.0

    def test_all_keys_present(self):
        """Return dict has all expected keys."""
        stats = benchmark.compute_stats([1.0])
        expected_keys = {"min", "max", "mean", "p50", "p95", "p99", "count"}
        assert set(stats.keys()) == expected_keys

    def test_all_same_values(self):
        """All identical values produce identical stats."""
        stats = benchmark.compute_stats([7.0, 7.0, 7.0])
        assert stats["min"] == 7.0
        assert stats["max"] == 7.0
        assert stats["mean"] == 7.0
        assert stats["p50"] == 7.0


class TestParseSSETokens:
    """Tests for parse_sse_tokens()."""

    def test_empty_input(self):
        """Empty string returns empty list."""
        assert benchmark.parse_sse_tokens("") == []

    def test_done_sentinel(self):
        """DONE sentinel returns empty list."""
        assert benchmark.parse_sse_tokens("data: [DONE]\n") == []

    def test_single_token(self):
        """Single SSE event with content."""
        event = 'data: {"choices":[{"delta":{"content":"hello"}}]}\n'
        tokens = benchmark.parse_sse_tokens(event)
        assert tokens == ["hello"]

    def test_multiple_tokens(self):
        """Multiple SSE events extract tokens in order."""
        events = (
            'data: {"choices":[{"delta":{"content":"Hello"}}]}\n'
            'data: {"choices":[{"delta":{"content":" world"}}]}\n'
            "data: [DONE]\n"
        )
        tokens = benchmark.parse_sse_tokens(events)
        assert tokens == ["Hello", " world"]

    def test_empty_delta(self):
        """Empty delta object yields no tokens."""
        event = 'data: {"choices":[{"delta":{}}]}\n'
        tokens = benchmark.parse_sse_tokens(event)
        assert tokens == []

    def test_role_delta_ignored(self):
        """Role-only delta is skipped, content delta is extracted."""
        events = (
            'data: {"choices":[{"delta":{"role":"assistant"}}]}\n'
            'data: {"choices":[{"delta":{"content":"Hi"}}]}\n'
        )
        tokens = benchmark.parse_sse_tokens(events)
        assert tokens == ["Hi"]

    def test_invalid_json_skipped(self):
        """Invalid JSON lines are skipped gracefully."""
        events = "data: {invalid json}\n" 'data: {"choices":[{"delta":{"content":"ok"}}]}\n'
        tokens = benchmark.parse_sse_tokens(events)
        assert tokens == ["ok"]

    def test_non_data_lines_skipped(self):
        """Non-data lines (comments, event types) are ignored."""
        events = (
            ": comment line\n"
            "event: message\n"
            'data: {"choices":[{"delta":{"content":"token"}}]}\n'
            "\n"
        )
        tokens = benchmark.parse_sse_tokens(events)
        assert tokens == ["token"]

    def test_no_choices(self):
        """Event with no choices key yields empty list."""
        event = 'data: {"id":"123","object":"chat.completion.chunk"}\n'
        tokens = benchmark.parse_sse_tokens(event)
        assert tokens == []

    def test_null_content_skipped(self):
        """Null content value is skipped."""
        event = 'data: {"choices":[{"delta":{"content":null}}]}\n'
        tokens = benchmark.parse_sse_tokens(event)
        assert tokens == []

    def test_whitespace_around_data_prefix(self):
        """Leading/trailing whitespace on data lines is handled."""
        event = '  data: {"choices":[{"delta":{"content":"x"}}]}  \n'
        tokens = benchmark.parse_sse_tokens(event)
        assert tokens == ["x"]


class TestCountTokensApprox:
    """Tests for count_tokens_approx()."""

    def test_empty(self):
        """Empty string has zero tokens."""
        assert benchmark.count_tokens_approx("") == 0

    def test_single_word(self):
        """Single word counts as one token."""
        assert benchmark.count_tokens_approx("hello") == 1

    def test_multiple_words(self):
        """Multiple words count correctly."""
        assert benchmark.count_tokens_approx("the quick brown fox") == 4

    def test_extra_whitespace(self):
        """Extra whitespace does not inflate count."""
        assert benchmark.count_tokens_approx("a  b   c") == 3


class TestFormatTextOutput:
    """Tests for format_text_output()."""

    def test_gateway_only(self):
        """Gateway-only results show gateway section, no inference."""
        gateway = {
            "ping": {"stats": {"p50": 0.001, "p95": 0.002, "p99": 0.003}},
            "health": {"stats": {"p50": 0.005, "p95": 0.008, "p99": 0.010}},
        }
        result = benchmark.format_text_output(gateway, None)
        assert "=== Gateway Overhead ===" in result
        assert "/ping latency:" in result
        assert "/health latency:" in result
        assert "Inference" not in result

    def test_inference_only(self):
        """Inference-only results show inference section, no gateway."""
        inference = {
            "ttft": {"stats": {"p50": 0.1, "p95": 0.2, "p99": 0.3}},
            "tokens_per_sec": {"stats": {"mean": 40.0, "p50": 38.0, "min": 30.0}},
            "total_latency": {"stats": {"p50": 3.0, "p95": 4.0, "p99": 5.0}},
            "requests_total": 10,
            "requests_success": 9,
            "requests_failed": 1,
            "wall_time": 35.0,
            "concurrency": 2,
        }
        result = benchmark.format_text_output(None, inference)
        assert "Gateway" not in result
        assert "=== Inference Performance (concurrency=2, requests=10) ===" in result
        assert "Time to first token:" in result
        assert "Tokens/sec:" in result
        assert "Total latency:" in result
        assert "10 total" in result
        assert "9 success" in result
        assert "1 failed" in result

    def test_both(self):
        """Both gateway and inference results included."""
        gateway = {
            "ping": {"stats": {"p50": 0.001, "p95": 0.002, "p99": 0.003}},
            "health": {"stats": {"p50": 0.005, "p95": 0.008, "p99": 0.010}},
        }
        inference = {
            "ttft": {"stats": {"p50": 0.1, "p95": 0.2, "p99": 0.3}},
            "tokens_per_sec": {"stats": {"mean": 40.0, "p50": 38.0, "min": 30.0}},
            "total_latency": {"stats": {"p50": 3.0, "p95": 4.0, "p99": 5.0}},
            "requests_total": 10,
            "requests_success": 10,
            "requests_failed": 0,
            "wall_time": 32.0,
            "concurrency": 1,
        }
        result = benchmark.format_text_output(gateway, inference)
        assert "Gateway Overhead" in result
        assert "Inference Performance" in result

    def test_none_both(self):
        """Both None returns empty string."""
        result = benchmark.format_text_output(None, None)
        assert result == ""


class TestFormatJsonOutput:
    """Tests for format_json_output()."""

    def test_gateway_only(self):
        """Gateway-only JSON contains gateway key only."""
        gateway = {
            "ping": {"stats": {"p50": 0.001, "count": 10}},
            "health": {"stats": {"p50": 0.005, "count": 10}},
        }
        result = benchmark.format_json_output(gateway, None)
        data = json.loads(result)
        assert "gateway" in data
        assert "inference" not in data
        assert data["gateway"]["ping"]["p50"] == 0.001

    def test_inference_only(self):
        """Inference-only JSON contains inference key only."""
        inference = {
            "ttft": {"stats": {"p50": 0.1}},
            "tokens_per_sec": {"stats": {"mean": 40.0}},
            "total_latency": {"stats": {"p50": 3.0}},
            "requests_total": 10,
            "requests_success": 10,
            "requests_failed": 0,
            "wall_time": 30.0,
            "concurrency": 1,
        }
        result = benchmark.format_json_output(None, inference)
        data = json.loads(result)
        assert "inference" in data
        assert "gateway" not in data
        assert data["inference"]["requests_total"] == 10

    def test_valid_json(self):
        """Both gateway and inference produce valid JSON."""
        gateway = {
            "ping": {"stats": {"p50": 0.001}},
            "health": {"stats": {"p50": 0.005}},
        }
        inference = {
            "ttft": {"stats": {"p50": 0.1}},
            "tokens_per_sec": {"stats": {"mean": 40.0}},
            "total_latency": {"stats": {"p50": 3.0}},
            "requests_total": 10,
            "requests_success": 10,
            "requests_failed": 0,
            "wall_time": 30.0,
            "concurrency": 1,
        }
        result = benchmark.format_json_output(gateway, inference)
        data = json.loads(result)
        assert "gateway" in data
        assert "inference" in data

    def test_empty_both(self):
        """Both None produces empty JSON object."""
        result = benchmark.format_json_output(None, None)
        data = json.loads(result)
        assert data == {}


class TestBuildParser:
    """Tests for build_parser() and CLI argument handling."""

    def test_required_url(self):
        """URL is required; omitting it exits."""
        parser = benchmark.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_minimal_args(self):
        """Minimal args set correct defaults."""
        parser = benchmark.build_parser()
        args = parser.parse_args(["--url", "http://localhost:8000"])
        assert args.url == "http://localhost:8000"
        assert args.api_key is None
        assert args.concurrency == 1
        assert args.requests == 10
        assert args.warmup == 1
        assert args.output == "text"
        assert args.gateway_only is False
        assert args.max_tokens == 128
        assert args.prompt == "Write a short poem about the sea"

    def test_all_args(self):
        """All arguments are parsed correctly."""
        parser = benchmark.build_parser()
        args = parser.parse_args(
            [
                "--url",
                "http://example.com:9000",
                "--api-key",
                "sk-mykey-1234567890",
                "--prompt",
                "Hello world",
                "--max-tokens",
                "256",
                "--concurrency",
                "4",
                "--requests",
                "20",
                "--warmup",
                "2",
                "--output",
                "json",
                "--gateway-only",
            ]
        )
        assert args.url == "http://example.com:9000"
        assert args.api_key == "sk-mykey-1234567890"
        assert args.prompt == "Hello world"
        assert args.max_tokens == 256
        assert args.concurrency == 4
        assert args.requests == 20
        assert args.warmup == 2
        assert args.output == "json"
        assert args.gateway_only is True

    def test_invalid_output_format(self):
        """Invalid output format exits."""
        parser = benchmark.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--url", "http://localhost:8000", "--output", "xml"])


class TestParseUrl:
    """Tests for _parse_url() internal helper."""

    def test_http_default_port(self):
        """HTTP URL uses port 80 by default."""
        host, path, port, use_ssl = benchmark._parse_url("http://localhost/ping")
        assert host == "localhost"
        assert path == "/ping"
        assert port == 80
        assert use_ssl is False

    def test_https_default_port(self):
        """HTTPS URL uses port 443 and SSL."""
        host, path, port, use_ssl = benchmark._parse_url("https://example.com/health")
        assert host == "example.com"
        assert path == "/health"
        assert port == 443
        assert use_ssl is True

    def test_custom_port(self):
        """Custom port is extracted from URL."""
        host, path, port, use_ssl = benchmark._parse_url("http://localhost:8000/v1/models")
        assert host == "localhost"
        assert path == "/v1/models"
        assert port == 8000
        assert use_ssl is False

    def test_root_path(self):
        """URL without path defaults to /."""
        _host, path, _port, _use_ssl = benchmark._parse_url("http://localhost:8000")
        assert path == "/"

    def test_query_string(self):
        """Query string is preserved in path."""
        _host, path, _port, _use_ssl = benchmark._parse_url("http://localhost/api?key=val")
        assert path == "/api?key=val"


class TestFormatHelpers:
    """Tests for _fmt_ms() and _fmt_s()."""

    def test_fmt_ms(self):
        """Seconds formatted as milliseconds."""
        assert benchmark._fmt_ms(0.001) == "1.0ms"
        assert benchmark._fmt_ms(0.0005) == "0.5ms"
        assert benchmark._fmt_ms(1.234) == "1234.0ms"

    def test_fmt_s(self):
        """Seconds formatted with one decimal."""
        assert benchmark._fmt_s(1.0) == "1.0s"
        assert benchmark._fmt_s(0.5) == "0.5s"
        assert benchmark._fmt_s(123.456) == "123.5s"


class TestOpenConnection:
    """Tests for _open_connection() with mocked asyncio."""

    @pytest.mark.asyncio
    async def test_http_connection(self):
        """Plain TCP connection passes no SSL context."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        with patch("benchmark.asyncio.open_connection", new_callable=AsyncMock) as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)
            reader, writer = await benchmark._open_connection("localhost", 8000, False)
            mock_open.assert_called_once_with("localhost", 8000, ssl=None)
            assert reader is mock_reader
            assert writer is mock_writer

    @pytest.mark.asyncio
    async def test_https_connection(self):
        """TLS connection creates SSL context."""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        with patch("benchmark.asyncio.open_connection", new_callable=AsyncMock) as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)
            with patch("benchmark.ssl.create_default_context") as mock_ssl:
                mock_ctx = MagicMock()
                mock_ssl.return_value = mock_ctx
                await benchmark._open_connection("example.com", 443, True)
                mock_open.assert_called_once_with("example.com", 443, ssl=mock_ctx)

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        """Connection timeout raises TimeoutError."""
        with patch("benchmark.asyncio.open_connection", new_callable=AsyncMock) as mock_open:
            mock_open.side_effect = asyncio.TimeoutError()
            with pytest.raises(asyncio.TimeoutError):
                await benchmark._open_connection("localhost", 8000, False, timeout=1.0)


class TestSendRequest:
    """Tests for _send_request() with mocked StreamWriter."""

    @pytest.mark.asyncio
    async def test_get_request(self):
        """GET request writes correct HTTP request line and headers."""
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        await benchmark._send_request(mock_writer, "GET", "localhost", 8000, "/ping")
        written = mock_writer.write.call_args_list[0][0][0].decode()
        assert "GET /ping HTTP/1.1" in written
        assert "Host: localhost:8000" in written
        assert "Connection: close" in written

    @pytest.mark.asyncio
    async def test_post_request_with_body(self):
        """POST request includes headers, Content-Length, and body."""
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        body = b'{"test": true}'
        headers = {"Content-Type": "application/json", "Authorization": "Bearer sk-test"}
        await benchmark._send_request(
            mock_writer, "POST", "localhost", 8000, "/v1/chat/completions", headers, body
        )
        written = mock_writer.write.call_args_list[0][0][0].decode()
        assert "POST /v1/chat/completions HTTP/1.1" in written
        assert "Content-Type: application/json" in written
        assert "Authorization: Bearer sk-test" in written
        assert f"Content-Length: {len(body)}" in written
        assert mock_writer.write.call_args_list[1][0][0] == body

    @pytest.mark.asyncio
    async def test_request_without_body(self):
        """GET request without body only writes headers once."""
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        await benchmark._send_request(mock_writer, "GET", "localhost", 80, "/")
        assert mock_writer.write.call_count == 1

    @pytest.mark.asyncio
    async def test_request_with_custom_headers(self):
        """Custom headers are included in the request."""
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        headers = {"X-Custom": "value123"}
        await benchmark._send_request(mock_writer, "GET", "localhost", 80, "/", headers)
        written = mock_writer.write.call_args_list[0][0][0].decode()
        assert "X-Custom: value123" in written


class TestReadStatusAndHeaders:
    """Tests for _read_status_and_headers() with mocked StreamReader."""

    @pytest.mark.asyncio
    async def test_parse_200_response(self):
        """Parses 200 OK response with headers correctly."""
        lines = [
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Type: text/plain\r\n",
            b"Content-Length: 5\r\n",
            b"\r\n",
        ]
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=lines)
        status, headers = await benchmark._read_status_and_headers(mock_reader)
        assert status == 200
        assert headers["content-type"] == "text/plain"
        assert headers["content-length"] == "5"

    @pytest.mark.asyncio
    async def test_parse_404_response(self):
        """Parses 404 Not Found response."""
        lines = [b"HTTP/1.1 404 Not Found\r\n", b"\r\n"]
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=lines)
        status, headers = await benchmark._read_status_and_headers(mock_reader)
        assert status == 404
        assert headers == {}

    @pytest.mark.asyncio
    async def test_parse_response_no_reason_phrase(self):
        """Parses minimal status line without reason phrase."""
        lines = [b"HTTP/1.1 200\r\n", b"\r\n"]
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=lines)
        status, _headers = await benchmark._read_status_and_headers(mock_reader)
        assert status == 200


class TestBenchEndpoint:
    """Tests for bench_endpoint() with mocked connections."""

    @pytest.mark.asyncio
    async def test_successful_requests(self):
        """Returns latencies for successful requests after warmup."""
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=[b"HTTP/1.1 200 OK\r\n", b"\r\n"] * 3)
        mock_reader.read = AsyncMock(return_value=b"OK")
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        with patch("benchmark._open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.return_value = (mock_reader, mock_writer)
            latencies = await benchmark.bench_endpoint(
                "http://localhost:8000", "/ping", n_requests=2, warmup=1
            )
            assert len(latencies) == 2
            assert all(isinstance(lat, float) for lat in latencies)
            assert all(lat >= 0 for lat in latencies)

    @pytest.mark.asyncio
    async def test_failed_requests_skipped(self):
        """Connection failures produce no latencies."""
        with patch("benchmark._open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.side_effect = ConnectionRefusedError("Connection refused")
            latencies = await benchmark.bench_endpoint(
                "http://localhost:8000", "/ping", n_requests=2, warmup=0
            )
            assert len(latencies) == 0

    @pytest.mark.asyncio
    async def test_warmup_excluded(self):
        """Warmup requests are not included in returned latencies."""
        call_count = 0

        async def mock_open(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            reader = AsyncMock()
            reader.readline = AsyncMock(side_effect=[b"HTTP/1.1 200 OK\r\n", b"\r\n"])
            reader.read = AsyncMock(return_value=b"OK")
            writer = MagicMock()
            writer.drain = AsyncMock()
            writer.close = MagicMock()
            writer.wait_closed = AsyncMock()
            return reader, writer

        with patch("benchmark._open_connection", side_effect=mock_open):
            latencies = await benchmark.bench_endpoint(
                "http://localhost:8000", "/ping", n_requests=3, warmup=2
            )
            assert len(latencies) == 3
            assert call_count == 5


class TestRunGatewayBenchmark:
    """Tests for run_gateway_benchmark()."""

    @pytest.mark.asyncio
    async def test_returns_ping_and_health(self):
        """Returns both ping and health stats with correct structure."""
        with patch("benchmark.bench_endpoint", new_callable=AsyncMock) as mock_bench:
            mock_bench.return_value = [0.001, 0.002, 0.003]
            result = await benchmark.run_gateway_benchmark(
                "http://localhost:8000", n_requests=3, warmup=1
            )
            assert "ping" in result
            assert "health" in result
            assert "latencies" in result["ping"]
            assert "stats" in result["ping"]
            assert "latencies" in result["health"]
            assert "stats" in result["health"]
            assert result["ping"]["stats"]["count"] == 3

    @pytest.mark.asyncio
    async def test_calls_bench_endpoint_twice(self):
        """Both /ping and /health endpoints are benchmarked."""
        with patch("benchmark.bench_endpoint", new_callable=AsyncMock) as mock_bench:
            mock_bench.return_value = [0.001]
            await benchmark.run_gateway_benchmark("http://localhost:8000")
            assert mock_bench.call_count == 2
            paths = [call.args[1] for call in mock_bench.call_args_list]
            assert "/ping" in paths
            assert "/health" in paths


class TestInferenceRequest:
    """Tests for _inference_request() with mocked connections."""

    @pytest.mark.asyncio
    async def test_successful_streaming_request(self):
        """Successful streaming request extracts tokens correctly."""
        sse_body = (
            'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":" world"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        header_lines = [
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Type: text/event-stream\r\n",
            b"\r\n",
        ]
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=header_lines)
        mock_reader.read = AsyncMock(side_effect=[sse_body.encode(), b""])
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        with patch("benchmark._open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.return_value = (mock_reader, mock_writer)
            result = await benchmark._inference_request(
                "http://localhost:8000", "Hello", max_tokens=64
            )
            assert result["error"] is None
            assert result["total_latency"] is not None
            assert result["total_latency"] > 0
            assert result["ttft"] is not None
            assert result["token_count"] >= 1
            assert len(result["tokens"]) >= 1

    @pytest.mark.asyncio
    async def test_non_200_response(self):
        """Non-200 HTTP status is captured as an error."""
        header_lines = [b"HTTP/1.1 401 Unauthorized\r\n", b"\r\n"]
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=header_lines)
        mock_reader.read = AsyncMock(return_value=b'{"error": "unauthorized"}')
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        with patch("benchmark._open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.return_value = (mock_reader, mock_writer)
            result = await benchmark._inference_request(
                "http://localhost:8000", "Hello", max_tokens=64
            )
            assert result["error"] is not None
            assert "401" in result["error"]
            assert result["total_latency"] is not None

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Connection failure sets error and zero latency."""
        with patch("benchmark._open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.side_effect = ConnectionRefusedError("Connection refused")
            result = await benchmark._inference_request(
                "http://localhost:8000", "Hello", max_tokens=64
            )
            assert result["error"] is not None
            assert "Connection refused" in result["error"]
            assert result["total_latency"] == 0.0

    @pytest.mark.asyncio
    async def test_api_key_header_sent(self):
        """API key is sent as Bearer token in Authorization header."""
        header_lines = [b"HTTP/1.1 200 OK\r\n", b"\r\n"]
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=header_lines)
        mock_reader.read = AsyncMock(side_effect=[b"data: [DONE]\n\n", b""])
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        with patch("benchmark._open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.return_value = (mock_reader, mock_writer)
            with patch("benchmark._send_request", new_callable=AsyncMock) as mock_send:
                await benchmark._inference_request(
                    "http://localhost:8000", "Hello", max_tokens=64, api_key="sk-test123"
                )
                sent_headers = mock_send.call_args[0][5]
                assert sent_headers["Authorization"] == "Bearer sk-test123"

    @pytest.mark.asyncio
    async def test_empty_response_no_tokens(self):
        """Response with only DONE marker yields no tokens."""
        header_lines = [
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Type: text/event-stream\r\n",
            b"\r\n",
        ]
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=header_lines)
        mock_reader.read = AsyncMock(side_effect=[b"data: [DONE]\n\n", b""])
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        with patch("benchmark._open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.return_value = (mock_reader, mock_writer)
            result = await benchmark._inference_request(
                "http://localhost:8000", "Hello", max_tokens=64
            )
            assert result["error"] is None
            assert result["tokens"] == []
            assert result["token_count"] == 0
            assert result["ttft"] is None

    @pytest.mark.asyncio
    async def test_timeout_during_streaming(self):
        """Timeout during streaming returns partial results without error."""
        header_lines = [
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Type: text/event-stream\r\n",
            b"\r\n",
        ]
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=header_lines)
        mock_reader.read = AsyncMock(
            side_effect=[
                b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n',
                asyncio.TimeoutError(),
            ]
        )
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        with patch("benchmark._open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.return_value = (mock_reader, mock_writer)
            result = await benchmark._inference_request(
                "http://localhost:8000", "Hello", max_tokens=64, timeout=1.0
            )
            assert result["error"] is None
            assert len(result["tokens"]) >= 1


class TestRunInferenceBenchmark:
    """Tests for run_inference_benchmark()."""

    @pytest.mark.asyncio
    async def test_successful_benchmark(self):
        """Aggregates results from successful inference requests."""
        mock_result = {
            "ttft": 0.1,
            "total_latency": 2.0,
            "tokens": ["Hello", " world"],
            "token_count": 2,
            "error": None,
        }
        with patch("benchmark._inference_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_result
            result = await benchmark.run_inference_benchmark(
                "http://localhost:8000",
                prompt="test",
                max_tokens=64,
                concurrency=1,
                n_requests=3,
                warmup=1,
            )
            assert result["requests_total"] == 3
            assert result["requests_success"] == 3
            assert result["requests_failed"] == 0
            assert result["concurrency"] == 1
            assert result["wall_time"] > 0
            assert result["ttft"]["stats"]["count"] == 3
            assert result["tokens_per_sec"]["stats"]["count"] == 3
            assert result["total_latency"]["stats"]["count"] == 3

    @pytest.mark.asyncio
    async def test_benchmark_with_failures(self):
        """Handles mixed success/failure results correctly."""
        success_result = {
            "ttft": 0.1,
            "total_latency": 2.0,
            "tokens": ["Hello"],
            "token_count": 1,
            "error": None,
        }
        failure_result = {
            "ttft": None,
            "total_latency": None,
            "tokens": [],
            "token_count": 0,
            "error": "Connection refused",
        }
        call_count = 0

        async def mock_inference(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return success_result
            return success_result if call_count % 2 == 0 else failure_result

        with patch("benchmark._inference_request", side_effect=mock_inference):
            result = await benchmark.run_inference_benchmark(
                "http://localhost:8000",
                prompt="test",
                max_tokens=64,
                concurrency=1,
                n_requests=4,
                warmup=1,
            )
            assert result["requests_total"] == 4
            assert result["requests_success"] + result["requests_failed"] == 4

    @pytest.mark.asyncio
    async def test_benchmark_with_concurrency(self):
        """Concurrency parameter controls parallelism."""
        mock_result = {
            "ttft": 0.05,
            "total_latency": 1.0,
            "tokens": ["Hello"],
            "token_count": 1,
            "error": None,
        }
        with patch("benchmark._inference_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_result
            result = await benchmark.run_inference_benchmark(
                "http://localhost:8000",
                prompt="test",
                max_tokens=64,
                concurrency=4,
                n_requests=8,
                warmup=0,
            )
            assert result["concurrency"] == 4
            assert result["requests_total"] == 8
            assert result["requests_success"] == 8

    @pytest.mark.asyncio
    async def test_benchmark_with_api_key(self):
        """API key is passed through to all inference requests."""
        mock_result = {
            "ttft": 0.1,
            "total_latency": 1.0,
            "tokens": ["ok"],
            "token_count": 1,
            "error": None,
        }
        with patch("benchmark._inference_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_result
            await benchmark.run_inference_benchmark(
                "http://localhost:8000",
                api_key="sk-test123",
                n_requests=1,
                warmup=0,
            )
            for call in mock_req.call_args_list:
                assert call[1].get("api_key") == "sk-test123" or call[0][3] == "sk-test123"


class TestAsyncMain:
    """Tests for async_main() with mocked benchmark functions."""

    @pytest.mark.asyncio
    async def test_gateway_only_mode(self, capsys):
        """Gateway-only flag skips inference benchmarks."""
        args = argparse.Namespace(
            url="http://localhost:8000",
            output="text",
            gateway_only=True,
            requests=5,
            warmup=1,
            prompt="test",
            max_tokens=64,
            concurrency=1,
            api_key=None,
        )
        mock_gw_result = {
            "ping": {"latencies": [0.001], "stats": benchmark.compute_stats([0.001])},
            "health": {"latencies": [0.002], "stats": benchmark.compute_stats([0.002])},
        }
        with patch("benchmark.run_gateway_benchmark", new_callable=AsyncMock) as mock_gw:
            mock_gw.return_value = mock_gw_result
            with patch("benchmark.run_inference_benchmark", new_callable=AsyncMock) as mock_inf:
                await benchmark.async_main(args)
                mock_gw.assert_called_once()
                mock_inf.assert_not_called()
        captured = capsys.readouterr()
        assert "Gateway Overhead" in captured.out

    @pytest.mark.asyncio
    async def test_full_benchmark_mode(self, capsys):
        """Full mode runs both gateway and inference benchmarks."""
        args = argparse.Namespace(
            url="http://localhost:8000",
            output="text",
            gateway_only=False,
            requests=5,
            warmup=1,
            prompt="test prompt",
            max_tokens=64,
            concurrency=2,
            api_key="sk-test",
        )
        mock_gw_result = {
            "ping": {"latencies": [0.001], "stats": benchmark.compute_stats([0.001])},
            "health": {"latencies": [0.002], "stats": benchmark.compute_stats([0.002])},
        }
        mock_inf_result = {
            "ttft": {"values": [0.1], "stats": benchmark.compute_stats([0.1])},
            "tokens_per_sec": {"values": [30.0], "stats": benchmark.compute_stats([30.0])},
            "total_latency": {"values": [2.0], "stats": benchmark.compute_stats([2.0])},
            "requests_total": 5,
            "requests_success": 5,
            "requests_failed": 0,
            "wall_time": 10.0,
            "concurrency": 2,
        }
        with patch("benchmark.run_gateway_benchmark", new_callable=AsyncMock) as mock_gw:
            mock_gw.return_value = mock_gw_result
            with patch("benchmark.run_inference_benchmark", new_callable=AsyncMock) as mock_inf:
                mock_inf.return_value = mock_inf_result
                await benchmark.async_main(args)
                mock_gw.assert_called_once()
                mock_inf.assert_called_once()
        captured = capsys.readouterr()
        assert "Gateway Overhead" in captured.out
        assert "Inference Performance" in captured.out

    @pytest.mark.asyncio
    async def test_json_output_mode(self, capsys):
        """JSON output mode produces valid JSON to stdout."""
        args = argparse.Namespace(
            url="http://localhost:8000",
            output="json",
            gateway_only=True,
            requests=5,
            warmup=1,
            prompt="test",
            max_tokens=64,
            concurrency=1,
            api_key=None,
        )
        mock_gw_result = {
            "ping": {"latencies": [0.001], "stats": benchmark.compute_stats([0.001])},
            "health": {"latencies": [0.002], "stats": benchmark.compute_stats([0.002])},
        }
        with patch("benchmark.run_gateway_benchmark", new_callable=AsyncMock) as mock_gw:
            mock_gw.return_value = mock_gw_result
            await benchmark.async_main(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "gateway" in data

    @pytest.mark.asyncio
    async def test_stderr_progress_in_text_mode(self, capsys):
        """Text mode prints progress messages to stderr."""
        args = argparse.Namespace(
            url="http://localhost:8000",
            output="text",
            gateway_only=True,
            requests=3,
            warmup=0,
            prompt="test",
            max_tokens=64,
            concurrency=1,
            api_key=None,
        )
        mock_gw_result = {
            "ping": {"latencies": [0.001], "stats": benchmark.compute_stats([0.001])},
            "health": {"latencies": [0.001], "stats": benchmark.compute_stats([0.001])},
        }
        with patch("benchmark.run_gateway_benchmark", new_callable=AsyncMock) as mock_gw:
            mock_gw.return_value = mock_gw_result
            await benchmark.async_main(args)
        captured = capsys.readouterr()
        assert "Benchmarking gateway" in captured.err

    @pytest.mark.asyncio
    async def test_no_stderr_progress_in_json_mode(self, capsys):
        """JSON mode suppresses progress messages on stderr."""
        args = argparse.Namespace(
            url="http://localhost:8000",
            output="json",
            gateway_only=True,
            requests=3,
            warmup=0,
            prompt="test",
            max_tokens=64,
            concurrency=1,
            api_key=None,
        )
        mock_gw_result = {
            "ping": {"latencies": [0.001], "stats": benchmark.compute_stats([0.001])},
            "health": {"latencies": [0.001], "stats": benchmark.compute_stats([0.001])},
        }
        with patch("benchmark.run_gateway_benchmark", new_callable=AsyncMock) as mock_gw:
            mock_gw.return_value = mock_gw_result
            await benchmark.async_main(args)
        captured = capsys.readouterr()
        assert "Benchmarking" not in captured.err


class TestMainEntryPoint:
    """Tests for main() entry point."""

    def test_main_calls_asyncio_run(self):
        """Entry point builds parser and calls asyncio.run."""
        with patch("benchmark.build_parser") as mock_parser:
            mock_args = MagicMock()
            mock_parser.return_value.parse_args.return_value = mock_args
            with patch("benchmark.asyncio.run") as mock_run:
                benchmark.main()
                mock_run.assert_called_once()
                coro = mock_run.call_args[0][0]
                assert coro is not None
                coro.close()
