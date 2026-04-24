"""Unified CompressionStage protocol + CompressionPipeline orchestrator.

v9.0.0 PV-06 (v8.5.1) — Theme T3 closure (Open Decision §9.2 #10 default-yes):
Until v8.5.0, every compression-side primitive (tool-output truncation in
``compressor.truncate_tool_output``, hierarchical predecessor summariser in
``compressor.summarise_predecessor``, directed compaction in
``compressor.directed_compact``, abstractive Stage A heuristic in
``compressor._assemble_abstractive_summary``, abstractive Stage B LLM in
``llm_client.LLMClient.complete``, and the RTK-pattern command-output mapping
in ``shell_proxy.commands.apply_local_recipe``) shipped as an independent
function with its own argument shape, its own logging surface, and its own
opt-in / opt-out condition. Composing two transforms required hand-wiring
their argument lists at every call site; testing the byte-identical-when-
bypassed invariant required separate fixtures per primitive.

This module unifies the 6 transforms behind a single :class:`CompressionStage`
protocol — ``transform(payload, context) -> payload`` — and a
:class:`CompressionPipeline` orchestrator that chains stages in order. The
orchestrator is a pure-Python sequential reducer: when ``stages`` is empty
(or every stage's ``bypass`` predicate returns ``True``), the pipeline is
**byte-identical to passing the input through unmodified** — this is the R5
strict invariant the v9-ADR-006 tests pin (see
``tests/test_compression_pipeline.py::test_empty_pipeline_is_byte_identical``
and ``::test_all_stages_bypassed_is_byte_identical``).

Design ref: ``.local/research/v9.0.0_implementation_plan.md`` §6.6.2 T03/T05
            ``.local/research/adr/v9-ADR-006-compression-pipeline-and-b3-flip.md``
            ``schemas/compression-pipeline.yaml`` (the schema this module
            implements)

P6-safe (A-2 Cache-Layout Governance v2): this module adds NO new top-level
dispatch keys, NO new NESTED dispatch fields, and NO new env-flags. The
pipeline composes existing transforms; adopters who want to invoke the
pipeline thread the existing per-transform kwargs through the stage's
``params`` dict instead of through bespoke function arguments. The 16-key
canonical_order + schema version 5 stay byte-identical (verified by
``tests/test_layout_invariant_multi_baseline.py``).

S-5 (No Silent Failures): every stage MAY raise; the pipeline catches and
re-raises with the offending stage's name appended to the exception message
so operators can locate the breaking transform without grepping logs. The
default behaviour is therefore loud — callers that want best-effort can pass
``strict=False`` to :meth:`CompressionPipeline.run` (the per-stage failure
is then logged via ``logging.WARNING`` and the stage's input is forwarded
to the next stage unchanged — preserving CO-2 verbatim semantics).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

__all__ = [
    "CompressionStage",
    "CompressionStageError",
    "CompressionPipeline",
    "PipelineRunResult",
    "StageResult",
    "BYPASS_ALWAYS",
    "BYPASS_NEVER",
    "make_stage",
]


# ---------------------------------------------------------------------------
# Bypass predicate helpers
# ---------------------------------------------------------------------------


def _bypass_never_impl(_payload: Any, _context: Mapping[str, Any]) -> bool:
    return False


def _bypass_always_impl(_payload: Any, _context: Mapping[str, Any]) -> bool:
    return True


BYPASS_NEVER: Callable[[Any, Mapping[str, Any]], bool] = _bypass_never_impl
"""Default bypass predicate: never bypass (the stage always runs).

Stages that want to honour an env-flag / profile setting / runtime probe
should supply a custom predicate via :func:`make_stage` or by
subclassing :class:`CompressionStage`. The uppercase-constant alias
documents the intent (this is a named sentinel, not a one-off callable).
"""

BYPASS_ALWAYS: Callable[[Any, Mapping[str, Any]], bool] = _bypass_always_impl
"""Bypass predicate that always returns ``True`` (skip the stage).

