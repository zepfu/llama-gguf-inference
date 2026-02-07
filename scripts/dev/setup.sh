#!/usr/bin/env bash
# ==============================================================================
# setup.sh - One-command development environment setup
#
# This script sets up everything needed for local development:
# - Installs pre-commit hooks
# - Sets executable permissions on scripts
# - Validates environment
# - Creates necessary directories
#
# Usage:
#   bash scripts/dev/setup.sh
# ==============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Development Environment Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ==============================================================================
# Check Python
# ==============================================================================

echo "Checking Python..."
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Python 3 not found${NC}"
    echo "   Please install Python 3.11 or later"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
echo ""

# ==============================================================================
# Install pre-commit
# ==============================================================================

echo "Installing pre-commit..."
if command -v pre-commit >/dev/null 2>&1; then
    echo -e "${GREEN}✓ pre-commit already installed${NC}"
else
    pip install pre-commit
    echo -e "${GREEN}✓ pre-commit installed${NC}"
fi
echo ""

# ==============================================================================
# Install pre-commit hooks
# ==============================================================================

echo "Installing pre-commit hooks..."
pre-commit install --hook-type pre-commit --hook-type pre-push
echo -e "${GREEN}✓ Hooks installed${NC}"
echo ""

# ==============================================================================
# Set executable permissions
# ==============================================================================

echo "Setting executable permissions..."
find scripts -type f -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
find scripts -type f -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
echo -e "${GREEN}✓ Permissions set${NC}"
echo ""

# ==============================================================================
# Create directories
# ==============================================================================

echo "Creating directories..."
mkdir -p data/models data/logs scripts/tests/fixtures
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# ==============================================================================
# Validate configuration files
# ==============================================================================

echo "Validating configuration..."

REQUIRED_FILES=(
    ".pre-commit-config.yaml"
    ".flake8"
    ".editorconfig"
    "Makefile"
)

MISSING=()
for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        MISSING+=("$file")
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo -e "${YELLOW}⚠️  Missing configuration files:${NC}"
    printf '  - %s\n' "${MISSING[@]}"
    echo ""
    echo "Run: make sync-configs"
    echo ""
else
    echo -e "${GREEN}✓ All configuration files present${NC}"
    echo ""
fi

# ==============================================================================
# Test pre-commit
# ==============================================================================

echo "Testing pre-commit setup..."
if pre-commit run --all-files 2>&1 | grep -q "Passed\|Skipped"; then
    echo -e "${GREEN}✓ Pre-commit working${NC}"
else
    echo -e "${YELLOW}⚠️  Some pre-commit checks failed (this is normal for first run)${NC}"
    echo "   Run: make check"
fi
echo ""

# ==============================================================================
# Summary
# ==============================================================================

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Setup complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Review available commands: make help"
echo "  2. Run tests: make test"
echo "  3. Generate docs: make docs"
echo ""
echo "Common commands:"
echo "  make test      - Run all tests"
echo "  make check     - Run pre-commit checks"
echo "  make docs      - Update documentation"
echo "  make build     - Build Docker image"
echo ""
