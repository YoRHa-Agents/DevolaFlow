#!/usr/bin/env python3
"""Sync .cursor/skills/devola-flow/ to the canonical workflow-system/agent/ skill.

This is the repo-local project-skill mirror that Cursor picks up when the user
opens the DevolaFlow repo itself. It mirrors EXACTLY the 19 files that
scripts/install.sh::install_cursor downloads (SKILL.md + 15 references + 3
examples), plus a single-line .devola-flow-version stamp equal to
src/devolaflow/__init__.py __version__.

The mirror is **opt-in** (gitignored as of chore/cursor-skill-mirror-untrack).
Default sync and --check are no-ops when the mirror directory is absent so
fresh clones, CI runners, and bump_version.py all pass without it. To opt in,
run --init once; subsequent default-sync runs will keep the mirror fresh.

Run manually:
    python scripts/sync_cursor_skill.py           # sync if mirror present; no-op otherwise
    python scripts/sync_cursor_skill.py --init    # bytewise-create the mirror (opt-in)
    python scripts/sync_cursor_skill.py --check   # exit 1 only on present-and-stale; 0 if absent

scripts/bump_version.py invokes this at the end of every version bump; when
the mirror is absent the hook prints a "skipped" line and exits 0.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

# Set must match scripts/install.sh::install_cursor (SKILL + 15 refs + 3 examples).
# Edit BOTH files in lockstep if you ever change what Cursor users receive.
# v8.0.0 P-08 grew this set 12 -> 13 by appending references/behavioral-guidelines.md
# (the L3 behavioral primitives reference wired through the new top-level
# behavioral_guidelines dispatch field at canonical_order position 14, schema v3).
# v8.3.0 PV-09 grew this set 13 -> 14 by appending references/agent-workspace.md
# (the change-driven workspace reference covering .local/.agent/, append-only
# handoff envelopes, source-of-truth specs, and per-artifact token budgets).
# v8.4.0 rollup grew this set 14 -> 15 by appending references/shell-proxy.md
# (the RTK + memory-router stack reference covering runtime-plugins.yaml RTK row,
# the shell_proxy/ package, the pre_shell_call lifecycle hook, the memory_router/
# planning fast-path, and the .local/memory/{cases,commands}/ recipe layers).
# v9.0.0 PV-01 (v8.4.1) grew this set 15 -> 16 by appending references/plan-mode-enforcement.md
# (the plan-mode L0 operating contract reference absorbing SKILL.md §"Mode
# Awareness" PLAN MODE detail + §"Reinforcement Rules" mechanism, freeing
# ~57 lines of SKILL.md headroom and closing R7 carry-forward + B-01 from
# .local/research/v9.0.0_gap_analysis.md).
# v9.0.0 PV-05 (v8.5.0) grew this set 16 -> 17 by appending references/env-flags.md
# (the canonical DEVOLAFLOW_* env-var inventory: 8 active runtime flags + 6
# forward-declared gate-primitive flags + 4 BG defaults + 3 test-fixture flags).
# Pairs with Workflow Rule W-20 (env-flag reuse vs new-flag policy).
# v10.4.0 PV-05 grew this set 17 -> 18 by appending references/troubleshooting.md
# (the 15th SF-4 canonical reference: ~30 distinct operator-trip patterns
# harvested from cycle retrospectives v8.0.0 -> v10.3.0; D-X-5 closure).
# v10.7.0 D-O-1 grew this set 19 -> 20 (with the 4th example landed at
# v10.5.0 PV-01) by appending references/evaluator-rosetta.md (the 16th
# SF-4 canonical reference: 6 × 9 SI-3 × NineS × Si-Chip cross-walk).
# v10.8.0 D-C-1 grew this set 20 -> 21 by appending references/degraded-mode.md
# (the 17th SF-4 canonical reference: per-plugin unreachable-scenario contract
# for NineS / Si-Chip / RTK / ui-pro with a "Degraded ≠ Full" leading warning
# per D-C-1 §9 R1 mitigation). Pairs with `tests/test_degraded_mode.py`.
CANONICAL_DIR = Path("workflow-system/agent")
MIRROR_DIR = Path(".cursor/skills/devola-flow")
MIRRORED_FILES = [
    "SKILL.md",
    "references/agent-hierarchy.md",
    "references/agent-workspace.md",
    "references/meta-framework.md",
    "references/decomposition-gate.md",
    "references/repo-modes.md",
    "references/execution-protocol.md",
    "references/message-schemas.md",
    "references/team-roles.md",
    "references/context-isolation.md",
    "references/behavioral-guidelines.md",
    "references/shell-proxy.md",
    "references/plan-mode-enforcement.md",
    # v8.5.0 PV-05 — 13th SF-4 canonical reference (env-flag inventory).
    "references/env-flags.md",
    # v8.5.1 PV-06 — 14th SF-4 canonical reference (CompressionPipeline protocol
    # + 6-transform unification + multi-pass filter chain). Pairs with
    # src/devolaflow/compression_pipeline.py and schemas/compression-pipeline.yaml.
    "references/compression-pipeline.md",
    # v10.4.0 PV-05 — 15th SF-4 canonical reference (operator troubleshooting
    # handbook). Quick lookup index + per-symptom diagnostic patterns +
    # escalation patterns harvested from v8.0.0 -> v10.3.0 retros.
    "references/troubleshooting.md",
    # v10.7.0 D-O-1 — 16th SF-4 canonical reference (three-evaluator
    # rosetta). 6 × 9 cross-walk between SI-3 dimensions + NineS hygiene
    # axes / capability sub-bundles + Si-Chip iteration_delta scalar with
    # per-cell verbatim source citations. Pairs with
    # `scripts/auto_collect_si3_metrics.py` (D-O-2) and
    # `scripts/generate_evaluator_rosetta.py` (D-O-1 companion).
    "references/evaluator-rosetta.md",
    # v10.8.0 D-C-1 — 17th SF-4 canonical reference (upstream-unreachable
    # degraded-mode contract). Per-plugin fallback doc for NineS / Si-Chip /
    # RTK / ui-pro with "Degraded ≠ Full" leading warning (D-C-1 §9 R1
    # mitigation). Pairs with `tests/test_degraded_mode.py` regression
    # suite and closes the v10.3.0 retrospective §3 NineS A1 pain. v12.5.0
    # PV-05 D-1.3 augments §"Plugin Matrix" + Section 5 with the codegraph
    # row + structured-cause failure-mode taxonomy.
    "references/degraded-mode.md",
    # v12.5.0 PV-05 D-1.3 — codegraph reference (NEW Tier-2 Large-tier
    # entry; ~248 lines under the ≤1000 ceiling). Documents the 9 MCP
    # tools / 5 Python wrapper helpers / DevolaFlow integration map /
    # degraded-mode contract / cache management. Pairs with
    # src/devolaflow/codegraph/ + tests/test_codegraph.py +
    # tests/test_codegraph_workflow_wiring.py.
    "references/codegraph.md",
    # v13.0.0 — impeccable reference (NEW Tier-2 Large-tier entry; ~179
    # lines under the ≤1000 ceiling). Documents the design language system
    # (1 skill + 23 /impeccable commands), the no-LLM `impeccable detect`
    # anti-pattern detector, the npm_then_init backend (auto-detect harness),
    # the ui-pro → impeccable web-design composition, and the degraded-mode
    # contract. Pairs with workflow-system/agent/templates/builtin/web-design.yaml
    # + tests/test_impeccable_reference_doc.py.
    "references/impeccable.md",
    # v14.0.0 — human-surface reference (24th SF-4 canonical Tier-2 entry;
    # ~569 lines under the ≤1000 Large-tier ceiling). Documents the new
    # `.local/human/` surface: immutable INPUT (constitution + REQ-IDs +
    # append-only amendments) / anti-flooding OUTPUT (convergence report +
    # DIGEST), the C-9 token budgets, INPUT-only git tracking, the
    # scan_workspace discovery fields, and the trace_requirements /
    # lint_human / render_human_report APIs. Pairs with
    # src/devolaflow/agent_workspace/requirements_trace.py +
    # src/devolaflow/lifecycle/check_human_input_append_only.py.
    "references/human-surface.md",
    # v14.3.0 — artifact-quality reference (25th SF-4 canonical Tier-2
    # entry; well under the ≤1000 Large-tier ceiling). The EVIDENCE-ONLY
    # rubric for the L3 task artifact itself per v15-ADR-007: four
    # excellence dimensions (correctness / minimal diff / test evidence /
    # convention adherence), the dimension → lean-report transport map
    # (self_check / ac_results / diff_stats), the §4 self-verify
    # checklist, and §5 failure honesty. L3 emits evidence, NEVER a
    # numeric score (doctrine guard: reject_subagent_quality_score hook).
    # Pairs with references/execution-protocol.md §15 "L3 Self-Verify".
    "references/artifact-quality.md",
    "examples/full-pipeline-trace.md",
    "examples/hotfix-trace.md",
    "examples/convergence-loop-trace.md",
    # v10.5.0 PV-01 (D-A-1) grew the example set 3 -> 4 by appending
    # examples/multi-stage-trace.md (the multi-team analyze + cross-stage
    # merge counter-example referenced by the SKILL.md Quick Action
    # Decision advisory annotation). The audit's recommendation
    # (`scripts/audit_layer_usage.py`) is data-driven on the v10.4.0
    # corpus; this example documents WHEN the L1 + L2 layers are still
    # required so operators have a worked counter-case before they
    # collapse the dispatch chain.
    "examples/multi-stage-trace.md",
]
STAMP_FILE = MIRROR_DIR / ".devola-flow-version"
VERSION_FILE = Path("src/devolaflow/__init__.py")
VERSION_PATTERN = re.compile(r'__version__\s*=\s*"([^"]+)"')


def read_canonical_version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    m = VERSION_PATTERN.search(text)
    if not m:
        raise SystemExit(f"{VERSION_FILE}: __version__ not found")
    return m.group(1)


def iter_pairs() -> list[tuple[Path, Path]]:
    return [(CANONICAL_DIR / rel, MIRROR_DIR / rel) for rel in MIRRORED_FILES]


def check() -> int:
    """Exit 1 if any mirrored file differs or the stamp is wrong; else 0.

    Returns 0 (no-op) when MIRROR_DIR is absent — the mirror is opt-in and
    CI / fresh clones must pass without it.
    """
    if not MIRROR_DIR.exists():
        print(f"[.cursor mirror] not present at {MIRROR_DIR} — opt-in (see Rule SF-3)")
        return 0
    version = read_canonical_version()
    problems: list[str] = []
    for src, dst in iter_pairs():
        if not src.is_file():
            problems.append(f"MISSING CANONICAL: {src}")
            continue
        if not dst.is_file():
            problems.append(f"MISSING MIRROR:    {dst}")
            continue
        if src.read_bytes() != dst.read_bytes():
            problems.append(f"OUT OF SYNC:       {dst} differs from {src}")
    if not STAMP_FILE.is_file():
        problems.append(f"MISSING STAMP:     {STAMP_FILE}")
    else:
        stamp_lines = STAMP_FILE.read_text(encoding="utf-8").splitlines()
        first = stamp_lines[0] if stamp_lines else ""
        if first != version:
            problems.append(
                f"STAMP MISMATCH:    {STAMP_FILE} first-line={first!r} vs __version__={version!r}"
            )
    if problems:
        print(
            "[.cursor mirror] out of sync — run: python scripts/sync_cursor_skill.py",
            file=sys.stderr,
        )
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"[.cursor mirror] ok ({len(MIRRORED_FILES)} files, stamp {version})")
    return 0


def sync(*, allow_init: bool = False) -> int:
    """Sync the mirror in place.

    When MIRROR_DIR is absent and ``allow_init`` is False, exits 0 with an
    info line — does NOT create the mirror out of nothing. Only --init
    (allow_init=True) materialises the mirror from canonical, so accidental
    `bump_version.py` / `make all` runs cannot resurrect it for users who
    deliberately opted out.
    """
    if not MIRROR_DIR.exists() and not allow_init:
        print(
            f"[.cursor mirror] not present at {MIRROR_DIR} — "
            "opt-in via `--init` (see Rule SF-3)"
        )
        return 0
    version = read_canonical_version()
    changed = 0
    for src, dst in iter_pairs():
        if not src.is_file():
            raise SystemExit(f"canonical missing: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file() or src.read_bytes() != dst.read_bytes():
            shutil.copyfile(src, dst)
            changed += 1
            print(f"  sync  {dst}")
    stamp_body = f"{version}\n"
    if (
        not STAMP_FILE.is_file()
        or STAMP_FILE.read_text(encoding="utf-8") != stamp_body
    ):
        STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
        STAMP_FILE.write_text(stamp_body, encoding="utf-8")
        print(f"  stamp {STAMP_FILE} -> {version}")
        changed += 1
    if changed == 0:
        print(f"[.cursor mirror] already in sync ({len(MIRRORED_FILES)} files, stamp {version})")
    else:
        print(f"[.cursor mirror] synced {changed} file(s) to v{version}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="exit 1 only if mirror is present-and-stale (no writes); exit 0 if absent",
    )
    ap.add_argument(
        "--init",
        action="store_true",
        help="create the mirror from canonical (opt-in to project-local skill)",
    )
    args = ap.parse_args(argv)
    if args.check:
        return check()
    return sync(allow_init=args.init)


if __name__ == "__main__":
    raise SystemExit(main())
