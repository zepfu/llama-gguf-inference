#!/usr/bin/env bash
# ==============================================================================
# start.sh — Main entrypoint for llama-gguf-inference
#
# This script:
#   1. Runs boot diagnostics (written to DATA_DIR if available)
#   2. Resolves the model path
#   3. Generates random backend authentication key
#   4. Starts llama-server on PORT_BACKEND (default 8080) with backend auth
#   5. Starts health_server.py on PORT_HEALTH (default 8001) for platform checks
#   6. Starts gateway.py on PORT (default 8000) with API endpoints
#   7. Handles graceful shutdown on SIGTERM/SIGINT
#
# Environment Variables (see docs/configuration.md for details):
#   MODEL_NAME     - (required) Model filename in MODELS_DIR
#   MODEL_PATH     - (alternative) Full path to model file
#   DATA_DIR       - Base directory for models/logs (default: /data)
#   NGL            - GPU layers to offload (default: 99 = all)
#   CTX            - Context length (default: 16384)
#   PORT           - Public port for gateway (default: 8000)
#   PORT_HEALTH    - Health check port for platform (default: 8001)
#   PORT_BACKEND   - Internal llama-server port (default: 8080)
#   WORKER_TYPE    - Optional worker classification (e.g., "instruct", "coder", "omni")
#   AUTH_ENABLED   - Enable API key authentication (default: true)
#   AUTH_KEYS_FILE - Path to API keys file (default: $DATA_DIR/api_keys.txt)
#   MOCK_BACKEND   - Skip llama-server for testing (default: false)
#
# Security:
#   Backend authentication key is auto-generated on startup and stored in a
#   secure temporary file (600 permissions). Gateway authenticates to llama-server
#   using this key, providing defense-in-depth protection.
#
# ==============================================================================
set -euo pipefail

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

log() { echo "[$(date -Is)] $*"; }
die() { log "FATAL: $*" >&2; exit 1; }

# Normalize truthy values: true/1/yes/on -> 0 (success), else 1 (failure)
is_truthy() {
    local val="${1:-}"
    val="${val,,}"  # lowercase
    [[ "$val" =~ ^(true|1|yes|on)$ ]]
}

# ==============================================================================
# MOCK BACKEND MODE (for CI testing)
# ==============================================================================
# Must come early to skip all validation and setup
if [ "${MOCK_BACKEND:-false}" = "true" ]; then
    echo "[$(date -Is)] ========================================"
    echo "[$(date -Is)] MOCK BACKEND MODE - Testing Only"
    echo "[$(date -Is)] ========================================"
    echo "[$(date -Is)] Skipping llama-server startup"
    echo "[$(date -Is)] Starting minimal services for testing"
    echo "[$(date -Is)]"

    # Set minimal required environment
    export GATEWAY_PORT="${PORT:-8000}"
    export BACKEND_HOST="127.0.0.1"
    export PORT_BACKEND="${PORT_BACKEND:-8080}"
    export BACKEND_API_KEY="mock-backend-key-not-validated"
    export AUTH_ENABLED="${AUTH_ENABLED:-true}"
    export AUTH_KEYS_FILE="${AUTH_KEYS_FILE:-/data/api_keys.txt}"
    export MAX_REQUESTS_PER_MINUTE="${MAX_REQUESTS_PER_MINUTE:-100}"
    export DATA_DIR="${DATA_DIR:-/data}"
    export PORT_HEALTH="${PORT_HEALTH:-8001}"

    # Ensure Python can find auth.py and other scripts
    export PYTHONPATH="/opt/app/scripts:${PYTHONPATH:-}"

    # Start health server (for platform health checks)
    HEALTH_SERVER_PY="/opt/app/scripts/health_server.py"
    if [ -f "$HEALTH_SERVER_PY" ]; then
        echo "[$(date -Is)] Starting health server on port $PORT_HEALTH..."
        PORT_HEALTH="$PORT_HEALTH" python3 -u "$HEALTH_SERVER_PY" &
        HEALTH_PID=$!
        echo "[$(date -Is)] Health server PID: $HEALTH_PID"
    fi

    # Start gateway (will return 502 for /v1/* endpoints)
    GATEWAY_PY="/opt/app/scripts/gateway.py"
    if [ -f "$GATEWAY_PY" ]; then
        echo "[$(date -Is)] Starting gateway on port $GATEWAY_PORT..."
        python3 -u "$GATEWAY_PY" &
        GATEWAY_PID=$!
        echo "[$(date -Is)] Gateway PID: $GATEWAY_PID"

        sleep 2

        if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
            echo "[$(date -Is)] ERROR: Gateway failed to start"
            exit 1
        fi
    else
        echo "[$(date -Is)] ERROR: Gateway not found at $GATEWAY_PY"
        exit 1
    fi

    echo "[$(date -Is)]"
    echo "[$(date -Is)] ========================================"
    echo "[$(date -Is)] Mock backend ready"
    echo "[$(date -Is)] ========================================"
    echo "[$(date -Is)] Health: http://0.0.0.0:$GATEWAY_PORT/ping"
    echo "[$(date -Is)] Gateway: http://0.0.0.0:$GATEWAY_PORT (returns 502 for /v1/*)"
    if [ "$AUTH_ENABLED" = "true" ]; then
        echo "[$(date -Is)] Auth: ENABLED"
    else
        echo "[$(date -Is)] Auth: DISABLED"
    fi
    echo "[$(date -Is)]"
    echo "[$(date -Is)] Keeping container alive..."

    # Keep container running
    tail -f /dev/null
