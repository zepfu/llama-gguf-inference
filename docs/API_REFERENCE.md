# API Reference

Complete HTTP API reference for the llama-gguf-inference gateway.

The gateway listens on port 8000 (configurable via `GATEWAY_PORT` or `PORT`) and proxies authenticated requests to the
llama-server backend on port 8080. Health and metrics endpoints are always public. All API endpoints follow the OpenAI
API format.

______________________________________________________________________

## Public Endpoints

These endpoints require **no authentication** and do not touch the backend, making them safe for platform health checks
and scale-to-zero environments.

### GET /ping

Lightweight liveness probe. Returns immediately without contacting the backend. Designed for RunPod Serverless and
similar platforms that poll a health endpoint to decide whether to keep a worker active.

**Auth required:** No

**Response:**

- **200 OK** with empty body

**Headers:**

| Header           | Value   |
| ---------------- | ------- |
| `Content-Length` | `0`     |
| `Connection`     | `close` |

**Example:**

```bash
curl -i http://localhost:8000/ping
```

```
HTTP/1.1 200 OK
Content-Length: 0
Connection: close
```

______________________________________________________________________

### GET /health

Detailed health status including backend readiness, gateway metrics, queue state, and authentication status. Queries the
backend's `/health` endpoint with a configurable timeout (`HEALTH_TIMEOUT`, default 2 seconds).

**Auth required:** No

**Response:**

- **200 OK** with JSON body

**Response body:**

```json
{
  "status": "ok",
  "code": 200,
  "backend": {
    "status": "ok"
  },
  "gateway": {
    "status": "ok",
    "metrics": {
      "requests_total": 42,
      "requests_success": 40,
      "requests_error": 2,
      "requests_active": 1,
      "requests_authenticated": 39,
      "requests_unauthorized": 1,
      "bytes_sent": 123456,
      "queue_depth": 0,
      "queue_rejections": 0,
      "queue_wait_seconds_total": 1.234,
      "uptime_seconds": 3600
    }
  },
  "queue": {
    "max_concurrent": 1,
    "max_queue_size": 0,
    "active": 0,
    "waiting": 0
  },
  "authentication": {
    "enabled": true
  }
}
```

| Field                    | Description                                              |
| ------------------------ | -------------------------------------------------------- |
| `status`                 | Backend health check result: `ok`, `timeout`, or `error` |
| `code`                   | HTTP status code from the backend health endpoint        |
| `backend`                | Parsed JSON from llama-server's `/health` response       |
| `gateway.metrics`        | Current gateway counters (same data as `/metrics`)       |
| `queue.max_concurrent`   | Value of `MAX_CONCURRENT_REQUESTS`                       |
| `queue.max_queue_size`   | Value of `MAX_QUEUE_SIZE` (0 = unlimited)                |
| `queue.active`           | Requests currently being proxied to backend              |
| `queue.waiting`          | Requests waiting for a concurrency slot                  |
| `authentication.enabled` | Whether API key auth is active                           |

**Example:**

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

______________________________________________________________________

### GET /metrics

Gateway metrics. Supports content negotiation: returns JSON by default, or Prometheus text exposition format when the
`Accept` header includes `text/plain` or `application/openmetrics-text`.

**Auth required:** No

#### JSON format (default)

**Request:**

```bash
curl -s http://localhost:8000/metrics
```

**Response (200 OK):**

```json
{
  "gateway": {
    "requests_total": 100,
    "requests_success": 95,
    "requests_error": 5,
    "requests_active": 1,
    "requests_authenticated": 90,
    "requests_unauthorized": 3,
    "bytes_sent": 524288,
    "queue_depth": 0,
    "queue_rejections": 2,
    "queue_wait_seconds_total": 12.345,
    "uptime_seconds": 7200
  }
}
```

| Metric                     | Type    | Description                                             |
| -------------------------- | ------- | ------------------------------------------------------- |
| `requests_total`           | counter | Total requests handled by the gateway                   |
| `requests_success`         | counter | Requests successfully proxied to backend                |
| `requests_error`           | counter | Requests that failed (backend unreachable, proxy error) |
| `requests_active`          | gauge   | Requests currently in flight                            |
| `requests_authenticated`   | counter | Requests that passed authentication                     |
| `requests_unauthorized`    | counter | Requests rejected by auth (401)                         |
| `bytes_sent`               | counter | Total response bytes sent to clients                    |
| `queue_depth`              | gauge   | Requests currently waiting for a concurrency slot       |
| `queue_rejections`         | counter | Requests rejected because the queue was full (503)      |
| `queue_wait_seconds_total` | counter | Cumulative time requests spent waiting in queue         |
| `uptime_seconds`           | gauge   | Seconds since gateway started                           |

