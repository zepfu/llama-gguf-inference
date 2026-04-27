# Architecture (Auto-Generated)

**Generated:** 2026-04-27 09:52:22 **Project:** /home/runner/work/llama-gguf-inference/llama-gguf-inference

## Overview

Analyzed **13** Python modules containing:

- **138** classes
- **713** functions
- **0** async functions

### Detected Patterns

- ❌ **Api**
- ❌ **Async**
- ✅ **Cli**
- ❌ **Database**
- ❌ **Dataclass**
- ❌ **Orm**
- ✅ **Server**
- ✅ **State Machine**
- ✅ **Workflows**

## Flowchart Diagram

```mermaid
flowchart TD
    Start([Start]) --> Init[Initialize]
    Init --> testuptimereflectsstarttime[test_uptime_reflects_start_time]
    Init --> testqueuedepthstartsatzero[test_queue_depth_starts_at_zero]
    testqueuedepthstartsatzero --> End([End])
```

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> TestLogAccessHandlesPermissionError
    TestLogAccessHandlesPermissionError --> [*]
    Idle --> TestReloadHandlesEmptyFile
    TestReloadHandlesEmptyFile --> TestReloadPreservesRateLimiterState
    TestReloadPreservesRateLimiterState --> [*]
```

## Sequence Diagram

*Sequence diagram not applicable for this codebase.*

## Architecture Diagram

```mermaid
architecture-beta
    group tests(cloud)[Tests]
        service tests_test_auth(server)[test_auth] in tests
        service tests_test_gateway(server)[test_gateway] in tests
        service tests_test_health_server(server)[test_health_server] in tests
    end
    group scripts(cloud)[Scripts]
        service scripts_gateway(server)[gateway] in scripts
        service scripts_auth(server)[auth] in scripts
        service scripts_benchmark(server)[benchmark] in scripts
    end
    group docs(cloud)[Docs]
        service docs_conf(server)[conf] in docs
    end
