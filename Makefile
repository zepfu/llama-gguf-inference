.PHONY: help setup clean test lint format check docs map changelog api-docs architecture build run diagnostics docs-build docs-serve docs-clean

# Configuration
REPO_STANDARDS_URL := https://raw.githubusercontent.com/zepfu/repo-standards/main/scripts
PYTHON := python3
DOCKER_IMAGE := llama-gguf-inference
DOCS_DIR := docs
DOCS_BUILD_DIR := $(DOCS_DIR)/_build

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m

##@ Help

help:  ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup

setup:  ## First-time setup (install pre-commit, set permissions)
	@echo "$(GREEN)Setting up development environment...$(NC)"
	@command -v pre-commit >/dev/null 2>&1 || { echo "Installing pre-commit..."; python3 -m pip install --user pre-commit; }
	@pre-commit install --hook-type pre-commit --hook-type pre-push
	@chmod +x scripts/**/*.sh 2>/dev/null || true
	@chmod +x scripts/**/*.py 2>/dev/null || true
	@echo "$(GREEN)✓ Setup complete$(NC)"

clean:  ## Clean generated files and caches
	@echo "Cleaning..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

##@ Testing

test:  ## Run all tests
	@echo "$(GREEN)Running tests...$(NC)"
	@bash scripts/tests/test_runner.sh

test-auth:  ## Run authentication tests
	@bash scripts/tests/test_auth.sh

test-health:  ## Run health endpoint tests
	@bash scripts/tests/test_health.sh

test-integration:  ## Run integration tests
	@bash scripts/tests/test_integration.sh

test-docker:  ## Run Docker integration tests
	@DOCKER_TEST=true bash scripts/tests/test_docker_integration.sh

##@ Code Quality

lint:  ## Run linting checks
	@echo "$(GREEN)Running linters...$(NC)"
	@$(PYTHON) -m flake8 scripts/*.py || true
	@shellcheck scripts/**/*.sh || true

format:  ## Format code (Python with Black, shell with shfmt if available)
	@echo "$(GREEN)Formatting code...$(NC)"
	@$(PYTHON) -m black scripts/*.py 2>/dev/null || echo "Black not installed, skipping Python formatting"
	@$(PYTHON) -m isort scripts/*.py 2>/dev/null || echo "isort not installed, skipping import sorting"
	@command -v shfmt >/dev/null 2>&1 && shfmt -w scripts/**/*.sh || echo "shfmt not installed, skipping shell formatting"

check:  ## Run all pre-commit checks
	@echo "$(GREEN)Running pre-commit checks...$(NC)"
	@pre-commit run --all-files

##@ Documentation

docs: map changelog architecture  ## Update all auto-generated documentation locally
	@echo "$(GREEN)✓ All auto-generated documentation updated$(NC)"
	@echo ""
	@echo "Generated files:"
	@echo "  - docs/auto/REPO_MAP.md"
	@echo "  - docs/auto/CHANGELOG.md"
	@echo "  - docs/auto/ARCHITECTURE_AUTO.md"

docs-build:  ## Build Sphinx documentation locally
	@echo "$(GREEN)Building Sphinx documentation...$(NC)"
	@if [ ! -f $(DOCS_DIR)/requirements.txt ]; then \
		echo "$(RED)✗ docs/requirements.txt not found$(NC)"; \
		exit 1; \
	fi
	@echo "Installing/checking Sphinx dependencies..."
	@pip install -q -r $(DOCS_DIR)/requirements.txt
	@cd $(DOCS_DIR) && sphinx-build -b html . _build/html
	@echo "$(GREEN)✓ Documentation built at $(DOCS_BUILD_DIR)/html/index.html$(NC)"

docs-serve:  ## Build and serve documentation locally (port 8080)
	@$(MAKE) docs-build
	@echo "$(GREEN)Serving documentation at http://localhost:8080$(NC)"
	@echo "Press Ctrl+C to stop"
	@cd $(DOCS_BUILD_DIR)/html && $(PYTHON) -m http.server 8080

docs-clean:  ## Clean Sphinx build artifacts
	@echo "Cleaning Sphinx build artifacts..."
	@rm -rf $(DOCS_BUILD_DIR)
	@echo "$(GREEN)✓ Sphinx build artifacts cleaned$(NC)"

docs-check:  ## Check documentation builds without warnings
	@echo "$(GREEN)Checking documentation build...$(NC)"
	@pip install -q -r $(DOCS_DIR)/requirements.txt
	@cd $(DOCS_DIR) && sphinx-build -b html -W . _build/html
	@echo "$(GREEN)✓ Documentation builds without warnings$(NC)"

docs-linkcheck:  ## Check for broken links in documentation
	@echo "$(GREEN)Checking documentation links...$(NC)"
	@pip install -q -r $(DOCS_DIR)/requirements.txt
	@cd $(DOCS_DIR) && sphinx-build -b linkcheck . _build/linkcheck
	@echo "$(GREEN)✓ Link check complete$(NC)"

