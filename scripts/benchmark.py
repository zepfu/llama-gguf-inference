#!/usr/bin/env python3
"""
benchmark.py -- Performance benchmarking for llama-gguf-inference gateway.

Measures two categories of performance:

1. Gateway overhead (proxy latency)
   - /ping latency (gateway-only, no backend interaction)
   - /health latency (includes backend health check)

2. End-to-end inference performance
   - Time to first token (TTFT) via SSE streaming
   - Tokens per second (generation throughput)
   - Total request latency
   - Statistics at configurable concurrency levels

Usage::

    python3 scripts/benchmark.py --url http://localhost:8000
    python3 scripts/benchmark.py --url http://localhost:8000 --api-key sk-mykey
    python3 scripts/benchmark.py --url http://localhost:8000 --gateway-only
    python3 scripts/benchmark.py --url http://localhost:8000 --concurrency 4 --requests 20
    python3 scripts/benchmark.py --url http://localhost:8000 --output json

Environment: Python 3.11+ stdlib only (no pip dependencies).
"""

import argparse
import asyncio
import json
import ssl
import statistics
import sys
import time
from typing import Any, Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def percentile(data: list[float], pct: float) -> float:
    """Calculate the given percentile of a sorted list of values.

    Uses the 'nearest rank' method. Returns 0.0 for empty input.

    Args:
        data: List of numeric values (need not be sorted).
        pct: Percentile to compute, in 0-100.

    Returns:
        The percentile value, or 0.0 if data is empty.
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    # nearest-rank index
    k = max(0, min(int(len(sorted_data) * pct / 100.0 + 0.5) - 1, len(sorted_data) - 1))
    return sorted_data[k]


def compute_stats(values: list[float]) -> dict[str, float]:
    """Compute summary statistics for a list of measurements.

    Returns:
        Dict with keys: min, max, mean, p50, p95, p99, count.
    """
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}
    return {
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "count": len(values),
    }


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------


def parse_sse_tokens(sse_data: str) -> list[str]:
    """Extract content tokens from an SSE stream (OpenAI chat completions format).

    Parses lines of the form ``data: {...}`` where the JSON payload contains
    ``choices[0].delta.content``.  The ``[DONE]`` sentinel is ignored.

    Args:
        sse_data: Raw SSE text (may contain multiple ``data:`` lines).

    Returns:
        List of content token strings extracted from the stream.
    """
    tokens: list[str] = []
    for line in sse_data.split("\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
            choices = obj.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    tokens.append(content)
        except (json.JSONDecodeError, IndexError, KeyError):
            continue
    return tokens


def count_tokens_approx(text: str) -> int:
    """Rough token count by splitting on whitespace.

    Good enough for benchmarking throughput; not a real tokenizer.
    """
    return len(text.split())


# ---------------------------------------------------------------------------
# Low-level async HTTP helpers (stdlib only, no urllib for streaming)
# ---------------------------------------------------------------------------


def _parse_url(url: str) -> tuple[str, str, int, bool]:
    """Parse a URL into (host, path, port, use_ssl)."""
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    use_ssl = parsed.scheme == "https"
    default_port = 443 if use_ssl else 80
    port = parsed.port or default_port
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return host, path, port, use_ssl


async def _open_connection(
    host: str, port: int, use_ssl: bool, timeout: float = 10.0
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Open a TCP (or TLS) connection with a timeout."""
    ssl_ctx: Optional[ssl.SSLContext] = None
    if use_ssl:
        ssl_ctx = ssl.create_default_context()
    return await asyncio.wait_for(
        asyncio.open_connection(host, port, ssl=ssl_ctx),
        timeout=timeout,
    )


async def _send_request(
    writer: asyncio.StreamWriter,
    method: str,
    host: str,
    port: int,
    path: str,
    headers: Optional[dict[str, str]] = None,
    body: Optional[bytes] = None,
) -> None:
    """Write a raw HTTP/1.1 request onto *writer*."""
    lines = [f"{method} {path} HTTP/1.1", f"Host: {host}:{port}"]
    if headers:
        for k, v in headers.items():
            lines.append(f"{k}: {v}")
    if body:
        lines.append(f"Content-Length: {len(body)}")
    lines.append("Connection: close")
    lines.append("")
    lines.append("")
    writer.write("\r\n".join(lines).encode())
    if body:
        writer.write(body)
    await writer.drain()


