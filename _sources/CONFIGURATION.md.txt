# Configuration Guide

Complete reference for all configuration options.

## Environment Variables

### Authentication Configuration

| Variable                  | Default                  | Description                           |
| ------------------------- | ------------------------ | ------------------------------------- |
| `AUTH_ENABLED`            | `true`                   | Enable/disable API key authentication |
| `AUTH_KEYS_FILE`          | `$DATA_DIR/api_keys.txt` | Path to API keys file                 |
| `MAX_REQUESTS_PER_MINUTE` | `100`                    | Rate limit per API key                |

**Authentication Details:**

API key authentication is enabled by default to secure your endpoint. When enabled:

- API endpoints (`/v1/*`) require valid API key via `Authorization: Bearer <key>` header
- Health endpoints (`/ping`, `/health`, `/metrics`) work without authentication
- Rate limiting is enforced per key_id

**API Keys File Format:**

```
# /data/api_keys.txt
# Format: key_id:api_key

production:sk-prod-abc123def456ghi789
development:sk-dev-xyz789abc123def456
alice-laptop:sk-alice-abc123
testing:sk-test-12345

# Generate keys with:
# openssl rand -hex 32
```

**Examples:**

```bash
# Enable auth with default file location
AUTH_ENABLED=true
# Uses: $DATA_DIR/api_keys.txt

# Custom key file location
AUTH_ENABLED=true
AUTH_KEYS_FILE=/mnt/secrets/my-keys.txt

# Disable auth (testing only)
AUTH_ENABLED=false

# Custom rate limit
MAX_REQUESTS_PER_MINUTE=200
```

See [AUTHENTICATION.md](AUTHENTICATION.md) for complete authentication guide.

______________________________________________________________________

### Hot-Reload API Keys

API keys can be reloaded without restarting the container. This is useful for key rotation, adding new keys, or revoking
compromised keys in production.

**Two reload methods:**

| Method        | How                                                                          | When to Use                   |
| ------------- | ---------------------------------------------------------------------------- | ----------------------------- |
| SIGHUP signal | `docker kill -s HUP <container>`                                             | Automation, scripted rotation |
| POST /reload  | `curl -X POST -H "Authorization: Bearer <key>" http://localhost:8000/reload` | Ad-hoc reload, health checks  |

**SIGHUP example:**

```bash
# From the host machine
docker kill -s HUP $(docker ps -q --filter ancestor=ghcr.io/zepfu/llama-gguf-inference)

# Or by container name
docker kill -s HUP my-inference-container
```

**POST /reload example:**

```bash
# Requires a valid API key (when AUTH_ENABLED=true)
curl -X POST \
  -H "Authorization: Bearer sk-prod-abc123def456" \
  http://localhost:8000/reload

# Response:
# {"status": "ok", "keys_loaded": 3}
```

**Behavior:**

- Keys are replaced atomically -- either all keys update or none do
- Rate limiter state (request timestamps) is preserved across reloads
- If the keys file is missing or unreadable, the validator loads 0 keys (fail-closed: all requests rejected)
- The `AUTH_KEYS_FILE` environment variable is re-read on each reload, so you can point to a new file at runtime
- The gateway never crashes on reload failure; it logs the error and continues serving with the previous key set

**Key rotation workflow:**

```bash
# 1. Add new key to the file
echo "new-client:sk-new-$(openssl rand -hex 32)" >> /data/api_keys.txt

# 2. Reload keys
docker kill -s HUP my-inference-container

# 3. Verify new key count in logs
docker logs my-inference-container 2>&1 | tail -5
# ... "API keys reloaded via SIGHUP: 4 key(s) loaded"

# 4. Update clients to use new key

# 5. Remove old key from file and reload again
sed -i '/old-client/d' /data/api_keys.txt
docker kill -s HUP my-inference-container
```

______________________________________________________________________

### CORS Configuration

