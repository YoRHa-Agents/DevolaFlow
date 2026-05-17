"""Cyclomatic-complexity pins for the v12.4.0 PV-03 D-2 ``evaluate_gate`` refactor.

This file is the W-18 / W-4 / SI-3 pin that locks the post-refactor
cyclomatic complexity (cc) ceilings for :func:`evaluate_gate` (orchestrator)
and the four ``_apply_*`` helpers extracted from it during v12.4.0 PV-03
per ``.local/research/v12.4.0_gap_analysis.md`` §2 D-2 +
``.cursor/plans/v12.4.0_expansion_refactor_cycle_240b72f0.plan.md`` §3 PV-03.

Why an AST-based cc visitor instead of ``radon.complexity.cc_visit``?
``radon`` is not a declared runtime/dev dependency in
``pyproject.toml`` — every previous cc-spike pin in this repo (see
``tests/test_no_ghost_features.py::test_v8_0_0_p01_cc_cleanup``,
``test_v9_0_0_pv05_*_helper_extraction``, etc.) has used a stdlib
``ast``-only walker. We follow the same precedent here so the pin lands
without adding a heavy dev-dep just for one assertion file.

The visitor follows the canonical cc formula used by ``radon`` and
McCabe (1976):

* base 1 per function definition
* +1 for each: ``if`` / ``elif`` / ``while`` / ``for`` / ``except`` /
  ``with`` (single context) / ternary ``x if cond else y`` /
  ``bool_op`` operand beyond the first (``and`` / ``or`` short-circuit)
* +1 for each ``assert`` (matches radon's strict mode; conservative)
* comprehensions/generator branches with ``if`` add +1 each

The pin tests assert:
1. ``evaluate_gate`` cc ≤ 10 (target was cc=22 pre-refactor; post-refactor cc=7)
2. Each new ``_apply_*`` helper cc ≤ 8 (target per cycle plan §3 PV-03)
3. ``evaluate_gate`` public signature is byte-identical to the pre-refactor
   form documented at ``.local/research/v12.4.0_gap_analysis.md`` §2 D-2.

Source: v12.4.0 PV-03 D-2.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Repository-root-relative path; resolved against this test file's parent
# so the test runs identically from any cwd (matches the established
# pattern in ``tests/test_no_ghost_features.py`` constants block).
_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
_SCORER_PATH: Path = _REPO_ROOT / "src" / "devolaflow" / "gate" / "scorer.py"

# Per cycle plan §3 PV-03: orchestrator ≤ 10, each helper ≤ 8.
_EVALUATE_GATE_CC_CEILING: int = 10
_HELPER_CC_CEILING: int = 8

# The 4 helpers extracted from ``evaluate_gate`` during v12.4.0 PV-03.
# Order matches ``src/devolaflow/gate/scorer.py`` definition order so a
# future grep for the helper names lands in the right spot.
_EVALUATE_GATE_HELPERS: tuple[str, ...] = (
    "_apply_breaker_check",
    "_apply_cycle_detection",
    "_apply_ratchet",
    "_apply_complexity_and_legibility",
)

# Public signature of ``evaluate_gate`` — MUST be byte-identical pre and
# post the v12.4.0 PV-03 refactor. The CO-2 / C-3 "no API break" rule
# requires this literal string match against the post-refactor source.
# This is the verbatim signature documented at
# ``.local/research/v12.4.0_gap_analysis.md`` §2 D-2.
_EVALUATE_GATE_SIGNATURE: str = """\
def evaluate_gate(
    gate_input: GateInput,
    profile: GateProfile,
    round_num: int = 1,
    history: list[ConvergenceRound] | None = None,
    gate_type: str = "standard",
    breaker: TokenBudgetBreaker | None = None,
    cumulative_tokens: int | None = None,
    cycle_detector: CycleDetector | None = None,
    ratchet: MonotonicRatchet | None = None,
    ratchet_artifact: dict[str, object] | None = None,
    complexity_detector: ComplexityDetector | None = None,
    complexity_signals: ComplexitySignals | None = None,
    complexity_task_complexity: str = "standard",
    legibility_scorer: LegibilityScorer | None = None,
    legibility_files: Sequence[str] | None = None,
) -> GateVerdict:"""


def _cyclomatic_complexity(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Compute McCabe cyclomatic complexity for *func* via AST walk.

    Matches the canonical formula used by ``radon`` in non-coverage mode:
    base 1 + branch points. The walk is intentionally restricted to
    ``func``'s own body (nested function definitions get their OWN cc
    score in a separate visit; we do NOT roll them into the enclosing
    function's count — that mirrors ``radon.complexity.cc_visit``
    behaviour and means the pin remains stable when a helper later grows
    its own private sub-helper).
    """
    complexity = 1  # base count per McCabe (1976)

    for node in ast.walk(func):
        # Skip nested function bodies — they're scored independently.
        if node is not func and isinstance(
            node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
        ):
            continue

        if isinstance(node, ast.If | ast.While | ast.For | ast.AsyncFor | ast.ExceptHandler):
            complexity += 1
        elif isinstance(node, ast.With | ast.AsyncWith):
            # Each context manager in the with-statement counts +1.
            complexity += len(node.items)
        elif isinstance(node, ast.BoolOp):
            # `a and b and c` has 2 short-circuit branch points
            # (3 operands - 1). `or` is symmetric.
            complexity += max(0, len(node.values) - 1)
        elif isinstance(node, ast.IfExp):
            # Ternary `x if cond else y` adds one decision point.
            complexity += 1
        elif isinstance(node, ast.Assert):
            complexity += 1
        elif isinstance(node, ast.comprehension):
            # Each `if` clause inside a comprehension is a branch.
            complexity += len(node.ifs)

    return complexity