async def _read_status_and_headers(
    reader: asyncio.StreamReader, timeout: float = 30.0
) -> tuple[int, dict[str, str]]:
    """Read the HTTP status line and headers, return (status_code, headers_dict)."""
    first_line = await asyncio.wait_for(reader.readline(), timeout=timeout)
    parts = first_line.decode("utf-8", errors="replace").strip().split(None, 2)
    status_code = int(parts[1]) if len(parts) > 1 else 0

    headers: dict[str, str] = {}
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        decoded = line.decode("utf-8", errors="replace").strip()
        if not decoded:
            break
        if ":" in decoded:
            k, v = decoded.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return status_code, headers


# ---------------------------------------------------------------------------
# Benchmark: gateway overhead
# ---------------------------------------------------------------------------


async def bench_endpoint(
    url: str,
    path: str,
    n_requests: int,
    warmup: int = 1,
) -> list[float]:
    """Measure latency of a simple GET endpoint (e.g. /ping, /health).

    Args:
        url: Base URL of the gateway.
        path: Endpoint path to hit.
        n_requests: Number of measurement requests (after warmup).
        warmup: Number of warmup requests to discard.

    Returns:
        List of latencies in seconds (warmup excluded).
    """
    host, _base_path, port, use_ssl = _parse_url(url)
    latencies: list[float] = []

    for i in range(warmup + n_requests):
        try:
            reader, writer = await _open_connection(host, port, use_ssl)
            t0 = time.monotonic()
            await _send_request(writer, "GET", host, port, path)
            status, _ = await _read_status_and_headers(reader)
            # Read body to completion
            await asyncio.wait_for(reader.read(), timeout=10.0)
            elapsed = time.monotonic() - t0
            writer.close()
            await writer.wait_closed()

            if i >= warmup:
                latencies.append(elapsed)
        except Exception as exc:
            if i >= warmup:
                print(f"  [warn] {path} request failed: {exc}", file=sys.stderr)
    return latencies


async def run_gateway_benchmark(
    url: str,
    n_requests: int = 10,
    warmup: int = 1,
) -> dict[str, Any]:
    """Run gateway overhead benchmarks for /ping and /health.

    Returns:
        Dict with 'ping' and 'health' keys, each containing stats.
    """
    ping_latencies = await bench_endpoint(url, "/ping", n_requests, warmup)
    health_latencies = await bench_endpoint(url, "/health", n_requests, warmup)

    return {
        "ping": {
            "latencies": ping_latencies,
            "stats": compute_stats(ping_latencies),
        },
        "health": {
            "latencies": health_latencies,
            "stats": compute_stats(health_latencies),
        },
    }


# ---------------------------------------------------------------------------
# Benchmark: inference (streaming SSE)
# ---------------------------------------------------------------------------