fi

# CONFIGURATION & DEFAULTS
# ==============================================================================

# Data directory - configurable for any platform
# Common values:
#   /data           (default, generic)
#   /runpod-volume  (RunPod Serverless)
#   /workspace      (RunPod Pods, Vast.ai)
DATA_DIR="${DATA_DIR:-/data}"

# Auto-detect common platforms if DATA_DIR not explicitly set and /data doesn't exist
if [[ "$DATA_DIR" == "/data" && ! -d "/data" ]]; then
    if [[ -d /runpod-volume ]]; then
        DATA_DIR=/runpod-volume
    elif [[ -d /workspace ]]; then
        DATA_DIR=/workspace
    fi
fi

# Model configuration
MODEL_PATH="${MODEL_PATH:-}"
MODEL_NAME="${MODEL_NAME:-}"
MODELS_DIR="${MODELS_DIR:-$DATA_DIR/models}"

# Server configuration
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
PORT_HEALTH="${PORT_HEALTH:-8001}"

# Support both PORT_BACKEND (new) and BACKEND_PORT (old, deprecated)
if [[ -n "${BACKEND_PORT:-}" ]]; then
    log "WARNING: BACKEND_PORT is deprecated, use PORT_BACKEND instead"
    PORT_BACKEND="${BACKEND_PORT}"
else
    PORT_BACKEND="${PORT_BACKEND:-8080}"
fi

NGL="${NGL:-99}"
CTX="${CTX:-16384}"
THREADS="${THREADS:-0}"
EXTRA_ARGS="${EXTRA_ARGS:-}"

# Logging configuration
WORKER_TYPE="${WORKER_TYPE:-}"
WORKER_TYPE="${WORKER_TYPE//[^A-Za-z0-9_-]/_}"  # Sanitize (allow hyphens)

# Construct log directory name based on worker type
if [[ -n "$WORKER_TYPE" ]]; then
    LOG_NAME="llama-${WORKER_TYPE}"
else
    LOG_NAME="${LOG_NAME:-llama}"
fi
LOG_NAME="${LOG_NAME//[^A-Za-z0-9_.-]/_}"  # Sanitize
LOG_DIR="${LOG_DIR:-$DATA_DIR/logs}"

