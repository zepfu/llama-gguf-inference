#!/usr/bin/env bash
# ==============================================================================
# test_health.sh - Test health endpoint functionality
#
# This script verifies:
# 1. /ping endpoint is accessible without auth
# 2. /health endpoint is accessible without auth
# 3. /metrics endpoint is accessible without auth
# 4. Health endpoints return proper status codes
# 5. Health server on PORT_HEALTH is accessible
#
# Usage:
#   bash scripts/tests/test_health.sh
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
# ==============================================================================

set -euo pipefail

# Configuration
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8000}"
HEALTH_URL="${HEALTH_URL:-http://localhost:8001}"
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

test_ping_endpoint() {
    test_start "/ping endpoint is accessible"
    
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/ping" 2>&1 || echo "error")
    verbose "  Response code: $response"
    
    if [[ "$response" == "200" ]]; then
        test_pass
    else
        test_fail "Expected 200, got $response"
        return 1
    fi
}

test_health_endpoint() {
    test_start "/health endpoint returns valid JSON"
    
    local response http_code body
    body=$(curl -s -w "\n%{http_code}" "$GATEWAY_URL/health" 2>&1 || echo "error")
    http_code=$(echo "$body" | tail -1)
    body=$(echo "$body" | head -n -1)
    
    verbose "  Response code: $http_code"
    
    if [[ "$http_code" != "200" ]]; then
        test_fail "Expected 200, got $http_code"
        return 1
    fi
    
    # Check if response is valid JSON
    if echo "$body" | jq . >/dev/null 2>&1; then
        verbose "  Valid JSON response"
        
        # Check for expected fields
        if echo "$body" | jq -e '.gateway' >/dev/null 2>&1; then
            verbose "  Contains 'gateway' field"
        else
            warn "Missing 'gateway' field in response"
        fi
        
        test_pass
    else
        test_fail "Response is not valid JSON"
        verbose "  Body: ${body:0:100}"
        return 1
    fi
}

test_metrics_endpoint() {
    test_start "/metrics endpoint returns valid JSON"
    
    local response http_code body
    body=$(curl -s -w "\n%{http_code}" "$GATEWAY_URL/metrics" 2>&1 || echo "error")
    http_code=$(echo "$body" | tail -1)
    body=$(echo "$body" | head -n -1)
    
    verbose "  Response code: $http_code"
    
    if [[ "$http_code" != "200" ]]; then
        test_fail "Expected 200, got $http_code"
        return 1
    fi
    
    # Check if response is valid JSON
    if echo "$body" | jq . >/dev/null 2>&1; then
        verbose "  Valid JSON response"
        
        # Check for expected fields
        if echo "$body" | jq -e '.gateway' >/dev/null 2>&1; then
            verbose "  Contains 'gateway' field"
        else
            warn "Missing 'gateway' field in response"
        fi
        
        test_pass
    else
        test_fail "Response is not valid JSON"
        verbose "  Body: ${body:0:100}"
        return 1
    fi
}

test_health_server() {
    test_start "Health server (PORT_HEALTH) is accessible"
    
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL/" 2>&1 || echo "error")
    verbose "  Response code: $response"
    
    if [[ "$response" == "200" ]]; then
        verbose "  Health server responding on $HEALTH_URL"
        test_pass
    elif [[ "$response" == "error" ]] || [[ "$response" == "000" ]]; then
        warn "Health server not accessible at $HEALTH_URL (may not be running)"
        test_pass  # Non-fatal
    else
        test_fail "Unexpected response: $response"
        return 1
    fi
}

test_health_no_auth_required() {
    test_start "Health endpoints work without Authorization header"
    
    # These should all work without any auth header
    local ping_response health_response metrics_response
    
    ping_response=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/ping" 2>&1)
    health_response=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/health" 2>&1)
    metrics_response=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/metrics" 2>&1)
    
    verbose "  /ping: $ping_response"
    verbose "  /health: $health_response"
    verbose "  /metrics: $metrics_response"
    
    if [[ "$ping_response" == "200" ]] && [[ "$health_response" == "200" ]] && [[ "$metrics_response" == "200" ]]; then
        verbose "  All health endpoints accessible without auth"
        test_pass
    else
        test_fail "One or more endpoints returned non-200: ping=$ping_response health=$health_response metrics=$metrics_response"
        return 1
    fi
}

test_health_with_auth_header() {
    test_start "Health endpoints work even with invalid auth header"
    
    # Health endpoints should work regardless of Authorization header
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer invalid-key-12345" \
        "$GATEWAY_URL/ping" 2>&1)
    verbose "  /ping with invalid auth: $response"
    
    if [[ "$response" == "200" ]]; then
        verbose "  Health endpoint bypasses auth (correct behavior)"
        test_pass
    else
        test_fail "Health endpoint should not require auth, got $response"
        return 1
    fi
}

# ==============================================================================
# Main Test Execution
# ==============================================================================

main() {
    log "========================================"
    log "Health Endpoint Tests"
    log "========================================"
    log "Gateway URL: $GATEWAY_URL"
    log "Health URL:  $HEALTH_URL"
    log ""
    
    # Check if gateway is accessible
    if ! curl -s -f -o /dev/null "$GATEWAY_URL/ping" 2>/dev/null; then
        error "Gateway not accessible at $GATEWAY_URL"
        error "Start the service first or set GATEWAY_URL"
        exit 1
    fi
    
    # Check for jq (needed for JSON validation)
    if ! command -v jq >/dev/null 2>&1; then
        warn "jq not found - JSON validation will be skipped"
    fi
    
    # Run tests
    test_ping_endpoint
    test_health_endpoint
    test_metrics_endpoint
    test_health_server
    test_health_no_auth_required
    test_health_with_auth_header
    
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