:::{note} Per-key authentication metrics are excluded from the unauthenticated `/metrics` endpoint to prevent key ID
disclosure. Per-key stats are available via the `/health` endpoint's gateway metrics when authentication context is
available. :::

#### Prometheus format

**Request:**

```bash
curl -s -H "Accept: text/plain" http://localhost:8000/metrics
```

**Response (200 OK, Content-Type: `text/plain; version=0.0.4; charset=utf-8`):**

```
# HELP gateway_requests_total Total requests handled
# TYPE gateway_requests_total counter
gateway_requests_total 100
# HELP gateway_requests_success Total successful requests
# TYPE gateway_requests_success counter
gateway_requests_success 95
# HELP gateway_requests_error Total failed requests
# TYPE gateway_requests_error counter
gateway_requests_error 5
# HELP gateway_requests_active Currently active requests
# TYPE gateway_requests_active gauge
gateway_requests_active 1
# HELP gateway_requests_authenticated Total authenticated requests
# TYPE gateway_requests_authenticated counter
gateway_requests_authenticated 90
# HELP gateway_requests_unauthorized Total unauthorized requests
# TYPE gateway_requests_unauthorized counter
gateway_requests_unauthorized 3
# HELP gateway_bytes_sent Total bytes sent to clients
# TYPE gateway_bytes_sent counter
gateway_bytes_sent 524288
# HELP gateway_queue_depth Current requests waiting for semaphore
# TYPE gateway_queue_depth gauge
gateway_queue_depth 0
# HELP gateway_queue_rejections Total requests rejected due to full queue
# TYPE gateway_queue_rejections counter
gateway_queue_rejections 2
# HELP gateway_queue_wait_seconds_total Cumulative queue wait time in seconds
# TYPE gateway_queue_wait_seconds_total counter
gateway_queue_wait_seconds_total 12.345
# HELP gateway_uptime_seconds Gateway uptime in seconds
# TYPE gateway_uptime_seconds gauge
gateway_uptime_seconds 7200
```

**Prometheus scrape config example:**

```yaml
scrape_configs:
  - job_name: "llama-gateway"
    metrics_path: "/metrics"
    scrape_interval: 15s
    static_configs:
      - targets: ["localhost:8000"]
    # Request Prometheus format via Accept header
    params: {}
    # Override default Accept header
    honor_labels: true
```

______________________________________________________________________

### OPTIONS (any path)

CORS preflight handler. Returns 204 No Content with CORS headers when `CORS_ORIGINS` is configured. No authentication
required.

**Auth required:** No

**Precondition:** `CORS_ORIGINS` environment variable must be set (otherwise no CORS headers are returned).

**Response:**

- **204 No Content**

**CORS headers (when enabled):**

| Header                         | Value                                           |
| ------------------------------ | ----------------------------------------------- |
| `Access-Control-Allow-Origin`  | Matching origin or `*`                          |
| `Access-Control-Allow-Methods` | `GET, POST, OPTIONS`                            |
| `Access-Control-Allow-Headers` | `Authorization, Content-Type`                   |
| `Access-Control-Max-Age`       | `86400` (24 hours)                              |
| `Vary`                         | `Origin` (only in allowlist mode, not wildcard) |

**Example:**

```bash
curl -i -X OPTIONS \
  -H "Origin: https://my-app.example.com" \
  http://localhost:8000/v1/chat/completions
```

______________________________________________________________________

### POST /reload

Hot-reload API keys from the keys file without restarting the gateway. The reload is atomic: either all keys are
replaced successfully, or the previous key set is preserved unchanged. Rate limiter state (request timestamps) is
preserved across reloads so existing rate limits for known keys survive.

**Auth required:** Yes

**Response (200 OK):**

```json
{
  "status": "ok",
  "keys_loaded": 3
}
```

| Field         | Type    | Description                             |
| ------------- | ------- | --------------------------------------- |
| `status`      | string  | Always `"ok"` on success                |
| `keys_loaded` | integer | Number of API keys loaded from the file |

**Error responses:**

- **500 Internal Server Error** — Auth module not available or reload failed

```json
{
  "error": {
    "message": "Reload failed: <details>",
    "type": "server_error",
    "code": "reload_failed"
  }
}
```