| Variable       | Default | Description                                        |
| -------------- | ------- | -------------------------------------------------- |
| `CORS_ORIGINS` | `""`    | Comma-separated allowed origins (empty = disabled) |

When set, the gateway injects CORS headers into all responses and handles `OPTIONS` preflight requests automatically
(204 No Content, no auth required).

**Examples:**

```bash
# Disabled (default)
CORS_ORIGINS=""

# Allow a single origin
CORS_ORIGINS=https://my-app.example.com

# Allow multiple origins
CORS_ORIGINS=https://app.example.com,https://staging.example.com

# Allow all origins (wildcard)
CORS_ORIGINS=*
```

**Injected headers:**

```
Access-Control-Allow-Origin: <origin or *>
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 86400
```

______________________________________________________________________

### Request Timeouts

| Variable                  | Default | Description                                  |
| ------------------------- | ------- | -------------------------------------------- |
| `REQUEST_TIMEOUT`         | `300`   | Total request timeout in seconds (5 minutes) |
| `BACKEND_CONNECT_TIMEOUT` | `10`    | Backend TCP connect timeout in seconds       |
| `CLIENT_HEADER_TIMEOUT`   | `30`    | Client header/body read timeout in seconds   |

The gateway enforces three separate timeouts:

- **`REQUEST_TIMEOUT`** -- Covers the entire backend interaction after the TCP connection is established: sending the
  request, reading response headers, and streaming the response body. If this timeout is exceeded, the gateway returns
  `504 Gateway Timeout` in OpenAI error format. Set this high enough for your longest inference requests (large
  generation tasks can take several minutes).
- **`BACKEND_CONNECT_TIMEOUT`** -- Covers only the initial TCP connection to the llama-server backend. If the backend is
  unreachable or slow to accept connections, the gateway returns `502 Bad Gateway`.
- **`CLIENT_HEADER_TIMEOUT`** -- Covers reading the HTTP request line, headers, and body from the client. Protects
  against slowloris-style attacks.

**Examples:**

```bash
# Defaults (suitable for most deployments)
REQUEST_TIMEOUT=300
BACKEND_CONNECT_TIMEOUT=10
CLIENT_HEADER_TIMEOUT=30

# Long inference tasks (e.g., large context generation)
REQUEST_TIMEOUT=600

# Faster failure on backend issues
BACKEND_CONNECT_TIMEOUT=5

# Stricter client timeouts
CLIENT_HEADER_TIMEOUT=15
```

______________________________________________________________________

### Concurrency Control

| Variable                  | Default | Description                                        |
| ------------------------- | ------- | -------------------------------------------------- |
| `MAX_CONCURRENT_REQUESTS` | `1`     | Max simultaneous requests forwarded to the backend |
| `MAX_QUEUE_SIZE`          | `0`     | Max requests waiting in queue (0 = unlimited)      |

The gateway queues incoming API requests and forwards them to the llama-server backend with bounded concurrency. Health
endpoints (`/ping`, `/health`, `/metrics`) bypass the queue entirely.

When the queue is full, the gateway returns `503 Service Unavailable` with a `Retry-After: 5` header.

**Examples:**

```bash
# Default: single request at a time, unlimited queue
MAX_CONCURRENT_REQUESTS=1
MAX_QUEUE_SIZE=0

# Allow 4 concurrent requests, queue up to 20
MAX_CONCURRENT_REQUESTS=4
MAX_QUEUE_SIZE=20

# High throughput with bounded queue
MAX_CONCURRENT_REQUESTS=8
MAX_QUEUE_SIZE=50
```

The `/health` endpoint includes a `queue` section showing current state:

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

The `/metrics` endpoint includes `queue_depth`, `queue_rejections`, and `queue_wait_seconds_total`.

______________________________________________________________________

### Security Limits

