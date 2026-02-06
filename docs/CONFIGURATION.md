# Configuration Guide

Complete reference for all configuration options.

## Environment Variables

### Authentication Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_ENABLED` | `true` | Enable/disable API key authentication |
| `AUTH_KEYS_FILE` | `$DATA_DIR/api_keys.txt` | Path to API keys file |
| `MAX_REQUESTS_PER_MINUTE` | `100` | Rate limit per API key |

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

---

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

---

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

---

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Public gateway port |
| `PORT_HEALTH` | `8001` | Health check port (for platform monitoring) |
| `PORT_BACKEND` | `8080` | Internal llama-server port |
| `BACKEND_PORT` | `8080` | ⚠️ **Deprecated** - Use `PORT_BACKEND` instead |
| `HOST` | `0.0.0.0` | Bind address |

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

---

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

---

### Logging Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_NAME` | `llama` | Subdirectory name for logs (deprecated if using WORKER_TYPE) |
| `WORKER_TYPE` | `""` | Worker classification for log organization |
| `LOG_DIR` | `$DATA_DIR/logs` | Base log directory |

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

**Multiple deployments:**
Use `WORKER_TYPE` to separate logs:
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

---

### Debug Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG_SHELL` | `false` | Hold container without starting services |

When enabled, container prints environment and waits 5 minutes for inspection.

---

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

---

### A100 (40GB)

**70B Models:**
```bash
MODEL_NAME=Llama-3-70B-Q4_K_M.gguf
NGL=99
CTX=16384
AUTH_ENABLED=true
```

---

### A100 (80GB) / H100

**70B Models (high quality):**
```bash
MODEL_NAME=Llama-3-70B-Q8_0.gguf
NGL=99
CTX=32768
AUTH_ENABLED=true
```

---

### CPU Only

```bash
MODEL_NAME=Llama-3-8B-Q4_K_M.gguf
NGL=0
CTX=4096
THREADS=8
AUTH_ENABLED=true
```

---

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

---

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

---

## Environment Variable Precedence

1. Explicit environment variables (highest)
2. Dockerfile ENV defaults
3. Script defaults (lowest)

---

## Validation

The container validates at startup:

1. **Model exists** — File present and readable
2. **Binary exists** — llama-server found
3. **Libraries load** — Shared libraries resolved
4. **GPU status** — Reports GPU info (doesn't fail if missing)
5. **Auth configuration** — Validates API keys file if auth enabled

Errors are logged to console and boot log.

---

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

---

## Security Best Practices

### API Keys

1. **Use strong keys:**
   ```bash
   # Generate with:
   openssl rand -hex 32
   ```

2. **Secure file permissions:**
   ```bash
   chmod 600 /data/api_keys.txt
   ```

3. **Mount read-only:**
   ```bash
   -v /data/api_keys.txt:/data/api_keys.txt:ro
   ```

4. **Rotate regularly:**
   - Add new key
   - Update clients
   - Remove old key after grace period

### Network Security

1. **Use health port for platform checks:**
   ```bash
   PORT_HEALTH=8001  # Separate from API traffic
   ```

2. **Reverse proxy for production:**
   - Put gateway behind nginx/traefik
   - Add TLS termination
   - Add additional rate limiting

3. **Firewall rules:**
   - Allow 8000 for API (authenticated)
   - Allow 8001 for health checks (platform only)
   - Block 8080 (internal llama-server)

---

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

---

## See Also

- [CONFIGURATION.md](docs/CONFIGURATION.md) - Complete authentication guide
- [TESTING.md](TESTING.md) - Testing procedures
- [DEBUGGING.md](../DEBUGGING.md) - Troubleshooting guide
- [SCALE_TO_ZERO.md](../SCALE_TO_ZERO.md) - Serverless configuration
