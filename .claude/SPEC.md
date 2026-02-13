# SPEC.md — Technical Specification

## Architecture Overview

Three-tier containerized inference server:

```
┌─────────────────────────────────────────┐
│  Health Server (PORT_HEALTH, default 8001)│
│  - Platform health checks (RunPod, etc.) │
│  - Returns 200 OK on any GET             │
│  - No backend interaction                │
│  - Enables scale-to-zero                 │
│  - Python stdlib HTTPServer              │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Gateway (PORT, default 8000)            │
│  - Async HTTP proxy (asyncio streams)    │
│  - API key authentication + rate limiting│
│  - SSE/streaming pass-through            │
│  - /ping, /health, /metrics (no auth)    │
│  - Routes to llama-server backend        │
│  - Per-key access logging                │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  llama-server (PORT_BACKEND, default 8080)│
│  - llama.cpp inference engine            │
│  - OpenAI-compatible API                 │
│  - GPU offloading (NGL layers)           │
│  - Protected by backend API key          │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Storage Layer (DATA_DIR, default /data)  │
│  - /data/models/        GGUF model files │
│  - /data/logs/          Runtime logs     │
│  - /data/api_keys.txt   Auth keys (r/o)  │
└─────────────────────────────────────────┘
```

All three services are orchestrated by `scripts/start.sh` which handles boot diagnostics, model resolution, key
generation, process supervision, and graceful shutdown.

## Tech Stack

| Layer            | Technology                                     | Notes                                                     |
| ---------------- | ---------------------------------------------- | --------------------------------------------------------- |
| Core Gateway     | Python 3.11 (stdlib only)                      | `asyncio` streams, no pip dependencies                    |
| Auth Module      | Python 3.11 (stdlib only)                      | File-based key validation, sliding window rate limiting   |
| Health Server    | Python 3.11 (stdlib only)                      | `http.server.HTTPServer`, minimal footprint               |
| Inference Engine | llama.cpp (`llama-server`)                     | Pre-built in base Docker image                            |
| Orchestration    | Bash (`start.sh`)                              | Boot diagnostics, process management, signal handling     |
| Container        | Docker                                         | Base: `ghcr.io/ggml-org/llama.cpp:server-cuda`            |
| CI/CD            | GitHub Actions                                 | 3 workflows: `ci.yml`, `cd.yml`, `docs.yml`               |
| Registry         | GHCR                                           | `ghcr.io/zepfu/llama-gguf-inference`                      |
| Documentation    | Sphinx + ReadTheDocs                           | Auto-generated changelog, repo map, architecture diagrams |
| Code Quality     | black, isort, flake8, mypy, bandit, shellcheck | Enforced via pre-commit hooks                             |
| Testing          | Bash test scripts + pytest                     | Auth, health, integration, Docker integration             |

______________________________________________________________________

## Core Concepts

### Inference Pipeline

The critical path from request to response:

1. Client sends OpenAI-compatible request to gateway (port 8000)
1. Gateway authenticates via API key (if `AUTH_ENABLED=true`)
1. Gateway proxies request to llama-server (port 8080) with backend key
1. llama-server runs inference on GPU and returns response
1. Gateway streams response back (SSE for streaming, JSON for non-streaming)

- **Invariant:** Gateway adds zero business logic — it is a transparent auth proxy.
- **Invariant:** Health endpoints (`/ping`, `/health`, `/metrics`) never touch the backend.

### Platform Detection

Automatic detection of deployment environment:

- `/runpod-volume` exists → RunPod Serverless (DATA_DIR defaults to `/runpod-volume`)

- `/workspace` exists → RunPod Pods / Vast.ai (DATA_DIR defaults to `/workspace`)

- Otherwise → Local Docker or custom (DATA_DIR defaults to `/data`)

- **Rule:** Platform detection only affects `DATA_DIR` default. All other behavior is identical.

- **Rule:** User can always override with explicit `DATA_DIR` environment variable.

### Authentication

File-based API key system:

- Keys stored in `key_id:api_key` format in a text file

- Loaded into memory at startup (no database)

- Bearer token format: `Authorization: Bearer <api_key>`

- Per-key-id sliding window rate limiting

- Backend protected by auto-generated key (defense-in-depth)

- **Invariant:** When `AUTH_ENABLED=false`, all auth checks are skipped entirely.

- **Invariant:** Health endpoints are always exempt from authentication.

______________________________________________________________________

## Data Model

This project has no traditional database. State is minimal and ephemeral:

### API Key Entry (in-memory)

```
key_id          string      Identifier for logging/rate-limiting
api_key         string      Secret key for authentication
request_count   int         Sliding window counter
window_start    float       Timestamp of current rate limit window
```