**Example:**

```bash
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8000/reload
```

You can also trigger a reload via the SIGHUP signal:

```bash
# Via Docker
docker kill -s HUP my-inference-container

# Via process signal (inside the container)
kill -HUP $(pgrep -f gateway.py)
```

______________________________________________________________________

## Protected Endpoints

All endpoints not listed above require authentication when `AUTH_ENABLED=true` (the default). The gateway proxies these
requests to the llama-server backend.

Authentication uses the `Authorization` header with a Bearer token:

```
Authorization: Bearer <key_id>:<api_key>
```

Or without the `Bearer` prefix:

```
Authorization: <key_id>:<api_key>
```

See the [Authentication](#authentication) section below for details.

______________________________________________________________________

### POST /v1/chat/completions

Generate a chat completion. This is the primary inference endpoint, compatible with the OpenAI Chat Completions API.

**Auth required:** Yes

**Request headers:**

| Header          | Required | Description        |
| --------------- | -------- | ------------------ |
| `Authorization` | Yes      | `Bearer <api_key>` |
| `Content-Type`  | Yes      | `application/json` |

**Request body:**

```json
{
  "model": "any",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "temperature": 0.7,
  "max_tokens": 256,
  "stream": false
}
```

| Field               | Type         | Required | Description                                                            |
| ------------------- | ------------ | -------- | ---------------------------------------------------------------------- |
| `model`             | string       | Yes      | Model identifier (any string accepted; the container serves one model) |
| `messages`          | array        | Yes      | Array of message objects with `role` and `content`                     |
| `temperature`       | float        | No       | Sampling temperature (0.0-2.0)                                         |
| `max_tokens`        | integer      | No       | Maximum tokens to generate                                             |
| `stream`            | boolean      | No       | Enable Server-Sent Events streaming (default: false)                   |
| `top_p`             | float        | No       | Nucleus sampling parameter                                             |
| `frequency_penalty` | float        | No       | Frequency penalty (-2.0 to 2.0)                                        |
| `presence_penalty`  | float        | No       | Presence penalty (-2.0 to 2.0)                                         |
| `stop`              | string/array | No       | Stop sequences                                                         |

:::{note} The `model` field is required by the OpenAI API format but its value does not matter -- the container always
serves the single model it was started with. :::

**Response (non-streaming, 200 OK):**

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "your-model-name",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm doing well, thank you for asking."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 12,
    "total_tokens": 37
  }
}
```

**Response (streaming, 200 OK):**

When `"stream": true`, the response uses Server-Sent Events (SSE). Each event is a line prefixed with `data: `
containing a JSON chunk:

```
data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}

data: [DONE]
```

**Example (non-streaming):**

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "any",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 50
  }'
```

**Example (streaming):**

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "any",
    "messages": [{"role": "user", "content": "Say hello"}],
    "stream": true
  }'
```

______________________________________________________________________

### POST /v1/completions

Generate a text completion (legacy completions API). Compatible with the OpenAI Completions API.

**Auth required:** Yes

**Request headers:**

| Header          | Required | Description        |
| --------------- | -------- | ------------------ |
| `Authorization` | Yes      | `Bearer <api_key>` |
| `Content-Type`  | Yes      | `application/json` |

**Request body:**

```json
{
  "model": "any",
  "prompt": "Once upon a time",
  "max_tokens": 100,
  "temperature": 0.7
}
```

| Field         | Type         | Required | Description                   |
| ------------- | ------------ | -------- | ----------------------------- |
| `model`       | string       | Yes      | Model identifier (any string) |
| `prompt`      | string       | Yes      | Text prompt to complete       |
| `max_tokens`  | integer      | No       | Maximum tokens to generate    |
| `temperature` | float        | No       | Sampling temperature          |
| `stream`      | boolean      | No       | Enable SSE streaming          |
| `stop`        | string/array | No       | Stop sequences                |

**Example:**

```bash
curl -s http://localhost:8000/v1/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "any",
    "prompt": "The capital of France is",
    "max_tokens": 20
  }'