| Variable                | Default           | Description                                   |
| ----------------------- | ----------------- | --------------------------------------------- |
| `MAX_REQUEST_BODY_SIZE` | `10485760` (10MB) | Maximum request body size in bytes            |
| `MAX_HEADERS`           | `64`              | Maximum number of request headers             |
| `MAX_HEADER_LINE_SIZE`  | `8192` (8KB)      | Maximum size of a single header line in bytes |

The gateway enforces request size limits to prevent memory exhaustion and header flooding attacks. Requests exceeding
these limits receive an error response before any body data is read.

- **413 Payload Too Large** — returned when `Content-Length` exceeds `MAX_REQUEST_BODY_SIZE`
- **431 Request Header Fields Too Large** — returned when header count exceeds `MAX_HEADERS` or a single header line
  exceeds `MAX_HEADER_LINE_SIZE`

Health endpoints (`/ping`, `/health`, `/metrics`) are subject to header limits but not body size limits (they have no
request body).

**Examples:**

```bash
# Defaults (suitable for most deployments)
MAX_REQUEST_BODY_SIZE=10485760
MAX_HEADERS=64
MAX_HEADER_LINE_SIZE=8192

# Increase body limit for large prompts
MAX_REQUEST_BODY_SIZE=52428800  # 50MB

# Stricter header limits
MAX_HEADERS=32
MAX_HEADER_LINE_SIZE=4096
```

______________________________________________________________________

### Data Directory

| Variable   | Default | Description                        |
| ---------- | ------- | ---------------------------------- |
| `DATA_DIR` | `/data` | Base directory for models and logs |

**Auto-detection:** If `DATA_DIR` is not set and `/data` doesn't exist, the container checks for:

1. `/runpod-volume` (RunPod Serverless)
1. `/workspace` (RunPod Pods, Vast.ai)

**Platform examples:**

```bash
# Local Docker
DATA_DIR=/data
# Mount: -v /path/to/data:/data

# RunPod Serverless (auto-detected)
# Uses /runpod-volume automatically

# Custom path
DATA_DIR=/mnt/storage
```

______________________________________________________________________

### Model Configuration

| Variable     | Required | Default            | Description                      |
| ------------ | -------- | ------------------ | -------------------------------- |
| `MODEL_NAME` | Yes\*    | —                  | Model filename in MODELS_DIR     |
| `MODEL_PATH` | Yes\*    | —                  | Full absolute path to model file |
| `MODELS_DIR` | No       | `$DATA_DIR/models` | Directory containing models      |

\*One of `MODEL_NAME` or `MODEL_PATH` is required.

**Examples:**

```bash
# Using MODEL_NAME (recommended)
MODEL_NAME=Llama-3-8B-Instruct-Q4_K_M.gguf
# Resolves to: $DATA_DIR/models/Llama-3-8B-Instruct-Q4_K_M.gguf

# Using MODEL_PATH (full control)
MODEL_PATH=/custom/path/to/my-model.gguf

# Custom models directory
MODELS_DIR=/mnt/fast-storage/models
MODEL_NAME=model.gguf
```

______________________________________________________________________

### Server Configuration

| Variable       | Default   | Description                                    |
| -------------- | --------- | ---------------------------------------------- |
| `PORT`         | `8000`    | Public gateway port                            |
| `PORT_HEALTH`  | `8001`    | Health check port (for platform monitoring)    |
| `PORT_BACKEND` | `8080`    | Internal llama-server port                     |
| `BACKEND_PORT` | `8080`    | ⚠️ **Deprecated** - Use `PORT_BACKEND` instead |
| `HOST`         | `0.0.0.0` | Bind address                                   |

**Port architecture:**

```
Client → Health Server:8001 (platform checks, no auth)
Client → Gateway:8000 (API, with auth) → llama-server:8080
              ↓
         /ping (health, no auth)
         /health (status, no auth)
         /v1/* (API, requires auth)
```

**Port naming change:**

- **New naming:** `PORT_BACKEND` (consistent with `PORT` and `PORT_HEALTH`)
- **Old naming:** `BACKEND_PORT` is deprecated but still works with warning
- Old name will be removed in future major version

