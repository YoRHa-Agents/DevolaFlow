"""Comprehensive tests for `devolaflow.template_engine.runtime` (v7.4.9 P-04).

Closes G-G1 / G-G2 / G-I2 by exercising:

- :func:`evaluate_skip_condition` — the minimal expression evaluator
  (``==`` / ``!=``, identifier lookup, single/double-quoted literals,
  numeric literals, malformed-input safety, no-eval discipline).
- :func:`select_stages_for_runtime` — mode-driven stage filtering,
  default-mode resolution from ``parameters.mode.default``, environment
  overlays (``skip_stages`` + ``extra_stages``), edge cases (empty
  templates, parametrised templates, Choice composition).

Predecessor artifacts:
    - ``.local/research/v7.5.0_ghost_audit.md`` §3.G + §3.I + §5 P-04 row
    - ``src/devolaflow/template_engine/runtime.py``

Acceptance criteria source: P-04 task spec AC-1 through AC-5.
"""

from __future__ import annotations

import logging
from pathlib import Path

from devolaflow.template_engine.models import (
    Choice,
    Sequence,
    StageDefinition,
    StageRef,
    TemplateMetadata,
    WorkflowTemplate,
)
from devolaflow.template_engine.runtime import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_MODE,
    evaluate_skip_condition,
    select_stages_for_runtime,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_PATH = REPO_ROOT / "src" / "devolaflow" / "template_engine" / "runtime.py"


# ── Helpers ─────────────────────────────────────────────────────────


def _make_template(
    stages: list[StageDefinition],
    composition: Sequence | Choice | StageRef,
    *,
    parameters: dict | None = None,
    environment_modes: dict | None = None,
) -> WorkflowTemplate:
    """Build a minimal WorkflowTemplate for unit tests."""
    return WorkflowTemplate(
        schema_version="1.0",
        metadata=TemplateMetadata(name="test", version="0.0.1"),
        stages=stages,
        composition=composition,
        parameters=parameters or {},
        environment_modes=environment_modes or {},
    )


# ── 1. evaluate_skip_condition: equality + inequality ──────────────


def test_evaluate_eq_true_with_single_quoted_string() -> None:
    """`mode == 'deep'` is True when context['mode'] == 'deep'."""
    assert evaluate_skip_condition("mode == 'deep'", {"mode": "deep"}) is True


def test_evaluate_eq_false_when_value_differs() -> None:
    """`mode == 'deep'` is False when context['mode'] == 'standard'."""
    assert evaluate_skip_condition("mode == 'deep'", {"mode": "standard"}) is False


def test_evaluate_neq_true_when_value_differs() -> None:
    """`mode != 'deep'` is True when context['mode'] == 'standard'."""
    assert evaluate_skip_condition("mode != 'deep'", {"mode": "standard"}) is True


def test_evaluate_neq_false_when_value_matches() -> None:
    """`mode != 'deep'` is False when context['mode'] == 'deep'."""
    assert evaluate_skip_condition("mode != 'deep'", {"mode": "deep"}) is False


def test_evaluate_double_quoted_literal_supported() -> None:
    """Double-quoted RHS literals work the same as single-quoted ones."""
    assert evaluate_skip_condition('mode == "deep"', {"mode": "deep"}) is True
    assert evaluate_skip_condition('mode != "deep"', {"mode": "minimal"}) is True


def test_evaluate_bare_identifier_rhs_resolves_in_context() -> None:
    """Bare RHS identifier is looked up in context (e.g. `lhs == rhs_var`)."""
    ctx = {"current_env": "github", "target_env": "github"}
    assert evaluate_skip_condition("current_env == target_env", ctx) is True
    ctx["target_env"] = "local"
    assert evaluate_skip_condition("current_env == target_env", ctx) is False


def test_evaluate_numeric_literal_rhs() -> None:
    """Bare numeric RHS is coerced to int / float when not in context."""
    assert evaluate_skip_condition("retry_count == 3", {"retry_count": 3}) is True
    assert evaluate_skip_condition("ratio != 0.5", {"ratio": 0.6}) is True


def test_evaluate_missing_lhs_treats_as_none() -> None:
    """Unknown LHS identifier resolves to None (still answerable for ==/!=)."""
    assert evaluate_skip_condition("missing_key == 'x'", {}) is False
    assert evaluate_skip_condition("missing_key != 'x'", {}) is True


# ── 2. evaluate_skip_condition: edge cases & safety ────────────────


def test_evaluate_none_returns_false() -> None:
    """A None expression is treated as 'no skip condition' and returns False."""
    assert evaluate_skip_condition(None, {"mode": "deep"}) is False


