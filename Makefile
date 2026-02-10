.PHONY: help setup clean docs build run run-gpu diagnostics sync-configs archive

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

##@ Documentation

docs:  ## Update all auto-generated documentation (map, changelog, architecture)
	@echo "$(GREEN)Generating documentation...$(NC)"
	@mkdir -p docs/auto
	@echo "  Generating REPO_MAP.md..."
	@curl -fsSL $(REPO_STANDARDS_URL)/repo_map.py | $(PYTHON) - --output docs/auto/REPO_MAP.md
	@echo "  Generating CHANGELOG.md..."
	@curl -fsSL $(REPO_STANDARDS_URL)/changelog.py | $(PYTHON) - --from-git --with-commits --output docs/auto/CHANGELOG.md
	@echo "  Generating ARCHITECTURE_AUTO.md..."
	@curl -fsSL $(REPO_STANDARDS_URL)/generate_architecture.py | $(PYTHON) - --output docs/auto/ARCHITECTURE_AUTO.md

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

##@ Maintenance

sync-configs:  ## Sync config files from repo-standards
	@echo "$(GREEN)Syncing config files...$(NC)"
	@curl -fsSL https://raw.githubusercontent.com/zepfu/repo-standards/main/scripts/sync-configs.sh$(date +%s) | bash -s -- --yes
	@echo "$(GREEN)✓ Configs synced$(NC)"

archive:  ## Create tar.gz archive for AI context
	@curl -fsSL $(REPO_STANDARDS_URL)/archive.sh | sh
