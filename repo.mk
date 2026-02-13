# repo.mk - Repository-specific Makefile targets
# Included via -include in the main Makefile
#
# Add your targets with inline ## comments for automatic help generation

.PHONY: build run run-gpu

##@ Docker

build:  ## Build Docker image
	@echo "$(GREEN)Building Docker image...$(NC)"
	@docker build -t $(DOCKER_IMAGE):dev \
		--build-arg GIT_SHA=$$(git rev-parse --short HEAD) \
		--build-arg BUILD_TIME=$$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
		.
	@echo "$(GREEN)? Built $(DOCKER_IMAGE):dev$(NC)"

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
