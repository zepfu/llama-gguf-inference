#!/usr/bin/env bash
# ==============================================================================
# collect.sh - Collect diagnostic information for troubleshooting
#
# This script collects relevant diagnostic information including:
# - System information (CPU, RAM, GPU)
# - Environment variables (sanitized)
# - Recent logs (last 500 lines)
# - Process information
# - Model information
# - Health check status
#
# Usage:
#   bash scripts/diagnostics/collect.sh [output_dir]
#
# Output:
#   /tmp/llama-diagnostics-YYYYMMDD_HHMMSS/
#   /tmp/llama-diagnostics-YYYYMMDD_HHMMSS.tar.gz
# ==============================================================================

set -euo pipefail

# Configuration
OUTPUT_DIR="${1:-/tmp/llama-diagnostics-$(date +%Y%m%d_%H%M%S)}"
DATA_DIR="${DATA_DIR:-/data}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "Diagnostic Information Collection"
echo "========================================"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR/logs"
mkdir -p "$OUTPUT_DIR/config"

# ==============================================================================
# System Information
# ==============================================================================

echo "Collecting system information..."
cat > "$OUTPUT_DIR/system_info.txt" << EOF
System Diagnostics - $(date)
======================================

# Hostname
$(hostname)

# Operating System
$(cat /etc/os-release 2>/dev/null || echo "Not available")

# Kernel
$(uname -a)

# CPU Information
$(lscpu 2>/dev/null || echo "lscpu not available")

# Memory
$(free -h 2>/dev/null || echo "free not available")

# Disk Space
$(df -h 2>/dev/null || echo "df not available")

# GPU Information
$(nvidia-smi 2>/dev/null || echo "nvidia-smi not available (no GPU or driver)")

EOF

# ==============================================================================
# Environment Variables
# ==============================================================================

echo "Collecting environment variables..."
cat > "$OUTPUT_DIR/environment.txt" << EOF
Environment Variables
======================================

# Sanitized environment (secrets removed)
$(env | grep -v -i "key\|password\|token\|secret" | sort)

EOF

# ==============================================================================
# Process Information
# ==============================================================================

echo "Collecting process information..."
cat > "$OUTPUT_DIR/processes.txt" << EOF
Running Processes
======================================

# All processes
$(ps aux 2>/dev/null || echo "ps not available")

# llama-server process
$(ps aux | grep llama-server | grep -v grep || echo "llama-server not running")

# Python processes (gateway, health server)
$(ps aux | grep python | grep -v grep || echo "No Python processes")

# Port listeners
$(netstat -tlnp 2>/dev/null || ss -tlnp 2>/dev/null || echo "netstat/ss not available")

EOF

# ==============================================================================
# Model Information
# ==============================================================================

echo "Collecting model information..."
cat > "$OUTPUT_DIR/model_info.txt" << EOF
Model Information
======================================

# Models directory
$(ls -lh "$DATA_DIR/models/" 2>/dev/null || echo "Models directory not found")

# Current model (from environment)
MODEL_NAME: ${MODEL_NAME:-not set}
MODEL_PATH: ${MODEL_PATH:-not set}

# Model file info (if exists)
$(if [[ -n "${MODEL_NAME:-}" ]] && [[ -f "$DATA_DIR/models/$MODEL_NAME" ]]; then
    ls -lh "$DATA_DIR/models/$MODEL_NAME"
    file "$DATA_DIR/models/$MODEL_NAME"
elif [[ -n "${MODEL_PATH:-}" ]] && [[ -f "$MODEL_PATH" ]]; then
    ls -lh "$MODEL_PATH"
    file "$MODEL_PATH"
else
    echo "Model file not found"
fi)

EOF

# ==============================================================================
# Container/Docker Information
# ==============================================================================

echo "Collecting container information..."
cat > "$OUTPUT_DIR/container_info.txt" << EOF
Container Information
======================================

# Check if running in container
$(if [[ -f /.dockerenv ]]; then
    echo "Running in Docker container"
elif [[ -f /run/.containerenv ]]; then
    echo "Running in Podman container"
else
    echo "Not running in container"
fi)

# Container ID (if available)
$(cat /proc/self/cgroup 2>/dev/null | grep -o -E '[0-9a-f]{64}' | head -1 || echo "N/A")

# Hostname
$(hostname)

EOF

# ==============================================================================
# Health Check Status
# ==============================================================================

echo "Collecting health check status..."
cat > "$OUTPUT_DIR/health_status.txt" << EOF
Health Check Status
======================================

