# Debugging Guide

Quick reference for debugging llama-gguf-inference deployments.

## Quick Diagnostics

### 1. Check Boot Logs

From a machine with volume access:
```bash
# Latest boot log
cat /workspace/logs/_boot/latest.txt | xargs cat

# Or on RunPod serverless
cat /runpod-volume/logs/_boot/latest.txt | xargs cat
```

### 2. Check Server Logs
```bash
# Latest server log (default LOG_NAME=llama)
cat /workspace/logs/llama/latest.txt | xargs cat
```

### 3. Enable Debug Mode

Set environment variable:
```
DEBUG_SHELL=true
```
Container will print full environment and pause for 5 minutes.

---

## Environment Variables for Debugging

| Variable | Value | Purpose |
|----------|-------|---------|
| `DEBUG_SHELL` | `true` | Hold container, dump env |
| `NGL` | `0` | CPU-only mode (isolate GPU issues) |
| `CTX` | `2048` | Minimal context (reduce memory) |

---

## Common Issues

### "Model file not found"

```bash
# Check exact filename (case-sensitive!)
ls -la /workspace/models/

# Verify MODEL_NAME matches
echo $MODEL_NAME
```

### Out of Memory (OOM)

**Symptoms:** Exit code 137, CUDA OOM errors

**Fix:** Reduce memory usage
```bash
NGL=40      # Fewer GPU layers
CTX=8192    # Smaller context
```

### Server Exits Immediately

**Check the boot log for:**
1. Missing shared libraries (`ldd` output)
2. Invalid arguments
3. Model load errors

**Try CPU mode to isolate:**
```bash
NGL=0
```

### GPU Not Detected

**Check boot log for:**
```
[boot] nvidia-smi output:
# Should show your GPU
```

If missing, verify:
- GPU is allocated to the endpoint/pod
- NVIDIA drivers are loaded

---

## Exit Code Reference

| Code | Signal | Meaning |
|------|--------|---------|
| 0 | - | Normal exit |
| 1 | - | General error |
| 127 | - | Binary not found |
| 134 | SIGABRT | Assertion failure |
| 137 | SIGKILL | OOM / killed |
| 139 | SIGSEGV | Segmentation fault |

---

## Log Locations

| Log | Path |
|-----|------|
| Boot logs | `<volume>/logs/_boot/` |
| Server logs | `<volume>/logs/<LOG_NAME>/` |
| Latest boot | `<volume>/logs/_boot/latest.txt` |
| Latest server | `<volume>/logs/<LOG_NAME>/latest.txt` |

Where `<volume>` is:
- `/runpod-volume` (RunPod serverless)
- `/workspace` (RunPod pods, Vast.ai, etc.)

---

## Health Check Endpoints

| Endpoint | Response | Meaning |
|----------|----------|---------|
| `GET /ping` | 200 | Ready |
| `GET /ping` | 204 | Still loading |
| `GET /health` | JSON | Detailed status |
| `GET /metrics` | JSON | Request stats |

---

## Debugging Workflow

1. **Deploy with defaults** - See if it works at all

2. **If it crashes immediately:**
   - Check boot log
   - Try `NGL=0` (CPU mode)
   - Try `DEBUG_SHELL=true`

3. **If it runs but OOMs:**
   - Reduce `NGL` (e.g., 40 instead of 99)
   - Reduce `CTX` (e.g., 8192 instead of 16384)

4. **If health checks fail:**
   - Check if model is still loading (large models take time)
   - Verify port configuration matches platform expectations

5. **If inference is slow:**
   - Check `NGL` - should be high for GPU acceleration
   - Check boot log for "offloaded X/Y layers to GPU"

---

## Getting More Verbose Output

Add to `EXTRA_ARGS`:
```bash
EXTRA_ARGS="--verbose"
```

This increases llama-server logging detail.