def test_evaluate_empty_string_returns_false() -> None:
    """Empty / whitespace-only expressions return False."""
    assert evaluate_skip_condition("", {"mode": "deep"}) is False
    assert evaluate_skip_condition("   ", {"mode": "deep"}) is False


def test_evaluate_malformed_warns_and_returns_false(caplog) -> None:
    """Malformed expressions log WARNING and default to NOT skipping (safe)."""
    with caplog.at_level(logging.WARNING, logger="devolaflow.template_engine.runtime"):
        result = evaluate_skip_condition("this is not valid", {"mode": "deep"})
    assert result is False
    assert any("Malformed skip_condition" in r.message for r in caplog.records), (
        f"Expected a 'Malformed skip_condition' WARNING; got records: "
        f"{[r.message for r in caplog.records]}"
    )


def test_evaluate_does_not_use_python_eval() -> None:
    """Defensive: runtime.py must NOT call eval/exec/compile/__import__ (S-5 + security).

    AST-based check (rather than substring match) so docstring mentions like
    ``**Python eval() / exec() are never used**`` don't trigger false positives.
    Walks every call site in the module and rejects bare-name calls to the
    forbidden builtins.
    """
    import ast as _ast

    src = RUNTIME_PATH.read_text(encoding="utf-8")
    tree = _ast.parse(src, filename=str(RUNTIME_PATH))
    forbidden = {"eval", "exec", "__import__"}
    bad_calls: list[str] = []
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        func = node.func
        if isinstance(func, _ast.Name) and func.id in forbidden:
            bad_calls.append(f"{func.id}() at line {node.lineno}")
    assert not bad_calls, (
        f"runtime.py must not invoke any of {sorted(forbidden)} "
        f"(security: skip_condition is a YAML-authored string and untrusted); "
        f"found: {bad_calls}"
    )


# ── 3. select_stages_for_runtime: mode-driven filtering ────────────


def test_select_stages_no_skip_conditions_returns_all_stages() -> None:
    """A template with zero skip_conditions returns every stage in order."""
    stages = [StageDefinition(id=sid, primitive="implement") for sid in ("s1", "s2", "s3")]
    composition = Sequence(
        stages=[StageRef(stage="s1"), StageRef(stage="s2"), StageRef(stage="s3")]
    )
    tpl = _make_template(stages, composition)
    refs = select_stages_for_runtime(tpl, mode="standard")
    assert [r.stage for r in refs] == ["s1", "s2", "s3"]


def test_select_stages_filters_by_skip_condition() -> None:
    """skip_condition expressions are honoured per-stage."""
    stages = [
        StageDefinition(id="a", primitive="implement"),
        StageDefinition(id="b", primitive="verify", skip_condition="mode != 'deep'"),
        StageDefinition(id="c", primitive="implement", skip_condition="mode == 'minimal'"),
    ]
    composition = Sequence(stages=[StageRef(stage="a"), StageRef(stage="c"), StageRef(stage="b")])
    tpl = _make_template(stages, composition)

    minimal = [r.stage for r in select_stages_for_runtime(tpl, mode="minimal")]
    standard = [r.stage for r in select_stages_for_runtime(tpl, mode="standard")]
    deep = [r.stage for r in select_stages_for_runtime(tpl, mode="deep")]

    assert minimal == ["a"], f"minimal: only a (b skipped, c skipped); got {minimal}"
    assert standard == ["a", "c"], f"standard: a + c (b skipped); got {standard}"
    assert deep == ["a", "c", "b"], f"deep: all three; got {deep}"


def test_select_stages_default_mode_resolved_from_parameters() -> None:
    """When `mode` is not passed, fall back to `parameters.mode.default`."""
    stages = [
        StageDefinition(id="a", primitive="implement"),
        StageDefinition(id="b", primitive="verify", skip_condition="mode != 'deep'"),
    ]
    composition = Sequence(stages=[StageRef(stage="a"), StageRef(stage="b")])
    tpl = _make_template(
        stages,
        composition,
        parameters={
            "mode": {"type": "enum", "default": "standard", "choices": ["standard", "deep"]}
        },
    )
    refs = select_stages_for_runtime(tpl)
    assert [r.stage for r in refs] == ["a"], (
        "default mode='standard' from parameters should elide b (skip_condition: mode != 'deep')"
    )


