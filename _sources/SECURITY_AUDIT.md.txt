# Security Audit Report — llama-gguf-inference v1

**Audit Date:** 2026-02-13 **Auditor:** SECURITY-ENGINEER **Scope:** Full code-level security audit of all endpoints and
container configuration for v1 release gate. **Phase:** Phase 4 — v1 Release Gate

______________________________________________________________________

## Audit Scope

The following files were reviewed line-by-line:

| File                       | LOC  | Description                                                     |
| -------------------------- | ---- | --------------------------------------------------------------- |
| `scripts/gateway.py`       | 888  | HTTP gateway, proxy logic, streaming, CORS, metrics, queuing    |
| `scripts/auth.py`          | 385  | API key validation, rate limiting, access logging               |
| `scripts/health_server.py` | 52   | Health check server on port 8001                                |
| `scripts/start.sh`         | ~800 | Startup orchestration, backend key generation, env var handling |
| `scripts/key_mgmt.py`      | 367  | API key management CLI (generate, list, remove, rotate)         |
| `Dockerfile`               | 73   | CUDA container image definition                                 |
| `Dockerfile.cpu`           | 85   | CPU multi-arch container image definition                       |

### Checklist Areas

For each file, the following categories were evaluated:

- Input validation (all external inputs sanitized)
- Authentication bypass possibilities
- Injection vulnerabilities (command injection, header injection)
- Information disclosure (error messages, logs, stack traces)
- Resource exhaustion (memory, CPU, connections, file descriptors)
- Race conditions (concurrent access, TOCTOU)
- Secrets handling (no secrets in logs, proper generation, secure comparison)
- Error handling (fail-closed, no sensitive data in error responses)
- Container security (permissions, exposed ports, capabilities)

______________________________________________________________________

## Previously Fixed Issues (Verified)

These issues were identified in prior audits and have been verified as correctly resolved.

| ID     | Severity | Description                                                                                        | File                                  | Status                                                                                                                                              |
| ------ | -------- | -------------------------------------------------------------------------------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| SEC-01 | HIGH     | Timing attack on API key comparison — dictionary lookup leaked timing information about valid keys | `scripts/auth.py` L221-233            | **VERIFIED FIXED** — Uses `hmac.compare_digest()` for constant-time comparison. Iterates all keys without early return.                             |
| SEC-02 | HIGH     | Fail-open on key file read error — exception during key loading allowed all requests through       | `scripts/auth.py` L77-154             | **VERIFIED FIXED** — Returns empty dict on error, which triggers fail-closed behavior (line 173: "no API keys loaded" rejects all).                 |
| SEC-03 | HIGH     | No request body size limit — attacker could send unbounded body to exhaust memory                  | `scripts/gateway.py` L80, L777        | **VERIFIED FIXED** — `MAX_REQUEST_BODY_SIZE` enforced before reading body. Returns 413 with proper error format.                                    |
| SEC-04 | MEDIUM   | CORS origin validation gaps — trailing slashes, oversized origins, missing scheme warnings         | `scripts/gateway.py` L84-156          | **VERIFIED FIXED** — Trailing slash stripped, `MAX_ORIGIN_LENGTH` enforced, startup warnings for missing schemes, `Vary: Origin` in allowlist mode. |
| SEC-05 | MEDIUM   | No header count/size limits — attacker could send many/large headers to exhaust memory             | `scripts/gateway.py` L81-82, L696-736 | **VERIFIED FIXED** — `MAX_HEADERS` (64) and `MAX_HEADER_LINE_SIZE` (8192) enforced per-header. Returns 431.                                         |

______________________________________________________________________

## New Findings

### SEC-06 [HIGH] — INSTANCE_ID used before definition/sanitization in start.sh

| Field        | Value                         |
| ------------ | ----------------------------- |
| **Severity** | HIGH                          |
| **File**     | `scripts/start.sh`            |
| **Lines**    | 196 (use) vs 234 (definition) |
| **Status**   | **FIXED**                     |

**Description:** The `INSTANCE_ID` variable was used in the backend key file path
(`BACKEND_KEY_FILE="$BACKEND_KEY_DIR/backend-${INSTANCE_ID}.key"`) on line 196 before it was defined and sanitized on
lines 234-235. If `INSTANCE_ID` was set via an external environment variable containing path traversal characters (e.g.,
`../../etc/cron.d/malicious`), the unsanitized value would be used directly in the file path where the backend API key
is written. This could allow an attacker with control over the environment to write the key file to an arbitrary path.

