# Authentication Guide

Complete guide to API key authentication in llama-gguf-inference.

## Overview

The gateway supports optional API key authentication to secure access to your inference endpoints while keeping health
checks publicly accessible.

**Key Features:**

- File-based API key management
- Key ID tracking for audit logs
- Per-key rate limiting
- OpenAI-compatible auth format
- Health endpoints always accessible (no auth required)

## Quick Start

### 1. Create API Keys File

```bash
# Copy example file
cp api_keys.txt.example /data/api_keys.txt

# Generate a secure key
KEY=$(openssl rand -hex 32)
echo "production:sk-prod-$KEY" >> /data/api_keys.txt

# Secure the file
chmod 600 /data/api_keys.txt
```

### 2. Enable Authentication

```bash
# Set environment variable (default is already true)
AUTH_ENABLED=true
AUTH_KEYS_FILE=/data/api_keys.txt
```

### 3. Make Authenticated Requests

```bash
# With Bearer token (OpenAI format)
curl -H "Authorization: Bearer sk-prod-YOUR_KEY" \
  http://localhost:8000/v1/chat/completions \
  -d '{"model":"any","messages":[{"role":"user","content":"Hello"}]}'

# Without Bearer prefix (also works)
curl -H "Authorization: sk-prod-YOUR_KEY" \
  http://localhost:8000/v1/chat/completions \
  -d '{"model":"any","messages":[{"role":"user","content":"Hello"}]}'
```

## Configuration

### Environment Variables

| Variable                  | Default                  | Description                   |
| ------------------------- | ------------------------ | ----------------------------- |
| `AUTH_ENABLED`            | `true`                   | Enable/disable authentication |
| `AUTH_KEYS_FILE`          | `$DATA_DIR/api_keys.txt` | Path to API keys file         |
| `MAX_REQUESTS_PER_MINUTE` | `100`                    | Rate limit per key ID         |

### Keys File Format

File: `/data/api_keys.txt` (or custom path via `AUTH_KEYS_FILE`)

Format: `key_id:api_key`

```
# Comments are allowed
production:sk-prod-a1b2c3d4e5f6...
development:sk-dev-x9y8z7w6v5u4...
alice-laptop:sk-alice-m1n2o3p4...

# Blank lines are ignored
staging:sk-staging-q5r6s7t8...
```

**Rules:**

- One key per line
- Format: `key_id:api_key` (colon-separated)
- key_id: Alphanumeric, hyphens, underscores (e.g., `production`, `dev-team`)
- api_key: 16-128 characters, alphanumeric with hyphens/underscores
- Comments start with `#`
- Duplicate keys are rejected

## Key Management

### Generate Secure Keys

**Method 1: OpenSSL (Recommended)**

```bash
openssl rand -hex 32
# Outputs 64 hex characters
# Use as: sk-prod-<output>
```

**Method 2: Python**

```bash
python3 -c "import secrets; print('sk-' + secrets.token_hex(32))"
# Outputs: sk-<64 hex characters>
```

**Method 3: Online (Use with caution)**

```
https://randomkeygen.com/
Select "504-bit WPA Key" and add sk- prefix
```

### Add New Key

```bash
# Generate key
NEW_KEY=$(openssl rand -hex 32)

# Add to file with descriptive ID
echo "alice-laptop:sk-alice-$NEW_KEY" >> /data/api_keys.txt

# Share key securely with user (via encrypted channel)
```

### Rotate Key

```bash
# 1. Generate new key
NEW_KEY=$(openssl rand -hex 32)

# 2. Add new key (keep old key temporarily)
echo "production-v2:sk-prod-$NEW_KEY" >> /data/api_keys.txt

# 3. Update clients to use new key

# 4. After grace period, remove old key
# Edit /data/api_keys.txt and delete old production line

# 5. Optionally rename production-v2 to production
```

### Revoke Key

```bash
# Edit keys file
nano /data/api_keys.txt

# Comment out or delete the line
# alice-laptop:sk-alice-xyz...  (REVOKED 2024-02-06)

# Changes take effect immediately (no restart needed)
```

## Endpoint Access

### Public Endpoints (No Auth Required)

These endpoints are always accessible without authentication:

```bash
GET /ping           # Quick health check
GET /health         # Detailed status
GET /metrics        # Gateway metrics
```

