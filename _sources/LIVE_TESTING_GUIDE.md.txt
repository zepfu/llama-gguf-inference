# Live Testing Guide — v1.0.0-rc.1

Step-by-step guide for validating `v1.0.0-rc.1` on a live RunPod Serverless environment with a real GPU and GGUF model.

## Overview

This testing covers the final Phase 3 gate criteria that require a live inference backend:

1. **Performance baseline** — TTFT, tokens/sec, latency percentiles (p50/p95/p99)
1. **OpenAI SDK compatibility** — Verify `openai` Python SDK works without modification
1. **Scale-to-zero validation** — Health checks don't keep the worker active
1. **Queue behavior** — Concurrency limiting and 503 responses under load
1. **CORS validation** — Cross-origin requests work when configured

## Roles

| Step                      | Who                         | Description                                       |
| ------------------------- | --------------------------- | ------------------------------------------------- |
| 1. Provision environment  | **Operator**                | Create RunPod Serverless endpoint with RC image   |
| 2. Provide access details | **Operator**                | Share endpoint URL, API key, model info           |
| 3. Gateway overhead test  | **QA-ENGINEER**             | Run benchmark `--gateway-only`                    |
| 4. Inference performance  | **QA-ENGINEER**             | Run full benchmark at multiple concurrency levels |
| 5. OpenAI SDK test        | **QA-ENGINEER**             | Run SDK compatibility checks                      |
| 6. Scale-to-zero test     | **INFRASTRUCTURE-ENGINEER** | Verify idle worker scales down                    |
| 7. Queue behavior test    | **QA-ENGINEER**             | Verify concurrency limits and 503 responses       |
| 8. Results analysis       | **TECH-LEAD**               | Review results, determine pass/fail               |
| 9. Sign-off               | **PRODUCT-OWNER**           | Approve for Phase 4 gate                          |

## Step 1: Provision RunPod Serverless Environment (Operator)

### Docker Image

```
ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1
```

### Required Environment Variables

| Variable       | Value                   | Notes                                         |
| -------------- | ----------------------- | --------------------------------------------- |
| `MODEL_PATH`   | Path to GGUF model file | e.g., `/runpod-volume/models/your-model.gguf` |
| `AUTH_ENABLED` | `true`                  | Use auth to test the full request path        |
| `GPU_LAYERS`   | `-1`                    | Offload all layers to GPU (or set per model)  |
| `CONTEXT_SIZE` | `4096`                  | Adjust per model                              |

### Recommended Setup

- **GPU**: A100 or L40S (for consistent benchmark results)
- **Model**: A small-to-medium GGUF (7B-13B Q4/Q5) for reasonable test times
- **Volume**: Attach a network volume with the model pre-downloaded
- **Min workers**: 0 (to test scale-to-zero)
- **Max workers**: 1 (to test queue behavior)

### Generate API Keys

Before deploying, create an API keys file on the volume:

```bash
# On the volume (or bake into the container env)
python3 scripts/key_mgmt.py generate --file /runpod-volume/api_keys.txt --quiet
# Note the generated key for testing
```

Or set `AUTH_ENABLED=false` for initial smoke testing, then re-enable.

## Step 2: Provide Access Details (Operator)

Share the following with the team:

```
Endpoint URL: https://<runpod-endpoint-id>-8000.proxy.runpod.net
API Key: sk-<the-generated-key>
Model: <model-name-and-quant>
GPU: <gpu-type>
Context Size: <context-size>
```

## Step 3: Gateway Overhead Test (QA-ENGINEER)

Measures proxy latency without touching the inference backend.

```bash
python3 scripts/benchmark.py \
  --url https://<endpoint>:8000 \
  --gateway-only \
  --requests 50 \
  --warmup 5
```

**Expected results:**

- `/ping` latency: < 5ms p99 (gateway-only, no backend)
- `/health` latency: < 50ms p99 (includes backend health poll)

