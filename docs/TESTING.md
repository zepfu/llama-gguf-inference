# Testing Guide

Comprehensive testing strategy for llama-gguf-inference.

## Current Test Coverage

### Minimal Tests (Pre-commit)

Located in `scripts/tests/`, these run quickly during development:

#### `test_auth.sh`
Quick validation of authentication functionality:
- ✅ Syntax validation of auth.py
- ✅ Basic import tests
- ✅ Configuration validation

#### `test_health.sh`
Health endpoint validation:
- ✅ Health server starts successfully
- ✅ Gateway health endpoints work
- ✅ Health checks work when auth enabled

### Full Tests (GitHub Actions)

Located in `.github/workflows/code-quality.yml`:
- ✅ All pre-commit checks
- ✅ Docker build test
- ✅ Integration tests

## Running Tests

### Locally (Pre-commit)

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run all checks
pre-commit run --all-files

# Run specific test
bash scripts/tests/test_auth.sh
bash scripts/tests/test_health.sh
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

## Future: Comprehensive Test Suite

The following tests should be implemented for production deployments:

### Unit Tests

**Python (`tests/unit/`)**
```python
# tests/unit/test_auth.py
def test_api_key_validation():
    """Test key format validation"""
    pass

def test_rate_limiting():
    """Test rate limiter logic"""
    pass

def test_key_id_extraction():
    """Test parsing key_id:api_key format"""
    pass

# tests/unit/test_gateway.py
def test_request_routing():
    """Test request routing logic"""
    pass

def test_health_endpoint_exemption():
    """Test health endpoints skip auth"""
    pass
```

**Bash (`tests/unit/`)**
```bash
# tests/unit/test_start_sh.sh
test_worker_type_directory_creation() {
    # Test LOG_NAME construction
}

test_port_backward_compatibility() {
    # Test BACKEND_PORT fallback
}
```

### Integration Tests

**Full Workflow (`tests/integration/`)**
```bash
# tests/integration/test_full_workflow.sh

# 1. Start container
# 2. Wait for ready
# 3. Test auth flow
# 4. Test rate limiting
# 5. Test logging
# 6. Cleanup
```

### Load Tests

**Performance Testing (`tests/load/`)**
```bash
# tests/load/test_rate_limiting.sh

# Send 1000 requests, verify rate limiting works
# Measure: response times, success rate, rate limit accuracy
```

**Concurrent Requests (`tests/load/`)**
```bash
# tests/load/test_concurrent.sh

# 10 concurrent clients, 100 requests each
# Verify: no race conditions, accurate rate limiting
```

### Security Tests

**Auth Bypass Attempts (`tests/security/`)**
```bash
# tests/security/test_auth_bypass.sh

# Try various bypass techniques:
# - Missing header
# - Malformed header
# - SQL injection in key
# - Path traversal in key_id
# - Timing attacks
```

### End-to-End Tests

**Complete Deployment (`tests/e2e/`)**
```bash
# tests/e2e/test_production_scenario.sh

# 1. Deploy with production config
# 2. Create API keys
# 3. Test client connections
# 4. Verify logging
# 5. Test key rotation
# 6. Verify metrics
```

## Test Structure (Future)

```
tests/
├── unit/
│   ├── test_auth.py
│   ├── test_gateway.py
│   ├── test_start_sh.sh
│   └── test_health_server.py
├── integration/
│   ├── test_full_workflow.sh
│   ├── test_auth_integration.sh
│   └── test_logging.sh
├── load/
│   ├── test_rate_limiting.sh
│   ├── test_concurrent.sh
│   └── test_performance.sh
├── security/
│   ├── test_auth_bypass.sh
│   ├── test_injection.sh
│   └── test_timing.sh
├── e2e/
│   ├── test_production_scenario.sh
│   ├── test_multi_worker.sh
│   └── test_key_rotation.sh
└── fixtures/
    ├── test_keys.txt
    ├── test_models/
    └── test_data/
```

## CI/CD Pipeline (Future)

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  unit:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - run: python -m pytest tests/unit/
      - run: bash tests/unit/test_start_sh.sh

  integration:
    name: Integration Tests
    runs-on: ubuntu-latest
    steps:
      - run: bash tests/integration/test_full_workflow.sh

  load:
    name: Load Tests
    runs-on: ubuntu-latest
    # Only on main branch
    if: github.ref == 'refs/heads/main'
    steps:
      - run: bash tests/load/test_rate_limiting.sh

  security:
    name: Security Tests
    runs-on: ubuntu-latest
    steps:
      - run: bash tests/security/test_auth_bypass.sh

  e2e:
    name: End-to-End Tests
    runs-on: ubuntu-latest
    # Only on release tags
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - run: bash tests/e2e/test_production_scenario.sh
```

## Test Data Management

### Fixtures

**API Keys (`tests/fixtures/test_keys.txt`)**
```
testing:sk-test-12345
loadtest:sk-load-67890
security:sk-sec-abcdef
```

**Mock Responses (`tests/fixtures/`)**
```
mock_llama_response.json
mock_health_response.json
```

### Test Models

For integration tests, use small test models:
```bash
# Download tiny GGUF for testing
curl -L -o tests/fixtures/tiny-model.gguf \
  https://huggingface.co/...
```

## Measuring Coverage

### Python Coverage

```bash
# Install coverage
pip install coverage

# Run tests with coverage
coverage run -m pytest tests/unit/
coverage report
coverage html  # Generate HTML report
```

### Bash Coverage

```bash
# Use bashcov (requires Ruby)
gem install bashcov

# Run with coverage
bashcov tests/unit/test_start_sh.sh
```

## Performance Benchmarks

Track performance over time:

```bash
# tests/benchmarks/auth_performance.sh

# Measure:
# - Auth validation time
# - Rate limiter overhead
# - Log write performance
# - Overall request latency
```

**Example output:**
```
Auth validation: 0.5ms average
Rate limiter check: 0.1ms average
Access logging: 0.3ms average
Total auth overhead: 0.9ms
```

## Test Automation

### Git Hooks

```bash
# .git/hooks/pre-push
#!/bin/bash
echo "Running tests before push..."
pre-commit run --all-files
bash scripts/tests/test_auth.sh
bash scripts/tests/test_health.sh
```

### Makefile

```makefile
.PHONY: test test-unit test-integration test-all

test: test-unit

test-unit:
	python -m pytest tests/unit/
	bash tests/unit/test_start_sh.sh

test-integration:
	bash tests/integration/test_full_workflow.sh

test-all: test-unit test-integration
	bash tests/load/test_rate_limiting.sh
	bash tests/security/test_auth_bypass.sh
```

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
2. **Add integration tests** for new workflows
3. **Update test documentation** in this file
4. **Run all tests** before submitting PR

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