```

______________________________________________________________________

### GET /v1/models

List available models. Returns a single model entry (one container = one model).

**Auth required:** Yes

**Request headers:**

| Header          | Required | Description        |
| --------------- | -------- | ------------------ |
| `Authorization` | Yes      | `Bearer <api_key>` |

**Response (200 OK):**

```json
{
  "object": "list",
  "data": [
    {
      "id": "your-model-name",
      "object": "model",
      "owned_by": "local"
    }
  ]
}
```

**Example:**

```bash
curl -s http://localhost:8000/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY" | python3 -m json.tool
```

______________________________________________________________________

### POST /v1/embeddings

Generate text embeddings. Only available if the loaded model supports embeddings (llama-server must be started with
embedding support).

**Auth required:** Yes

**Request headers:**

| Header          | Required | Description        |
| --------------- | -------- | ------------------ |
| `Authorization` | Yes      | `Bearer <api_key>` |
| `Content-Type`  | Yes      | `application/json` |

**Request body:**

```json
{
  "model": "any",
  "input": "The quick brown fox jumps over the lazy dog"
}
```

| Field   | Type         | Required | Description                     |
| ------- | ------------ | -------- | ------------------------------- |
| `model` | string       | Yes      | Model identifier (any string)   |
| `input` | string/array | Yes      | Text or array of texts to embed |

**Response (200 OK):**

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [0.0023, -0.0091, 0.0152, ...],
      "index": 0
    }
  ],
  "model": "your-model-name",
  "usage": {
    "prompt_tokens": 9,
    "total_tokens": 9
  }
}
```

**Example:**

```bash
curl -s http://localhost:8000/v1/embeddings \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "any",
    "input": "Hello world"
  }'
```

______________________________________________________________________

### Other Paths

Any request path not matching the endpoints above is proxied directly to the llama-server backend with authentication
enforced. This allows access to any additional endpoints that llama-server exposes.

**Auth required:** Yes

______________________________________________________________________

## Authentication

Authentication is enabled by default (`AUTH_ENABLED=true`). When enabled, all endpoints except `/ping`, `/health`,
`/metrics`, and `OPTIONS` require a valid API key.

### Header Format

```
Authorization: Bearer <api_key>
```

The `Bearer` prefix is optional. Both of these are accepted:

```bash
# With Bearer prefix (OpenAI standard)
curl -H "Authorization: Bearer sk-prod-abc123def456" ...

# Without prefix (also works)
curl -H "Authorization: sk-prod-abc123def456" ...
```

### Key Format

API keys are stored in a flat file with the format `key_id:api_key`:

```
production:sk-prod-abc123def456ghi789jkl012mno345
development:sk-dev-xyz789abc123def456ghi789jkl012
```

- **key_id**: Alphanumeric characters, hyphens, and underscores. Used for logging and rate limiting.
- **api_key**: 16-128 characters. Alphanumeric, hyphens, and underscores.

The `Authorization` header carries the `api_key` portion only (not the `key_id`). The gateway looks up the `key_id` from
the stored mapping.

### Key Validation

Keys are validated using constant-time comparison (`hmac.compare_digest`) to prevent timing attacks. All stored keys are
checked on every request regardless of whether a match is found early, ensuring consistent response times.

### Rate Limiting

Rate limits are enforced **per key_id** using a sliding window of 60 seconds.

| Variable                  | Default | Description                                      |
| ------------------------- | ------- | ------------------------------------------------ |
| `MAX_REQUESTS_PER_MINUTE` | `100`   | Maximum requests per key_id per 60-second window |

