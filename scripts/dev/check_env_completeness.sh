#!/usr/bin/env bash
# ==============================================================================
# check_env_completeness.sh - Validate environment variable documentation
#
# This script ensures that:
# 1. All env vars used in start.sh are documented in .env.example
# 2. All env vars in .env.example are actually used
# 3. Critical env vars are documented in docs/CONFIGURATION.md
#
# Usage:
#   bash scripts/dev/check_env_completeness.sh
#
# Exit codes:
#   0 - All checks passed
#   1 - Missing or undocumented variables found
# ==============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0

echo "Checking environment variable completeness..."
echo ""

# ==============================================================================
# Check 1: Extract variables from start.sh
# ==============================================================================

if [[ ! -f scripts/start.sh ]]; then
    echo -e "${RED}✗ scripts/start.sh not found${NC}"
    exit 1
fi

# Extract all ${VAR:-default} and $VAR references from start.sh
USED_VARS=$(grep -oE '\$\{?[A-Z_][A-Z0-9_]*' scripts/start.sh | \
    sed 's/\${//g' | sed 's/\$//g' | \
    sort -u)

echo "Variables used in start.sh:"
echo "$USED_VARS" | sed 's/^/  - /'
echo ""

# ==============================================================================
# Check 2: Extract variables from .env.example
# ==============================================================================

if [[ ! -f .env.example ]]; then
    echo -e "${YELLOW}⚠️  .env.example not found${NC}"
    echo "   Create it to document environment variables"
    echo ""
    DOCUMENTED_VARS=""
else
    # Extract variable names from .env.example (lines like VAR=value or VAR=${VAR:-default})
    DOCUMENTED_VARS=$(grep -E '^[A-Z_][A-Z0-9_]*=' .env.example | \
        cut -d '=' -f 1 | \
        sort -u)

    echo "Variables documented in .env.example:"
    echo "$DOCUMENTED_VARS" | sed 's/^/  - /'
    echo ""
fi

# ==============================================================================
# Check 3: Find undocumented variables
# ==============================================================================

UNDOCUMENTED=()
while IFS= read -r var; do
    if [[ -n "$var" ]] && ! echo "$DOCUMENTED_VARS" | grep -qx "$var"; then
        UNDOCUMENTED+=("$var")
    fi
done <<< "$USED_VARS"

if [[ ${#UNDOCUMENTED[@]} -gt 0 ]]; then
    echo -e "${RED}✗ Variables used but not documented in .env.example:${NC}"
    printf '  - %s\n' "${UNDOCUMENTED[@]}"
    echo ""
    ((ERRORS++))
fi

# ==============================================================================
# Check 4: Find unused documented variables
# ==============================================================================

if [[ -n "$DOCUMENTED_VARS" ]]; then
    UNUSED=()
    while IFS= read -r var; do
        if [[ -n "$var" ]] && ! echo "$USED_VARS" | grep -qx "$var"; then
            UNUSED+=("$var")
        fi
    done <<< "$DOCUMENTED_VARS"

    if [[ ${#UNUSED[@]} -gt 0 ]]; then
        echo -e "${YELLOW}⚠️  Variables documented but not used:${NC}"
        printf '  - %s\n' "${UNUSED[@]}"
        echo ""
        echo "   These may be outdated or used elsewhere"
        echo ""
    fi
fi

# ==============================================================================
# Check 5: Verify critical vars in CONFIGURATION.md
# ==============================================================================

CRITICAL_VARS=(
    "MODEL_NAME"
    "MODEL_PATH"
    "DATA_DIR"
    "PORT"
    "PORT_BACKEND"
    "PORT_HEALTH"
    "AUTH_ENABLED"
    "AUTH_KEYS_FILE"
    "NGL"
    "CTX"
)

if [[ -f docs/CONFIGURATION.md ]]; then
    echo "Checking docs/CONFIGURATION.md..."

    MISSING_DOCS=()
    for var in "${CRITICAL_VARS[@]}"; do
        if ! grep -q "\`$var\`" docs/CONFIGURATION.md; then
            MISSING_DOCS+=("$var")
        fi
    done

    if [[ ${#MISSING_DOCS[@]} -gt 0 ]]; then
        echo -e "${RED}✗ Critical variables not documented in docs/CONFIGURATION.md:${NC}"
        printf '  - %s\n' "${MISSING_DOCS[@]}"
        echo ""
        ((ERRORS++))
    else
        echo -e "${GREEN}✓ All critical variables documented${NC}"
        echo ""
    fi
else
    echo -e "${YELLOW}⚠️  docs/CONFIGURATION.md not found${NC}"
    echo ""
fi

# ==============================================================================
# Summary
# ==============================================================================

if [[ $ERRORS -eq 0 ]]; then
    echo -e "${GREEN}✓ All environment variable checks passed${NC}"
    exit 0
else
    echo -e "${RED}✗ Found $ERRORS issue(s) with environment variables${NC}"
    echo ""
    echo "To fix:"
    echo "  1. Add missing variables to .env.example"
    echo "  2. Document critical variables in docs/CONFIGURATION.md"
    echo "  3. Remove or update unused variables"
    echo ""
    exit 1
fi