# Authentication configuration
AUTH_ENABLED="${AUTH_ENABLED:-true}"
AUTH_KEYS_FILE="${AUTH_KEYS_FILE:-$DATA_DIR/api_keys.txt}"
MAX_REQUESTS_PER_MINUTE="${MAX_REQUESTS_PER_MINUTE:-100}"

# Backend authentication - generate random key for this session
# This provides defense-in-depth: users auth to gateway, gateway auths to backend
BACKEND_API_KEY=$(python3 -c "import secrets; print('gateway-' + secrets.token_urlsafe(32))")

# Store in secure temporary file (use memory-backed filesystem if available)
if [[ -d /dev/shm ]]; then
    BACKEND_KEY_DIR="/dev/shm/llama-keys"
else
    BACKEND_KEY_DIR="/tmp/llama-keys"
fi

mkdir -p "$BACKEND_KEY_DIR" 2>/dev/null || true
chmod 700 "$BACKEND_KEY_DIR" 2>/dev/null || true

BACKEND_KEY_FILE="$BACKEND_KEY_DIR/backend-${INSTANCE_ID}.key"
echo "$BACKEND_API_KEY" > "$BACKEND_KEY_FILE"
chmod 600 "$BACKEND_KEY_FILE" 2>/dev/null || true

# Verify backend key file was created correctly
if [[ ! -f "$BACKEND_KEY_FILE" ]]; then
    die "Failed to create backend key file: $BACKEND_KEY_FILE"
fi

# Verify file permissions (platform-specific stat command)
if command -v stat &>/dev/null; then
    # Try GNU stat first (Linux)
    PERMS=$(stat -c "%a" "$BACKEND_KEY_FILE" 2>/dev/null || stat -f "%Lp" "$BACKEND_KEY_FILE" 2>/dev/null)
    if [[ -n "$PERMS" ]]; then
        if [[ "$PERMS" != "600" ]]; then
            log "WARNING: Backend key file has permissions $PERMS (expected 600), attempting to fix..."
            chmod 600 "$BACKEND_KEY_FILE" || die "Failed to set correct permissions on $BACKEND_KEY_FILE"
            PERMS=$(stat -c "%a" "$BACKEND_KEY_FILE" 2>/dev/null || stat -f "%Lp" "$BACKEND_KEY_FILE" 2>/dev/null)
            [[ "$PERMS" == "600" ]] || die "Still unable to set 600 permissions on key file"
        fi
        log "Backend key file permissions verified: 600"
    fi
fi

# Verify file content matches generated key
FILE_KEY=$(cat "$BACKEND_KEY_FILE" 2>/dev/null)
if [[ "$FILE_KEY" != "$BACKEND_API_KEY" ]]; then
    die "Backend key file content doesn't match generated key (possible filesystem corruption)"
fi

