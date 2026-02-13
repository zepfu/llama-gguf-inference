# Deployment Guide

Platform-specific deployment instructions for llama-gguf-inference.

Each section is self-contained. Jump to the platform you are deploying on:

- [RunPod Serverless](#runpod-serverless) (primary target)
- [RunPod Pods](#runpod-pods)
- [Vast.ai](#vastai)
- [Lambda Labs](#lambda-labs)
- [Local Docker / docker-compose](#local-docker--docker-compose)

______________________________________________________________________

## RunPod Serverless

RunPod Serverless is the primary deployment target. Workers scale to zero when idle, and you pay only for active
inference time.

### Prerequisites

- A RunPod account with GPU credits
- A RunPod Network Volume with your GGUF model file uploaded
- An API keys file uploaded to the network volume (if using authentication)

### Quick Start

1. **Create a Network Volume** in the RunPod dashboard and upload your model:

   ```
   /runpod-volume/
   ├── models/
   │   └── your-model.gguf
   └── api_keys.txt
   ```

1. **Create a Serverless Endpoint** with the following settings:

   - **Container Image:** `ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1`
   - **Container Disk:** 10 GB (enough for the runtime; model is on the volume)
   - **Volume:** Attach your Network Volume (mounts at `/runpod-volume`)
   - **GPU:** Select GPU matching your model size (see [Memory Estimation](#memory-estimation))
   - **Active Workers:** 0 (enables scale-to-zero)
   - **Idle Timeout:** 5 seconds (how long to keep a warm worker)
   - **Exposed Ports:** `8000` (API gateway), `8001` (health checks)
   - **Health Check Port:** `8001`

1. **Set environment variables** in the endpoint configuration:

   | Variable                  | Value                         | Required |
   | ------------------------- | ----------------------------- | -------- |
   | `MODEL_NAME`              | `your-model.gguf`             | Yes      |
   | `AUTH_ENABLED`            | `true`                        | No       |
   | `AUTH_KEYS_FILE`          | `/runpod-volume/api_keys.txt` | No       |
   | `PORT_HEALTH`             | `8001`                        | No       |
   | `NGL`                     | `99`                          | No       |
   | `CTX`                     | `16384`                       | No       |
   | `MAX_REQUESTS_PER_MINUTE` | `100`                         | No       |
   | `MAX_CONCURRENT_REQUESTS` | `1`                           | No       |

### Scale-to-Zero Behavior

The container exposes two ports to support scale-to-zero:

- **Port 8001** (health server) — A minimal HTTP server that responds to platform health checks without touching the
  llama-server backend. RunPod uses this to determine if the worker is alive.
- **Port 8000** (gateway) — The API gateway that handles authenticated requests, CORS, and request queuing.

Configure RunPod to health-check on port 8001. This ensures that health probes do not keep the worker active when there
are no real API requests.

### API Key Setup

Upload your API keys file to the network volume before starting the endpoint:

```bash
# Generate a key
python3 scripts/key_mgmt.py generate --name production --file api_keys.txt

# Upload to volume (via RunPod file browser or SSH)
# Place at: /runpod-volume/api_keys.txt
```

### Testing

**With `curl`:**

```bash
# Health check (no auth required)
curl https://your-endpoint-id-runpod.io/health

# Chat completion
curl https://your-endpoint-id-runpod.io/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "any",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

**With the OpenAI Python SDK:**

```python
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_API_KEY",
    base_url="https://your-endpoint-id-runpod.io/v1"
)

response = client.chat.completions.create(
    model="any",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

### Health Check Verification

```bash
# Should return 200 with status JSON when model is loaded
curl -s https://your-endpoint-id-runpod.io/health | python3 -m json.tool

# Quick ping (returns 200 with empty body when ready, 204 when initializing)
curl -s -o /dev/null -w "%{http_code}" https://your-endpoint-id-runpod.io/ping
```

### Common Issues

- **Worker stuck in "Initializing":** Large models take time to load. Check the boot log at
  `/runpod-volume/logs/_boot/latest.txt`. Increase the startup timeout in RunPod settings if needed.
- **HuggingFace validation stuck:** This is a RunPod/HF platform issue. Use a placeholder value in the HF repo field or
  wait for HF to recover.
- **Model not found:** Ensure the model file is in `/runpod-volume/models/` and the `MODEL_NAME` matches exactly
  (case-sensitive).

______________________________________________________________________

## RunPod Pods

RunPod Pods are persistent GPU instances. Unlike Serverless, Pods stay running and you pay for the full uptime.

### Prerequisites

- A RunPod account with GPU credits
- A Pod with a GPU matching your model size

### Quick Start

1. **Create a Pod** in the RunPod dashboard:

   - **Container Image:** `ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1`
   - **GPU:** Select based on your model size
   - **Volume:** Allocate disk for models (or attach a Network Volume)
   - **Exposed Ports:** `8000` (gateway), `8001` (health)

1. **Upload your model** to the pod volume:

   ```
   /workspace/
   ├── models/
   │   └── your-model.gguf
   └── api_keys.txt
   ```

1. **Set environment variables:**

   | Variable                  | Value                     | Required |
   | ------------------------- | ------------------------- | -------- |
   | `MODEL_NAME`              | `your-model.gguf`         | Yes      |
   | `AUTH_ENABLED`            | `true`                    | No       |
   | `AUTH_KEYS_FILE`          | `/workspace/api_keys.txt` | No       |
   | `NGL`                     | `99`                      | No       |
   | `CTX`                     | `16384`                   | No       |
   | `MAX_REQUESTS_PER_MINUTE` | `100`                     | No       |

The container auto-detects `/workspace` and uses it as the data directory.

### Health Check Verification

```bash
curl -s http://YOUR_POD_IP:8000/health | python3 -m json.tool
```

### Common Issues

- **Volume not mounted:** Ensure the pod has a volume attached. Check that `/workspace` exists and contains your model.
- **Port not exposed:** Verify both ports 8000 and 8001 are listed in the pod's exposed ports.

______________________________________________________________________

## Vast.ai

Vast.ai provides competitive GPU pricing with Docker-based deployments.

### Prerequisites

- A Vast.ai account with credits
- A GPU instance matching your model size

### Quick Start

1. **Create an instance** on Vast.ai:

   - **Docker Image:** `ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1`
   - **GPU:** Select based on your model size
   - **Disk:** Allocate enough for your model file
   - **Exposed Ports:** `8000`, `8001`

1. **Pull the image** (if not automatic):

   ```bash
   docker pull ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1
   ```

1. **Upload your model** to the instance volume:

   ```
   /workspace/
   ├── models/
   │   └── your-model.gguf
   └── api_keys.txt
   ```

1. **Set environment variables** in the instance configuration:

   | Variable                  | Value                     | Required |
   | ------------------------- | ------------------------- | -------- |
   | `MODEL_NAME`              | `your-model.gguf`         | Yes      |
   | `AUTH_ENABLED`            | `true`                    | No       |
   | `AUTH_KEYS_FILE`          | `/workspace/api_keys.txt` | No       |
   | `NGL`                     | `99`                      | No       |
   | `CTX`                     | `16384`                   | No       |
   | `MAX_REQUESTS_PER_MINUTE` | `100`                     | No       |

The container auto-detects `/workspace` and uses it as the data directory.

### Health Check Verification

```bash
# Replace YOUR_INSTANCE_IP and mapped port
curl -s http://YOUR_INSTANCE_IP:8000/health | python3 -m json.tool
```

### Common Issues

- **Volume not mounted:** Ensure the instance has disk allocated. Check that `/workspace` exists.
- **Port mapping:** Vast.ai maps container ports to random host ports. Use the Vast.ai dashboard to find the mapped port
  numbers for 8000 and 8001.
- **Model not found:** Upload the model to `/workspace/models/` and verify the filename matches `MODEL_NAME` exactly.

______________________________________________________________________

## Lambda Labs

Lambda Labs provides on-demand GPU cloud instances with Docker support.

### Prerequisites

- A Lambda Labs account
- An instance with a GPU (A10, A100, H100, etc.)
- Docker installed on the instance (pre-installed on Lambda Cloud instances)

### Quick Start

1. **Launch a Lambda instance** with Docker pre-installed.

1. **Pull the image:**

   ```bash
   docker pull ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1
   ```

1. **Prepare your data directory:**

   ```bash
   mkdir -p /data/models
   # Copy or download your model
   cp your-model.gguf /data/models/

   # Create API keys file (optional)
   python3 scripts/key_mgmt.py generate --name production --file /data/api_keys.txt
   ```

1. **Run the container:**

   ```bash
   docker run --gpus all \
     -v /data:/data \
     -e MODEL_NAME=your-model.gguf \
     -e AUTH_ENABLED=true \
     -e AUTH_KEYS_FILE=/data/api_keys.txt \
     -p 8000:8000 \
     -p 8001:8001 \
     ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1
   ```

   | Variable                  | Value                | Required |
   | ------------------------- | -------------------- | -------- |
   | `MODEL_NAME`              | `your-model.gguf`    | Yes      |
   | `AUTH_ENABLED`            | `true`               | No       |
   | `AUTH_KEYS_FILE`          | `/data/api_keys.txt` | No       |
   | `NGL`                     | `99`                 | No       |
   | `CTX`                     | `16384`              | No       |
   | `DATA_DIR`                | `/data`              | No       |
   | `MAX_REQUESTS_PER_MINUTE` | `100`                | No       |

GPU detection works automatically on Lambda instances — no additional configuration needed.

### Health Check Verification

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

### Common Issues

- **Docker GPU access:** Ensure `nvidia-container-toolkit` is installed. Lambda Cloud instances have this pre-installed.
  Verify with `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`.
- **Firewall:** Lambda instances may require you to open ports 8000 and 8001 in the firewall or security group settings.

______________________________________________________________________

## Local Docker / docker-compose

Run llama-gguf-inference on your local machine or any Docker host.

### Prerequisites

- Docker installed ([Install Docker](https://docs.docker.com/get-docker/))
- For GPU: NVIDIA GPU with drivers installed and
  [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- A GGUF model file

### Quick Start (GPU)

```bash
# Pull the image
docker pull ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1

# Prepare data directory
mkdir -p ./data/models
cp your-model.gguf ./data/models/

# Create API keys file
cat > ./data/api_keys.txt << EOF
production:sk-prod-$(openssl rand -hex 32)
EOF
chmod 600 ./data/api_keys.txt

# Run with GPU
docker run --gpus all \
  -v $(pwd)/data:/data \
  -e MODEL_NAME=your-model.gguf \
  -e AUTH_ENABLED=true \
  -p 8000:8000 \
  -p 8001:8001 \
  ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1
```

### Quick Start (CPU)

```bash
# Pull the CPU image
docker pull ghcr.io/zepfu/llama-gguf-inference:cpu-1.0.0-rc.1

# Run without GPU
docker run \
  -v $(pwd)/data:/data \
  -e MODEL_NAME=your-model.gguf \
  -e AUTH_ENABLED=false \
  -e NGL=0 \
  -e CTX=4096 \
  -p 8000:8000 \
  -p 8001:8001 \
  ghcr.io/zepfu/llama-gguf-inference:cpu-1.0.0-rc.1
```

### Using docker-compose

A `docker-compose.yml` is included in the repository with GPU and CPU service definitions:

```bash
# GPU service
docker compose up inference-gpu

# CPU service
docker compose up inference-cpu
```

Before starting, update the `docker-compose.yml` environment variables:

```yaml
environment:
  - MODEL_NAME=your-model.gguf    # Set to your model filename
  - AUTH_ENABLED=true
  - AUTH_KEYS_FILE=/data/api_keys.txt
```

Place your model and keys file in the `./data/` directory:

```
./data/
├── models/
│   └── your-model.gguf
└── api_keys.txt
```

### Environment Variables

| Variable                  | Default                  | Description                                     |
| ------------------------- | ------------------------ | ----------------------------------------------- |
| `MODEL_NAME`              | —                        | Model filename in `DATA_DIR/models/` (required) |
| `AUTH_ENABLED`            | `true`                   | Enable API key authentication                   |
| `AUTH_KEYS_FILE`          | `$DATA_DIR/api_keys.txt` | Path to API keys file                           |
| `NGL`                     | `99`                     | GPU layers (99 = all, 0 = CPU only)             |
| `CTX`                     | `16384`                  | Context length                                  |
| `DATA_DIR`                | `/data`                  | Base directory for models and logs              |
| `PORT`                    | `8000`                   | Gateway port                                    |
| `PORT_HEALTH`             | `8001`                   | Health check port                               |
| `PORT_BACKEND`            | `8080`                   | Internal llama-server port                      |
| `MAX_CONCURRENT_REQUESTS` | `1`                      | Max simultaneous backend requests               |
| `MAX_QUEUE_SIZE`          | `0`                      | Max queued requests (0 = unlimited)             |
| `MAX_REQUESTS_PER_MINUTE` | `100`                    | Rate limit per API key                          |
| `CORS_ORIGINS`            | `""`                     | Comma-separated allowed CORS origins            |
| `WORKER_TYPE`             | `""`                     | Worker classification for log organization      |
| `THREADS`                 | `0`                      | CPU threads (0 = auto-detect)                   |
| `EXTRA_ARGS`              | —                        | Additional llama-server arguments               |
| `DEBUG_SHELL`             | `false`                  | Hold container for debugging                    |

For the complete reference, see [CONFIGURATION.md](CONFIGURATION.md).

### GPU Passthrough

For NVIDIA GPUs, use the `--gpus` flag:

```bash
# All GPUs
docker run --gpus all ...

# Specific GPU
docker run --gpus '"device=0"' ...
```

Verify GPU access inside the container:

```bash
docker run --gpus all ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1 nvidia-smi
```

If `nvidia-smi` is not found, install
[nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

### Volume Mounts

Mount your data directory into the container at `/data`:

```bash
-v /path/to/your/data:/data
```

Directory structure inside the volume:

```
/data/
├── models/           # Place your .gguf files here
│   └── model.gguf
├── api_keys.txt      # API keys (if AUTH_ENABLED=true)
└── logs/             # Created automatically at runtime
    ├── _boot/
    └── llama/
```

For read-only API keys (recommended for production):

```bash
-v /path/to/api_keys.txt:/data/api_keys.txt:ro
```

### Testing

```bash
# Health check
curl http://localhost:8000/ping

# Detailed health status
curl -s http://localhost:8000/health | python3 -m json.tool

# Chat completion (with auth)
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "any",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# Chat completion (auth disabled)
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "any",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# List models
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8000/v1/models

# Streaming
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "any",
    "stream": true,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Health Check Verification

```bash
# Quick ping (200 = ready, 204 = initializing)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ping

# Full status
curl -s http://localhost:8000/health | python3 -m json.tool

# Metrics
curl -s http://localhost:8000/metrics | python3 -m json.tool
```

### Common Issues

- **GPU not detected:** Ensure `--gpus all` is passed and nvidia-container-toolkit is installed. Test with
  `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`.
- **Model not found:** Check that the model file is in `./data/models/` and `MODEL_NAME` matches exactly
  (case-sensitive). Run `ls -la ./data/models/` to verify.
- **Permission denied:** Ensure the data directory is readable. Run `chmod -R 755 ./data/` if needed.
- **Port already in use:** Change the host port mapping: `-p 9000:8000` instead of `-p 8000:8000`.
- **Out of memory:** Reduce `NGL` for partial GPU offload or reduce `CTX`. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
  for memory estimation tables.

______________________________________________________________________

## Memory Estimation

Use this table to select the right GPU for your model. Values are approximate for Q4 quantized models:

| Model Size | VRAM (full offload) | Recommended GPU          |
| ---------- | ------------------- | ------------------------ |
| 7B         | ~4-5 GB             | RTX 3060+, T4, any cloud |
| 13B        | ~8-9 GB             | RTX 3080+, T4, L4        |
| 30B        | ~18-20 GB           | RTX 4090, A10, L40       |
| 70B        | ~40+ GB             | A100 40GB+, H100         |

Additional VRAM overhead: ~0.5 GB per 8K context length, plus ~0.5 GB for compute buffers.

______________________________________________________________________

## See Also

- [CONFIGURATION.md](CONFIGURATION.md) — Full environment variable reference
- [AUTHENTICATION.md](AUTHENTICATION.md) — Authentication setup and key management
- [MIGRATION.md](MIGRATION.md) — Upgrade guide and breaking changes
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Diagnosing common issues