map:  ## Generate repository structure map
	@echo "Generating docs/auto/REPO_MAP.md..."
	@mkdir -p docs/auto
	@curl -fsSL $(REPO_STANDARDS_URL)/repo_map.py | $(PYTHON) - --output docs/auto/REPO_MAP.md
	@echo "$(GREEN)✓ Generated docs/auto/REPO_MAP.md$(NC)"

changelog:  ## Generate changelog from git history
	@echo "Generating docs/auto/CHANGELOG.md..."
	@mkdir -p docs/auto
	@curl -fsSL $(REPO_STANDARDS_URL)/changelog.py | $(PYTHON) - --from-git --with-commits --output docs/auto/CHANGELOG.md
	@echo "$(GREEN)✓ Generated docs/auto/CHANGELOG.md$(NC)"

architecture:  ## Generate architecture diagrams
	@echo "Generating docs/auto/ARCHITECTURE_AUTO.md..."
	@mkdir -p docs/auto
	@if [ -f scripts/dev/generate_architecture.py ]; then \
		$(PYTHON) scripts/dev/generate_architecture.py --output docs/auto/ARCHITECTURE_AUTO.md; \
	else \
		curl -fsSL $(REPO_STANDARDS_URL)/generate_architecture.py | $(PYTHON) - --output docs/auto/ARCHITECTURE_AUTO.md; \
	fi
	@echo "$(GREEN)✓ Generated docs/auto/ARCHITECTURE_AUTO.md$(NC)"

view-architecture:  ## View manual architecture documentation
	@echo "Opening docs/ARCHITECTURE.md..."
	@test -f docs/ARCHITECTURE.md && cat docs/ARCHITECTURE.md || echo "docs/ARCHITECTURE.md not found"

update-docs:  ## 🚀 Quick: Update docs and create PR automatically
	@$(MAKE) trigger-docs-update

api-docs:  ## Generate API documentation with Sphinx
	@echo "Generating API documentation..."
	@bash scripts/dev/generate_api_docs.sh

check-docs:  ## Check if documentation is current
	@bash scripts/dev/check_repo_map.sh
	@bash scripts/dev/check_changelog.sh
	@echo "$(GREEN)✓ Documentation is current$(NC)"

##@ Docker

build:  ## Build Docker image
	@echo "$(GREEN)Building Docker image...$(NC)"
	@docker build -t $(DOCKER_IMAGE):dev \
		--build-arg GIT_SHA=$$(git rev-parse --short HEAD) \
		--build-arg BUILD_TIME=$$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
		.
	@echo "$(GREEN)✓ Built $(DOCKER_IMAGE):dev$(NC)"

run:  ## Run Docker container locally (no auth, CPU mode)
	@echo "$(GREEN)Running Docker container...$(NC)"
	@docker run --rm -it \
		-v $$(pwd)/data:/data \
		-e MODEL_NAME=$${MODEL_NAME:-test-model.gguf} \
		-e AUTH_ENABLED=false \
		-e NGL=0 \
		-p 8000:8000 \
		$(DOCKER_IMAGE):dev

run-gpu:  ## Run Docker container with GPU
	@echo "$(GREEN)Running Docker container with GPU...$(NC)"
	@docker run --rm -it --gpus all \
		-v $$(pwd)/data:/data \
		-e MODEL_NAME=$${MODEL_NAME:-test-model.gguf} \
		-e AUTH_ENABLED=false \
		-p 8000:8000 \
		$(DOCKER_IMAGE):dev

##@ Diagnostics

diagnostics:  ## Collect system diagnostics
	@echo "$(GREEN)Collecting diagnostics...$(NC)"
	@bash scripts/diagnostics/collect.sh
	@echo "$(GREEN)✓ Diagnostics collected$(NC)"

##@ Development

dev-setup:  ## Setup development environment
	@bash scripts/dev/setup.sh

check-env:  ## Check environment variable completeness
	@bash scripts/dev/check_env_completeness.sh

##@ Maintenance

update-tools:  ## Update development tools and dependencies
	@echo "$(GREEN)Updating tools...$(NC)"
	@pip install --upgrade pre-commit black isort flake8
	@pre-commit autoupdate
	@echo "$(GREEN)✓ Tools updated$(NC)"

sync-configs:  ## Sync config files from repo-standards
	@echo "$(GREEN)Syncing config files...$(NC)"
	@curl -fsSL https://raw.githubusercontent.com/zepfu/repo-standards/main/scripts/sync-configs.sh | bash
	@echo "$(GREEN)✓ Configs synced$(NC)"

trigger-docs-update:  ## Trigger documentation update workflow (requires gh CLI)
	@echo "$(GREEN)Triggering documentation update workflow...$(NC)"
	@if command -v gh >/dev/null 2>&1; then \
		gh workflow run update-docs.yml; \
		echo "$(GREEN)✓ Workflow triggered! Check Actions tab for progress.$(NC)"; \
	else \
		echo "$(RED)✗ GitHub CLI (gh) not installed$(NC)"; \
		echo "Install: https://cli.github.com/"; \
		echo "Or trigger manually at: https://github.com/$$(git config --get remote.origin.url | sed 's/.*://;s/.git$$//')/actions/workflows/update-docs.yml"; \
	fi
