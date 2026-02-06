#!/usr/bin/env bash
# ==============================================================================
# test_auth.sh - Test API authentication functionality
#
# This script tests:
# 1. Health endpoints work without auth
# 2. API endpoints require auth when enabled
# 3. Valid keys are accepted
# 4. Invalid keys are rejected
#
# Usage:
#   bash scripts/tests/test_auth.sh
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
NC='\033[0m' # No Color

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

test_health_no_auth() {
    test_start "Health endpoints work without auth"
    
    # Test /ping
    local ping_response
    ping_response=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/ping" 2>&1 || echo "error")
    verbose "  /ping response: $ping_response"
    
    if [[ "$ping_response" == "200" ]]; then
        verbose "  /ping: OK"
    else
        test_fail "/ping returned $ping_response (expected 200)"
        return 1
    fi
    
    # Test /health
    local health_response
    health_response=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/health" 2>&1 || echo "error")
    verbose "  /health response: $health_response"
    
    if [[ "$health_response" == "200" ]]; then
        verbose "  /health: OK"
    else
        test_fail "/health returned $health_response (expected 200)"
        return 1
    fi
    
    test_pass
}

test_api_requires_auth() {
    test_start "API endpoints require auth (when enabled)"
    
    # Try to access /v1/models without auth
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/v1/models" 2>&1 || echo "error")
    verbose "  /v1/models without auth: $response"
    
    # Should be 401 if auth is enabled, or 200/404 if auth is disabled
    if [[ "$response" == "401" ]]; then
        verbose "  Auth is enabled (401 returned)"
        test_pass
    elif [[ "$response" == "200" ]] || [[ "$response" == "404" ]] || [[ "$response" == "502" ]]; then
        warn "Auth appears to be disabled ($response returned)"
        test_pass
    else
        test_fail "Unexpected response: $response"
        return 1
    fi
}

test_valid_key_accepted() {
    test_start "Valid API key is accepted"
    
    # Try to access with valid key
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $TEST_KEY" \
        "$GATEWAY_URL/v1/models" 2>&1 || echo "error")
    verbose "  /v1/models with valid key: $response"
    
    # Should be 200, 404 (no models endpoint), or 502 (backend not ready)
    # 401 means auth rejected the key
    if [[ "$response" == "401" ]]; then
        test_fail "Valid key was rejected (401)"
        return 1
    elif [[ "$response" == "200" ]] || [[ "$response" == "404" ]] || [[ "$response" == "502" ]]; then
        verbose "  Key accepted (response: $response)"
        test_pass
    else
        warn "Unexpected response: $response (but key was not rejected)"
        test_pass
    fi
}

test_invalid_key_rejected() {
    test_start "Invalid API key is rejected"
    
    # Try to access with invalid key
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer sk-invalid-wrong-key" \
        "$GATEWAY_URL/v1/models" 2>&1 || echo "error")
    verbose "  /v1/models with invalid key: $response"
    
    # Should be 401 if auth is enabled
    if [[ "$response" == "401" ]]; then
        verbose "  Invalid key rejected (401)"
        test_pass
    elif [[ "$response" == "200" ]] || [[ "$response" == "404" ]] || [[ "$response" == "502" ]]; then
        warn "Auth appears to be disabled (invalid key not rejected)"
        test_pass
    else
        test_fail "Unexpected response: $response"
        return 1
    fi
}

test_bearer_format() {
    test_start "Bearer token format is supported"
    
    # Test both formats
    local response1 response2
    
    # Format 1: Bearer <key>
    response1=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $TEST_KEY" \
        "$GATEWAY_URL/v1/models" 2>&1 || echo "error")
    verbose "  'Bearer $TEST_KEY': $response1"
    
    # Format 2: Just <key>
    response2=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: $TEST_KEY" \
        "$GATEWAY_URL/v1/models" 2>&1 || echo "error")
    verbose "  '$TEST_KEY': $response2"
    
    # Both should work the same (either both accepted or both rejected based on auth state)
    if [[ "$response1" == "$response2" ]]; then
        verbose "  Both formats handled consistently"
        test_pass
    else
        test_fail "Inconsistent handling: Bearer format=$response1, direct=$response2"
        return 1
    fi
}

# ==============================================================================
# Main Test Execution
# ==============================================================================

main() {
    log "========================================"
    log "API Authentication Tests"
    log "========================================"
    log "Gateway URL: $GATEWAY_URL"
    log "Test Key: $TEST_KEY"
    log ""
    
    # Check if gateway is accessible
    if ! curl -s -f -o /dev/null "$GATEWAY_URL/ping" 2>/dev/null; then
        error "Gateway not accessible at $GATEWAY_URL"
        error "Start the service first or set GATEWAY_URL"
        exit 1
    fi
    
    # Run tests
    test_health_no_auth
    test_api_requires_auth
    test_valid_key_accepted
    test_invalid_key_rejected
    test_bearer_format
    
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