When the rate limit is exceeded, the gateway returns 429 with a `Retry-After: 60` header. See
[Error Responses](#error-responses) below.

### Disabling Authentication

Set `AUTH_ENABLED=false` to allow all requests without authentication. This is intended for local development and
testing only.

For the full authentication guide, including key management, rotation, and security best practices, see
[AUTHENTICATION.md](AUTHENTICATION.md).

______________________________________________________________________

## Error Responses

All error responses use an OpenAI-compatible JSON format:

```json
{
  "error": {
    "message": "Human-readable error description",
    "type": "error_type",
    "code": "error_code"
  }
}
```

Some errors include an additional `param` field indicating which request parameter caused the error.

### 401 Unauthorized

Returned when authentication fails. Possible messages:

| Message                                            | Cause                                                                               |
| -------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `Missing Authorization header`                     | No `Authorization` header in request                                                |
| `Empty Authorization header`                       | Header present but no key value                                                     |
| `Invalid API key format`                           | Key does not match expected format (16-128 chars, alphanumeric/hyphens/underscores) |
| `Invalid API key`                                  | Key format is valid but does not match any configured key                           |
| `Authentication misconfigured: no API keys loaded` | Auth is enabled but the keys file is missing or empty                               |

**Response:**

```json
{
  "error": {
    "message": "Invalid API key",
    "type": "invalid_request_error",
    "param": "authorization",
    "code": "invalid_api_key"
  }
}
```

**Example:**

```bash
curl -s http://localhost:8000/v1/models | python3 -m json.tool
```

```json
{
  "error": {
    "message": "Missing Authorization header",
    "type": "invalid_request_error",
    "param": "authorization",
    "code": "invalid_api_key"
  }
}
```

______________________________________________________________________

### 413 Payload Too Large

Returned when the request body exceeds `MAX_REQUEST_BODY_SIZE` (default: 10 MB). The check is performed on the
`Content-Length` header before reading the body.

**Response:**

```json
{
  "error": {
    "message": "Request body too large (max 10485760 bytes)",
    "type": "invalid_request_error",
    "code": "payload_too_large"
  }
}
```

______________________________________________________________________

### 429 Too Many Requests

Returned when a key_id exceeds its per-minute rate limit. Includes a `Retry-After` header indicating how long to wait.

**Response headers:**

```
Retry-After: 60
```

**Response body:**

```json
{
  "error": {
    "message": "Rate limit exceeded. Please slow down your requests.",
    "type": "rate_limit_error",
    "code": "rate_limit_exceeded"
  }
}
```

______________________________________________________________________

### 431 Request Header Fields Too Large

Returned when the request exceeds header limits:

- More than `MAX_HEADERS` headers (default: 64)
- Any single header line exceeds `MAX_HEADER_LINE_SIZE` bytes (default: 8192)

**Response:**

```json
{
  "error": {
    "message": "Request headers too large or too many headers",
    "type": "invalid_request_error",
    "code": "header_fields_too_large"
  }
}
```

______________________________________________________________________

### 400 Bad Request

Returned when the request is malformed. Common causes include a non-numeric or negative `Content-Length` header.

**Response:**

```json
{
  "error": {
    "message": "Invalid Content-Length",
    "type": "invalid_request_error",
    "code": "bad_request"
  }
}
```

______________________________________________________________________

### 414 URI Too Long

Returned when the HTTP request line (method + path + protocol) exceeds `MAX_REQUEST_LINE_SIZE` (default: 8192 bytes).

**Response:**

```json
{
  "error": {
    "message": "Request line too long (max 8192 bytes)",
    "type": "invalid_request_error",
    "code": "uri_too_long"
  }
}
```

______________________________________________________________________

### 502 Bad Gateway

Returned when the gateway cannot connect to the llama-server backend or when a proxy error occurs during request
forwarding.

**Response:**

Empty body with `Content-Length: 0`.

```bash
HTTP/1.1 502 Bad Gateway
Content-Length: 0
Connection: close
```

This typically means:

- The llama-server backend is not running
- The backend is still loading the model
- A network error occurred between gateway and backend

Check the `/health` endpoint for backend status.

______________________________________________________________________

### 503 Service Unavailable

Returned when the request queue is full. Only occurs when `MAX_QUEUE_SIZE` is set to a non-zero value and that many
requests are already queued.

**Response headers:**

```
Retry-After: 5
```

**Response body:**

```json
{
  "error": {
    "message": "Server busy, try again later",
    "type": "server_error",
    "code": "queue_full"
  }
}
```

______________________________________________________________________

### 504 Gateway Timeout

Returned when a proxied request to the llama-server backend exceeds `REQUEST_TIMEOUT` (default: 300 seconds). This
typically occurs with large generation requests or when the backend is under heavy load.

**Response:**

```json
{
  "error": {
    "message": "Request timed out",
    "type": "timeout_error",
    "code": 504
  }
}
```

______________________________________________________________________

## Configuration Summary

Key environment variables that affect API behavior. For the complete configuration reference, see
[CONFIGURATION.md](CONFIGURATION.md).

### Ports

| Variable                | Default | Description                                      |
| ----------------------- | ------- | ------------------------------------------------ |
| `GATEWAY_PORT` / `PORT` | `8000`  | Gateway listen port                              |
| `PORT_HEALTH`           | `8001`  | Dedicated health check server (separate process) |
| `PORT_BACKEND`          | `8080`  | Internal llama-server port                       |

### Authentication

| Variable                  | Default                  | Description                           |
| ------------------------- | ------------------------ | ------------------------------------- |
| `AUTH_ENABLED`            | `true`                   | Enable API key authentication         |
| `AUTH_KEYS_FILE`          | `$DATA_DIR/api_keys.txt` | Path to API keys file                 |
| `MAX_REQUESTS_PER_MINUTE` | `100`                    | Rate limit per key_id                 |
| `METRICS_AUTH_ENABLED`    | `false`                  | Require authentication for `/metrics` |

### Request Limits

| Variable                  | Default            | Description                            |
| ------------------------- | ------------------ | -------------------------------------- |
| `MAX_REQUEST_BODY_SIZE`   | `10485760` (10 MB) | Maximum request body size              |
| `MAX_HEADERS`             | `64`               | Maximum number of request headers      |
| `MAX_HEADER_LINE_SIZE`    | `8192` (8 KB)      | Maximum size of a single header line   |
| `MAX_REQUEST_LINE_SIZE`   | `8192` (8 KB)      | Maximum size of HTTP request line      |
| `REQUEST_TIMEOUT`         | `300` (5 min)      | Maximum time for a proxied request     |
| `BACKEND_CONNECT_TIMEOUT` | `10`               | Backend TCP connect timeout in seconds |
| `CLIENT_HEADER_TIMEOUT`   | `30`               | Client header read timeout in seconds  |
| `HEALTH_TIMEOUT`          | `2`                | Timeout for backend health checks      |

### Concurrency

| Variable                  | Default | Description                          |
| ------------------------- | ------- | ------------------------------------ |
| `MAX_CONCURRENT_REQUESTS` | `1`     | Max simultaneous requests to backend |
| `MAX_QUEUE_SIZE`          | `0`     | Max queued requests (0 = unlimited)  |

### CORS

| Variable       | Default         | Description                     |
| -------------- | --------------- | ------------------------------- |
| `CORS_ORIGINS` | `""` (disabled) | Comma-separated allowed origins |

______________________________________________________________________

## OpenAI SDK Compatibility

The gateway is designed as a drop-in replacement for the OpenAI API. Use the standard `openai` Python SDK by pointing it
at your gateway URL.

### Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="YOUR_API_KEY",
)