**Save output:**

```bash
python3 scripts/benchmark.py \
  --url https://<endpoint>:8000 \
  --gateway-only \
  --requests 50 \
  --warmup 5 \
  --output json > results/gateway_overhead.json
```

## Step 4: Inference Performance Baseline (QA-ENGINEER)

Run at multiple concurrency levels to establish baseline.

### Single-request baseline (concurrency=1)

```bash
python3 scripts/benchmark.py \
  --url https://<endpoint>:8000 \
  --api-key sk-<key> \
  --prompt "Write a short poem about the sea" \
  --max-tokens 128 \
  --concurrency 1 \
  --requests 10 \
  --warmup 2 \
  --output json > results/inference_c1.json
```

### Moderate concurrency (concurrency=4)

```bash
python3 scripts/benchmark.py \
  --url https://<endpoint>:8000 \
  --api-key sk-<key> \
  --prompt "Write a short poem about the sea" \
  --max-tokens 128 \
  --concurrency 4 \
  --requests 20 \
  --warmup 2 \
  --output json > results/inference_c4.json
```

### Higher concurrency (concurrency=8)

```bash
python3 scripts/benchmark.py \
  --url https://<endpoint>:8000 \
  --api-key sk-<key> \
  --prompt "Explain quantum computing in simple terms" \
  --max-tokens 256 \
  --concurrency 8 \
  --requests 30 \
  --warmup 3 \
  --output json > results/inference_c8.json
```

**Key metrics to capture:**

- **TTFT** (Time to First Token): p50, p95, p99
- **Tokens/sec** (generation throughput): mean, p50
- **Total latency**: p50, p95, p99
- **Error rate**: should be 0% for concurrency within limits

## Step 5: OpenAI SDK Compatibility (QA-ENGINEER)

Verify the `openai` Python SDK works without modification against our gateway.

```python
# test_openai_sdk.py — run from any machine with `pip install openai`
from openai import OpenAI

client = OpenAI(
    base_url="https://<endpoint>:8000/v1",
    api_key="sk-<key>",
)

# --- Chat completion (non-streaming) ---
response = client.chat.completions.create(
    model="local-model",      # model name doesn't matter, single-model server
    messages=[{"role": "user", "content": "Say hello in 3 languages"}],
    max_tokens=100,
)
print("Non-streaming:", response.choices[0].message.content)
assert response.choices[0].message.content, "Empty response"
assert response.usage.total_tokens > 0, "No usage data"

# --- Chat completion (streaming) ---
stream = client.chat.completions.create(
    model="local-model",
    messages=[{"role": "user", "content": "Count to 5"}],
    max_tokens=50,
    stream=True,
)
chunks = []
for chunk in stream:
    if chunk.choices[0].delta.content:
        chunks.append(chunk.choices[0].delta.content)
full_response = "".join(chunks)
print("Streaming:", full_response)
assert len(chunks) > 1, "Stream should produce multiple chunks"

# --- Model listing ---
models = client.models.list()
print("Models:", [m.id for m in models.data])
assert len(models.data) > 0, "No models listed"

# --- Embeddings (if model supports it) ---
try:
    emb = client.embeddings.create(
        model="local-model",
        input="test embedding input",
    )
    print("Embeddings dim:", len(emb.data[0].embedding))
except Exception as e:
    print(f"Embeddings not supported by this model: {e}")

print("\nAll OpenAI SDK compatibility tests PASSED")
```

**Pass criteria:** All assertions pass. No SDK errors or unexpected response formats.

## Step 6: Scale-to-Zero Validation (INFRASTRUCTURE-ENGINEER)

Verify that idle workers scale down when no inference requests are active.

1. **Confirm worker is active** — send a request, verify response
1. **Stop sending requests** — wait for RunPod idle timeout (usually 5-10 min)
1. **Check RunPod dashboard** — worker count should drop to 0
1. **Verify health endpoint still responds** — `curl https://<endpoint>:8001/ping` should return `pong` (health server
   on port 8001, independent of worker)
