#!/usr/bin/env python3
"""v9.6.0 PV-01 — NineS-driven reference library refresh harness.

Iterates `workflow-system/agent/knowledge/reference-dependencies.yaml` and
runs `nines analyze --depth deep --agent-impact --keypoints` against each
reference whose `source_type == github_repo` AND whose canonical clone is
present under the local clone root (default: ``$DEVOLAFLOW_REFERENCE_ROOT``
or ``~/reference/``). Per-ref JSON output is written to
``.local/research/v9.6.0_reference_deltas/<ref-id>.json`` and a master
synthesis is written to ``.local/research/v9.6.0_reference_deltas.md``.

Per W-2 (NineS-Driven Analysis) and W-1 (SI-1 planning gate), this harness:

* Is the canonical input to the v9.6.0 SI-1 gap analysis.
* Skips gracefully when ``nines`` CLI is missing or a reference is not
  locally cloned (per W-2 fallback: "manual analysis... must be explicitly
  noted as manual"). Skipped entries are recorded in the synthesis with a
  ``status: skipped`` row and an explicit reason.
* Honors S-2 (no absolute paths in agent-facing output): the synthesis
  document refers to clones ONLY by their relative path under the local
  clone root, not by absolute filesystem path.
* Honors S-7 (external resources cited by remote URL): the per-ref entries
  cite ``repo_url`` from the YAML; local clone paths are operator-side
  inputs, never embedded in agent-facing files.

Usage::

    python scripts/nines_refresh_references.py
    python scripts/nines_refresh_references.py --reference-root ~/reference
    python scripts/nines_refresh_references.py --only superpowers,caveman
    python scripts/nines_refresh_references.py --dry-run
    python scripts/nines_refresh_references.py --depth shallow  # CI-friendly

Exit codes:

* ``0`` — analysis completed (some refs may have been skipped — see synthesis)
* ``2`` — bad CLI arguments
* ``3`` — YAML parse error
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = REPO_ROOT / "workflow-system" / "agent" / "knowledge" / "reference-dependencies.yaml"
DEFAULT_REFERENCE_ROOT = Path(
    os.environ.get("DEVOLAFLOW_REFERENCE_ROOT", str(Path.home() / "reference"))
).expanduser()
OUTPUT_BASE = REPO_ROOT / ".local" / "research"
DELTAS_DIR = OUTPUT_BASE / "v9.6.0_reference_deltas"
SYNTHESIS_PATH = OUTPUT_BASE / "v9.6.0_reference_deltas.md"

# Per-ref folder mapping — when the YAML id does not match the cloned dir name
# (e.g. "understand-anything" vs "Understand-Anything"). The mapping is
# explicit so the harness never silently picks up the wrong directory.
CLONE_NAME_OVERRIDES: dict[str, str] = {
    "understand-anything": "Understand-Anything",
}


@dataclass
class RefResult:
    """One row in the synthesis table."""

    ref_id: str
    repo_url: str
    source_type: str
    relevance_score: int | None
    # status ∈ {analyzed_deep, skipped_manual, skipped_no_clone,
    #           skipped_no_nines, skipped_non_repo}
    status: str
    reason: str
    findings_summary: str = ""
    output_json: str = ""  # repo-relative
    integration_points: list[str] = field(default_factory=list)


def _load_refs() -> list[dict]:
    """Parse the reference-dependencies.yaml into a flat list of dicts."""
    with YAML_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    refs: list[dict] = []
    for entry in data.get("active_tracking", []) or []:
        entry["_bucket"] = "active_tracking"
        refs.append(entry)
    for entry in data.get("periodic_monitoring", []) or []:
        entry["_bucket"] = "periodic_monitoring"
        refs.append(entry)
    return refs


def _nines_available() -> bool:
    return shutil.which("nines") is not None


def _resolve_clone(ref: dict, reference_root: Path) -> Path | None:
    """Return the local clone path for a ref, or None if not cloned."""
    if ref.get("source_type") != "github_repo":
        return None
    ref_id = ref["id"]
    candidate = CLONE_NAME_OVERRIDES.get(ref_id, ref_id)
    path = reference_root / candidate
    if path.is_dir():
        return path
    return None


def _run_nines(
    target_path: Path,
    output_json: Path,
    *,
    depth: str,
    timeout: int = 600,
) -> tuple[bool, str]:
    """Invoke nines analyze and write JSON to output_json. Return (ok, log)."""
    output_json.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "nines",
        "-f",
        "json",
        "analyze",
        "--target-path",
        str(target_path),
        "--depth",
        depth,
        "--agent-impact",
        "--keypoints",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    except OSError as e:
        return False, f"OSERROR: {e}"
    if proc.returncode not in (0, 1, 2):
        # NineS may exit 1/2 for advisory findings — still useful output.
        return False, f"exit={proc.returncode} stderr={proc.stderr[:400]}"
    output_json.write_text(proc.stdout, encoding="utf-8")
    return True, f"exit={proc.returncode}, {len(proc.stdout)} bytes JSON"


def _summarize_findings(json_path: Path) -> str:
    """Return a one-line summary for the synthesis table."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return f"(unparseable nines JSON: {e})"
    findings = data.get("findings") or []
    if not findings:
        return "0 findings"
    # Count by severity
    sev_counts: dict[str, int] = {}
    for f in findings:
        sev = (f.get("severity") or "info").lower()
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
    parts = [f"{n} {sev}" for sev, n in sorted(sev_counts.items())]
    return ", ".join(parts)


