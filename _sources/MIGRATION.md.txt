# Migration Guide

Upgrade notes and breaking changes for llama-gguf-inference.

______________________________________________________________________

## Migrating from pre-v1.0.0 to v1.0.0

This section covers all changes you need to be aware of when upgrading to v1.0.0.

### Environment Variable Changes

**Removed: `BACKEND_PORT`**

The `BACKEND_PORT` environment variable has been removed. Use `PORT_BACKEND` instead, which is consistent with `PORT`
and `PORT_HEALTH`. If `BACKEND_PORT` is set, a warning is logged but the value is ignored.

```bash
# Before (removed — no longer works)
BACKEND_PORT=8080

# After (required)
PORT_BACKEND=8080
```

### New Features Requiring Configuration

#### CORS Support

Cross-origin resource sharing (CORS) is now supported but **disabled by default**. If you have browser-based clients
that need to access the API directly, enable it with the `CORS_ORIGINS` environment variable:

```bash
# Allow a single origin
CORS_ORIGINS=https://my-app.example.com

# Allow multiple origins
CORS_ORIGINS=https://app.example.com,https://staging.example.com

# Allow all origins (use with caution)
CORS_ORIGINS=*
```

When enabled, the gateway injects CORS headers into all responses and handles `OPTIONS` preflight requests automatically
(204 No Content, no auth required).

See [CONFIGURATION.md](CONFIGURATION.md) for full CORS configuration details.

#### Concurrency Control

The gateway now queues incoming API requests and forwards them to the llama-server backend with bounded concurrency. Two
new environment variables control this behavior:

| Variable                  | Default | Description                                    |
| ------------------------- | ------- | ---------------------------------------------- |
| `MAX_CONCURRENT_REQUESTS` | `1`     | Max simultaneous requests forwarded to backend |
| `MAX_QUEUE_SIZE`          | `0`     | Max requests waiting in queue (0 = unlimited)  |

Health endpoints (`/ping`, `/health`, `/metrics`) bypass the queue entirely.

When the queue is full, the gateway returns `503 Service Unavailable` with a `Retry-After: 5` header.

```bash
# Allow 4 concurrent requests, queue up to 20
MAX_CONCURRENT_REQUESTS=4
MAX_QUEUE_SIZE=20
```

#### API Key Management CLI

A new command-line tool (`scripts/key_mgmt.py`) provides safe key management with atomic writes and proper file
permissions:

```bash
# Generate a new key
python3 scripts/key_mgmt.py generate --name production

# List configured key IDs (never shows key values)
python3 scripts/key_mgmt.py list

# Rotate a key (regenerate with same key_id)
python3 scripts/key_mgmt.py rotate --name production

# Remove a key
python3 scripts/key_mgmt.py remove --name old-client
```

See [AUTHENTICATION.md](AUTHENTICATION.md) for complete key management documentation.

### Docker Image Tag Structure

Docker images are published to `ghcr.io/zepfu/llama-gguf-inference` with the following tag scheme:

**CUDA images (amd64, GPU):**

| Tag           | Example | Description              |
| ------------- | ------- | ------------------------ |
| `VERSION`     | `1.0.0` | Exact version            |
| `MAJOR.MINOR` | `1.0`   | Latest patch in 1.0.x    |
| `MAJOR`       | `1`     | Latest minor in 1.x      |
| `latest`      | —       | Most recent stable build |
| `cuda`        | —       | Alias for `latest`       |

**CPU images (amd64 + arm64, no GPU):**

| Tag               | Example     | Description            |
| ----------------- | ----------- | ---------------------- |
| `cpu-VERSION`     | `cpu-1.0.0` | Exact version          |
| `cpu-MAJOR.MINOR` | `cpu-1.0`   | Latest patch in 1.0.x  |
| `cpu`             | —           | Most recent stable CPU |

**Pulling a specific version:**

```bash
# CUDA (GPU)
docker pull ghcr.io/zepfu/llama-gguf-inference:1.0.0

# CPU
docker pull ghcr.io/zepfu/llama-gguf-inference:cpu-1.0.0
```

### Authentication Changes

The following authentication behaviors changed in v1.0.0. Most are transparent improvements, but one is a **breaking
change** if you relied on the previous behavior.

**Constant-time key comparison (transparent):** API key validation now uses `hmac.compare_digest` for constant-time
comparison, preventing timing-based attacks. No user action required.

**Fail-closed when no keys loaded (BREAKING):** When `AUTH_ENABLED=true` but no valid keys are loaded (empty file,
missing file, all keys malformed), the gateway now **rejects all API requests**. Previously, this scenario would
fail-open and allow unauthenticated access. If you relied on the old behavior, ensure your keys file is properly
configured before enabling auth.

**Rate limit errors return 429 (was 401):** Rate-limited requests now correctly return `429 Too Many Requests` with a
`Retry-After: 60` header. Previously, rate limit errors returned `401 Unauthorized`. Update any client-side error
handling that checks for rate limit responses.

### Health Endpoint Changes

**Sensitive data removed from `/health`:** The `/health` endpoint no longer exposes the number of loaded API keys or
per-key rate limit data. This information was accessible without authentication and could reveal deployment details to
unauthenticated users.

