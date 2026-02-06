# Contributing to llama-gguf-inference

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

### Prerequisites

- Git
- Docker (for testing containers)
- Python 3.11+
- pre-commit

### Initial Setup

```bash
# 1. Clone repository with submodules
git clone --recursive https://github.com/zepfu/llama-gguf-inference.git
cd llama-gguf-inference

# 2. Install pre-commit
pip install pre-commit

# 3. Install git hooks
pre-commit install

# 4. Test pre-commit
pre-commit run --all-files
```

## Development Workflow

### Making Changes

```bash
# 1. Create feature branch
git checkout -b feature/your-feature-name

# 2. Make your changes
# Edit files...

# 3. Test locally
bash scripts/tests/test_auth.sh
bash scripts/tests/test_health.sh

# 4. Commit (pre-commit hooks run automatically)
git add .
git commit -m "feat: Add new feature"

# 5. Push
git push origin feature/your-feature-name

# 6. Create Pull Request
```

### Commit Messages

Follow conventional commits format:

```
feat: Add new feature
fix: Fix bug in gateway
docs: Update README
refactor: Refactor auth module
test: Add tests for health endpoints
chore: Update dependencies
```

## Code Quality

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit:

- **Black** - Python code formatting (100 char lines)
- **isort** - Import sorting
- **Flake8** - Python linting
- **ShellCheck** - Bash linting
- **markdownlint** - Markdown formatting

### Manual Checks

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run specific checks
black scripts/*.py
flake8 scripts/*.py
shellcheck scripts/*.sh
```

### Python Style

```python
# Line length: 100 characters
# Docstrings: Use """triple quotes"""
# Type hints: Encouraged
# Imports: Sorted by isort

def process_request(
    method: str,
    path: str,
    headers: dict,
) -> Response:
    """
    Process an HTTP request.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        headers: Request headers

    Returns:
        Response object
    """
    pass
```

### Bash Style

```bash
#!/usr/bin/env bash
set -euo pipefail

# Quote all variables
echo "$VARIABLE"

# Use [[ ]] for tests
if [[ "$VAR" == "value" ]]; then
    # ...
fi

# Use functions for complex logic
process_data() {
    local input="$1"
    # ...
}
```

## Testing

### Running Tests

```bash
# Quick auth tests
bash scripts/tests/test_auth.sh

# Health endpoint tests
bash scripts/tests/test_health.sh

# All tests
bash scripts/tests/test_auth.sh && bash scripts/tests/test_health.sh
```

### Adding Tests

When adding new features:

1. Add test cases to appropriate test file
2. Test both success and failure cases
3. Document test expectations

```bash
# Example test function
test_new_feature() {
    test_start "New feature works correctly"

    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" "$URL/feature")

    if [[ "$response" == "200" ]]; then
        test_pass
    else
        test_fail "Expected 200, got $response"
        return 1
    fi
}
```

## Documentation

### Updating Documentation

When changing functionality:

1. Update relevant docs in `docs/`
2. Update README.md if needed
3. Add examples for new features
4. Update configuration docs

### Documentation Style

- Use clear, concise language
- Include code examples
- Add troubleshooting sections
- Use consistent formatting

## Pull Request Process

### Before Submitting

- [ ] Code passes pre-commit hooks
- [ ] Tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] No merge conflicts

### PR Description

Include:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How you tested the changes

## Checklist
- [ ] Pre-commit hooks pass
- [ ] Tests pass
- [ ] Documentation updated
```

### Review Process

1. Automated checks run (GitHub Actions)
2. Code review by maintainer
3. Address feedback if any
4. Merge when approved

## Project Structure

```
llama-gguf-inference/
├── scripts/
│   ├── auth.py           # Authentication module
│   ├── gateway.py        # HTTP gateway
│   ├── start.sh          # Main entrypoint
│   └── tests/            # Test scripts
├── docs/                 # Documentation
├── .github/workflows/    # CI/CD
├── .ai-tools/           # Submodule: dev tools
└── Dockerfile           # Container definition
```

## Getting Help

- **Issues:** Open an issue for bugs or feature requests
- **Discussions:** Use discussions for questions
- **Documentation:** Check docs/ directory

## Code of Conduct

- Be respectful and professional
- Provide constructive feedback
- Help others learn
- Focus on the code, not the person

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Development Tools

### ai-dev-tools Submodule

The project uses ai-dev-tools for standardized workflows:

```bash
# Update submodule
git submodule update --remote .ai-tools

# Use changelog tool
python3 .ai-tools/changelog/generate.py --from-git

# Use repo map tool
python3 .ai-tools/repo_map/generate.py
```

See [.ai-tools/README.md](.ai-tools/README.md) for more information.

## Questions?

Don't hesitate to ask! Open an issue or start a discussion.

Thank you for contributing! 🎉
