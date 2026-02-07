#!/usr/bin/env bash
# ==============================================================================
# test_docker_integration.sh - Docker-specific integration tests
#
# This script tests Docker container functionality including:
# - Docker build
# - Container startup
# - Volume mounts
# - Environment variables
# - Service orchestration
#
# Usage:
#   bash scripts/tests/test_docker_integration.sh
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
# ==============================================================================

set -euo pipefail

# Configuration
IMAGE_NAME="${IMAGE_NAME:-llama-gguf-inference-test}"
CONTAINER_NAME="llama-test-$$"
TEST_PORT="${TEST_PORT:-18000}"
VERBOSE="${VERBOSE:-false}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test tracking
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Cleanup flag
CLEANUP_NEEDED=false

# ==============================================================================
# Helper Functions
# ==============================================================================

log() {
    echo -e "${GREEN}[TEST]${NC} $*"
}

error() {
    echo -e "${RED}[FAIL]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${NC}       $*${NC}"
    fi
}

test_start() {
    ((TESTS_RUN++))
    log "Test $TESTS_RUN: $1"
}

test_pass() {
    ((TESTS_PASSED++))
    echo -e "       ${GREEN}✓ PASS${NC}"
}

test_fail() {
    ((TESTS_FAILED++))
    error "✗ FAIL: $1"
}

cleanup() {
    if [[ "$CLEANUP_NEEDED" == "true" ]]; then
        log "Cleaning up..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
        rm -rf /tmp/llama-docker-test-* 2>/dev/null || true
    fi
}

trap cleanup EXIT

# ==============================================================================
# Test Functions
# ==============================================================================

test_docker_available() {
    test_start "Docker is available"

    if ! command -v docker >/dev/null 2>&1; then
        test_fail "Docker not found"
        return 1
    fi
    verbose "  Docker found"

    if ! docker info >/dev/null 2>&1; then
        test_fail "Docker daemon not running"
        return 1
    fi
    verbose "  Docker daemon running"

    test_pass
}

test_docker_build() {
    test_start "Docker image builds successfully"

    # Build with mock backend for testing
    if docker build \
        -t "$IMAGE_NAME" \
        --build-arg GIT_SHA=test \
        --build-arg BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        . >/dev/null 2>&1; then
        verbose "  Image built successfully"
        test_pass
    else
        test_fail "Docker build failed"
        return 1
    fi
}

test_image_metadata() {
    test_start "Image metadata is correct"

    # Check image exists
    if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
        test_fail "Image not found"
        return 1
    fi

    # Check labels
    local labels
    labels=$(docker image inspect "$IMAGE_NAME" --format='{{json .Config.Labels}}')
    verbose "  Labels: $(echo "$labels" | jq -r 'keys | join(", ")')"

    # Check exposed ports
    local ports
    ports=$(docker image inspect "$IMAGE_NAME" --format='{{json .Config.ExposedPorts}}')

    if echo "$ports" | grep -q "8000"; then
        verbose "  Port 8000 exposed"
    else
        test_fail "Port 8000 not exposed"
        return 1
    fi

    test_pass
}

test_container_startup() {
    test_start "Container starts successfully"

    # Create test data directory
    local test_dir="/tmp/llama-docker-test-$$"
    mkdir -p "$test_dir/models"
    mkdir -p "$test_dir/logs"

    # Create test API keys
    echo "testing:sk-test-1234567890abcdef" > "$test_dir/api_keys.txt"

    # Create dummy model file
    touch "$test_dir/models/test-model.gguf"

    # Start container with mock backend
    if docker run -d \
        --name "$CONTAINER_NAME" \
        -v "$test_dir:/data" \
        -e MODEL_NAME=test-model.gguf \
        -e AUTH_ENABLED=true \
        -e AUTH_KEYS_FILE=/data/api_keys.txt \
        -e MOCK_BACKEND=true \
        -p "$TEST_PORT:8000" \
        "$IMAGE_NAME" >/dev/null 2>&1; then
        verbose "  Container started"
        CLEANUP_NEEDED=true
    else
        test_fail "Container failed to start"
        rm -rf "$test_dir"
        return 1
    fi

    # Wait for container to be ready
    verbose "  Waiting for container to be ready..."
    local retries=30
    local ready=false

    for ((i=1; i<=retries; i++)); do
        if docker ps --filter "name=$CONTAINER_NAME" --format '{{.Status}}' | grep -q "Up"; then
            verbose "  Container is running"
            ready=true
            break
        fi
        sleep 1
    done

    if [[ "$ready" == "false" ]]; then
        test_fail "Container did not start within timeout"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        return 1
    fi

    test_pass
}

test_health_endpoint() {
    test_start "Health endpoints are accessible"

    # Wait for services to be ready
    sleep 5

    # Test /ping
    local ping_code
    ping_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$TEST_PORT/ping" 2>&1)

    if [[ "$ping_code" == "200" ]]; then
        verbose "  /ping: 200"
    else
        test_fail "/ping returned $ping_code (expected 200)"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        return 1
    fi

    # Test /health
    local health_code
    health_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$TEST_PORT/health" 2>&1)

    if [[ "$health_code" == "200" ]]; then
        verbose "  /health: 200"
    else
        test_fail "/health returned $health_code (expected 200)"
        return 1
    fi

    test_pass
}

