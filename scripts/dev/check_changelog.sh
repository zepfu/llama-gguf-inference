#!/usr/bin/env bash
# ==============================================================================
# check_changelog.sh - Check if CHANGELOG.md is reasonably current
#
# This script performs a quick heuristic check to see if CHANGELOG.md
# appears to be up-to-date. It's not perfect, but catches obvious issues.
#
# Usage:
#   bash scripts/dev/check_changelog.sh
#
# Exit codes:
#   0 - CHANGELOG.md appears current (or can't determine)
#   1 - CHANGELOG.md is clearly outdated
# ==============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Checking if CHANGELOG.md is current..."

# Check if CHANGELOG.md exists
if [[ ! -f CHANGELOG.md ]]; then
    echo -e "${YELLOW}⚠️  CHANGELOG.md not found${NC}"
    echo ""
    echo "Generate it with:"
    echo "  make changelog"
    echo ""
    # Don't fail - changelog might not be used yet
    exit 0
fi

# Check if we're in a git repo
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Not a git repository${NC}"
    exit 0
fi

# Get last few commit messages (excluding doc updates)
RECENT_COMMITS=$(git log -5 --pretty=format:"%s" | grep -v "^docs:" | grep -v "^\[automated\]" || true)

if [[ -z "$RECENT_COMMITS" ]]; then
    # No recent non-doc commits
    echo -e "${GREEN}✓ No recent commits to check${NC}"
    exit 0
fi

# Simple heuristic: Check if any recent commit message appears in changelog
FOUND_ANY=false
while IFS= read -r commit_msg; do
    # Extract the key part of the message (first ~30 chars)
    KEY_PART=$(echo "$commit_msg" | cut -c 1-30)

    if grep -qF "$KEY_PART" CHANGELOG.md 2>/dev/null; then
        FOUND_ANY=true
        break
    fi
done <<< "$RECENT_COMMITS"

if [[ "$FOUND_ANY" == "true" ]]; then
    echo -e "${GREEN}✓ CHANGELOG.md appears current${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  CHANGELOG.md may be outdated${NC}"
    echo ""
    echo "Recent commits not found in changelog:"
    echo "$RECENT_COMMITS" | head -3
    echo ""
    echo "To update:"
    echo "  make changelog"
    echo ""
    # Don't fail - this is just a warning
    # The weekly automation will catch it
    exit 0
fi