**Impact:** Path traversal in backend key file creation. An attacker controlling the `INSTANCE_ID` environment variable
could write the backend API key to an arbitrary filesystem location.

**Fix Applied:** Moved the `INSTANCE_ID` definition and sanitization (`${INSTANCE_ID//[^a-zA-Z0-9._-]/_}`) to before the
backend key file path construction. INSTANCE_ID is now defined on line 183 and sanitized on line 184, before its first
use on line 200.

______________________________________________________________________

### SEC-07 [MEDIUM] — No request line length limit

| Field        | Value                |
| ------------ | -------------------- |
| **Severity** | MEDIUM               |
| **File**     | `scripts/gateway.py` |
| **Line**     | 758                  |
| **Status**   | **FIXED**            |

**Description:** The HTTP request line (e.g., `GET /path HTTP/1.1`) is read via `asyncio.StreamReader.readline()`
without an explicit length limit. While `asyncio.StreamReader` has a default internal buffer limit of 64KB (`2**16`),
which provides an implicit ceiling, this is not explicitly controlled by the application. A malicious client could send
a very long request line (up to 64KB) consuming memory per-connection.

**Recommendation:** Consider setting a `limit` parameter on `asyncio.start_server()` or adding an explicit request line
length check similar to the header line size check (SEC-05). Not urgent for v1 since asyncio's default buffer provides a
reasonable cap.

**Fix Applied:** Added `MAX_REQUEST_LINE_SIZE` constant (default 8192 bytes) with an explicit length check on the
request line after reading. Returns 414 URI Too Long if the request line exceeds the limit.

______________________________________________________________________

### SEC-08 [MEDIUM] — Container runs as root

| Field        | Value                          |
| ------------ | ------------------------------ |
| **Severity** | MEDIUM                         |
| **File**     | `Dockerfile`, `Dockerfile.cpu` |
| **Lines**    | All                            |
| **Status**   | **FIXED**                      |

**Description:** Neither Dockerfile defines a non-root `USER` directive. All container processes (llama-server, gateway,
health server) run as root. If an attacker achieves code execution through a vulnerability in llama-server or the
gateway, they have full root privileges inside the container.

**Mitigating factors:**

- The base image (`ghcr.io/ggml-org/llama.cpp:server-cuda`) may require root for NVIDIA GPU device access
- Container isolation provides a boundary regardless of internal user
- No external package installation at runtime reduces the attack surface

**Recommendation:** For a future hardening pass, investigate running as a non-root user. This may require changes to the
base image or device permission configuration for GPU access. Document the rationale for running as root in the
Dockerfiles.

**Fix Applied:** Added a non-root `inference` user (UID 1000) to both Dockerfiles. The CUDA image includes `video` group
membership for GPU device access. The CPU image has no GPU groups. Pre-created `/data` directories with correct
ownership so the non-root user can write model data and keys. All container processes now run as the `inference` user.

______________________________________________________________________

### SEC-09 [MEDIUM] — Rate limiter state not bounded

| Field        | Value             |
| ------------ | ----------------- |
| **Severity** | MEDIUM            |
| **File**     | `scripts/auth.py` |
| **Lines**    | 65, 235-255       |
| **Status**   | **FIXED**         |

**Description:** The rate limiter uses `defaultdict(list)` mapping `key_id -> [timestamps]`. While old timestamps are
pruned on each check, the pruning only occurs for the specific `key_id` being checked. If many distinct key_ids
accumulate entries (e.g., through many different valid API keys), stale entries for inactive keys are never cleaned up.
Additionally, if a single key makes many requests in rapid succession beyond the rate limit, the timestamp list grows
until the next check call prunes it.

**Impact:** Gradual memory growth over long-running instances with many active API keys. In practice, the impact is
limited since each timestamp is only 8 bytes and keys are validated (16-128 chars), so realistic key counts are bounded.

**Recommendation:** Add periodic background cleanup of stale rate limiter entries (e.g., every 5 minutes, remove all
key_ids with no recent timestamps). Not blocking for v1 but should be addressed for long-running production deployments.

