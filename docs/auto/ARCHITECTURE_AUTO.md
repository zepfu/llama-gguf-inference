# Architecture (Auto-Generated)

**Generated:** 2026-10-26 15:57:16 **Project:** /home/runner/work/llama-gguf-inference/llama-gguf-inference

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
    Init --> testmainstartsserver[test_main_starts_server]
    Init --> testmainprintsstartupmessage[test_main_prints_startup_message]
    Init --> testmainhandleskeyboardinterrupt[test_main_handles_keyboard_interrupt]
    testmainhandleskeyboardinterrupt --> End([End])
```

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> MakeHandler
    MakeHandler --> [*]
    Idle --> TestMainHandlesKeyboardInterrupt
    TestMainHandlesKeyboardInterrupt --> [*]
```

## Sequence Diagram

*Sequence diagram not applicable for this codebase.*

## Architecture Diagram

```mermaid
architecture-beta
    group tests(cloud)[Tests]
        service tests_test_benchmark(server)[test_benchmark] in tests
        service tests_test_health_server(server)[test_health_server] in tests
        service tests_test_auth(server)[test_auth] in tests
    end
    group docs(cloud)[Docs]
        service docs_conf(server)[conf] in docs
    end
    group scripts(cloud)[Scripts]
        service scripts_health_server(server)[health_server] in scripts
        service scripts_key_mgmt(server)[key_mgmt] in scripts
        service scripts_benchmark(server)[benchmark] in scripts
    end
```

## Er Diagram

*Er diagram not applicable for this codebase.*

## Class Diagram

```mermaid
classDiagram
    class tests_test_benchmark_TestPercentile {
        +test_empty_data()
        +test_single_value()
        +test_p50_even_count()
        +test_p50_odd_count()
        +test_p95()
    }
    class tests_test_benchmark_TestComputeStats {
        +test_empty_input()
        +test_single_value()
        +test_multiple_values()
        +test_all_keys_present()
        +test_all_same_values()
    }
    class tests_test_benchmark_TestParseSSETokens {
        +test_empty_input()
        +test_done_sentinel()
        +test_single_token()
        +test_multiple_tokens()
        +test_empty_delta()
    }
    class tests_test_benchmark_TestCountTokensApprox {
        +test_empty()
        +test_single_word()
        +test_multiple_words()
        +test_extra_whitespace()
    }
    class tests_test_benchmark_TestFormatTextOutput {
        +test_gateway_only()
        +test_inference_only()
        +test_both()
        +test_none_both()
    }
    class tests_test_benchmark_TestFormatJsonOutput {
        +test_gateway_only()
        +test_inference_only()
        +test_valid_json()
        +test_empty_both()
    }
    class tests_test_benchmark_TestBuildParser {
        +test_required_url()
        +test_minimal_args()
        +test_all_args()
        +test_invalid_output_format()
    }
    class tests_test_benchmark_TestParseUrl {
        +test_http_default_port()
        +test_https_default_port()
        +test_custom_port()
        +test_root_path()
        +test_query_string()
    }
    class tests_test_benchmark_TestFormatHelpers {
        +test_fmt_ms()
        +test_fmt_s()
    }
    class tests_test_benchmark_TestOpenConnection {
    }
    class tests_test_benchmark_TestSendRequest {
    }
    class tests_test_benchmark_TestReadStatusAndHeaders {
    }
    class tests_test_benchmark_TestBenchEndpoint {
    }
    class tests_test_benchmark_TestRunGatewayBenchmark {
    }
    class tests_test_benchmark_TestInferenceRequest {
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
      health_server
      key_mgmt
      benchmark
      gateway
      auth
    tests
      test_benchmark
      test_health_server
      test_auth
      test_key_mgmt
      conftest
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
