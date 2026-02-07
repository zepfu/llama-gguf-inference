# Scripts Documentation

Complete guide to all scripts in the llama-gguf-inference project.

## Directory Structure

```
scripts/
├── core/              # Runtime scripts (started by container)
│   ├── start.sh       # Main entrypoint
│   ├── gateway.py     # HTTP gateway with auth
│   ├── auth.py        # Authentication module
│   └── health_server.py  # Health check server
├── dev/               # Development utilities
│   ├── setup.sh       # One-command dev setup
│   ├── check_repo_map.sh
│   ├── check_changelog.sh
│   ├── check_env_completeness.sh
│   └── generate_api_docs.sh
├── tests/             # Test scripts
│   ├── test_runner.sh
│   ├── test_auth.sh
│   ├── test_health.sh
│   ├── test_integration.sh
│   └── test_docker_integration.sh
└── diagnostics/       # Diagnostic collection
    ├── collect.sh
    └── README.md
```

---

## Core Runtime Scripts

### start.sh

**Purpose:** Main container entrypoint that orchestrates all services.

**What it does:**
1. Validates environment configuration
2. Resolves model path
3. Starts llama-server
4. Starts health_server.py
5. Starts gateway.py
6. Handles graceful shutdown

**Usage:**
```bash
# Typically run by Docker
ENTRYPOINT ["/opt/app/scripts/start.sh"]

# Or manually for testing
bash scripts/start.sh
```

**Environment Variables:**
- `MODEL_NAME` or `MODEL_PATH` - Required
- `DATA_DIR` - Base directory (default: /data)
- `NGL`, `CTX`, `PORT`, etc. - Configuration

**Logs to:**
- Boot: `/data/logs/_boot/YYYYMMDD_HHMMSS_boot_hostname.log`
- Server: `/data/logs/llama-{TYPE}/YYYYMMDD_HHMMSS_server_hostname.log`

---

### gateway.py

**Purpose:** Async HTTP gateway providing authentication and request proxying.

**What it does:**
- Validates API keys (via auth.py)
- Enforces rate limits per key_id
- Proxies requests to llama-server
- Handles SSE streaming correctly
- Provides health endpoints without auth

**Usage:**
```bash
# Started by start.sh
python3 scripts/gateway.py

# Or directly
GATEWAY_PORT=8000 PORT_BACKEND=8080 python3 scripts/gateway.py
```

**Endpoints:**
- `/ping` - Quick health check (no auth)
- `/health` - Detailed status (no auth)
- `/metrics` - Gateway metrics (no auth)
- `/v1/*` - API endpoints (requires auth)

**Environment Variables:**
- `GATEWAY_PORT` / `PORT` - Gateway port (default: 8000)
- `PORT_BACKEND` - llama-server port (default: 8080)
- `AUTH_ENABLED` - Enable authentication (default: true)
- `AUTH_KEYS_FILE` - API keys file path

---

### auth.py

**Purpose:** API key authentication and rate limiting module.

**What it does:**
- Loads API keys from file (key_id:api_key format)
- Validates Authorization headers
- Tracks request rates per key_id
- Logs authenticated requests

**Usage:**
```python
# Imported by gateway.py
from auth import api_validator, authenticate_request, log_access

# Validate request
key_id = await authenticate_request(writer, headers)
if key_id is None:
    return  # 401 already sent

# Log access
await log_access(method, path, key_id, status_code)
```

**API Keys File:**
```
# /data/api_keys.txt
key_id:api_key

production:sk-prod-abc123def456
development:sk-dev-xyz789abc123
```

**Features:**
- In-memory key storage (no database needed)
- Sliding window rate limiting
- Automatic key reload not supported (restart required)

---

### health_server.py

**Purpose:** Minimal health check server for platform monitoring.

**What it does:**
- Runs on separate port (PORT_HEALTH, default 8001)
- Returns 200 OK for all GET requests
- No authentication
- No backend interaction
- Enables scale-to-zero in serverless

**Usage:**
```bash
# Started by start.sh
PORT_HEALTH=8001 python3 scripts/health_server.py
```

**Why separate port?**
- Platform health checks (RunPod, K8s, etc.) don't count as "activity"
- Allows proper idle detection for scale-to-zero
- Isolates monitoring from API traffic

---

## Development Scripts

### setup.sh

**Purpose:** One-command setup for new developers.

**What it does:**
1. Checks Python version (3.11+ required)
2. Installs pre-commit
3. Installs pre-commit hooks
4. Sets executable permissions on scripts
5. Creates data directories
6. Validates configuration files