**Fix Applied:** Added lazy cleanup in `_check_rate_limit()` that runs every 5 minutes (`CLEANUP_INTERVAL = 300`). On
each cleanup pass, all key_ids with no recent timestamps (outside the current rate limit window) are removed from the
rate limiter dictionary, preventing unbounded memory growth over long-running instances.

______________________________________________________________________

### SEC-10 [LOW] — Content-Length parsing lacks error handling

| Field        | Value                |
| ------------ | -------------------- |
| **Severity** | LOW                  |
| **File**     | `scripts/gateway.py` |
| **Line**     | 734                  |
| **Status**   | **FIXED**            |

**Description:** The `Content-Length` header value is parsed with `int(value.strip())` without a try/except for
`ValueError`. If a client sends a malformed Content-Length (e.g., `Content-Length: abc`), the exception propagates to
the outer handler in `handle_client`, which catches it generically and closes the connection silently. The client
receives no HTTP error response.

**Recommendation:** Wrap `int()` in a try/except and return a 400 Bad Request response for malformed Content-Length
values.

**Fix Applied:** Wrapped the `int()` call in a try/except `ValueError` block. On malformed Content-Length values, the
gateway now returns a 400 Bad Request response using the `send_bad_request()` helper, giving the client a clear error
instead of a silent connection close.

______________________________________________________________________

### SEC-11 [LOW] — Log injection via request path and method

| Field        | Value             |
| ------------ | ----------------- |
| **Severity** | LOW               |
| **File**     | `scripts/auth.py` |
| **Lines**    | 374               |
| **Status**   | **FIXED**         |

**Description:** The `log_access()` function writes `method` and `path` directly into the access log file without
sanitization. A malicious client could craft a request line containing newlines or pipe characters to inject fake log
entries (e.g., `GET /path\n2026-01-01T00:00:00 | admin | DELETE /keys | 200`). While the HTTP request line is decoded
with `errors="replace"` in the gateway (which replaces invalid bytes), valid UTF-8 newline characters in the request
line would pass through.

**Mitigating factors:** The access log is an internal audit file, not user-facing. Exploitation requires a valid API key
(authenticated endpoint). The `readline()` call in the gateway naturally splits on `\n`, so injecting newlines in the
request line would require the raw bytes to contain `\r\n` followed by more data, which `readline()` would not include.

**Recommendation:** Sanitize `method` and `path` in `log_access()` by replacing control characters (e.g., `\n`, `\r`,
`|`) before writing.

**Fix Applied:** Added `_sanitize_log_field()` helper in `auth.py` that replaces `\n`, `\r`, `\t`, and `|` characters
with underscores. Applied to `method`, `path`, and `key_id` fields in `log_access()` before writing to the access log.

______________________________________________________________________

### SEC-12 [LOW] — Health endpoint exposes internal metrics to unauthenticated clients

| Field        | Value                |
| ------------ | -------------------- |
| **Severity** | LOW                  |
| **File**     | `scripts/gateway.py` |
| **Lines**    | 335-370, 381-417     |
| **Status**   | **FIXED**            |

**Description:** The `/health` and `/metrics` endpoints are unauthenticated and expose operational details including:

- Request counts, error rates, active connections
- Queue depth and configuration (max_concurrent, max_queue_size)
- Gateway uptime
- Whether authentication is enabled
- Backend health status

This information could help an attacker understand system load patterns, timing, and configuration.

**Mitigating factors:** This is a common pattern for infrastructure endpoints. The endpoints deliberately exclude
sensitive per-key metrics. The information is operational, not credential-related.

**Recommendation:** Consider making `/metrics` optionally authenticated via a configuration flag for deployments where
metric exposure is a concern. The current behavior is acceptable for v1 since operational monitoring is a primary use
case.

**Fix Applied:** Added `METRICS_AUTH_ENABLED` environment variable (default `false`). When set to `true`, the `/metrics`
endpoint requires authentication (same as API endpoints). The `/ping` and `/health` endpoints remain public to support
platform health checks and scale-to-zero behavior.

______________________________________________________________________

### SEC-13 [LOW] — Backend response headers forwarded without size limit

