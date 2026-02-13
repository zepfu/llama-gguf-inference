.DEFAULT_GOAL := help
.PHONY: help all test sphinx archive clean sync-configs mermaid mermaid-png mermaid-pdf mermaid-check docs

# Configuration
SHELL := /bin/bash
PYTHON := python3
REPO_STANDARDS_URL := https://raw.githubusercontent.com/zepfu/repo-standards/main/scripts

##@ Help

help: ## Display this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

all: docs ## Build all generated assets

test: ## Run tests
	@echo "[SKIP] No tests configured"

# Include optional repo-specific Makefile
# Users can create repo.mk to add custom targets with ## comments
-include repo.mk

##@ Documentation

sphinx: ## Build and serve Sphinx documentation locally
	@echo "Building Sphinx documentation..."
	@cd docs && sphinx-build -b html . _build/html
	@echo "[PASS] Documentation built at docs/_build/html/index.html"
	@echo ""
	@echo "Serving documentation at http://localhost:8000"
	@cd docs/_build/html && python3 -m http.server 8000

docs: ## Generate auto-documentation (changelog, repo map, architecture)
	@curl -fsSL $(REPO_STANDARDS_URL)/repo_map.py | $(PYTHON) - --output docs/auto/REPO_MAP.md
	@curl -fsSL $(REPO_STANDARDS_URL)/changelog.py | $(PYTHON) - --from-git --with-commits --output docs/auto/CHANGELOG.md
	@curl -fsSL $(REPO_STANDARDS_URL)/generate_architecture.py | $(PYTHON) - --output docs/auto/ARCHITECTURE_AUTO.md
	@echo "[INFO] Formatting auto-generated markdown..."
	@mdformat --wrap 120 docs/auto/*.md 2>/dev/null \
		|| echo "[WARN] mdformat not installed -- skipping formatting (pip install mdformat)"

mermaid: ## Render all Mermaid diagrams to SVG images
	@echo "Downloading render-mermaid.sh..."
	@curl -fsSL $(REPO_STANDARDS_URL)/render-mermaid.sh -o /tmp/render-mermaid.sh
	@chmod +x /tmp/render-mermaid.sh
	@bash /tmp/render-mermaid.sh --format svg
	@rm /tmp/render-mermaid.sh

mermaid-png: ## Render all Mermaid diagrams to PNG images
	@echo "Downloading render-mermaid.sh..."
	@curl -fsSL $(REPO_STANDARDS_URL)/render-mermaid.sh -o /tmp/render-mermaid.sh
	@chmod +x /tmp/render-mermaid.sh
	@bash /tmp/render-mermaid.sh --format png
	@rm /tmp/render-mermaid.sh

mermaid-pdf: ## Render all Mermaid diagrams to PDF files
	@echo "Downloading render-mermaid.sh..."
	@curl -fsSL $(REPO_STANDARDS_URL)/render-mermaid.sh -o /tmp/render-mermaid.sh
	@chmod +x /tmp/render-mermaid.sh
	@bash /tmp/render-mermaid.sh --format pdf
	@rm /tmp/render-mermaid.sh

mermaid-check: ## Validate Mermaid diagrams (check if mmdc is installed)
	@if command -v mmdc &> /dev/null; then \
		echo "[PASS] mermaid-cli is installed: $$(mmdc --version 2>&1 | head -1)"; \
	else \
		echo "[FAIL] mermaid-cli (mmdc) not found"; \
		echo ""; \
		echo "Install with:"; \
		echo "  npm install -g @mermaid-js/mermaid-cli"; \
		exit 1; \
	fi

##@ Maintenance

sync-configs: ## Sync config files from repo-standards
	@echo "[INFO] Syncing config files from repo-standards..."
	@curl -fsSL $(REPO_STANDARDS_URL)/sync-configs.sh -o /tmp/sync-configs.sh
	@chmod +x /tmp/sync-configs.sh
	@bash /tmp/sync-configs.sh --yes; \
	EXIT_CODE=$$?; \
	if [ $$EXIT_CODE -ne 0 ]; then \
		echo "[WARN] Sync completed with warnings (exit code: $$EXIT_CODE)"; \
	fi
	@rm /tmp/sync-configs.sh

archive: ## Create tar.gz archive for AI context
	@curl -fsSL $(REPO_STANDARDS_URL)/archive.sh | sh

clean: ## Remove backup files, logs, and Zone.Identifier files
	@echo "[INFO] Cleaning repository..."
	@find . \( -name "*.bak" -o -name "*.backup" -o -name "*.old" \
		-o -name "*.orig" -o -name "*~" -o -name "*:Zone.Identifier" \
		-o -name "*.log" -o -name "*.log.*" -o -name "*.pyc" \
		-o -name "*.pyo" \) -type f -delete 2>/dev/null || true
	@find . -name "*.tar.gz" -not -path "./archive/*" \
		-type f -delete 2>/dev/null || true
	@find . -type d \( -name "__pycache__" -o -name "*.egg-info" \
		-o -name ".pytest_cache" \) -exec rm -rf {} + 2>/dev/null || true
	@echo "[PASS] Cleanup complete"
