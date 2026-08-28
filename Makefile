# ------------------------------------------------------------------------------
# SentraAura — Development Makefile
# Common tasks for local development, testing, and deployment.
# ------------------------------------------------------------------------------

.PHONY: help dev-up dev-down dev-logs test lint fmt migrate seed build push deploy

# Default target
help:
	@echo "SentraAura Development Commands:"
	@echo ""
	@echo "  make dev-up          Start local development stack"
	@echo "  make dev-down        Stop local development stack"
	@echo "  make dev-logs        Tail logs from all services"
	@echo "  make test            Run all tests"
	@echo "  make test-unit       Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make lint            Run linters (ruff, mypy)"
	@echo "  make fmt             Format code"
	@echo "  make migrate         Run database migrations"
	@echo "  make migrate-down    Rollback last migration"
	@echo "  make seed            Seed local database"
	@echo "  make build           Build all service images"
	@echo "  make build-SERVICE   Build specific service image"
	@echo "  make push            Push images to registry"
	@echo "  make deploy-dev      Deploy to dev environment"
	@echo "  make deploy-staging  Deploy to staging environment"
	@echo "  make tf-plan         Run Terraform plan for dev"
	@echo "  make tf-apply        Run Terraform apply for dev"
	@echo "  make helm-lint       Lint all Helm charts"
	@echo "  make helm-template   Template Helm charts"
	@echo "  make clean           Clean build artifacts"
	@echo "  make audit           Run security audit"

# Local Development
dev-up:
	docker compose -f local/docker-compose.yml up -d --wait
	@echo "Local stack ready!"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  Redis: localhost:6379"
	@echo "  NATS: localhost:4222"
	@echo "  Temporal: localhost:7233"
	@echo "  Temporal UI: http://localhost:8233"
	@echo "  MinIO: http://localhost:9001"
	@echo "  Grafana: http://localhost:3000"
	@echo "  MailHog: http://localhost:8025"

dev-down:
	docker compose -f local/docker-compose.yml down -v

dev-logs:
	docker compose -f local/docker-compose.yml logs -f

# Testing
test: test-unit test-integration

test-unit:
	@echo "Running unit tests..."
	@for svc in services/*/; do \
		if [ -d "$$svc/tests/unit" ]; then \
			echo "Testing $$(basename $$svc)..."; \
			cd $$svc && pytest tests/unit -v --tb=short && cd ../..; \
		fi \
	done

test-integration:
	@echo "Running integration tests..."
	pytest tests/integration -v --tb=short

test-contract:
	@echo "Running contract tests..."
	python -m pytest tests/contract -v

test-workflow:
	@echo "Running workflow tests..."
	pytest tests/workflow -v --temporal-test-server

# Linting & Formatting
lint:
	ruff check services/ packages/ contracts/
	mypy --strict services/ packages/

fmt:
	ruff format services/ packages/ contracts/

fmt-check:
	ruff format --check services/ packages/ contracts/

# Database
migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

migrate-create:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

seed:
	@echo "Seeding local database..."
	python local/seed/seed_channels.py
	python local/seed/seed_topics.py
	python local/seed/seed_assets.py

# Building
build:
	@for svc in services/*/; do \
		make build-$$(basename $$svc); \
	done

build-%:
	@echo "Building $*..."
	docker build -t sentra/$*:latest -f services/$*/Dockerfile .

# Pushing
push:
	@for svc in services/*/; do \
		make push-$$(basename $$svc); \
	done

push-%:
	@echo "Pushing $*..."
	docker tag sentra/$*:latest ghcr.io/sentra-aura/$*:latest
	docker push ghcr.io/sentra-aura/$*:latest

# Deployment
deploy-dev:
	@echo "Deploying to dev..."
	cd infra/terraform/environments/dev && terraform apply -auto-approve
	@echo "Running Helm releases..."
	@for release in infra/helm/releases/*/; do \
		svc=$$(basename $$release); \
		helm upgrade --install $$svc infra/helm/charts/sentra-service \
			--namespace sentra \
			--values infra/helm/environments/dev/values.yaml \
			--set serviceName=$$svc \
			--set imageTag=latest; \
	done

deploy-staging:
	@echo "Deploying to staging..."
	cd infra/terraform/environments/staging && terraform apply

# Terraform
tf-init:
	cd infra/terraform/environments/dev && terraform init

tf-plan:
	cd infra/terraform/environments/dev && terraform plan

tf-apply:
	cd infra/terraform/environments/dev && terraform apply

tf-fmt:
	terraform fmt -recursive infra/terraform/

tf-validate:
	@for env in local dev staging canary production; do \
		echo "Validating $$env..."; \
		cd infra/terraform/environments/$$env && terraform validate && cd ../../..; \
	done

# Helm
helm-lint:
	helm lint infra/helm/charts/sentra-service
	@for chart in infra/helm/charts/platform/*/; do \
		helm lint $$chart; \
	done

helm-template:
	helm template sentra-service infra/helm/charts/sentra-service \
		--values infra/helm/environments/dev/values.yaml \
		--set serviceName=test-service \
		--set imageTag=test

# Security
audit:
	@echo "Running security audit..."
	bandit -r services/ packages/
	semgrep --config=p/security-audit services/ packages/
	detect-secrets scan --all-files

sbom:
	@for svc in services/*/; do \
		syft sentra/$$(basename $$svc):latest -o spdx-json=sbom-$$(basename $$svc).json; \
	done

scan:
	@for svc in services/*/; do \
		grype sentra/$$(basename $$svc):latest --fail-on high; \
	done

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	docker system prune -f

# CI Helpers
ci-lint:
	ruff check services/ packages/ --output-format=github
	ruff format --check services/ packages/
	mypy --strict services/ packages/

ci-test:
	pytest services/ -v --cov --cov-report=xml

ci-build:
	@for svc in services/*/; do \
		docker build -t sentra/$$(basename $$svc):$${CI_COMMIT_SHA:-latest} -f services/$$(basename $$svc)/Dockerfile .; \
	done