| Field        | Value                |
| ------------ | -------------------- |
| **Severity** | LOW                  |
| **File**     | `scripts/gateway.py` |
| **Lines**    | 725-752              |
| **Status**   | **FIXED**            |

**Description:** When proxying responses from the backend, response headers are accumulated in memory without a size
limit (`response_headers += line` in a loop). A compromised or malicious backend could send very large response headers
to exhaust gateway memory.

**Mitigating factors:** The backend is llama-server running on localhost, controlled by the same operator. The
`readline()` timeout prevents indefinite hanging. This would only be exploitable if the backend itself were compromised.

**Fix Applied:** Added `MAX_RESPONSE_HEADER_SIZE` constant (65536 = 64KB) enforced in the response header accumulation
loop in `proxy_request()`. When the cumulative size exceeds the limit, the backend connection is closed and a 502 Bad
Gateway response is returned to the client. This is a defense-in-depth measure; the limit is not configurable via
environment variable since operators should not need to change it.

______________________________________________________________________

### SEC-14 [INFO] — EXTRA_ARGS word-split without validation

| Field        | Value              |
| ------------ | ------------------ |
| **Severity** | INFO               |
| **File**     | `scripts/start.sh` |
| **Line**     | 494                |
| **Status**   | **FIXED**          |

**Description:** The `EXTRA_ARGS` environment variable is word-split and appended to the llama-server command arguments
without validation. This is intentional (shellcheck disable comment present) and allows operators to pass additional
flags. However, there is no documentation warning that this could override security-critical arguments (e.g.,
`--host 0.0.0.0` to rebind llama-server to all interfaces, bypassing the localhost-only restriction).

**Recommendation:** Add a comment and documentation note warning operators that `EXTRA_ARGS` can override security
defaults, and consider a blocklist of dangerous overrides (e.g., `--host`).

**Fix Applied:** Added a startup warning when `EXTRA_ARGS` is non-empty, logging the actual value to alert operators
that custom arguments are being passed to llama-server. This makes the use of `EXTRA_ARGS` visible in container logs for
audit and debugging purposes.

______________________________________________________________________

### SEC-15 [INFO] — DEBUG_SHELL mode exposes full environment

| Field        | Value              |
| ------------ | ------------------ |
| **Severity** | INFO               |
| **File**     | `scripts/start.sh` |
| **Lines**    | 253-261            |
| **Status**   | **FIXED**          |

**Description:** When `DEBUG_SHELL=true`, the script logs the complete environment (`env | sort`), which includes
`BACKEND_API_KEY` and any other sensitive environment variables. This is intended for debugging only but could
inadvertently expose secrets if container logs are captured or forwarded to a logging service.

**Mitigating factors:** Requires explicit opt-in via `DEBUG_SHELL=true`. Only outputs to container stdout/stderr. The
backend key is generated per-session and would be invalidated on next restart.

**Recommendation:** Filter sensitive variables from the `env | sort` output (e.g., exclude `*KEY*`, `*SECRET*`,
`*TOKEN*`, `*PASSWORD*`).

**Fix Applied:** Changed the debug environment dump from `env | sort` to
`env | sort | grep -viE '(key|secret|token|password|credential)'` to filter out any environment variables whose names
contain sensitive keywords. This prevents accidental disclosure of secrets in debug output while still providing useful
diagnostic information.

______________________________________________________________________

### SEC-16 [INFO] — Backend key partial disclosure in startup log

| Field        | Value              |
| ------------ | ------------------ |
| **Severity** | INFO               |
| **File**     | `scripts/start.sh` |
| **Line**     | 306                |
| **Status**   | **FIXED**          |

**Description:** The startup log prints the first 8 and last 8 characters of the backend API key:
`BACKEND_AUTH=enabled (key: ${BACKEND_API_KEY:0:8}...${BACKEND_API_KEY: -8})`. While this is a truncated form useful for
debugging, revealing 16 of 51 characters (31%) reduces the brute-force search space.

**Mitigating factors:** The backend key is only used for localhost communication between the gateway and llama-server.
An attacker with access to container logs cannot reach the backend directly (bound to 127.0.0.1). The key is per-session
and regenerated on restart.

**Recommendation:** Reduce to showing only the first 8 characters (prefix only) for identification purposes.

