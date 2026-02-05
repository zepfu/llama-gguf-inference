# llama-gguf-inference

Run **GGUF models** with llama.cpp on any GPU cloud or local machine.

## Quick Start

1. **Set your model:**
   ```bash
   MODEL_NAME=your-model.gguf
   ```

2. **Run the container:**
   ```bash
   docker run --gpus all \
     -v /path/to/models:/data/models \
     -e MODEL_NAME=your-model.gguf \
     -p 8000:8000 \
     ghcr.io/<owner>/llama-gguf-inference
   ```

3. **Send requests:**
   ```bash
   curl http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "any",
       "messages": [{"role": "user", "content": "Hello!"}]
     }'
   ```

## Features

- **Platform agnostic** — Works on RunPod, Vast.ai, Lambda Labs, or local Docker
- **Simple configuration** — Only `MODEL_NAME` is required
- **OpenAI-compatible API** — Drop-in replacement for `/v1/chat/completions`
- **Streaming support** — Real-time token streaming via SSE
- **Auto GPU offload** — Automatically uses available VRAM
- **Health checks** — Built-in `/ping` and `/health` endpoints

## Supported Platforms

| Platform | DATA_DIR | Notes |
|----------|----------|-------|
| Local Docker | `/data` (default) | Mount your models directory |
| RunPod Serverless | `/runpod-volume` | Auto-detected |
| RunPod Pods | `/workspace` | Auto-detected |
| Vast.ai | `/workspace` | Auto-detected |
| Lambda Labs | `/data` or custom | Set `DATA_DIR` |
| Any Docker host | Custom | Set `DATA_DIR=/your/path` |

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `MODEL_NAME` | Model filename in `DATA_DIR/models/` | `Llama-3-8B-Q4_K_M.gguf` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | — | Full path to model (alternative to MODEL_NAME) |
| `DATA_DIR` | `/data` | Base directory for models and logs |
| `MODELS_DIR` | `$DATA_DIR/models` | Override models directory |
| `NGL` | `99` | GPU layers to offload (99 = all, 0 = CPU only) |
| `CTX` | `16384` | Context length |
| `PORT` | `8000` | Public gateway port |
| `BACKEND_PORT` | `8080` | Internal llama-server port |
| `LOG_NAME` | `llama` | Log folder name |
| `THREADS` | `0` | CPU threads (0 = auto) |
| `EXTRA_ARGS` | — | Additional llama-server arguments |
| `DEBUG_SHELL` | `false` | Hold container for debugging |

## Directory Structure

```
$DATA_DIR/
├── models/           # Place your .gguf files here
│   └── model.gguf
└── logs/
    ├── _boot/        # Container startup logs
    └── llama/        # Server runtime logs
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /ping` | Health check (200=ready, 204=loading) |
| `GET /health` | Detailed health status (JSON) |
| `GET /metrics` | Basic metrics (JSON) |
| `POST /v1/chat/completions` | Chat completions (OpenAI format) |
| `POST /v1/completions` | Text completions |
| `GET /v1/models` | List models |

## Platform-Specific Setup

### Local Docker

```bash
# Create data directory
mkdir -p ./data/models
cp your-model.gguf ./data/models/

# Run
docker run --gpus all \
  -v $(pwd)/data:/data \
  -e MODEL_NAME=your-model.gguf \
  -p 8000:8000 \
  ghcr.io/<owner>/llama-gguf-inference
```

### RunPod Serverless

Environment variables:
```
MODEL_NAME=your-model.gguf
```

The container auto-detects `/runpod-volume` and uses it for models and logs.

### RunPod Pods / Vast.ai

Environment variables:
```
MODEL_NAME=your-model.gguf
```

Auto-detects `/workspace`.

### Custom Setup

```bash
DATA_DIR=/mnt/storage
MODEL_NAME=your-model.gguf
# Models expected at: /mnt/storage/models/your-model.gguf
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Gateway (port 8000)                 │
│  - Health checks (/ping, /health)               │
│  - Streaming support                             │
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
└─────────────────────────────────────────────────┘
```

## GPU Memory Guide

Rough VRAM requirements for Q4 quantized models:

| Model Size | VRAM (full offload) | Good For |
|------------|---------------------|----------|
| 7B | ~4-5 GB | RTX 3060+, any cloud GPU |
| 13B | ~8-9 GB | RTX 3080+, T4, L4 |
| 30B | ~18-20 GB | RTX 4090, A10, L40 |
| 70B | ~40+ GB | A100 40GB+, H100 |

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

### Debug mode
```bash
DEBUG_SHELL=true
# Container will pause and print environment
```

See [docs/troubleshooting.md](docs/troubleshooting.md) for more.

## Development

```bash
# Build locally
docker build -t llama-gguf-inference .

# Test locally
docker run --gpus all \
  -v /path/to/models:/data/models \
  -e MODEL_NAME=test-model.gguf \
  -p 8000:8000 \
  llama-gguf-inference
```

## License

MIT
