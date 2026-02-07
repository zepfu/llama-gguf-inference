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
├── CONTRIBUTING.md
├── DEBUGGING.md
├── ⭐ Dockerfile
├── ⭐ Makefile
├── ⭐ README.md
├── REPO_MAP.md
├── api_keys.txt.example
├── pyproject.toml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── AUTHENTICATION.md
│   ├── CONFIGURATION.md
│   ├── TESTING.md
│   ├── TROUBLESHOOTING.md
│   ├── conf.py
│   └── index.rst
└── scripts/
    ├── ⭐ README.md
    ├── ⭐ auth.py
    ├── ⭐ gateway.py
    ├── health_server.py
    ├── ⭐ start.sh
    ├── dev/
    │   ├── check_changelog.sh
    │   ├── check_env_completeness.sh
    │   ├── check_repo_map.sh
    │   ├── generate_api_docs.sh
    │   └── setup.sh
    ├── diagnostics/
    │   ├── ⭐ README.md
    │   └── collect.sh
    └── tests/
        ├── test_auth.sh
        ├── test_docker_integration.sh
        ├── test_health.sh
        ├── test_integration.sh
        └── test_runner.sh
```

## Key Files

### Entry Points

**`start.sh`**

### Important Files

**`Dockerfile`**

**`Makefile`**

**`README.md`**
  - llama-gguf-inference

**`README.md`**
  - Scripts Documentation

**`auth.py`**

**`gateway.py`**

**`README.md`**
  - Diagnostics

## Configuration Files

| File | Description |
|------|-------------|
| `Dockerfile` | *No description* |
| `Makefile` | *No description* |
| `pyproject.toml` | *No description* |

## Documentation

- **`CHANGELOG.md`**
  - Changelog
- **`CONTRIBUTING.md`**
- **`DEBUGGING.md`**
  - Debugging Guide
- **`README.md`**
  - llama-gguf-inference
- **`REPO_MAP.md`**
  - Repository Structure
- **`ARCHITECTURE.md`**
  - Architecture
- **`AUTHENTICATION.md`**
  - Authentication Guide
- **`CONFIGURATION.md`**
  - Configuration Guide
- **`TESTING.md`**
  - Testing Guide
- **`TROUBLESHOOTING.md`**
  - Troubleshooting Guide
- **`README.md`**
  - Scripts Documentation
- **`README.md`**
  - Diagnostics

## Scripts

| Script | Description |
|--------|-------------|
| `auth.py` | *No description* |
| `gateway.py` | *No description* |
| `health_server.py` | health_server.py — Ultra-lightweight health check server for RunPod |
| `check_changelog.sh` | *No description* |
| `check_env_completeness.sh` | *No description* |
| `check_repo_map.sh` | *No description* |
| `generate_api_docs.sh` | *No description* |
| `setup.sh` | *No description* |
| `collect.sh` | *No description* |
| `test_auth.sh` | *No description* |
| `test_docker_integration.sh` | *No description* |
| `test_health.sh` | *No description* |
| `test_integration.sh` | *No description* |
| `test_runner.sh` | *No description* |

---

*This file is auto-generated. Do not edit manually.*

*Last updated: /home/zepfu/projects/llama-gguf-inference*
