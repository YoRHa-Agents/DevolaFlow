# DevolaFlow Build System
# Design ref: design_dual_system.md §4.5

.PHONY: all test lint build-skill sync-human-docs check-drift validate-templates clean install \
       build-site release-preflight release-dry-run scaffold-agent

all: lint test validate-templates build-skill sync-human-docs sync-cursor-skill check-drift

install:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --tb=short --cov=devolaflow --cov-report=term-missing

validate-templates:
	validate-template --all

build-skill:
	build-skill --all

sync-human-docs:
	python scripts/generate_human_docs.py --all

sync-human-docs-en:
	python scripts/generate_human_docs.py --lang en

sync-human-docs-zh:
	python scripts/generate_human_docs.py --lang zh

sync-cursor-skill:
	python scripts/sync_cursor_skill.py

check-cursor-skill:
	python scripts/sync_cursor_skill.py --check

.PHONY: sync-cursor-skill check-cursor-skill scaffold-agent

# v8.2.3 — one-shot re-scaffold for existing repos. Idempotent: safe to re-run.
# Repairs G-1 (.local/index.md drift) + G-2 (missing TRACKER.md / MEMORY.md)
# and creates the .local/.agent/{active,handoff,archive}/ + .local/memory/specs/
# substrate per .local/research/v8.3.0_design.md §1.1.
scaffold-agent:
	python -c "from devolaflow.local.workspace import scaffold_local; scaffold_local('.')"

check-drift:
	check-drift

detect-repo-mode:
	bash scripts/detect-repo-mode.sh

build-site:
	bash scripts/build-site.sh

release-preflight: lint test validate-templates build-skill sync-human-docs check-cursor-skill check-drift
	@echo "--- Release preflight PASSED ---"
	@echo "Next: python scripts/bump_version.py <version> --tag"
	@echo "Then: git add -A && git commit -m 'chore: bump version to <version>'"
	@echo "Then: git push origin main --tags"

release-dry-run:
	@echo "=== Release dry-run ==="
	@echo "1. Preflight checks..."
	$(MAKE) lint test validate-templates build-skill sync-human-docs check-drift
	@echo ""
	@echo "2. Current version:"
	@python scripts/bump_version.py
	@echo ""
	@echo "3. Site build test..."
	$(MAKE) build-site
	@echo ""
	@echo "=== Dry-run complete. Run 'make release-preflight' for the real check. ==="

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache htmlcov .coverage _site/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