**Examples:**

```bash
# Standard configuration (recommended)
PORT=8000
PORT_HEALTH=8001
PORT_BACKEND=8080

# Custom ports
PORT=9000
PORT_HEALTH=9001
PORT_BACKEND=9080

# Using old name (shows deprecation warning)
BACKEND_PORT=8080  # Works but deprecated - use PORT_BACKEND instead
```

______________________________________________________________________

### Inference Configuration

| Variable     | Default | Description                        |
| ------------ | ------- | ---------------------------------- |
| `NGL`        | `99`    | Number of layers to offload to GPU |
| `CTX`        | `16384` | Context length (max tokens)        |
| `THREADS`    | `0`     | CPU threads (0 = auto-detect)      |
| `EXTRA_ARGS` | —       | Additional llama-server arguments  |

**GPU Offload (NGL):**

- `99` — Offload all layers that fit (recommended)
- `0` — CPU only (for testing or no GPU)
- `20-50` — Partial offload (large models on smaller GPUs)

**Context Length (CTX):** Higher context = more memory usage. Common values:

- `4096` — Basic chat
- `8192` — Longer conversations
- `16384` — Extended context (default)
- `32768` — Very long documents

**Extra Arguments:**

```bash
# Example: verbose logging and temperature
EXTRA_ARGS="--verbose --temp 0.7"
```

______________________________________________________________________

### Logging Configuration

| Variable      | Default          | Description                                                  |
| ------------- | ---------------- | ------------------------------------------------------------ |
| `LOG_FORMAT`  | `text`           | Log output format: `text` (plain) or `json` (JSONL)          |
| `LOG_NAME`    | `llama`          | Subdirectory name for logs (deprecated if using WORKER_TYPE) |
| `WORKER_TYPE` | `""`             | Worker classification for log organization                   |
| `LOG_DIR`     | `$DATA_DIR/logs` | Base log directory                                           |

**Structured JSON Logging:**

Set `LOG_FORMAT=json` to enable structured JSON log output (JSONL format). Each log line is a single JSON object written
to stderr, making it easy to ingest into log aggregation systems (Datadog, ELK, Grafana Loki, etc.).

```bash
# Enable JSON logging
LOG_FORMAT=json
```

When enabled, gateway stderr output looks like:

```json
{"ts":"2026-02-13T09:15:00.123456+00:00","level":"info","msg":"Gateway starting","port":8000}
{"ts":"2026-02-13T09:15:01.456789+00:00","level":"info","msg":"Request completed","method":"POST","path":"/v1/chat/completions","status":200,"duration_ms":142.3,"key_id":"production","bytes_sent":1024}
```

Access logs (written to `/data/logs/api_access.log`) also switch to JSONL when `LOG_FORMAT=json`:

```json
{"ts":"2026-02-13T09:15:01.456789+00:00","key_id":"production","method":"POST","path":"/v1/chat/completions","status":200}
```

When `LOG_FORMAT=text` (default), all logging remains unchanged from previous behavior.

**Worker Type Organization:**

Use `WORKER_TYPE` to organize logs by worker purpose:

```bash
# Default (no worker type)
WORKER_TYPE=""
# Logs go to: $DATA_DIR/logs/llama/

# Instruct model worker
WORKER_TYPE=instruct
# Logs go to: $DATA_DIR/logs/llama-instruct/

# Coding model worker
WORKER_TYPE=coder
# Logs go to: $DATA_DIR/logs/llama-coder/

# Omni-modal worker
WORKER_TYPE=omni
# Logs go to: $DATA_DIR/logs/llama-omni/
```

**Log filename format** (timestamp-first for chronological sorting):

```
20240206_143022_server_instanceid.log  # Most recent
20240206_120000_server_instanceid.log
20240205_180000_server_instanceid.log  # Oldest
```

**Log structure:**

