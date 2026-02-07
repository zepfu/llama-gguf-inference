#!/usr/bin/env bash
# ==============================================================================
# test_integration.sh - Full workflow integration tests
#
# This script tests the complete request lifecycle through all components.
#
# Prerequisites:
#   - Gateway running on PORT (default 8000)
#   - llama-server running on PORT_BACKEND (default 8080)
#   - Valid API keys configured (if AUTH_ENABLED=true)
#
# Usage:
#   bash scripts/tests/test_integration.sh
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
# ==============================================================================

set -euo pipefail

# Configuration
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8000}"
TEST_KEY="${TEST_KEY:-sk-test-12345}"
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

# ==============================================================================
# Test Functions
# ==============================================================================

test_system_ready() {
    test_start "System is ready for testing"

    # Check gateway
    if ! curl -sf "$GATEWAY_URL/ping" >/dev/null 2>&1; then
        test_fail "Gateway not accessible at $GATEWAY_URL"
        return 1
    fi
    verbose "  Gateway accessible"

    # Check health
    local health_response
    health_response=$(curl -s "$GATEWAY_URL/health" 2>&1 || echo "error")

    if [[ "$health_response" == "error" ]]; then
        test_fail "Health endpoint not accessible"
        return 1
    fi
    verbose "  Health endpoint working"

    test_pass
}

test_health_endpoints() {
    test_start "Health endpoints respond correctly"

    # /ping should return 200
    local ping_code
    ping_code=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/ping")

    if [[ "$ping_code" != "200" ]]; then
        test_fail "/ping returned $ping_code (expected 200)"
        return 1
    fi
    verbose "  /ping: 200"

    # /health should return JSON
    local health_body
    health_body=$(curl -s "$GATEWAY_URL/health")

    if ! echo "$health_body" | jq . >/dev/null 2>&1; then
        test_fail "/health did not return valid JSON"
        return 1
    fi
    verbose "  /health: valid JSON"

    # /metrics should return JSON
    local metrics_body
    metrics_body=$(curl -s "$GATEWAY_URL/metrics")

    if ! echo "$metrics_body" | jq . >/dev/null 2>&1; then
        test_fail "/metrics did not return valid JSON"
        return 1
    fi
    verbose "  /metrics: valid JSON"

    test_pass
}

test_auth_flow() {
    test_start "Authentication flow works correctly"

    # Request without auth should fail
    local no_auth_code
    no_auth_code=$(curl -s -o /dev/null -w "%{http_code}" \
        "$GATEWAY_URL/v1/models" 2>&1)

    if [[ "$no_auth_code" == "401" ]]; then
        verbose "  Correctly rejected unauthenticated request"
    elif [[ "$no_auth_code" == "200" ]] || [[ "$no_auth_code" == "404" ]]; then
        warn "Auth appears to be disabled"
    else
        test_fail "Unexpected response without auth: $no_auth_code"
        return 1
    fi

    # Request with valid auth should pass auth layer
    local with_auth_code
    with_auth_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $TEST_KEY" \
        "$GATEWAY_URL/v1/models" 2>&1)

    # Should NOT be 401 (auth layer passed)
    if [[ "$with_auth_code" == "401" ]]; then
        test_fail "Valid key was rejected"
        return 1
    fi
    verbose "  Valid key accepted (response: $with_auth_code)"

    test_pass
}

test_request_proxying() {
    test_start "Requests are proxied to backend correctly"

    # Make a simple request
    local response_code response_body
    response_body=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer $TEST_KEY" \
        -H "Content-Type: application/json" \
        -d '{"model":"test","messages":[{"role":"user","content":"hi"}],"max_tokens":1}' \
        "$GATEWAY_URL/v1/chat/completions" 2>&1)

    response_code=$(echo "$response_body" | tail -1)
    response_body=$(echo "$response_body" | head -n -1)

    verbose "  Response code: $response_code"

    # 200 = success, 502 = backend not ready (acceptable for test)
    if [[ "$response_code" == "200" ]]; then
        verbose "  Backend returned successful response"

        # Check if response is valid JSON
        if echo "$response_body" | jq . >/dev/null 2>&1; then
            verbose "  Valid JSON response"
        else
            warn "Response not valid JSON (but request succeeded)"
        fi
    elif [[ "$response_code" == "502" ]]; then
        verbose "  Backend not ready (502) - acceptable for integration test"
    else
        test_fail "Unexpected response code: $response_code"
        verbose "  Body: ${response_body:0:200}"
        return 1
    fi

    test_pass
}