**Why?** Health endpoints must remain public for:

- Platform health checks (RunPod, Vast.ai, etc.)
- Scale-to-zero functionality in serverless deployments
- Monitoring systems

### Protected Endpoints (Auth Required)

These endpoints require valid API key when `AUTH_ENABLED=true`:

```bash
POST /v1/chat/completions
POST /v1/completions
GET  /v1/models
# All other /v1/* endpoints
```

## Authentication Flow

```
1. Client sends request with Authorization header
   GET /v1/models
   Authorization: Bearer sk-prod-abc123...

2. Gateway validates key
   - Extract key from header (with or without "Bearer " prefix)
   - Check if key exists in loaded keys
   - Check rate limit for this key_id

3a. If valid:
   - Record request for rate limiting
   - Log access with key_id
   - Forward request to backend

3b. If invalid:
   - Return 401 Unauthorized
   - Log unauthorized attempt
   - Close connection
```

## Error Responses

### 401 Unauthorized

**Missing header:**

```json
{
  "error": {
    "message": "Missing Authorization header",
    "type": "invalid_request_error",
    "param": "authorization",
    "code": "invalid_api_key"
  }
}
```

**Invalid key:**

```json
{
  "error": {
    "message": "Invalid API key",
    "type": "invalid_request_error",
    "param": "authorization",
    "code": "invalid_api_key"
  }
}
```

### 429 Rate Limit Exceeded

```json
{
  "error": {
    "message": "Rate limit exceeded. Please slow down your requests.",
    "type": "rate_limit_error",
    "code": "rate_limit_exceeded"
  }
}
```

Headers include:

```
Retry-After: 60
```

## Rate Limiting

Rate limits are enforced **per key_id**, not per IP address.

**Configuration:**

```bash
MAX_REQUESTS_PER_MINUTE=100  # Default
```

**Behavior:**

- Sliding window: Last 60 seconds
- Counted per key_id (e.g., "production", "alice-laptop")
- Separate limits for each key
- Resets automatically after 60 seconds

**Example:**

```bash
# production key: 100 req/min
# development key: 100 req/min
# alice-laptop key: 100 req/min
# Each has independent limit
```

## Access Logging

All authenticated requests are logged to `/data/logs/api_access.log`

**Format:**

```
timestamp | key_id | method path | status_code
```

**Example:**

```
2024-02-06T14:30:22.123456 | production | POST /v1/chat/completions | 200
2024-02-06T14:30:25.654321 | alice-laptop | POST /v1/chat/completions | 200
2024-02-06T14:30:28.987654 | development | GET /v1/models | 200
2024-02-06T14:30:31.456789 | unknown-key | POST /v1/chat/completions | 401
```

**Benefits:**

- Know who made each request
- Track usage per key/user/system
- Investigate rate limit issues
- Audit access patterns
- Debug client issues

## Metrics

Access `/metrics` endpoint (no auth required) to see per-key statistics:

```json
{
  "gateway": {
    "requests_total": 1523,
    "requests_authenticated": 1520,
    "requests_unauthorized": 3
  },
  "authentication": {
    "production": {
      "requests_last_minute": 45,
      "rate_limit": 100
    },
    "alice-laptop": {
      "requests_last_minute": 12,
      "rate_limit": 100
    }
  }
}
```

## Deployment Scenarios

### Local Development (Auth Disabled)

```bash
# .env
AUTH_ENABLED=false
MODEL_NAME=test-model.gguf
NGL=0  # CPU only
```

No authentication required - useful for testing.

### Local Development (Auth Enabled)

```bash
# .env
AUTH_ENABLED=true
AUTH_KEYS_FILE=/data/api_keys.txt

# /data/api_keys.txt
testing:sk-test-12345
```

```bash
# Test request
curl -H "Authorization: Bearer sk-test-12345" \
  http://localhost:8000/v1/models
```

### Production (Secure)

```bash
# .env
AUTH_ENABLED=true
AUTH_KEYS_FILE=/secrets/api_keys.txt
MAX_REQUESTS_PER_MINUTE=200

# /secrets/api_keys.txt (chmod 600)
production:sk-prod-<64-char-secure-key>
production-backup:sk-prod-backup-<64-char-secure-key>
monitoring:sk-monitor-<64-char-secure-key>
```