# Verify key format (should be gateway-{43 chars})
if [[ ${#BACKEND_API_KEY} -ne 51 ]]; then
    die "Backend key has invalid length: ${#BACKEND_API_KEY} (expected 51)"
fi

log "Backend key file verified: $BACKEND_KEY_FILE"

# Instance identity
INSTANCE_ID="${INSTANCE_ID:-${HOSTNAME:-unknown}}"
INSTANCE_ID="${INSTANCE_ID//[^a-zA-Z0-9._-]/_}"

# Paths
LLAMA_BIN="/app/llama-server"
GATEWAY_PY="/opt/app/scripts/gateway.py"
HEALTH_SERVER_PY="/opt/app/scripts/health_server.py"

# Process tracking
LLAMA_PID=""
GATEWAY_PID=""
HEALTH_PID=""
AUDIT_PID=""
SHUTDOWN_IN_PROGRESS=0

# ==============================================================================
# DEBUG MODE
# ==============================================================================

if is_truthy "${DEBUG_SHELL:-}"; then
    log "DEBUG_SHELL enabled - holding for inspection"
    log "id=$(id) hostname=$(hostname)"
    log "Environment:"
    env | sort
    log "Sleeping 300s..."
    sleep 300
    exit 0
fi

# ==============================================================================
# BOOT LOGGING
# ==============================================================================

BOOT_LOG=""
if [[ -d "$DATA_DIR" ]] || mkdir -p "$DATA_DIR" 2>/dev/null; then
    BOOT_DIR="$DATA_DIR/logs/_boot"
    mkdir -p "$BOOT_DIR" 2>/dev/null || true
    # Timestamp-first format for chronological sorting
    BOOT_LOG="$BOOT_DIR/$(date +%Y%m%d_%H%M%S)_boot_${INSTANCE_ID}.log"
    echo "$BOOT_LOG" > "$BOOT_DIR/latest.txt" 2>/dev/null || true

    # Mirror output to boot log
    exec > >(tee -a "$BOOT_LOG") 2>&1 || true
fi

log "========================================"
log "llama-gguf-inference"
log "========================================"
log "Hostname: $(hostname)"
log "Instance: $INSTANCE_ID"

# Version info
if [[ -f /opt/app/VERSION ]]; then
    log "Version: $(cat /opt/app/VERSION | tr '\n' ' ')"
fi

# ==============================================================================
# ENVIRONMENT VALIDATION
# ==============================================================================

log "--- Configuration ---"
log "DATA_DIR=$DATA_DIR"
log "MODEL_NAME=${MODEL_NAME:-<unset>}"
log "MODEL_PATH=${MODEL_PATH:-<unset>}"
log "MODELS_DIR=$MODELS_DIR"
log "NGL=$NGL CTX=$CTX"
log "PORT=$PORT PORT_HEALTH=$PORT_HEALTH PORT_BACKEND=$PORT_BACKEND"
log "WORKER_TYPE=${WORKER_TYPE:-<unset>}"
log "LOG_NAME=$LOG_NAME"
log "AUTH_ENABLED=$AUTH_ENABLED"
log "AUTH_KEYS_FILE=$AUTH_KEYS_FILE"
log "MAX_REQUESTS_PER_MINUTE=$MAX_REQUESTS_PER_MINUTE"
log "BACKEND_AUTH=enabled (key: ${BACKEND_API_KEY:0:8}...${BACKEND_API_KEY: -8}) file: $BACKEND_KEY_FILE"

# ==============================================================================
# MODEL RESOLUTION
# ==============================================================================

resolve_model() {
    # If MODEL_PATH is set, use it directly
    if [[ -n "$MODEL_PATH" ]]; then
        echo "$MODEL_PATH"
        return 0
    fi

    # If MODEL_NAME is set, look in MODELS_DIR
    if [[ -n "$MODEL_NAME" ]]; then
        if [[ -z "$MODELS_DIR" ]]; then
            die "MODEL_NAME set but MODELS_DIR is empty"
        fi
        echo "$MODELS_DIR/$MODEL_NAME"
        return 0
    fi

    # No model specified
    return 1
}

MODEL="$(resolve_model)" || die "No model specified. Set MODEL_NAME or MODEL_PATH."

log "--- Model ---"
log "Resolved: $MODEL"

if [[ ! -f "$MODEL" ]]; then
    die "Model file not found: $MODEL"
fi

if [[ ! -r "$MODEL" ]]; then
    die "Model file not readable: $MODEL"
fi

MODEL_SIZE=$(stat -c%s "$MODEL" 2>/dev/null || echo "unknown")
log "Size: $MODEL_SIZE bytes"

# ==============================================================================
# BINARY & LIBRARY CHECKS
# ==============================================================================

log "--- Binary Check ---"

if [[ ! -x "$LLAMA_BIN" ]]; then
    die "llama-server not found or not executable: $LLAMA_BIN"
fi

# Ensure shared libraries are findable
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-/app}:/app:/usr/local/lib:/usr/lib/x86_64-linux-gnu"

# Quick sanity check
if ! "$LLAMA_BIN" --version >/dev/null 2>&1; then
    log "WARNING: llama-server --version failed, checking libraries..."
    ldd "$LLAMA_BIN" 2>&1 | grep -i "not found" && die "Missing shared libraries"
fi

LLAMA_VERSION=$("$LLAMA_BIN" --version 2>&1 | head -1 || echo "unknown")
log "llama-server: $LLAMA_VERSION"

# ==============================================================================
# GPU CHECK
# ==============================================================================

log "--- GPU Check ---"
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "unavailable")
    log "GPU: $GPU_INFO"
else
    log "nvidia-smi not available (CPU mode)"
fi

# ==============================================================================
# AUTHENTICATION CHECK
# ==============================================================================

log "--- Authentication ---"
if is_truthy "$AUTH_ENABLED"; then
    log "Authentication: ENABLED"
    if [[ -f "$AUTH_KEYS_FILE" ]]; then
        KEY_COUNT=$(grep -v "^#" "$AUTH_KEYS_FILE" | grep -v "^$" | wc -l)
        log "Keys file: $AUTH_KEYS_FILE ($KEY_COUNT keys)"
    else
        log "WARNING: AUTH_ENABLED=true but keys file not found: $AUTH_KEYS_FILE"
        log "         Create keys file or all requests will be accepted!"
    fi
else
    log "Authentication: DISABLED"
    log "WARNING: All requests will be accepted without authentication!"
fi

# ==============================================================================
# GRACEFUL SHUTDOWN HANDLER
# ==============================================================================

shutdown() {
    if [[ "$SHUTDOWN_IN_PROGRESS" == "1" ]]; then
        return
    fi
    SHUTDOWN_IN_PROGRESS=1

    log ""
    log "========================================"
    log "Shutdown signal received"
    log "========================================"

    # Give llama-server time to finish in-flight requests
    if [[ -n "$LLAMA_PID" ]] && kill -0 "$LLAMA_PID" 2>/dev/null; then
        log "Sending SIGTERM to llama-server (PID $LLAMA_PID)..."
        kill -TERM "$LLAMA_PID" 2>/dev/null || true

        # Wait up to 30 seconds for graceful shutdown
        local count=0
        while kill -0 "$LLAMA_PID" 2>/dev/null && [[ $count -lt 30 ]]; do
            sleep 1
            ((count++))
        done

        if kill -0 "$LLAMA_PID" 2>/dev/null; then
            log "llama-server didn't exit gracefully, sending SIGKILL..."
            kill -KILL "$LLAMA_PID" 2>/dev/null || true
        fi
    fi

    if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
        log "Stopping gateway (PID $GATEWAY_PID)..."
        kill -TERM "$GATEWAY_PID" 2>/dev/null || true
    fi

    if [[ -n "$HEALTH_PID" ]] && kill -0 "$HEALTH_PID" 2>/dev/null; then
        log "Stopping health server (PID $HEALTH_PID)..."
        kill -TERM "$HEALTH_PID" 2>/dev/null || true
    fi

    if [[ -n "$AUDIT_PID" ]] && kill -0 "$AUDIT_PID" 2>/dev/null; then
        log "Stopping audit monitor (PID $AUDIT_PID)..."
        kill -TERM "$AUDIT_PID" 2>/dev/null || true
    fi

    # Clean up backend key file securely
    if [[ -n "$BACKEND_KEY_FILE" ]] && [[ -f "$BACKEND_KEY_FILE" ]]; then
        log "Securely removing backend key file..."

        # Use shred if available for secure deletion
        if command -v shred &>/dev/null; then
            # Overwrite file 3 times with random data, then zero, then delete
            shred -vfz -n 3 "$BACKEND_KEY_FILE" 2>/dev/null || rm -f "$BACKEND_KEY_FILE"
        else
            # Fallback: overwrite with zeros before deleting
            dd if=/dev/zero of="$BACKEND_KEY_FILE" bs=52 count=1 2>/dev/null || true
            rm -f "$BACKEND_KEY_FILE" 2>/dev/null || true
        fi

        log "Backend key file removed"
    fi

    log "Shutdown complete"
    exit 0
}

trap shutdown SIGTERM SIGINT EXIT

# ==============================================================================
# BUILD LLAMA-SERVER ARGUMENTS
# ==============================================================================

LLAMA_ARGS=(
    -m "$MODEL"
    --host "127.0.0.1"
    --port "$PORT_BACKEND"
    -c "$CTX"
    -ngl "$NGL"
    --api-key-file "$BACKEND_KEY_FILE"
)

log "Security: llama-server will bind to 127.0.0.1 only (not accessible from network)"

if [[ "$THREADS" != "0" ]]; then
    LLAMA_ARGS+=(-t "$THREADS")
fi

# Append extra args (space-split)
# shellcheck disable=SC2206
if [[ -n "$EXTRA_ARGS" ]]; then
    LLAMA_ARGS+=($EXTRA_ARGS)
fi

# ==============================================================================
# START LLAMA-SERVER
# ==============================================================================

log ""
log "========================================"
log "Starting llama-server"
log "========================================"
log "Command: $LLAMA_BIN ${LLAMA_ARGS[*]}"

# Determine where to send llama-server output
if [[ -d "$DATA_DIR" ]]; then
    LLAMA_LOG_DIR="$LOG_DIR/$LOG_NAME"
    mkdir -p "$LLAMA_LOG_DIR" 2>/dev/null || true
    # Timestamp-first format for chronological sorting
    LLAMA_LOG="$LLAMA_LOG_DIR/$(date +%Y%m%d_%H%M%S)_server_${INSTANCE_ID}.log"
    echo "$LLAMA_LOG" > "$LLAMA_LOG_DIR/latest.txt" 2>/dev/null || true
    log "Log file: $LLAMA_LOG"

    # Start with output to both console and file
    "$LLAMA_BIN" "${LLAMA_ARGS[@]}" 2>&1 | tee -a "$LLAMA_LOG" &
    LLAMA_PID=$!
else
    log "No data directory - logging to stdout only"
    "$LLAMA_BIN" "${LLAMA_ARGS[@]}" &
    LLAMA_PID=$!
fi

log "llama-server PID: $LLAMA_PID"

# Wait a moment and verify it started
sleep 2

if ! kill -0 "$LLAMA_PID" 2>/dev/null; then
    # Try to get exit code
    wait "$LLAMA_PID" 2>/dev/null || true
    EXIT_CODE=$?

    log ""
    log "========================================"
    log "FATAL: llama-server failed to start"
    log "========================================"
    log "Exit code: $EXIT_CODE"

    case $EXIT_CODE in
        0)   log "Exit 0 but process gone - check logs above" ;;
        1)   log "General error - check model path and arguments" ;;
        127) log "Binary not found" ;;
        134) log "SIGABRT - assertion failure or abort()" ;;
        137) log "SIGKILL - likely OOM (out of memory)" ;;
        139) log "SIGSEGV - segmentation fault" ;;
        *)   log "Unknown exit code" ;;
    esac

    exit 1
