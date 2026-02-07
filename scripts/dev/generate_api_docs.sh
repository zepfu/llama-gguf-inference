#!/usr/bin/env bash
# ==============================================================================
# generate_api_docs.sh - Generate API documentation using Sphinx
#
# This script generates HTML API documentation from Python docstrings.
#
# Usage:
#   bash scripts/dev/generate_api_docs.sh
#
# Requirements:
#   pip install sphinx sphinx-rtd-theme
# ==============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "========================================"
echo "Generating API Documentation"
echo "========================================"
echo ""

# Check if Sphinx is installed
if ! command -v sphinx-build >/dev/null 2>&1; then
    echo -e "${RED}✗ Sphinx not installed${NC}"
    echo ""
    echo "Install with:"
    echo "  pip install sphinx sphinx-rtd-theme"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Sphinx found${NC}"

# Check if docs/conf.py exists
if [[ ! -f docs/conf.py ]]; then
    echo -e "${YELLOW}⚠️  docs/conf.py not found${NC}"
    echo ""
    echo "Creating basic Sphinx configuration..."

    mkdir -p docs

    cat > docs/conf.py << 'CONFEOF'
# Configuration file for Sphinx documentation

import os
import sys

# Add scripts directory to path
sys.path.insert(0, os.path.abspath('../scripts'))

# Project information
project = 'llama-gguf-inference'
copyright = '2024, llama-gguf-inference contributors'
author = 'llama-gguf-inference contributors'

# Extensions
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]

# HTML theme
html_theme = 'sphinx_rtd_theme'

# Output options
html_static_path = []
templates_path = []
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
CONFEOF

    echo -e "${GREEN}✓ Created docs/conf.py${NC}"
fi

# Create index.rst if it doesn't exist
if [[ ! -f docs/index.rst ]]; then
    echo "Creating docs/index.rst..."

    cat > docs/index.rst << 'RSTEOF'
llama-gguf-inference API Documentation
======================================

Welcome to the API documentation for llama-gguf-inference.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   gateway
   auth
   health_server

Gateway Module
==============

.. automodule:: gateway
   :members:
   :undoc-members:
   :show-inheritance:

Authentication Module
=====================

.. automodule:: auth
   :members:
   :undoc-members:
   :show-inheritance:

Health Server Module
====================

.. automodule:: health_server
   :members:
   :undoc-members:
   :show-inheritance:

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
RSTEOF

    echo -e "${GREEN}✓ Created docs/index.rst${NC}"
fi

# Build the documentation
echo ""
echo "Building HTML documentation..."

# Clean previous build
rm -rf docs/_build 2>/dev/null || true

# Build
if sphinx-build -b html docs docs/_build/html; then
    echo ""
    echo -e "${GREEN}✓ Documentation built successfully${NC}"
    echo ""
    echo "Output: docs/_build/html/"
    echo ""
    echo "To view:"
    echo "  open docs/_build/html/index.html"
    echo ""
    echo "Or serve locally:"
    echo "  cd docs/_build/html && python3 -m http.server 8080"
    echo ""
else
    echo ""
    echo -e "${RED}✗ Documentation build failed${NC}"
    echo ""
    echo "Check that:"
    echo "  1. Python files have proper docstrings"
    echo "  2. No syntax errors in Python files"
    echo "  3. Sphinx extensions are installed"
    echo ""
    exit 1
fi
