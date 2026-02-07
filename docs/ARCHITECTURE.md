# Architecture

System architecture and design documentation for llama-gguf-inference.

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Request Flow](#request-flow)
- [Port Configuration](#port-configuration)
- [Authentication Flow](#authentication-flow)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Deployment Patterns](#deployment-patterns)
- [Performance Considerations](#performance-considerations)
- [Security](#security)

## Overview

llama-gguf-inference is a production-ready inference server for GGUF models using llama.cpp. It provides:

- **OpenAI-compatible API** - Drop-in replacement for OpenAI endpoints
- **Authentication** - API key-based access control
- **Health monitoring** - Separate health check port for platform integration
- **Streaming support** - Real-time token streaming via SSE
- **Platform agnostic** - Runs on any GPU cloud or local machine

## System Architecture

```mermaid
graph TD
    Client[Client/User] -->|HTTP| HealthServer[Health Server :8001]
    Client -->|HTTP + Auth| Gateway[Gateway :8000]
    Gateway -->|Proxy| LlamaServer[llama-server :8080]
    LlamaServer -->|Load| Model[GGUF Model]
    LlamaServer -->|Offload| GPU[GPU/VRAM]

    Gateway -->|Read| APIKeys[API Keys File]
    Gateway -->|Write| AccessLog[Access Logs]
    LlamaServer -->|Write| ServerLog[Server Logs]

    HealthServer -.->|No interaction| LlamaServer

    style HealthServer fill:#90EE90
    style Gateway fill:#87CEEB
    style LlamaServer fill:#FFB6C1
    style Model fill:#DDA0DD
```

### Components

1. **Health Server** (port 8001)
   - Minimal HTTP server for platform health checks
   - No authentication required
   - No backend interaction
   - Enables scale-to-zero in serverless

2. **Gateway** (port 8000)
   - Python async HTTP gateway
   - API key authentication
   - Request proxying to llama-server
   - SSE streaming support
   - Public-facing interface

3. **llama-server** (port 8080)
   - Official llama.cpp HTTP server
   - Model inference engine
   - OpenAI-compatible API
   - Internal-only access

4. **Data Storage**
   - Models: `/data/models/*.gguf`
   - Logs: `/data/logs/`
   - API keys: `/data/api_keys.txt`

## Request Flow

### Standard API Request

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Auth
    participant Llama
    participant GPU

    Client->>Gateway: POST /v1/chat/completions
    Note over Client,Gateway: Authorization: Bearer sk-key

    Gateway->>Auth: Validate API key
    Auth-->>Gateway: Valid (key_id)

    Gateway->>Gateway: Check rate limit
    Gateway->>Llama: Proxy request

    Llama->>GPU: Offload inference
    GPU-->>Llama: Tokens

    Llama-->>Gateway: Stream tokens (SSE)
    Gateway-->>Client: Stream tokens (SSE)

    Gateway->>Gateway: Log access (key_id)
```

### Health Check Request

```mermaid
sequenceDiagram
    participant Platform
    participant HealthServer
    participant Gateway

    Note over Platform,HealthServer: Platform health checks

    Platform->>HealthServer: GET / (port 8001)
    HealthServer-->>Platform: 200 OK

    Note over HealthServer: No auth, no backend check

    Note over Platform,Gateway: User health checks

    Platform->>Gateway: GET /ping (port 8000)
    Gateway-->>Platform: 200 OK

    Note over Gateway: No auth required
```

## Port Configuration

```mermaid
graph LR
    subgraph Public
        P8001[":8001 Health"]
        P8000[":8000 Gateway"]
    end

    subgraph Internal
        P8080[":8080 llama-server"]
    end

    P8001 -.->|No connection| P8080
    P8000 -->|Proxies to| P8080

    style P8001 fill:#90EE90
    style P8000 fill:#87CEEB
    style P8080 fill:#FFB6C1
```

### Port Purposes

| Port | Service | Public | Auth | Purpose |
|------|---------|--------|------|---------|
| 8001 | Health Server | ✅ | ❌ | Platform health checks (scale-to-zero) |
| 8000 | Gateway | ✅ | ✅* | API endpoints |
| 8080 | llama-server | ❌ | N/A | Internal inference engine |

*Auth required for `/v1/*` endpoints, not for `/ping`, `/health`, `/metrics`

## Authentication Flow

```mermaid
flowchart TD
    Start[Incoming Request] --> CheckPath{Path?}

    CheckPath -->|/ping, /health, /metrics| NoAuth[Allow without auth]
    CheckPath -->|/v1/*| NeedAuth[Requires auth]

    NeedAuth --> HasHeader{Has Authorization header?}
    HasHeader -->|No| Return401A[Return 401]
    HasHeader -->|Yes| ExtractKey[Extract API key]

    ExtractKey --> ValidKey{Key valid?}
    ValidKey -->|No| Return401B[Return 401]
    ValidKey -->|Yes| CheckRate{Under rate limit?}

    CheckRate -->|No| Return429[Return 429]
    CheckRate -->|Yes| ProxyRequest[Proxy to backend]

    ProxyRequest --> LogAccess[Log access with key_id]
    LogAccess --> ReturnResponse[Return response]

    NoAuth --> ReturnResponse
```

### API Key Format

```
File: /data/api_keys.txt
Format: key_id:api_key

Example:
production:sk-prod-abc123def456
alice-laptop:sk-alice-xyz789
```

## Component Details

### Gateway (scripts/gateway.py)

**Responsibilities:**
- API key validation
- Rate limiting (per key_id)
- Request proxying
- SSE streaming
- Access logging

**Technology:**
- Python 3.11+
- asyncio (async HTTP)
- No external dependencies (stdlib only)

**Key Features:**
- Handles streaming correctly (SSE)
- Non-blocking I/O
- Graceful shutdown (SIGTERM)
- Health endpoints exempt from auth

### Auth Module (scripts/auth.py)

**Responsibilities:**
- Load API keys from file
- Validate incoming keys
- Rate limit enforcement
- Access logging

**Data Structures:**
```python
# In-memory storage
keys = {
    "sk-prod-abc123": "production",  # api_key -> key_id
    "sk-alice-xyz789": "alice-laptop"
}

rate_limiter = {
    "production": [timestamp1, timestamp2, ...],  # key_id -> timestamps
    "alice-laptop": [timestamp3, ...]
}
```

### Health Server (scripts/health_server.py)

**Responsibilities:**
- Respond to platform health checks
- Minimal overhead
- No backend interaction

**Why Separate Port?**
- Platform health checks don't count as "activity"
- Enables proper scale-to-zero
- Avoids false positive "active" state

### llama-server (Binary)

**From:** llama.cpp project (ghcr.io/ggml-org/llama.cpp:server-cuda)

**Responsibilities:**
- Load GGUF model
- GPU offloading (NGL layers)
- Token generation
- OpenAI-compatible API

**Configuration:**
```bash
/app/llama-server \
  -m /data/models/model.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  -c 16384 \
  -ngl 99
```

## Data Flow

### Model Loading

```mermaid
graph TD
    Start[Container Start] --> CheckModel{Model file exists?}
    CheckModel -->|No| Error[FATAL: Exit]
    CheckModel -->|Yes| StartLlama[Start llama-server]

    StartLlama --> LoadModel[Load GGUF model]
    LoadModel --> CheckGPU{GPU available?}

    CheckGPU -->|Yes| OffloadGPU[Offload NGL layers to GPU]
    CheckGPU -->|No| UseCPU[Use CPU only]

    OffloadGPU --> AllocKV[Allocate KV cache]
    UseCPU --> AllocKV

    AllocKV --> Ready[Server Ready]
    Ready --> StartGateway[Start Gateway]
    StartGateway --> StartHealth[Start Health Server]
    StartHealth --> Running[System Running]
```

### Request Processing

```mermaid
graph LR
    Request[HTTP Request] --> Gateway

    Gateway --> Auth{Needs auth?}
    Auth -->|No| Proxy[Proxy to llama-server]
    Auth -->|Yes| Validate[Validate & Rate Limit]

    Validate -->|Fail| Reject[Return 401/429]
    Validate -->|Pass| Proxy

    Proxy --> Llama[llama-server]
    Llama --> Inference[Model Inference]
    Inference --> GPUCPU[GPU/CPU]

    GPUCPU --> Tokens[Generate Tokens]
    Tokens --> Stream{Streaming?}

    Stream -->|Yes| SSE[SSE Events]
    Stream -->|No| JSON[Complete JSON]

    SSE --> Client
    JSON --> Client
```

### Logging

```mermaid
graph TD
    Boot[Container Boot] -->|Logs to| BootLog[/data/logs/_boot/YYYYMMDD_HHMMSS_boot_host.log]

    LlamaServer[llama-server] -->|Logs to| ServerLog[/data/logs/llama-TYPE/YYYYMMDD_HHMMSS_server_host.log]

    Gateway[Gateway Auth] -->|Logs to| AccessLog[/data/logs/api_access.log]

    BootLog -.->|Symlink| BootLatest[/data/logs/_boot/latest.txt]
    ServerLog -.->|Symlink| ServerLatest[/data/logs/llama-TYPE/latest.txt]

    style BootLog fill:#FFE4B5
    style ServerLog fill:#FFE4B5
    style AccessLog fill:#FFE4B5
```

**Log Organization:**
```
/data/logs/
├── _boot/
│   ├── 20240207_143022_boot_hostname.log    # Most recent
│   ├── 20240206_120000_boot_hostname.log
│   └── latest.txt -> 20240207_143022_boot_hostname.log
└── llama-{WORKER_TYPE}/
    ├── 20240207_143022_server_hostname.log  # Most recent
    ├── 20240206_120000_server_hostname.log
    └── latest.txt -> 20240207_143022_server_hostname.log
```

## Deployment Patterns

### Serverless (RunPod)

```mermaid
graph TD
    Request[HTTP Request] -->|Port 8001| HealthCheck[Platform Health Check]
    Request -->|Port 8000| API[API Request]

    HealthCheck -->|200 OK| NoScale[Don't count as activity]
    API -->|Processing| ResetIdle[Reset idle timer]

    NoActivity[No API requests] -->|Idle timeout| ScaleToZero[Scale to 0]
    ResetIdle -.->|Activity detected| NoScaleToZero[Stay active]
```

### Traditional Deployment

```mermaid
graph LR
    LoadBalancer[Load Balancer] -->|Route| Instance1[Instance 1]
    LoadBalancer -->|Route| Instance2[Instance 2]
    LoadBalancer -->|Route| Instance3[Instance 3]

    Instance1 --> Model1[Model in VRAM]
    Instance2 --> Model2[Model in VRAM]
    Instance3 --> Model3[Model in VRAM]
```

## Performance Considerations

### Memory Usage

```
Total VRAM = Model Size + KV Cache + Compute Buffer

Example (7B Q4 model, 16K context):
- Model: ~4 GB
- KV Cache: ~512 MB (per 8K context)
- Compute: ~500 MB
- Total: ~5 GB
```

### Throughput

**Factors:**
- GPU memory bandwidth
- Context length
- Batch size (handled by llama-server)
- Model quantization level

**Typical Performance (RTX 4090):**
- 7B Q4: ~100 tokens/sec
- 13B Q4: ~50 tokens/sec
- 30B Q4: ~25 tokens/sec

### Latency

**Time to first token:**
- Prompt processing: ~100-500ms (depends on prompt length)
- Network overhead: ~10-50ms
- Authentication: ~1ms

**Token generation:**
- 7B: ~10ms/token
- 13B: ~20ms/token
- 30B: ~40ms/token

## Security

### Threat Model

**Protected Against:**
- ✅ Unauthorized API access (API keys)
- ✅ Rate limit abuse (per-key limits)
- ✅ Credential leakage (keys in separate file)
- ✅ Platform coupling (health port separation)

**Not Protected Against:**
- ❌ DDoS (use external rate limiting/WAF)
- ❌ Prompt injection (application-level concern)
- ❌ Model extraction (inherent to API access)

### Best Practices

1. **API Keys:**
   - Generate with `openssl rand -hex 32`
   - Store in `chmod 600` file
   - Rotate regularly

2. **Network:**
   - Use reverse proxy (nginx/traefik)
   - Add TLS termination
   - Additional rate limiting at edge

3. **Monitoring:**
   - Check `/data/logs/api_access.log`
   - Monitor rate limit metrics
   - Alert on unusual patterns

---

*This document is auto-generated. For updates, modify the source and regenerate.*
