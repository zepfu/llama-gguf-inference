# Authentication Guide

Complete guide to API key authentication in llama-gguf-inference.

## Overview

The gateway supports optional API key authentication to secure access to your inference endpoints while keeping health
checks publicly accessible.

**Key Features:**

- File-based API key management
- Key ID tracking for audit logs
- Per-key rate limiting (global default or per-key override)
- Key expiration with ISO 8601 timestamps or relative durations
- Hot-reload keys via SIGHUP signal or `POST /reload` endpoint
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

Format: `key_id:api_key[:rate_limit][:expiration]`

```
# Comments are allowed
production:sk-prod-a1b2c3d4e5f6...
development:sk-dev-x9y8z7w6v5u4...
alice-laptop:sk-alice-m1n2o3p4...

# Blank lines are ignored
staging:sk-staging-q5r6s7t8...

# With per-key rate limit (requests per minute)
batch-user:sk-batch-a1b2c3d4e5f6...:120

# With expiration only (ISO 8601 timestamp)
temp-key:sk-temp-x9y8z7w6v5u4...::2026-03-01T00:00:00

# With both rate limit and expiration
vip-client:sk-vip-m1n2o3p4...:300:2026-12-31T23:59:59
```

**Key format reference (all optional fields):**

```
key_id:api_key                           # basic
key_id:api_key:120                       # with per-key rate limit
key_id:api_key::2026-03-01T00:00:00     # with expiration
key_id:api_key:300:2026-12-31T23:59:59  # with both
```

**Rules:**

- One key per line
- Format: `key_id:api_key[:rate_limit][:expiration]` (colon-separated)
- key_id: Alphanumeric, hyphens, underscores (e.g., `production`, `dev-team`)
- api_key: 16-128 characters, alphanumeric with hyphens/underscores
- rate_limit: Optional positive integer (requests per minute), overrides `MAX_REQUESTS_PER_MINUTE`
- expiration: Optional ISO 8601 timestamp (e.g., `2026-03-01T00:00:00`)
- Comments start with `#`
- Duplicate keys are rejected

## Key Management

### Key Management CLI

The `key_mgmt.py` tool provides safe key management with atomic writes and proper file permissions.

```bash
python3 scripts/key_mgmt.py <command> [options]
```

**Commands:**

| Command    | Description                    | Requires `--name` |
| ---------- | ------------------------------ | ----------------- |
| `generate` | Create a new API key           | Yes               |
| `list`     | List configured key IDs        | No                |
| `remove`   | Remove a key by key ID         | Yes               |
| `rotate`   | Regenerate key for existing ID | Yes               |

**Global options:**

| Option          | Description                                                                |
| --------------- | -------------------------------------------------------------------------- |
| `--file PATH`   | Path to keys file (default: `$AUTH_KEYS_FILE` or `$DATA_DIR/api_keys.txt`) |
| `--quiet`, `-q` | Suppress output except key values (useful for scripting)                   |

**Generate options:**

| Option            | Description                                                                |
| ----------------- | -------------------------------------------------------------------------- |
| `--rate-limit N`  | Per-key rate limit in requests per minute (overrides global default)       |
| `--expires VALUE` | Key expiration: ISO 8601 datetime or relative format (`30d`, `24h`, `60m`) |

**Rotate options:**

| Option            | Description                                    |
| ----------------- | ---------------------------------------------- |
| `--expires VALUE` | New expiration (preserves existing rate limit) |

**Key format:** `sk-` prefix + 43 base64url characters (46 characters total), generated with a CSPRNG.

**Examples:**

```bash
# Generate a new key
python3 scripts/key_mgmt.py generate --name production
# Output: Generated key for 'production': sk-abc123...

# Generate with per-key rate limit (requests per minute)
python3 scripts/key_mgmt.py generate --name batch-user --rate-limit 120

# Generate with expiration (ISO 8601 or relative: 30d, 24h, 60m)
python3 scripts/key_mgmt.py generate --name temp-key --expires 2026-03-01T00:00:00
python3 scripts/key_mgmt.py generate --name temp-key --expires 30d

# Generate with both rate limit and expiration
python3 scripts/key_mgmt.py generate --name vip --rate-limit 300 --expires 365d

# Generate and capture for scripting
KEY=$(python3 scripts/key_mgmt.py generate --name ci-runner --quiet)

# List all configured keys (never shows key values, shows rate limit and expiration status)
python3 scripts/key_mgmt.py list

# Rotate a key (regenerate with same key_id, preserves rate limit)
python3 scripts/key_mgmt.py rotate --name production

# Rotate and update expiration
python3 scripts/key_mgmt.py rotate --name alice-laptop --expires 30d

# Remove a key
python3 scripts/key_mgmt.py remove --name old-client

# Use a custom keys file
python3 scripts/key_mgmt.py generate --name staging --file /secrets/api_keys.txt
```

