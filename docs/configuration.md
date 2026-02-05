# Configuration Guide

Complete reference for all configuration options.

## Environment Variables

### Data Directory

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `/data` | Base directory for models and logs |

**Auto-detection:** If `DATA_DIR` is not set and `/data` doesn't exist, the container checks for:
1. `/runpod-volume` (RunPod Serverless)
2. `/workspace` (RunPod Pods, Vast.ai)

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

### Model Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MODEL_NAME` | Yes* | — | Model filename in MODELS_DIR |
| `MODEL_PATH` | Yes* | — | Full absolute path to model file |
| `MODELS_DIR` | No | `$DATA_DIR/models` | Directory containing models |

*One of `MODEL_NAME` or `MODEL_PATH` is required.

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

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Public gateway port |
| `BACKEND_PORT` | `8080` | Internal llama-server port |
| `HOST` | `0.0.0.0` | Bind address |

**Port architecture:**
```
Client → Gateway:8000 → llama-server:8080
              ↓
         /ping (health)
         /v1/* (API)
```

### Inference Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NGL` | `99` | Number of layers to offload to GPU |
| `CTX` | `16384` | Context length (max tokens) |
| `THREADS` | `0` | CPU threads (0 = auto-detect) |
| `EXTRA_ARGS` | — | Additional llama-server arguments |

**GPU Offload (NGL):**
- `99` — Offload all layers that fit (recommended)
- `0` — CPU only (for testing or no GPU)
- `20-50` — Partial offload (large models on smaller GPUs)

**Context Length (CTX):**
Higher context = more memory usage. Common values:
- `4096` — Basic chat
- `8192` — Longer conversations
- `16384` — Extended context (default)
- `32768` — Very long documents

**Extra Arguments:**
```bash
# Example: verbose logging and temperature
EXTRA_ARGS="--verbose --temp 0.7"
```

### Logging Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_NAME` | `llama` | Subdirectory name for logs |
| `LOG_DIR` | `$DATA_DIR/logs` | Base log directory |

**Log structure:**
```
$DATA_DIR/logs/
├── _boot/                          # Boot/startup logs
│   ├── boot_<hostname>_<ts>.log
│   └── latest.txt
└── <LOG_NAME>/                     # Runtime logs
    ├── server_<hostname>_<ts>.log
    └── latest.txt
```

**Multiple deployments:**
Use `LOG_NAME` to separate logs:
```bash
# Deployment 1
LOG_NAME=instruct

# Deployment 2
LOG_NAME=coder
```

### Debug Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG_SHELL` | `false` | Hold container without starting services |

When enabled, container prints environment and waits 5 minutes for inspection.

## Recommended Configurations

### RTX 4090 (24GB)

**7B-13B Models:**
```bash
MODEL_NAME=Llama-3-8B-Q4_K_M.gguf
NGL=99
CTX=16384
```

**30B Models:**
```bash
MODEL_NAME=Qwen-30B-Q4_K_M.gguf
NGL=99
CTX=16384
```

**70B Models:**
```bash
MODEL_NAME=Llama-3-70B-Q4_K_M.gguf
NGL=35       # Partial offload
CTX=8192     # Reduced context
```

### A100 (40GB)

**70B Models:**
```bash
MODEL_NAME=Llama-3-70B-Q4_K_M.gguf
NGL=99
CTX=16384
```

### A100 (80GB) / H100

**70B Models (high quality):**
```bash
MODEL_NAME=Llama-3-70B-Q8_0.gguf
NGL=99
CTX=32768
```

### CPU Only

```bash
MODEL_NAME=Llama-3-8B-Q4_K_M.gguf
NGL=0
CTX=4096
THREADS=8
```

## Memory Estimation

Rough VRAM requirements for Q4 models:

| Component | Estimate |
|-----------|----------|
| 7B model | ~4 GB |
| 13B model | ~8 GB |
| 30B model | ~17 GB |
| 70B model | ~40 GB |
| KV cache | ~0.5 GB per 8K context |
| Compute | ~0.5 GB |

## Environment Variable Precedence

1. Explicit environment variables (highest)
2. Dockerfile ENV defaults
3. Script defaults (lowest)

## Validation

The container validates at startup:

1. **Model exists** — File present and readable
2. **Binary exists** — llama-server found
3. **Libraries load** — Shared libraries resolved
4. **GPU status** — Reports GPU info (doesn't fail if missing)

Errors are logged to console and boot log.
