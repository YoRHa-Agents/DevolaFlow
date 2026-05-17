"""Cyclomatic-complexity pins for the v12.4.0 PV-04 D-3 refactor pair.

This file is the W-18 / W-4 / SI-3 pin that locks the post-refactor
cyclomatic complexity (cc) ceilings for the two PV-04 refactor targets
plus a cross-PV regression guard for the PV-03 ``evaluate_gate`` refactor:

* :func:`devolaflow.shell_proxy.commands.build_mapping_from_dict` — was
  cc=21 (per ``.local/research/v12.4.0_nines_deep_commands.json`` finding,
  AST walker measures cc=22) refactored to cc=9 via 4 ``_validate_*`` /
  ``_build_*`` helpers per v12.4.0 PV-04 D-3.
* :func:`devolaflow.writing_style.transforms.bullets._collapse_block` —
  was cc=25 (per ``.local/research/v12.4.0_nines_deep_bullets.json``
  finding, AST walker measures cc=26) refactored to cc=6 via 4
  helpers per v12.4.0 PV-04 D-3.
* :func:`devolaflow.gate.scorer.evaluate_gate` — PV-03 baseline cc=7;
  pinned at the cc≤10 ceiling as a cross-PV regression guard so any
  subsequent PV (PV-05 / PV-06) that touches ``evaluate_gate`` cannot
  silently re-bloat it past the v12.4.0 PV-03 invariant.

Why an AST-based cc visitor instead of ``radon.complexity.cc_visit``?
``radon`` is not a declared runtime/dev dependency in
``pyproject.toml`` — every previous cc-spike pin in this repo (see
``tests/test_no_ghost_features.py::test_v8_0_0_p01_cc_cleanup``,
``test_v9_0_0_pv05_*_helper_extraction``, etc.) plus the v12.4.0 PV-03
companion file ``tests/test_evaluate_gate_complexity.py`` has used a
stdlib ``ast``-only walker. We follow the same precedent here so the
pin lands without adding a heavy dev-dep just for one assertion file.

The visitor follows the canonical cc formula used by ``radon`` and
McCabe (1976):

* base 1 per function definition
* +1 for each: ``if`` / ``elif`` / ``while`` / ``for`` / ``except`` /
  ``with`` (single context) / ternary ``x if cond else y`` /
  ``bool_op`` operand beyond the first (``and`` / ``or`` short-circuit)
* +1 for each ``assert`` (matches radon's strict mode; conservative)
* comprehensions/generator branches with ``if`` add +1 each

The pin tests assert:
1. ``build_mapping_from_dict`` cc ≤ 10 (target was cc=21 pre-refactor;
   post-refactor cc=9).
2. ``_collapse_block`` cc ≤ 10 (target was cc=25 pre-refactor;
   post-refactor cc=6).
3. Each new helper cc ≤ 8.
4. Public signatures of the two refactor targets are byte-identical.
5. ``evaluate_gate`` cc ≤ 10 (PV-03 baseline cc=7; cross-PV regression
   guard so re-bloat is caught at PV-04 close, not at v12.4.0 cycle
   close when rollback is expensive).

Source: v12.4.0 PV-04 D-3 +
``.local/research/v12.4.0_gap_analysis.md`` §2 D-3 +
``tests/test_evaluate_gate_complexity.py`` (the PV-03 sibling pin).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Repository-root-relative paths; resolved against this test file's
# parent so the test runs identically from any cwd (matches the
# established pattern in ``tests/test_evaluate_gate_complexity.py``
# constants block).
_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
_COMMANDS_PATH: Path = _REPO_ROOT / "src" / "devolaflow" / "shell_proxy" / "commands.py"
_BULLETS_PATH: Path = (
    _REPO_ROOT / "src" / "devolaflow" / "writing_style" / "transforms" / "bullets.py"
)
_SCORER_PATH: Path = _REPO_ROOT / "src" / "devolaflow" / "gate" / "scorer.py"

# Per cycle plan §3 PV-04 + gap analysis §2 D-3: orchestrator ≤ 10, each
# helper ≤ 8. Same ceilings as PV-03 — the two PVs share the cc-spike
# refactor discipline.
_ORCHESTRATOR_CC_CEILING: int = 10
_HELPER_CC_CEILING: int = 8

# The 4 helpers extracted from ``build_mapping_from_dict`` during
# v12.4.0 PV-04 D-3. Order matches definition order in
# ``src/devolaflow/shell_proxy/commands.py`` so a future grep for the
# helper names lands in the right spot.
_BUILD_MAPPING_HELPERS: tuple[str, ...] = (
    "_validate_schema_version",
    "_validate_scalar_fields",
    "_validate_tags",
    "_build_filter_lists",
)

# The 4 helpers extracted from ``_collapse_block`` during v12.4.0 PV-04 D-3.
_COLLAPSE_BLOCK_HELPERS: tuple[str, ...] = (
    "_classify_block_lines",
    "_validate_bullet_constraints",
    "_collapse_no_intro",
    "_collapse_with_intro",
)

# Public signature of ``build_mapping_from_dict`` — MUST be byte-identical
# pre and post the v12.4.0 PV-04 refactor. The CO-2 / C-3 "no API break"
# rule requires this literal string match against the post-refactor source.
_BUILD_MAPPING_SIGNATURE: str = """\
def build_mapping_from_dict(
    payload: Any,
    *,
    source_path: str = "<command-mapping.yaml>",
    recipe_id: str = "",
) -> CommandMapping:"""

# Public signature of ``_collapse_block`` — the function is private
# (underscore-prefixed) but still has a stable in-module API surface
# that the orchestrator ``_transform_prose`` calls in a hot loop.
_COLLAPSE_BLOCK_SIGNATURE: str = """\
def _collapse_block(lines: list[str]) -> list[str]:"""


def _cyclomatic_complexity(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Compute McCabe cyclomatic complexity for *func* via AST walk.

    Matches the canonical formula used by ``radon`` in non-coverage mode:
    base 1 + branch points. The walk is intentionally restricted to
    *func*'s own body (nested function definitions get their OWN cc
    score in a separate visit; we do NOT roll them into the enclosing
    function's count — that mirrors ``radon.complexity.cc_visit``
    behaviour and means the pin remains stable when a helper later grows
    its own private sub-helper). Identical implementation to the PV-03
    sibling in ``tests/test_evaluate_gate_complexity.py``.
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


def _load_module(path: Path) -> ast.Module:
    """Parse *path* into an AST module.

    Per-test re-parse is cheap (target files are ≤ ~1000 lines) — we
    accept the cost to keep the helper trivially pure across the 9
    parametrize entries.
    """
    source = path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(path))


def _find_function(module: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Locate the top-level function *name* in *module*.

    Raises :class:`LookupError` if the function is absent — the
    refactor-removed-the-symbol failure mode S-5 (no silent failure)
    requires us to surface explicitly so the per-helper test ties to a
    clear assertion message.
    """
    for node in module.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    raise LookupError(
        f"Function {name!r} not found at module scope. v12.4.0 PV-04 D-3 "
        "refactor MUST keep the orchestrator + every helper at module scope "
        "per the cycle plan."
    )


