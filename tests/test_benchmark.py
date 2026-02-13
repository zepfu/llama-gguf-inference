"""Unit tests for scripts/benchmark.py -- Benchmark module."""

import json
import os
import sys

import pytest

# Add scripts/ to path so we can import benchmark module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import benchmark  # noqa: E402

# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


class TestPercentile:
    """Tests for the percentile() function."""

    def test_empty_data(self):
        assert benchmark.percentile([], 50) == 0.0

    def test_single_value(self):
        assert benchmark.percentile([5.0], 50) == 5.0
        assert benchmark.percentile([5.0], 99) == 5.0

    def test_p50_even_count(self):
        data = [1.0, 2.0, 3.0, 4.0]
        result = benchmark.percentile(data, 50)
        assert result in (2.0, 3.0)  # nearest-rank, either is acceptable

    def test_p50_odd_count(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = benchmark.percentile(data, 50)
        assert result == 3.0

    def test_p95(self):
        data = list(range(1, 101))  # 1..100
        result = benchmark.percentile([float(x) for x in data], 95)
        assert result >= 95.0

    def test_p99(self):
        data = [float(x) for x in range(1, 101)]
        result = benchmark.percentile(data, 99)
        assert result >= 99.0

    def test_p0(self):
        data = [10.0, 20.0, 30.0]
        result = benchmark.percentile(data, 0)
        assert result == 10.0

    def test_p100(self):
        data = [10.0, 20.0, 30.0]
        result = benchmark.percentile(data, 100)
        assert result == 30.0

    def test_unsorted_input(self):
        data = [50.0, 10.0, 30.0, 20.0, 40.0]
        result = benchmark.percentile(data, 50)
        assert result == 30.0

    def test_original_unchanged(self):
        data = [3.0, 1.0, 2.0]
        benchmark.percentile(data, 50)
        assert data == [3.0, 1.0, 2.0]


class TestComputeStats:
    """Tests for compute_stats()."""

    def test_empty_input(self):
        stats = benchmark.compute_stats([])
        assert stats["count"] == 0
        assert stats["min"] == 0.0
        assert stats["max"] == 0.0
        assert stats["mean"] == 0.0
        assert stats["p50"] == 0.0

    def test_single_value(self):
        stats = benchmark.compute_stats([42.0])
        assert stats["count"] == 1
        assert stats["min"] == 42.0
        assert stats["max"] == 42.0
        assert stats["mean"] == 42.0
        assert stats["p50"] == 42.0
        assert stats["p95"] == 42.0
        assert stats["p99"] == 42.0

    def test_multiple_values(self):
        stats = benchmark.compute_stats([1.0, 2.0, 3.0, 4.0, 5.0])
        assert stats["count"] == 5
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["mean"] == 3.0
        assert stats["p50"] == 3.0

    def test_all_keys_present(self):
        stats = benchmark.compute_stats([1.0])
        expected_keys = {"min", "max", "mean", "p50", "p95", "p99", "count"}
        assert set(stats.keys()) == expected_keys

    def test_all_same_values(self):
        stats = benchmark.compute_stats([7.0, 7.0, 7.0])
        assert stats["min"] == 7.0
        assert stats["max"] == 7.0
        assert stats["mean"] == 7.0
        assert stats["p50"] == 7.0


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------


class TestParseSSETokens:
    """Tests for parse_sse_tokens()."""

    def test_empty_input(self):
        assert benchmark.parse_sse_tokens("") == []

    def test_done_sentinel(self):
        assert benchmark.parse_sse_tokens("data: [DONE]\n") == []

    def test_single_token(self):
        event = 'data: {"choices":[{"delta":{"content":"hello"}}]}\n'
        tokens = benchmark.parse_sse_tokens(event)
        assert tokens == ["hello"]

    def test_multiple_tokens(self):
        events = (
            'data: {"choices":[{"delta":{"content":"Hello"}}]}\n'
            'data: {"choices":[{"delta":{"content":" world"}}]}\n'
            "data: [DONE]\n"
        )
        tokens = benchmark.parse_sse_tokens(events)
        assert tokens == ["Hello", " world"]

    def test_empty_delta(self):
        event = 'data: {"choices":[{"delta":{}}]}\n'
        tokens = benchmark.parse_sse_tokens(event)
        assert tokens == []

    def test_role_delta_ignored(self):
        events = (
            'data: {"choices":[{"delta":{"role":"assistant"}}]}\n'
            'data: {"choices":[{"delta":{"content":"Hi"}}]}\n'
        )
        tokens = benchmark.parse_sse_tokens(events)
        assert tokens == ["Hi"]

    def test_invalid_json_skipped(self):
        events = "data: {invalid json}\n" 'data: {"choices":[{"delta":{"content":"ok"}}]}\n'
        tokens = benchmark.parse_sse_tokens(events)
        assert tokens == ["ok"]

    def test_non_data_lines_skipped(self):
        events = (
            ": comment line\n"
            "event: message\n"
            'data: {"choices":[{"delta":{"content":"token"}}]}\n'
            "\n"
        )
        tokens = benchmark.parse_sse_tokens(events)
        assert tokens == ["token"]

    def test_no_choices(self):
        event = 'data: {"id":"123","object":"chat.completion.chunk"}\n'
        tokens = benchmark.parse_sse_tokens(event)
        assert tokens == []

    def test_null_content_skipped(self):
        event = 'data: {"choices":[{"delta":{"content":null}}]}\n'
        tokens = benchmark.parse_sse_tokens(event)
        assert tokens == []

    def test_whitespace_around_data_prefix(self):
        event = '  data: {"choices":[{"delta":{"content":"x"}}]}  \n'
        tokens = benchmark.parse_sse_tokens(event)
        assert tokens == ["x"]


class TestCountTokensApprox:
    """Tests for count_tokens_approx()."""

    def test_empty(self):
        assert benchmark.count_tokens_approx("") == 0  # "".split() == []

    def test_single_word(self):
        assert benchmark.count_tokens_approx("hello") == 1

    def test_multiple_words(self):
        assert benchmark.count_tokens_approx("the quick brown fox") == 4

    def test_extra_whitespace(self):
        # split() handles multiple spaces
        assert benchmark.count_tokens_approx("a  b   c") == 3


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


class TestFormatTextOutput:
    """Tests for format_text_output()."""

    def test_gateway_only(self):
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
        result = benchmark.format_text_output(None, None)
        assert result == ""


class TestFormatJsonOutput:
    """Tests for format_json_output()."""

    def test_gateway_only(self):
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
        result = benchmark.format_json_output(None, None)
        data = json.loads(result)
        assert data == {}


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


class TestBuildParser:
    """Tests for build_parser() and CLI argument handling."""

    def test_required_url(self):
        parser = benchmark.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_minimal_args(self):
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
        parser = benchmark.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--url", "http://localhost:8000", "--output", "xml"])


# ---------------------------------------------------------------------------
# URL parsing helper
# ---------------------------------------------------------------------------


class TestParseUrl:
    """Tests for _parse_url() internal helper."""

    def test_http_default_port(self):
        host, path, port, use_ssl = benchmark._parse_url("http://localhost/ping")
        assert host == "localhost"
        assert path == "/ping"
        assert port == 80
        assert use_ssl is False

    def test_https_default_port(self):
        host, path, port, use_ssl = benchmark._parse_url("https://example.com/health")
        assert host == "example.com"
        assert path == "/health"
        assert port == 443
        assert use_ssl is True

    def test_custom_port(self):
        host, path, port, use_ssl = benchmark._parse_url("http://localhost:8000/v1/models")
        assert host == "localhost"
        assert path == "/v1/models"
        assert port == 8000
        assert use_ssl is False

    def test_root_path(self):
        host, path, port, use_ssl = benchmark._parse_url("http://localhost:8000")
        assert path == "/"

    def test_query_string(self):
        host, path, port, use_ssl = benchmark._parse_url("http://localhost/api?key=val")
        assert path == "/api?key=val"


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------


class TestFormatHelpers:
    """Tests for _fmt_ms() and _fmt_s()."""

    def test_fmt_ms(self):
        assert benchmark._fmt_ms(0.001) == "1.0ms"
        assert benchmark._fmt_ms(0.0005) == "0.5ms"
        assert benchmark._fmt_ms(1.234) == "1234.0ms"

    def test_fmt_s(self):
        assert benchmark._fmt_s(1.0) == "1.0s"
        assert benchmark._fmt_s(0.5) == "0.5s"
        assert benchmark._fmt_s(123.456) == "123.5s"