**Usage:**
```bash
bash scripts/dev/setup.sh

# Or via Makefile
make setup
```

**Creates:**
- `data/models/` - For GGUF models
- `data/logs/` - For logs
- `scripts/tests/fixtures/` - For test data

---

### check_repo_map.sh

**Purpose:** Pre-commit check that REPO_MAP.md is current.

**What it does:**
1. Downloads repo_map.py from repo-standards
2. Generates temp REPO_MAP.md
3. Compares with current file
4. Fails commit if outdated

**Usage:**
```bash
# Manually
bash scripts/dev/check_repo_map.sh

# Automatically via pre-commit
git commit -m "feat: add feature"
# → Runs automatically
```

**Exit codes:**
- 0 - REPO_MAP.md is current
- 1 - REPO_MAP.md is outdated

**To fix:**
```bash
make map
git add REPO_MAP.md
git commit -m "docs: update repo map"
```

---

### check_changelog.sh

**Purpose:** Heuristic check that CHANGELOG.md is reasonably current.

**What it does:**
1. Gets last 5 non-doc commits
2. Checks if any appear in CHANGELOG.md
3. Warns if none found (non-fatal)

**Usage:**
```bash
# Manually
bash scripts/dev/check_changelog.sh

# Automatically via pre-commit
git commit -m "feat: new feature"
# → Runs automatically
```