Mount secrets securely:

```bash
docker run -v /secure/path/api_keys.txt:/secrets/api_keys.txt:ro \
  -e AUTH_KEYS_FILE=/secrets/api_keys.txt \
  ...
```

### RunPod Serverless

```bash
# Environment variables in RunPod
AUTH_ENABLED=true
AUTH_KEYS_FILE=/runpod-volume/api_keys.txt
PORT_HEALTH=8001  # For scale-to-zero

# Upload api_keys.txt to your network volume
```

Health checks on PORT_HEALTH don't require auth, enabling proper scale-to-zero.

## Security Best Practices

### File Security

```bash
# Restrict file permissions
chmod 600 /data/api_keys.txt
chown root:root /data/api_keys.txt

# Never commit to version control
echo "api_keys.txt" >> .gitignore
```

### Key Generation

- ✅ Use cryptographically secure random generators
- ✅ Generate minimum 32 bytes (64 hex chars) of entropy
- ✅ Use different keys per environment
- ❌ Don't use predictable patterns
- ❌ Don't reuse keys across deployments

### Key Storage

- ✅ Store in separate file with restricted permissions
- ✅ Mount as read-only in containers
- ✅ Use secrets management (Vault, AWS Secrets Manager, etc.)
- ❌ Don't store in environment variables
- ❌ Don't commit to version control
- ❌ Don't log full keys

### Key Rotation

- ✅ Rotate keys regularly (monthly/quarterly)
- ✅ Have grace period when rotating (both keys work temporarily)
- ✅ Track key age/creation date
- ❌ Don't rotate all keys simultaneously
- ❌ Don't reuse old keys

### Access Control

- ✅ Use descriptive key IDs (production, alice-laptop, monitoring)
- ✅ Issue separate keys per user/system/purpose
- ✅ Revoke keys when no longer needed
- ✅ Monitor access logs for suspicious activity
- ❌ Don't share keys
- ❌ Don't use generic IDs (key1, key2)

## Troubleshooting

### Auth Not Working (All Requests Accepted)

**Check 1: Is AUTH_ENABLED set?**

```bash
# In container
echo $AUTH_ENABLED
# Should be: true
```

**Check 2: Does keys file exist?**

```bash
ls -la $AUTH_KEYS_FILE
# Should show: -rw------- 1 root root ... api_keys.txt
```

**Check 3: Are there valid keys in file?**

```bash
grep -v "^#" $AUTH_KEYS_FILE | grep -v "^$"
# Should show your keys
```

**Check 4: Check gateway logs**

```bash
# Look for startup message
# ✅ Authentication enabled with X keys
# vs
# ⚠️  Authentication enabled but no keys configured
```

### Valid Key Rejected (401)

**Check 1: Key format**

```bash
# Key should be 16-128 characters
# Only: alphanumeric, hyphens, underscores
```

**Check 2: Authorization header format**

```bash
# Both formats work:
Authorization: Bearer sk-your-key
Authorization: sk-your-key
```

**Check 3: Whitespace**

```bash
# No extra spaces
Authorization: Bearer sk-your-key
# Not:
Authorization: Bearer  sk-your-key  (extra spaces)
```

**Check 4: Key exists in file**

```bash
grep "sk-your-key" $AUTH_KEYS_FILE
```

### Rate Limit Issues

**Check current limit:**

```bash
curl http://localhost:8000/metrics | jq '.authentication'
```

**Increase limit:**

```bash
# In .env or environment
MAX_REQUESTS_PER_MINUTE=200  # Default is 100
```

**Different limits per key:** Currently not supported - all keys share the same limit. This is planned for future
enhancement.

### Access Logs Not Written

**Check 1: Directory exists**

```bash
ls -la /data/logs/
# Should have api_access.log
```

**Check 2: Permissions**

```bash
ls -la /data/logs/api_access.log
# Should be writable
```

**Check 3: Disk space**

```bash
df -h /data
```

## Future Enhancements

See [docs/FUTURE_KEY_MANAGEMENT.md](FUTURE_KEY_MANAGEMENT.md) for planned features:

- Client ID/Client Secret OAuth-style authentication
- Database-backed key storage
- Key expiration/TTL
- Scopes and permissions
- Usage quotas
- Key management API/dashboard

The current file-based system is designed to be extended, not replaced.
