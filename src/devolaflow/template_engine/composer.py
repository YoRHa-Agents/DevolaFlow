"""Composition operator semantics.

Design ref: design_meta_framework.md §3.1 (operators), §3.3 (grammar)

Defines the five composition operators and utilities for walking
composition trees.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from devolaflow.template_engine.models import (
    Break,
    Choice,
    CompositionNode,
    GateRef,
    LoopRef,
    Parallel,
    Sequence,
    StageRef,
)

# ── Operator definitions (runtime-facing descriptors) ─────────────


@dataclass(frozen=True)
class SequenceOp:
    """Execute stages in strict order.

    Output of stage N becomes available to stage N+1.
    Semantics: start(B) requires completed(A).
    """

    name: str = "sequence"

    @staticmethod
    def stage_order(node: Sequence) -> list[CompositionNode]:
        return node.stages


@dataclass(frozen=True)
class ParallelOp:
    """Execute stages concurrently with a join strategy.

    Join strategies:
      - all: wait for every branch (default)
      - any: proceed when first branch completes
      - n_of: proceed when k branches complete
    """

    name: str = "parallel"

    @staticmethod
    def join_count(node: Parallel) -> int | None:
        if node.join == "all":
            return len(node.stages)
        if node.join == "any":
            return 1
        if node.join == "n_of":
            return node.n_of_count
        return len(node.stages)


@dataclass(frozen=True)
class ChoiceOp:
    """Conditional branch.

    Evaluates a predicate and executes exactly one of two paths.
    Predicates use dot-notation field references and support
    ``and``, ``or``, ``not`` combinators.
    """

    name: str = "choice"


@dataclass(frozen=True)
class LoopOp:
    """Repeat body until termination condition or max iterations.

    On exhaustion behaviour:
      - escalate: loop back to escalation_target
      - abort: halt workflow with divergence report
      - continue: exit loop and proceed despite unmet condition
    """

    name: str = "loop"


@dataclass(frozen=True)
class GateOp:
    """Quality checkpoint.

    Evaluates criteria against current state.  All criteria must pass
    for on_pass; otherwise on_fail executes.
    """

    name: str = "gate"


OPERATORS: dict[str, SequenceOp | ParallelOp | ChoiceOp | LoopOp | GateOp] = {
    "sequence": SequenceOp(),
    "parallel": ParallelOp(),
    "choice": ChoiceOp(),
    "loop": LoopOp(),
    "gate": GateOp(),
}


# ── Composition tree traversal ────────────────────────────────────


def collect_stage_refs(node: CompositionNode) -> set[str]:
    """Return all stage ids directly referenced in the composition tree."""
    refs: set[str] = set()
    _walk(node, refs)
    return refs


def _walk(node: CompositionNode, refs: set[str]) -> None:
    if isinstance(node, StageRef):
        refs.add(node.stage)
    elif isinstance(node, (Sequence, Parallel)):
        for child in node.stages:
            _walk(child, refs)
    elif isinstance(node, Choice):
        _walk(node.if_true, refs)
        _walk(node.if_false, refs)
    elif isinstance(node, (LoopRef, GateRef, Break)):
        pass


def collect_all_refs(
    node: CompositionNode,
    loops: dict[str, Any] | None = None,
    gates: dict[str, Any] | None = None,
) -> set[str]:
    """Collect stage refs from composition + loop bodies + gate targets."""
    refs = collect_stage_refs(node)

    if loops:
        for loop_def in loops.values():
            refs.update(loop_def.body_stages)
            if loop_def.escalation_target:
                refs.add(loop_def.escalation_target)

    if gates:
        for gate_def in gates.values():
            if gate_def.on_pass and gate_def.on_pass != "next":
                refs.add(gate_def.on_pass)
            if gate_def.on_fail and gate_def.on_fail.target:
                refs.add(gate_def.on_fail.target)

    return refs
