# Diagnostics

Tools for collecting debugging information when troubleshooting llama-gguf-inference.

## Quick Start

```bash
# Collect diagnostics
bash scripts/diagnostics/collect.sh

# Or via Makefile
make diagnostics
```

## What Gets Collected

The diagnostic script collects:

### System Information
- Operating system and kernel version
- CPU information (cores, model)
- Memory usage (total, used, available)
- Disk space
- GPU information (if available via nvidia-smi)

### Environment Variables
- All environment variables (sensitive values filtered)
- Configuration values
- Paths and settings

### Process Information
- All running processes
- llama-server process details
- Python processes (gateway, health server)
- Network port listeners

### Model Information
- Model file location and size
- Model file type
- Directory contents

### Health Status
- Gateway health check results
- llama-server health check results
- Port accessibility

### Recent Logs
- Last 500 lines of boot log
- Last 500 lines of server log
- Last 500 lines of access log (if exists)

### Error Extraction
- Extracted errors from all logs
- Fatal messages
- Failure indicators

### Configuration Files
- Copy of main scripts (start.sh, gateway.py, etc.)

## Output Structure

```
/tmp/llama-diagnostics-YYYYMMDD_HHMMSS/
├── SUMMARY.txt              # Quick overview
├── system_info.txt          # System resources
├── environment.txt          # Environment variables
├── processes.txt            # Running processes
├── model_info.txt           # Model file info
├── container_info.txt       # Container/Docker info
├── health_status.txt        # Health check results
├── errors.txt               # Extracted errors
├── logs/
│   ├── boot_recent.log      # Last 500 lines of boot
│   ├── server_recent.log    # Last 500 lines of server
│   └── access_recent.log    # Last 500 lines of access
└── config/
    ├── start.sh             # Copy of start script
    ├── gateway.py           # Copy of gateway
    └── ...                  # Other scripts

/tmp/llama-diagnostics-YYYYMMDD_HHMMSS.tar.gz  # Compressed version
```

## Usage Examples

### Basic Collection

```bash
bash scripts/diagnostics/collect.sh
```

Output goes to `/tmp/llama-diagnostics-YYYYMMDD_HHMMSS/`

### Custom Output Directory

```bash
bash scripts/diagnostics/collect.sh /path/to/output
```

### Via Makefile

```bash
make diagnostics
```

### From Container

```bash
# If running in Docker
docker exec <container-id> bash scripts/diagnostics/collect.sh

# Copy out of container
docker cp <container-id>:/tmp/llama-diagnostics-YYYYMMDD_HHMMSS.tar.gz .
```

## Reviewing Diagnostics

### Quick Summary

```bash
cat /tmp/llama-diagnostics-*/SUMMARY.txt
```

Shows:
- System overview
- Service status
- Model configuration
- Error count

### Check for Errors

```bash
cat /tmp/llama-diagnostics-*/errors.txt
```

Shows extracted errors from all logs.

### Review Specific Information

```bash
# System resources
cat /tmp/llama-diagnostics-*/system_info.txt

# Environment
cat /tmp/llama-diagnostics-*/environment.txt

# Process list
cat /tmp/llama-diagnostics-*/processes.txt

# Health checks
cat /tmp/llama-diagnostics-*/health_status.txt
```

## Sharing Diagnostics

### Compressed File

The script automatically creates a `.tar.gz` file:

```bash
# Find the tarball
ls -lh /tmp/llama-diagnostics-*.tar.gz

# It's usually small (< 2 MB)
```

### Review Before Sharing

**Always review diagnostics before sharing publicly:**

1. Check `environment.txt` for sensitive values
2. Check logs for API keys or tokens
3. Verify no customer data in logs

The script filters common sensitive variable names, but always verify.

### Sharing Safely

```bash
# Review contents first
tar -tzf diagnostics.tar.gz

# Extract and review
tar -xzf diagnostics.tar.gz
cat llama-diagnostics-*/SUMMARY.txt
cat llama-diagnostics-*/errors.txt

# If safe, share the tarball
```

## Common Issues

### Issue: Out of Memory

**Check:**
```bash
cat diagnostics/system_info.txt | grep -A 5 "Memory"
cat diagnostics/system_info.txt | grep -A 10 "GPU"
```

