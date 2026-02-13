# CONTRACTS.md — Cross-Agent Interface Contracts

> **Shared source of truth for boundaries between agents.** When two or more agents must produce/consume the same
> interface (API response shape, webhook payload, event format, shared type, config schema), the contract is defined
> here BEFORE either agent begins implementation.
>
> PRODUCT-OWNER approves contracts. TECH-LEAD enforces them during dispatch and review. Changes require PRODUCT-OWNER
> approval and are logged in the changelog at the bottom.

______________________________________________________________________

## How Contracts Work

### Lifecycle

1. **PRODUCT-OWNER identifies a coordination boundary** during planning (typically from PHASES.md execution streams or
   when multiple agents touch the same interface). TECH-LEAD may also escalate the need for a contract during dispatch.
1. **PRODUCT-OWNER drafts the contract** with the producing agent's input (or the coordinator dispatches to
   API-ARCHITECT for complex contracts via TECH-LEAD).
1. **Contract is written here** with status `DRAFT`.
1. **Both sides confirm** — producer and consumer agents acknowledge the contract in their dispatch response. Status
   moves to `ACTIVE`.
1. **Agents implement against the contract**, not against assumptions or each other's code.
1. **Changes go through PRODUCT-OWNER** — if an agent discovers the contract needs to change during implementation, they
   propose the change (not apply it). PRODUCT-OWNER evaluates impact on the other side, updates the contract, and the
   coordinator notifies affected agents. Logged in the changelog.
1. **Contract is marked `VERIFIED`** once both sides have integration tests passing against it.
1. **Contract moves to `ARCHIVED`** when the feature is stable and the interface is unlikely to change.

### When to Create a Contract

- An API endpoint's response shape is consumed by a frontend component, plugin, or external integration
- A webhook/event payload is produced by one agent and handled by another
- A shared type or interface is used across packages/modules owned by different agents
- A database query result is shaped by one agent and consumed by another's service layer
- A configuration format is written by one agent and read by another

### When NOT Needed

- Work entirely within one agent's ownership boundary
- Internal implementation details that don't cross agent boundaries
- Standard patterns already fully defined in GUIDELINES.md (e.g., error response envelope, pagination format)

______________________________________________________________________

## Active Contracts

### C-001: Gateway ↔ llama-server Proxy Interface

**Status:** ACTIVE (pre-existing, documenting current behavior) **Producer:** llama-server (llama.cpp binary)
**Consumer(s):** BACKEND-LEAD (gateway.py) **Phase:** Phase 1 (established) **Related files:** `scripts/gateway.py`

**Interface:**

```
Gateway forwards requests to llama-server at:
  http://{BACKEND_HOST}:{PORT_BACKEND}{original_path}

Headers added by gateway:
  Authorization: Bearer {BACKEND_API_KEY}    (auto-generated at startup)
  Content-Type: application/json             (pass-through from client)

Supported paths (proxied as-is):
  POST /v1/chat/completions
  POST /v1/completions
  GET  /v1/models

Response handling:
  Non-streaming: Read full response body, forward to client with original status code
  Streaming:     Pass-through SSE chunks (data: {JSON}\n\n) until data: [DONE]\n\n
```

**Rules/Invariants:**

- Gateway MUST NOT modify request or response bodies
- Gateway MUST add backend API key to proxied requests
- Gateway MUST handle connection errors gracefully (return 502/503 to client)
- Gateway MUST respect `REQUEST_TIMEOUT` for all proxied requests
- Streaming responses MUST be forwarded chunk-by-chunk (no buffering)

**Notes:**

- llama-server's API format is defined by llama.cpp upstream — we consume, not define
- Backend API key is generated fresh on each container start in `start.sh`

______________________________________________________________________

### C-002: Authentication Interface

**Status:** ACTIVE (pre-existing, documenting current behavior) **Producer:** SECURITY-ENGINEER (auth.py)
**Consumer(s):** BACKEND-LEAD (gateway.py) **Phase:** Phase 1 (established) **Related files:** `scripts/auth.py`,
`scripts/gateway.py`

**Interface:**

```python
# Auth module exports:
api_validator: ApiKeyValidator     # Singleton, loaded at startup
authenticate_request(writer, headers) -> Optional[str]
    # Returns key_id on success, None on failure (401 already sent)
log_access(method, path, key_id, status_code) -> None

# ApiKeyValidator interface:
validator.load_keys(filepath)      # Load keys from file
validator.validate(api_key) -> Optional[str]  # Returns key_id or None
validator.check_rate_limit(key_id) -> bool     # True if allowed
```

**Rules/Invariants:**

- `authenticate_request` sends 401 response directly on failure — caller just returns
- Rate limit check happens inside `authenticate_request`
- `AUTH_ENABLED=false` skips all validation — `authenticate_request` returns a default key_id
- Keys file format: one `key_id:api_key` per line, `#` comments, empty lines ignored

______________________________________________________________________

### C-003: Health Endpoints Contract

**Status:** ACTIVE (pre-existing, documenting current behavior) **Producer:** BACKEND-LEAD (gateway.py,
health_server.py) **Consumer(s):** Platform health checks (RunPod, Vast.ai), monitoring systems **Phase:** Phase 1
(established) **Related files:** `scripts/gateway.py`, `scripts/health_server.py`

**Interface:**

```
# Health Server (PORT_HEALTH, default 8001)
GET /{any_path}
  Response: 200 OK, Content-Type: text/plain, empty body
  Purpose: Platform health checks (scale-to-zero)
  Auth: None
  Backend interaction: None

# Gateway Health Endpoints (PORT, default 8000)
GET /ping
  Response: 200 OK, text/plain, body: "pong"
  Auth: None
  Backend interaction: None

GET /health
  Response: 200 OK, application/json
  Body: {"status": "ok"|"degraded", "backend": "up"|"down", "model": "loaded"|"loading"|"unknown"}
  Auth: None
  Backend interaction: Quick check to backend /health

GET /metrics
  Response: 200 OK, application/json
  Body: {"total_requests": int, "active_requests": int, "requests_by_path": {}, "errors_by_type": {}}
  Auth: None
  Backend interaction: None (reads in-memory counters)
```

**Rules/Invariants:**

- Health server on PORT_HEALTH MUST NEVER touch the backend — this enables scale-to-zero
- Gateway `/ping` MUST NEVER touch the backend
- Gateway `/health` MAY check backend status but MUST timeout quickly (HEALTH_TIMEOUT)
- All health endpoints MUST be exempt from authentication

______________________________________________________________________

## Draft Contracts

<!-- Contracts being defined but not yet confirmed by both sides -->

______________________________________________________________________

## Deprecated / Archived Contracts

<!-- Contracts that are no longer active. Keep for historical reference. -->

______________________________________________________________________

## Changelog

### 2026-02-12 — Initial documentation of existing contracts

**Contracts:** C-001, C-002, C-003 **Change:** Documented pre-existing interfaces as formal contracts **Reason:**
Project onboarding — formalizing interfaces that were implemented in Phase 1 **Impact:** No code changes — documentation
only **Notified:** All agents (initial setup)