fi

# ==============================================================================
# VERIFY BACKEND SECURITY & CONNECTIVITY
# ==============================================================================

log ""
log "========================================"
log "Verifying backend security"
log "========================================"

# Test 1: Verify localhost binding (not 0.0.0.0)
log "Test 1: Checking network binding..."
sleep 1  # Give server moment to bind

if command -v netstat &>/dev/null; then
    if netstat -tln 2>/dev/null | grep ":$PORT_BACKEND" | grep -q "0.0.0.0"; then
        log "ERROR: llama-server is bound to 0.0.0.0 (accessible from network)!"
        log "ERROR: This is a security risk - backend should only bind to 127.0.0.1"
        kill "$LLAMA_PID" 2>/dev/null || true
        exit 1
    fi

    if netstat -tln 2>/dev/null | grep ":$PORT_BACKEND" | grep -q "127.0.0.1"; then
        log "✓ Verified: llama-server bound to 127.0.0.1 only (network isolated)"
    else
        log "WARNING: Could not verify binding address, but --host was set to 127.0.0.1"
    fi
elif command -v ss &>/dev/null; then
    # Alternative using ss command
    if ss -tln 2>/dev/null | grep ":$PORT_BACKEND" | grep -q "0.0.0.0"; then
        log "ERROR: llama-server is bound to 0.0.0.0 (accessible from network)!"
        kill "$LLAMA_PID" 2>/dev/null || true
        exit 1
    fi
    log "✓ Verified: llama-server bound to 127.0.0.1 only"