Used by :data:`tests.test_compression_pipeline.test_all_stages_bypassed_is_byte_identical`
to pin the byte-identical invariant. Production callers SHOULD NOT use
this directly — instead, rely on per-stage runtime probes (e.g.
``shell_proxy.commands.is_command_mapping_active``) to express the real
activation condition.
"""


# ---------------------------------------------------------------------------
# Stage protocol + dataclass
# ---------------------------------------------------------------------------


@runtime_checkable
class _CompressionStageProtocol(Protocol):
    """Structural protocol that any object implementing ``transform`` satisfies.

    Defined as a ``Protocol`` so the orchestrator can accept both
    :class:`CompressionStage` dataclass instances AND third-party objects
    that expose the same ``name`` / ``transform`` / ``bypass_conditions``
    surface (e.g. a future plugin module).
    """

    name: str

    def transform(self, payload: Any, context: Mapping[str, Any]) -> Any: ...


class CompressionStageError(RuntimeError):
    """Raised when a :class:`CompressionStage` fails AND ``strict=True``.

    Carries the stage's ``name``, the original exception class name, and
    the original exception message so the operator can locate the breaking
    transform without grepping logs. The ``__cause__`` chain preserves the
    original traceback for debugging.
    """


@dataclass(frozen=True)
class StageResult:
    """Per-stage outcome reported by :meth:`CompressionPipeline.run`.

    Mirrors the shape of the existing v8.0.0 P-12 / v8.2.0 PV-01 dict
    returns (``summary_text`` / ``transformations_applied`` / etc.) at the
    *aggregation* layer — individual stages keep their own return shapes.

    Attributes:
        name: The stage's canonical id (e.g. ``"truncate_tool_output"``,
            ``"summarise_predecessor"``, ``"apply_local_recipe"``).
        bypassed: ``True`` iff the stage's bypass predicate returned True
            (stage was skipped; payload forwarded unchanged).
        applied: ``True`` iff the stage actually mutated the payload.
            ``False`` for both "bypassed" and "ran but produced same output".
        error: ``None`` on success; the canonical Stage B-style mode name
            (``"network"`` / ``"parse"`` / ``"schema"`` / etc.) on
            best-effort failure when ``strict=False``.
        telemetry: Free-form per-stage metrics dict (token counts,
            compression ratios, latency_ms, etc.). Keys are stage-defined.
    """

    name: str
    bypassed: bool = False
    applied: bool = False
    error: str | None = None
    telemetry: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineRunResult:
    """Aggregated outcome of a :meth:`CompressionPipeline.run` call.

    Attributes:
        payload: Final payload after every stage has run (or been bypassed).
            When the pipeline is empty / fully-bypassed, this is the input
            payload unchanged (R5 strict — byte-identical invariant).
        stage_results: One :class:`StageResult` per stage in pipeline order.
        any_applied: ``True`` iff at least one stage actually mutated the
            payload. ``False`` for the byte-identical-bypass case.
        total_stages: ``len(stages)`` at construction time (stable across
            run calls — the pipeline is immutable after construction).
        applied_stages: List of stage names that ran AND produced a
            mutation. Used by status reports + telemetry attribution.
        bypassed_stages: List of stage names that returned bypass=True.
        failed_stages: List of stage names that raised AND ``strict=False``
            converted the failure to a soft skip. Empty when ``strict=True``
            (the pipeline raises on first failure).
    """

    payload: Any
    stage_results: tuple[StageResult, ...]
    any_applied: bool
    total_stages: int
    applied_stages: tuple[str, ...]
    bypassed_stages: tuple[str, ...]
    failed_stages: tuple[str, ...]


@dataclass
class CompressionStage:
    """One stage in a :class:`CompressionPipeline`.

    Concrete usage::

        stage = CompressionStage(
            name="truncate_tool_output",
            transform=lambda payload, ctx: truncate_tool_output(
                payload, head_chars=ctx.get("head_chars", 500),
                tail_chars=ctx.get("tail_chars", 500),
            )[0],  # truncate returns (text, removed)
            bypass=lambda _payload, ctx: not ctx.get("truncate_enabled", False),
            telemetry_key="truncate",
        )

    Attributes:
        name: Stage's canonical id; surfaces in :class:`StageResult.name`.
        transform: ``Callable[[payload, context], payload]``. Receives the
            running payload (output of the previous stage, or pipeline
            input for the first stage) and the read-only ``context`` dict.
            MUST return the new payload (may be the input unchanged).
        bypass: ``Callable[[payload, context], bool]``. When it returns
            ``True``, ``transform`` is NOT invoked and the payload passes
            through unchanged. Default :data:`BYPASS_NEVER` (always run).
        bypass_conditions: Optional list of human-readable bypass triggers
            (e.g. ``["env_flag_unset", "fresh_checkout"]``) for status
            reports. Has no runtime effect — pure documentation.
        telemetry_key: Optional key under which the stage attaches its
            telemetry dict on the :class:`StageResult` (defaults to ``name``).
    """

    name: str
    transform: Callable[[Any, Mapping[str, Any]], Any]
    bypass: Callable[[Any, Mapping[str, Any]], bool] = field(default=BYPASS_NEVER)
    bypass_conditions: tuple[str, ...] = field(default_factory=tuple)
    telemetry_key: str = ""

    def __post_init__(self) -> None:
        """Validate the stage at construction time (loud per S-5)."""
        if not self.name:
            raise ValueError("CompressionStage.name MUST be a non-empty string")
        if not callable(self.transform):
            raise TypeError(
                f"CompressionStage.transform MUST be callable; got {type(self.transform).__name__}"
            )
        if not callable(self.bypass):
            raise TypeError(
                f"CompressionStage.bypass MUST be callable; got {type(self.bypass).__name__}"
            )

    def should_bypass(self, payload: Any, context: Mapping[str, Any]) -> bool:
        """Wrapper around ``self.bypass`` that swallows non-bool returns.

        Per S-5 the predicate MUST return a bool; non-bool returns are
        treated as ``True`` (defensive bypass) AND a WARNING is logged so
        the operator sees the buggy predicate.
        """
        try:
            verdict = self.bypass(payload, context)
        except Exception as exc:  # noqa: BLE001 - S-5: never propagate from a predicate
            logger.warning(
                "[compression_pipeline] stage %r bypass predicate raised %s: %s "
                "— treating as bypass=True (defensive)",
                self.name,
                type(exc).__name__,
                exc,
            )
            return True
        if not isinstance(verdict, bool):
            logger.warning(
                "[compression_pipeline] stage %r bypass predicate returned non-bool "
                "(%s=%r) — treating as bypass=True (defensive per S-5)",
                self.name,
                type(verdict).__name__,
                verdict,
            )
            return True
        return verdict


def make_stage(
    name: str,
    transform: Callable[[Any, Mapping[str, Any]], Any],
    *,
    bypass: Callable[[Any, Mapping[str, Any]], bool] | None = None,
    bypass_conditions: Sequence[str] | None = None,
    telemetry_key: str = "",
) -> CompressionStage:
    """Convenience constructor for :class:`CompressionStage`.

    Equivalent to calling the dataclass constructor directly but accepts
    ``None`` for ``bypass`` / ``bypass_conditions`` to mean "use defaults"
    (the dataclass treats ``None`` as a TypeError because the fields are
    typed). Used by the v9.0.0 PV-06 refactor of the 6 transforms.
    """
    return CompressionStage(
        name=name,
        transform=transform,
        bypass=bypass if bypass is not None else BYPASS_NEVER,
        bypass_conditions=tuple(bypass_conditions or ()),
        telemetry_key=telemetry_key or name,
    )


# ---------------------------------------------------------------------------
# CompressionPipeline orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompressionPipeline:
    """Immutable sequential reducer over a list of :class:`CompressionStage`.

    The pipeline is the canonical orchestrator wired by:

    * :func:`devolaflow.compressor.summarise_predecessor` (extractive +
      Stage A abstractive + Stage B LLM-assisted)
    * :func:`devolaflow.compressor.truncate_tool_output` (tool-output
      truncation primitive)
    * :func:`devolaflow.compressor.directed_compact` (focus-keyword
      paragraph filter)
    * :func:`devolaflow.shell_proxy.commands.apply_local_recipe` (RTK
      pattern command-output mapping with multi-pass filter chain)

    R5 strict invariants (verified by
    ``tests/test_compression_pipeline.py``):

    1. **Empty pipeline** → ``payload`` returned unchanged
       (``test_empty_pipeline_is_byte_identical``).
    2. **All stages bypassed** → ``payload`` returned unchanged
       (``test_all_stages_bypassed_is_byte_identical``).
    3. **Single stage that returns input** → ``payload`` returned
       unchanged (``test_identity_stage_is_byte_identical``).
    4. **Stages run in declaration order** — the pipeline is a
       deterministic sequential reducer; stages do NOT see each other's
       inputs (only the running payload + the shared context dict).

    P6-safe: pipeline construction does NOT touch any module-level state,
    does NOT load files, does NOT spawn subprocesses, does NOT validate
    against ``DEFAULT_DISPATCH_LAYOUT``. The pipeline is a pure-Python
    composition primitive — orthogonal to the dispatch-layout invariant.

    Attributes:
        stages: Tuple of :class:`CompressionStage` (or any
            ``_CompressionStageProtocol``-implementing object) in run order.
        name: Optional pipeline id surfaced in error messages and telemetry.
            Default ``"unnamed"``.
    """

    stages: tuple[CompressionStage, ...] = field(default_factory=tuple)
    name: str = "unnamed"

    def __post_init__(self) -> None:
        """Validate stages at construction time (loud per S-5)."""
        if not isinstance(self.stages, tuple):
            object.__setattr__(self, "stages", tuple(self.stages))
        seen_names: set[str] = set()
        for idx, stage in enumerate(self.stages):
            if not hasattr(stage, "name") or not hasattr(stage, "transform"):
                raise TypeError(
                    f"CompressionPipeline.stages[{idx}] does not satisfy the "
                    f"_CompressionStageProtocol (missing 'name' or 'transform'); "
                    f"got {type(stage).__name__}"
                )
            if stage.name in seen_names:
                raise ValueError(
                    f"CompressionPipeline.stages contains duplicate stage name "
                    f"{stage.name!r} (each stage MUST have a unique name so "
                    f"telemetry attribution is unambiguous)"
                )
            seen_names.add(stage.name)

    def run(
        self,
        payload: Any,
        context: Mapping[str, Any] | None = None,
        *,
        strict: bool = True,
    ) -> PipelineRunResult:
        """Execute every stage in order and return the aggregated result.

        Parameters
        ----------
        payload:
            The input payload (text / dict / dataclass — stage-defined).
        context:
            Optional read-only context dict passed verbatim to every
            stage's ``transform`` and ``bypass`` callables. Stages
            consume their own kwargs from this dict (e.g. ``head_chars``
            for the truncate stage, ``focus_keywords`` for the directed-
            compact stage). Default ``{}``.
        strict:
            When ``True`` (default), the FIRST stage that raises propagates
            a :class:`CompressionStageError` carrying the stage name +
            original exception. When ``False``, per-stage failures are
            logged as WARNING (S-5 — never silently swallow), the
            failing stage's input is forwarded to the next stage
            unchanged, and the failed stage's name is recorded in
            ``failed_stages``.

        Returns
        -------
        :class:`PipelineRunResult`
            Aggregated outcome with ``payload`` set to the post-pipeline
            value (or the input verbatim when every stage was bypassed).

        Raises
        ------
        :class:`CompressionStageError`
            When ``strict=True`` AND any stage raised. The ``__cause__``
            chain preserves the original traceback.
        """
        ctx: Mapping[str, Any] = context if context is not None else {}
        running_payload = payload
        results: list[StageResult] = []
        applied_names: list[str] = []
        bypassed_names: list[str] = []
        failed_names: list[str] = []

        for stage in self.stages:
            if stage.should_bypass(running_payload, ctx):
                results.append(
                    StageResult(
                        name=stage.name,
                        bypassed=True,
                        applied=False,
                        error=None,
                        telemetry={"reason": "bypass_predicate"},
                    )
                )
                bypassed_names.append(stage.name)
                continue
            try:
                pre_payload = running_payload
                new_payload = stage.transform(pre_payload, ctx)
            except Exception as exc:  # noqa: BLE001 - S-5: log + classify
                msg = (
                    f"compression stage {stage.name!r} raised "
                    f"{type(exc).__name__}: {exc} (pipeline={self.name!r})"
                )
                if strict:
                    raise CompressionStageError(msg) from exc
                logger.warning(
                    "[compression_pipeline] %s — best-effort skip (strict=False)",
                    msg,
                )
                results.append(
                    StageResult(
                        name=stage.name,
                        bypassed=False,
                        applied=False,
                        error=type(exc).__name__,
                        telemetry={"exception": str(exc)},
                    )
                )
                failed_names.append(stage.name)
                continue
            applied = new_payload is not pre_payload and new_payload != pre_payload
            results.append(
                StageResult(
                    name=stage.name,
                    bypassed=False,
                    applied=applied,
                    error=None,
                    telemetry={"input_type": type(pre_payload).__name__},
                )
            )
            if applied:
                applied_names.append(stage.name)
            running_payload = new_payload

        return PipelineRunResult(
            payload=running_payload,
            stage_results=tuple(results),
            any_applied=bool(applied_names),
            total_stages=len(self.stages),
            applied_stages=tuple(applied_names),
            bypassed_stages=tuple(bypassed_names),
            failed_stages=tuple(failed_names),
        )

    def with_extra_stage(self, stage: CompressionStage) -> CompressionPipeline:
        """Return a new pipeline with ``stage`` appended after existing ones.

        The original pipeline is untouched (frozen dataclass). Used by
        callers that build a base pipeline once and customise per-call
        without mutating shared state.
        """
        return CompressionPipeline(stages=(*self.stages, stage), name=self.name)

    def __len__(self) -> int:
        return len(self.stages)

    def __bool__(self) -> bool:
        return bool(self.stages)

    def stage_names(self) -> tuple[str, ...]:
        """Return the ordered stage names — convenience for telemetry."""
        return tuple(stage.name for stage in self.stages)
