# Workflow Registry & Tool Coverage

**Auto-generated:** 2026-02-13 11:17:10

> Complete reference for all reusable workflows: what tools they run, their inputs, blocking vs. advisory behavior, and
> overlap with pre-commit.

## How to Use This Document

- **Adopting workflows?** Jump to [Recommended Adoption Profiles](#recommended-adoption-profiles) to see which
  combination fits your project.
- **Debugging a CI failure?** Find the failing workflow in the [Workflow Registry](#workflow-registry) to see exactly
  which tools run and whether failures are blocking.
- **Choosing between pre-commit and CI?** See the [Tool Coverage Matrix](#tool-coverage-matrix) for the full overlap
  picture.

## Pre-commit vs. CI: How They Work Together

Many tools appear in **both** pre-commit hooks and CI workflows. This is intentional — they serve different roles:

|             | Pre-commit (local)                  | CI Workflows (remote)                            |
| ----------- | ----------------------------------- | ------------------------------------------------ |
| **When**    | Before each commit                  | On push / PR                                     |
| **Mode**    | Fix-then-commit — auto-fix in place | Check-only — report violations without modifying |
| **Scope**   | Staged files only                   | Full repository                                  |
| **Purpose** | Fast feedback; prevent bad commits  | Enforcement gate; catches skipped hooks          |
| **Failure** | Blocks `git commit` locally         | Blocks PR merge                                  |

### Why the overlap matters

A downstream repo should run **both** pre-commit and CI workflows. Pre-commit gives developers instant feedback and
auto-fixes. CI is the safety net that guarantees standards are met regardless of local setup — someone who clones fresh,
skips `pre-commit install`, or uses `--no-verify` will still be caught.

### Tools unique to each context

Some tools only run in one context:

- **CI only:** Vulture (dead code), PyLint unreachable-code checks, py_compile syntax validation, Docker build, Sphinx
  docs build. These are too slow or too noisy for a pre-commit hook.
- **Pre-commit only:** hadolint (Dockerfile linting), file-hygiene hooks (trailing whitespace, EOF fixer, merge conflict
  detection, private key detection). These are fast fixers best run locally.

See the [Tool Coverage Matrix](#tool-coverage-matrix) below for the complete mapping.

## Workflow Registry

## Tool Coverage Matrix

Which tools run where — at a glance.

| Tool                                 | Category       | CI Workflow(s) | Pre-commit | Unique to       |
| ------------------------------------ | -------------- | -------------- | ---------- | --------------- |
| actionlint                           | other          | —              | ✅         | pre-commit only |
| autoflake                            | other          | —              | ✅         | pre-commit only |
| bandit                               | other          | —              | ✅         | pre-commit only |
| black                                | other          | —              | ✅         | pre-commit only |
| check-added-large-files              | file-hygiene   | —              | ✅         | pre-commit only |
| check-case-conflict                  | file-hygiene   | —              | ✅         | pre-commit only |
| check-executables-have-shebangs      | file-hygiene   | —              | ✅         | pre-commit only |
| check-json                           | json-syntax    | —              | ✅         | pre-commit only |
| check-merge-conflict                 | file-hygiene   | —              | ✅         | pre-commit only |
| check-shebang-scripts-are-executable | file-hygiene   | —              | ✅         | pre-commit only |
| check-symlinks                       | file-hygiene   | —              | ✅         | pre-commit only |
| check-toml                           | toml-syntax    | —              | ✅         | pre-commit only |
| check-yaml                           | yaml-syntax    | —              | ✅         | pre-commit only |
| checkmake                            | other          | —              | ✅         | pre-commit only |
| destroyed-symlinks                   | file-hygiene   | —              | ✅         | pre-commit only |
| detect-private-key                   | security       | —              | ✅         | pre-commit only |
| end-of-file-fixer                    | file-hygiene   | —              | ✅         | pre-commit only |
| eradicate                            | other          | —              | ✅         | pre-commit only |
| fix-byte-order-marker                | file-hygiene   | —              | ✅         | pre-commit only |
| flake8                               | other          | —              | ✅         | pre-commit only |
| hadolint                             | docker-linting | —              | ✅         | pre-commit only |
| isort                                | other          | —              | ✅         | pre-commit only |
| mdformat                             | other          | —              | ✅         | pre-commit only |
| mixed-line-ending                    | file-hygiene   | —              | ✅         | pre-commit only |
| mypy                                 | other          | —              | ✅         | pre-commit only |
| pydocstyle                           | other          | —              | ✅         | pre-commit only |
| shellcheck                           | other          | —              | ✅         | pre-commit only |
| trailing-whitespace                  | file-hygiene   | —              | ✅         | pre-commit only |
| yamllint                             | other          | —              | ✅         | pre-commit only |

### Version Comparison (tools in both CI and pre-commit)

| Tool | CI Version | Pre-commit Rev |
| ---- | ---------- | -------------- |

> **⚠️ Version drift risk:** CI workflows install tools via `pip install` without version pins, so they always get the
> latest release. Pre-commit pins specific revisions. A tool releasing a breaking change can cause CI to fail while
> pre-commit passes locally (or vice versa). If you hit this, check whether the versions in these two columns have
> diverged. Downstream repos that need stability should pin tool versions in their CI config or rely on pre-commit as
> the single source of truth for tool versions.

### Scope Differences Between CI and Pre-commit

Some tools scan different file sets in CI vs. pre-commit, which can produce different results:

| Tool                 | CI Scope                                  | Pre-commit Scope                                | Impact                                                                                                                                              |
| -------------------- | ----------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bandit               | `-r .` with `pyproject.toml` exclude_dirs | All staged `.py` files with `-c pyproject.toml` | CI scans the full tree (minus excludes); pre-commit only scans staged files. New `.py` files outside `scripts/` may be missed locally until staged. |
| Black, isort         | `. (all Python)`                          | Staged `.py` files only                         | CI catches unformatted files that weren't staged in the committing developer's working tree.                                                        |
| ShellCheck           | `**/*.sh` (full tree)                     | Staged `.sh` files only                         | Same pattern — CI is exhaustive, pre-commit is incremental.                                                                                         |
| Autoflake, Eradicate | `scripts/` (CI check-only)                | All staged `.py` (fix in-place)                 | CI only checks `scripts/`; pre-commit fixes across all staged Python files.                                                                         |

> For most repos this is fine — pre-commit catches issues incrementally and CI validates the full tree. But if CI fails
> on a file that pre-commit never saw, scope difference is the likely cause.

## Blocking vs. Advisory Behavior

Understanding which tools will block your PR and which are informational.

### Blocking (will fail your PR)

### Advisory (warnings only, will not fail)

## Recommended Adoption Profiles

### Python Project (Minimal)

```yaml
jobs:
  python-standards:
    uses: zepfu/repo-standards/.github/workflows/reusable-python-ci.yml@main
  pre-commit:
    uses: zepfu/repo-standards/.github/workflows/reusable-pre-commit.yml@main
```

**What you get:** Black, isort, Flake8, syntax validation via CI; full hook suite locally via pre-commit.

**Overlap:** Black, isort, Flake8 run in both `reusable-python-ci.yml` and pre-commit. See
[Pre-commit vs. CI](#pre-commit-vs-ci-how-they-work-together) for why both are recommended.

______________________________________________________________________

### Python Project (Comprehensive)

```yaml
jobs:
  python-standards:
    uses: zepfu/repo-standards/.github/workflows/reusable-python-ci.yml@main
  quality-checks:
    uses: zepfu/repo-standards/.github/workflows/reusable-quality-checks.yml@main
  pre-commit:
    uses: zepfu/repo-standards/.github/workflows/reusable-pre-commit.yml@main
  config-validation:
    uses: zepfu/repo-standards/.github/workflows/reusable-config-validation.yml@main
```

**What you get:** Everything from minimal, plus Bandit security scanning, mypy type checking, Vulture dead-code
detection, pydocstyle, actionlint, and mdformat.

**Overlap:** `reusable-quality-checks.yml` runs Bandit, mypy, pydocstyle, actionlint, Autoflake, Eradicate, and mdformat
— all of which also run via pre-commit hooks. The CI versions provide granular per-job visibility and add Vulture and
PyLint unreachable-code checks (not in pre-commit). See [Pre-commit vs. CI](#pre-commit-vs-ci-how-they-work-together)
for why both are recommended.

______________________________________________________________________

### Shell Project

```yaml
jobs:
  shell-standards:
    uses: zepfu/repo-standards/.github/workflows/reusable-shell-ci.yml@main
  pre-commit:
    uses: zepfu/repo-standards/.github/workflows/reusable-pre-commit.yml@main
  config-validation:
    uses: zepfu/repo-standards/.github/workflows/reusable-config-validation.yml@main
```

______________________________________________________________________

### Python + Docker Project

```yaml
jobs:
  python-standards:
    uses: zepfu/repo-standards/.github/workflows/reusable-python-ci.yml@main
  quality-checks:
    uses: zepfu/repo-standards/.github/workflows/reusable-quality-checks.yml@main
  shell-standards:
    uses: zepfu/repo-standards/.github/workflows/reusable-shell-ci.yml@main
  docker-build:
    uses: zepfu/repo-standards/.github/workflows/reusable-docker-build.yml@main
    needs: [python-standards, shell-standards]
  pre-commit:
    uses: zepfu/repo-standards/.github/workflows/reusable-pre-commit.yml@main
  config-validation:
    uses: zepfu/repo-standards/.github/workflows/reusable-config-validation.yml@main
```

**Note:** hadolint (Dockerfile linting) is in pre-commit only — there is no dedicated CI workflow for it yet. Docker
build validation happens via `reusable-docker-build.yml`.

______________________________________________________________________

### Full Stack (All Workflows)

```yaml
jobs:
  config-validation:
    uses: zepfu/repo-standards/.github/workflows/reusable-config-validation.yml@main
  python-standards:
    uses: zepfu/repo-standards/.github/workflows/reusable-python-ci.yml@main
  shell-standards:
    uses: zepfu/repo-standards/.github/workflows/reusable-shell-ci.yml@main
  yaml-standards:
    uses: zepfu/repo-standards/.github/workflows/reusable-yaml-ci.yml@main
  makefile-standards:
    uses: zepfu/repo-standards/.github/workflows/reusable-makefile-ci.yml@main
  quality-checks:
    uses: zepfu/repo-standards/.github/workflows/reusable-quality-checks.yml@main
  docker-build:
    uses: zepfu/repo-standards/.github/workflows/reusable-docker-build.yml@main
    needs: [python-standards, shell-standards]
  pre-commit:
    uses: zepfu/repo-standards/.github/workflows/reusable-pre-commit.yml@main
  update-docs:
    uses: zepfu/repo-standards/.github/workflows/reusable-update-docs.yml@main
    needs: [python-standards, shell-standards]
```

## Workflow Version Defaults

Key input defaults across workflows. Pin these in your CI config if you need stability — defaults may change when
repo-standards is updated.

| Workflow | Input | Current Default |
| -------- | ----- | --------------- |

> **Tip:** If your project requires Python 3.11, pass `python-version: '3.11'` explicitly rather than relying on the
> default, which is currently `3.13`.

______________________________________________________________________

*This file is auto-generated by `generate_workflow_registry.py` from repo-standards.* *Manual edits will be
overwritten.*
