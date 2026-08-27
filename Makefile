# DevolaFlow Build System
# Design ref: design_dual_system.md §4.5

.PHONY: all test test-core test-cov test-version test-harness lint build-skill sync-human-docs \
       check-drift validate-templates clean install \
       generate-demo-seed-catalog check-demo-seed-catalog build-site \
       release-preflight release-dry-run scaffold-agent agent-reports \
       compile-rules check-rules-drift check-module-size check-agent-language precommit precommit-fast precommit-full \
       scaffold-template scaffold-reference audit-references audit-long-references \
       check-import-graph

define RUN_TIMED
start=$$(date +%s); printf '[gate:%s] START\n' "$(1)"; $(2); status=$$?; elapsed=$$(($$(date +%s)-start)); printf '[gate:%s] %s elapsed=%ss\n' "$(1)" "$$([ $$status -eq 0 ] && printf PASS || printf FAIL)" "$$elapsed"; exit $$status
endef

all: lint test validate-templates build-skill sync-human-docs sync-cursor-skill compile-rules check-drift check-rules-drift check-import-graph

install:
	pip install -e ".[dev]"

lint:
	@$(call RUN_TIMED,lint,ruff check src/ tests/ && ruff format --check src/ tests/)

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

test:
	pytest tests/ -v --tb=short

test-cov:
	@$(call RUN_TIMED,test-cov,GHOST_FULL=1 pytest tests/ -v --tb=short --cov=devolaflow --cov-report=term-missing --cov-report=json && python scripts/check_module_coverage.py coverage.json --minimum 70)

# ---------------------------------------------------------------------------
# v14.5.0 G-033 — SI-10 core gate targets (single-execution chain).
#
# The W-9 / SI-10 protocol is 7 gates; `.rules/workflow.mdc` §W-9 is
# RECOMPILED FROM THIS SECTION (the Makefile is the source of truth for
# the gate list per the v14.2.1 G-033 recompile). The 7 gates map to 6
# make targets (`lint` runs gates 2+3):
#
#   gate 1  test-core             pytest suite MINUS the standalone gate files
#   gate 2  lint (ruff check)     no lint errors
#   gate 3  lint (ruff format)    formatting correct
#   gate 4  test-version          version consistency (standalone)
#   gate 5  test-harness          harness domain guard (standalone)
#   gate 6  check-cursor-skill    cursor-skill mirror in sync
#   gate 7  iteration-delta-gate  Si-Chip iteration_delta (standalone)
#
# Single-execution design (chosen over no-op-with-note): gates 4, 5 and 7
# run their test files standalone, and gate 1 `--ignore`s exactly those
# three files, so no test executes twice in one chain run. Failure
# isolation stays meaningful — a version-consistency or harness
# regression fails its OWN named gate, not a generic step-1 failure
# (a no-op gate 4/5 would report green without attributable evidence).
# Each gate remains individually invocable; `make test` keeps the
# undeduplicated full suite for developer convenience.
test-core:
	@$(call RUN_TIMED,test-core,pytest tests/ -q --tb=short \
		--ignore=tests/harness \
		--ignore=tests/test_version.py \
		--ignore=tests/test_sichip_iteration_delta_gate.py)

test-version:
	@$(call RUN_TIMED,test-version,python -m pytest tests/test_version.py -v)

test-harness:
	@$(call RUN_TIMED,test-harness,python -m pytest tests/harness/ -v)

validate-templates:
	validate-template --all

# v14.5.0 G-035 (tooling slice) — VERIFIED NO-OP: the `build-skill`
# console script (devolaflow.cli:build_skill_cmd → build_skill.build_all)
# is already truth-driven. Without `--tools`, it iterates
# `AdapterRegistry.list_names()` = the 4 core adapters registered by
# `adapters/registry.py::create_default_registry` PLUS every YAML
# adapter discovered under `adapter_configs/*.yaml` by
# `adapters/data_driven.py::load_data_driven_adapters`. No hardcoded
# adapter list exists; W-12's "4 core + registered data-driven set"
# wording (recompiled v14.2.1) matches the implementation. The `--all`
# flag below is inert vocabulary (only `--tools` is parsed) kept for
# operator-facing self-documentation.
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
	@$(call RUN_TIMED,check-cursor-skill,python scripts/sync_cursor_skill.py --check)

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