**Safety features:**

- Atomic writes (temp file + rename) prevent corruption
- File permissions set to `0600` (owner read/write only)
- Creates parent directories and keys file if they do not exist
- Rejects duplicate key IDs on generate (use `rotate` instead)
- Never displays existing key values (only newly generated keys)

### Manual Key Generation

If you prefer to generate keys manually:

**Method 1: OpenSSL**

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

### Add New Key (Manual)

```bash
# Generate key
NEW_KEY=$(openssl rand -hex 32)

# Add to file with descriptive ID
echo "alice-laptop:sk-alice-$NEW_KEY" >> /data/api_keys.txt

# Share key securely with user (via encrypted channel)
```

### Rotate Key (Manual)

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
# Using the CLI (recommended)
python3 scripts/key_mgmt.py remove --name alice-laptop

# Or manually edit the keys file
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
# production key: 100 req/min (global default)
# development key: 100 req/min (global default)
# alice-laptop key: 100 req/min (global default)
# Each has independent limit
```

### Per-Key Rate Limits

Individual keys can override the global `MAX_REQUESTS_PER_MINUTE` by specifying a per-key rate limit in the keys file.
This allows different usage tiers -- for example, a VIP key with a higher limit or a batch processing key with a lower
limit.

**Setting via keys file:**

```
# Format: key_id:api_key:rate_limit
vip-client:sk-vip-abc123...:300
batch-user:sk-batch-xyz789...:50
standard:sk-std-def456...          # uses global default (100)
```

**Setting via key_mgmt.py:**

```bash
python3 scripts/key_mgmt.py generate --name vip-client --rate-limit 300
```

**Behavior:**

- Per-key rate limits override the global `MAX_REQUESTS_PER_MINUTE` for that specific key
- Keys without a per-key limit fall back to the global default
- Rate limits use the same sliding 60-second window as the global limiter
- Per-key limits are preserved during hot-reload

### Key Expiration

Keys can be given an expiration time, after which they will be rejected with a 401 response. This is useful for
temporary access, trial keys, or enforcing periodic key rotation.

**Setting via keys file:**

```
# Format: key_id:api_key::expiration (note the empty rate_limit field)
temp-key:sk-temp-abc123...::2026-03-01T00:00:00

# With both rate limit and expiration
vip-key:sk-vip-xyz789...:300:2026-12-31T23:59:59
```

**Setting via key_mgmt.py:**

```bash
# ISO 8601 datetime
python3 scripts/key_mgmt.py generate --name temp-key --expires 2026-03-01T00:00:00

# Relative formats
python3 scripts/key_mgmt.py generate --name trial-key --expires 30d    # 30 days from now
python3 scripts/key_mgmt.py generate --name demo-key --expires 24h     # 24 hours from now
python3 scripts/key_mgmt.py generate --name test-key --expires 60m     # 60 minutes from now
```

**Behavior:**

- Expired keys receive a `401 Unauthorized` response with the message `API key has expired`
- Expiration is checked on every request after key validation
- The `list` command shows expiration status (active, expired) for each key
- Expiration can be updated when rotating a key with `--expires`

### Hot-Reload API Keys

API keys can be reloaded without restarting the gateway, allowing you to add, remove, or modify keys with zero downtime.

**Via SIGHUP signal:**

```bash
# Docker
docker kill -s HUP my-inference-container

# Direct process signal (inside the container)
kill -HUP $(pgrep -f gateway.py)
```

**Via POST /reload endpoint (requires authentication):**

```bash
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8000/reload
# {"status": "ok", "keys_loaded": 3}
```

**Behavior:**

- **Atomic replacement:** Either all keys are replaced or the previous set is preserved unchanged
- **Fail-closed:** If the reload fails (e.g., file not found, parse error), the gateway continues serving with the
  previous keys
- **Rate limiter preserved:** Request timestamps for known keys survive the reload, preventing rate limit bypass by
  triggering a reload
- **Re-reads environment:** The `AUTH_KEYS_FILE` path is re-read from the environment at reload time, allowing you to
  point to a new file without restarting

**Typical workflow:**

1. Edit the keys file to add/remove/modify keys
1. Send `SIGHUP` or call `POST /reload`
1. Verify the response shows the expected key count
1. Gateway immediately uses the new keys for all subsequent requests

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

**Different limits per key:** Supported via per-key rate limits in the keys file. See the
[Per-Key Rate Limits](#per-key-rate-limits) section above.

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
- Scopes and permissions
- Usage quotas
- Key management API/dashboard

The current file-based system is designed to be extended, not replaced.
