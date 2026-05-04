#!/usr/bin/env python3
"""Audit canonical_order field non-emptiness rate across dispatch payloads.

Implements the v10.7.0 D-P-1 deliverable per
`.local/research/v11.0.0_patches/D-P-1.md`. The audit answers a simple
quantitative question: **for each of the 17 positions in
``schemas/lean-dispatch.yaml#layout_invariant.canonical_order``, what
fraction of sampled dispatch payloads carries a populated (non-empty,
non-null) value for that key?**

Why this matters: positions 13-17 of `canonical_order` are APPEND-ONLY
TAIL entries (per A-2.2). A tail field whose non-empty rate is < 5%
across observed dispatches is a candidate for future NEST consolidation
under an existing block (per the A-2.3 nest-vs-append decision matrix
D3). The audit produces the per-position non-empty rate AS DATA — it
does NOT modify the schema, does NOT trigger any NEST conversion, and
does NOT touch ``schemas/lean-dispatch.yaml`` or
``src/devolaflow/compressor/layout.py::FROZEN_PREFIX_V7``.

D-P-1 is **audit-only**: zero schema mutations. The output is a markdown
synthesis (default) or JSON (``--json``). The G-6 cache-prefix gate is
preserved by construction — positions 1-12 are FROZEN per A-2.1; this
script reports their rates as informational only and emits a verbatim
DEFER notice in the report header.

Algorithm (per PDS §2):

1. Load ``schemas/lean-dispatch.yaml``; extract ``layout_invariant.canonical_order``
   (a 17-element list).
2. Walk ``.local/.agent/handoff/*.yaml`` envelopes (the empirical
   handoff ledger) and ``.local/research/v*_*.md`` artifacts that embed
   dispatch payloads inline (regex-matched code fences).
3. For each canonical_order key, count: present (key exists) AND
   non-empty (value is not None, not empty list, not empty dict, not
   empty string).
4. Emit a markdown report with the per-position table:
   position | key | sampled_count | non_empty_count | non_empty_rate |
   nest_candidate? | rationale.
5. ``nest_candidate?`` flags TAIL positions (13+) with rate < 0.05 as
   potential future merge candidates. Positions 1-12 are pinned
   "FROZEN — informational only".

Public API:

* :func:`scan_handoff_envelopes(handoff_dir)` -> list[dict]
* :func:`scan_research_dispatches(research_dir)` -> list[dict]
* :func:`compute_emptiness_report(canonical_order, payloads)` -> CanonicalOrderReport
* :func:`render_markdown(report)` -> str
* :func:`render_json(report)` -> str
* :func:`run(repo_root, *, output, json_out)` -> int

Entry point: ``python scripts/audit_canonical_order_emptiness.py
[--repo-root .] [--json] [--output PATH]``

Source: v10.7.0 PV — codified per
`.local/research/v11.0.0_patches/D-P-1.md` §2.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

__all__ = [
    "CanonicalOrderReport",
    "FROZEN_PREFIX_LENGTH",
    "NEST_CANDIDATE_THRESHOLD",
    "compute_emptiness_report",
    "load_canonical_order",
    "render_json",
    "render_markdown",
    "run",
    "scan_handoff_envelopes",
    "scan_research_dispatches",
]

# Per A-2.1: positions 1-12 of canonical_order are the FROZEN PREFIX.
# Their non-empty rates are reported but flagged "FROZEN — informational
# only". Future NEST consolidation MUST NOT touch positions 1-12.
FROZEN_PREFIX_LENGTH: int = 12

# Per PDS §2 step 5: tail positions (13+) with non-empty rate below
# this threshold are flagged as potential future NEST candidates. The
# threshold is informational; the actual nest-vs-append decision lives
# in A-2.3 + a dedicated ADR.
NEST_CANDIDATE_THRESHOLD: float = 0.05

_LEAN_DISPATCH_PATH = Path("schemas/lean-dispatch.yaml")
_HANDOFF_DIR = Path(".local/.agent/handoff")
_RESEARCH_DIR = Path(".local/research")

# Match ```yaml ... ``` (or ```yml) code fences that look like dispatch
# payloads. We require that the payload contain at least one of `hdr:`
# or `task:` (FROZEN PREFIX position 1 and 2) at top-level so we don't
# accidentally pick up unrelated YAML blocks.
_YAML_FENCE_RE = re.compile(
    r"```(?:yaml|yml)\s*\n(?P<body>.*?)\n```",
    re.DOTALL,
)
_DISPATCH_FINGERPRINT_RE = re.compile(r"^(?:hdr|task)\s*:", re.MULTILINE)


@dataclass(frozen=True)
class FieldEmptinessRow:
    """Per-position result row for the audit report."""

    position: int  # 1-indexed
    key: str
    sampled: int  # number of dispatch payloads inspected
    non_empty: int  # number where the key is present + non-empty
    non_empty_rate: float  # 0.0 .. 1.0
    is_frozen: bool  # True iff position <= FROZEN_PREFIX_LENGTH
    nest_candidate: bool  # True iff !is_frozen AND rate < NEST_CANDIDATE_THRESHOLD


@dataclass(frozen=True)
class CanonicalOrderReport:
    """Aggregated audit report."""

    canonical_order: tuple[str, ...]
    sampled_count: int
    handoff_count: int
    research_count: int
    rows: tuple[FieldEmptinessRow, ...]
    sources: tuple[Path, ...] = field(default_factory=tuple)


def _is_non_empty(value: object) -> bool:
    """True iff value is present and carries a non-empty payload.

    Treats ``None``, empty string, empty list, empty dict, and the
    literal sentinels ``[]`` / ``{}`` as empty. Numeric ``0`` and
    boolean ``False`` ARE considered non-empty (they are intentional
    field values, not absence markers).
    """
    if value is None:
        return False
    if isinstance(value, (str, list, dict)) and len(value) == 0:
        return False
    return True


def load_canonical_order(repo_root: Path) -> tuple[str, ...]:
    """Load ``layout_invariant.canonical_order`` from ``schemas/lean-dispatch.yaml``."""
    schema_path = repo_root / _LEAN_DISPATCH_PATH
    if not schema_path.is_file():
        raise SystemExit(f"missing canonical schema: {schema_path}")
    with schema_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    layout = data.get("layout_invariant") if isinstance(data, dict) else None
    if not isinstance(layout, dict):
        raise SystemExit(
            f"{schema_path} does not declare layout_invariant — cannot audit canonical_order"
        )
    order = layout.get("canonical_order")
    if not isinstance(order, list) or not order:
        raise SystemExit(
            f"{schema_path}#layout_invariant.canonical_order must be a non-empty list"
        )
    return tuple(str(k) for k in order)


def _parse_yaml_safe(text: str) -> dict | None:
    """Attempt to parse ``text`` as YAML; return None on any failure.

    The audit is best-effort over heterogeneous historical artifacts;
    a non-parseable fixture is silently skipped (counted in
    ``rejected_count``). Per S-5 we do NOT swallow the parse error
    silently — we log it on stderr — but the audit continues.
    """
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        print(f"[audit] skipped malformed YAML payload: {exc}", file=sys.stderr)
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded


def scan_handoff_envelopes(handoff_dir: Path) -> list[dict]:
    """Walk ``handoff_dir`` and return parsed envelope payloads.

    Each envelope is itself a dispatch-or-status YAML document. Per
    `.local/research/v8.3.0_design.md` §3.2, envelopes carry a
    ``payload`` block when they convey dispatch content; the envelope
    metadata wraps it. We probe BOTH the envelope top-level (some
    envelopes ARE dispatch payloads) and any inner ``payload`` /
    ``dispatch`` block.

    Returns a list of dispatch-shaped dicts (each with at least one of
    the FROZEN_PREFIX keys present). Non-dispatch envelopes (e.g. pure
    StatusReport messages) are excluded.
    """
    if not handoff_dir.is_dir():
        return []
    out: list[dict] = []
    for child in sorted(handoff_dir.glob("*.yaml")):
        try:
            text = child.read_text(encoding="utf-8")
        except OSError:
            continue
        loaded = _parse_yaml_safe(text)
        if loaded is None:
            continue
        candidates: list[dict] = [loaded]
        for inner_key in ("payload", "dispatch"):
            inner = loaded.get(inner_key)
            if isinstance(inner, dict):
                candidates.append(inner)
        for cand in candidates:
            if any(k in cand for k in ("hdr", "task", "goal")):
                out.append(cand)
                break
    return out


def scan_research_dispatches(research_dir: Path) -> list[dict]:
    """Walk ``research_dir`` and extract embedded dispatch YAML fences.

    Many `.local/research/v*_*.md` artifacts embed example dispatch
    payloads inside ```yaml fences. The fingerprint is the presence of
    `hdr:` or `task:` at top-level. Each match is parsed as YAML; if
    parsing fails the chunk is silently skipped (stderr-logged per S-5).
    """
    if not research_dir.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(research_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in _YAML_FENCE_RE.finditer(text):
            body = match.group("body")
            if not _DISPATCH_FINGERPRINT_RE.search(body):
                continue
            loaded = _parse_yaml_safe(body)
            if loaded is None:
                continue
            if any(k in loaded for k in ("hdr", "task", "goal")):
                out.append(loaded)
    return out


def compute_emptiness_report(
    canonical_order: tuple[str, ...],
    payloads: list[dict],
    *,
    handoff_count: int = 0,
    research_count: int = 0,
    sources: tuple[Path, ...] = (),
) -> CanonicalOrderReport:
    """Compute per-position non-emptiness rates across ``payloads``."""
    sampled = len(payloads)
    rows: list[FieldEmptinessRow] = []
    for idx, key in enumerate(canonical_order, start=1):
        non_empty = 0
        for payload in payloads:
            if key in payload and _is_non_empty(payload[key]):
                non_empty += 1
        rate = (non_empty / sampled) if sampled > 0 else 0.0
        is_frozen = idx <= FROZEN_PREFIX_LENGTH
        nest_candidate = (not is_frozen) and rate < NEST_CANDIDATE_THRESHOLD
        rows.append(
            FieldEmptinessRow(
                position=idx,
                key=key,
                sampled=sampled,
                non_empty=non_empty,
                non_empty_rate=rate,
                is_frozen=is_frozen,
                nest_candidate=nest_candidate,
            )
        )
    return CanonicalOrderReport(
        canonical_order=canonical_order,
        sampled_count=sampled,
        handoff_count=handoff_count,
        research_count=research_count,
        rows=tuple(rows),
        sources=sources,
    )


def render_markdown(report: CanonicalOrderReport) -> str:
    """Render the report as a markdown synthesis."""
    lines: list[str] = []
    lines.append("# Canonical Order Field Non-Emptiness Audit")
    lines.append("")
    lines.append(
        "> **AUDIT-ONLY** — this report measures per-position non-empty "
        "rates across observed dispatch payloads. It does NOT modify "
        "`schemas/lean-dispatch.yaml`, does NOT trigger any "
        "NEST conversion, and does NOT touch "
        "`src/devolaflow/compressor/layout.py::FROZEN_PREFIX_V7`."
    )
    lines.append("")
    lines.append(
        "> **G-6 frozen-prefix gate**: positions 1-12 (the v7.0.0 baseline "
        "FROZEN PREFIX per A-2.1) are reported below as informational "
        "only. Reordering / removing / merging any of these 12 keys "
        "invalidates the LLM cache prefix every L0/L1/L2/L3 dispatcher "
        "keys on and is a release blocker. Tail positions (13+) with "
        "non-empty rate below "
        f"{NEST_CANDIDATE_THRESHOLD:.0%} are flagged as POTENTIAL future "
        "NEST candidates per A-2.3 — the flag is advisory, not "
        "actionable; any actual merge requires a fresh ADR + new "
        "multi-baseline byte-test pin per A-2.4."
    )
    lines.append("")
    lines.append("## Sampling summary")
    lines.append("")
    lines.append(f"- Sampled dispatch payloads: **{report.sampled_count}**")
    lines.append(
        f"- Sources: {report.handoff_count} handoff envelopes + "
        f"{report.research_count} research-artifact embeds"
    )
    lines.append(f"- canonical_order length: **{len(report.canonical_order)}**")
    lines.append(
        "  (FROZEN PREFIX: positions 1-12; APPEND-ONLY TAIL: positions 13+)"
    )
    lines.append("")
    lines.append("## Per-position non-empty rates")
    lines.append("")
    lines.append(
        "| Pos | Key | Sampled | Non-empty | Rate | Disposition |"
    )
    lines.append("|---:|---|---:|---:|---:|---|")
    for row in report.rows:
        if row.is_frozen:
            disp = "FROZEN (A-2.1; reorder/merge prohibited)"
        elif row.nest_candidate:
            disp = (
                f"NEST candidate (rate < {NEST_CANDIDATE_THRESHOLD:.0%}; "
                f"see A-2.3 — advisory only, requires fresh ADR)"
            )
        else:
            disp = "APPEND retained (rate above threshold)"
        rate_pct = f"{row.non_empty_rate * 100:.1f}%"
        lines.append(
            f"| {row.position} | `{row.key}` | {row.sampled} | "
            f"{row.non_empty} | {rate_pct} | {disp} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- Sampling treats payloads heterogeneously: handoff envelopes "
        "may unwrap a `payload:` / `dispatch:` block; research-artifact "
        "embeds are extracted from `yaml` code fences whose first or "
        "second top-level key is `hdr:` or `task:`."
    )
    lines.append(
        "- Rates of 0% or 100% on a small sample (< 10 payloads) carry "
        "high variance; treat as directional signal, not statistical "
        "evidence."
    )
    lines.append(
        "- Non-empty = key present AND value is non-null, non-empty "
        f"string, non-empty list, non-empty dict. `0` and `False` ARE "
        "considered non-empty (intentional values)."
    )
    lines.append("")
    lines.append("## Multi-baseline byte test")
    lines.append("")
    lines.append(
        "This audit MUST coexist with the multi-baseline byte test at "
        "`tests/test_layout_invariant_multi_baseline.py` staying GREEN. "
        "If the audit sample is large and a tail field's rate drops to "
        "0% for a multi-cycle window, the operator may *propose* a "
        "future cycle that NEST-consolidates the field — but the gate "
        "is the new ADR + new baseline pin, NOT the threshold above."
    )
    lines.append("")
    return "\n".join(lines)


def render_json(report: CanonicalOrderReport) -> str:
    """Render the report as JSON (machine-consumable)."""
    return json.dumps(
        {
            "canonical_order": list(report.canonical_order),
            "sampled_count": report.sampled_count,
            "handoff_count": report.handoff_count,
            "research_count": report.research_count,
            "frozen_prefix_length": FROZEN_PREFIX_LENGTH,
            "nest_candidate_threshold": NEST_CANDIDATE_THRESHOLD,
            "rows": [
                {
                    "position": row.position,
                    "key": row.key,
                    "sampled": row.sampled,
                    "non_empty": row.non_empty,
                    "non_empty_rate": row.non_empty_rate,
                    "is_frozen": row.is_frozen,
                    "nest_candidate": row.nest_candidate,
                }
                for row in report.rows
            ],
        },
        indent=2,
    )


def _resolve_repo_root(start: Path | None = None) -> Path:
    p = (start or Path(__file__)).resolve()
    if p.is_file():
        p = p.parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise SystemExit("could not locate repo root (no pyproject.toml)")


def run(
    repo_root: Path,
    *,
    output: Path | None = None,
    json_out: bool = False,
) -> int:
    """Top-level driver: load schema, scan sources, render report."""
    canonical_order = load_canonical_order(repo_root)
    handoff_dir = repo_root / _HANDOFF_DIR
    research_dir = repo_root / _RESEARCH_DIR
    handoff_payloads = scan_handoff_envelopes(handoff_dir)
    research_payloads = scan_research_dispatches(research_dir)
    payloads = handoff_payloads + research_payloads
    report = compute_emptiness_report(
        canonical_order,
        payloads,
        handoff_count=len(handoff_payloads),
        research_count=len(research_payloads),
        sources=(handoff_dir, research_dir),
    )
    body = render_json(report) if json_out else render_markdown(report)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body, encoding="utf-8")
        print(f"[audit] wrote {output}")
    else:
        sys.stdout.write(body)
        if not body.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-consumable JSON instead of markdown",
    )
    parser.add_argument(
        "--include-positions",
        type=str,
        default=None,
        help=(
            "REJECTED — frozen prefix positions 1-12 are not selectable. "
            "Per A-2.1, these positions are pinned to the v7.0.0 baseline "
            "and reorder/merge is a release blocker. The audit reports "
            "their rates as informational only."
        ),
    )
    args = parser.parse_args(argv)
    if args.include_positions is not None:
        # We deliberately reject this flag at argparse-time per PDS §2 step 5.
        parser.error(
            "--include-positions is rejected: positions 1-12 are FROZEN per A-2.1 "
            "(`src/devolaflow/compressor/layout.py::FROZEN_PREFIX_V7`); "
            "their rates are reported informationally without operator opt-in."
        )
    repo_root = args.repo_root or _resolve_repo_root()
    return run(repo_root, output=args.output, json_out=args.json)


if __name__ == "__main__":
    sys.exit(main())
