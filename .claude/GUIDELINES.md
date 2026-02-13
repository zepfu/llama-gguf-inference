# GUIDELINES.md — Development Conventions & Standards

## API Design Conventions

- All API responses match OpenAI's format exactly — no custom envelope. Client SDK compatibility is the priority.
- Health endpoints (`/ping`, `/health`, `/metrics`) return `200` with no authentication.
- Error responses use standard HTTP status codes with JSON body:
  `{"error": {"message": "...", "type": "...", "code": "..."}}`
- Streaming uses Server-Sent Events: `data: {JSON}\n\n` chunks, terminated by `data: [DONE]\n\n`
- All timestamps ISO 8601 UTC
- Rate limit responses (429) should indicate `MAX_REQUESTS_PER_MINUTE` in the error message

## Security Standards

- **API keys:** Plaintext in `key_id:api_key` format, loaded into memory at startup. File mounted read-only in
  production.
- **Backend key:** Auto-generated random key at each container start (`/tmp/.llama_backend_key`), permissions 600.
  Defense-in-depth — prevents direct backend access.
- **Rate limiting:** Sliding window per `key_id`, configurable via `MAX_REQUESTS_PER_MINUTE` (default: 100).
- **No secrets in code or logs.** Diagnostic output filters sensitive values. Pre-commit hooks detect private keys.
- **All external connections over TLS.** CA certificates included in container.
- **Health endpoints exempt from auth** — required for platform health checks and scale-to-zero.
- **Container runs non-root** (inherited from base image).
- **Input validation:** Validate Content-Type, method, and path before proxying. Reject malformed requests at the
  gateway.

## Coding Standards

### Python Conventions

- **Version:** Python 3.11 (stdlib only — no pip dependencies in container)
- **Formatter:** black (line length 100, target py311)
- **Import sorting:** isort (black-compatible profile)
- **Linter:** flake8
- **Type checker:** mypy (allow missing imports)
- **Security scanner:** bandit (skip B101, B404, B603)
- **Docstrings:** Google convention (format enforced when present, not required on every function)
- **Error handling:** Log errors to stderr with `[component]` prefix (e.g., `[gateway]`, `[auth]`, `[health]`). Never
  swallow exceptions silently.
- **Async:** Use `asyncio` streams for network I/O. No third-party async frameworks.
- **Logging:** Print to stderr with flush. Format: `[component] message`. No structured logging library — keep it
  simple.

### Bash Conventions

- **Linter:** shellcheck (`-x` follow sources, `-S error` severity)
- **Error handling:** `set -euo pipefail` at top of all scripts
- **Functions:** Use `local` for all function variables
- **Logging:** `log()` function with timestamp prefix, output to stderr
- **Signal handling:** Trap SIGTERM/SIGINT for graceful shutdown
- **Platform detection:** Check for directory existence, not environment variables

## Testing Strategy

- **Auth tests** (`test_auth.sh`): API key validation, rate limiting, health endpoint exemption, Bearer token format
- **Health tests** (`test_health.sh`): `/ping` returns 200, `/health` returns valid JSON, `/metrics` returns valid JSON,
  no auth required
- **Integration tests** (`test_integration.sh`): Full request lifecycle, auth → gateway → backend flow, streaming
  responses, error handling
- **Docker tests** (`test_docker_integration.sh`): Container build, startup, env vars, volume mounting, service startup
  order
- **Master orchestrator** (`test_runner.sh`): Runs all suites, tracks pass/fail, reports summary
- **CI validation:** Pre-commit hooks enforce formatting, linting, security scanning, and config validation on every
  commit

### Critical Test Scenarios

1. Health endpoints work without authentication and without backend being up
1. Authenticated request reaches backend and returns valid inference response
1. Invalid/missing API key returns 401 with clear error message
1. Rate limit exceeded returns 429 with appropriate message
1. Streaming (SSE) request passes through correctly with all chunks
1. Container starts and serves requests on all supported platforms (RunPod, Vast.ai, local)
1. Graceful shutdown terminates all child processes without data loss
1. Backend unreachable returns appropriate error (not hang or crash)

## Environment Variables

```env
# Model Configuration (required)
MODEL_NAME=                         # GGUF filename in MODELS_DIR (e.g., model.gguf)
# MODEL_PATH=                       # Full path — overrides MODEL_NAME + MODELS_DIR

# GPU & Inference
NGL=99                              # GPU layers to offload (default: 99 = all)
CTX=16384                           # Context length (default: 16384)
# LLAMA_ARGS=                       # Additional llama-server arguments

# Ports
PORT=8000                           # Gateway port (API)
PORT_HEALTH=8001                    # Health check port (platform monitoring)
PORT_BACKEND=8080                   # llama-server port (internal)

# Authentication
AUTH_ENABLED=true                   # Enable API key authentication
# AUTH_KEYS_FILE=                   # Path to keys file (default: $DATA_DIR/api_keys.txt)
MAX_REQUESTS_PER_MINUTE=100         # Rate limit per key_id

# Storage
# DATA_DIR=                         # Base directory (auto-detected by platform)
# MODELS_DIR=                       # Model directory (default: $DATA_DIR/models)

# Networking
BACKEND_HOST=127.0.0.1              # llama-server host
REQUEST_TIMEOUT=300                 # Max request time in seconds
HEALTH_TIMEOUT=2                    # Health check timeout in seconds

# Debugging
# DEBUG_SHELL=true                  # Pause container for 5 minutes, print full environment
```