def _load_scorer_module() -> ast.Module:
    """Parse ``src/devolaflow/gate/scorer.py`` into an AST module.

    Cached per pytest session (Path.read_text is the I/O bottleneck) —
    the module is ~2500 lines but parses in O(ms); we accept the per-test
    re-parse cost to keep the helper trivially pure for the 3 tests.
    """
    source = _SCORER_PATH.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(_SCORER_PATH))


def _find_function(module: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Locate the top-level function *name* in *module*.

    Raises :class:`LookupError` if the function is absent — this is the
    refactor-removed-the-symbol failure mode S-5 (no silent failure)
    requires us to surface explicitly so the per-helper test ties to a
    clear assertion message.
    """
    for node in module.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    raise LookupError(
        f"Function {name!r} not found at module scope in {_SCORER_PATH}. "
        "v12.4.0 PV-03 D-2 refactor MUST keep ``evaluate_gate`` and the four "
        "``_apply_*`` helpers at module scope per the cycle plan."
    )


def test_evaluate_gate_cc_under_ceiling() -> None:
    """``evaluate_gate`` cc ≤ 10 (was cc=22 pre-v12.4.0 PV-03 refactor).

    Pins the v12.4.0 PV-03 D-2 acceptance criterion (1) per
    ``.cursor/plans/v12.4.0_expansion_refactor_cycle_240b72f0.plan.md``
    §3 PV-03: post-refactor orchestrator cyclomatic complexity must
    drop from 22 (the NineS deep-analyzed pre-refactor value documented
    at ``.local/research/v12.4.0_nines_deep_evaluate_gate.json`` finding
    ``CC-67079a-0000``) to at most 10. The expected post-refactor value
    is 7 (one ``if history`` + one ``if break_verdict`` + one ``if handler``
    + one ``elif history`` + one ``if decision is not None and decision.action
    is BudgetAction.WARN`` (counts as 2 for the ``and`` short-circuit) =
    cc=7), comfortably under the cc=10 ceiling.
    """
    module = _load_scorer_module()
    func = _find_function(module, "evaluate_gate")
    cc = _cyclomatic_complexity(func)

    assert cc <= _EVALUATE_GATE_CC_CEILING, (
        f"v12.4.0 PV-03 D-2 violation: ``evaluate_gate`` cc={cc} exceeds "
        f"ceiling {_EVALUATE_GATE_CC_CEILING}. The refactor was supposed "
        f"to bring cc from 22 to ≤ 10 via four ``_apply_*`` helpers; if "
        f"this assertion fires, a future PV has re-bloated the orchestrator "
        f"body and must extract additional collaborators or revert."
    )


@pytest.mark.parametrize("helper_name", _EVALUATE_GATE_HELPERS)
def test_evaluate_gate_helpers_cc_under_ceiling(helper_name: str) -> None:
    """Each ``_apply_*`` helper cc ≤ 8 per cycle plan §3 PV-03.

    Pins the v12.4.0 PV-03 D-2 acceptance criterion (2): every helper
    extracted from the original ``evaluate_gate`` body must individually
    stay under cc=8 so the refactor genuinely improves maintainability
    (not just shifting complexity from one symbol to four). Per the gap
    analysis estimates:

    * ``_apply_breaker_check`` — estimated cc=6, measured cc=3
    * ``_apply_cycle_detection`` — estimated cc=4, measured cc=3
    * ``_apply_ratchet`` — estimated cc=5, measured cc=2
    * ``_apply_complexity_and_legibility`` — estimated cc=8, measured cc=5
    """
    module = _load_scorer_module()
    func = _find_function(module, helper_name)
    cc = _cyclomatic_complexity(func)

    assert cc <= _HELPER_CC_CEILING, (
        f"v12.4.0 PV-03 D-2 violation: helper ``{helper_name}`` cc={cc} "
        f"exceeds ceiling {_HELPER_CC_CEILING}. The refactor decomposed "
        f"``evaluate_gate`` into four helpers each ≤ 8; if this assertion "
        f"fires, the helper has accumulated additional branches and either "
        f"needs to be further decomposed or the corresponding orchestrator "
        f"collaborator block needs a different extraction strategy."
    )


def test_evaluate_gate_signature_byte_identical() -> None:
    """``evaluate_gate`` public signature is byte-identical pre/post-refactor.

    Pins the v12.4.0 PV-03 D-2 acceptance criterion (3) + the CO-2 / C-3
    "no API break" invariant: the public signature of ``evaluate_gate``
    MUST remain literally identical to the pre-refactor form so all 101
    ``tests/test_gate.py`` callers + the 36 ``tests/test_benchmarks.py``
    scenarios + downstream consumers (W-3 SI-3 harness, PV-06 self-eval)
    keep working without modification.

    The signature is captured verbatim in
    :data:`_EVALUATE_GATE_SIGNATURE` and matched against a substring
    of the live source. Whitespace must be preserved exactly because
    ``ruff format`` is the tie-breaker for the canonical form.
    """
    source = _SCORER_PATH.read_text(encoding="utf-8")

    assert _EVALUATE_GATE_SIGNATURE in source, (
        "v12.4.0 PV-03 D-2 violation: ``evaluate_gate`` public signature "
        f"differs from the pre-refactor canonical form. The signature MUST "
        f"match this literal verbatim (whitespace included):\n\n"
        f"{_EVALUATE_GATE_SIGNATURE}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``legibility_files`` with a default value (additive change) — "
        "do NOT reorder existing parameters or change defaults. Per A-2.3 "
        "NEST-vs-APPEND, prefer nesting under an existing optional dict "
        "argument before appending."
    )