```

## Er Diagram

*Er diagram not applicable for this codebase.*

## Class Diagram

```mermaid
classDiagram
    class tests_test_auth_TestKeyFormatValidation {
        +test_valid_key(noauth_env, monkeypatch)
        +test_key_too_short(noauth_env, monkeypatch)
        +test_key_too_long(noauth_env, monkeypatch)
        +test_key_min_length(noauth_env, monkeypatch)
        +test_key_max_length(noauth_env, monkeypatch)
    }
    class tests_test_auth_TestLoadKeys {
        +test_load_valid_keys(keys_file, monkeypatch)
        +test_load_disabled(keys_file, monkeypatch)
        +test_load_missing_file(monkeypatch)
        +test_load_empty_file(empty_keys_file, monkeypatch)
        +test_load_with_comments(tmp_path, monkeypatch)
    }
    class tests_test_auth_TestValidate {
        +test_auth_disabled(monkeypatch)
        +test_no_keys_configured_rejects(monkeypatch)
        +test_missing_auth_header(keys_file, monkeypatch)
        +test_empty_auth_header(keys_file, monkeypatch)
        +test_bearer_prefix(keys_file, monkeypatch)
    }
    class tests_test_auth_TestRateLimiting {
        +test_under_limit(keys_file, monkeypatch)
        +test_over_limit(keys_file, monkeypatch)
        +test_different_keys_separate_limits(keys_file, monkeypatch)
        +test_rate_limit_resets(keys_file, monkeypatch)
    }
    class tests_test_auth_TestMetrics {
        +test_empty_metrics(noauth_env, monkeypatch)
        +test_metrics_after_requests(keys_file, monkeypatch)
    }
    class tests_test_auth_TestAuthenticateRequest {
        +test_authenticate_success_returns_key_id(keys_file, monkeypatch)
        +test_authenticate_failure_sends_401(keys_file, monkeypatch)
        +test_authenticate_missing_header_sends_401(keys_file, monkeypatch)
        +test_authenticate_rate_limited_sends_429(keys_file, monkeypatch)
        +test_authenticate_disabled_returns_auth_disabled(monkeypatch)
    }
    class tests_test_auth_TestSendRateLimitError {
        +test_429_response_format(monkeypatch)
    }
    class tests_test_auth_TestLogAccess {
        +test_log_access_writes_to_file(monkeypatch, tmp_path)
        +test_log_access_creates_directory(monkeypatch, tmp_path)
        +test_log_access_handles_permission_error(monkeypatch, capsys)
    }
    class tests_test_auth_TestLoadKeysEdgeCases {
        +test_load_keys_file_read_exception(monkeypatch, tmp_path)
        +test_load_keys_empty_key_id(tmp_path, monkeypatch)
        +test_load_keys_invalid_api_key_format(tmp_path, monkeypatch)
    }
    class tests_test_auth_TestValidateEdgeCases {
        +test_empty_api_key_after_bearer_strip(keys_file, monkeypatch)
        +test_constant_time_comparison(keys_file, monkeypatch)
        +test_record_request_appends_timestamp(keys_file, monkeypatch)
        +test_check_rate_limit_cleans_old_entries(keys_file, monkeypatch)
    }
    class tests_test_auth_TestSanitizeLogField {
        +test_clean_value_unchanged(monkeypatch)
        +test_newline_replaced(monkeypatch)
        +test_carriage_return_replaced(monkeypatch)
        +test_tab_replaced(monkeypatch)
        +test_pipe_replaced(monkeypatch)
    }
    class tests_test_auth_TestPerKeyRateLimits {
        +test_per_key_rate_limit_loaded(tmp_path, monkeypatch)
        +test_per_key_rate_limit_enforced(tmp_path, monkeypatch)
        +test_per_key_higher_limit(tmp_path, monkeypatch)
        +test_default_rate_limit_without_per_key(tmp_path, monkeypatch)
        +test_invalid_rate_limit_skips_key(tmp_path, monkeypatch)
    }
    class tests_test_auth_TestKeyExpiration {
        +test_expired_key_rejected(tmp_path, monkeypatch)
        +test_non_expired_key_accepted(tmp_path, monkeypatch)
        +test_no_expiration_means_never_expires(tmp_path, monkeypatch)
        +test_empty_expiration_means_never_expires(tmp_path, monkeypatch)
        +test_invalid_expiration_skips_key(tmp_path, monkeypatch)
    }
    class tests_test_auth_TestRateLimiterCleanup {
        +test_cleanup_removes_stale_entries(keys_file, monkeypatch)
        +test_cleanup_keeps_active_entries(keys_file, monkeypatch)
        +test_cleanup_skipped_within_interval(keys_file, monkeypatch)
        +test_cleanup_triggered_by_check_rate_limit(keys_file, monkeypatch)
        +test_cleanup_mixed_stale_and_active(keys_file, monkeypatch)
    }
    class tests_test_auth_TestBackwardCompatibility {
        +test_simple_key_format(tmp_path, monkeypatch)
        +test_key_with_rate_limit_only(tmp_path, monkeypatch)
        +test_key_with_expiration_only(tmp_path, monkeypatch)
        +test_key_with_all_fields(tmp_path, monkeypatch)
        +test_mixed_formats_in_same_file(tmp_path, monkeypatch)
    }
```

## Journey Diagram

*Journey diagram not applicable for this codebase.*

## Mindmap Diagram

```mermaid
mindmap
  root((Project))
    docs
      conf
    scripts
      gateway
      auth
      benchmark
      key_mgmt
      health_server
    tests
      test_auth
      test_gateway
      test_health_server
      conftest
      test_key_mgmt
```

## Workflow Pipeline Diagram

```mermaid
flowchart TD

    Push -->|Doc Changes| Docs[Build Docs]
    Docs --> docs[Documentation]

    Tag[Release Tag] --> Release[Release Process]
    Release --> release[Release]
```

## Workflow Triggers Diagram

```mermaid
graph TD
    ci[CI]
    docs[Documentation]
    cd[CD]
    release[Release]
