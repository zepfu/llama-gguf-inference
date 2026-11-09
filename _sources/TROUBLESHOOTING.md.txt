# Troubleshooting Guide

Common issues and solutions for llama-gguf-inference.

## Quick Diagnostics

### Check boot logs

```bash
# Find the latest boot log
cat $DATA_DIR/logs/_boot/latest.txt | xargs cat

# Or on RunPod/Vast.ai:
cat /workspace/logs/_boot/latest.txt | xargs cat
```

### Check server logs

```bash
cat $DATA_DIR/logs/llama/latest.txt | xargs cat
```

### Enable debug mode

```bash
DEBUG_SHELL=true
```

Container will pause for 5 minutes, printing environment info.

______________________________________________________________________

## Common Issues

### Model Not Found

**Symptom:**

```
FATAL: Model file not found: /data/models/my-model.gguf
```

**Solutions:**

1. **Check exact filename** (case-sensitive):

   ```bash
   ls -la $DATA_DIR/models/
   ```

1. **Verify DATA_DIR is correct:**

   ```bash
   echo $DATA_DIR
   # Check if it matches your mount
   ```

1. **Check mount is working:**

   ```bash
   # Local Docker
   docker run -v /path/to/models:/data/models ...

   # Should see your files at /data/models/
   ```

1. **Using MODEL_PATH instead:**

   ```bash
   MODEL_PATH=/absolute/path/to/model.gguf
   ```

______________________________________________________________________

### Out of Memory (OOM)

**Symptom:**

- Exit code 137 (SIGKILL)
- "CUDA out of memory" in logs
- Server crashes during model load

**Solutions:**

1. **Reduce GPU layers:**

   ```bash
   NGL=40  # Instead of 99
   ```

1. **Reduce context length:**

   ```bash
   CTX=8192  # Instead of 16384
   ```

1. **Use smaller quantization:**

   - Q8_0 → Q6_K → Q5_K_M → Q4_K_M → Q4_K_S → Q3_K_M

1. **Check VRAM usage** (from boot log):

   ```
   load_tensors: CUDA0 model buffer size = 20730.50 MiB
   llama_kv_cache: CUDA0 KV buffer size = 384.00 MiB
   ```

**Memory guide for RTX 4090 (24GB):**

| Model  | Max NGL | Max CTX |
| ------ | ------- | ------- |
| 7B Q4  | 99      | 32768   |
| 13B Q4 | 99      | 16384   |
| 30B Q4 | 99      | 16384   |
| 70B Q4 | 35      | 8192    |

______________________________________________________________________

### Server Exits Immediately

**Symptom:**

```
FATAL: llama-server failed to start
Exit code: 1
```

**Diagnosis:**

1. **Check for missing libraries:**

   ```bash
   # In boot log, look for "not found" in ldd output
   ```

1. **Check for argument errors:**

   - Invalid `EXTRA_ARGS`
   - Malformed model file
   - Unsupported model architecture

1. **Try CPU-only mode:**

   ```bash
   NGL=0
   ```

   If this works, the issue is GPU-related.

**Exit codes:**

| Code | Meaning             |
| ---- | ------------------- |
| 0    | Normal exit         |
| 1    | General error       |
| 127  | Binary not found    |
| 134  | SIGABRT (assertion) |
| 137  | SIGKILL (OOM)       |
| 139  | SIGSEGV (crash)     |

______________________________________________________________________

### GPU Not Detected

**Symptom:**

```
nvidia-smi not available (CPU mode)
```

**Solutions:**

1. **Docker GPU flag:**

   ```bash
   docker run --gpus all ...
   ```

1. **Check NVIDIA runtime:**

   ```bash
   docker run --gpus all nvidia/cuda:12.0-base nvidia-smi
   ```

1. **Platform-specific:**

   - RunPod: Ensure endpoint has GPU selected
   - Vast.ai: Ensure GPU instance type
   - Local: Install nvidia-container-toolkit

______________________________________________________________________

### Health Check Failing

**Symptom:**

- `/ping` returns 204 indefinitely
- Platform shows "Initializing" forever

**Diagnosis:**

1. **Model still loading:**

   - Large models take time
   - Check logs for `main: model loaded`

1. **Server crashed:**

   - Check boot log for errors
   - Look for exit code

1. **Port mismatch:**

   - Ensure `PORT` matches platform expectations

**Health behavior:**

- `200` = Ready (model loaded)
- `204` = Initializing (still loading)

______________________________________________________________________

### Streaming Not Working

**Symptom:**

- Responses arrive all at once
- SSE events not received

**Solutions:**

1. **Verify stream parameter:**

   ```json
   {"stream": true}
   ```

1. **Check client timeout:**

   - Increase client-side timeout for first token

1. **Proxy issues:**

   - Some reverse proxies buffer SSE
   - Check platform proxy configuration

______________________________________________________________________

### Slow Inference

**Symptom:**

- Low tokens/second
- Long time to first token

**Solutions:**

1. **Maximize GPU offload:**

   ```bash
   NGL=99
   ```

1. **Check GPU utilization:**

   ```bash
   nvidia-smi
   # Should show high GPU-Util during inference
   ```

1. **Reduce context if not needed:**

   ```bash
   CTX=8192
   ```

1. **Check for CPU fallback:**

   - If model doesn't fit, computation falls back to CPU
   - Reduce NGL or model size

______________________________________________________________________

### DATA_DIR Not Found

**Symptom:**

```
No data directory - logging to stdout only
```

**Solutions:**

1. **Mount a volume:**

   ```bash
   docker run -v /path:/data ...
   ```

1. **Set DATA_DIR explicitly:**

   ```bash
   DATA_DIR=/mnt/storage
   ```

1. **Platform auto-detection:**

   - RunPod Serverless: `/runpod-volume`
   - RunPod Pods: `/workspace`
   - Vast.ai: `/workspace`

______________________________________________________________________

## Log Locations

| Log Type      | Default Location                      |
| ------------- | ------------------------------------- |
| Boot logs     | `$DATA_DIR/logs/_boot/`               |
| Server logs   | `$DATA_DIR/logs/$LOG_NAME/`           |
| Latest boot   | `$DATA_DIR/logs/_boot/latest.txt`     |
| Latest server | `$DATA_DIR/logs/$LOG_NAME/latest.txt` |

**View latest logs:**

```bash
# Boot log
cat $(cat $DATA_DIR/logs/_boot/latest.txt)

# Server log
cat $(cat $DATA_DIR/logs/llama/latest.txt)
```

______________________________________________________________________

## Platform-Specific Issues

### RunPod Serverless

**HuggingFace validation stuck:**

- This is a RunPod/HF issue, not this container
- Use a placeholder repo in the HF field
- Or wait for HF to recover

**Worker not starting:**

- Check RunPod dashboard for errors
- Verify container image is accessible

### Vast.ai

**Volume not mounted:**

- Ensure "disk" is allocated in template
- Check `/workspace` exists

### Local Docker

**Permission denied:**

```bash
# Run as root or fix permissions
docker run --user root ...
# Or
chmod -R 777 /path/to/data
```

______________________________________________________________________

## Getting Help

1. **Check boot log first** — Most issues visible there
1. **Try DEBUG_SHELL=true** — Inspect container state
1. **Try NGL=0** — Isolate GPU issues
1. **Simplify** — Minimal config, small model

## Reporting Issues

Include:

1. Boot log contents
1. Environment variables (redact secrets)
1. Model name and size
1. GPU type
1. Platform (RunPod/Vast.ai/local/etc)
1. Error messages
