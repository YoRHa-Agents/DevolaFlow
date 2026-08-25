"""Per-task-type AGENTS.md slicing — extracted from ``task_adaptive_selector.py``.

v14.5.0 (ADR-006 / gap G-025 module split) — code extracted VERBATIM from
``task_adaptive_selector.py`` (the ~380-line v9.0.0 PV-07 AGENTS.md-slicing
subsystem: ``select_agents_md_slice`` + ``count_agents_md_rules`` + their
private helpers — conceptually a rules-distribution concern pairing with
``local/compiler.py``) per
``docs/cycle-archive/adr/v15-ADR-006-scorer-selector-module-split.md`` decision
item 2. Mechanical import fix only: ``select_agents_md_slice`` imports the
selector-core ``load_profiles`` / ``estimate_tokens`` at function level to
keep this module free of module-level cycles.

The ADR-006 re-export shims at the old ``devolaflow.task_adaptive_selector``
path were retired in v17.0.0 after call-site migration; this module is the
sole import surface. Absence pinned by ``tests/test_module_split_shims.py``.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# v9.0.0 (PV-07) — Per-task-type AGENTS.md slicing.
#
# Codified per ``docs/cycle-archive/adr/v9-ADR-007-rule-rebalancing-and-rollup.md``
# D3 (the OPERATOR-VISIBLE breaking-change facet of v9.0.0 MAJOR semver).
#
# select_agents_md_slice(task_type) filters the compiled AGENTS.md content by
# layer-prefix (Soul / Architecture / Conventions / Workflow / Style) per
# the ``meta.agents_md_slice.profiles[<profile>]`` configuration in
# context_profiles.yaml.
#
# v9.1.5 PV-05 default-ON flip: ``meta.agents_md_slice.enabled`` flips
# from ``false`` to ``true``. R5 strict env-flag opt-out
# ``DEVOLAFLOW_AGENTS_MD_SLICE=0`` reverts to the v9.1.4 byte-identical
# full-AGENTS.md behaviour for operators that have not yet adopted the
# sliced surface (the only NEW operator-visible behaviour change of the
# v9.2.0 cycle; W-20 reuses an existing-but-unwired flag rather than
# adding a new one). EXACTLY ``"0"`` forces opt-out; EXACTLY ``"1"``
# forces opt-in (overriding a hypothetical YAML opt-out); any other env
# value falls through to the YAML default. Pinned by
# ``tests/test_pv07_agents_md_slice.py``.
#
# The slice is a POST-COMPILE filter — never reorders or rewrites canonical
# rules; only HIDES rules irrelevant to the task type. The canonical
# AGENTS.md surface (compiled from ``.rules/*.mdc`` via
# ``devolaflow.local.compiler.RuleCompiler``) remains the single source of
# truth per the A-5 SSOT registry pattern (PV-03 ADR-003).
#
# MAJOR semver justification: when an operator opts into slicing, the
# cached prefix that L0 sends to L1/L2 dispatchees shrinks by 15-70%
# depending on task type. For long-running L0 sessions that cache the
# AGENTS.md prefix between dispatches, this is an observable change in
# the input prompt — downstream tools that audit / log prompts will see
# different content.
# ---------------------------------------------------------------------------


# v9.1.5 PV-05 — env-flag override for the agents_md_slice default-ON flip.
# Per W-20 reuse-first: the flag was telegraphed in the v9.0.0 PV-07 ADR-007
# D3 design but the runtime read landed in v9.1.5 PV-05 alongside the
# YAML default flip. R5 strict — EXACTLY "0" / "1" matched; anything else
# (including "true" / "yes" / "on" / " 1 " / "0.0") falls through to the
# YAML default per references/env-flags.md §6 conjunction contract.
_AGENTS_MD_SLICE_ENV_FLAG: str = "DEVOLAFLOW_AGENTS_MD_SLICE"


def _agents_md_slice_env_override(env: dict[str, str] | None = None) -> bool | None:
    """Return ``True`` / ``False`` / ``None`` for the env-flag override.

    Returns:
      * ``True`` when ``DEVOLAFLOW_AGENTS_MD_SLICE`` is EXACTLY ``"1"``
        (force opt-in).
      * ``False`` when ``DEVOLAFLOW_AGENTS_MD_SLICE`` is EXACTLY ``"0"``
        (force opt-out — the v9.1.5 PV-05 default-ON escape hatch).
      * ``None`` when the env var is unset or any other value
        (fall through to ``meta.agents_md_slice.enabled`` in
        context_profiles.yaml).

    R5 strict: pure dict.get with no IO; safe to call from import-time
    contexts. Per ``references/env-flags.md`` §6 the conjunction contract
    requires literal-only matching — loose variants like ``"true"`` /
    ``"yes"`` / ``"on"`` / ``"01"`` / leading-trailing whitespace fall
    through to the YAML default.
    """
    source = env if env is not None else os.environ
    raw = source.get(_AGENTS_MD_SLICE_ENV_FLAG, "")
    if raw == "0":
        return False
    if raw == "1":
        return True
    return None


_AGENTS_MD_PATH: Path = Path(__file__).parents[2] / "AGENTS.md"
_RULE_HEADING_RE = re.compile(r"^## ((?:S|A|C|W|ST)-\d+)\b", re.MULTILINE)
_TOP_LEVEL_HEADING_RE = re.compile(
    r"^# (Soul Rules|Architecture Rules|Conventions Rules|Workflow Rules|Style Rules)\b",
    re.MULTILINE,
)
_LAYER_PREFIX_BY_HEADING: dict[str, str] = {
    "Soul Rules": "soul",
    "Architecture Rules": "architecture",
    "Conventions Rules": "conventions",
    "Workflow Rules": "workflow",
    "Style Rules": "style",
}
_RULE_LAYER_BY_PREFIX: dict[str, str] = {
    "S": "soul",
    "A": "architecture",
    "C": "conventions",
    "W": "workflow",
    "ST": "style",
}


def _resolve_agents_md_path(agents_md_path: Path | None = None) -> Path:
    """Resolve the AGENTS.md path with optional override.

    Lookup order:
      1. Explicit ``agents_md_path`` parameter (test / script override).
      2. Module-level :data:`_AGENTS_MD_PATH` (parents[2] / AGENTS.md —
         the canonical compile target of `.rules/compile-config.yaml`
         per `RuleCompiler.compile_all()`).
    """
    if agents_md_path is not None:
        return agents_md_path
    return _AGENTS_MD_PATH


def _read_agents_md(agents_md_path: Path | None = None) -> str:
    """Read AGENTS.md verbatim. Returns "" when file is missing.

    Per S-5: missing file is an explicit empty signal returned with a
    DEBUG log line, NOT a silent exception.
    """
    path = _resolve_agents_md_path(agents_md_path)
    if not path.exists():
        logger.debug("AGENTS.md not found at %s — returning empty", path)
        return ""
    return path.read_text(encoding="utf-8")


def _split_agents_md_into_layers(text: str) -> list[tuple[str, str, list[tuple[str, str]]]]:
    """Split AGENTS.md text into ordered (layer_name, layer_header_line, [(rule_id, rule_text)]).

    Each layer block starts at a ``^# <layer> Rules`` line and contains all
    ``^## <prefix>-<N>`` rule sub-blocks until the next layer header (or
    EOF). The ``layer_header_line`` carries the verbatim ``# Soul Rules
    (P0) — ...`` line + the immediately-following blurb until the first
    rule heading. Rule text is the verbatim ``## S-1 — ...`` block plus
    its body until the next ``## `` or ``# `` boundary.

    Used by :func:`select_agents_md_slice` and by
    :func:`count_agents_md_rules` (the latter is the ground-truth used by
    ``tests/test_no_ghost_features.py::test_rule_count_under_cap``).
    """
    layers: list[tuple[str, str, list[tuple[str, str]]]] = []

    # Find every top-level layer heading. Each layer spans from one heading
    # to the next (or EOF).
    layer_matches: list[re.Match[str]] = list(_TOP_LEVEL_HEADING_RE.finditer(text))
    if not layer_matches:
        return layers

    for i, match in enumerate(layer_matches):
        layer_name = match.group(1)
        layer_start = match.start()
        layer_end = layer_matches[i + 1].start() if i + 1 < len(layer_matches) else len(text)
        layer_block = text[layer_start:layer_end]

        # Within the layer block, find every ``^## <prefix>-<N>`` sub-block.
        rule_matches = list(_RULE_HEADING_RE.finditer(layer_block))
        if not rule_matches:
            # Layer header with no rules — preserve header line, no rules.
            layers.append((layer_name, layer_block.rstrip() + "\n", []))
            continue

        # Layer header = everything before the first rule heading.
        header_line = layer_block[: rule_matches[0].start()].rstrip() + "\n"
        rules: list[tuple[str, str]] = []
        for j, rule_match in enumerate(rule_matches):
            rule_id = rule_match.group(1)
            rule_start = rule_match.start()
            rule_end = (
                rule_matches[j + 1].start() if j + 1 < len(rule_matches) else len(layer_block)
            )
            rule_text = layer_block[rule_start:rule_end].rstrip() + "\n"
            rules.append((rule_id, rule_text))

        layers.append((layer_name, header_line, rules))

    return layers


def count_agents_md_rules(agents_md_path: Path | None = None) -> dict[str, int | list[str]]:
    """Count total rules in compiled AGENTS.md, partitioned by layer prefix.

    Returns dict with:
      - ``total``: int — total ``^## ([SACW]|ST)-\\d+`` headings.
      - ``by_layer``: dict[str, int] — counts keyed by layer name
        (``"soul"`` / ``"architecture"`` / ``"conventions"`` / ``"workflow"`` / ``"style"``).
      - ``rule_ids``: list[str] — ordered list of every rule ID seen.

    The ground-truth source for the v9.0.0 60-rule HARD cap enforced by
    ``tests/test_no_ghost_features.py::test_rule_count_under_cap`` (per
    ADR-007 D5).
    """
    text = _read_agents_md(agents_md_path)
    layers = _split_agents_md_into_layers(text)

    by_layer: dict[str, int] = {prefix: 0 for prefix in _LAYER_PREFIX_BY_HEADING.values()}
    rule_ids: list[str] = []

    for layer_name, _header, rules in layers:
        layer_prefix = _LAYER_PREFIX_BY_HEADING.get(layer_name)
        if layer_prefix is None:
            continue
        by_layer[layer_prefix] += len(rules)
        rule_ids.extend(rid for rid, _ in rules)

    return {
        "total": sum(by_layer.values()),
        "by_layer": by_layer,
        "rule_ids": rule_ids,
    }


def _match_slice_profile(task_type: str, slice_cfg: dict[str, Any]) -> str:
    """Match ``task_type`` to a slice-profile name with goal-hint fallback.

    Lookup order (mirrors :func:`match_profile`):
      1. Exact key match on ``slice_cfg["profiles"]``.
      2. Goal-hint substring match against an existing :func:`match_profile`
         resolution (so the slice profile follows the section profile
         when both share a hint vocabulary).
      3. ``slice_cfg["fallback"]`` — when set to ``"full"`` the caller
         returns the unsliced AGENTS.md; when set to a profile name,
         that profile's slice is used.
    """
    profiles = slice_cfg.get("profiles", {})

    if task_type in profiles:
        return task_type

    task_lower = task_type.lower()
    for profile_name in profiles:
        if profile_name.lower() == task_lower:
            return profile_name

    return ""  # caller honours fallback semantics


def _filter_agents_md_by_profile(
    text: str,
    profile_layers: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    """Filter AGENTS.md text per a per-profile layer mapping.

    Args:
      text: full AGENTS.md content.
      profile_layers: dict like
        ``{"soul": "all", "architecture": ["A-1"], "workflow": ["W-9"], ...}``.
        Layer values are either the literal ``"all"`` (keep every rule
        in that layer) OR a list of rule IDs (keep only those). Missing
        keys SKIP the entire layer (drop the layer header too).

    Returns:
      (sliced_text, included_rule_ids, skipped_rule_ids)
    """
    layers = _split_agents_md_into_layers(text)
    out_parts: list[str] = []
    included: list[str] = []
    skipped: list[str] = []

    if text.startswith("<!--"):
        head_end = text.find("-->\n")
        if head_end != -1:
            out_parts.append(text[: head_end + len("-->\n")])
        else:
            head_end = text.find("-->")
            if head_end != -1:
                out_parts.append(text[: head_end + len("-->")])
        out_parts.append("\n")

    for layer_name, header_line, rules in layers:
        layer_prefix = _LAYER_PREFIX_BY_HEADING.get(layer_name)
        if layer_prefix is None:
            continue

        layer_spec = profile_layers.get(layer_prefix)
        if layer_spec is None:
            for rid, _ in rules:
                skipped.append(rid)
            continue

        if layer_spec == "all":
            allowed_ids: set[str] | None = None
        else:
            allowed_ids = set(layer_spec)

        kept_rules: list[tuple[str, str]] = []
        for rid, rtext in rules:
            if allowed_ids is None or rid in allowed_ids:
                kept_rules.append((rid, rtext))
                included.append(rid)
            else:
                skipped.append(rid)

        if not kept_rules:
            continue

        out_parts.append(header_line)
        out_parts.append("\n")
        for _rid, rtext in kept_rules:
            out_parts.append(rtext)
            out_parts.append("\n")

    sliced_text = "".join(out_parts).rstrip() + "\n"
    return sliced_text, included, skipped


def select_agents_md_slice(
    task_type: str,
    profiles_path: Path | None = None,
    agents_md_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Filter AGENTS.md to the rule slice for ``task_type``.

    v9.0.0 (PV-07) — per ADR-007 D3, the OPERATOR-VISIBLE breaking-change
    facet of v9.0.0 MAJOR semver. v9.1.5 PV-05 flipped
    ``meta.agents_md_slice.enabled`` from ``false`` to ``true`` —
    operators on the YAML default now receive sliced AGENTS.md
    automatically. The R5 strict env-flag opt-out
    ``DEVOLAFLOW_AGENTS_MD_SLICE=0`` reverts to the v9.1.4 byte-identical
    full-AGENTS.md behaviour for operators that have not yet adopted
    slicing.

    Override precedence (highest wins):
      1. ``DEVOLAFLOW_AGENTS_MD_SLICE=0`` — force opt-out (full text).
      2. ``DEVOLAFLOW_AGENTS_MD_SLICE=1`` — force opt-in (slice always on).
      3. ``meta.agents_md_slice.enabled`` from the YAML profile.

    Args:
      task_type: dispatch task type used for profile match.
      profiles_path: override for ``context_profiles.yaml`` location
        (test fixture override; production resolves to the canonical
        repo path).
      agents_md_path: override for ``AGENTS.md`` location (test fixture
        override; production resolves to the canonical compile target).
      env: override for ``os.environ`` — used by tests to exercise the
        env-flag override path without mutating process state.

    Returns dict with:
      - ``sliced_text``: filtered AGENTS.md text.
      - ``included_rules``: list[str] of rule IDs preserved (e.g.
        ``["S-1", ..., "A-1", "W-9"]``) OR the literal ``"all"`` when
        slicing is OFF (the byte-stable fast path).
      - ``skipped_rules``: list[str] of rule IDs hidden (empty when
        slicing OFF).
      - ``profile_name``: matched ``agents_md_slice.profiles`` key, or
        ``""`` when slicing OFF or no match (fallback applied).
      - ``slice_enabled``: bool — true when the slice was actually applied.
      - ``total_tokens``: estimated token count of returned text.
      - ``full_tokens``: estimated token count of the unsliced AGENTS.md.
      - ``slice_savings_pct``: percentage reduction (0.0 when slicing OFF).
    """
    from devolaflow.task_adaptive_selector import estimate_tokens, load_profiles

    config = load_profiles(profiles_path)
    full_text = _read_agents_md(agents_md_path)
    full_tokens = estimate_tokens(full_text) if full_text else 0

    slice_cfg = config.get("meta", {}).get("agents_md_slice", {})

    env_override = _agents_md_slice_env_override(env)
    if env_override is False:
        # R5 strict opt-out: env=0 → byte-identical full AGENTS.md.
        return {
            "sliced_text": full_text,
            "included_rules": "all",
            "skipped_rules": [],
            "profile_name": "",
            "slice_enabled": False,
            "total_tokens": full_tokens,
            "full_tokens": full_tokens,
            "slice_savings_pct": 0.0,
        }

    yaml_enabled = bool(slice_cfg.get("enabled", False))
    effective_enabled = env_override if env_override is True else yaml_enabled

    if not effective_enabled:
        return {
            "sliced_text": full_text,
            "included_rules": "all",
            "skipped_rules": [],
            "profile_name": "",
            "slice_enabled": False,
            "total_tokens": full_tokens,
            "full_tokens": full_tokens,
            "slice_savings_pct": 0.0,
        }

    profile_name = _match_slice_profile(task_type, slice_cfg)
    profile_layers = slice_cfg.get("profiles", {}).get(profile_name, {}) if profile_name else {}

    if not profile_layers:
        fallback = slice_cfg.get("fallback", "full")
        if fallback == "full":
            return {
                "sliced_text": full_text,
                "included_rules": "all",
                "skipped_rules": [],
                "profile_name": "",
                "slice_enabled": False,
                "total_tokens": full_tokens,
                "full_tokens": full_tokens,
                "slice_savings_pct": 0.0,
            }
        # Named-profile fallback
        profile_name = fallback
        profile_layers = slice_cfg.get("profiles", {}).get(profile_name, {})
        if not profile_layers:
            return {
                "sliced_text": full_text,
                "included_rules": "all",
                "skipped_rules": [],
                "profile_name": "",
                "slice_enabled": False,
                "total_tokens": full_tokens,
                "full_tokens": full_tokens,
                "slice_savings_pct": 0.0,
            }

    sliced_text, included, skipped = _filter_agents_md_by_profile(full_text, profile_layers)
    sliced_tokens = estimate_tokens(sliced_text)
    savings_pct = (
        round((full_tokens - sliced_tokens) / full_tokens * 100, 1) if full_tokens else 0.0
    )

    return {
        "sliced_text": sliced_text,
        "included_rules": included,
        "skipped_rules": skipped,
        "profile_name": profile_name,
        "slice_enabled": True,
        "total_tokens": sliced_tokens,
        "full_tokens": full_tokens,
        "slice_savings_pct": savings_pct,
    }
