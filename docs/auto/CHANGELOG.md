# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Per-key rate limits: individual keys can override `MAX_REQUESTS_PER_MINUTE` via extended key format
  `key_id:api_key:rate_limit` ([567c25e])
- Key expiration/TTL: optional ISO 8601 timestamp in key format `key_id:api_key::expiration`, with relative format
  support (`30d`, `24h`, `60m`) in `key_mgmt.py --expires` ([567c25e])
- Hot-reload API keys via SIGHUP signal or `POST /reload` endpoint without gateway restart ([8d4072d])
- Configurable request timeout via `REQUEST_TIMEOUT` env var (default 300s), returns 504 on timeout ([635913b])
- Structured JSON logging via `LOG_FORMAT=json` environment variable ([86355ed])
- API reference documentation with full endpoint, error, and configuration coverage ([a66a2e7])
- CI coverage threshold gate at 70% minimum ([9ee3959])
- Migration guide and platform-specific deployment guides for RunPod, Vast.ai, and Lambda Labs ([75ec1bb])
- Live testing guide for end-to-end validation on GPU environments ([402dcab])

### Changed

- Optimized container image size by reducing Docker layers and cleaning up build artifacts ([3f8547f])
- Updated configuration, testing, and README documentation for current state ([1f1c759])
- Test suite expanded from 224 to 480 tests with overall coverage increased from 59% to 93% ([76240ec], [f0e28d3])

### Security

- Added request body size limits, header count limits, and CORS origin validation to prevent resource exhaustion and
  abuse ([a44d9da])
- Added backend response header size limit to prevent oversized responses (SEC-13) ([b25ffe2])
- Fixed SEC-07/10/11/12/14/15/16: request line size limit (414), malformed Content-Length (400), client header timeout,
  backend connect timeout, and removed `BACKEND_PORT` deprecation ([3a5206d])
- Run containers as non-root user (SEC-08) ([1e6d23b])
- Completed final v1 security audit with all findings addressed ([6a6401f])

## [1.0.0-rc.1] - 2026-02-13

First release candidate. Three-tier inference server with full OpenAI-compatible API, authentication, and multi-platform
deployment support.

**Docker images:**

- `ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1` (CUDA, amd64)
- `ghcr.io/zepfu/llama-gguf-inference:1.0.0-rc.1-cpu` (CPU, amd64 + arm64)

### Added

- Three-tier inference server architecture: health server (port 8001), gateway (port 8000), llama-server backend (port
  8080\) ([ee44290], [20a10bb])
- OpenAI-compatible API endpoints: `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/models` with SSE
  streaming support ([ee44290], [0850d56])
