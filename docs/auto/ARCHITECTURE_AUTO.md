# Architecture (Auto-Generated)

**Generated:** 2026-04-06 10:12:40 **Project:** /home/runner/work/llama-gguf-inference/llama-gguf-inference

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
    Init --> main[main]
    main --> End([End])
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
    group scripts(cloud)[Scripts]
        service scripts_benchmark(server)[benchmark] in scripts
        service scripts_auth(server)[auth] in scripts
        service scripts_health_server(server)[health_server] in scripts
    end
    group tests(cloud)[Tests]
        service tests_test_gateway(server)[test_gateway] in tests
        service tests___init__(server)[__init__] in tests
        service tests_conftest(server)[conftest] in tests
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
    class scripts_auth_APIKeyValidator {
        +__init__()
        +_load_keys()
        +_parse_key_metadata()
        +validate(headers)
        +_is_key_expired(key_id)
    }
    class scripts_health_server_HealthHandler {
        +do_GET()
        +log_message(format)
    }
    class scripts_gateway_Metrics {
        +requests_total
        +requests_success
        +requests_error
        +requests_active
        +requests_authenticated
        +to_dict()
        +to_prometheus()
    }
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
      benchmark
      auth
      health_server
      key_mgmt
      gateway
    tests
      test_gateway
      __init__
      conftest
      test_key_mgmt
      test_benchmark
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
    release[Release]
    cd[CD]
    docs[Documentation]
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
