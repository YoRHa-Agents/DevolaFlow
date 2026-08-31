"""Selector-backed context assembly for L1/L2 dispatches.

The host may inject ``AGENTS.md`` outside DevolaFlow's control.  This module
therefore owns the executable boundary: it obtains the selector's slice,
compresses the supplied selector context, and records what was actually
measured.  No legacy dispatch is changed unless a caller explicitly supplies
selector output or a task type for context assembly.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from devolaflow._compressor_transforms.validation import (
    compress_message,
    detect_bypass_conditions,
)

_LAYER_ALIASES = {
    "L0": "L0",
    "L1": "L1",
    "L2": "L2",
    "project": "L0",
    "wave": "L1",
    "task": "L2",
}
_AUDIT_PROFILE_NAMES = frozenset({"audit", "security-audit", "security_audit"})


def _normalize_layer(layer: str) -> str:
    if not isinstance(layer, str) or layer not in _LAYER_ALIASES:
        raise ValueError("layer must be L0, L1, L2, project, wave, or task")
    return _LAYER_ALIASES[layer]


def _source_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _selector_rule_text(
    selector_output: Mapping[str, Any] | None,
    *,
    task_type: str,
    profiles_path: Path | None,
    agents_md_path: Path | None,
    env: dict[str, str] | None,
) -> tuple[str | None, dict[str, Any]]:
    """Resolve the actual rule corpus and its slice account.

    A future selector can pass ``agents_md_text`` directly.  Current
    selectors expose the compact account only, so the canonical slicer is
    called at this boundary to obtain the actual text.
    """

    if selector_output is not None:
        direct = _source_text(selector_output.get("agents_md_text"))
        if direct is not None:
            account = selector_output.get("agents_md_slice")
            return direct, dict(account) if isinstance(account, Mapping) else {}

    if not task_type:
        return None, {}

    from devolaflow.agents_md_slice import select_agents_md_slice

    result = select_agents_md_slice(
        task_type,
        profiles_path=profiles_path,
        agents_md_path=agents_md_path,
        env=env,
    )
    return _source_text(result.get("sliced_text")), {
        key: value for key, value in result.items() if key != "sliced_text"
    }


def _measurement(
    source: str,
    profile: str,
    layer: str,
    original: str | None,
    compressed: str | None,
) -> dict[str, Any]:
    """Build a measurement without inferring unavailable token counts."""

    from devolaflow.task_adaptive_selector import estimate_tokens

    original_tokens = estimate_tokens(original) if original is not None else None
    compressed_tokens = estimate_tokens(compressed) if compressed is not None else None
    status = (
        "AVAILABLE"
        if original_tokens is not None and compressed_tokens is not None
        else "INSUFFICIENT"
    )
    reduction = (
        max(original_tokens - compressed_tokens, 0)
        if original_tokens is not None and compressed_tokens is not None
        else None
    )
    reduction_pct = (
        round(reduction / original_tokens * 100, 1)
        if reduction is not None and original_tokens
        else (0.0 if reduction == 0 else None)
    )
    return {
        "source": source,
        "profile": profile,
        "layer": layer,
        "tokens_in": original_tokens,
        "tokens_out": compressed_tokens,
        "token_reduction": reduction,
        "token_reduction_pct": reduction_pct,
        "status": status,
    }


def _is_preserve_context(
    text: str,
    *,
    task_type: str,
    profile: str,
) -> tuple[bool, list[str]]:
    """Return whether safety, destructive, or audit content must pass through."""

    reasons = detect_bypass_conditions(text)
    profile_key = profile.strip().lower().replace("_", "-") if isinstance(profile, str) else ""
    task_key = task_type.strip().lower().replace("_", "-") if isinstance(task_type, str) else ""
    if (
        profile_key in _AUDIT_PROFILE_NAMES
        or "audit" in profile_key
        or "audit" in task_key
        or task_key in {"security", "safety"}
    ):
        reasons.append("audit_context")
    return bool(reasons), list(dict.fromkeys(reasons))


def assemble_context(
    selector_output: Mapping[str, Any] | None = None,
    *,
    task_type: str = "",
    layer: str = "L2",
    profile: str | None = None,
    source: str = "selector",
    intensity: str | None = None,
    profiles_path: Path | None = None,
    agents_md_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build selector-backed, compressed context for one dispatch boundary.

    ``selector_output`` is normally the result of ``select_context``.  The
    returned ``rule_text`` is the actual per-task AGENTS.md slice, rather than
    the compact accounting-only summary.  Missing text remains ``None`` and
    is reported as ``INSUFFICIENT``.
    """

    if selector_output is not None and not isinstance(selector_output, Mapping):
        raise TypeError("selector_output must be a mapping or None")
    normalized_layer = _normalize_layer(layer)
    resolved_task_type = task_type if isinstance(task_type, str) else ""
    if not resolved_task_type and selector_output is not None:
        candidate = selector_output.get("task_type") or selector_output.get("profile_name")
        if isinstance(candidate, str):
            resolved_task_type = candidate
    resolved_profile = (
        profile
        if isinstance(profile, str)
        else (
            selector_output.get("profile_name")
            if selector_output is not None and isinstance(selector_output.get("profile_name"), str)
            else resolved_task_type
        )
    )
    resolved_profile = resolved_profile or "unknown"

    skill_text = (
        _source_text(selector_output.get("assembled_text")) if selector_output is not None else None
    )
    rule_text, slice_account = _selector_rule_text(
        selector_output,
        task_type=resolved_task_type,
        profiles_path=profiles_path,
        agents_md_path=agents_md_path,
        env=env,
    )
    if intensity is None:
        intensity = (
            selector_output.get("compression_intensity") if selector_output is not None else None
        )
    if not isinstance(intensity, str) or intensity not in {"minimal", "standard", "aggressive"}:
        from devolaflow.task_adaptive_selector import (
            load_profiles,
            resolve_compression_intensity,
        )

        intensity = resolve_compression_intensity(
            "l1_to_l2",
            load_profiles(profiles_path),
        )

    bypass_probe_text = "\n".join(
        value
        for value in (
            skill_text,
            _source_text(selector_output.get("goal")) if selector_output is not None else None,
            _source_text(selector_output.get("description"))
            if selector_output is not None
            else None,
        )
        if value
    )
    preserve, bypass_reasons = _is_preserve_context(
        bypass_probe_text,
        task_type=resolved_task_type,
        profile=resolved_profile,
    )
    if preserve:
        compressed_skill = skill_text
        compressed_rules = rule_text
    else:
        compressed_skill = (
            compress_message(skill_text, intensity=intensity, bypass_conditions=[])[
                "compressed_text"
            ]
            if skill_text is not None
            else None
        )
        compressed_rules = (
            compress_message(rule_text, intensity=intensity, bypass_conditions=[])[
                "compressed_text"
            ]
            if rule_text is not None
            else None
        )

    skill_measurement = _measurement(
        source,
        resolved_profile,
        normalized_layer,
        skill_text,
        compressed_skill,
    )
    rule_measurement = _measurement(
        source,
        resolved_profile,
        normalized_layer,
        rule_text,
        compressed_rules,
    )
    measured_inputs = [
        value
        for value in (skill_measurement["tokens_in"], rule_measurement["tokens_in"])
        if isinstance(value, int)
    ]
    measured_outputs = [
        value
        for value in (skill_measurement["tokens_out"], rule_measurement["tokens_out"])
        if isinstance(value, int)
    ]
    aggregate_measurement = {
        "source": source,
        "profile": resolved_profile,
        "layer": normalized_layer,
        "tokens_in": None,
        "tokens_out": None,
        "token_reduction": None,
        "token_reduction_pct": None,
        "status": "INSUFFICIENT",
    }
    if measured_inputs and measured_outputs:
        aggregate_measurement["tokens_in"] = sum(measured_inputs)
        aggregate_measurement["tokens_out"] = sum(measured_outputs)
        aggregate_measurement["token_reduction"] = max(
            aggregate_measurement["tokens_in"] - aggregate_measurement["tokens_out"],
            0,
        )
        aggregate_measurement["token_reduction_pct"] = (
            round(
                aggregate_measurement["token_reduction"] / aggregate_measurement["tokens_in"] * 100,
                1,
            )
            if aggregate_measurement["tokens_in"]
            else 0.0
        )
        aggregate_measurement["status"] = "AVAILABLE"

    return {
        "skill_text": compressed_skill,
        "rule_text": compressed_rules,
        "profile": resolved_profile,
        "layer": normalized_layer,
        "source": source,
        "intensity": intensity,
        "preserve_list_bypass": preserve,
        "bypass_reasons": bypass_reasons,
        "agents_md_slice": slice_account,
        "measurement": {
            **aggregate_measurement,
            "skill": skill_measurement,
            "rule": rule_measurement,
        },
    }


