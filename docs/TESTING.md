# Testing Guide

Comprehensive testing strategy for llama-gguf-inference.

## Current Test Coverage

**224 tests total** across 4 test modules. Coverage: `auth.py` 78%, `gateway.py` 60%, `key_mgmt.py` 79%, overall 59%.

### pytest Test Suite

Located in `tests/`, run with `python3 -m pytest tests/ -v`:

#### `test_auth.py` — 33 tests

- API key validation and format checking
- Rate limiter logic and sliding window behavior
- Key file parsing (comments, blanks, duplicates)
- Authorization header extraction (Bearer and raw)
- Error response format (401, 429)

#### `test_gateway.py` — 95 tests

- Request routing and health endpoint exemptions
- CORS header injection, preflight handling, and origin validation
- Prometheus metrics format and content negotiation
- Concurrency control and queue behavior (config, response format, enforcement)
- Request body size limits (413 Payload Too Large)
- Header count and size limits (431 Request Header Fields Too Large)
- Security limits integration tests
- Streaming proxy and backend connection handling
- Metrics counters (requests, errors, bytes, queue)

#### `test_key_mgmt.py` — 47 tests

- Key generation (format, uniqueness, CSPRNG)
- Key listing (display, empty file, quiet mode)
- Key removal (existing, missing, file integrity)
- Key rotation (regeneration, atomic write)
- Validation (key_id format, duplicates, edge cases)
- Atomic write safety and file permission (0600)

#### `test_benchmark.py` — 49 tests

- Statistics computation (percentile, mean, min/max)
- SSE token parsing and content extraction
- Output formatting (text and JSON)
- Gateway benchmark configuration
- Inference benchmark configuration

### Shell Tests (Pre-commit)

Located in `scripts/tests/`, these run quickly during development:

#### `test_auth.sh`

Quick validation of authentication functionality:

- Syntax validation of auth.py
- Basic import tests
- Configuration validation

#### `test_health.sh`

Health endpoint validation:

- Health server starts successfully
- Gateway health endpoints work
- Health checks work when auth enabled

### Full Tests (GitHub Actions)

Located in `.github/workflows/ci.yml`:

- All pre-commit checks
- pytest suite (`tests/`)
- Docker build test
- Integration tests

## Running Tests

```bash
# Run full pytest suite
python3 -m pytest tests/ -v

# Run with coverage report
python3 -m pytest tests/ --cov=scripts --cov-report=term-missing

# Run specific test file
python3 -m pytest tests/test_gateway.py -v
python3 -m pytest tests/test_auth.py -v
python3 -m pytest tests/test_key_mgmt.py -v
python3 -m pytest tests/test_benchmark.py -v
```

### Manual Testing

#### Test Authentication

```bash
# 1. Disable auth for baseline
AUTH_ENABLED=false docker run ...

# Test without key (should work)
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"any","messages":[{"role":"user","content":"test"}]}'
# Expected: Passes through to backend

# 2. Enable auth with test key
echo "testing:sk-test-12345" > /tmp/test_keys.txt

AUTH_ENABLED=true \
AUTH_KEYS_FILE=/tmp/test_keys.txt \
docker run -v /tmp/test_keys.txt:/tmp/test_keys.txt:ro ...

# Test with valid key (should work)
curl -H "Authorization: Bearer sk-test-12345" \
  http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"any","messages":[{"role":"user","content":"test"}]}'
# Expected: 200 or passes to backend

# Test with invalid key (should fail)
curl -H "Authorization: Bearer sk-wrong" \
  http://localhost:8000/v1/chat/completions
# Expected: 401 {"error": {"code": "invalid_api_key", ...}}

# Test without key (should fail)
curl http://localhost:8000/v1/chat/completions
# Expected: 401 {"error": {"message": "Missing Authorization header", ...}}

# Test health endpoints (should work without auth)
curl http://localhost:8000/ping
# Expected: 200

curl http://localhost:8000/health
# Expected: 200 with JSON response
```

#### Test Rate Limiting

```bash
# Send 101 requests rapidly (rate limit: 100/min)
for i in {1..101}; do
  curl -H "Authorization: Bearer sk-test-12345" \
    http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"any","messages":[{"role":"user","content":"test"}]}'
done

# Request 101 should return: 429 Rate Limit Exceeded
```

#### Test Logging

```bash
# Enable auth and make requests
AUTH_ENABLED=true AUTH_KEYS_FILE=/data/api_keys.txt docker run ...

# Make some requests with different keys
curl -H "Authorization: Bearer sk-prod-key" ...
curl -H "Authorization: Bearer sk-dev-key" ...

# Check access log
cat /data/logs/api_access.log

# Expected format:
# 2024-02-06T14:30:22.123456 | production | POST /v1/chat/completions | 200
# 2024-02-06T14:30:25.654321 | development | POST /v1/chat/completions | 200
```

#### Test Worker Type Logging

```bash
# Run with worker type
WORKER_TYPE=instruct docker run ...

# Check logs are in correct directory
ls /data/logs/llama-instruct/

# Check timestamp-first naming
ls /data/logs/llama-instruct/
# Expected: 20240206_143022_server_instanceid.log
```

#### Test Port Naming

```bash
# Test with new name
PORT_BACKEND=9080 docker run ...

# Test with old name (should warn)
BACKEND_PORT=9080 docker run ...
# Expected: Log shows deprecation warning

# Test both (new takes precedence)
PORT_BACKEND=8080 BACKEND_PORT=9080 docker run ...
# Expected: Uses 8080, shows warning
```

## Planned Improvements

- **Integration tests with live backend** — Full end-to-end testing on RunPod Serverless (see
  [LIVE_TESTING_GUIDE.md](LIVE_TESTING_GUIDE.md))
- **Load testing** — Sustained concurrency testing at target throughput levels
- **Security testing** — Auth bypass attempts, injection testing, timing attack verification
- **Coverage target** — Push from 59% toward 80%+ by covering remaining gateway and auth paths

## Debugging Failed Tests

### View Test Logs

```bash
# CI logs
gh run view  # GitHub CLI

# Local logs
cat /tmp/test_*.log
```

### Run Individual Test

```bash
# Run single test with verbose output
bash -x scripts/tests/test_auth.sh
```

### Debug Auth Issues

```bash
# Enable debug logging
export DEBUG=true
bash scripts/tests/test_auth.sh
```

## Contributing Tests

When adding new features:

1. **Add unit tests** for new functions
1. **Add integration tests** for new workflows
1. **Update test documentation** in this file
1. **Run all tests** before submitting PR

## Test Checklist

Before release:

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Auth workflow tested manually
- [ ] Rate limiting verified
- [ ] Logging verified
- [ ] Health endpoints work
- [ ] Docker build succeeds
- [ ] Documentation updated
- [ ] Pre-commit hooks pass
- [ ] GitHub Actions pass

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [bash testing with bats](https://github.com/bats-core/bats-core)
- [Docker test containers](https://www.testcontainers.org/)
- [API testing with curl](https://everything.curl.dev/)