# Gateway health endpoint
$(curl -s http://localhost:${PORT:-8000}/health 2>&1 || echo "Gateway not accessible")

# Gateway ping endpoint
$(curl -s -o /dev/null -w "Status: %{http_code}" http://localhost:${PORT:-8000}/ping 2>&1 || echo "Gateway ping not accessible")

# Health server (if separate port)
$(curl -s -o /dev/null -w "Status: %{http_code}" http://localhost:${PORT_HEALTH:-8001}/ 2>&1 || echo "Health server not accessible")

# llama-server health
$(curl -s http://localhost:${PORT_BACKEND:-8080}/health 2>&1 || echo "llama-server not accessible")

EOF

# ==============================================================================
# Recent Logs
# ==============================================================================

echo "Collecting recent logs..."

# Boot log
if [[ -f "$DATA_DIR/logs/_boot/latest.txt" ]]; then
    BOOT_LOG=$(cat "$DATA_DIR/logs/_boot/latest.txt" 2>/dev/null || echo "")
    if [[ -n "$BOOT_LOG" ]] && [[ -f "$BOOT_LOG" ]]; then
        echo "Boot log: $BOOT_LOG"
        tail -500 "$BOOT_LOG" > "$OUTPUT_DIR/logs/boot_recent.log" 2>/dev/null || echo "Could not read boot log"
    fi
fi

# Server log
if [[ -f "$DATA_DIR/logs/llama/latest.txt" ]]; then
    SERVER_LOG=$(cat "$DATA_DIR/logs/llama/latest.txt" 2>/dev/null || echo "")
    if [[ -n "$SERVER_LOG" ]] && [[ -f "$SERVER_LOG" ]]; then
        echo "Server log: $SERVER_LOG"
        tail -500 "$SERVER_LOG" > "$OUTPUT_DIR/logs/server_recent.log" 2>/dev/null || echo "Could not read server log"
    fi
fi

# Access log (if exists)
if [[ -f "$DATA_DIR/logs/api_access.log" ]]; then
    echo "Access log found"
    tail -500 "$DATA_DIR/logs/api_access.log" > "$OUTPUT_DIR/logs/access_recent.log" 2>/dev/null || echo "Could not read access log"
fi

# ==============================================================================
# Configuration Files
# ==============================================================================

echo "Collecting configuration files..."

# Copy important config files (if they exist)
for file in start.sh gateway.py auth.py health_server.py; do
    if [[ -f "scripts/$file" ]]; then
        cp "scripts/$file" "$OUTPUT_DIR/config/" 2>/dev/null || true
    elif [[ -f "/opt/app/scripts/$file" ]]; then
        cp "/opt/app/scripts/$file" "$OUTPUT_DIR/config/" 2>/dev/null || true
    fi
done

# ==============================================================================
# Error Extraction
# ==============================================================================

echo "Extracting errors from logs..."
cat > "$OUTPUT_DIR/errors.txt" << EOF
Recent Errors
======================================

EOF

# Extract errors from boot log
if [[ -f "$OUTPUT_DIR/logs/boot_recent.log" ]]; then
    echo "# Boot Log Errors" >> "$OUTPUT_DIR/errors.txt"
    grep -i "error\|fatal\|fail" "$OUTPUT_DIR/logs/boot_recent.log" | tail -20 >> "$OUTPUT_DIR/errors.txt" 2>/dev/null || echo "No errors found" >> "$OUTPUT_DIR/errors.txt"
    echo "" >> "$OUTPUT_DIR/errors.txt"
fi

# Extract errors from server log
if [[ -f "$OUTPUT_DIR/logs/server_recent.log" ]]; then
    echo "# Server Log Errors" >> "$OUTPUT_DIR/errors.txt"
    grep -i "error\|fatal\|fail" "$OUTPUT_DIR/logs/server_recent.log" | tail -20 >> "$OUTPUT_DIR/errors.txt" 2>/dev/null || echo "No errors found" >> "$OUTPUT_DIR/errors.txt"
    echo "" >> "$OUTPUT_DIR/errors.txt"
fi

# ==============================================================================
# Summary
# ==============================================================================

echo "Generating summary..."
cat > "$OUTPUT_DIR/SUMMARY.txt" << EOF
Diagnostic Summary
======================================
Generated: $(date)
Output Directory: $OUTPUT_DIR

Quick Overview:
---------------

System:
$(uname -s) $(uname -r)

Memory:
$(free -h 2>/dev/null | grep Mem | awk '{print $2 " total, " $3 " used, " $4 " free"}' || echo "Not available")

GPU:
$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "Not available")

Model:
${MODEL_NAME:-${MODEL_PATH:-Not set}}

Ports:
Gateway: ${PORT:-8000}
Health: ${PORT_HEALTH:-8001}
Backend: ${PORT_BACKEND:-8080}

Services Status:
$(ps aux | grep -E "llama-server|gateway.py|health_server.py" | grep -v grep | wc -l) processes running

Recent Errors:
$(wc -l < "$OUTPUT_DIR/errors.txt") error lines found

Files Collected:
---------------
$(ls -1 "$OUTPUT_DIR")

To share diagnostics:
--------------------
tar -czf diagnostics.tar.gz -C $(dirname "$OUTPUT_DIR") $(basename "$OUTPUT_DIR")

EOF

# ==============================================================================
# Compress
# ==============================================================================

echo ""
echo "Compressing diagnostics..."
TARBALL="$OUTPUT_DIR.tar.gz"
tar -czf "$TARBALL" -C "$(dirname "$OUTPUT_DIR")" "$(basename "$OUTPUT_DIR")" 2>/dev/null

# ==============================================================================
# Complete
# ==============================================================================

echo ""
echo "========================================"
echo -e "${GREEN}✓ Diagnostics collected${NC}"
echo "========================================"
echo ""
echo "Output directory: $OUTPUT_DIR"
echo "Compressed file:  $TARBALL"
echo ""
echo "Files collected:"
ls -lh "$OUTPUT_DIR" | tail -n +2
echo ""
echo "Size:"
du -sh "$OUTPUT_DIR"
du -sh "$TARBALL"
echo ""
echo "To review:"
echo "  cat $OUTPUT_DIR/SUMMARY.txt"
echo "  cat $OUTPUT_DIR/errors.txt"
echo ""
echo "To share:"
echo "  Send $TARBALL"
echo ""