test_environment_variables() {
    test_start "Environment variables are set correctly"

    # Check key environment variables in container
    local model_name
    model_name=$(docker exec "$CONTAINER_NAME" printenv MODEL_NAME 2>&1 || echo "")

    if [[ "$model_name" == "test-model.gguf" ]]; then
        verbose "  MODEL_NAME: $model_name"
    else
        test_fail "MODEL_NAME not set correctly (got: $model_name)"
        return 1
    fi

    local auth_enabled
    auth_enabled=$(docker exec "$CONTAINER_NAME" printenv AUTH_ENABLED 2>&1 || echo "")

    if [[ "$auth_enabled" == "true" ]]; then
        verbose "  AUTH_ENABLED: $auth_enabled"
    else
        test_fail "AUTH_ENABLED not set correctly"
        return 1
    fi

    test_pass
}

test_volume_mounts() {
    test_start "Volume mounts work correctly"

    # Check if /data is mounted
    if docker exec "$CONTAINER_NAME" test -d /data; then
        verbose "  /data directory exists"
    else
        test_fail "/data directory not found"
        return 1
    fi

    # Check if model file is accessible
    if docker exec "$CONTAINER_NAME" test -f /data/models/test-model.gguf; then
        verbose "  Model file accessible"
    else
        test_fail "Model file not accessible in container"
        return 1
    fi

    # Check if api_keys.txt is accessible
    if docker exec "$CONTAINER_NAME" test -f /data/api_keys.txt; then
        verbose "  API keys file accessible"
    else
        test_fail "API keys file not accessible"
        return 1
    fi

    test_pass
}

test_authentication() {
    test_start "Authentication works in container"

    # Request without auth should fail
    local no_auth_code
    no_auth_code=$(curl -s -o /dev/null -w "%{http_code}" \
        "http://localhost:$TEST_PORT/v1/models" 2>&1)

    if [[ "$no_auth_code" == "401" ]]; then
        verbose "  Correctly rejected unauthenticated request"
    else
        test_fail "Expected 401, got $no_auth_code"
        return 1
    fi

    # Request with valid auth should pass
    local with_auth_code
    with_auth_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer sk-test-1234567890abcdef" \
        "http://localhost:$TEST_PORT/v1/models" 2>&1)

    # Should NOT be 401 (auth passed)
    if [[ "$with_auth_code" != "401" ]]; then
        verbose "  Valid key accepted (response: $with_auth_code)"
    else
        test_fail "Valid key was rejected"
        return 1
    fi

    test_pass
}

test_logs_created() {
    test_start "Logs are created correctly"

    # Wait a bit for logs to be written
    sleep 2

    # Check if boot log was created
    if docker exec "$CONTAINER_NAME" test -d /data/logs/_boot; then
        verbose "  Boot log directory exists"
    else
        test_fail "Boot log directory not created"
        return 1
    fi

    # Check if server log directory was created
    if docker exec "$CONTAINER_NAME" sh -c 'ls /data/logs/ | grep -q llama'; then
        verbose "  Server log directory exists"
    else
        warn "Server log directory not created (may be expected with mock backend)"
    fi

    test_pass
}

test_graceful_shutdown() {
    test_start "Container shuts down gracefully"

    # Send SIGTERM
    if docker stop -t 30 "$CONTAINER_NAME" >/dev/null 2>&1; then
        verbose "  Container stopped gracefully"
    else
        test_fail "Container did not stop gracefully"
        return 1
    fi

    # Check exit code
    local exit_code
    exit_code=$(docker inspect "$CONTAINER_NAME" --format='{{.State.ExitCode}}')

    if [[ "$exit_code" == "0" ]] || [[ "$exit_code" == "143" ]]; then
        verbose "  Exit code: $exit_code (clean shutdown)"
    else
        test_fail "Unexpected exit code: $exit_code"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        return 1
    fi

    test_pass
}

# ==============================================================================
# Main Test Execution
# ==============================================================================

main() {
    log "========================================"
    log "Docker Integration Tests"
    log "========================================"
    log "Image: $IMAGE_NAME"
    log "Test Port: $TEST_PORT"
    log ""

    # Run tests
    test_docker_available || exit 1
    test_docker_build || exit 1
    test_image_metadata
    test_container_startup || exit 1
    test_health_endpoint
    test_environment_variables
    test_volume_mounts
    test_authentication
    test_logs_created
    test_graceful_shutdown

    # Summary
    log ""
    log "========================================"
    log "Test Summary"
    log "========================================"
    log "Tests run:    $TESTS_RUN"
    log "Tests passed: $TESTS_PASSED"
    log "Tests failed: $TESTS_FAILED"

    if [[ $TESTS_FAILED -eq 0 ]]; then
        log ""
        log "${GREEN}✓ All Docker tests passed!${NC}"
        exit 0
    else
        error ""
        error "✗ Some tests failed"
        exit 1
    fi
}

main "$@"