1. **Send a new request** — worker should cold-start and respond

**Critical check:** Health probes on port 8001 must NOT prevent scale-down. The health server is a separate lightweight
process that doesn't touch the llama-server backend.

> **Note:** On RunPod Serverless, the proxy routing may differ from direct Docker. The key test is that the health
> endpoint doesn't trigger worker activation.

## Step 7: Queue Behavior Test (QA-ENGINEER)

Test concurrency limiting and queue overflow behavior.

### Setup

Deploy with these env vars to make queue behavior observable:

```
MAX_CONCURRENT_REQUESTS=1
MAX_QUEUE_SIZE=2
```

### Test sequence

1. **Send 1 request** — should succeed normally
1. **Send 4 concurrent requests** — 1 active, 2 queued, 1 should get 503 with `Retry-After: 5`
1. **Check /health** — should show queue depth: `curl https://<endpoint>:8000/health | jq .queue`
1. **Check /metrics** — should show `queue_depth`, `queue_rejections`, `queue_wait_seconds_total`

```bash
# Quick parallel test with curl
for i in 1 2 3 4; do
  curl -s -w "\n%{http_code}\n" \
    -H "Authorization: Bearer sk-<key>" \
    -H "Content-Type: application/json" \
    -d '{"model":"m","messages":[{"role":"user","content":"Count to 100"}],"max_tokens":200}' \
    https://<endpoint>:8000/v1/chat/completions &
done
wait
```

**Expected:** 1 returns 200, 2 return 200 (after waiting), 1 returns 503.

## Step 8: Results Analysis (TECH-LEAD)

Review all JSON output files and determine pass/fail.

### Performance baseline thresholds (suggested)

| Metric                | Target             | Notes                                 |
| --------------------- | ------------------ | ------------------------------------- |
| Gateway `/ping` p99   | < 5ms              | Pure proxy overhead                   |
| TTFT p50 (c=1)        | < 500ms            | Depends heavily on model size         |
| TTFT p95 (c=1)        | < 1000ms           | Acceptable first-token latency        |
| Tokens/sec mean (c=1) | > 20 tok/s         | Depends on GPU + model + quant        |
| Error rate            | 0%                 | Within concurrency limits             |
| SDK compatibility     | All pass           | Non-streaming, streaming, models list |
| Scale-to-zero         | Worker scales down | Health checks don't prevent it        |

> Exact targets depend on GPU type and model size. The first run establishes the baseline; subsequent releases compare
> against it.

### Report format

```markdown
## Performance Baseline — v1.0.0-rc.1
- GPU: <type>
- Model: <name> (<quant>)
- Date: <date>

### Gateway Overhead
- /ping p50: Xms, p95: Xms, p99: Xms
- /health p50: Xms, p95: Xms, p99: Xms

### Inference (concurrency=1)
- TTFT p50: Xms, p95: Xms, p99: Xms
- Tokens/sec mean: X, p50: X
- Total latency p50: Xms, p95: Xms, p99: Xms

### Inference (concurrency=4)
- [same metrics]

### OpenAI SDK: PASS / FAIL
### Scale-to-Zero: PASS / FAIL
### Queue Behavior: PASS / FAIL
```

## Step 9: Sign-Off (PRODUCT-OWNER)

Review the TECH-LEAD's analysis. If all gate criteria pass:

- Approve Phase 3 → Phase 4 transition
- Record `[GATE]` entry in PROJECT_LOG.md
- Update `.claude/PHASES.md` Phase 3 status to COMPLETE

## File Outputs

All test results should be saved to a `results/` directory (gitignored):

```
results/
  gateway_overhead.json
  inference_c1.json
  inference_c4.json
  inference_c8.json
  openai_sdk_test.log
  scale_to_zero.log
  queue_behavior.log
  baseline_report.md
```
