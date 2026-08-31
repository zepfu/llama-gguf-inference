# Repository Structure

> Auto-generated repository map

## Table of Contents

- [Directory Tree](#directory-tree)
- [Key Files](#key-files)
- [Configuration Files](#configuration-files)
- [Documentation](#documentation)
- [Scripts](#scripts)

## Directory Tree

```
llama-gguf-inference/
├── CHANGELOG.md
├── CLAUDE.md
├── CONTRIBUTING.md
├── DEBUGGING.md
├── ⭐ Dockerfile
├── Dockerfile.cpu
├── ⭐ Makefile
├── ⭐ README.md
├── api_keys.txt.example
├── ⭐ docker-compose.yml
├── pyproject.toml
├── repo.mk
├── repo.mk.example
├── docs/
│   ├── API_REFERENCE.md
│   ├── AUTHENTICATION.md
│   ├── CONFIGURATION.md
│   ├── DEPLOYMENT.md
│   ├── LIVE_TESTING_GUIDE.md
│   ├── MIGRATION.md
│   ├── SECURITY_AUDIT.md
│   ├── TESTING.md
│   ├── TROUBLESHOOTING.md
│   ├── conf.py
│   ├── index.rst
│   ├── requirements.txt
│   └── auto/
│       ├── ARCHITECTURE_AUTO.md
│       ├── CHANGELOG.md
│       ├── REPO_MAP.md
│       └── WORKFLOW_REGISTRY.md
├── scripts/
│   ├── ⭐ README.md
│   ├── ⭐ auth.py
│   ├── benchmark.py
│   ├── ⭐ gateway.py
│   ├── health_server.py
│   ├── key_mgmt.py
│   ├── ⭐ start.sh
│   ├── dev/
│   │   ├── check_changelog.sh
│   │   ├── check_repo_map.sh
│   │   ├── generate_api_docs.sh
│   │   └── setup.sh
│   ├── diagnostics/
│   │   ├── ⭐ README.md
│   │   └── collect.sh
│   └── tests/
│       ├── test_auth.sh
│       ├── test_docker_integration.sh
│       ├── test_health.sh
│       ├── test_integration.sh
│       └── test_runner.sh
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_auth.py
    ├── test_benchmark.py
    ├── test_gateway.py
    ├── test_health_server.py
    └── test_key_mgmt.py
```

## Key Files

### Entry Points

**`start.sh`**

### Important Files

**`Dockerfile`**

**`Makefile`**

**`README.md`**

- llama-gguf-inference

**`docker-compose.yml`**

- \==============================================================================

**`README.md`**

- Scripts Documentation

**`auth.py`**

**`gateway.py`**

**`README.md`**

- Diagnostics

## Configuration Files

| File                 | Description                                                                    |
| -------------------- | ------------------------------------------------------------------------------ |
| `Dockerfile`         | *No description*                                                               |
| `Makefile`           | *No description*                                                               |
| `docker-compose.yml` | ============================================================================== |
| `pyproject.toml`     | *No description*                                                               |

## Documentation

- **`CHANGELOG.md`**
  - Changelog
- **`CLAUDE.md`**
  - CLAUDE.md — llama-gguf-inference
- **`CONTRIBUTING.md`**
- **`DEBUGGING.md`**
  - Debugging Guide
- **`README.md`**
  - llama-gguf-inference
- **`API_REFERENCE.md`**
  - API Reference
- **`AUTHENTICATION.md`**
  - Authentication Guide
- **`CONFIGURATION.md`**
  - Configuration Guide
- **`DEPLOYMENT.md`**
  - Deployment Guide
- **`LIVE_TESTING_GUIDE.md`**
  - Live Testing Guide — v1.0.0-rc.1
- **`MIGRATION.md`**
  - Migration Guide
- **`SECURITY_AUDIT.md`**
  - Security Audit Report — llama-gguf-inference v1
- **`TESTING.md`**
  - Testing Guide
- **`TROUBLESHOOTING.md`**
  - Troubleshooting Guide
- **`ARCHITECTURE_AUTO.md`**
  - Architecture (Auto-Generated)
- **`CHANGELOG.md`**
  - Changelog
- **`REPO_MAP.md`**
  - Repository Structure
- **`WORKFLOW_REGISTRY.md`**
  - Workflow Registry & Tool Coverage
- **`README.md`**
  - Scripts Documentation
- **`README.md`**
  - Diagnostics

## Scripts

| Script                       | Description                                                         |
| ---------------------------- | ------------------------------------------------------------------- |
| `auth.py`                    | *No description*                                                    |
| `benchmark.py`               | *No description*                                                    |
| `gateway.py`                 | *No description*                                                    |
| `health_server.py`           | health_server.py — Ultra-lightweight health check server for RunPod |
| `key_mgmt.py`                | *No description*                                                    |
| `check_changelog.sh`         | *No description*                                                    |
| `check_repo_map.sh`          | *No description*                                                    |
| `generate_api_docs.sh`       | *No description*                                                    |
| `setup.sh`                   | *No description*                                                    |
| `collect.sh`                 | *No description*                                                    |
| `test_auth.sh`               | *No description*                                                    |
| `test_docker_integration.sh` | *No description*                                                    |
| `test_health.sh`             | *No description*                                                    |
| `test_integration.sh`        | *No description*                                                    |
| `test_runner.sh`             | *No description*                                                    |

______________________________________________________________________

*This file is auto-generated. Do not edit manually.*

*Last updated: /home/runner/work/llama-gguf-inference/llama-gguf-inference*
