"""Focused implementation slice for the legacy module."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def _stage_truncate_tool_output_transform(payload, ctx: Mapping):
    """Pipeline-wrapped wrapper for :func:`truncate_tool_output`."""
    head = ctx.get("head_chars", DEFAULT_TRUNCATION_HEAD_CHARS)
    tail = ctx.get("tail_chars", DEFAULT_TRUNCATION_TAIL_CHARS)
    placeholder = ctx.get("placeholder_template", DEFAULT_TRUNCATION_PLACEHOLDER)
    new_text, _removed = truncate_tool_output(
        payload,
        head_chars=head,
        tail_chars=tail,
        placeholder_template=placeholder,
    )
    return new_text


def _stage_summarise_predecessor_transform(payload, ctx: Mapping):
    """Pipeline-wrapped wrapper for :func:`summarise_predecessor`.

    The stage expects ``payload`` to be the artifact path string (matching
    the existing ``summarise_predecessor(artifact_path, ...)`` signature)
    and returns the dict result verbatim.
    """
    return summarise_predecessor(
        payload,
        max_tokens=ctx.get("max_tokens", DEFAULT_SUMMARY_MAX_TOKENS),
        mode=ctx.get("mode", DEFAULT_SUMMARY_MODE),
        schema_hint=ctx.get("schema_hint"),
        retrieval_query=ctx.get("retrieval_query"),
        directive=ctx.get("directive"),
        llm_assist=bool(ctx.get("llm_assist", False)),
        llm_client=ctx.get("llm_client"),
    )


def _stage_directed_compact_transform(payload, ctx: Mapping):
    """Pipeline-wrapped wrapper for :func:`directed_compact`."""
    return directed_compact(
        payload,
        focus_keywords=ctx.get("focus_keywords"),
        max_drop_pct=ctx.get("max_drop_pct", DEFAULT_DIRECTED_COMPACT_MAX_DROP_PCT),
    )


def compression_pipeline_stages() -> list[CompressionStage]:
    """Return a fresh list of :class:`CompressionStage` for the 4 module transforms.

    The default ordering matches the v8.0.0 layered-pipeline reference
    (Layer 1 truncate / Layer 2 summarise / Layer 3 directed_compact). All
    four stages default to :data:`devolaflow.compression_pipeline.BYPASS_NEVER`
    (always run); callers that want activation gating attach their own
    bypass predicate by constructing a fresh stage via
    :func:`devolaflow.compression_pipeline.make_stage` and substituting it
    into the returned list.

    Per v9-ADR-006 D1 + Cycle Plan §6.6.2 T07: this is the canonical entry
    point for the v9.0.0 PV-06 unification. The function imports the
    pipeline module lazily so ``compressor.py`` does not gain a hard
    dependency on it (preserves the existing import graph + lets tests
    reach into compressor.py without dragging the pipeline runtime).
    """
    from devolaflow.compression_pipeline import make_stage

    return [
        make_stage(
            name="truncate_tool_output",
            transform=_stage_truncate_tool_output_transform,
            telemetry_key="truncate",
        ),
        make_stage(
            name="summarise_predecessor",
            transform=_stage_summarise_predecessor_transform,
            telemetry_key="summarise",
        ),
        make_stage(
            name="directed_compact",
            transform=_stage_directed_compact_transform,
            telemetry_key="compact",
        ),
    ]


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