def test_select_stages_no_parameters_falls_back_to_module_default() -> None:
    """A template without `parameters.mode` falls back to DEFAULT_MODE='standard'."""
    stages = [
        StageDefinition(id="a", primitive="implement"),
        StageDefinition(id="b", primitive="verify", skip_condition=f"mode != '{DEFAULT_MODE}'"),
    ]
    composition = Sequence(stages=[StageRef(stage="a"), StageRef(stage="b")])
    tpl = _make_template(stages, composition)
    refs = select_stages_for_runtime(tpl)
    assert [r.stage for r in refs] == ["a", "b"], (
        f"DEFAULT_MODE={DEFAULT_MODE!r} should make `mode != '{DEFAULT_MODE}'` false → keep b"
    )


def test_select_stages_default_environment_is_local() -> None:
    """The default environment is `local` per DEFAULT_ENVIRONMENT."""
    assert DEFAULT_ENVIRONMENT == "local"


# ── 4. select_stages_for_runtime: environment_modes overlay ────────


def test_environment_modes_skip_stages_filters_out() -> None:
    """environment_modes[<env>].skip_stages drops listed stages from the result."""
    stages = [StageDefinition(id=sid, primitive="implement") for sid in ("a", "b", "c")]
    composition = Sequence(stages=[StageRef(stage="a"), StageRef(stage="b"), StageRef(stage="c")])
    tpl = _make_template(
        stages,
        composition,
        environment_modes={"local": {"skip_stages": ["b"]}, "github": {}},
    )
    local = [r.stage for r in select_stages_for_runtime(tpl, environment="local")]
    github = [r.stage for r in select_stages_for_runtime(tpl, environment="github")]
    assert local == ["a", "c"], f"local skips b; got {local}"
    assert github == ["a", "b", "c"], f"github untouched; got {github}"


def test_environment_modes_extra_stages_appends() -> None:
    """environment_modes[<env>].extra_stages appends listed stages at the end."""
    stages = [StageDefinition(id=sid, primitive="implement") for sid in ("a", "b", "extra")]
    composition = Sequence(stages=[StageRef(stage="a"), StageRef(stage="b")])
    tpl = _make_template(
        stages,
        composition,
        environment_modes={"github": {"extra_stages": ["extra"]}, "local": {}},
    )
    github = [r.stage for r in select_stages_for_runtime(tpl, environment="github")]
    local = [r.stage for r in select_stages_for_runtime(tpl, environment="local")]
    assert github == ["a", "b", "extra"], f"github appends extra; got {github}"
    assert local == ["a", "b"], f"local untouched; got {local}"


def test_environment_modes_extra_stages_unknown_id_warns(caplog) -> None:
    """Unknown extra_stages id logs WARNING and is dropped (S-5: no silent failure)."""
    stages = [StageDefinition(id="a", primitive="implement")]
    composition = Sequence(stages=[StageRef(stage="a")])
    tpl = _make_template(
        stages,
        composition,
        environment_modes={"github": {"extra_stages": ["nonexistent"]}},
    )
    with caplog.at_level(logging.WARNING, logger="devolaflow.template_engine.runtime"):
        refs = select_stages_for_runtime(tpl, environment="github")
    assert [r.stage for r in refs] == ["a"]
    assert any("nonexistent" in r.message for r in caplog.records), (
        "Unknown extra_stages id must produce a WARNING per S-5"
    )


def test_environment_modes_unknown_environment_is_noop() -> None:
    """Querying an undeclared environment is a no-op (no skip / no extras)."""
    stages = [StageDefinition(id="a", primitive="implement")]
    composition = Sequence(stages=[StageRef(stage="a")])
    tpl = _make_template(stages, composition, environment_modes={"local": {"skip_stages": ["a"]}})
    refs = select_stages_for_runtime(tpl, environment="nonexistent")
    assert [r.stage for r in refs] == ["a"]


# ── 5. select_stages_for_runtime: composition variants & extras ────


def test_select_stages_with_choice_walks_both_branches() -> None:
    """Choice composition contributes both if_true and if_false branches.

    select_stages_for_runtime cannot evaluate the choice predicate at
    runtime-filter time (predicate is dispatch-layer concern), so it
    conservatively flattens both branches and lets per-stage
    skip_condition do the actual filtering.
    """
    stages = [StageDefinition(id=sid, primitive="implement") for sid in ("a", "b", "c")]
    composition = Choice(
        condition="env == 'prod'",
        if_true=StageRef(stage="b"),
        if_false=StageRef(stage="c"),
    )
    tpl = _make_template([*stages], Sequence(stages=[StageRef(stage="a"), composition]))
    refs = select_stages_for_runtime(tpl, mode="standard")
    assert [r.stage for r in refs] == ["a", "b", "c"], (
        "Choice branches both flattened — selection happens via skip_condition, not predicate"
    )