**Look for:**
- Low available RAM
- High GPU memory usage
- OOM errors in logs

### Issue: Model Not Found

**Check:**
```bash
cat diagnostics/model_info.txt
cat diagnostics/environment.txt | grep MODEL
```

**Look for:**
- MODEL_NAME or MODEL_PATH set correctly
- File exists in models directory
- File permissions

### Issue: Port Conflicts

**Check:**
```bash
cat diagnostics/processes.txt | grep LISTEN
cat diagnostics/health_status.txt
```

**Look for:**
- Duplicate port listeners
- Connection refused errors
- Port mismatch between components

### Issue: GPU Not Detected

**Check:**
```bash
cat diagnostics/system_info.txt | grep -A 20 "GPU"
```

**Look for:**
- "nvidia-smi not available"
- GPU name and memory
- Driver version

### Issue: Services Not Starting

**Check:**
```bash
cat diagnostics/processes.txt
cat diagnostics/errors.txt
cat diagnostics/logs/boot_recent.log
```

**Look for:**
- Missing processes
- Exit codes in boot log
- Error messages

## Automated Collection

### On Failure

Add to `start.sh` or service:

```bash
on_error() {
    echo "Failure detected, collecting diagnostics..."
    bash scripts/diagnostics/collect.sh /tmp/failure-diagnostics
}

trap on_error ERR
```

### Periodic Collection

```bash
# Cron job (every hour)
0 * * * * cd /path/to/project && bash scripts/diagnostics/collect.sh /tmp/diagnostics-$(date +\%H)
```

### On Signal

```bash
# Collect on SIGUSR1
trap 'bash scripts/diagnostics/collect.sh' USR1

# Then send signal:
kill -USR1 <pid>
```

## What's NOT Collected

To keep diagnostic files small and fast:

- ❌ Full log history (only last 500 lines)
- ❌ Model files (only metadata)
- ❌ Large binary files
- ❌ Build artifacts
- ❌ Complete source code

## Privacy Considerations

The script attempts to filter:

- API keys (KEY, TOKEN, SECRET patterns)
- Passwords
- Auth tokens

But always review before sharing:

```bash
# Check for sensitive data
grep -i "key\|password\|token\|secret" diagnostics.tar.gz
```

## Troubleshooting the Diagnostic Script

### Script Fails to Run

```bash
# Check permissions
ls -la scripts/diagnostics/collect.sh
# Should be executable

# Fix
chmod +x scripts/diagnostics/collect.sh
```

### Missing Commands

Some commands may not be available in minimal containers:

- `lscpu` - CPU info (fallback: OK)
- `free` - Memory info (fallback: OK)
- `nvidia-smi` - GPU info (fallback: OK)
- `netstat` / `ss` - Port info (fallback: OK)

Script will note "not available" and continue.

### Permission Errors

```bash
# If can't write to /tmp
bash scripts/diagnostics/collect.sh /data/diagnostics

# If can't read logs
sudo bash scripts/diagnostics/collect.sh
```

## Size Estimates

Typical sizes:

| Component | Size |
|-----------|------|
| System info | ~10 KB |
| Logs (500 lines each) | ~100 KB |
| Config files | ~50 KB |
| Total uncompressed | ~200 KB - 1 MB |
| Compressed (tar.gz) | ~50 KB - 500 KB |

Very reasonable for sharing or uploading.

## Integration

### CI/CD

```yaml
# GitHub Actions
- name: Collect diagnostics on failure
  if: failure()
  run: |
    bash scripts/diagnostics/collect.sh

- name: Upload diagnostics
  if: failure()
  uses: actions/upload-artifact@v3
  with:
    name: diagnostics
    path: /tmp/llama-diagnostics-*
```

### Monitoring

Send diagnostics to monitoring system:

```bash
# Collect and upload
bash scripts/diagnostics/collect.sh
curl -F "file=@/tmp/llama-diagnostics-*.tar.gz" https://monitoring.example.com/upload
```

## See Also

- [DEBUGGING.md](../../DEBUGGING.md) - General debugging guide
- [TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md) - Common issues
- [CONFIGURATION.md](../../docs/CONFIGURATION.md) - Configuration reference