check-module-size:
	@$(call RUN_TIMED,check-module-size,python scripts/check_module_size.py --baseline-ref origin/main)

check-agent-language:
	@$(call RUN_TIMED,check-agent-language,python scripts/check_agent_language.py)

check-import-graph:
	@$(call RUN_TIMED,check-import-graph,python3 scripts/check_import_graph.py)

detect-repo-mode:
	bash scripts/detect-repo-mode.sh

generate-demo-seed-catalog:
	python scripts/generate_demo_seed_catalog.py

check-demo-seed-catalog:
	python scripts/generate_demo_seed_catalog.py --check

build-site:
	bash scripts/build-site.sh

# v10.2.1 PV-02 (D-S-3 / D-V-1) — 7th SI-10 step: Si-Chip iteration_delta gate.
# The 6 base SI-10 gates are codified at .cursor/rules/repo-governance.mdc §W-9
# (pytest / ruff check / ruff format / test_version / test-harness /
# check-cursor-skill). v10.2.1 adds the Si-Chip iteration_delta gate as the
# 7th step; this Makefile target is the canonical wire so the cycle-wide
# pre-commit protocol fires deterministically per `.local/research/v10.2.0_cycle_plan.md`
# §4 D-V-1.
.PHONY: iteration-delta-gate
iteration-delta-gate:
	@$(call RUN_TIMED,iteration-delta-gate,echo "Si-Chip iteration_delta gate (SI-10 step 7)" && python -m pytest tests/test_sichip_iteration_delta_gate.py -q --no-cov)

# v14.5.0 G-033 — release-preflight = SI-10 CORE (the 7 W-9 gates, in
# W-9 order, single-execution per the `test-core` section above) plus
# the RELEASE-ONLY EXTRAS. The extras are NOT part of the SI-10 gate
# count; they are release-hygiene targets that only the preflight chain
# (and `make all`) runs:
#
#   release-only extras: validate-templates, build-skill,
#                        sync-human-docs, compile-rules, check-drift,
#                        check-rules-drift
#
#   post-prerequisite:   check-demo-seed-catalog, then build-site
#                       (the recipe keeps these after generated docs/rules)
#
# SI-10 core:           test-core lint test-version test-harness
#                       check-cursor-skill iteration-delta-gate
release-preflight: test-core lint test-version test-harness check-import-graph check-agent-language check-cursor-skill iteration-delta-gate validate-templates build-skill sync-human-docs compile-rules check-drift check-rules-drift check-module-size
	$(MAKE) check-demo-seed-catalog
	$(MAKE) build-site
	@echo "--- Release preflight PASSED ---"
	@echo "Release sequence (start on a feature branch before this target):"
	@echo "1. python scripts/bump_version.py <version>"
	@echo "2. make release-preflight  # mandatory on the bumped tree"
	@echo "3. Commit the verified bump, open a PR, and merge it into main"
	@echo "4. git checkout main"
	@echo "5. git fetch origin main && git pull --ff-only origin main"
	@echo "6. python scripts/bump_version.py <version> --tag --dry-run"
	@echo "7. python scripts/bump_version.py <version> --tag  # clean main HEAD == origin/main"
	@echo "8. git push origin v<version>  # push the tag only"

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

# v10.5.0 PV-01..PV-05 (D-A-1, D-A-2, D-D-3, D-D-4) — architecture &
# documentation health audits. Each one is observability-only —
# emits a markdown report; no source modifications. Run them with
# explicit `--output .local/research/v10.5.X_*.md` to refresh the
# audit artifacts that the v10.5.0 W-18 lint pins.
.PHONY: audit-layers audit-templates measure-friction audit-w18
audit-layers:
	@python scripts/audit_layer_usage.py

audit-templates:
	@python scripts/audit_template_usage.py

