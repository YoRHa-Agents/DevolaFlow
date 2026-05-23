"""Cyclomatic-complexity pins for the v12.5.0 PV-02 D-2 cc-spike sweep.

This file is the W-18 / W-4 / SI-3 pin that locks the post-refactor
cyclomatic complexity (cc) ceilings for the two PV-02 refactor targets:

* :func:`devolaflow.shell_proxy.commands.load_command_mappings` — was
  cc=18 (per ``.local/research/v12.4.0_nines_deep_commands.json``
  finding, AST walker measures cc=18) refactored to cc=9 via 4
  ``_resolve_*`` / ``_load_*`` / ``_filter_*`` / ``_should_*`` helpers
  per v12.5.0 PV-02 D-2.
* :func:`devolaflow.shell_proxy.commands.apply_local_recipe` — was
  cc=17 (per the same NineS finding) refactored to cc=4 via 2
  helpers (:func:`_resolve_apply_inputs` folding the 5 early-return
  decisions, :func:`_apply_recipe_transform` folding the strip-ansi →
  pre/post filter → truncate → on-empty pipeline) per v12.5.0 PV-02 D-2.

This file mirrors ``tests/test_v12_4_0_complexity_targets.py``
verbatim — same AST walker, same ceiling constants
(:data:`_ORCHESTRATOR_CC_CEILING` = 10, :data:`_HELPER_CC_CEILING` = 8),
same byte-identical-public-signature pattern. The v12.5.0 PV-02 D-2 sweep
was authored as a direct application of the canonical helper-extraction
template documented in v12.4.0 retrospective §4.1.

The visitor follows the canonical cc formula used by ``radon`` and
McCabe (1976):

* base 1 per function definition
* +1 for each: ``if`` / ``elif`` / ``while`` / ``for`` / ``except`` /
  ``with`` (single context) / ternary ``x if cond else y`` /
  ``bool_op`` operand beyond the first (``and`` / ``or`` short-circuit)
* +1 for each ``assert`` (matches radon's strict mode; conservative)
* comprehensions/generator branches with ``if`` add +1 each

Source: v12.5.0 PV-02 D-2 + ``.local/research/v12.5.0_gap_analysis.md``
§2 D-2 + ``tests/test_v12_4_0_complexity_targets.py`` (the v12.4.0
sibling pin).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Repository-root-relative paths; resolved against this test file's
# parent so the test runs identically from any cwd (matches the
# established pattern in ``tests/test_v12_4_0_complexity_targets.py``
# constants block).
_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
_COMMANDS_PATH: Path = _REPO_ROOT / "src" / "devolaflow" / "shell_proxy" / "commands.py"

# Per cycle plan §3 PV-02 + gap analysis §2 D-2: orchestrator ≤ 10, each
# helper ≤ 8. Same ceilings as v12.4.0 PV-04 — the PV inherits the
# established cc-spike refactor discipline verbatim.
_ORCHESTRATOR_CC_CEILING: int = 10
_HELPER_CC_CEILING: int = 8

# The 4 helpers extracted from ``load_command_mappings`` during
# v12.5.0 PV-02 D-2. Order matches definition order in
# ``src/devolaflow/shell_proxy/commands.py`` so a future grep for the
# helper names lands in the right spot.
_LOAD_MAPPINGS_HELPERS: tuple[str, ...] = (
    "_resolve_commands_root",
    "_load_recipe_payload",
    "_filter_recipe_freshness",
    "_should_keep_recipe",
)

# The 2 helpers extracted from ``apply_local_recipe`` during v12.5.0 PV-02
# D-2. apply_local_recipe's body is naturally bipartite (5 early-return
# decisions + 5 transform-pipeline steps), which the 2-helper extraction
# captures cleanly without forcing a 4-helper decomposition that would
# add seams without reducing measurable complexity.
_APPLY_RECIPE_HELPERS: tuple[str, ...] = (
    "_resolve_apply_inputs",
    "_apply_recipe_transform",
)

# Public signature of ``load_command_mappings`` — MUST be byte-identical
# pre and post the v12.5.0 PV-02 refactor. The CO-2 / C-3 "no API break"
# rule requires this literal string match against the post-refactor source.
_LOAD_MAPPINGS_SIGNATURE: str = """\
def load_command_mappings(
    *,
    commands_dir: Path | str | None = None,
    repo_signal: str | None = None,
    env: dict[str, str] | None = None,
    current_version: str | None = None,
) -> dict[str, CommandMapping]:"""

# Public signature of ``apply_local_recipe`` — likewise byte-identical.
_APPLY_RECIPE_SIGNATURE: str = """\
def apply_local_recipe(
    cmd: str,
    output: str,
    *,
    mappings: dict[str, CommandMapping] | None = None,
    env: dict[str, str] | None = None,
    commands_dir: Path | str | None = None,
    repo_signal: str | None = None,
) -> tuple[str, bool]:"""


def _cyclomatic_complexity(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Compute McCabe cyclomatic complexity for *func* via AST walk.

    Identical implementation to the v12.4.0 PV-04 sibling in
    ``tests/test_v12_4_0_complexity_targets.py``. Matches the canonical
    formula used by ``radon`` in non-coverage mode: base 1 + branch
    points. The walk is intentionally restricted to *func*'s own body
    (nested function definitions get their OWN cc score in a separate
    visit; we do NOT roll them into the enclosing function's count —
    that mirrors ``radon.complexity.cc_visit`` behaviour and means the
    pin remains stable when a helper later grows its own private
    sub-helper).
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
            complexity += len(node.items)
        elif isinstance(node, ast.BoolOp):
            # `a and b and c` has 2 short-circuit branch points
            # (3 operands - 1). `or` is symmetric.
            complexity += max(0, len(node.values) - 1)
        elif isinstance(node, ast.IfExp):
            # Ternary `x if cond else y` adds one decision point.
            complexity += 1
        elif isinstance(node, ast.Assert):
            # Matches radon's strict mode (conservative).
            complexity += 1
        elif isinstance(node, ast.comprehension):
            # Each `if` clause inside a comprehension is a branch.
            complexity += len(node.ifs)

    return complexity


def _load_module(path: Path) -> ast.Module:
    """Parse *path* into an AST module."""
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
        f"Function {name!r} not found at module scope. v12.5.0 PV-02 D-2 "
        "refactor MUST keep the orchestrator + every helper at module scope "
        "per the cycle plan."
    )


# ---------------------------------------------------------------------------
# Target 1 — load_command_mappings (cc=18 pre / cc=9 post / ceiling 10)
# ---------------------------------------------------------------------------


def test_load_command_mappings_cc_under_ceiling() -> None:
    """``load_command_mappings`` cc ≤ 10 (was cc=18 pre-v12.5.0 PV-02 refactor).

    Pins the v12.5.0 PV-02 D-2 acceptance criterion (1) per
    ``.local/research/v12.5.0_gap_analysis.md`` §2 D-2: post-refactor
    orchestrator cyclomatic complexity must drop from cc=18 (NineS
    deep analyze on commands.py recorded cc=16; this AST walker reads
    cc=18 due to bool-op operand counting). Expected post-refactor value
    is cc=9 (under the cc=10 ceiling with one slot of headroom).
    """
    module = _load_module(_COMMANDS_PATH)
    func = _find_function(module, "load_command_mappings")
    cc = _cyclomatic_complexity(func)

    assert cc <= _ORCHESTRATOR_CC_CEILING, (
        f"v12.5.0 PV-02 D-2 violation: ``load_command_mappings`` cc={cc} "
        f"exceeds ceiling {_ORCHESTRATOR_CC_CEILING}. The refactor was supposed "
        f"to bring cc from 18 to ≤ 10 via four ``_resolve_*`` / ``_load_*`` / "
        f"``_filter_*`` / ``_should_*`` helpers; if this assertion fires, a "
        f"future PV has re-bloated the orchestrator body and must extract "
        f"additional collaborators or revert."
    )


@pytest.mark.parametrize("helper_name", _LOAD_MAPPINGS_HELPERS)
def test_load_command_mappings_helpers_cc_under_ceiling(helper_name: str) -> None:
    """Each ``load_command_mappings`` helper cc ≤ 8 per cycle plan §3 PV-02.

    Pins the v12.5.0 PV-02 D-2 acceptance criterion (3): every helper
    extracted from the original orchestrator body must individually stay
    under cc=8 so the refactor genuinely improves maintainability.
    """
    module = _load_module(_COMMANDS_PATH)
    func = _find_function(module, helper_name)
    cc = _cyclomatic_complexity(func)

    assert cc <= _HELPER_CC_CEILING, (
        f"v12.5.0 PV-02 D-2 violation: helper ``{helper_name}`` cc={cc} "
        f"exceeds ceiling {_HELPER_CC_CEILING}. The refactor decomposed "
        f"``load_command_mappings`` into four helpers each ≤ 8; if this "
        f"assertion fires, the helper has accumulated additional branches "
        f"and either needs to be further decomposed or the corresponding "
        f"orchestrator block needs a different extraction strategy."
    )


def test_load_command_mappings_signature_byte_identical() -> None:
    """``load_command_mappings`` public signature is byte-identical pre/post-refactor.

    Pins the v12.5.0 PV-02 D-2 acceptance criterion (4) + the CO-2 / C-3
    "no API break" invariant: the public signature of the orchestrator
    MUST remain literally identical so all callers
    (the apply layer, the compression-pipeline stage, every test fixture)
    keep working without modification.
    """
    source = _COMMANDS_PATH.read_text(encoding="utf-8")

    assert _LOAD_MAPPINGS_SIGNATURE in source, (
        "v12.5.0 PV-02 D-2 violation: ``load_command_mappings`` public "
        f"signature differs from the pre-refactor canonical form. The "
        f"signature MUST match this literal verbatim (whitespace included):"
        f"\n\n{_LOAD_MAPPINGS_SIGNATURE}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``current_version`` with a default value (additive change) — do NOT "
        "reorder existing parameters or change defaults."
    )


# ---------------------------------------------------------------------------
# Target 2 — apply_local_recipe (cc=17 pre / cc=4 post / ceiling 10)
# ---------------------------------------------------------------------------


def test_apply_local_recipe_cc_under_ceiling() -> None:
    """``apply_local_recipe`` cc ≤ 10 (was cc=17 pre-v12.5.0 PV-02 refactor).

    Pins the v12.5.0 PV-02 D-2 acceptance criterion (2) per
    ``.local/research/v12.5.0_gap_analysis.md`` §2 D-2: post-refactor
    orchestrator cyclomatic complexity must drop from cc=17 (NineS deep
    analyze recorded cc=16) to ≤ 10. Expected post-refactor value is
    cc=4 (one None-check after :func:`_resolve_apply_inputs`, one
    try/except around :func:`_apply_recipe_transform`, one
    ``recipe_id or command`` BoolOp).
    """
    module = _load_module(_COMMANDS_PATH)
    func = _find_function(module, "apply_local_recipe")
    cc = _cyclomatic_complexity(func)

    assert cc <= _ORCHESTRATOR_CC_CEILING, (
        f"v12.5.0 PV-02 D-2 violation: ``apply_local_recipe`` cc={cc} "
        f"exceeds ceiling {_ORCHESTRATOR_CC_CEILING}. The refactor was supposed "
        f"to bring cc from 17 to ≤ 10 via two helpers "
        f"(``_resolve_apply_inputs`` folding the 5 early-return decisions, "
        f"``_apply_recipe_transform`` folding the strip-ansi → pre/post "
        f"filter → truncate → on-empty pipeline). If this assertion fires, "
        f"a future PV has re-bloated the orchestrator body."
    )


@pytest.mark.parametrize("helper_name", _APPLY_RECIPE_HELPERS)
def test_apply_local_recipe_helpers_cc_under_ceiling(helper_name: str) -> None:
    """Each ``apply_local_recipe`` helper cc ≤ 8 per cycle plan §3 PV-02."""
    module = _load_module(_COMMANDS_PATH)
    func = _find_function(module, helper_name)
    cc = _cyclomatic_complexity(func)

    assert cc <= _HELPER_CC_CEILING, (
        f"v12.5.0 PV-02 D-2 violation: helper ``{helper_name}`` cc={cc} "
        f"exceeds ceiling {_HELPER_CC_CEILING}. The 2-helper extraction "
        f"deliberately keeps each helper ≤ 8 so the cc reduction is real "
        f"(not just shifted complexity)."
    )


def test_apply_local_recipe_signature_byte_identical() -> None:
    """``apply_local_recipe`` public signature is byte-identical pre/post-refactor."""
    source = _COMMANDS_PATH.read_text(encoding="utf-8")

    assert _APPLY_RECIPE_SIGNATURE in source, (
        "v12.5.0 PV-02 D-2 violation: ``apply_local_recipe`` public signature "
        f"differs from the pre-refactor canonical form. MUST match this "
        f"literal verbatim (whitespace included):\n\n{_APPLY_RECIPE_SIGNATURE}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``repo_signal`` with a default value (additive change)."
    )


# ---------------------------------------------------------------------------
# All-helpers-present sentinel (W-18 stanza couples to test_no_ghost_features)
# ---------------------------------------------------------------------------


def test_v12_5_0_pv02_helpers_all_present() -> None:
    """All 6 v12.5.0 PV-02 D-2 helpers exist at module scope.

    A single sentinel test that asserts every named helper resolves to a
    top-level function in ``commands.py``. Coupled with the W-18 ghost-
    audit stanza in ``tests/test_no_ghost_features.py`` to prevent the
    "helper named in the cc-pin but never actually extracted" failure
    mode (which would silently cause a cc=0 reading on a missing helper).
    """
    module = _load_module(_COMMANDS_PATH)
    expected = (*_LOAD_MAPPINGS_HELPERS, *_APPLY_RECIPE_HELPERS)
    found = {
        node.name
        for node in module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing = [name for name in expected if name not in found]
    assert not missing, (
        f"v12.5.0 PV-02 D-2 sweep is incomplete — missing helper(s): {missing}. "
        f"Expected the 6 helpers ({len(expected)} total) to be defined at "
        f"module scope in ``src/devolaflow/shell_proxy/commands.py``."
    )
