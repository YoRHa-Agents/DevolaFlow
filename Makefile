# DevolaFlow Build System
# Design ref: design_dual_system.md §4.5

.PHONY: all test lint build-skill sync-human-docs check-drift validate-templates clean install

all: lint test validate-templates build-skill sync-human-docs check-drift

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

check-drift:
	check-drift

detect-repo-mode:
	bash scripts/detect-repo-mode.sh

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