### Metrics (in-memory)

```
total_requests      int         Total requests received
active_requests     int         Currently in-flight requests
requests_by_path    dict        Count per endpoint path
errors_by_type      dict        Count per error category
```

### Model Configuration (from environment)

```
MODEL_NAME          string      GGUF filename in MODELS_DIR
MODEL_PATH          string      Full path (overrides MODEL_NAME)
NGL                 int         GPU layers to offload (default: 99)
CTX                 int         Context length (default: 16384)
```

______________________________________________________________________

## API Design

OpenAI-compatible REST API. No custom envelope — responses match OpenAI's format exactly to ensure client SDK
compatibility.

Auth: Bearer token via `Authorization` header. Versioning: `/v1/` prefix (matching OpenAI convention).

### Endpoint Groups

```
# Health & Monitoring (no auth required)
GET  /ping                          Quick health check → 200 OK
GET  /health                        Detailed status JSON (backend reachable, model loaded)
GET  /metrics                       Request statistics JSON

# Inference (auth required when AUTH_ENABLED=true)
POST /v1/chat/completions           Chat completions (OpenAI format, supports streaming)
POST /v1/completions                Text completions (OpenAI format)
GET  /v1/models                     List available models
```

### Streaming Contract

When `"stream": true` in request body:

- Response is `Content-Type: text/event-stream`
- Each chunk: `data: {JSON}\n\n`
- Final chunk: `data: [DONE]\n\n`
- Gateway passes through SSE chunks from llama-server without modification

______________________________________________________________________

## Project Structure

```
llama-gguf-inference/
├── CLAUDE.md                       # Project coordinator instructions
├── TASKS.md                        # Operator task injection
├── PROJECT_LOG.md                  # Build activity log
├── CLAUDE_SUGGESTIONS.md           # Suggestion inbox
├── .claude/                        # AI coordination reference files
│   ├── SPEC.md                     # This file — architecture & API
│   ├── GUIDELINES.md               # Dev conventions & standards
│   ├── PHASES.md                   # Build phases & execution plan
│   ├── CONTRACTS.md                # Cross-agent interface contracts
│   └── GITHUB_INTEGRATION.md       # GitHub sync rules
├── agent-logs/                     # Per-agent work logs
│   ├── _TEMPLATE.md
│   └── archive/
├── logs/                           # Archived logs
│   └── REJECTED_SUGGESTIONS.md
├── scripts/                        # Core application code
│   ├── start.sh                    # Main entrypoint (797 lines)
│   ├── gateway.py                  # Async HTTP gateway (485 lines)
│   ├── auth.py                     # API key auth module (366 lines)
│   ├── health_server.py            # Health check server (51 lines)
│   ├── README.md                   # Script documentation
│   ├── dev/                        # Development utilities
│   │   ├── setup.sh                # One-command dev setup
│   │   ├── check_repo_map.sh
│   │   ├── check_changelog.sh
│   │   ├── generate_api_docs.sh
│   │   └── check_env_completeness.sh
│   ├── tests/                      # Test suites
│   │   ├── test_runner.sh          # Master orchestrator
│   │   ├── test_auth.sh
│   │   ├── test_health.sh
│   │   ├── test_integration.sh
│   │   └── test_docker_integration.sh
│   └── diagnostics/                # Troubleshooting tools
│       ├── collect.sh
│       └── README.md
├── docs/                           # User & auto-generated documentation
│   ├── AUTHENTICATION.md
│   ├── CONFIGURATION.md
│   ├── TESTING.md
│   ├── TROUBLESHOOTING.md
│   ├── auto/                       # Auto-generated
│   │   ├── CHANGELOG.md
│   │   ├── REPO_MAP.md
│   │   └── ARCHITECTURE_AUTO.md
│   ├── diagrams/                   # Mermaid architecture diagrams
│   ├── conf.py                     # Sphinx config
│   └── index.rst                   # Sphinx entry
├── Dockerfile                      # Container definition
├── Makefile                        # Build targets
├── pyproject.toml                  # Python tooling config
├── .pre-commit-config.yaml         # Pre-commit hooks
├── .github/workflows/              # CI/CD pipelines
│   ├── ci.yml                      # Tests, linting, validation
│   ├── cd.yml                      # Docker build → GHCR
│   └── docs.yml                    # Documentation generation
├── README.md                       # User-facing documentation
├── CONTRIBUTING.md                 # Developer guide
├── DEBUGGING.md                    # Debugging procedures
├── CHANGELOG.md                    # Release changelog
└── .env.example                    # Environment variables template
```