```

## Workflow Jobs Diagram

```mermaid
flowchart LR
    subgraph ci[CI]
        pre_commit[pre-commit]
        python_standards[python-standards]
        shell_standards[shell-standards]
        quality_checks[quality-checks]
        config_validation[config-validation]
        makefile_validation[makefile-validation]
        unit_tests[unit-tests]
        validate_project[validate-project]
        docker_build[docker-build]
        integration_test[integration-test]
        python_standards --> unit_tests
        config_validation --> validate_project
        python_standards --> docker_build
        shell_standards --> docker_build
        quality_checks --> docker_build
        validate_project --> docker_build
        docker_build --> integration_test
    end
```

## Development Workflows

### GitHub Workflows Summary

| Workflow      | Triggers | Jobs                                             |
| ------------- | -------- | ------------------------------------------------ |
| CD            |          | publish-cuda, publish-cpu                        |
| CI            |          | pre-commit, python-standards, shell-standards... |
| Documentation |          | build-docs, validate-rtd, update-docs            |
| Release       |          | prepare, release-cuda, release-cpu...            |

## Module Summary

### `docs.conf`

- **Classes:** 0
- **Functions:** 0
- **Async Functions:** 0

### `scripts.auth`

auth.py - API Key Authentication Module for Gateway

File-based authentication system that enforces API keys while maintaining OpenAI compatibility. Uses key_id:api_key
format for easy management and ...

- **Classes:** 1
- **Functions:** 13
- **Async Functions:** 0

### `scripts.benchmark`

benchmark.py -- Performance benchmarking for llama-gguf-inference gateway.

Measures two categories of performance:

1. Gateway overhead (proxy latency)
   - /ping latency (gateway-only, no backend in...

- **Classes:** 0
- **Functions:** 11
- **Async Functions:** 0

### `scripts.gateway`

gateway.py – Async HTTP gateway for llama.cpp llama-server

Features:

- API key authentication with health endpoint exemption

- Proper SSE/streaming support for chat completions

- /ping and /health en...

- **Classes:** 1

- **Functions:** 11

- **Async Functions:** 0

### `scripts.health_server`

health_server.py — Ultra-lightweight health check server for RunPod

This server runs on PORT_HEALTH (separate from the main gateway) and provides a minimal health check endpoint that
doesn't interact...

- **Classes:** 1
- **Functions:** 3
- **Async Functions:** 0

### `scripts.key_mgmt`

key_mgmt.py - API Key Management CLI for llama-gguf-inference

Standalone CLI tool for managing API keys used by the gateway's authentication system. Keys are stored in a flat file
with the format: ...

- **Classes:** 0
- **Functions:** 16
- **Async Functions:** 0

### `tests.__init__`

- **Classes:** 0
- **Functions:** 0
- **Async Functions:** 0

### `tests.conftest`

Shared test fixtures for auth module tests.

- **Classes:** 0
- **Functions:** 4
- **Async Functions:** 0

### `tests.test_auth`

Unit tests for scripts/auth.py - API Key Authentication Module.

- **Classes:** 28
- **Functions:** 117
- **Async Functions:** 0

### `tests.test_benchmark`

Unit tests for scripts/benchmark.py -- Benchmark module.

- **Classes:** 19
- **Functions:** 50
- **Async Functions:** 0

### `tests.test_gateway`

Unit tests for scripts/gateway.py - Gateway module (CORS, Prometheus metrics, queue).

- **Classes:** 161
- **Functions:** 357
- **Async Functions:** 0

### `tests.test_health_server`

Unit tests for scripts/health_server.py -- Health check server.

- **Classes:** 3
- **Functions:** 11
- **Async Functions:** 0

### `tests.test_key_mgmt`

Unit tests for scripts/key_mgmt.py - API Key Management CLI.

- **Classes:** 29
- **Functions:** 120
- **Async Functions:** 0

______________________________________________________________________

*Generated by: `generate_architecture.py` from repo-standards*