def apply_context_assembly(
    dispatch: Mapping[str, Any],
    assembly: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a dispatch copy with actual rules and nested measurement.

    ``rules`` is an existing canonical key, so this nests the new data
    without adding or reordering top-level keys.  If a legacy payload omitted
    ``rules``, it is inserted at its canonical slot before ``shared``.
    """

    if not isinstance(dispatch, Mapping):
        raise TypeError("dispatch must be a mapping")
    if not isinstance(assembly, Mapping):
        raise TypeError("assembly must be a mapping")
    result = copy.deepcopy(dict(dispatch))
    rules = result.get("rules")
    if not isinstance(rules, dict):
        rules = {}
        items = list(result.items())
        result = dict()
        inserted = False
        for key, value in items:
            if not inserted and key == "shared":
                result["rules"] = rules
                inserted = True
            result[key] = value
        if not inserted:
            result["rules"] = rules
    else:
        rules = copy.deepcopy(rules)

    if assembly.get("rule_text") is not None:
        rules["text"] = assembly["rule_text"]
    rules["compression"] = {
        "source": assembly.get("source"),
        "profile": assembly.get("profile"),
        "layer": assembly.get("layer"),
        "intensity": assembly.get("intensity"),
        "preserve_list_bypass": assembly.get("preserve_list_bypass", False),
        "bypass_reasons": list(assembly.get("bypass_reasons", [])),
        "measurement": copy.deepcopy(assembly.get("measurement", {})),
    }
    result["rules"] = rules
    return result


__all__ = ["apply_context_assembly", "assemble_context"]
