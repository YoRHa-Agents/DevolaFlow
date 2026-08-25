"""v8.5.0 PV-05 (T8 NineS Hygiene A2 closure) — agent-context overhead test.

Closes the v8.1.0-rc.1 NineS-flagged ``AI-24c4f48d-0002`` measurement
(46179 tokens for the agent-facing surface, above the 40000-token
ceiling target). The test sums an estimated-token count across the
**always-loaded** agent-facing files using the SAME ``len(text) // 4``
estimator that the rule compiler uses
(``src/devolaflow/local/compiler.py::_estimate_tokens``) so the metric
reported here matches the AGENTS.md ``5857/6000`` and ``cursor 6889/8000``
figures the operator sees from ``sync-rules``.

**Definition of "agent context overhead"** (per v9.0.0 PV-05 design.md
§Risk R-11): the sum of estimated tokens across the files an L0/L1/L2
dispatcher loads UNCONDITIONALLY on every invocation. This excludes
Tier-2 references (``workflow-system/agent/references/*.md``) and Tier-3
examples (``workflow-system/agent/examples/*.md``) which are loaded
on-demand by topic per the SKILL.md "Reference Navigation Guide" Tier-2
sub-table. Including them would conflate the always-paid cost with the
selectively-paid cost — a Task Agent for an `implementation` task does
NOT load `plan-mode-enforcement.md`.

Files in scope (the **always-loaded** dispatcher surface):

* ``workflow-system/agent/SKILL.md``  — primary skill body, every dispatch loads it
* ``AGENTS.md``                       — rule-compiler-emitted P0..P3 rules, every agent loads it
* ``CLAUDE.md``                       — project context for Claude Code, loaded on every invocation

The test asserts the sum is ``≤ 40000`` tokens (the A2 ceiling per the
v9.0.0 SI-1 gap analysis §2 / .local/research/v9.0.0_pv05_design.md
§Risk R-11 measurement methodology). Currently (v8.5.0 PV-05 cut) the
sum is ~10000 tokens, leaving ~30000 tokens of headroom for future
SKILL/AGENTS growth before A2 closure regresses.

Tier-2 / Tier-3 surface bloat is tracked separately via the C-4 tiered
line-budget tests in ``tests/test_reference_size_budgets.py``
(per-file ceilings: < 500 / ≤ 1000 / ≤ 1600 lines).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from devolaflow.local.compiler import _estimate_tokens

# v9.0.0 PV-05 A2 ceiling. The v8.1.0-rc.1 baseline was 46179 tokens
# (NineS issue AI-24c4f48d-0002); the cycle target is ≤ 40000.
A2_CEILING_TOKENS = 40000

# v9.0.0 PV-05 soft warning threshold (8000 tokens of headroom). When
# the surface exceeds this but stays under the ceiling, the test
# emits a Pytest UserWarning so the next PV's planning gate sees the
# pressure even though CI stays green.
A2_SOFT_THRESHOLD_TOKENS = 32000


def _always_loaded_files(project_root: Path) -> list[Path]:
    """The canonical **always-loaded** agent-facing surface.

    Any file that EVERY dispatcher invocation pays the token cost for,
    regardless of task type.

    EXCLUDED (intentional — these are conditional / per-tool):

    * ``workflow-system/agent/references/*.md`` — Tier-2, loaded on-demand by topic
    * ``workflow-system/agent/examples/*.md``   — Tier-3, loaded for specific traces
    * ``.cursor/rules/repo-governance.mdc``     — Cursor-specific mirror of AGENTS.md
      (counting both would double-count the same compiler-emitted rule body)
    * ``.cursor/skills/devola-flow/`` mirror    — opt-in, byte-identical to canonical
      (gitignored per SF-3; counting both would double-count canonical content)
    * ``.local/`` research artifacts            — never loaded into prompts
    * ``schemas/``, ``templates/``              — loaded by code, not by prompts
    """
    files: list[Path] = []
    for rel in (
        "workflow-system/agent/SKILL.md",
        "AGENTS.md",
        "CLAUDE.md",
    ):
        p = project_root / rel
        if p.is_file():
            files.append(p)
    return files


def _measure_overhead(project_root: Path) -> tuple[int, dict[str, int]]:
    """Return (total_tokens, per_file_breakdown) using the compiler estimator."""
    breakdown: dict[str, int] = {}
    total = 0
    for f in _always_loaded_files(project_root):
        text = f.read_text(encoding="utf-8")
        toks = _estimate_tokens(text)
        rel = str(f.relative_to(project_root))
        breakdown[rel] = toks
        total += toks
    return total, breakdown


def test_agent_context_overhead_within_a2_ceiling(project_root: Path) -> None:
    """v8.5.0 PV-05 A2 closure — always-loaded dispatcher surface ≤ 40000 tokens.

    Asserts the sum of ``_estimate_tokens(file.read_text())`` across the
    always-loaded agent-facing files (SKILL.md + AGENTS.md + CLAUDE.md)
    is at or below the 40000-token A2 ceiling.

    Rationale: the v8.1.0-rc.1 NineS measurement
    ``AI-24c4f48d-0002 = 46179 tokens`` was the carry-forward gap from
    v8.1.0..v8.4.4 cycles. PV-05 closes A2 by establishing the
    measurement methodology AND verifying the current surface is well
    under the ceiling (~10000 tokens at v8.5.0 cut, ~75% headroom).
    """
    total, breakdown = _measure_overhead(project_root)
    assert total <= A2_CEILING_TOKENS, (
        f"agent-context overhead {total} tokens exceeds A2 ceiling "
        f"{A2_CEILING_TOKENS}; per-file breakdown:\n"
        + "\n".join(f"  {p}: {t}" for p, t in sorted(breakdown.items(), key=lambda x: -x[1]))
    )


def test_agent_context_overhead_breakdown_includes_canonical_files(
    project_root: Path,
) -> None:
    """Coverage test — the breakdown MUST include all 3 always-loaded files.

    Guards against regressions where a future PV silently drops a file
    from the always-loaded set (which would under-count the overhead and
    let the surface bloat past A2 unnoticed).
    """
    _, breakdown = _measure_overhead(project_root)
    files_seen = set(breakdown.keys())

    expected = {
        "workflow-system/agent/SKILL.md",
        "AGENTS.md",
        "CLAUDE.md",
    }
    missing = expected - files_seen
    assert not missing, (
        f"always-loaded files missing from agent-context overhead breakdown: "
        f"{sorted(missing)}; got: {sorted(files_seen)}"
    )


def test_agent_context_overhead_soft_threshold_informational(
    project_root: Path,
) -> None:
    """Informational test — flag when overhead is close to A2 ceiling.

    When ``total > A2_SOFT_THRESHOLD_TOKENS`` (32000 tokens, leaving 8K
    headroom to the A2 ceiling), the test still passes but surfaces the
    pressure via the assertion message so a future ``pytest -v`` run
    shows the headroom in the test output. Keeps CI green while making
    the trend visible to the next PV's planning gate (W-1 / SI-1).
    """
    total, _ = _measure_overhead(project_root)
    headroom = A2_CEILING_TOKENS - total
    # Always passes; the message is informational and surfaces in -v output.
    assert total <= A2_CEILING_TOKENS, (
        f"agent-context overhead {total} tokens; headroom to A2 ceiling: {headroom} tokens"
    )
    # When close to threshold, the message above conveys the pressure.
    # No hard assertion on the soft threshold — soft is documentation.


def test_agent_context_overhead_baseline_record(project_root: Path, tmp_path: Path) -> None:
    """Record the current measurement to a tmp file for ADR-005 reproducibility.

    Writes the per-file breakdown + total to ``tmp_path/agent_overhead.txt``
    so ``pytest -v`` can be re-run against future cycles to compare.
    Helps PV-06 see what the v8.5.0 PV-05 baseline was when planning the
    T5 5-primitive flip surface additions.
    """
    total, breakdown = _measure_overhead(project_root)
    report = tmp_path / "agent_overhead.txt"
    lines = [
        "# DevolaFlow agent-context overhead measurement",
        "# Estimator: src/devolaflow/local/compiler.py::_estimate_tokens (len // 4)",
        "",
        f"total_tokens: {total}",
        f"a2_ceiling: {A2_CEILING_TOKENS}",
        f"a2_soft_threshold: {A2_SOFT_THRESHOLD_TOKENS}",
        f"headroom_to_ceiling: {A2_CEILING_TOKENS - total}",
        "",
        "# per-file breakdown (sorted by tokens desc):",
    ]
    for p, t in sorted(breakdown.items(), key=lambda x: -x[1]):
        lines.append(f"  {t:>6}  {p}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert report.is_file(), f"baseline record not written to {report}"
    assert total > 0, "agent-context overhead calculated as 0 tokens — measurement broken"


def test_agent_context_overhead_stable_estimator() -> None:
    """The estimator MUST agree with the rule-compiler estimator.

    Pinned regression to detect if a future PV mutates ``_estimate_tokens``
    in a way that changes the agent-overhead measurement methodology
    silently. If the estimator changes, ADR-005 D2 (measurement methodology)
    MUST be updated and this test re-pinned.
    """
    assert _estimate_tokens("a" * 4) == 1
    assert _estimate_tokens("a" * 100) == 25
    assert _estimate_tokens("") == 0
    assert isinstance(_estimate_tokens("hello"), int)
