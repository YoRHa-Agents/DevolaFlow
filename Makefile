# DevolaFlow Build System
# Design ref: design_dual_system.md §4.5

.PHONY: all test lint build-skill sync-human-docs check-drift validate-templates clean install \
       build-site release-preflight release-dry-run scaffold-agent agent-reports \
       compile-rules check-rules-drift precommit precommit-fast precommit-full \
       scaffold-template scaffold-reference audit-references audit-long-references

all: lint test validate-templates build-skill sync-human-docs sync-cursor-skill compile-rules check-drift check-rules-drift

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

# v10.1.0 PV-04 — apply writing-style transforms to hand-edited
# human-facing docs (README + CHANGELOG + EN/ZH guides). The
# `generate_human_docs.py` pipeline already humanizes EN/ZH guides
# at generation time (Q-B); this target covers the hand-edited
# surface so authors can run the same humanizer on demand. Per Q-D,
# the CHANGELOG is hit with T-S1 + T-S5 only (technical_concise).
.PHONY: humanize-docs
humanize-docs:
	@python scripts/humanize_doc.py apply README.md -v
	@python scripts/humanize_doc.py apply CHANGELOG.md -v
	@for f in workflow-system/human/en/*.md workflow-system/human/zh/*.md; do \
		python scripts/humanize_doc.py apply "$$f" -v; \
	done

.PHONY: check-humanize
check-humanize:
	@python scripts/humanize_doc.py check README.md
	@python scripts/humanize_doc.py check CHANGELOG.md
	@for f in workflow-system/human/en/*.md workflow-system/human/zh/*.md; do \
		python scripts/humanize_doc.py check "$$f"; \
	done

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

# v8.2.7 — opt-in REPORT.md surface (closes H-005). Regenerates the four
# canonical reports (.local/.agent/REPORT.md, .local/memory/REPORT.md,
# .rules/REPORT.md, plus per-archive REPORT.md files). Idempotent: with a
# pinned clock, two consecutive invocations produce byte-identical files.
agent-reports:
	python -m devolaflow.agent_workspace.reporter --all

# v8.5.0 PV-05 (T8 NineS Hygiene A3 closure) — rebuild NineS index.
# Wraps `nines analyze --target-path . --depth deep --agent-impact --keypoints`
# via `devolaflow.nines.researcher.rebuild_index`. Refreshes the NineS
# index so `index_recall` recovers from the v8.4.x baseline of 0.8 to
# the cycle target 0.85+ (per .local/research/v9.0.0_pv05_design.md §1.2).
# Re-run after a `data/golden_test_set/` refresh or a fresh checkout.
.PHONY: nines-index-rebuild
nines-index-rebuild:
	python -c "from devolaflow.nines.researcher import rebuild_index; \
import json; r = rebuild_index(project_root='.', src_dir='src/devolaflow', timeout=300); \
print(json.dumps({'ok': True, 'keys': sorted(r.keys()) if isinstance(r, dict) else 'non-dict'}))"

check-drift:
	check-drift

# v9.1.0 (G-008 + G-009) — .rules/ corpus targets.
#
# Naming distinction (kept deliberate so future readers don't conflate them):
#   * `compile-rules` (Makefile alias, this section) wraps the `sync-rules`
#     console script (defined by pyproject.toml [project.scripts]). The
#     Makefile name is the user-facing entry point; the console script is
#     the implementation. Two names exist so `make all` reads naturally
#     ("compile rules") while pyproject keeps the verb-first script name
#     consistent with `sync-cursor-skill` / `sync-human-docs`.
#   * `check-rules-drift` (this section) ≠ `check-drift` (above).
#     `check-drift` lints HUMAN docs vs agent source; `check-rules-drift`
#     lints COMPILED .rules/ outputs vs the pinned hashes in
#     .rules/.compile-hashes.json. Both run in `make all` because they
#     cover complementary surfaces.

# v9.1.0 (G-008) — Compile .rules/*.mdc → .cursor/rules/repo-governance.mdc + AGENTS.md.
# Wraps the `sync-rules` console script (defined by pyproject.toml [project.scripts]).
# Run after editing any .rules/*.mdc to refresh compiled outputs.
compile-rules:
	sync-rules

# v9.1.0 (G-009) — Check that compiled .rules/ outputs match the pinned
# hashes in .rules/.compile-hashes.json. Distinct from `check-drift`
# (which lints human docs vs agent source).
check-rules-drift:
	check-rules-drift

detect-repo-mode:
	bash scripts/detect-repo-mode.sh

build-site:
	bash scripts/build-site.sh

# v10.2.1 PV-02 (D-S-3 / D-V-1) — 7th SI-10 step: Si-Chip iteration_delta gate.
# The 6 base SI-10 gates are codified at .cursor/rules/repo-governance.mdc §W-9
# (pytest / ruff check / ruff format / test_version / test_benchmarks /
# check-cursor-skill). v10.2.1 adds the Si-Chip iteration_delta gate as the
# 7th step; this Makefile target is the canonical wire so the cycle-wide
# pre-commit protocol fires deterministically per `.local/research/v10.2.0_cycle_plan.md`
# §4 D-V-1.
.PHONY: iteration-delta-gate
iteration-delta-gate:
	@echo "Si-Chip iteration_delta gate (SI-10 step 7, v10.2.0 cycle)"
	@python -m pytest tests/test_sichip_iteration_delta_gate.py -q --no-cov

release-preflight: lint test validate-templates build-skill sync-human-docs check-cursor-skill compile-rules check-drift check-rules-drift iteration-delta-gate
	@echo "--- Release preflight PASSED ---"
	@echo "Next: python scripts/bump_version.py <version> --tag"
	@echo "Then: git add -A && git commit -m 'chore: bump version to <version>'"
	@echo "Then: git push origin main --tags"

# v10.4.0 PV-05 (D-X-3) — SI-10 fast-path / full-path split.
#
# `precommit-fast` runs ONLY ruff + smoke pytest (`-x --lf`); it is
# suitable for in-PR iteration but is NEVER a substitute for SI-10.
# `precommit-full` is an alias for `release-preflight` (the canonical
# 7-step W-9 chain). `precommit` (no suffix) defaults to the SAFE full
# path so an operator who types `make precommit` always gets full
# coverage. Per W-9.1 (telegraphed); the SI-10 invariant remains
# unchanged at 7 gates.
.PHONY: precommit precommit-fast precommit-full
precommit-fast:
	@echo "[precommit-fast] ruff check --fix + ruff format + pytest -x --lf"
	@ruff check --fix src/ tests/
	@ruff format src/ tests/
	@python -m pytest tests/ -x --lf --no-cov -q

precommit-full: release-preflight
	@echo "[precommit-full] full SI-10 chain complete (alias for release-preflight)"

precommit: precommit-full
	@echo "[precommit] default = precommit-full (use precommit-fast for iteration)"

# v10.4.0 PV-05 (D-X-1, D-X-2) — scaffold CLIs.
.PHONY: scaffold-template scaffold-reference
scaffold-template:
	@echo "Usage: python scripts/scaffold_template.py <name> --primitives a,b,c --category build"
	@echo "       (run with --dry-run to preview without writes)"

scaffold-reference:
	@echo "Usage: python scripts/scaffold_reference.py <name> --tier large --load-when '<trigger>'"
	@echo "       (run with --dry-run to preview without writes)"

# v10.4.0 PV-05 (D-D-1, D-D-2) — reference utilization + long-reference audits.
.PHONY: audit-references audit-long-references
audit-references:
	@python scripts/audit_reference_utilization.py

audit-long-references:
	@python scripts/audit_long_reference_usage.py

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