async def _inference_request(
    url: str,
    prompt: str,
    max_tokens: int,
    api_key: Optional[str] = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Send a single streaming chat completion request and measure performance.

    Returns:
        Dict with keys: ttft, total_latency, tokens, token_count, error.
    """
    host, _base_path, port, use_ssl = _parse_url(url)
    path = "/v1/chat/completions"

    payload = json.dumps(
        {
            "model": "default",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": True,
        }
    ).encode()

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    result: dict[str, Any] = {
        "ttft": None,
        "total_latency": None,
        "tokens": [],
        "token_count": 0,  # nosec B105
        "error": None,
    }

    try:
        reader, writer = await _open_connection(host, port, use_ssl, timeout=10.0)
        t0 = time.monotonic()
        await _send_request(writer, "POST", host, port, path, headers, payload)

        status, resp_headers = await _read_status_and_headers(reader, timeout=timeout)
        if status != 200:
            # Read error body
            body = await asyncio.wait_for(reader.read(), timeout=10.0)
            writer.close()
            await writer.wait_closed()
            result["error"] = f"HTTP {status}: {body.decode('utf-8', errors='replace')[:200]}"
            result["total_latency"] = time.monotonic() - t0
            return result

        # Stream SSE events
        first_token_time: Optional[float] = None
        all_tokens: list[str] = []
        buffer = ""

        while True:
            try:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break

            buffer += chunk.decode("utf-8", errors="replace")

            # Process complete lines in the buffer
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:") :].strip()
                if data_str == "[DONE]":
                    break

                try:
                    obj = json.loads(data_str)
                    choices = obj.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            if first_token_time is None:
                                first_token_time = time.monotonic()
                            all_tokens.append(content)
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue

        t_end = time.monotonic()
        writer.close()
        await writer.wait_closed()

        full_text = "".join(all_tokens)
        result["tokens"] = all_tokens
        result["token_count"] = count_tokens_approx(full_text)
        result["total_latency"] = t_end - t0
        if first_token_time is not None:
            result["ttft"] = first_token_time - t0

    except Exception as exc:
        result["error"] = str(exc)
        if result["total_latency"] is None:
            result["total_latency"] = 0.0

    return result


async def run_inference_benchmark(
    url: str,
    prompt: str = "Write a short poem about the sea",
    max_tokens: int = 128,
    api_key: Optional[str] = None,
    concurrency: int = 1,
    n_requests: int = 10,
    warmup: int = 1,
) -> dict[str, Any]:
    """Run inference benchmarks at the specified concurrency level.

    Args:
        url: Base gateway URL.
        prompt: Prompt to send.
        max_tokens: Maximum tokens to generate.
        api_key: Optional API key.
        concurrency: Number of concurrent requests.
        n_requests: Total number of measured requests.
        warmup: Warmup requests to discard.

    Returns:
        Dict with stats for ttft, tokens_per_sec, total_latency, plus counts.
    """
    # Warmup phase (sequential)
    for _ in range(warmup):
        await _inference_request(url, prompt, max_tokens, api_key)

    # Measurement phase with concurrency
    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict[str, Any]] = []

    async def _run_one() -> dict[str, Any]:
        async with semaphore:
            return await _inference_request(url, prompt, max_tokens, api_key)

    t_total_start = time.monotonic()
    tasks = [asyncio.create_task(_run_one()) for _ in range(n_requests)]
    results = await asyncio.gather(*tasks)
    t_total_end = time.monotonic()

    # Collect metrics
    ttfts: list[float] = []
    tps_values: list[float] = []
    latencies: list[float] = []
    successes = 0
    failures = 0

    for r in results:
        if r["error"]:
            failures += 1
            continue
        successes += 1
        if r["total_latency"] is not None:
            latencies.append(r["total_latency"])
        if r["ttft"] is not None:
            ttfts.append(r["ttft"])
        # Tokens per second: tokens / generation_time
        # generation_time = total_latency - ttft (time spent generating after first token)
        if r["token_count"] > 0 and r["total_latency"] and r["total_latency"] > 0:
            tps = r["token_count"] / r["total_latency"]
            tps_values.append(tps)

    return {
        "ttft": {"values": ttfts, "stats": compute_stats(ttfts)},
        "tokens_per_sec": {"values": tps_values, "stats": compute_stats(tps_values)},
        "total_latency": {"values": latencies, "stats": compute_stats(latencies)},
        "requests_total": n_requests,
        "requests_success": successes,
        "requests_failed": failures,
        "wall_time": t_total_end - t_total_start,
        "concurrency": concurrency,
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _fmt_ms(seconds: float) -> str:
    """Format seconds as milliseconds string."""
    return f"{seconds * 1000:.1f}ms"


def _fmt_s(seconds: float) -> str:
    """Format seconds with one decimal."""
    return f"{seconds:.1f}s"


def format_text_output(
    gateway_results: Optional[dict[str, Any]],
    inference_results: Optional[dict[str, Any]],
) -> str:
    """Format benchmark results as human-readable text.

    Args:
        gateway_results: Output from run_gateway_benchmark, or None.
        inference_results: Output from run_inference_benchmark, or None.

    Returns:
        Formatted multi-line string.
    """
    lines: list[str] = []

    if gateway_results:
        lines.append("=== Gateway Overhead ===")
        for name, key in [("/ping", "ping"), ("/health", "health")]:
            s = gateway_results[key]["stats"]
            lines.append(
                f"{name} latency:    "
                f"{_fmt_ms(s['p50'])} (p50), "
                f"{_fmt_ms(s['p95'])} (p95), "
                f"{_fmt_ms(s['p99'])} (p99)"
            )
        lines.append("")

    if inference_results:
        conc = inference_results["concurrency"]
        total = inference_results["requests_total"]
        lines.append(f"=== Inference Performance (concurrency={conc}, requests={total}) ===")

        ttft_s = inference_results["ttft"]["stats"]
        lines.append(
            f"Time to first token:  "
            f"{_fmt_ms(ttft_s['p50'])} (p50), "
            f"{_fmt_ms(ttft_s['p95'])} (p95), "
            f"{_fmt_ms(ttft_s['p99'])} (p99)"
        )

        tps_s = inference_results["tokens_per_sec"]["stats"]
        lines.append(
            f"Tokens/sec:           "
            f"{tps_s['mean']:.1f} (mean), "
            f"{tps_s['p50']:.1f} (p50), "
            f"{tps_s['min']:.1f} (min)"
        )

        lat_s = inference_results["total_latency"]["stats"]
        lines.append(
            f"Total latency:        "
            f"{_fmt_s(lat_s['p50'])} (p50), "
            f"{_fmt_s(lat_s['p95'])} (p95), "
            f"{_fmt_s(lat_s['p99'])} (p99)"
        )

        succ = inference_results["requests_success"]
        fail = inference_results["requests_failed"]
        wall = inference_results["wall_time"]
        lines.append("")
        lines.append(f"Requests: {total} total, {succ} success, {fail} failed")
        lines.append(f"Total time: {_fmt_s(wall)}")

    return "\n".join(lines)


def format_json_output(
    gateway_results: Optional[dict[str, Any]],
    inference_results: Optional[dict[str, Any]],
) -> str:
    """Format benchmark results as JSON.

    Strips raw value lists to keep output concise; only stats are included.

    Args:
        gateway_results: Output from run_gateway_benchmark, or None.
        inference_results: Output from run_inference_benchmark, or None.

    Returns:
        JSON string.
    """
    output: dict[str, Any] = {}

    if gateway_results:
        output["gateway"] = {
            "ping": gateway_results["ping"]["stats"],
            "health": gateway_results["health"]["stats"],
        }

    if inference_results:
        output["inference"] = {
            "ttft": inference_results["ttft"]["stats"],
            "tokens_per_sec": inference_results["tokens_per_sec"]["stats"],
            "total_latency": inference_results["total_latency"]["stats"],
            "requests_total": inference_results["requests_total"],
            "requests_success": inference_results["requests_success"],
            "requests_failed": inference_results["requests_failed"],
            "wall_time": inference_results["wall_time"],
            "concurrency": inference_results["concurrency"],
        }

    return json.dumps(output, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the benchmark CLI."""
    parser = argparse.ArgumentParser(
        description="Benchmark gateway and inference performance for llama-gguf-inference.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/benchmark.py --url http://localhost:8000\n"
            "  python3 scripts/benchmark.py --url http://localhost:8000 --gateway-only\n"
            "  python3 scripts/benchmark.py --url http://localhost:8000 --concurrency 4\n"
            "  python3 scripts/benchmark.py --url http://localhost:8000 --output json\n"
        ),
    )
    parser.add_argument(
        "--url", required=True, help="Target gateway URL (e.g. http://localhost:8000)"
    )
    parser.add_argument("--api-key", default=None, help="API key for authentication")
    parser.add_argument(
        "--prompt",
        default="Write a short poem about the sea",
        help="Prompt to use for inference (default: 'Write a short poem about the sea')",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=128, help="Max tokens to generate (default: 128)"
    )
    parser.add_argument(
        "--concurrency", type=int, default=1, help="Number of concurrent requests (default: 1)"
    )
    parser.add_argument(
        "--requests", type=int, default=10, help="Total number of requests (default: 10)"
    )
    parser.add_argument(
        "--warmup", type=int, default=1, help="Warmup requests to discard (default: 1)"
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--gateway-only",
        action="store_true",
        help="Only measure gateway overhead (ping + health latency)",
    )
    return parser


async def async_main(args: argparse.Namespace) -> None:
    """Run benchmarks according to parsed CLI arguments."""
    gateway_results: Optional[dict[str, Any]] = None
    inference_results: Optional[dict[str, Any]] = None

    # Always run gateway benchmarks
    if args.output == "text":
        print(f"Benchmarking gateway at {args.url} ...", file=sys.stderr)
    gateway_results = await run_gateway_benchmark(
        args.url, n_requests=args.requests, warmup=args.warmup
    )

    # Run inference benchmarks unless --gateway-only
    if not args.gateway_only:
        if args.output == "text":
            print(
                f"Benchmarking inference (concurrency={args.concurrency}, "
                f"requests={args.requests}) ...",
                file=sys.stderr,
            )
        inference_results = await run_inference_benchmark(
            url=args.url,
            prompt=args.prompt,
            max_tokens=args.max_tokens,
            api_key=args.api_key,
            concurrency=args.concurrency,
            n_requests=args.requests,
            warmup=args.warmup,
        )

    # Output
    if args.output == "json":
        print(format_json_output(gateway_results, inference_results))
    else:
        print(format_text_output(gateway_results, inference_results))


def main() -> None:
    """Entry point for the benchmark CLI."""
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
