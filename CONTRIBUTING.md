
## Documentation Automation

### Repository Map

The repository structure is automatically documented in `REPO_MAP.md`.

**Automatic Updates:**
- Weekly via GitHub Action (Monday 9 AM UTC)
- Creates PR if changes detected
- Auto-merges if CI passes

**Manual Update:**
```bash
make map
```

**Pre-commit Check:**
The pre-commit hook will fail if REPO_MAP.md is outdated.

### Changelog

Changelog is generated from git commit history using conventional commits.

**Automatic Updates:**
- Weekly via GitHub Action
- Includes commit links
- Groups by change type (Added, Fixed, Changed, etc.)

**Manual Update:**
```bash
make changelog
```

**Conventional Commit Format:**
```
feat: add new feature
fix: fix bug
docs: update documentation
refactor: refactor code
test: add tests
```

**Commit Types Mapping:**
- `feat:` → Added
- `fix:` → Fixed
- `docs:`, `refactor:`, `perf:`, `test:`, `build:`, `ci:`, `chore:` → Changed

### API Documentation

Generate API documentation from Python docstrings:

```bash
make api-docs
```

Requires Sphinx:
```bash
pip install sphinx sphinx-rtd-theme
```

## Development Workflows

### Weekly Automation

Every Monday at 9 AM UTC, a GitHub Action:
1. Generates updated REPO_MAP.md
2. Generates updated CHANGELOG.md
3. Creates PR if changes detected
4. Auto-merges if CI passes

You can also trigger manually:
```bash
# Via GitHub UI: Actions → Update Documentation → Run workflow

# Or via CLI
gh workflow run update-docs.yml
```

### Pre-commit Hooks

Three project-specific hooks run automatically:

1. **check-repo-map** - Fails if REPO_MAP.md outdated
2. **check-env-completeness** - Validates env var docs
3. **check-changelog** - Warns if CHANGELOG.md outdated (pre-push only)

To bypass (not recommended):
```bash
git commit --no-verify
```

### Testing Strategy

**Quick Tests:**
```bash
make test-auth    # Auth tests only
make test-health  # Health endpoint tests
```

**Integration Tests:**
```bash
make test-integration  # Full workflow
```

**Docker Tests:**
```bash
make test-docker  # Docker integration
```

**All Tests:**
```bash
make test  # Runs all available tests
```

### Makefile Commands

See all available commands:
```bash
make help
```

Key commands:
- `make setup` - One-time dev setup
- `make docs` - Update all documentation
- `make check` - Run pre-commit checks
- `make test` - Run test suite
- `make build` - Build Docker image
- `make diagnostics` - Collect system diagnostics

## Release Process

### Creating a Release

1. **Update version** (if needed in files)

2. **Tag the release:**
```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

3. **Automated steps** (via GitHub Action):
   - Generates release changelog
   - Builds Docker image
   - Pushes to ghcr.io with version tags
   - Creates GitHub Release

### Version Tags

Use semantic versioning:
- `v1.0.0` - Major release
- `v1.1.0` - Minor release
- `v1.1.1` - Patch release

Docker images are tagged:
- `v1.0.0` - Specific version
- `1.0` - Major.minor
- `1` - Major
- `latest` - Latest release

## Documentation Guidelines

### Updating Documentation

**Architecture changes:**
Edit `docs/ARCHITECTURE.md` with Mermaid diagrams.

**Script documentation:**
Update `scripts/README.md` when adding/changing scripts.

**Configuration changes:**
Update `docs/CONFIGURATION.md` with new env vars.

### Mermaid Diagrams

Use Mermaid for architecture diagrams:

```mermaid
graph LR
    A[Client] --> B[Gateway]
    B --> C[Backend]
```

Renders correctly in GitHub and most markdown viewers.

## Environment Variables

### Adding New Variables

1. **Add to start.sh:**
```bash
NEW_VAR="${NEW_VAR:-default_value}"
```

2. **Document in .env.example:**
```bash
# Description of NEW_VAR
NEW_VAR=default_value
```

3. **Document in docs/CONFIGURATION.md:**
Add to appropriate table with description.

4. **Run validation:**
```bash
make check-env
```

Pre-commit hook will catch missing documentation.

## Troubleshooting Development

### Pre-commit Failing

**Repo map outdated:**
```bash
make map
git add REPO_MAP.md
git commit
```

**Env completeness:**
```bash
make check-env
# Fix reported issues
```

**Format issues:**
```bash
make format  # Auto-format code
make check   # Verify all checks pass
```

### Tests Failing

**Collect diagnostics:**
```bash
make diagnostics
# Review /tmp/llama-diagnostics-*/SUMMARY.txt
```

**Enable verbose mode:**
```bash
VERBOSE=true bash scripts/tests/test_auth.sh
```

### Docker Issues

**Build failures:**
Check build logs and ensure all files are present.

**Container won't start:**
```bash
docker logs <container-id>
```

**Permission errors:**
```bash
chmod +x scripts/**/*.sh
```