def analyze_one(
    ref: dict,
    *,
    reference_root: Path,
    nines_present: bool,
    depth: str,
    dry_run: bool,
) -> RefResult:
    ref_id = ref["id"]
    base = RefResult(
        ref_id=ref_id,
        repo_url=ref.get("repo_url", ""),
        source_type=ref.get("source_type", ""),
        relevance_score=ref.get("relevance_score"),
        status="",
        reason="",
        integration_points=ref.get("devolaflow_integration_points", []) or [],
    )
    if ref.get("source_type") != "github_repo":
        base.status = "skipped_non_repo"
        st = ref.get("source_type")
        base.reason = f"source_type={st} (not a github_repo — manual review per W-2)"
        return base
    clone = _resolve_clone(ref, reference_root)
    if clone is None:
        base.status = "skipped_no_clone"
        clone_name = CLONE_NAME_OVERRIDES.get(ref_id, ref_id)
        base.reason = (
            f"local clone not found at {reference_root.name}/{clone_name} — manual review per W-2"
        )
        return base
    if not nines_present:
        base.status = "skipped_no_nines"
        base.reason = "nines CLI not installed — manual review per W-2"
        return base
    json_path = DELTAS_DIR / f"{ref_id}.json"
    if dry_run:
        base.status = "analyzed_deep"
        base.reason = f"DRY-RUN — would write {json_path.relative_to(REPO_ROOT)}"
        base.output_json = str(json_path.relative_to(REPO_ROOT))
        base.findings_summary = "(dry-run)"
        return base
    ok, log = _run_nines(clone, json_path, depth=depth)
    if not ok:
        base.status = "skipped_no_nines"
        base.reason = f"nines failed on local clone: {log}"
        return base
    base.status = "analyzed_deep"
    base.reason = log
    base.output_json = str(json_path.relative_to(REPO_ROOT))
    base.findings_summary = _summarize_findings(json_path)
    return base


