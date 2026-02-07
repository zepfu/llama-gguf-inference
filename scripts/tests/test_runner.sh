#!/usr/bin/env bash
# Test runner - orchestrates all tests

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASSED=0
FAILED=0

run_test() {
    local test_script="$1"
    local test_name="$2"

    echo "Running: $test_name..."
    if bash "$test_script"; then
        echo -e "${GREEN}✓ $test_name passed${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ $test_name failed${NC}"
        ((FAILED++))
    fi
    echo ""
}

echo "=========================================="
echo "Test Suite"
echo "=========================================="
echo ""

# Run existing tests
if [[ -f "scripts/tests/test_auth.sh" ]]; then
    run_test "scripts/tests/test_auth.sh" "Authentication Tests"
fi

if [[ -f "scripts/tests/test_health.sh" ]]; then
    run_test "scripts/tests/test_health.sh" "Health Endpoint Tests"
fi

# Docker tests (optional)
if [[ "${DOCKER_TEST:-false}" == "true" ]] && [[ -f "scripts/tests/test_docker_integration.sh" ]]; then
    run_test "scripts/tests/test_docker_integration.sh" "Docker Integration Tests"
fi

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
