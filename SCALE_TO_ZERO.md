# Scale-to-Zero Configuration for Serverless Deployments

This guide explains how to configure llama-gguf-inference for proper scale-to-zero behavior on serverless platforms like RunPod.

## The Problem

In serverless environments, platforms like RunPod periodically send health check requests to monitor worker status. By default, these health checks can prevent your worker from ever being considered "idle," which means:

- Workers stay active indefinitely
- You pay for idle time
- Scale-to-zero doesn't work

## The Solution

llama-gguf-inference solves this by separating platform health checks from actual API traffic using two ports:

- **Port 8001 (PORT_HEALTH)**: Lightweight health server for platform monitoring
- **Port 8000 (PORT)**: Full gateway with API endpoints

When platform health checks use the dedicated health port, they don't count as "activity" for idle timeout purposes.

## RunPod Serverless Configuration

### 1. Endpoint Settings

In your RunPod Serverless endpoint configuration:

**Worker Scaling:**
- Active Workers: `0`
- Max Workers: Set to your desired maximum (e.g., `3`)

**Lifecycle and Timeouts:**
- Idle Timeout: `5` seconds (or as low as your use case allows)
- Execution Timeout: Set based on your inference needs (e.g., `300` seconds)

**Container Configuration:**
- Expose Ports: `8000, 8001`

### 2. Environment Variables

Add these to your endpoint:

```bash
MODEL_NAME=your-model.gguf
PORT=8000
PORT_HEALTH=8001
```

### 3. Health Check Configuration

Configure RunPod to use port 8001 for health checks:

- In endpoint settings, set the health check port to `8001`
- Or configure via API when creating the endpoint

### 4. Verify Scale-to-Zero Behavior

After deploying:

1. **Send a test request** to trigger worker startup
2. **Wait for idle timeout** (e.g., 5 seconds after request completes)
3. **Check worker status** in RunPod dashboard
4. Worker should transition to "Idle" then terminate

If the worker stays active:
- Check logs for continuous incoming requests
- Verify health check is configured for port 8001
- Ensure no external monitoring is hitting port 8000

## How It Works

### Architecture

```
RunPod Platform
    │
    ├─> Port 8001 (Health Checks)
    │       │
    │       └─> health_server.py
    │           - Always returns 200 OK
    │           - No backend interaction
    │           - Doesn't count as "activity"
    │
    └─> Port 8000 (API Traffic)
            │
            └─> gateway.py
                - /v1/chat/completions
                - /v1/completions
                - /ping, /health, /metrics
                - Counts as real activity
```

### What Counts as Activity

**Counts as activity (keeps worker alive):**
- Requests to port 8000 (API endpoints)
- Streaming connections
- Long-running inference requests

**Does NOT count as activity:**
- Health checks to port 8001
- Platform monitoring on port 8001

## Other Serverless Platforms

The same principle applies to other platforms. Configure:

1. Expose both ports 8000 and 8001
2. Set `PORT_HEALTH=8001` environment variable
3. Configure platform health checks to use port 8001
4. Set appropriate idle timeout

### Platform-Specific Notes

**Vast.ai:**
- Similar configuration to RunPod
- Configure health check endpoint if supported

**Lambda Labs:**
- May not support separate health port
- Contact support for scale-to-zero configuration

**Modal, Replicate, etc.:**
- Check platform documentation for health check configuration
- Apply same port separation principle

## Troubleshooting

### Worker Never Scales Down

**Check 1: Verify health check port**
```bash
# In container logs, you should see:
[health] Starting health server on 0.0.0.0:8001
```

**Check 2: Monitor incoming traffic**
```bash
# Watch gateway logs for unexpected requests
tail -f /runpod-volume/logs/llama/latest.txt
```

**Check 3: Confirm endpoint settings**
- Active Workers = 0
- Idle Timeout is set (not disabled)
- Health checks are on port 8001

### Health Checks Failing

**Symptoms:** RunPod shows worker as unhealthy

**Fix:** Verify port exposure
```bash
# Both ports must be exposed in container config
EXPOSE 8000 8001
```

### Workers Scale Down Too Aggressively

**Symptoms:** Workers terminate during legitimate use

**Fix:** Increase idle timeout
```bash
# In RunPod endpoint settings:
Idle Timeout: 30  # seconds
```

Or reduce if you want faster scale-down:
```bash
Idle Timeout: 5  # seconds (more aggressive)
```

## Monitoring Scale-to-Zero

### Via RunPod Dashboard

Watch the "Workers" tab:
- Active workers should be 0 when idle
- Workers should spin up on first request
- Workers should scale down after idle timeout

### Via Logs

Check boot logs for proper startup:
```bash
cat /runpod-volume/logs/_boot/latest.txt | xargs cat
```

You should see:
```
[start.sh] Starting health server
[health] Starting health server on 0.0.0.0:8001
[start.sh] Health server PID: 123 (port 8001)
[start.sh] Starting gateway
[gateway] Starting gateway on 0.0.0.0:8000
```

## Cost Savings Example

With proper scale-to-zero configuration:

**Before (without PORT_HEALTH):**
- Worker always active: 24 hours/day
- Cost: 24 hours × $0.50/hr = $12/day

**After (with PORT_HEALTH):**
- Worker active: 2 hours/day (actual usage)
- Worker idle: 22 hours/day (scaled to zero)
- Cost: 2 hours × $0.50/hr = $1/day
- **Savings: $11/day = $330/month**

## Best Practices

1. **Set aggressive idle timeouts for dev/testing** (5 seconds)
2. **Use longer timeouts for production** (30-60 seconds) to avoid cold starts
3. **Monitor actual usage patterns** and adjust timeouts accordingly
4. **Keep separate endpoints** for dev (aggressive scale-down) and prod (balanced)
5. **Test scale-to-zero** in dev before deploying to production

## Additional Resources

- [RunPod Serverless Documentation](https://docs.runpod.io/serverless/overview)
- [Container Configuration Guide](docs/configuration.md)
- [Debugging Guide](DEBUGGING.md)