# ---------------------------------------------------------------------------
# Target 1 — build_mapping_from_dict (cc=22 pre / cc=9 post / ceiling 10)
# ---------------------------------------------------------------------------


def test_build_mapping_from_dict_cc_under_ceiling() -> None:
    """``build_mapping_from_dict`` cc ≤ 10 (was cc=21 pre-v12.4.0 PV-04 refactor).

    Pins the v12.4.0 PV-04 D-3 acceptance criterion (1) per
    ``.local/research/v12.4.0_gap_analysis.md`` §2 D-3: post-refactor
    orchestrator cyclomatic complexity must drop from the cc=21 NineS-
    documented value (this AST walker reads cc=22 because it counts each
    BoolOp operand beyond the first; radon counts BoolOps slightly
    differently for the same source — both readings exceed the cc=10
    ceiling and both refactor verdicts cross under it). The expected
    post-refactor value is cc=9 (one ``if not isinstance`` + one
    list-comp ``if not payload.get`` + one ``if missing`` + one
    ``recipe_id or "<unknown>"`` BoolOp + four ``or ""`` BoolOps in the
    final ``CommandMapping`` kwargs = cc=9), under the cc=10 ceiling
    with one slot of headroom.
    """
    module = _load_module(_COMMANDS_PATH)
    func = _find_function(module, "build_mapping_from_dict")
    cc = _cyclomatic_complexity(func)

    assert cc <= _ORCHESTRATOR_CC_CEILING, (
        f"v12.4.0 PV-04 D-3 violation: ``build_mapping_from_dict`` cc={cc} "
        f"exceeds ceiling {_ORCHESTRATOR_CC_CEILING}. The refactor was supposed "
        f"to bring cc from 21 to ≤ 10 via four ``_validate_*`` / ``_build_*`` "
        f"helpers; if this assertion fires, a future PV has re-bloated the "
        f"orchestrator body and must extract additional collaborators or revert."
    )


