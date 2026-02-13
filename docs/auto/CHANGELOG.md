# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add request queuing and concurrency control
  ([4600a81](https://github.com/zepfu/llama-gguf-inference/commit/4600a81d39ef96b2abc378846566f6b1c0b10769))
- Add API key management CLI tool
  ([cd42b99](https://github.com/zepfu/llama-gguf-inference/commit/cd42b994089b24884e839a77e8070ff73b90fad0))
- Add CORS headers and Prometheus metrics format
  ([c8ca8d9](https://github.com/zepfu/llama-gguf-inference/commit/c8ca8d9f4bda27bf352ef304f53a020a2c548d87))
- Add multi-arch support, .dockerignore, and docker-compose
  ([707b819](https://github.com/zepfu/llama-gguf-inference/commit/707b819de3076d8db03cce8e1f2078ba3734b9d8))
- Add unit tests and coverage for auth module
  ([fea0e43](https://github.com/zepfu/llama-gguf-inference/commit/fea0e436d8d62925d1a24914169e65b1502d4fb2))
- Add tag-triggered release workflow
  ([fe7e768](https://github.com/zepfu/llama-gguf-inference/commit/fe7e76863363cd156dcdabd6e7b33e9c74ef2e7f))
- additional doc updates
  ([31eb3ca](https://github.com/zepfu/llama-gguf-inference/commit/31eb3ca2a9c527e0281eda8b03c4d1b1257c17f6))
- Pages fix ([aa1c71a](https://github.com/zepfu/llama-gguf-inference/commit/aa1c71aa11bf89804bc40fd23a8b965ec47fd0f1))
- ReadTheDocs fix
  ([73fe5fe](https://github.com/zepfu/llama-gguf-inference/commit/73fe5fe7c5c66de4d5055e6dc6d2615c5afe0e47))
- ReadTheDocs and documentation automation
  ([634fa8c](https://github.com/zepfu/llama-gguf-inference/commit/634fa8c6aa207a87125583a3462ad23b9d923d9b))
- ReadTheDocs and documentation automation
  ([7f449b9](https://github.com/zepfu/llama-gguf-inference/commit/7f449b90f2035a5a5280dfe03075373138be3f47))
- Add ai-dev-tools as submodule
  ([146bf8e](https://github.com/zepfu/llama-gguf-inference/commit/146bf8e8778cd266d3b151ceb0d818fc83cb787c))

### Changed

- Fix critical and high severity findings
  ([1283071](https://github.com/zepfu/llama-gguf-inference/commit/128307144db378aa3395769090bcf3f126883b47))
- Add project coordination files
  ([c8c1972](https://github.com/zepfu/llama-gguf-inference/commit/c8c197249e511258da3c2ab031aacd06135328bc))
- Complete branch migration master → main
  ([bbd2152](https://github.com/zepfu/llama-gguf-inference/commit/bbd2152db23b7552eb6145246e78fa4832cf69fb))
- Add repo.mk with Docker build/run targets
  ([c6ef1ed](https://github.com/zepfu/llama-gguf-inference/commit/c6ef1edd6221cb500a9d0cbadbc103632874eb5e))
- Stabilization pass — CI/CD, pre-commit, docs, code quality
  ([14a8925](https://github.com/zepfu/llama-gguf-inference/commit/14a8925c1dde5844e3a770428d43d458a8bec766))
- cleanup ([fc6209d](https://github.com/zepfu/llama-gguf-inference/commit/fc6209d31e63976c683c6ac1e35f80ceed133417))
- workflow updates
  ([5f4a0fd](https://github.com/zepfu/llama-gguf-inference/commit/5f4a0fd1d99a96a696a12e512f0d40605c4208ad))
- more standards/documentation
  ([2ef5477](https://github.com/zepfu/llama-gguf-inference/commit/2ef5477adcd11a7b6dde1c04181da89238643644))
- more changes
  ([ea860a5](https://github.com/zepfu/llama-gguf-inference/commit/ea860a54f2791756bfd6feed40cd364fb92a9c99))
- standards support
  ([ba0aeef](https://github.com/zepfu/llama-gguf-inference/commit/ba0aeeff19a0916f469c4d9e5045e478c6e09534))
- cleaning ([e6467c9](https://github.com/zepfu/llama-gguf-inference/commit/e6467c9cdb1fa98ea751f364b55d32a03b58ef74))
- perms ([4a76bce](https://github.com/zepfu/llama-gguf-inference/commit/4a76bcef96d97bf05a00644b57ba50965de75081))
- updates for auth, gateway, code quality, qol.
  ([0850d56](https://github.com/zepfu/llama-gguf-inference/commit/0850d5653ed9e50c9ac385e89d83ebc8688c9f04))
- KAN-4: scale to zero resolution.
  ([20a10bb](https://github.com/zepfu/llama-gguf-inference/commit/20a10bb30263d11ade3fab67b89115ddb2dc8333))
- real initial commit...
  ([ee44290](https://github.com/zepfu/llama-gguf-inference/commit/ee44290a1c071da303a9201db9c581a1c728c1bf))
- Initial commit
  ([f0755af](https://github.com/zepfu/llama-gguf-inference/commit/f0755afee8c2f6601ccc0340f4182a6519d18061))

### Fixed

- Fix docs workflow startup_failure
  ([d8b45ee](https://github.com/zepfu/llama-gguf-inference/commit/d8b45eebd62d5e5592228d5fa2baad53113f991a))
- Generate valid backend key format in mock mode
  ([a8944c9](https://github.com/zepfu/llama-gguf-inference/commit/a8944c923fb71773a2f42264d5645c9cff466f2e))
- Fix pre-commit actionlint and integration test timing
  ([4c4f83d](https://github.com/zepfu/llama-gguf-inference/commit/4c4f83d4a20858e77040ceca069bd152c40b5512))
- Restore checkmake linting for .mk files
  ([f3ea83b](https://github.com/zepfu/llama-gguf-inference/commit/f3ea83bdc97d85456419a3e08f46d8695f5cf64a))
- ci fix ([f588262](https://github.com/zepfu/llama-gguf-inference/commit/f5882623369b3fc0073b53e0b2788759dab582a4))
- ci fix ([63a3c5e](https://github.com/zepfu/llama-gguf-inference/commit/63a3c5e7e771ee4e392b4358b15c12eeaf69187e))
- ci fix ([315a6c0](https://github.com/zepfu/llama-gguf-inference/commit/315a6c02b3c6cf48fad996f94a68143bdd762108))
- ci fix ([3480412](https://github.com/zepfu/llama-gguf-inference/commit/3480412db0d3e071c371bd85777783ce967ec939))

### Security

- security updates
  ([fb3989b](https://github.com/zepfu/llama-gguf-inference/commit/fb3989b91e73e4c56f165cdd35695203fbd26239))

______________________________________________________________________

*This file is auto-generated from git history.* *Manual edits may be overwritten.*