**Fix Applied:** Reduced the backend key disclosure from first 8 + last 8 characters (31% of the key) to first 8
characters only. The startup log now shows `key: ${BACKEND_API_KEY:0:8}...` which is sufficient for identification while
minimizing information disclosure.

______________________________________________________________________

## Security Strengths

The codebase demonstrates strong security practices in several areas:

1. **Constant-time key comparison** (SEC-01 fix): `hmac.compare_digest()` with full key iteration prevents timing
   attacks.

1. **Fail-closed authentication**: Missing keys file, empty keys, or load errors all result in rejecting all requests.

1. **Defense-in-depth with backend key**: The auto-generated per-session backend key ensures that even if the gateway is
   bypassed, llama-server requires authentication. The key is stored in `/dev/shm` (memory-backed, not persisted to
   disk) with 600 permissions and securely deleted on shutdown.

1. **Request size limits**: Body size (SEC-03), header count, and header line size (SEC-05) are all enforced before
   reading data.

1. **Backend isolation**: llama-server binds only to `127.0.0.1`, verified at startup via `netstat`/`ss`. This prevents
   direct network access to the backend.

1. **CORS hardening** (SEC-04): Origin validation with length limits, trailing slash normalization, and `Vary: Origin`
   for caching correctness.

1. **Secure key generation**: Both backend keys and API keys use `secrets.token_urlsafe()` (CSPRNG). API key management
   uses atomic writes with proper file permissions.

1. **Graceful error handling**: Error responses use OpenAI-compatible format without exposing internal details. Backend
   errors return generic 502 without stack traces.

1. **Secure shutdown**: Backend key files are securely deleted using `shred` (with fallback to zero-overwrite + `rm`).

1. **Input sanitization**: `INSTANCE_ID`, `WORKER_TYPE`, and `LOG_NAME` are all sanitized via character class
   substitution before use in file paths.

______________________________________________________________________

## Findings Summary

| Severity  | Count  | Open  | Fixed  |
| --------- | ------ | ----- | ------ |
| CRITICAL  | 0      | 0     | 0      |
| HIGH      | 1      | 0     | 1      |
| MEDIUM    | 3      | 0     | 3      |
| LOW       | 4      | 0     | 4      |
| INFO      | 3      | 0     | 3      |
| **Total** | **11** | **0** | **11** |

Previously fixed (verified): 5 (SEC-01 through SEC-05)

______________________________________________________________________

## v1 Release Assessment

**Recommendation: APPROVE for v1 release.**

**Rationale:**

- **All 11 findings from this audit are now FIXED.** Zero open findings across all severity levels.

- **No open CRITICAL findings.** The codebase has no vulnerabilities that could lead to unauthorized access, data
  breach, or complete system compromise.

- **No open HIGH findings.** The one HIGH finding (SEC-06: INSTANCE_ID path traversal) was fixed during the audit.

- **All MEDIUM findings have been resolved:**

  - SEC-07 (request line length): Explicit `MAX_REQUEST_LINE_SIZE` check added with 414 response.
  - SEC-08 (root container): Non-root `inference` user added to both Dockerfiles with proper group memberships.
  - SEC-09 (rate limiter unbounded): Lazy cleanup every 5 minutes removes stale entries.

- **All LOW findings have been resolved:**

  - SEC-10 (Content-Length parsing): Proper error handling with 400 Bad Request response.
  - SEC-11 (log injection): `_sanitize_log_field()` strips control characters from log entries.
  - SEC-12 (metrics auth): `METRICS_AUTH_ENABLED` flag allows operators to require auth on `/metrics`.
  - SEC-13 (backend response headers): `MAX_RESPONSE_HEADER_SIZE` enforced with 502 on overflow.

- **All INFO findings have been resolved:**

  - SEC-14 (EXTRA_ARGS): Startup warning logged when non-empty.
  - SEC-15 (DEBUG_SHELL): Sensitive environment variables filtered from debug output.
  - SEC-16 (backend key disclosure): Reduced to first 8 characters only.

- **The security architecture is sound:** Defense-in-depth (frontend auth + backend auth + localhost binding),
  fail-closed defaults, constant-time comparisons, secure key lifecycle management, and proper input validation
  throughout.

All findings from this and prior audits (SEC-01 through SEC-16) have been resolved. The codebase exceeds the v1 release
gate requirement for security with zero open findings.
