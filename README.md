# llama-gguf-inference

[![Code Quality](https://github.com/zepfu/llama-gguf-inference/workflows/Code%20Quality/badge.svg)](https://github.com/zepfu/llama-gguf-inference/actions)
[![GitHub Pages](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://zepfu.github.io/lama-gguf-inference/)
[![Documentation Status](https://readthedocs.org/projects/llama-gguf-inference/badge/?version=latest)](https://llama-gguf-inference.readthedocs.io/en/latest/?badge=latest)

Run **GGUF models** with llama.cpp on any GPU cloud or local machine.

## Quick Start

1. **Set your model:**

   ```bash
   MODEL_NAME=your-model.gguf
   ```

1. **Run the container:**

   ```bash
   # GPU (NVIDIA CUDA — amd64)
   docker run --gpus all \
     -v /path/to/models:/data/models \
     -v /path/to/api_keys.txt:/data/api_keys.txt:ro \
     -e MODEL_NAME=your-model.gguf \
     -e AUTH_ENABLED=true \
     -p 8000:8000 \
     ghcr.io/zepfu/llama-gguf-inference

   # CPU (amd64 + arm64, no GPU required)
   docker run \
     -v /path/to/models:/data/models \
     -e MODEL_NAME=your-model.gguf \
     -e AUTH_ENABLED=false \
     -e NGL=0 \
     -p 8000:8000 \
     ghcr.io/zepfu/llama-gguf-inference:cpu
   ```

   A `docker-compose.yml` is included with GPU and CPU service examples:

   ```bash
   docker compose up inference-gpu   # NVIDIA GPU
   docker compose up inference-cpu   # CPU only
   ```

1. **Send requests:**

   ```bash
   # With authentication (production)
   curl -H "Authorization: Bearer your-api-key" \
     http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "any",
       "messages": [{"role": "user", "content": "Hello!"}]
     }'

   # Without authentication (testing only, if AUTH_ENABLED=false)
   curl http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "any",
       "messages": [{"role": "user", "content": "Hello!"}]
     }'
   ```

## Features

- **Platform agnostic** — Works on RunPod, Vast.ai, Lambda Labs, or local Docker
- **Multi-architecture images** — CUDA (amd64) and CPU (amd64 + arm64) Docker images
- **Simple configuration** — Only `MODEL_NAME` is required
- **OpenAI-compatible API** — Drop-in replacement for `/v1/chat/completions`
- **Streaming support** — Real-time token streaming via SSE
- **Auto GPU offload** — Automatically uses available VRAM
- **Health checks** — Built-in `/ping` and `/health` endpoints
- **API key authentication** — Secure your endpoint with API keys (enabled by default)
- **Key management CLI** — Generate, list, rotate, and remove API keys
- **CORS support** — Configurable cross-origin headers for browser-based clients
- **Concurrency control** — Bounded request queuing with configurable limits
- **Prometheus metrics** — `/metrics` endpoint with JSON and Prometheus text format
- **Request size limits** — Configurable body and header size limits for security
- **Organized logging** — Multi-worker support with chronological log files
- **Code quality enforcement** — Pre-commit hooks and CI/CD

## Supported Platforms

| Platform          | DATA_DIR          | Notes                       |
| ----------------- | ----------------- | --------------------------- |
| Local Docker      | `/data` (default) | Mount your models directory |
| RunPod Serverless | `/runpod-volume`  | Auto-detected               |
| RunPod Pods       | `/workspace`      | Auto-detected               |
| Vast.ai           | `/workspace`      | Auto-detected               |
| Lambda Labs       | `/data` or custom | Set `DATA_DIR`              |
| Any Docker host   | Custom            | Set `DATA_DIR=/your/path`   |

## Authentication

API key authentication is **enabled by default** to secure your inference endpoint.

### Quick Start with Authentication

**Option 1: Disable auth (testing only)**

```bash
AUTH_ENABLED=false docker run ...
```

**Option 2: Use API keys (recommended)**

```bash
# 1. Create keys file
cp api_keys.txt.example /data/api_keys.txt

# 2. Edit and add your keys
nano /data/api_keys.txt
# Format: key_id:api_key
# Example: production:sk-prod-abc123def456

# 3. Secure the file
chmod 600 /data/api_keys.txt

# 4. Run with auth enabled
AUTH_ENABLED=true docker run \
  -v /data/api_keys.txt:/data/api_keys.txt:ro \
  -p 8000:8000 \
  ghcr.io/zepfu/llama-gguf-inference
```

### Making Authenticated Requests

```bash
curl -H "Authorization: Bearer sk-prod-abc123def456" \
  http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "any",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Health Endpoints (No Auth Required)

Health check endpoints work without authentication:

```bash
curl http://localhost:8000/ping    # Always works
curl http://localhost:8000/health  # Always works
```

**For detailed authentication setup, see [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md)**

## Environment Variables

### Required

| Variable     | Description                          | Example                  |
| ------------ | ------------------------------------ | ------------------------ |
| `MODEL_NAME` | Model filename in `DATA_DIR/models/` | `Llama-3-8B-Q4_K_M.gguf` |

### Optional

| Variable                  | Default                  | Description                                         |
| ------------------------- | ------------------------ | --------------------------------------------------- |
| `AUTH_ENABLED`            | `true`                   | Enable/disable API key authentication               |
| `AUTH_KEYS_FILE`          | `$DATA_DIR/api_keys.txt` | Path to API keys file                               |
| `MAX_REQUESTS_PER_MINUTE` | `100`                    | Rate limit per API key                              |
| `CORS_ORIGINS`            | `""`                     | Comma-separated allowed CORS origins (empty = off)  |
| `MAX_CONCURRENT_REQUESTS` | `1`                      | Max simultaneous requests to backend                |
| `MAX_QUEUE_SIZE`          | `0`                      | Max queued requests (0 = unlimited)                 |
| `MAX_REQUEST_BODY_SIZE`   | `10485760`               | Max request body size in bytes (default 10MB)       |
| `MAX_HEADERS`             | `64`                     | Max number of request headers                       |
| `MAX_HEADER_LINE_SIZE`    | `8192`                   | Max size of a single header line in bytes           |
| `MODEL_PATH`              | —                        | Full path to model (alternative to MODEL_NAME)      |
| `DATA_DIR`                | `/data`                  | Base directory for models and logs                  |
| `MODELS_DIR`              | `$DATA_DIR/models`       | Override models directory                           |
| `NGL`                     | `99`                     | GPU layers to offload (99 = all, 0 = CPU only)      |
| `CTX`                     | `16384`                  | Context length                                      |
| `PORT`                    | `8000`                   | Public gateway port                                 |
| `PORT_HEALTH`             | `8001`                   | Health check port (for platform monitoring)         |
| `PORT_BACKEND`            | `8080`                   | Internal llama-server port                          |
| `BACKEND_PORT`            | `8080`                   | Deprecated - Use `PORT_BACKEND` instead             |
| `LOG_NAME`                | `llama`                  | Log folder name                                     |
| `WORKER_TYPE`             | `""`                     | Worker classification (e.g., instruct, coder, omni) |
| `THREADS`                 | `0`                      | CPU threads (0 = auto)                              |
| `EXTRA_ARGS`              | —                        | Additional llama-server arguments                   |
| `DEBUG_SHELL`             | `false`                  | Hold container for debugging                        |

## Directory Structure

```
$DATA_DIR/
├── models/                   # Place your .gguf files here
│   └── model.gguf
├── logs/
│   ├── _boot/                # Container startup logs
│   ├── llama/                # Default server logs
│   ├── llama-instruct/       # Instruct worker logs (if WORKER_TYPE=instruct)
│   ├── llama-coder/          # Coder worker logs (if WORKER_TYPE=coder)
│   └── llama-omni/           # Omni worker logs (if WORKER_TYPE=omni)
└── api_keys.txt              # API keys (optional, for authentication)
```

### Log Organization

Logs are organized by worker type for multi-model deployments:

```bash
# Default worker (no type specified)
WORKER_TYPE=""  
# Logs: /data/logs/llama/

# Instruct model worker
WORKER_TYPE=instruct
# Logs: /data/logs/llama-instruct/

# Coding model worker
WORKER_TYPE=coder
# Logs: /data/logs/llama-coder/

# Omni-modal worker
WORKER_TYPE=omni
# Logs: /data/logs/llama-omni/
```

**Log filename format** (timestamp-first for chronological sorting):

```
20240206_143022_server_instanceid.log  # Most recent
20240206_120000_server_instanceid.log
20240205_180000_server_instanceid.log  # Oldest
```

## API Endpoints

| Endpoint                    | Auth Required | Description                                                          |
| --------------------------- | ------------- | -------------------------------------------------------------------- |
| `GET /ping`                 | No            | Quick health check (always returns 200)                              |
| `GET /health`               | No            | Detailed health status with backend and queue info                   |
| `GET /metrics`              | No            | Gateway metrics (JSON default, Prometheus with `Accept: text/plain`) |
| `OPTIONS *`                 | No            | CORS preflight (when `CORS_ORIGINS` is set)                          |
| `POST /v1/chat/completions` | **Yes**       | Chat completions (OpenAI format)                                     |
| `POST /v1/completions`      | **Yes**       | Text completions                                                     |
| `GET /v1/models`            | **Yes**       | List models                                                          |
| `POST /v1/embeddings`       | **Yes**       | Text embeddings (if model supports it)                               |

**Note:** When `AUTH_ENABLED=true` (default), API endpoints require a valid API key via `Authorization: Bearer <key>`
header. Health endpoints always work without authentication.

**For serverless deployments:** Platform health checks should use `PORT_HEALTH` (default 8001) instead of `/ping` to
enable proper scale-to-zero behavior.

## Platform-Specific Setup

### Local Docker

```bash
# Create data directory
mkdir -p ./data/models
cp your-model.gguf ./data/models/

# Create API keys file
cat > ./data/api_keys.txt << EOF
production:sk-prod-$(openssl rand -hex 32)
EOF
chmod 600 ./data/api_keys.txt

# Run
docker run --gpus all \
  -v $(pwd)/data:/data \
  -e MODEL_NAME=your-model.gguf \
  -e AUTH_ENABLED=true \
  -p 8000:8000 \
  ghcr.io/zepfu/llama-gguf-inference
```

### RunPod Serverless

Environment variables:

```
MODEL_NAME=your-model.gguf
AUTH_ENABLED=true
AUTH_KEYS_FILE=/runpod-volume/api_keys.txt
```

**Upload `api_keys.txt` to your RunPod volume before starting.**

The container auto-detects `/runpod-volume` and uses it for models and logs.

**For scale-to-zero behavior:**

- Set `Active Workers` to 0 in endpoint settings
- Configure `Idle Timeout` (e.g., 5 seconds)
- Expose ports: 8000 (API), 8001 (health checks)
- Set `PORT_HEALTH=8001` environment variable
- Configure RunPod to use port 8001 for health checks

This setup separates platform health checks from your actual API traffic, allowing the worker to properly scale to zero
when idle.

### RunPod Pods / Vast.ai

Environment variables:

```
MODEL_NAME=your-model.gguf
AUTH_ENABLED=true
AUTH_KEYS_FILE=/workspace/api_keys.txt
```

**Upload `api_keys.txt` to your workspace volume.**

Auto-detects `/workspace`.

### Custom Setup

```bash
DATA_DIR=/mnt/storage
MODEL_NAME=your-model.gguf
AUTH_ENABLED=true
AUTH_KEYS_FILE=/mnt/storage/api_keys.txt
# Models expected at: /mnt/storage/models/your-model.gguf
# Keys expected at: /mnt/storage/api_keys.txt
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│       Health Server (port 8001)                 │
│  - Minimal health checks for platform           │
│  - No backend interaction                       │
│  - Enables scale-to-zero                        │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│              Gateway (port 8000)                 │
│  - API key authentication                        │
│  - Health checks (/ping, /health, /metrics)     │
│  - Streaming support                             │
│  - CORS headers                                  │
│  - Concurrency control & request queuing         │
│  - Request routing                               │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│           llama-server (port 8080)              │
│  - Model inference                               │
│  - OpenAI-compatible API                         │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│              $DATA_DIR                           │
│  /models/  - GGUF model files                   │
│  /logs/    - Server logs                        │
│  api_keys.txt - API keys (optional)             │
└─────────────────────────────────────────────────┘
```

## GPU Memory Guide

Rough VRAM requirements for Q4 quantized models:

| Model Size | VRAM (full offload) | Good For                 |
| ---------- | ------------------- | ------------------------ |
| 7B         | ~4-5 GB             | RTX 3060+, any cloud GPU |
| 13B        | ~8-9 GB             | RTX 3080+, T4, L4        |
| 30B        | ~18-20 GB           | RTX 4090, A10, L40       |
| 70B        | ~40+ GB             | A100 40GB+, H100         |

## Troubleshooting

### Model not found

```bash
# Check model path
ls -la $DATA_DIR/models/
# Verify MODEL_NAME matches exactly (case-sensitive)
```

### Out of memory

```bash
# Reduce GPU layers
NGL=40

# Or reduce context
CTX=4096
```

### Authentication Issues

**Problem:** 401 Unauthorized

- Check API key format in `api_keys.txt` (`key_id:api_key`)
- Verify Authorization header: `Authorization: Bearer <key>`
- Check `AUTH_ENABLED=true`
- Verify `api_keys.txt` is mounted and readable

**Problem:** Health endpoints don't work

- Health endpoints (`/ping`, `/health`, `/metrics`) should always work without auth
- If they require auth, there's a configuration issue

**See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) for detailed troubleshooting.**

### Debug mode

```bash
DEBUG_SHELL=true
# Container will pause and print environment
```

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more.

## Development

### Code Quality

This project uses pre-commit hooks for code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### Running Tests

```bash
# Full pytest suite (224 tests)
python3 -m pytest tests/ -v

# Pre-commit hooks
pre-commit run --all-files
```

See [docs/TESTING.md](docs/TESTING.md) for comprehensive testing guide.

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

### Building Locally

```bash
# Build locally
docker build -t llama-gguf-inference .

# Test locally
docker run --gpus all \
  -v /path/to/models:/data/models \
  -e MODEL_NAME=test-model.gguf \
  -e AUTH_ENABLED=false \
  -p 8000:8000 \
  llama-gguf-inference
```

## License

MIT