- File-based API key authentication with per-key rate limiting and constant-time comparison ([0850d56], [1283071])
- API key management CLI tool (`key_mgmt.py`) with generate, list, remove, and rotate commands ([cd42b99], closes [#8])
- Request queuing with configurable concurrency control (`MAX_CONCURRENT_REQUESTS`, `MAX_QUEUE_SIZE`) and 503 +
  Retry-After when queue is full ([4600a81], closes [#10])
- Configurable CORS headers via `CORS_ORIGINS` environment variable with proper preflight handling ([c8ca8d9], closes
  [#7])
- Prometheus-compatible metrics endpoint (`/metrics`) with text exposition format ([c8ca8d9])
- Scale-to-zero compatible health checks on a separate port that never touch the backend ([20a10bb])
- Automatic GPU detection and multi-platform support (RunPod, Vast.ai, Lambda Labs, local Docker) ([ee44290])
- Multi-arch Docker builds: CUDA (amd64) and CPU (amd64 + arm64) with docker-compose support ([707b819], closes [#9])
- Tag-triggered release workflow with multi-tag Docker image strategy (version, major.minor, major, latest) ([fe7e768],
  closes [#4])
- Comprehensive CI pipeline with linting (black, ruff, mypy, bandit, pydocstyle, hadolint, actionlint, checkmake),
  testing, and coverage reporting ([14a8925])
- Unit test suite for auth module: 33 pytest tests covering key validation, rate limiting, and metrics (78% auth.py
  coverage) ([fea0e43], closes [#2])
- Benchmarking script (`benchmark.py`) for measuring gateway overhead, TTFT, tokens/sec, and latency percentiles
  ([50707c0])
- ReadTheDocs documentation with Sphinx, auto-generated from source ([7f449b9], [634fa8c])
- Project coordination files for multi-agent development workflow ([c8c1972], closes [#6])
- Makefile with Docker build/run targets via `repo.mk` ([c6ef1ed])

### Changed

- Consolidated 5 CI/CD workflows into 3 streamlined workflows (`ci.yml`, `cd.yml`, `docs.yml`) ([14a8925])
- Completed branch migration from `master` to `main` as default branch ([bbd2152], closes [#1])
- Added type annotations and fixed variable shadowing in gateway and auth modules ([14a8925])
- Upgraded all pre-commit hooks to latest versions and added security-focused linters ([14a8925])

### Fixed

- Backend key generation in mock mode now produces valid format (`gateway-` prefix + 43 base64url chars), fixing CI
  integration tests ([a8944c9], fixes [#3])
- Pre-commit actionlint compatibility and integration test timing with retry-based container readiness checks
  ([4c4f83d], fixes [#3])
- Checkmake linting for `.mk` include fragments using correct `disabled = true` syntax ([f3ea83b])
- Docs workflow permissions (`pages:write`, `id-token:write`) for GitHub Pages deployment ([d8b45ee])
- Sphinx build warnings treated as errors resolved by fixing docstring formatting and toctree references ([166e39c])
- Multiple CI pipeline fixes for workflow triggers and job configuration ([3480412], [315a6c0], [63a3c5e], [f588262])

### Security

- Constant-time key comparison using `hmac.compare_digest` to prevent timing attacks ([1283071], closes [#5])
- Fail-closed authentication when `AUTH_ENABLED=true` but no keys are loaded ([1283071], closes [#5])
- Removed key count and per-key rate limit data from unauthenticated `/health` endpoint ([1283071], closes [#5])
- Rate limit errors now return 429 (not 401) without leaking `key_id` in error messages ([1283071], closes [#5])
- Removed per-key auth metrics from unauthenticated `/metrics` endpoint to prevent key_id disclosure ([5c65407])
- Added `Vary: Origin` header for non-wildcard CORS to prevent cache poisoning ([5c65407])
- General security hardening: non-root container user, no secrets in logs, `nosec` annotations for intentional bind-all
  addresses ([fb3989b], [14a8925])

______________________________________________________________________

<!-- Link references -->

[#1]: https://github.com/zepfu/llama-gguf-inference/issues/1
[#10]: https://github.com/zepfu/llama-gguf-inference/issues/10
[#2]: https://github.com/zepfu/llama-gguf-inference/issues/2
[#3]: https://github.com/zepfu/llama-gguf-inference/issues/3
[#4]: https://github.com/zepfu/llama-gguf-inference/issues/4
[#5]: https://github.com/zepfu/llama-gguf-inference/issues/5
[#6]: https://github.com/zepfu/llama-gguf-inference/issues/6
[#7]: https://github.com/zepfu/llama-gguf-inference/issues/7
[#8]: https://github.com/zepfu/llama-gguf-inference/issues/8
[#9]: https://github.com/zepfu/llama-gguf-inference/issues/9
[1283071]: https://github.com/zepfu/llama-gguf-inference/commit/128307144db378aa3395769090bcf3f126883b47
[3480412]: https://github.com/zepfu/llama-gguf-inference/commit/3480412db0d3e071c371bd85777783ce967ec939
[0850d56]: https://github.com/zepfu/llama-gguf-inference/commit/0850d5653ed9e50c9ac385e89d83ebc8688c9f04
[1.0.0-rc.1]: https://github.com/zepfu/llama-gguf-inference/releases/tag/v1.0.0-rc.1
[14a8925]: https://github.com/zepfu/llama-gguf-inference/commit/14a8925c1dde5844e3a770428d43d458a8bec766
[166e39c]: https://github.com/zepfu/llama-gguf-inference/commit/166e39cf1e76b1c56eac6306d04c2e6087c0a360
[1e6d23b]: https://github.com/zepfu/llama-gguf-inference/commit/1e6d23b
[1f1c759]: https://github.com/zepfu/llama-gguf-inference/commit/1f1c759
[20a10bb]: https://github.com/zepfu/llama-gguf-inference/commit/20a10bb30263d11ade3fab67b89115ddb2dc8333
[315a6c0]: https://github.com/zepfu/llama-gguf-inference/commit/315a6c02b3c6cf48fad996f94a68143bdd762108
[3a5206d]: https://github.com/zepfu/llama-gguf-inference/commit/3a5206d
[3f8547f]: https://github.com/zepfu/llama-gguf-inference/commit/3f8547fdf084d0efa66db791db737842ea6274c6
[402dcab]: https://github.com/zepfu/llama-gguf-inference/commit/402dcabf65dd1a8c69f3266a0c3bce0bca636e43
[4600a81]: https://github.com/zepfu/llama-gguf-inference/commit/4600a81d39ef96b2abc378846566f6b1c0b10769
[4c4f83d]: https://github.com/zepfu/llama-gguf-inference/commit/4c4f83d4a20858e77040ceca069bd152c40b5512
[50707c0]: https://github.com/zepfu/llama-gguf-inference/commit/50707c0390ae8c6cd24c32d2f326f6724ee2ed1b
[567c25e]: https://github.com/zepfu/llama-gguf-inference/commit/567c25e
[5c65407]: https://github.com/zepfu/llama-gguf-inference/commit/5c6540729d3aaa66e175789dc64734ef7742f260
[634fa8c]: https://github.com/zepfu/llama-gguf-inference/commit/634fa8c6aa207a87125583a3462ad23b9d923d9b
[635913b]: https://github.com/zepfu/llama-gguf-inference/commit/635913b
[63a3c5e]: https://github.com/zepfu/llama-gguf-inference/commit/63a3c5e7e771ee4e392b4358b15c12eeaf69187e
[6a6401f]: https://github.com/zepfu/llama-gguf-inference/commit/6a6401f
[707b819]: https://github.com/zepfu/llama-gguf-inference/commit/707b819de3076d8db03cce8e1f2078ba3734b9d8
[75ec1bb]: https://github.com/zepfu/llama-gguf-inference/commit/75ec1bb745481db09f27d7ef25b35a5c740e0950
[76240ec]: https://github.com/zepfu/llama-gguf-inference/commit/76240ec
[7f449b9]: https://github.com/zepfu/llama-gguf-inference/commit/7f449b90f2035a5a5280dfe03075373138be3f47
[86355ed]: https://github.com/zepfu/llama-gguf-inference/commit/86355ed
[8d4072d]: https://github.com/zepfu/llama-gguf-inference/commit/8d4072d
[9ee3959]: https://github.com/zepfu/llama-gguf-inference/commit/9ee3959
[a44d9da]: https://github.com/zepfu/llama-gguf-inference/commit/a44d9dad66bfd1e7ef9537bc056a9892f44e3f32
[a66a2e7]: https://github.com/zepfu/llama-gguf-inference/commit/a66a2e7
[a8944c9]: https://github.com/zepfu/llama-gguf-inference/commit/a8944c923fb71773a2f42264d5645c9cff466f2e
[b25ffe2]: https://github.com/zepfu/llama-gguf-inference/commit/b25ffe2
[bbd2152]: https://github.com/zepfu/llama-gguf-inference/commit/bbd2152db23b7552eb6145246e78fa4832cf69fb
[c6ef1ed]: https://github.com/zepfu/llama-gguf-inference/commit/c6ef1edd6221cb500a9d0cbadbc103632874eb5e
[c8c1972]: https://github.com/zepfu/llama-gguf-inference/commit/c8c197249e511258da3c2ab031aacd06135328bc
[c8ca8d9]: https://github.com/zepfu/llama-gguf-inference/commit/c8ca8d9f4bda27bf352ef304f53a020a2c548d87
[cd42b99]: https://github.com/zepfu/llama-gguf-inference/commit/cd42b994089b24884e839a77e8070ff73b90fad0
[d8b45ee]: https://github.com/zepfu/llama-gguf-inference/commit/d8b45eebd62d5e5592228d5fa2baad53113f991a
[ee44290]: https://github.com/zepfu/llama-gguf-inference/commit/ee44290a1c071da303a9201db9c581a1c728c1bf
[f0e28d3]: https://github.com/zepfu/llama-gguf-inference/commit/f0e28d3
[f3ea83b]: https://github.com/zepfu/llama-gguf-inference/commit/f3ea83bdc97d85456419a3e08f46d8695f5cf64a
[f588262]: https://github.com/zepfu/llama-gguf-inference/commit/f5882623369b3fc0073b53e0b2788759dab582a4
[fb3989b]: https://github.com/zepfu/llama-gguf-inference/commit/fb3989b91e73e4c56f165cdd35695203fbd26239
[fe7e768]: https://github.com/zepfu/llama-gguf-inference/commit/fe7e76863363cd156dcdabd6e7b33e9c74ef2e7f
[fea0e43]: https://github.com/zepfu/llama-gguf-inference/commit/fea0e436d8d62925d1a24914169e65b1502d4fb2
[unreleased]: https://github.com/zepfu/llama-gguf-inference/compare/v1.0.0-rc.1...HEAD