measure-friction:
	@python scripts/measure_reference_friction.py

audit-w18:
	@python scripts/audit_w18_lint_maintenance.py

# v10.7.0 (D-P-1, D-O-1, D-O-2, D-O-3) — Protocol audit + observability.
# Each target is observability-only — emits a markdown / CSV / YAML
# report; no source modifications. Run them with explicit
# `--output .local/research/v10.7.X_*.md` to refresh the audit
# artifacts that the v10.7.0 W-18 lint pins.
.PHONY: audit-canonical-emptiness gen-evaluator-rosetta auto-collect-si3 index-research

# D-P-1 — canonical_order field non-empty rate audit. Audit-only;
# preserves G-6 frozen-prefix gate (positions 1-12 reported but
# never selectable for mutation per A-2.1).
audit-canonical-emptiness:
	@python scripts/audit_canonical_order_emptiness.py \
		--output .local/research/v10.7.1_canonical_order_emptiness.md

# D-O-1 companion — emit the 6 × 9 evaluator rosetta as machine-
# consumable CSV / markdown sanity-check. Pairs with the canonical
# `workflow-system/agent/references/evaluator-rosetta.md` reference.
gen-evaluator-rosetta:
	@python scripts/generate_evaluator_rosetta.py --markdown \
		--output .local/research/v10.7.2_evaluator_rosetta.md

# D-O-2 — SI-3 6-dim objective metric auto-collection. OPT-IN: not
# wired into release-preflight per the cycle-budget design (SI-10
# stays at 7 gates). Cycle-lead invokes manually at PV close.
# `--mock-data` short-circuits real probe invocation for CI smoke.
auto-collect-si3:
	@python scripts/auto_collect_si3_metrics.py --mock-data \
		--output .local/research/v10.7.3_si3_auto_collection.md

# D-O-3 — mid-cycle research artifact index. Workspace-local +
# ephemeral; complementary to the W-19 cycle-end committed archive
# at `docs/cycle-archive/v<X.Y.0>/`.
index-research:
	@python scripts/index_mid_cycle_research.py \
		--output .local/research/v10.7.4_research_index.md

# v10.8.0 D-C-2 — re-capture bridge shape-contract fixtures from live
# plugin binaries (Si-Chip / RTK / ui-pro). Gracefully skips
# plugins that are missing (logs WARNING, returns exit 0 per D-C-2 §9
# R2). Per-PR pytest uses CHECKED-IN fixtures from
# `tests/integration/fixtures/` — this target is operator-pull for
# weekly refresh; the real automation lives in
# `.github/workflows/bridge-fixture-refresh.yml` (cron weekly).
.PHONY: refresh-bridge-fixtures
refresh-bridge-fixtures:
	@python scripts/refresh_bridge_fixtures.py

# v10.6.0 PV-03 (D-Q-4) — compressor/ post-split health snapshot.
# Closes the v9.3.0 PV-04 → v10.6.0 coverage gap on the largest
# Python file in the tree (`transforms.py` at 2,198 LOC). Pure-audit
# observability — runs `radon cc -nB` against the 4-file package and
# emits a markdown synthesis; no source modifications. When radon is
# unavailable, falls back to LOC-only mode per W-2. Output path is
# `.local/research/v10.6.0_compressor_health.md` (the v10.6.0 W-18
# lint pins this exact path).
.PHONY: snapshot-compressor
snapshot-compressor:
	@python scripts/snapshot_compressor_health.py \
		--output .local/research/v10.6.0_compressor_health.md

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

# v14.5.0 G-036 — D-5 CHANGELOG single-application lint (telegraphed
# v11.1.0 retro §3 D-5; re-telegraphed v12.5.0 retro §6 #12). Standalone
# target — deliberately NOT added to the SI-10 chain (the gate-chain
# reorganization is a separate v14.5.0 task per G-033). CI runs the same
# script with the PR base sha in .github/workflows/ci.yml.
.PHONY: lint-changelog
lint-changelog:
	@python scripts/lint_changelog.py --base-ref origin/main