**Queue info added to `/health`:** The `/health` response now includes a `queue` section showing current concurrency
state:

```json
{
  "queue": {
    "max_concurrent": 4,
    "max_queue_size": 20,
    "active": 2,
    "waiting": 5
  }
}
```

### Post-rc.1 Features

The following features were added after the initial release candidate.

#### Per-Key Rate Limits

API keys now support an optional per-key rate limit override using an extended key format:

```
key_id:api_key:120
```

The third field sets the requests-per-minute limit for that specific key, overriding the global `RATE_LIMIT` value.

#### Key Expiration / TTL

Keys can include an expiration timestamp or relative TTL as a fourth field:

```
# Absolute expiration (ISO 8601)
key_id:api_key::2026-03-01T00:00:00

# Relative TTL (from container start)
key_id:api_key::30d
key_id:api_key::24h
key_id:api_key::60m
```

When a key expires, requests using it receive `401 Unauthorized`.

#### Hot-Reload API Keys

API keys can be reloaded without restarting the container:

- **Signal:** Send `SIGHUP` to the gateway process.
- **HTTP:** `POST /reload` (requires authentication if auth is enabled).

Both methods re-read the keys file and apply changes immediately.

#### Structured JSON Logging

Set `LOG_FORMAT=json` to produce structured JSONL output on stdout. Each log line is a valid JSON object with
`timestamp`, `level`, `message`, and contextual fields. Useful for log aggregation pipelines (Datadog, ELK, etc.).

#### Configurable Timeouts

Three new timeout variables provide fine-grained control:

| Variable                  | Default | Description                                         |
| ------------------------- | ------- | --------------------------------------------------- |
| `REQUEST_TIMEOUT`         | `300`   | Max seconds for a full inference request            |
| `BACKEND_CONNECT_TIMEOUT` | `10`    | Max seconds to establish connection to llama-server |
| `CLIENT_HEADER_TIMEOUT`   | `30`    | Max seconds to receive the complete request headers |

#### Non-Root Container

The container now runs as the `inference` user instead of root. Bind-mounted volumes must be readable by this user (UID
is set at build time). If you previously relied on root access inside the container, update your volume permissions.

#### New Security Limits

| Variable                | Default | Description                                        |
| ----------------------- | ------- | -------------------------------------------------- |
| `MAX_REQUEST_LINE_SIZE` | `8192`  | Maximum request line size in bytes (8 KB)          |
| `METRICS_AUTH_ENABLED`  | `false` | Require authentication for the `/metrics` endpoint |

#### New HTTP Responses

The gateway now returns additional status codes:

- **414 URI Too Long** — Request URI exceeds `MAX_REQUEST_LINE_SIZE`.
- **504 Gateway Timeout** — Backend did not respond within `REQUEST_TIMEOUT`.
- **400 Bad Request** — Malformed request line or headers.

______________________________________________________________________

## Breaking Changes Checklist

Use this checklist when upgrading to v1.0.0:

- [ ] **`BACKEND_PORT` removed** — Replace with `PORT_BACKEND` in deployment configs (`BACKEND_PORT` is ignored)
- [ ] **Auth fail-closed** — If `AUTH_ENABLED=true`, ensure a valid `api_keys.txt` file is mounted with at least one
  key. An empty or missing file now blocks all API requests.
- [ ] **Rate limit status code** — Update client error handling: rate limit errors now return `429` instead of `401`
- [ ] **Health endpoint data** — If you parsed key count or per-key rate limit info from `/health`, that data has been
  removed
- [ ] **Docker image tags** — Update image references to use the new tag scheme (see table above)

______________________________________________________________________

## New Environment Variables Reference

All environment variables added or changed in v1.0.0:

| Variable                  | Default | Status  | Description                                             |
| ------------------------- | ------- | ------- | ------------------------------------------------------- |
| `PORT_BACKEND`            | `8080`  | New     | Internal llama-server port (replaces `BACKEND_PORT`)    |
| `BACKEND_PORT`            | —       | Removed | Ignored; use `PORT_BACKEND` instead                     |
| `PORT_HEALTH`             | `8001`  | New     | Health check port for platform monitoring               |
| `CORS_ORIGINS`            | `""`    | New     | Comma-separated allowed CORS origins (empty = disabled) |
| `MAX_CONCURRENT_REQUESTS` | `1`     | New     | Max simultaneous requests forwarded to the backend      |
| `MAX_QUEUE_SIZE`          | `0`     | New     | Max requests waiting in queue (0 = unlimited)           |
| `WORKER_TYPE`             | `""`    | New     | Worker classification for log organization              |

For the complete environment variable reference, see [CONFIGURATION.md](CONFIGURATION.md).

______________________________________________________________________

## See Also

- [CONFIGURATION.md](CONFIGURATION.md) — Full environment variable reference
- [AUTHENTICATION.md](AUTHENTICATION.md) — Authentication setup and key management
- [DEPLOYMENT.md](DEPLOYMENT.md) — Platform-specific deployment guides
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Diagnosing common issues