else
    log "WARNING: netstat/ss not available, skipping binding verification"
    log "         (backend was configured with --host 127.0.0.1)"
fi

# Test 2: Verify backend responds with authentication
log "Test 2: Testing backend connectivity and authentication..."

# Check if curl is available
if ! command -v curl &>/dev/null; then
    log "WARNING: curl not found, skipping connectivity test"
    log "         Backend authentication cannot be verified at startup"
else
    BACKEND_READY=false
    MAX_WAIT=30

    for i in $(seq 1 $MAX_WAIT); do
        # Try to connect with backend key
        if curl -s -f -m 2 \
           -H "Authorization: Bearer $BACKEND_API_KEY" \
           "http://127.0.0.1:$PORT_BACKEND/health" &>/dev/null; then
            BACKEND_READY=true
            log "✓ Backend responds correctly (attempt $i/$MAX_WAIT)"
            break
        fi

        # Check if process still running
        if ! kill -0 "$LLAMA_PID" 2>/dev/null; then
            log "ERROR: llama-server process died during connectivity test"
            exit 1
        fi

        # Log progress every 5 seconds
        if [[ $((i % 5)) -eq 0 ]]; then
            log "Waiting for backend to be ready ($i/$MAX_WAIT)..."
        fi

        sleep 1
    done

    if [[ "$BACKEND_READY" != "true" ]]; then
        log "ERROR: Backend not responding after ${MAX_WAIT} seconds"
        log "ERROR: This could indicate:"
        log "       - llama-server failed to load model"
        log "       - Backend authentication not working"
        log "       - Network connectivity issues"
        kill "$LLAMA_PID" 2>/dev/null || true
        exit 1
    fi

    # Test 3: Verify authentication is actually enforced
    log "Test 3: Verifying backend authentication is enforced..."

    # Try without auth - should fail
    if curl -s -f -m 2 "http://127.0.0.1:$PORT_BACKEND/health" &>/dev/null; then
        log "WARNING: Backend responded without authentication!"
        log "WARNING: This suggests --api-key-file may not be working"
    else
        log "✓ Verified: Backend requires authentication (unauthorized requests rejected)"
    fi