```
$DATA_DIR/logs/
├── _boot/                          # Boot/startup logs
│   ├── 20240206_143022_boot_hostname.log
│   └── latest.txt
└── llama-{WORKER_TYPE}/            # Runtime logs (or just llama/ if no type)
    ├── 20240206_143022_server_hostname.log
    └── latest.txt
```

**Multiple deployments:** Use `WORKER_TYPE` to separate logs:

```bash
# Deployment 1: Instruct endpoint
WORKER_TYPE=instruct
MODEL_NAME=llama3-instruct.gguf

# Deployment 2: Coder endpoint
WORKER_TYPE=coder
MODEL_NAME=codellama.gguf

# Deployment 3: Omni endpoint
WORKER_TYPE=omni
MODEL_NAME=omni-model.gguf

# Results in separate log directories:
# /data/logs/llama-instruct/
# /data/logs/llama-coder/
# /data/logs/llama-omni/
```

______________________________________________________________________

### Debug Configuration

| Variable      | Default | Description                              |
| ------------- | ------- | ---------------------------------------- |
| `DEBUG_SHELL` | `false` | Hold container without starting services |

When enabled, container prints environment and waits 5 minutes for inspection.

______________________________________________________________________

## Recommended Configurations

### RTX 4090 (24GB)

**7B-13B Models:**

```bash
MODEL_NAME=Llama-3-8B-Q4_K_M.gguf
NGL=99
CTX=16384
AUTH_ENABLED=true
```

**30B Models:**

```bash
MODEL_NAME=Qwen-30B-Q4_K_M.gguf
NGL=99
CTX=16384
AUTH_ENABLED=true
```

**70B Models:**

```bash
MODEL_NAME=Llama-3-70B-Q4_K_M.gguf
NGL=35       # Partial offload
CTX=8192     # Reduced context
AUTH_ENABLED=true
```

______________________________________________________________________

### A100 (40GB)

**70B Models:**

```bash
MODEL_NAME=Llama-3-70B-Q4_K_M.gguf
NGL=99
CTX=16384
AUTH_ENABLED=true
```

______________________________________________________________________

### A100 (80GB) / H100

**70B Models (high quality):**

```bash
MODEL_NAME=Llama-3-70B-Q8_0.gguf
NGL=99
CTX=32768
AUTH_ENABLED=true
```

______________________________________________________________________

### CPU Only

```bash
MODEL_NAME=Llama-3-8B-Q4_K_M.gguf
NGL=0
CTX=4096
THREADS=8
AUTH_ENABLED=true
```

______________________________________________________________________

### Multi-Worker Deployment

**Instruct Worker:**

```bash
MODEL_NAME=llama3-instruct.gguf
WORKER_TYPE=instruct
PORT=8000
AUTH_ENABLED=true
AUTH_KEYS_FILE=/data/api_keys.txt
```

**Coder Worker:**

```bash
MODEL_NAME=codellama.gguf
WORKER_TYPE=coder
PORT=8100
AUTH_ENABLED=true
AUTH_KEYS_FILE=/data/api_keys.txt
```

**Omni Worker:**

```bash
MODEL_NAME=omni-model.gguf
WORKER_TYPE=omni
PORT=8200
AUTH_ENABLED=true
AUTH_KEYS_FILE=/data/api_keys.txt
```

______________________________________________________________________

## Memory Estimation

Rough VRAM requirements for Q4 models:

| Component | Estimate               |
| --------- | ---------------------- |
| 7B model  | ~4 GB                  |
| 13B model | ~8 GB                  |
| 30B model | ~17 GB                 |
| 70B model | ~40 GB                 |
| KV cache  | ~0.5 GB per 8K context |
| Compute   | ~0.5 GB                |

______________________________________________________________________

## Environment Variable Precedence

1. Explicit environment variables (highest)
1. Dockerfile ENV defaults
1. Script defaults (lowest)

______________________________________________________________________

## Validation

The container validates at startup:

