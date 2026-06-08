# Architecture (Auto-Generated)

**Generated:** 2026-06-08 10:41:29 **Project:** /home/runner/work/llama-gguf-inference/llama-gguf-inference

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
    Idle --> TestExceptionDuringRequestHandledGracefully
    TestExceptionDuringRequestHandledGracefully --> TestOptionsRequestHandled
    TestOptionsRequestHandled --> TestTimeoutDuringRequestHandledGracefully
    TestTimeoutDuringRequestHandledGracefully --> TestWriterCloseFailureHandled
    TestWriterCloseFailureHandled --> [*]
    Idle --> TestSighupHandlerCallsReload
    TestSighupHandlerCallsReload --> TestSighupHandlerLogsErrorOnFailure
    TestSighupHandlerLogsErrorOnFailure --> TestSighupHandlerNoAuthModule
    TestSighupHandlerNoAuthModule --> [*]
```

## Sequence Diagram

*Sequence diagram not applicable for this codebase.*

## Architecture Diagram

```mermaid
architecture-beta
    group docs(cloud)[Docs]
        service docs_conf(server)[conf] in docs
    end
    group tests(cloud)[Tests]
        service tests_test_gateway(server)[test_gateway] in tests
        service tests_conftest(server)[conftest] in tests
        service tests_test_key_mgmt(server)[test_key_mgmt] in tests
    end
    group scripts(cloud)[Scripts]
        service scripts_auth(server)[auth] in scripts
        service scripts_health_server(server)[health_server] in scripts
        service scripts_gateway(server)[gateway] in scripts
    end
```

## Er Diagram

*Er diagram not applicable for this codebase.*

## Class Diagram

```mermaid
classDiagram
    class tests_test_gateway_TestGetCorsHeaders {
        +test_cors_disabled_returns_empty(monkeypatch)
        +test_cors_wildcard_returns_star(monkeypatch)
        +test_cors_specific_origin_allowed(monkeypatch)
        +test_cors_specific_origin_denied(monkeypatch)
        +test_cors_multiple_origins(monkeypatch)
    }
    class tests_test_gateway_TestBuildCorsHeaderStr {
        +test_disabled_returns_empty_string(monkeypatch)
        +test_enabled_returns_crlf_joined(monkeypatch)
        +test_denied_origin_returns_empty(monkeypatch)
    }
    class tests_test_gateway_TestCorsEnabled {
        +test_disabled_when_empty(monkeypatch)
        +test_enabled_with_origin(monkeypatch)
        +test_wildcard_detected(monkeypatch)
    }
    class tests_test_gateway_TestWantsPrometheus {
        +test_empty_accept(monkeypatch)
        +test_json_accept(monkeypatch)
        +test_text_plain_accept(monkeypatch)
        +test_openmetrics_accept(monkeypatch)
        +test_mixed_accept_with_text_plain(monkeypatch)
    }
    class tests_test_gateway_TestMetricsToPrometheus {
        +test_default_metrics(monkeypatch)
        +test_metrics_with_values(monkeypatch)
        +test_prometheus_format_lines(monkeypatch)
        +test_uptime_reflects_start_time(monkeypatch)
    }
    class tests_test_gateway_TestMetricsToDict {
        +test_default_values(monkeypatch)
        +test_values_preserved(monkeypatch)
    }
    class tests_test_gateway_TestOptionsHandling {
        +test_options_response_format_with_cors(monkeypatch)
        +test_options_response_without_cors(monkeypatch)
    }
    class tests_test_gateway_TestHandlePingCors {
        +test_ping_with_cors(monkeypatch)
        +test_ping_without_cors(monkeypatch)
    }
    class tests_test_gateway_TestHandleMetricsFormats {
        +test_metrics_json_default(monkeypatch)
        +test_metrics_prometheus_text_plain(monkeypatch)
        +test_metrics_prometheus_openmetrics(monkeypatch)
        +test_metrics_json_with_application_json(monkeypatch)
        +test_metrics_with_cors(monkeypatch)
    }
    class tests_test_gateway_TestQueueConfig {
        +test_default_max_concurrent(monkeypatch)
        +test_custom_max_concurrent(monkeypatch)
        +test_default_max_queue_size(monkeypatch)
        +test_custom_max_queue_size(monkeypatch)
        +test_semaphore_created_with_correct_value(monkeypatch)
    }
    class tests_test_gateway_TestQueueFullResponse {
        +test_503_status_line(monkeypatch)
        +test_retry_after_header(monkeypatch)
        +test_json_body_format(monkeypatch)
        +test_content_type_json(monkeypatch)
        +test_cors_headers_included(monkeypatch)
    }
    class tests_test_gateway_TestQueueMetrics {
        +test_queue_fields_in_to_dict(monkeypatch)
        +test_queue_rejections_in_to_dict(monkeypatch)
        +test_queue_wait_time_in_to_dict(monkeypatch)
        +test_queue_depth_in_prometheus(monkeypatch)
        +test_queue_rejections_in_prometheus(monkeypatch)
    }
    class tests_test_gateway_TestHealthQueueInfo {
        +test_health_contains_queue_section(monkeypatch)
        +test_health_queue_active_reflects_semaphore(monkeypatch)
        +test_health_queue_waiting_reflects_depth(monkeypatch)
    }
    class tests_test_gateway_TestConcurrencyLimiting {
        +test_semaphore_limits_concurrent_proxy_calls(monkeypatch)
        +test_queue_rejection_when_full(monkeypatch)
        +test_queue_rejection_increments_metric(monkeypatch)
        +test_health_endpoints_bypass_queue(monkeypatch)
        +test_unlimited_queue_never_rejects(monkeypatch)
    }
    class tests_test_gateway_TestRequestBodySizeConfig {
        +test_default_max_request_body_size(monkeypatch)
        +test_custom_max_request_body_size(monkeypatch)
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
      auth
      health_server
      gateway
      key_mgmt
      benchmark
    tests
      test_gateway
      conftest
      test_key_mgmt
      test_auth
      __init__
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
    docs[Documentation]
    release[Release]
    ci[CI]
    cd[CD]
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
