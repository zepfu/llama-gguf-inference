# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add configurable request timeout (REQUEST_TIMEOUT env var)
  ([287917a](https://github.com/zepfu/llama-gguf-inference/commit/287917a02ae891e5438d03cfcbbd51fa172b375c))
- Add per-key rate limits, key expiration, and rate limiter cleanup
  ([2c51ee2](https://github.com/zepfu/llama-gguf-inference/commit/2c51ee219a61ba1621468c604888b8ca456055a1))
- Add benchmarking script for performance baseline
  ([aeb3d59](https://github.com/zepfu/llama-gguf-inference/commit/aeb3d59bd6ee6ae60c7aedc94144a38659d389aa))
- Add request queuing and concurrency control
  ([bfb3581](https://github.com/zepfu/llama-gguf-inference/commit/bfb358107da180c2dd4309fd21f292138d60c0b1))
- Add API key management CLI tool
  ([2835b3a](https://github.com/zepfu/llama-gguf-inference/commit/2835b3aae8072c6626be6d6035c4abbe2b372a01))
- Add CORS headers and Prometheus metrics format
  ([7f557c1](https://github.com/zepfu/llama-gguf-inference/commit/7f557c160678b225e646384d3fd6537e41d9d658))
- Add multi-arch support, .dockerignore, and docker-compose
  ([0103c82](https://github.com/zepfu/llama-gguf-inference/commit/0103c82ba112d90c41e103687e7238405e630bd0))
- Add unit tests and coverage for auth module
  ([460f513](https://github.com/zepfu/llama-gguf-inference/commit/460f513f35d868514a0513aca9947936449c134b))
- Add tag-triggered release workflow
  ([84e6d40](https://github.com/zepfu/llama-gguf-inference/commit/84e6d4011dae74659c4caf8928bb0119cecde715))
- additional doc updates
  ([32feee7](https://github.com/zepfu/llama-gguf-inference/commit/32feee797020a8ad7f2c9b3fa6f0e33ff03fc994))
- Pages fix ([a63b4d5](https://github.com/zepfu/llama-gguf-inference/commit/a63b4d550a528ed40185bba405880d8995a0e68c))
- ReadTheDocs fix
  ([815e568](https://github.com/zepfu/llama-gguf-inference/commit/815e568c32b3b47105d19577bf1fcd5e562917ee))
- ReadTheDocs and documentation automation
  ([d0c4a3a](https://github.com/zepfu/llama-gguf-inference/commit/d0c4a3a4494128a01c25e3a3a4ef1243df40bfae))
- ReadTheDocs and documentation automation
  ([b743523](https://github.com/zepfu/llama-gguf-inference/commit/b743523bb6f169105b2dea316fb99565f0892bc8))
- Add ai-dev-tools as submodule
  ([3eb2fdf](https://github.com/zepfu/llama-gguf-inference/commit/3eb2fdf40c9c333bf458e4f1b39ff6d2e870d9cc))

### Changed

- Auto-update documentation [skip ci]
  ([c434e4d](https://github.com/zepfu/llama-gguf-inference/commit/c434e4d7aab40e1e856bf7e167ec0005c3a60cb6))
- Auto-update documentation [skip ci]
  ([70c9736](https://github.com/zepfu/llama-gguf-inference/commit/70c9736569edd4c63efba1e1c49c203ead300a10))
- Auto-update documentation [skip ci]
  ([a35999f](https://github.com/zepfu/llama-gguf-inference/commit/a35999f5e002260d60b57dbde375f0ebd94e7ef4))
- Auto-update documentation [skip ci]
  ([f5ca5be](https://github.com/zepfu/llama-gguf-inference/commit/f5ca5bea61ca11c8faa86c8481f9f73d797485e3))
- Auto-update documentation [skip ci]
  ([5559f08](https://github.com/zepfu/llama-gguf-inference/commit/5559f08b58235c19eea8fbc59915a131c4fae830))
- Auto-update documentation [skip ci]
  ([b92e6c6](https://github.com/zepfu/llama-gguf-inference/commit/b92e6c601fa1064bcf955c88e0e4894ef218c8ad))
- Stop tracking local agent state
  ([6e31873](https://github.com/zepfu/llama-gguf-inference/commit/6e318739ce2dd5540100097461513e995f6d36e0))
- Auto-update documentation [skip ci]
  ([d11d365](https://github.com/zepfu/llama-gguf-inference/commit/d11d365d389adfb63936899b472684e7c03dc203))
- Auto-update documentation [skip ci]
  ([0d1e4da](https://github.com/zepfu/llama-gguf-inference/commit/0d1e4da7a628c669838169c58cb933a476d53c15))
- Auto-update documentation [skip ci]
  ([187a768](https://github.com/zepfu/llama-gguf-inference/commit/187a768cabfabc403aedd0ff6c2936630241aeb9))
- Auto-update documentation [skip ci]
  ([10bfc98](https://github.com/zepfu/llama-gguf-inference/commit/10bfc98e84b0655c9022c863749ebd7633d44471))
- Auto-update documentation [skip ci]
  ([2af8a59](https://github.com/zepfu/llama-gguf-inference/commit/2af8a59f050c2bf1a271a2b3bf1ee6afd6358547))
- Auto-update documentation [skip ci]
  ([6502573](https://github.com/zepfu/llama-gguf-inference/commit/65025737de2913c1f8ccf6378d5a330633cefd17))
- Auto-update documentation [skip ci]
  ([51f9b73](https://github.com/zepfu/llama-gguf-inference/commit/51f9b7309c4aa86450d239a9a7f049206fbc7139))
- Auto-update documentation [skip ci]
  ([b9beed3](https://github.com/zepfu/llama-gguf-inference/commit/b9beed382720ad59e11a3d362742a83f22150069))
- Auto-update documentation [skip ci]
  ([b6989a0](https://github.com/zepfu/llama-gguf-inference/commit/b6989a0328b00a4c0e789cba6d3004b409bc498a))
- Auto-update documentation [skip ci]
  ([ef56769](https://github.com/zepfu/llama-gguf-inference/commit/ef5676907b455457e73921a20ad1e7fa7b80b335))
- Auto-update documentation [skip ci]
  ([d9b01b4](https://github.com/zepfu/llama-gguf-inference/commit/d9b01b40846af8f32369c032e98f6f6e577ea7dd))
- Auto-update documentation [skip ci]
  ([2b9eae7](https://github.com/zepfu/llama-gguf-inference/commit/2b9eae746c77ffa8ecd8283062b595059c9c86c7))
- Auto-update documentation [skip ci]
  ([469340b](https://github.com/zepfu/llama-gguf-inference/commit/469340b9119ec948c7c6adc1f5531e80fc637bd4))
- Auto-update documentation [skip ci]
  ([5c727d3](https://github.com/zepfu/llama-gguf-inference/commit/5c727d3cf0a3713bf1466807e27a88a7cb00e1cf))
- Auto-update documentation [skip ci]
  ([8dad3fa](https://github.com/zepfu/llama-gguf-inference/commit/8dad3fa03594c21e63f4deb433af47fc644e1bc6))
- Auto-update documentation [skip ci]
  ([4a3feef](https://github.com/zepfu/llama-gguf-inference/commit/4a3feef32c9a076bc0d31a93b5fd7d528658d1a6))
- Push coverage to 98% across all modules
  ([029118e](https://github.com/zepfu/llama-gguf-inference/commit/029118ea672b134d2c742347e714485ca2fa05ad))
- Cover remaining uncovered lines for 99% coverage
  ([4077f40](https://github.com/zepfu/llama-gguf-inference/commit/4077f40ee6ef2a791138770b6468464daf4e5f49))
- Cover remaining lines for 100% coverage
  ([3ae27f7](https://github.com/zepfu/llama-gguf-inference/commit/3ae27f7548a72149aa9379c87da95c7fbce3d4d0))
- Update documentation for post-v1 features
  ([0e8fa04](https://github.com/zepfu/llama-gguf-inference/commit/0e8fa0461fd01611772202737e66ab602713f329))
- Update security audit — all findings resolved
  ([e8391cb](https://github.com/zepfu/llama-gguf-inference/commit/e8391cb068e00e690ca8ce9134ad55523e2c2a61))
- Document hot-reload API keys via SIGHUP and POST /reload
  ([f937129](https://github.com/zepfu/llama-gguf-inference/commit/f937129fb192ce6876d6e861bc903ccfa7206e3e))
- Add backend response header size limit (SEC-13)
  ([37bd514](https://github.com/zepfu/llama-gguf-inference/commit/37bd514f8a2fb276d91011c3e528d1b90b313e3c))
- Document LOG_FORMAT env var for structured JSON logging
  ([ddf2a18](https://github.com/zepfu/llama-gguf-inference/commit/ddf2a18eaa1a2e2414cb82ce9d5b7fb05eb42ebf))
- Fix SEC-07/10/11/12/14/15/16 and remove BACKEND_PORT deprecation
  ([43bd67d](https://github.com/zepfu/llama-gguf-inference/commit/43bd67de0ba0519a0cc1504eaee556ebc1304648))
- Run containers as non-root user (SEC-08)
  ([0a6b6c1](https://github.com/zepfu/llama-gguf-inference/commit/0a6b6c12eb4cd8fdce4142f4c8de8b34c0fa8861))
- Improve coverage for benchmark, key_mgmt, and health_server modules
  ([0fc7d76](https://github.com/zepfu/llama-gguf-inference/commit/0fc7d76594145ad13cd641e15c0fa9d9fd885c32))
- Final v1 security audit report
  ([cdaecb7](https://github.com/zepfu/llama-gguf-inference/commit/cdaecb790d1334f4218297c8a5e53631f05eba72))
- Add API reference documentation
  ([90f0718](https://github.com/zepfu/llama-gguf-inference/commit/90f0718e9aab2d528260b50807e9f0eccbd66731))
- Add coverage threshold gate at 70%
  ([f76cc3b](https://github.com/zepfu/llama-gguf-inference/commit/f76cc3b1a0ad0f51704f7063c7ff48f9e6938098))
- Improve coverage for gateway and auth modules
  ([f21eda7](https://github.com/zepfu/llama-gguf-inference/commit/f21eda76b43c5fac09f2240c770bddb9fd5e9b24))
- Generate changelog for v1.0.0-rc.1
  ([8091845](https://github.com/zepfu/llama-gguf-inference/commit/809184574c82642cffec5ccf2a65d4ae230339fe))
- Update configuration, testing, and README for current state
  ([803a3d2](https://github.com/zepfu/llama-gguf-inference/commit/803a3d23fa29617a05fe2b00045c9e3257fd1977))
- Update phase status and add live testing guide
  ([20e7ac2](https://github.com/zepfu/llama-gguf-inference/commit/20e7ac29921658e7eaaa5e29da5cb50ce73ca3e1))
- Add body size, header count, and CORS validation limits
  ([92b6a75](https://github.com/zepfu/llama-gguf-inference/commit/92b6a75c14c9ac50e02cb41896387d711c7a6d19))
- Optimize container image size
  ([471cc61](https://github.com/zepfu/llama-gguf-inference/commit/471cc61cda8045f2478d30ec4c16cb84ccd0c896))
- Add migration guide and platform deployment guides
  ([e98dddc](https://github.com/zepfu/llama-gguf-inference/commit/e98dddcd1a1a0a4438c7008cee54e2740a4b6242))
- Fix key_id disclosure and CORS cache poisoning
  ([e5e1f6e](https://github.com/zepfu/llama-gguf-inference/commit/e5e1f6e5219c3b5e9fd33b1c9307573d7e7a81bc))
- Update documentation for Phase 3 features
  ([eea889d](https://github.com/zepfu/llama-gguf-inference/commit/eea889d2f673927a91c5ec376414be52436630b8))
- Auto-update documentation [skip ci]
  ([0560a0d](https://github.com/zepfu/llama-gguf-inference/commit/0560a0d7464b385ed86a269a6fd2028f186a3757))
- Fix critical and high severity findings
  ([ede7a0b](https://github.com/zepfu/llama-gguf-inference/commit/ede7a0b20653b9aa3c6d181059c305ed5ceba1bd))
- Add project coordination files
  ([7f1b338](https://github.com/zepfu/llama-gguf-inference/commit/7f1b3384c0941b78f70b397f8954ce4d07e9456a))
- Complete branch migration master → main
  ([9309ad8](https://github.com/zepfu/llama-gguf-inference/commit/9309ad832cce54c559b12eea93c5610aa6b9652a))
- Add repo.mk with Docker build/run targets
  ([f549002](https://github.com/zepfu/llama-gguf-inference/commit/f5490027b450a261f94688843a214133151de79a))
- Stabilization pass — CI/CD, pre-commit, docs, code quality
  ([feb8c33](https://github.com/zepfu/llama-gguf-inference/commit/feb8c33b26d59f7dfb60a821a290c8adbac791c9))
- cleanup ([ae95098](https://github.com/zepfu/llama-gguf-inference/commit/ae95098c68e41d555d9c79ffd20d6dfcf94f4bf9))
- workflow updates
  ([6f20dd6](https://github.com/zepfu/llama-gguf-inference/commit/6f20dd6613f05829bf56c8cbc5bad3a395bf334f))
- more standards/documentation
  ([0084974](https://github.com/zepfu/llama-gguf-inference/commit/0084974fbdded76d36db752e63a0e96edfbcdf21))
- more changes
  ([ac612cc](https://github.com/zepfu/llama-gguf-inference/commit/ac612cc9d333684419d1e08c38f1fea4ae9585ec))
- standards support
  ([fe41a7b](https://github.com/zepfu/llama-gguf-inference/commit/fe41a7b1cf455f8360690503f4b06a12342d5ed8))
- cleaning ([f6b076a](https://github.com/zepfu/llama-gguf-inference/commit/f6b076a14180b28c51331155a49261ae9f499b40))
- perms ([41e387f](https://github.com/zepfu/llama-gguf-inference/commit/41e387f7d5df2c315a579de74db9f5ccf1857c84))
- updates for auth, gateway, code quality, qol.
  ([43dbffb](https://github.com/zepfu/llama-gguf-inference/commit/43dbffb69aea5052cafe6bccf7a83a4748b779cf))
- KAN-4: scale to zero resolution.
  ([aff1e96](https://github.com/zepfu/llama-gguf-inference/commit/aff1e96617cce7895281210eb686bf4bdc67e219))
- real initial commit...
  ([ab47a24](https://github.com/zepfu/llama-gguf-inference/commit/ab47a24819c5a2ba6b22b1672ca0939f55d4a4af))
- Initial commit
  ([985ee67](https://github.com/zepfu/llama-gguf-inference/commit/985ee67acf06d2ed309ac443148e652bc977e12a))

### Fixed

- Add pytest-asyncio dependency for async benchmark tests
  ([f25ce8c](https://github.com/zepfu/llama-gguf-inference/commit/f25ce8cbb116d71e044d6151ab4b22048a9ef729))
- Resolve Sphinx build warnings treated as errors
  ([da6d938](https://github.com/zepfu/llama-gguf-inference/commit/da6d93837e2cc37448f9c096b1e1a5e1bacd1438))
- Fix docs workflow startup_failure
  ([12b7152](https://github.com/zepfu/llama-gguf-inference/commit/12b7152cbc9fdf7d1d6beeda49a9c623683f8f2b))
- Generate valid backend key format in mock mode
  ([7cda56a](https://github.com/zepfu/llama-gguf-inference/commit/7cda56a2b3031e0f9a228cd8f09f23e33aa3e44e))
- Fix pre-commit actionlint and integration test timing
  ([843e8eb](https://github.com/zepfu/llama-gguf-inference/commit/843e8eb0812720944b8e64d3e0611bbcad5aefd1))
- Restore checkmake linting for .mk files
  ([3600eab](https://github.com/zepfu/llama-gguf-inference/commit/3600eabfc888a1ccd8ab53c35b24ed11e2f6fb58))
- ci fix ([b237f2b](https://github.com/zepfu/llama-gguf-inference/commit/b237f2b85ab2d838e3c070d2c73fc81214889093))
- ci fix ([8595a39](https://github.com/zepfu/llama-gguf-inference/commit/8595a3951dedc6abce32309f48d6ab70a9ab6c47))
- ci fix ([5e35f7a](https://github.com/zepfu/llama-gguf-inference/commit/5e35f7adab19912cbb4fd525e38aa46ff5fc90a5))
- ci fix ([5fa97f7](https://github.com/zepfu/llama-gguf-inference/commit/5fa97f7c17ce111a867ddb666a8fa9e9c17ca94d))

### Security

- security updates
  ([f1ceb4f](https://github.com/zepfu/llama-gguf-inference/commit/f1ceb4f920446a87ff3b894a622f45b74a4da541))

______________________________________________________________________

*This file is auto-generated from git history.* *Manual edits may be overwritten.*