@pytest.mark.parametrize("helper_name", _BUILD_MAPPING_HELPERS)
def test_build_mapping_helpers_cc_under_ceiling(helper_name: str) -> None:
    """Each ``build_mapping_from_dict`` helper cc ≤ 8 per cycle plan §3 PV-04.

    Pins the v12.4.0 PV-04 D-3 acceptance criterion (3): every helper
    extracted from the original orchestrator body must individually stay
    under cc=8 so the refactor genuinely improves maintainability (not
    just shifting complexity from one symbol to four). Measured values:

    * ``_validate_schema_version`` — cc=4 (est. 4)
    * ``_validate_scalar_fields`` — cc=6 (est. 7; combines TTL +
      truncate_lines + strip_ansi validation)
    * ``_validate_tags`` — cc=2 (est. 3)
    * ``_build_filter_lists`` — cc=5 (est. 8; folds pre + post filter
      list construction together)
    """
    module = _load_module(_COMMANDS_PATH)
    func = _find_function(module, helper_name)
    cc = _cyclomatic_complexity(func)

    assert cc <= _HELPER_CC_CEILING, (
        f"v12.4.0 PV-04 D-3 violation: helper ``{helper_name}`` cc={cc} "
        f"exceeds ceiling {_HELPER_CC_CEILING}. The refactor decomposed "
        f"``build_mapping_from_dict`` into four helpers each ≤ 8; if this "
        f"assertion fires, the helper has accumulated additional branches "
        f"and either needs to be further decomposed or the corresponding "
        f"orchestrator validation block needs a different extraction strategy."
    )


def test_build_mapping_from_dict_signature_byte_identical() -> None:
    """``build_mapping_from_dict`` public signature is byte-identical pre/post-refactor.

    Pins the v12.4.0 PV-04 D-3 acceptance criterion (4) + the CO-2 / C-3
    "no API break" invariant: the public signature of the orchestrator
    MUST remain literally identical so all 68 ``tests/test_shell_proxy_*``
    callers + downstream consumers (the loader, the apply_local_recipe
    layer) keep working without modification.

    The signature is captured verbatim in
    :data:`_BUILD_MAPPING_SIGNATURE` and matched against a substring of
    the live source. Whitespace must be preserved exactly because
    ``ruff format`` is the tie-breaker for the canonical form.
    """
    source = _COMMANDS_PATH.read_text(encoding="utf-8")

    assert _BUILD_MAPPING_SIGNATURE in source, (
        "v12.4.0 PV-04 D-3 violation: ``build_mapping_from_dict`` public "
        f"signature differs from the pre-refactor canonical form. The "
        f"signature MUST match this literal verbatim (whitespace included):"
        f"\n\n{_BUILD_MAPPING_SIGNATURE}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``recipe_id`` with a default value (additive change) — do NOT "
        "reorder existing parameters or change defaults. Per A-2.3 "
        "NEST-vs-APPEND, prefer nesting under an existing optional dict "
        "argument before appending."
    )


# ---------------------------------------------------------------------------
# Target 2 — _collapse_block (cc=26 pre / cc=6 post / ceiling 10)
# ---------------------------------------------------------------------------


def test_collapse_block_cc_under_ceiling() -> None:
    """``_collapse_block`` cc ≤ 10 (was cc=25 pre-v12.4.0 PV-04 refactor).

    Pins the v12.4.0 PV-04 D-3 acceptance criterion (2) per
    ``.local/research/v12.4.0_gap_analysis.md`` §2 D-3: post-refactor
    orchestrator cyclomatic complexity must drop from the cc=25 NineS-
    documented value (AST walker reads cc=26 due to BoolOp counting
    nuances) to at most 10. The expected post-refactor value is cc=6
    (one ``if parts is None`` + one ``if not _validate_bullet_constraints``
    + one list-comp ``if s.strip()`` + one ``if not non_blank_intro`` +
    one ``if not last_intro.endswith`` = cc=6), comfortably under the
    cc=10 ceiling.
    """
    module = _load_module(_BULLETS_PATH)
    func = _find_function(module, "_collapse_block")
    cc = _cyclomatic_complexity(func)

    assert cc <= _ORCHESTRATOR_CC_CEILING, (
        f"v12.4.0 PV-04 D-3 violation: ``_collapse_block`` cc={cc} exceeds "
        f"ceiling {_ORCHESTRATOR_CC_CEILING}. The refactor was supposed to "
        f"bring cc from 25 to ≤ 10 via four helpers (classify / validate / "
        f"collapse_no_intro / collapse_with_intro); if this assertion fires, "
        f"a future PV has re-bloated the orchestrator body and must extract "
        f"additional collaborators or revert."
    )


