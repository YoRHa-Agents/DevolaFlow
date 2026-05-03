"""Si-Chip bridge dataclass models — typed mirrors of the Si-Chip YAML shapes.

DevolaFlow consumes Si-Chip's YAML output via :mod:`subprocess` and parses
the YAML into these frozen dataclasses. We do NOT mirror the entire Si-Chip
schema — only the subset DevolaFlow actually consumes (token tier metrics,
iteration_delta, apply/defer verdict). When upstream Si-Chip evolves the
schema, the bridge gracefully ignores unknown fields per the
forward-compat contract.

Reference Si-Chip schema sources (read at runtime, not embedded):

* ``<si-chip-install>/templates/basic_ability_profile.schema.yaml`` —
  shape of :class:`BasicAbilityProfile`.
* ``<si-chip-install>/scripts/aggregate_eval.py`` — shape of
  :class:`MetricsReport` (the aggregate output).

Source: v9.5.0 PV-02 — closes part of D-S-2 from
`.local/research/v9.5.0_gap_analysis.md` §3.1.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ApplyVerdict(enum.StrEnum):
    """Verdict produced by :func:`apply_or_defer`.

    StrEnum (Python 3.11+) so values can be JSON-serialised AND passed
    verbatim into agent-facing CHANGELOG entries / commit messages
    without explicit ``.value`` access.
    """

    APPLY = "APPLY"
    DEFER = "DEFER"


@dataclass(frozen=True)
class BasicAbilityProfile:
    """Subset of Si-Chip's BasicAbilityProfile YAML shape.

    Si-Chip's full profile schema includes ~30 fields covering router
    floors, neighbour-skill comparisons, governance hooks, install
    telemetry, etc. DevolaFlow consumes the 6 fields actually used by
    the v9.5.0 PV-04 lifecycle hook + PV-05 dogfood:

    Attributes
    ----------
    ability_id : str
        The ``--ability`` argument passed to ``profile_static.py``;
        for DevolaFlow's dogfood pass this is ``"devola-flow"``.
    metadata_tokens : int
        Token count of the SKILL.md frontmatter; budget 100 per
        Si-Chip spec §3.1 D5/U1.
    body_tokens : int
        Token count of the SKILL.md body; budget 5000.
    references_count : int
        Number of files in ``references/`` directory.
    examples_count : int
        Number of files in ``examples/`` directory.
    raw : dict[str, Any]
        Verbatim parsed YAML — preserved for forward-compat if a
        future Si-Chip release adds fields the bridge doesn't yet
        model. Callers can read additional fields from ``raw`` without
        touching the dataclass.
    """

    ability_id: str
    metadata_tokens: int
    body_tokens: int
    references_count: int
    examples_count: int
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml_dict(cls, data: dict[str, Any]) -> BasicAbilityProfile:
        """Construct from Si-Chip's parsed YAML output.

        Tolerant of missing keys (returns 0 / "" defaults) — Si-Chip
        v0.4.0 sometimes omits ``examples_count`` for abilities that
        don't ship examples. Per S-5: missing keys log at DEBUG but do
        NOT raise — the caller decides whether the partial profile is
        usable.
        """
        return cls(
            ability_id=str(data.get("ability_id") or data.get("ability") or ""),
            metadata_tokens=int(data.get("metadata_tokens") or 0),
            body_tokens=int(data.get("body_tokens") or 0),
            references_count=int(data.get("references_count") or 0),
            examples_count=int(data.get("examples_count") or 0),
            raw=dict(data),
        )


@dataclass(frozen=True)
class MetricsReport:
    """Subset of Si-Chip's metrics_report.yaml shape.

    Si-Chip's aggregate_eval.py emits ~25 metrics (C1_metadata_tokens,
    C2_body_tokens, R1..R12 round-specific scores, governance flags,
    etc.). DevolaFlow consumes the composite + 4 component scores per
    Si-Chip spec §23 (the iteration_delta computation surface).

    Schema layouts supported by :meth:`from_yaml_dict`:

    * **Si-Chip MVP-8 (current)** — `aggregate_eval.py` v0.1.6+ emits
      a nested layout: ``metrics.task_quality.T1_pass_rate`` /
      ``metrics.task_quality.T3_baseline_delta`` /
      ``metrics.context_economy.C1_metadata_tokens`` /
      ``metrics.context_economy.C2_body_tokens`` plus
      ``summary.baseline_delta``. This is the layout the v10.2.2
      PV-03 dogfood pass #2 captured at
      ``.local/dogfood/10.2.1/skill-optimization_after_metrics.yaml``.
    * **Legacy top-level** — earlier Si-Chip cuts emitted flat
      top-level keys ``composite`` / ``task_delta`` / ``value_vector``
      / ``C1_metadata_tokens`` / ``C2_body_tokens``. The bridge
      preserves this for forward-compat with operators on pinned
      Si-Chip releases.

    Attributes
    ----------
    composite : float
        Si-Chip's overall composite score [0.0, 1.0]. Maps to
        MVP-8 ``metrics.task_quality.T1_pass_rate`` (the canonical
        composite proxy per Si-Chip spec §23) with fallback to a
        legacy top-level ``composite`` key.
    metadata_tokens : int
        Verbatim from C1_metadata_tokens; sourced via count_tokens.py
        when --skill-md is passed to aggregate_eval.py. Reads from
        ``metrics.context_economy.C1_metadata_tokens`` (MVP-8) with
        legacy top-level fallback.
    body_tokens : int
        Verbatim from C2_body_tokens. Reads from
        ``metrics.context_economy.C2_body_tokens`` (MVP-8) with
        legacy top-level fallback.
    task_delta : float
        Composite delta vs baseline (with-ability vs no-ability runs).
        Maps to MVP-8 ``summary.baseline_delta`` (preferred) or
        ``metrics.task_quality.T3_baseline_delta`` (fallback) with
        legacy top-level ``task_delta`` as the final fallback.
    value_vector : float
        Spec §23: weighted value computation; key input to
        iteration_delta. Maps to MVP-8 ``summary.baseline_delta``
        (the readily-available proxy emitted by current Si-Chip;
        a richer per-axis weighting will land upstream in a future
        Si-Chip cut). Legacy top-level ``value_vector`` honoured.
    raw : dict[str, Any]
        Forward-compat verbatim YAML.
    """

    composite: float
    metadata_tokens: int
    body_tokens: int
    task_delta: float
    value_vector: float
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml_dict(cls, data: dict[str, Any]) -> MetricsReport:
        """Construct from Si-Chip's parsed YAML output.

        Tolerates both the Si-Chip MVP-8 nested layout (the current
        ``aggregate_eval.py`` v0.1.6+ shape: ``metrics.task_quality.*``
        / ``metrics.context_economy.*`` / ``summary.*``) AND the legacy
        top-level layout (``composite`` / ``task_delta`` / etc. at the
        root). The MVP-8 nested paths are checked FIRST so that a
        document carrying both shapes (e.g. a future hybrid emit) is
        scored against the canonical MVP-8 surface.

        Per S-5: defaults to safe zeros when ALL candidate paths are
        missing. The downstream :func:`aggregate_delta` handles the
        "both runs scored 0" edge case explicitly. A partially-populated
        ``metrics`` block (e.g. ``T1_pass_rate`` set but
        ``baseline_delta`` ``None``) returns the populated values and
        zero for the missing fields — never raises ``KeyError``.

        Background: per ``.local/research/v10.2.2_dogfood_pass2.md`` §3,
        the v9.5.0..v10.2.2 builds of this helper read ONLY the legacy
        top-level keys. Si-Chip v0.1.6 emits only the MVP-8 nested
        keys, so every dogfood pass through PV-03 returned
        ``composite=0.0`` regardless of the actual scores. The fix
        landed in v10.2.3 PV-04.
        """
        metrics_block = data.get("metrics")
        if not isinstance(metrics_block, dict):
            metrics_block = {}
        task_quality = metrics_block.get("task_quality")
        if not isinstance(task_quality, dict):
            task_quality = {}
        context_economy = metrics_block.get("context_economy")
        if not isinstance(context_economy, dict):
            context_economy = {}
        summary_block = data.get("summary")
        if not isinstance(summary_block, dict):
            summary_block = {}

        composite_value = (
            task_quality.get("T1_pass_rate")
            if task_quality.get("T1_pass_rate") is not None
            else data.get("composite")
        )
        task_delta_value = (
            summary_block.get("baseline_delta")
            if summary_block.get("baseline_delta") is not None
            else (
                task_quality.get("T3_baseline_delta")
                if task_quality.get("T3_baseline_delta") is not None
                else data.get("task_delta")
            )
        )
        value_vector_value = (
            data.get("value_vector")
            if data.get("value_vector") is not None
            else summary_block.get("baseline_delta")
        )
        metadata_tokens_value = (
            context_economy.get("C1_metadata_tokens")
            if context_economy.get("C1_metadata_tokens") is not None
            else (data.get("C1_metadata_tokens") or data.get("metadata_tokens"))
        )
        body_tokens_value = (
            context_economy.get("C2_body_tokens")
            if context_economy.get("C2_body_tokens") is not None
            else (data.get("C2_body_tokens") or data.get("body_tokens"))
        )

        return cls(
            composite=float(composite_value or 0.0),
            metadata_tokens=int(metadata_tokens_value or 0),
            body_tokens=int(body_tokens_value or 0),
            task_delta=float(task_delta_value or 0.0),
            value_vector=float(value_vector_value or 0.0),
            raw=dict(data),
        )


@dataclass(frozen=True)
class IterationDeltaReport:
    """Computed delta between a "before" and "after" :class:`MetricsReport`.

    Si-Chip spec §23 defines iteration_delta as the per-round
    composite change. DevolaFlow's :func:`aggregate_delta` uses the
    composite-difference approximation (sufficient for the apply/defer
    verdict; the full spec §23 weighted formula is an opt-in upstream
    refinement we don't need at v9.5.0 cut).

    Attributes
    ----------
    before : MetricsReport
        The baseline run (no proposed changes applied).
    after : MetricsReport
        The post-change run.
    iteration_delta : float
        ``after.composite - before.composite``. Positive = improvement.
    threshold : float
        The apply-or-defer threshold (default 0.10 per Si-Chip §23).
    """

    before: MetricsReport
    after: MetricsReport
    iteration_delta: float
    threshold: float


@dataclass(frozen=True)
class SiChipResult:
    """Top-level result envelope for the v9.5.0 PV-04 lifecycle hook.

    Returned by the high-level :func:`run_dogfood_cycle` (declared in
    runner.py). Carries the verdict + provenance + structured metrics
    for downstream consumers (the PV-04 hook, the PV-05 feedback doc).

    Attributes
    ----------
    verdict : ApplyVerdict
        APPLY when iteration_delta >= threshold; else DEFER.
    delta : IterationDeltaReport | None
        The computed delta; ``None`` when the cycle bailed early
        (e.g. baseline run failed).
    install_source : str
        Which candidate path the resolver picked. See
        :class:`SiChipInstall.source`.
    skill_md : Path
        The skill file the cycle evaluated.
    notes : list[str]
        Free-form notes explaining edge cases (e.g. "baseline metrics
        zero — defer regardless"). Used by the PV-05 feedback doc.
    """

    verdict: ApplyVerdict
    delta: IterationDeltaReport | None
    install_source: str
    skill_md: Path
    notes: list[str] = field(default_factory=list)


__all__ = [
    "ApplyVerdict",
    "BasicAbilityProfile",
    "IterationDeltaReport",
    "MetricsReport",
    "SiChipResult",
]