**Exit codes:**
- 0 - CHANGELOG.md appears current (or can't determine)
- Never fails (warnings only)

**Note:** Weekly automation will catch missed updates.

---

### check_env_completeness.sh

**Purpose:** Validates environment variable documentation completeness.

**What it checks:**
1. All vars in `start.sh` are documented in `.env.example`
2. All vars in `.env.example` are actually used
3. Critical vars are documented in `docs/CONFIGURATION.md`

**Usage:**
```bash
# Manually
bash scripts/dev/check_env_completeness.sh

# Via Makefile
make check-env
```

**Exit codes:**
- 0 - All checks passed
- 1 - Missing or undocumented variables

**Critical variables checked:**
- MODEL_NAME, MODEL_PATH
- DATA_DIR, PORT, PORT_BACKEND, PORT_HEALTH
- AUTH_ENABLED, AUTH_KEYS_FILE
- NGL, CTX

---

### generate_api_docs.sh

**Purpose:** Generate API documentation from Python docstrings using Sphinx.

**What it does:**
1. Checks if Sphinx is installed
2. Extracts docstrings from Python files
3. Generates HTML documentation
4. Outputs to `docs/api/`

**Usage:**
```bash
bash scripts/dev/generate_api_docs.sh

# Or via Makefile
make api-docs
```

**Requirements:**
- Sphinx installed: `pip install sphinx sphinx-rtd-theme`
- `docs/conf.py` configured

**Output:**
- `docs/api/gateway.html`
- `docs/api/auth.html`
- `docs/api/index.html`

---

## Test Scripts

### test_runner.sh

**Purpose:** Orchestrates all test suites and reports results.

**What it does:**
1. Runs all available test scripts
2. Tracks pass/fail counts
3. Reports summary
4. Exits with appropriate code

**Usage:**
```bash
# Run all tests
bash scripts/tests/test_runner.sh

# Or via Makefile
make test

# Include Docker tests
DOCKER_TEST=true make test
```

**Runs:**
- test_auth.sh
- test_health.sh
- test_integration.sh (if exists)
- test_docker_integration.sh (if DOCKER_TEST=true)

---

### test_auth.sh

**Purpose:** Test API authentication functionality.

**What it tests:**
1. Health endpoints work without auth
2. API endpoints require auth (when enabled)
3. Valid keys are accepted
4. Invalid keys are rejected
5. Both Bearer and direct key formats work

**Usage:**
```bash
bash scripts/tests/test_auth.sh

# With custom URL
GATEWAY_URL=http://localhost:9000 bash scripts/tests/test_auth.sh

# Verbose mode
VERBOSE=true bash scripts/tests/test_auth.sh
```

**Requires:**
- Gateway running
- Test key configured (default: sk-test-12345)

---

### test_health.sh

**Purpose:** Test health endpoint functionality.

**What it tests:**
1. `/ping` returns 200
2. `/health` returns valid JSON
3. `/metrics` returns valid JSON
4. Health server (PORT_HEALTH) is accessible
5. All work without authentication

**Usage:**
```bash
bash scripts/tests/test_health.sh

# With custom URLs
GATEWAY_URL=http://localhost:8000 \
HEALTH_URL=http://localhost:8001 \
bash scripts/tests/test_health.sh
```

---

### test_integration.sh

**Purpose:** Full workflow integration tests.

**What it tests:**
1. Complete request lifecycle
2. Auth → Gateway → Backend flow
3. Streaming responses
4. Error handling
5. Rate limiting

**Usage:**
```bash
bash scripts/tests/test_integration.sh

# Requires running system:
# - llama-server
# - gateway
# - health_server
```

---

### test_docker_integration.sh

**Purpose:** Docker-specific integration tests.

**What it tests:**
1. Docker build succeeds
2. Container starts correctly
3. Environment variables work
4. Volumes mount properly
5. Services start in correct order

**Usage:**
```bash
DOCKER_TEST=true bash scripts/tests/test_docker_integration.sh

# Or via Makefile
make test-docker
```

**Requirements:**
- Docker installed
- Test model available

---

## Diagnostic Scripts

### diagnostics/collect.sh

**Purpose:** Collect system diagnostics for troubleshooting.

**What it collects:**
1. System information (CPU, RAM, GPU)
2. Environment variables (sanitized)
3. Recent logs (last 500 lines)
4. Process information
5. Model information
6. Container information
7. Health check status

**Usage:**
```bash
# Collect to default location
bash scripts/diagnostics/collect.sh

# Custom output directory
bash scripts/diagnostics/collect.sh /tmp/my-diagnostics

# Via Makefile
make diagnostics
```

**Output:**
```
/tmp/llama-diagnostics-YYYYMMDD_HHMMSS/
├── SUMMARY.txt
├── system_info.txt
├── environment.txt
├── processes.txt
├── model_info.txt
├── health_status.txt
└── logs/
    ├── boot_recent.log (last 500 lines)
    └── server_recent.log (last 500 lines)
```

**Compressed:**
```
/tmp/llama-diagnostics-YYYYMMDD_HHMMSS.tar.gz
```

---

## Script Organization Best Practices

### Naming Conventions

- **Runtime scripts:** Simple names (start.sh, gateway.py)
- **Dev utilities:** Descriptive names (check_repo_map.sh)
- **Tests:** Prefix with test_ (test_auth.sh)
- **Tools:** Action-based names (generate_api_docs.sh)

### File Locations

- **Core:** `/opt/app/scripts/*.{sh,py}` (container)
- **Development:** `scripts/dev/`
- **Tests:** `scripts/tests/`
- **Diagnostics:** `scripts/diagnostics/`

### Executable Permissions

All scripts should be executable:
```bash
chmod +x scripts/**/*.sh
chmod +x scripts/**/*.py
```

Or use setup script:
```bash
bash scripts/dev/setup.sh
```

### Shebang Lines

**Bash scripts:**
```bash
#!/usr/bin/env bash
set -euo pipefail
```

**Python scripts:**
```python
#!/usr/bin/env python3
```

---

## Common Patterns

### Error Handling

```bash
# Bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Check command exists
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found"
    exit 1
fi
```

### Logging

```bash
# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}✓ Success${NC}"
echo -e "${RED}✗ Error${NC}"
```

### Environment Variables

```bash
# With defaults
VAR="${VAR:-default_value}"

# Required variables
: "${REQUIRED_VAR:?Error: REQUIRED_VAR not set}"
```

---

## Troubleshooting

### Script Not Found

```bash
# Check permissions
ls -la scripts/start.sh
# Should be: -rwxr-xr-x

# Fix
chmod +x scripts/start.sh
```

### Import Errors (Python)

```bash
# Check PYTHONPATH
echo $PYTHONPATH

# Add scripts directory
export PYTHONPATH="/opt/app/scripts:$PYTHONPATH"
```

### Permission Denied

```bash
# Run setup
bash scripts/dev/setup.sh

# Or manually
chmod +x scripts/**/*.sh
chmod +x scripts/**/*.py
```

---

## Contributing

When adding new scripts:

1. **Choose correct directory:**
   - Runtime → `scripts/` (root)
   - Development → `scripts/dev/`
   - Tests → `scripts/tests/`
   - Diagnostics → `scripts/diagnostics/`

2. **Add documentation here**

3. **Add to Makefile** if appropriate

4. **Add tests** if it's a critical function

5. **Set executable permissions**

6. **Test with `make check`**

---

*For more information, see individual script files which contain detailed inline documentation.*