fi

log ""
log "========================================"
log "Backend security verification complete"
log "========================================"
log ""

# Start audit logging monitor (if logs are available)
if [[ -n "$LLAMA_LOG" ]] && [[ -f "$LLAMA_LOG" ]]; then
    log "Starting backend audit logging monitor..."

    # Monitor llama-server logs for authentication failures
    (
        tail -f "$LLAMA_LOG" 2>/dev/null | grep --line-buffered -iE "401|unauthorized|forbidden|auth.*fail" | while read -r line; do
            log "BACKEND AUTH FAILURE: $line"
        done
    ) &
    AUDIT_PID=$!

    log "Audit monitor PID: $AUDIT_PID"
else
    log "Audit logging not available (no log file)"
    AUDIT_PID=""
fi

# ==============================================================================
# START HEALTH SERVER
# ==============================================================================

log ""
log "========================================"
log "Starting health server"
log "========================================"

if [[ ! -f "$HEALTH_SERVER_PY" ]]; then
    die "Health server not found: $HEALTH_SERVER_PY"
fi

PORT_HEALTH="$PORT_HEALTH" \
python3 -u "$HEALTH_SERVER_PY" &
HEALTH_PID=$!

log "Health server PID: $HEALTH_PID (port $PORT_HEALTH)"