1. **Model exists** — File present and readable
1. **Binary exists** — llama-server found
1. **Libraries load** — Shared libraries resolved
1. **GPU status** — Reports GPU info (doesn't fail if missing)
1. **Auth configuration** — Validates API keys file if auth enabled

Errors are logged to console and boot log.

______________________________________________________________________

## Complete Example Configurations

### Local Development

```bash
# Minimal setup for local testing
AUTH_ENABLED=false
MODEL_NAME=test-model.gguf
DATA_DIR=/tmp/llama-test
NGL=0
CTX=4096
```

### Production (RunPod Serverless)

```bash
# Secure production setup
AUTH_ENABLED=true
AUTH_KEYS_FILE=/runpod-volume/api_keys.txt
MAX_REQUESTS_PER_MINUTE=100
MODEL_NAME=production-model.gguf
WORKER_TYPE=production
NGL=99
CTX=16384
PORT=8000
PORT_HEALTH=8001
PORT_BACKEND=8080
```

### Multi-Model Platform

```bash
# Endpoint 1: Instruct
AUTH_ENABLED=true
AUTH_KEYS_FILE=/data/api_keys.txt
MODEL_NAME=llama3-instruct.gguf
WORKER_TYPE=instruct
PORT=8000

# Endpoint 2: Code
AUTH_ENABLED=true
AUTH_KEYS_FILE=/data/api_keys.txt
MODEL_NAME=codellama.gguf
WORKER_TYPE=coder
PORT=8100

# Endpoint 3: Omni
AUTH_ENABLED=true
AUTH_KEYS_FILE=/data/api_keys.txt
MODEL_NAME=omni-model.gguf
WORKER_TYPE=omni
PORT=8200
```

______________________________________________________________________

## Security Best Practices

### API Keys

1. **Use strong keys:**

   ```bash
   # Generate with the key management CLI (recommended):
   python3 scripts/key_mgmt.py generate --name production

   # Or generate manually:
   openssl rand -hex 32
   ```

1. **Secure file permissions:**

   ```bash
   chmod 600 /data/api_keys.txt
   ```

1. **Mount read-only:**

   ```bash
   -v /data/api_keys.txt:/data/api_keys.txt:ro
   ```

1. **Rotate regularly:**

   - Add new key
   - Update clients
   - Remove old key after grace period

### Network Security

1. **Use health port for platform checks:**

   ```bash
   PORT_HEALTH=8001  # Separate from API traffic
   ```

1. **Reverse proxy for production:**

   - Put gateway behind nginx/traefik
   - Add TLS termination
   - Add additional rate limiting

1. **Firewall rules:**

   - Allow 8000 for API (authenticated)
   - Allow 8001 for health checks (platform only)
   - Block 8080 (internal llama-server)

______________________________________________________________________

## Troubleshooting Configuration

### Check Current Configuration

```bash
# Enable debug mode
DEBUG_SHELL=true

# Container will print all environment variables
# Wait 5 minutes for inspection
```

### Common Issues

**Auth not working:**

- Check `AUTH_ENABLED=true`
- Verify `AUTH_KEYS_FILE` path is correct
- Check file format: `key_id:api_key`
- Verify file is mounted and readable

**Logs not organized:**

- Set `WORKER_TYPE` environment variable
- Check logs directory: `ls -la $DATA_DIR/logs/`

**Port conflicts:**

- Ensure `PORT`, `PORT_HEALTH`, `PORT_BACKEND` are not in use
- Check with: `netstat -tlnp | grep 8000`

**Deprecation warnings:**

- Replace `BACKEND_PORT` with `PORT_BACKEND`
- Update deployment scripts

______________________________________________________________________

## See Also

- [CONFIGURATION.md](docs/CONFIGURATION.md) - Complete authentication guide
- [TESTING.md](TESTING.md) - Testing procedures
- [DEBUGGING.md](../DEBUGGING.md) - Troubleshooting guide
- [SCALE_TO_ZERO.md](../SCALE_TO_ZERO.md) - Serverless configuration