def render_synthesis(results: list[RefResult], *, depth: str) -> str:
    """Render the master `.local/research/v9.6.0_reference_deltas.md`."""
    today = date.today().isoformat()
    analyzed = [r for r in results if r.status == "analyzed_deep"]
    skipped_manual = [r for r in results if r.status in ("skipped_manual", "skipped_non_repo")]
    skipped_no_clone = [r for r in results if r.status == "skipped_no_clone"]
    skipped_no_nines = [r for r in results if r.status == "skipped_no_nines"]
    lines: list[str] = []
    lines.append("# v9.6.0 — Reference Library Refresh: NineS Synthesis")
    lines.append("")
    lines.append(f"**Authored:** {today}")
    lines.append("**Harness:** `scripts/nines_refresh_references.py`")
    lines.append("**Source YAML:** `workflow-system/agent/knowledge/reference-dependencies.yaml`")
    lines.append(f"**NineS depth:** `{depth}`")
    lines.append(f"**Total refs:** {len(results)}")
    lines.append(
        f"**Analyzed deep:** {len(analyzed)} | "
        f"Manual (non-repo / no clone / no nines): "
        f"{len(skipped_manual) + len(skipped_no_clone) + len(skipped_no_nines)}"
    )
    lines.append("")
    lines.append("## Coverage matrix")
    lines.append("")
    lines.append("| Ref ID | Source | Relevance | Status | Notes |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        rel = r.relevance_score if r.relevance_score is not None else "—"
        notes = r.findings_summary if r.findings_summary else r.reason
        lines.append(f"| `{r.ref_id}` | {r.source_type} | {rel} | {r.status} | {notes[:100]} |")
    lines.append("")

    if analyzed:
        lines.append("## Deep-analyzed refs (NineS findings)")
        lines.append("")
        for r in analyzed:
            lines.append(f"### `{r.ref_id}` (relevance {r.relevance_score})")
            lines.append("")
            lines.append(f"* **Repo:** {r.repo_url}")
            lines.append(f"* **NineS JSON:** `{r.output_json}`")
            lines.append(f"* **Findings:** {r.findings_summary}")
            lines.append(f"* **Run log:** {r.reason}")
            if r.integration_points:
                lines.append("* **Existing DevolaFlow integration points:**")
                for ip in r.integration_points:
                    lines.append(f"  * {ip}")
            lines.append("")

    manual_section = skipped_manual + skipped_no_clone + skipped_no_nines
    if manual_section:
        lines.append("## Manual-review refs (W-2 fallback)")
        lines.append("")
        lines.append(
            "These references could not be deep-analyzed by NineS because "
            "their `source_type` is not a github clone, OR the local clone "
            "was unavailable, OR the nines CLI was missing. They are "
            "covered by manual analysis in the v9.6.0 gap analysis "
            "(`v9.6.0_gap_analysis.md` §3-§4) using the existing key_patterns "
            "captured in `reference-dependencies.yaml`."
        )
        lines.append("")
        for r in manual_section:
            rel = r.relevance_score if r.relevance_score is not None else "—"
            lines.append(f"* `{r.ref_id}` (relevance {rel}, {r.source_type}) — {r.reason}")
        lines.append("")

    lines.append("## Cross-cycle coverage statement (W-2)")
    lines.append("")
    lines.append(
        'Per W-2: *"When NineS is unavailable, manual analysis following '
        "the same dimensions is acceptable but must be explicitly noted as "
        'manual."* The manual-review section above is the explicit note. '
        "Each ref in that section reuses its `key_patterns` + "
        "`devolaflow_integration_points` enumeration from "
        "`reference-dependencies.yaml` as the authoritative input to the "
        "v9.6.0 gap analysis (per W-1)."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-root",
        type=Path,
        default=DEFAULT_REFERENCE_ROOT,
        help=(
            "Root directory containing local reference clones "
            "(default: $DEVOLAFLOW_REFERENCE_ROOT or ~/reference/)"
        ),
    )
    parser.add_argument(
        "--only",
        type=str,
        default="",
        help="Comma-separated ref ids to analyze (default: all)",
    )
    parser.add_argument(
        "--depth",
        choices=["shallow", "deep"],
        default="deep",
        help="NineS analyze depth (default: deep per W-2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan only — write synthesis without invoking nines",
    )
    args = parser.parse_args(argv)

    try:
        refs = _load_refs()
    except (OSError, yaml.YAMLError) as e:
        print(f"ERROR parsing {YAML_PATH}: {e}", file=sys.stderr)
        return 3
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        refs = [r for r in refs if r["id"] in wanted]
        if not refs:
            print(f"ERROR: no refs matched --only={args.only}", file=sys.stderr)
            return 2

    nines_present = _nines_available()
    print(
        f"NineS available: {nines_present} | "
        f"reference-root: {args.reference_root.name} | "
        f"refs: {len(refs)} | depth: {args.depth} | "
        f"dry-run: {args.dry_run}",
        file=sys.stderr,
    )

    results: list[RefResult] = []
    for ref in refs:
        result = analyze_one(
            ref,
            reference_root=args.reference_root,
            nines_present=nines_present,
            depth=args.depth,
            dry_run=args.dry_run,
        )
        results.append(result)
        summary = result.findings_summary or result.reason[:60]
        print(
            f"  [{result.status:18}] {result.ref_id:35} {summary}",
            file=sys.stderr,
        )

    SYNTHESIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYNTHESIS_PATH.write_text(render_synthesis(results, depth=args.depth), encoding="utf-8")
    print(
        f"Wrote synthesis: {SYNTHESIS_PATH.relative_to(REPO_ROOT)} "
        f"({SYNTHESIS_PATH.stat().st_size} bytes)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