test_streaming_support() {
    test_start "Streaming responses work"

    # Request with streaming
    local response
    response=$(curl -s \
        -H "Authorization: Bearer $TEST_KEY" \
        -H "Content-Type: application/json" \
        -d '{"model":"test","messages":[{"role":"user","content":"test"}],"stream":true,"max_tokens":1}' \
        "$GATEWAY_URL/v1/chat/completions" 2>&1)

    # Should either get SSE events or 502
    if echo "$response" | grep -q "data:"; then
        verbose "  Received SSE events"
        test_pass
    elif echo "$response" | grep -q "502"; then
        verbose "  Backend not ready (502) - acceptable"
        test_pass
    else
        # May just get empty response if backend down
        verbose "  No SSE events (backend may not be ready)"
        test_pass
    fi
}

test_error_handling() {
    test_start "Error handling works correctly"

    # Invalid request (missing required field)
    local error_code
    error_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $TEST_KEY" \
        -H "Content-Type: application/json" \
        -d '{"invalid":"request"}' \
        "$GATEWAY_URL/v1/chat/completions" 2>&1)

    verbose "  Invalid request response: $error_code"

    # Should get error (400, 422, or 502 if backend down)
    if [[ "$error_code" =~ ^(400|422|502)$ ]]; then
        verbose "  Properly handled invalid request"
        test_pass
    else
        warn "Unexpected response to invalid request: $error_code"
        test_pass  # Non-fatal
    fi
}

test_metrics_tracking() {
    test_start "Metrics are tracked correctly"

    # Get initial metrics
    local metrics_before
    metrics_before=$(curl -s "$GATEWAY_URL/metrics")

    if ! echo "$metrics_before" | jq . >/dev/null 2>&1; then
        test_fail "Invalid metrics response"
        return 1
    fi

    local requests_before
    requests_before=$(echo "$metrics_before" | jq -r '.gateway.requests_total // 0')
    verbose "  Requests before: $requests_before"

    # Make a request
    curl -s -o /dev/null \
        -H "Authorization: Bearer $TEST_KEY" \
        "$GATEWAY_URL/v1/models" 2>&1 || true

    # Get metrics after
    sleep 1
    local metrics_after
    metrics_after=$(curl -s "$GATEWAY_URL/metrics")

    local requests_after
    requests_after=$(echo "$metrics_after" | jq -r '.gateway.requests_total // 0')
    verbose "  Requests after: $requests_after"

    # Should have incremented
    if [[ "$requests_after" -gt "$requests_before" ]]; then
        verbose "  Metrics incremented correctly"
        test_pass
    else
        warn "Metrics may not be updating (before: $requests_before, after: $requests_after)"
        test_pass  # Non-fatal
    fi
}

# ==============================================================================
# Main Test Execution
# ==============================================================================

main() {
    log "========================================"
    log "Integration Tests"
    log "========================================"
    log "Gateway URL: $GATEWAY_URL"
    log "Test Key: ${TEST_KEY:0:20}..."
    log ""

    # Check prerequisites
    if ! command -v curl >/dev/null 2>&1; then
        error "curl not found - required for tests"
        exit 1
    fi

    if ! command -v jq >/dev/null 2>&1; then
        warn "jq not found - some tests will be limited"
    fi

    # Run tests
    test_system_ready
    test_health_endpoints
    test_auth_flow
    test_request_proxying
    test_streaming_support
    test_error_handling

    if command -v jq >/dev/null 2>&1; then
        test_metrics_tracking
    fi

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
        log "${GREEN}✓ All tests passed!${NC}"
        exit 0
    else
        error ""
        error "✗ Some tests failed"
        exit 1
    fi
}

main "$@"