def test_select_stages_extra_context_is_threaded_into_evaluator() -> None:
    """Caller-supplied extra_context bindings are visible to skip_condition."""
    stages = [
        StageDefinition(id="a", primitive="implement"),
        StageDefinition(id="b", primitive="verify", skip_condition="role == 'reviewer'"),
    ]
    composition = Sequence(stages=[StageRef(stage="a"), StageRef(stage="b")])
    tpl = _make_template(stages, composition)

    refs_no_ctx = select_stages_for_runtime(tpl, mode="standard")
    refs_with_ctx = select_stages_for_runtime(
        tpl, mode="standard", extra_context={"role": "reviewer"}
    )
    assert [r.stage for r in refs_no_ctx] == ["a", "b"], (
        "Without extra_context, role lookup → None → 'reviewer' != None → keep b"
    )
    assert [r.stage for r in refs_with_ctx] == ["a"], (
        "With role='reviewer', skip_condition evaluates True → elide b"
    )


def test_select_stages_skip_condition_overrides_then_environment_filters_after() -> None:
    """environment_modes.skip_stages applies AFTER skip_condition (compose-friendly)."""
    stages = [
        StageDefinition(id="a", primitive="implement"),
        StageDefinition(id="b", primitive="verify", skip_condition="mode != 'deep'"),
        StageDefinition(id="c", primitive="implement"),
    ]
    composition = Sequence(stages=[StageRef(stage="a"), StageRef(stage="b"), StageRef(stage="c")])
    tpl = _make_template(
        stages,
        composition,
        environment_modes={"local": {"skip_stages": ["a"]}},
    )
    refs = select_stages_for_runtime(tpl, mode="deep", environment="local")
    got = [r.stage for r in refs]
    assert got == ["b", "c"], f"Order: 1) keep all (deep), 2) drop a per env. Got {got}"


# ── 6. Public API ──────────────────────────────────────────────────


def test_runtime_public_api_is_exported_from_template_engine() -> None:
    """`select_stages_for_runtime` and friends are exposed at the package level."""
    from devolaflow import template_engine as te

    for name in ("select_stages_for_runtime", "evaluate_skip_condition", "DEFAULT_MODE"):
        assert hasattr(te, name), f"{name} missing from template_engine.__init__ exports"


# ── 7. Coverage corner cases ───────────────────────────────────────


def test_evaluate_bare_unquoted_string_rhs() -> None:
    """Bare RHS that is neither in context nor numeric is treated as a literal string.

    Covers `_coerce_bare_rhs` final return branch (after both int and float coercion
    fail). Useful for declarative comparisons like `mode == deep` (no quotes).
    """
    assert evaluate_skip_condition("mode == deep", {"mode": "deep"}) is True
    assert evaluate_skip_condition("mode == deep", {"mode": "minimal"}) is False


def test_select_stages_with_loop_and_gate_refs_in_composition() -> None:
    """LoopRef / GateRef / Break in composition contribute no stages (dispatch concern)."""
    from devolaflow.template_engine.models import Break, GateRef, LoopRef

    stages = [StageDefinition(id="a", primitive="implement")]
    composition = Sequence(
        stages=[
            StageRef(stage="a"),
            LoopRef(ref="convergence_loop"),
            GateRef(ref="quality_gate"),
            Break(),
        ]
    )
    tpl = _make_template(stages, composition)
    refs = select_stages_for_runtime(tpl)
    assert [r.stage for r in refs] == ["a"], (
        "LoopRef/GateRef/Break must contribute no stages to the runtime list"
    )


def test_select_stages_unknown_ref_kept_as_is() -> None:
    """A composition StageRef with no matching StageDefinition is kept (defensive)."""
    stages = [StageDefinition(id="defined", primitive="implement")]
    composition = Sequence(stages=[StageRef(stage="defined"), StageRef(stage="orphan_ref")])
    tpl = _make_template(stages, composition)
    refs = select_stages_for_runtime(tpl)
    assert [r.stage for r in refs] == ["defined", "orphan_ref"], (
        "Unknown stage refs must be kept (fail-open) — the validator handles correctness"
    )


def test_environment_modes_extra_stages_non_string_entry_silently_skipped() -> None:
    """Non-string entries in extra_stages are silently filtered (defensive type check)."""
    stages = [StageDefinition(id="a", primitive="implement")]
    composition = Sequence(stages=[StageRef(stage="a")])
    tpl = _make_template(
        stages,
        composition,
        environment_modes={"github": {"extra_stages": [123, None, "a"]}},
    )
    refs = select_stages_for_runtime(tpl, environment="github")
    assert [r.stage for r in refs] == ["a", "a"], (
        "Only the string 'a' should be appended; 123 and None are dropped"
    )