# Chat completion
response = client.chat.completions.create(
    model="any",  # Value does not matter; one container = one model
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
    ],
    max_tokens=100,
)
print(response.choices[0].message.content)
```

### Streaming

```python
stream = client.chat.completions.create(
    model="any",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### Embeddings

```python
response = client.embeddings.create(
    model="any",
    input="Hello world",
)
print(response.data[0].embedding[:5])  # First 5 dimensions
```

### List Models

```python
models = client.models.list()
for model in models.data:
    print(model.id)
```

### Using with curl

```bash
# Set your base URL and key
export LLAMA_URL="http://localhost:8000"
export LLAMA_KEY="YOUR_API_KEY"

# Chat completion
curl -s "$LLAMA_URL/v1/chat/completions" \
  -H "Authorization: Bearer $LLAMA_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "any",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# List models
curl -s "$LLAMA_URL/v1/models" \
  -H "Authorization: Bearer $LLAMA_KEY"

# Health check (no auth)
curl -s "$LLAMA_URL/health"

# Metrics in Prometheus format
curl -s -H "Accept: text/plain" "$LLAMA_URL/metrics"
```

______________________________________________________________________

## Health Check Server (Port 8001)

In addition to the gateway's `/ping` and `/health` endpoints on port 8000, a separate lightweight health check server
runs on port 8001 (configurable via `PORT_HEALTH`). This server is a minimal HTTP server that returns 200 OK for **all**
GET requests regardless of path.

This dedicated server exists to support platforms like RunPod Serverless that need a health endpoint that never
interacts with the inference backend, enabling proper scale-to-zero behavior.

```bash
# All paths return 200 OK on the health port
curl http://localhost:8001/
curl http://localhost:8001/health
curl http://localhost:8001/anything
```

The health server runs as a separate process from the gateway and has no connection to the backend or authentication
system.

______________________________________________________________________

## Architecture Overview

```
Client
  |
  |-- :8001 --> Health Server (all GET = 200, no backend contact)
  |
  |-- :8000 --> Gateway
                  |
                  |-- /ping          --> 200 (no auth, no backend)
                  |-- /health        --> backend health check (no auth)
                  |-- /metrics       --> gateway counters (no auth)
                  |-- OPTIONS        --> CORS preflight (no auth)
                  |-- /v1/*          --> [auth] --> [queue] --> llama-server:8080
                  |-- (other paths)  --> [auth] --> [queue] --> llama-server:8080
```
