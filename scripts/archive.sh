#!/bin/bash

# Get the script's directory and repo name
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
REPO_NAME="$(basename "$REPO_ROOT")"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d%H%M%S)

# Output file (one directory up from repo root)
OUTPUT_FILE="${REPO_ROOT}/../${REPO_NAME}_${TIMESTAMP}.tar.gz"

echo "Creating archive: $OUTPUT_FILE"
echo "From directory: $REPO_ROOT"

# Create tar.gz excluding unnecessary files
cd "$REPO_ROOT" || exit 1

tar -czf "$OUTPUT_FILE" \
  --exclude="*.pyc" \
  --exclude="__pycache__" \
  --exclude="*.egg-info" \
  --exclude=".pytest_cache" \
  --exclude="venv" \
  --exclude=".venv" \
  --exclude=".git" \
  --exclude="dist" \
  --exclude="build" \
  --exclude=".vscode" \
  --exclude=".idea" \
  --exclude="*.swp" \
  --exclude="*~" \
  --exclude="*.bak" \
  --exclude="*.backup" \
  --exclude="*:Zone.Identifier" \
  --exclude="docs/_build" \
  --exclude=".DS_Store" \
  .

if [ $? -eq 0 ]; then
  echo "? Archive created successfully: $OUTPUT_FILE"
  # Show size
  ls -lh "$OUTPUT_FILE" | awk '{print "  Size:", $5}'
else
  echo "? Error creating archive"
  exit 1
fi