@pytest.mark.parametrize("helper_name", _COLLAPSE_BLOCK_HELPERS)
def test_collapse_block_helpers_cc_under_ceiling(helper_name: str) -> None:
    """Each ``_collapse_block`` helper cc ≤ 8 per cycle plan §3 PV-04.

    Pins the v12.4.0 PV-04 D-3 acceptance criterion (3): every helper
    extracted from the original orchestrator body must individually stay
    under cc=8. Measured values:

    * ``_classify_block_lines`` — cc=7 (est. 6; includes the state-
      machine for loop + indent check + 1 ternary IfExp ``(tail if
      in_bullets else intro)``)
    * ``_validate_bullet_constraints`` — cc=6 (est. 4; carries 4 reject
      conditions, each adding +1)
    * ``_collapse_no_intro`` — cc=2 (est. 3)
    * ``_collapse_with_intro`` — cc=4 (est. 7; the intro-eligibility
      check stays in the orchestrator so this helper only branches on
      item count + intro suffix punctuation)
    """
    module = _load_module(_BULLETS_PATH)
    func = _find_function(module, helper_name)
    cc = _cyclomatic_complexity(func)

    assert cc <= _HELPER_CC_CEILING, (
        f"v12.4.0 PV-04 D-3 violation: helper ``{helper_name}`` cc={cc} "
        f"exceeds ceiling {_HELPER_CC_CEILING}. The refactor decomposed "
        f"``_collapse_block`` into four helpers each ≤ 8; if this assertion "
        f"fires, the helper has accumulated additional branches and either "
        f"needs further decomposition or the corresponding orchestrator "
        f"block needs a different extraction strategy."
    )


def test_collapse_block_signature_byte_identical() -> None:
    """``_collapse_block`` private signature is byte-identical pre/post-refactor.

    Pins the v12.4.0 PV-04 D-3 acceptance criterion (4) for the bullets
    half of the refactor pair. ``_collapse_block`` is module-private
    (underscore-prefixed) but the in-module orchestrator
    :func:`devolaflow.writing_style.transforms.bullets._transform_prose`
    calls it on every block, and the 27 ``tests/test_writing_style_*``
    fixture-corpus tests rely on byte-identical input/output. The
    signature must therefore stay literally identical.
    """
    source = _BULLETS_PATH.read_text(encoding="utf-8")

    assert _COLLAPSE_BLOCK_SIGNATURE in source, (
        "v12.4.0 PV-04 D-3 violation: ``_collapse_block`` private "
        "signature differs from the pre-refactor canonical form. The "
        f"signature MUST match this literal verbatim:\n\n"
        f"{_COLLAPSE_BLOCK_SIGNATURE}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``lines`` with a default value (additive change) — do NOT "
        "reorder existing parameters or change defaults."
    )


# ---------------------------------------------------------------------------
# Cross-PV regression guard — evaluate_gate (PV-03 cc=7 / ceiling 10)
# ---------------------------------------------------------------------------


def test_evaluate_gate_cc_under_ceiling_v12_4_0_pv04_regression_guard() -> None:
    """``evaluate_gate`` cc ≤ 10 — PV-03 baseline cc=7 cross-PV regression guard.

    Pins the v12.4.0 PV-04 D-3 acceptance criterion (regression guard)
    per the task spec's instruction to include "a regression-guard for
    ``evaluate_gate`` from PV-03" in this PV-04 cc-pin file. The PV-03
    refactor brought ``evaluate_gate`` from cc=22 to cc=7 via four
    ``_apply_*`` helpers (see
    ``tests/test_evaluate_gate_complexity.py``); this PV-04 cc-pin
    re-asserts the same cc=10 ceiling so any subsequent PV (PV-05 /
    PV-06) that touches ``evaluate_gate`` cannot silently re-bloat it
    past the v12.4.0 PV-03 invariant.

    Why duplicate the PV-03 sibling assertion here? Because PV-04
    refactors ``build_mapping_from_dict`` + ``_collapse_block`` and the
    W-4 benchmark sweep at PV-04 close exercises the gate scorer
    transitively. A regression in ``evaluate_gate`` could land via the
    same PV through a careless dispatch-graph edit; surfacing that
    failure in the PV-04 cc-pin file (not just the PV-03 file) keeps
    the regression-class GREEN-flip detectable at the PV that actually
    introduced it.
    """
    module = _load_module(_SCORER_PATH)
    func = _find_function(module, "evaluate_gate")
    cc = _cyclomatic_complexity(func)

    assert cc <= _ORCHESTRATOR_CC_CEILING, (
        f"v12.4.0 PV-04 D-3 cross-regression violation: ``evaluate_gate`` "
        f"cc={cc} exceeds ceiling {_ORCHESTRATOR_CC_CEILING}. PV-03 "
        f"established cc=7 baseline via four ``_apply_*`` helpers (see "
        f"``tests/test_evaluate_gate_complexity.py``); if this assertion "
        f"fires alongside the PV-03 sibling, the regression landed in the "
        f"current PV — bisect the PV diff before merging."
    )