sleep 1

if ! kill -0 "$HEALTH_PID" 2>/dev/null; then
    log "WARNING: Health server failed to start (non-fatal)"
    HEALTH_PID=""
fi

# ==============================================================================
# START GATEWAY
# ==============================================================================

log ""
log "========================================"
log "Starting gateway"
log "========================================"

if [[ ! -f "$GATEWAY_PY" ]]; then
    die "Gateway not found: $GATEWAY_PY"
fi

# Export environment for gateway
export GATEWAY_PORT="$PORT"
export BACKEND_HOST="127.0.0.1"
export PORT_BACKEND="$PORT_BACKEND"
export BACKEND_API_KEY="$BACKEND_API_KEY"
export AUTH_ENABLED="$AUTH_ENABLED"
export AUTH_KEYS_FILE="$AUTH_KEYS_FILE"
export MAX_REQUESTS_PER_MINUTE="$MAX_REQUESTS_PER_MINUTE"
export DATA_DIR="$DATA_DIR"

python3 -u "$GATEWAY_PY" &
GATEWAY_PID=$!

log "Gateway PID: $GATEWAY_PID (port $PORT -> backend $PORT_BACKEND)"

sleep 1

if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
    log "FATAL: Gateway failed to start"
    exit 1
fi

# Unset backend key from shell environment (gateway already has it)
# This prevents the key from being inherited by any child processes
unset BACKEND_API_KEY
log "Backend key cleared from shell environment (gateway retains it)"

# ==============================================================================
# RUNNING
# ==============================================================================

log ""
log "========================================"
log "Services running"
log "========================================"
log "llama-server:   PID $LLAMA_PID (port $PORT_BACKEND)"
log "gateway:        PID $GATEWAY_PID (port $PORT)"
if [[ -n "$HEALTH_PID" ]]; then
    log "health server:  PID $HEALTH_PID (port $PORT_HEALTH)"
fi
log ""
log "Endpoints:"
log "  Health (no auth):  http://0.0.0.0:$PORT/ping"
log "  Status (no auth):  http://0.0.0.0:$PORT/health"
log "  Metrics (no auth): http://0.0.0.0:$PORT/metrics"
if is_truthy "$AUTH_ENABLED"; then
    log "  Chat (auth req):   http://0.0.0.0:$PORT/v1/chat/completions"
    log "  Complete (auth):   http://0.0.0.0:$PORT/v1/completions"
else
    log "  Chat (no auth):    http://0.0.0.0:$PORT/v1/chat/completions"
    log "  Complete (no auth): http://0.0.0.0:$PORT/v1/completions"
fi
if [[ -n "$HEALTH_PID" ]]; then
    log ""
    log "Platform health checks should use: http://0.0.0.0:$PORT_HEALTH/"
fi
if [[ -n "$WORKER_TYPE" ]]; then
    log ""
    log "Worker type: $WORKER_TYPE"
    log "Logs directory: $LOG_DIR/$LOG_NAME/"
fi
log ""
log "Waiting for processes..."

# ==============================================================================
# WAIT FOR EXIT
# ==============================================================================

# Wait for either process to exit
wait -n "$LLAMA_PID" "$GATEWAY_PID" 2>/dev/null || true
EXIT_CODE=$?

log ""
log "========================================"
log "Process exited"
log "========================================"

if ! kill -0 "$LLAMA_PID" 2>/dev/null; then
    log "llama-server exited (code: $EXIT_CODE)"
elif ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
    log "Gateway exited (code: $EXIT_CODE)"
fi

# Trigger cleanup
exit "$EXIT_CODE"
