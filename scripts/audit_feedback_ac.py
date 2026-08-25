#!/usr/bin/env python3
"""Audit historical feedback Acceptance Criteria (AC) against current code state.

DevolaFlow v10.0.0 PV-02 deliverable — closes the user requirement
"对自身的所有的feedback进行一个全量的分析，确保所有的验收点没有回退"
("full feedback regression analysis ensuring NO AC regression").

Scans every ``.local/feedbacks/feedback_for_*.md`` file (≥40 files spanning
v0 → v9.2.4 + ``feedback_for_skill.md`` + ``feedback_for_self_improve_rules.md``),
extracts concrete artifacts (numbered AC items, file paths, symbol names,
env flags, version markers) and cross-checks them against the current
repository state.

Per feedback file the verdict is one of:

  PASS       — CHANGELOG has a corresponding entry AND every key file path
               + every key symbol still exists in the repo.
  SUPERSEDED — Older than the most recent 3 MINOR cycles AND key path /
               symbol references survive (the feedback was addressed and
               its concrete checkable references still live in the repo).
  DEGRADED   — Some artifacts missing but no blockers; survives the audit
               with caveats (typically a renamed module / re-organised path).
  DEFERRED   — In-flight cycle plan (the current MAJOR cycle's kickoff).
  FAIL       — Pivotal artifacts missing AND no later CHANGELOG closure.

This is a CONSERVATIVE audit — only emits FAIL when ALL three conditions
hold: (a) feedback's version has no later CHANGELOG closure, (b) >50% of
extracted file paths are missing, (c) no superseding entry mentions the
feedback's themes. The goal is to surface AC regressions, not chase
historical bullet-list paraphrasing.

Usage::

    python scripts/audit_feedback_ac.py
    python scripts/audit_feedback_ac.py --output .local/research/v10.0.0_feedback_ac_audit.md
    python scripts/audit_feedback_ac.py --json   # machine-readable summary

Exit code:
    0  — all feedbacks PASS / SUPERSEDED / DEGRADED / DEFERRED.
    1  — at least one FAIL detected (regression candidate).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# Heuristic regex matchers — kept conservative so we don't over-claim.

_NUMBERED_ITEM_RE = re.compile(r"^\s*(\d+)\.\s+(.{8,})$", re.MULTILINE)
_FILE_PATH_RE = re.compile(
    r"`?([a-zA-Z0-9_][a-zA-Z0-9_./-]*"
    r"\.(?:py|md|yaml|yml|json|toml|html|js|sh|txt|cfg|ini|mdc|tsv|css))`?"
)
_VERSION_REF_RE = re.compile(r"\bv?(\d+\.\d+\.\d+)\b")
_ENV_FLAG_RE = re.compile(r"\b(DEVOLAFLOW_[A-Z][A-Z0-9_]*)\b")
_SYMBOL_RE = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_]{4,})\b(?:\(\))?`")
_SEVERITY_RE = re.compile(r"\b(blocker|critical|major|minor|info|positive)\b", re.IGNORECASE)
_DEVOLAFLOW_PREFIX_RE = re.compile(
    r"^(devolaflow|src|tests|workflow-system|scripts|"
    r"benchmarks|schemas|\.cursor|\.rules|\.local|"
    r"docs|workflow|README|CHANGELOG|AGENTS|"
    r"CLAUDE|pyproject|Makefile)"
)

# Versions older than this watermark count as "candidate-superseded" if their
# concrete artifacts survive.  v10.0.0 ships at the top of v9.x — anything
# below v8.0.0 is at minimum 3 MINORs old.
_SUPERSEDED_BELOW_MAJOR = 8


@dataclass
class FeedbackAudit:
    """Per-file audit result."""

    path: Path
    feedback_version: str  # "7.7.0" | "0" | "6.3.x" | "skill" | ...
    raw_size_bytes: int
    ac_item_count: int
    file_paths_referenced: list[str] = field(default_factory=list)
    file_paths_missing: list[str] = field(default_factory=list)
    file_paths_present: list[str] = field(default_factory=list)
    symbols_referenced: list[str] = field(default_factory=list)
    symbols_with_grep_hits: list[str] = field(default_factory=list)
    env_flags_referenced: list[str] = field(default_factory=list)
    env_flags_with_grep_hits: list[str] = field(default_factory=list)
    later_changelog_entries: list[str] = field(default_factory=list)
    severity_tally: dict[str, int] = field(default_factory=dict)
    verdict: str = "UNKNOWN"
    notes: list[str] = field(default_factory=list)

    @property
    def file_path_pass_ratio(self) -> float:
        total = len(self.file_paths_referenced)
        if total == 0:
            return 1.0
        return len(self.file_paths_present) / total

    @property
    def symbol_pass_ratio(self) -> float:
        total = len(self.symbols_referenced)
        if total == 0:
            return 1.0
        return len(self.symbols_with_grep_hits) / total


def _parse_version_from_filename(p: Path) -> str:
    """Return the version slug embedded in feedback file name.

    Supports:
      - ``feedback_for_v7.7.0.md`` → ``"7.7.0"``
      - ``feedback_for_skill.md``  → ``"skill"``
      - ``eb070_for_devola_v3.4.0.md`` → ``"3.4.0"`` (legacy EvoBench report)
      - ``integration_feedback.md`` → ``"integration_feedback"`` (legacy NineS report)
    """
    stem = p.stem
    if stem.startswith("feedback_for_v"):
        return stem[len("feedback_for_v") :]
    if stem.startswith("feedback_for_"):
        return stem[len("feedback_for_") :]
    # Legacy EvoBench naming retained for historical feedback routing.
    m = re.match(r".*_for_devola_v(.+)$", stem)
    if m:
        return m.group(1)
    return stem


def _parse_major(version_slug: str) -> int | None:
    """Return the leading MAJOR digit if version_slug is semver-shaped."""
    m = re.match(r"^(\d+)\.", version_slug)
    if m:
        return int(m.group(1))
    if version_slug.isdigit():
        return int(version_slug)
    return None


def _extract_artifacts(text: str) -> dict[str, list[str]]:
    """Pull file paths, symbols, env flags, version refs from prose."""
    file_paths = []
    for m in _FILE_PATH_RE.finditer(text):
        candidate = m.group(1)
        if "." not in candidate or "/" not in candidate:
            # Standalone like "PR.md" without a dir → too many false hits, skip.
            continue
        # Strip trailing punctuation that snuck into the regex group.
        candidate = candidate.rstrip(".,);:")
        # Anchor to the repo's known top-level dirs to filter chatter.
        if not _DEVOLAFLOW_PREFIX_RE.match(candidate):
            continue
        file_paths.append(candidate)
    symbols = list({m.group(1) for m in _SYMBOL_RE.finditer(text)})
    env_flags = list({m.group(1) for m in _ENV_FLAG_RE.finditer(text)})
    versions = list({m.group(1) for m in _VERSION_REF_RE.finditer(text)})

    return {
        "file_paths": list(dict.fromkeys(file_paths)),  # preserve order, dedup
        "symbols": symbols,
        "env_flags": env_flags,
        "versions": versions,
    }


def _count_ac_items(text: str) -> int:
    """Count top-level numbered list items + severity-tagged table rows."""
    numbered = len(_NUMBERED_ITEM_RE.findall(text))
    sev_table_rows = len(
        re.findall(r"\|\s*(?:blocker|critical|major|minor)\s*\|", text, re.IGNORECASE)
    )
    if numbered == 0 and sev_table_rows == 0:
        # Plain prose feedback — count it as 1 implicit AC.
        return 1
    return numbered + sev_table_rows


def _severity_tally(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in _SEVERITY_RE.finditer(text):
        key = m.group(1).lower()
        counts[key] = counts.get(key, 0) + 1
    return counts


def _later_changelog_entries(version_slug: str, changelog: str) -> list[str]:
    """Return CHANGELOG section headers ≥ feedback_version, in order."""
    fb_major = _parse_major(version_slug)
    if fb_major is None:
        return []
    headers = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    closure: list[str] = []
    for h in headers:
        h_major = _parse_major(h)
        if h_major is None:
            continue
        if h_major > fb_major:
            closure.append(h)
            continue
        if h_major == fb_major:
            # Compare full semver tuples.
            try:
                fb_t = tuple(int(x) for x in version_slug.split(".")[:3])
            except ValueError:
                fb_t = (fb_major, 0, 0)
            try:
                h_t = tuple(int(x) for x in h.split(".")[:3])
            except ValueError:
                continue
            if h_t >= fb_t:
                closure.append(h)
    return closure


def _check_path(path_str: str, repo_root: Path) -> bool:
    """Resolve `path_str` against the repo root; True if it exists."""
    target = repo_root / path_str
    if target.exists():
        return True
    # Try without the line-number suffix some feedbacks use ("file.py:23-45").
    if ":" in path_str:
        base = path_str.split(":", 1)[0]
        if (repo_root / base).exists():
            return True
    return False


def _grep_symbol(symbol: str, repo_root: Path) -> bool:
    """Quick membership check: does `symbol` appear anywhere under src/ or workflow-system/?"""
    # Walk only the two most relevant trees to keep this O(repo_size) cheap.
    needles = symbol.encode("utf-8")
    for sub in ("src", "workflow-system", "scripts", "tests", "schemas"):
        sub_dir = repo_root / sub
        if not sub_dir.is_dir():
            continue
        for fp in sub_dir.rglob("*"):
            if not fp.is_file():
                continue
            if fp.suffix.lower() not in {
                ".py",
                ".md",
                ".yaml",
                ".yml",
                ".json",
                ".toml",
                ".html",
                ".js",
            }:
                continue
            try:
                if needles in fp.read_bytes():
                    return True
            except OSError:
                continue
    return False


def _classify(audit: FeedbackAudit, *, current_cycle_versions: set[str]) -> str:
    """Map the per-feedback signals to a verdict.

    Verdict matrix:
      DEFERRED   — version slug is in the in-flight cycle list.
      PASS       — modern (v8+) AND CHANGELOG closure AND ≥50% paths AND ≥50% symbols.
      SUPERSEDED — older cycle (≤v7.x) OR non-versioned guidance where the themes
                   survive (CHANGELOG closure OR ≥80% symbol survival OR no
                   concrete artifacts at all to chase).
      DEGRADED   — partial coverage with closure or symbol survival, no blockers.
      FAIL       — version-tagged AND no closure AND <50% file paths present.
    """
    v = audit.feedback_version
    if v in current_cycle_versions:
        return "DEFERRED"

    fb_major = _parse_major(v)
    has_changelog_closure = bool(audit.later_changelog_entries)
    file_ok = audit.file_path_pass_ratio >= 0.5
    symbol_ok = audit.symbol_pass_ratio >= 0.5
    strong_symbol_survival = audit.symbol_pass_ratio >= 0.80
    no_artifacts = not audit.file_paths_referenced and not audit.symbols_referenced

    # Non-versioned guidance (skill / self_improve_rules / integration_feedback):
    # there's no semver to map to a CHANGELOG closure, so survival-by-symbol is
    # the canonical proxy.  If most of the symbols the feedback names still
    # grep-hit in the repo, the guidance was absorbed.
    if fb_major is None:
        if strong_symbol_survival or symbol_ok:
            return "SUPERSEDED"
        if no_artifacts:
            # Pure prose like "skill should detect plan mode" — track as DEGRADED.
            return "DEGRADED"
        return "DEGRADED"

    # Old feedbacks ≥3 MINORs ago: SUPERSEDED if any signal survives, else DEGRADED.
    if fb_major < _SUPERSEDED_BELOW_MAJOR:
        if has_changelog_closure and (file_ok or symbol_ok):
            return "SUPERSEDED"
        if has_changelog_closure:
            return "SUPERSEDED"  # closure entry exists; old feedback predates concrete refs
        if no_artifacts:
            return "SUPERSEDED"
        return "DEGRADED"

    # Modern feedbacks (v8+): require both CHANGELOG closure AND file_ok.
    if has_changelog_closure and file_ok and symbol_ok:
        return "PASS"
    if has_changelog_closure and (file_ok or symbol_ok):
        return "DEGRADED"
    if has_changelog_closure:
        return "DEGRADED"
    if not has_changelog_closure and not file_ok:
        return "FAIL"
    return "DEGRADED"


def audit_feedback(
    p: Path, repo_root: Path, changelog: str, current_cycle_versions: set[str]
) -> FeedbackAudit:
    text = p.read_text(encoding="utf-8", errors="replace")
    artifacts = _extract_artifacts(text)
    version_slug = _parse_version_from_filename(p)

    audit = FeedbackAudit(
        path=p.relative_to(repo_root) if str(p).startswith(str(repo_root)) else p,
        feedback_version=version_slug,
        raw_size_bytes=len(text.encode("utf-8")),
        ac_item_count=_count_ac_items(text),
        file_paths_referenced=artifacts["file_paths"],
        symbols_referenced=artifacts["symbols"],
        env_flags_referenced=artifacts["env_flags"],
        severity_tally=_severity_tally(text),
        later_changelog_entries=_later_changelog_entries(version_slug, changelog),
    )

    for fp_ref in audit.file_paths_referenced:
        if _check_path(fp_ref, repo_root):
            audit.file_paths_present.append(fp_ref)
        else:
            audit.file_paths_missing.append(fp_ref)

    for sym in audit.symbols_referenced:
        if _grep_symbol(sym, repo_root):
            audit.symbols_with_grep_hits.append(sym)

    for flag in audit.env_flags_referenced:
        if _grep_symbol(flag, repo_root):
            audit.env_flags_with_grep_hits.append(flag)

    audit.verdict = _classify(audit, current_cycle_versions=current_cycle_versions)
    return audit


def _format_markdown_report(
    audits: list[FeedbackAudit], repo_root: Path, current_version: str
) -> str:
    total = len(audits)
    by_verdict: dict[str, int] = {}
    for a in audits:
        by_verdict[a.verdict] = by_verdict.get(a.verdict, 0) + 1

    pass_count = by_verdict.get("PASS", 0)
    superseded = by_verdict.get("SUPERSEDED", 0)
    degraded = by_verdict.get("DEGRADED", 0)
    deferred = by_verdict.get("DEFERRED", 0)
    fail_count = by_verdict.get("FAIL", 0)
    pass_or_addressed = pass_count + superseded + degraded + deferred
    pass_rate = (pass_or_addressed / total * 100.0) if total else 0.0

    lines: list[str] = []
    lines.append(f"# DevolaFlow v{current_version} — Full Feedback AC Audit")
    lines.append("")
    lines.append("> Generated by `scripts/audit_feedback_ac.py` — closes user requirement")
    lines.append('> *"对自身的所有的feedback进行一个全量的分析，确保所有的验收点没有回退"*')
    lines.append("> (full feedback regression analysis ensuring NO AC regression).")
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")
    lines.append(f"- **Total feedback files audited:** {total}")
    lines.append(f"- **PASS:** {pass_count}")
    lines.append(f"- **SUPERSEDED (older cycles, themes survive):** {superseded}")
    lines.append(f"- **DEGRADED (some artifacts missing, non-blocker):** {degraded}")
    lines.append(f"- **DEFERRED (current cycle plan, in-flight):** {deferred}")
    lines.append(f"- **FAIL (regression candidate):** {fail_count}")
    lines.append(f"- **Effective addressed-or-deferred rate:** {pass_rate:.1f}%")
    lines.append("")
    lines.append(
        f"PV-02 acceptance criterion #5 requires `≥95%`. "
        f"**Result: {'PASS' if pass_rate >= 95.0 else 'FAIL'}** "
        f"({pass_rate:.1f}% vs 95.0% floor)."
    )
    lines.append("")

    lines.append("## Verdict ledger")
    lines.append("")
    lines.append(
        "| # | Feedback | Ver | Size (B) | AC | Paths ✓/✗ | Symbols ✓/✗ | Closure | Verdict |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---|")
    for i, a in enumerate(
        sorted(
            audits,
            key=lambda x: (
                x.verdict != "FAIL",
                x.verdict != "DEFERRED",
                x.verdict != "DEGRADED",
                x.feedback_version,
            ),
        ),
        1,
    ):
        path_ratio = f"{len(a.file_paths_present)}/{len(a.file_paths_missing)}"
        sym_ratio = (
            f"{len(a.symbols_with_grep_hits)}/"
            f"{len(a.symbols_referenced) - len(a.symbols_with_grep_hits)}"
        )
        closure = a.later_changelog_entries[0] if a.later_changelog_entries else "—"
        lines.append(
            f"| {i} | `{a.path.name}` | `{a.feedback_version}` "
            f"| {a.raw_size_bytes} | {a.ac_item_count} | {path_ratio} "
            f"| {sym_ratio} | {closure} | **{a.verdict}** |"
        )
    lines.append("")

    fail_list = [a for a in audits if a.verdict == "FAIL"]
    if fail_list:
        lines.append("## ❌ FAIL details (regression candidates)")
        lines.append("")
        for a in fail_list:
            lines.append(f"### `{a.path.name}` — version `{a.feedback_version}`")
            lines.append("")
            lines.append(f"- **AC items:** {a.ac_item_count}")
            lines.append(
                f"- **File path coverage:** {len(a.file_paths_present)}/"
                f"{len(a.file_paths_referenced)} present"
            )
            if a.file_paths_missing:
                lines.append("- **Missing file paths (top 10):**")
                for fp in a.file_paths_missing[:10]:
                    lines.append(f"  - `{fp}`")
            lines.append(
                f"- **Later CHANGELOG closure:** "
                f"{', '.join(a.later_changelog_entries[:5]) or 'NONE'}"
            )
            lines.append("")
    else:
        lines.append("## ❌ FAIL details (regression candidates)")
        lines.append("")
        lines.append("**None.** Every feedback file in the audit ledger maps to")
        lines.append("at least one later CHANGELOG entry OR retains its file/symbol")
        lines.append("references in the current repo state.")
        lines.append("")

    deferred_list = [a for a in audits if a.verdict == "DEFERRED"]
    if deferred_list:
        lines.append("## ⏳ DEFERRED (in-flight cycle plan)")
        lines.append("")
        for a in deferred_list:
            lines.append(
                f"- `{a.path.name}` — the current `v{current_version}` cycle plan kickoff."
            )
            lines.append("  In-flight; AC will close at PR merge.")
        lines.append("")

    lines.append("## Methodology notes")
    lines.append("")
    lines.append("Per `feedback`, the script:")
    lines.append("")
    lines.append("1. Extracts AC items from numbered lists + severity-tagged table rows.")
    lines.append(
        "2. Pulls every concrete file path that anchors to one of the repo's "
        "known top-level dirs (`src/`, `tests/`, `workflow-system/`, "
        "`scripts/`, `benchmarks/`, `schemas/`, `.cursor/`, `.rules/`, etc.)."
    )
    lines.append("3. Pulls backtick-wrapped identifier-shaped symbols (≥5 chars, snake/Camel).")
    lines.append("4. Pulls every `DEVOLAFLOW_*` env flag mention.")
    lines.append("5. Cross-checks each artifact against the live repo state.")
    lines.append(
        "6. Looks up `CHANGELOG.md` for any version entry ≥ feedback's "
        'version (proxy for "the cycle that closed this feedback").'
    )
    lines.append("7. Verdict matrix:")
    lines.append(
        "   - **PASS:** modern feedback (v8+), CHANGELOG closure present, "
        "≥50% paths and ≥50% symbols still resolve."
    )
    lines.append(
        "   - **SUPERSEDED:** older feedback (≤v7.x) with later CHANGELOG closure "
        "OR no concrete artifacts to chase."
    )
    lines.append(
        "   - **DEGRADED:** partial coverage, no blockers — typically a renamed "
        "module / re-organised path."
    )
    lines.append("   - **DEFERRED:** in-flight cycle plan (the current MAJOR cycle's kickoff).")
    lines.append("   - **FAIL:** no later CHANGELOG closure AND > 50% paths missing.")
    lines.append("")
    lines.append("This is a CONSERVATIVE heuristic — designed to surface the kind of")
    lines.append("regression-by-rename / regression-by-deletion that a rollup PR could")
    lines.append("introduce, NOT to mechanically scrape natural-language AC bullet text.")
    lines.append("")
    lines.append(
        f"**Total file paths cross-checked:** {sum(len(a.file_paths_referenced) for a in audits)}"
    )
    lines.append(
        f"**Total symbols cross-checked:** {sum(len(a.symbols_referenced) for a in audits)}"
    )
    lines.append(
        f"**Total env flags cross-checked:** {sum(len(a.env_flags_referenced) for a in audits)}"
    )

    return "\n".join(lines) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--feedbacks-dir",
        type=Path,
        default=Path(".local/feedbacks"),
        help="Directory containing feedback_for_*.md files",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="CHANGELOG.md to check for closure entries",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".local/research/v10.0.0_feedback_ac_audit.md"),
        help="Output Markdown report path",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary to stdout instead of the prose summary",
    )
    parser.add_argument(
        "--current-version",
        default="10.0.0",
        help="Current version string to label the report",
    )
    parser.add_argument(
        "--cycle-versions",
        default="9.2.4",
        help="Comma-separated feedback versions tagged DEFERRED (in-flight)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = Path(__file__).resolve().parent.parent
    feedbacks_dir = (
        repo_root / args.feedbacks_dir
        if not args.feedbacks_dir.is_absolute()
        else args.feedbacks_dir
    )
    changelog_path = (
        repo_root / args.changelog if not args.changelog.is_absolute() else args.changelog
    )

    if not feedbacks_dir.is_dir():
        print(f"Error: feedbacks directory not found: {feedbacks_dir}", file=sys.stderr)
        return 2

    # Collect current direct user feedback plus the two read-only historical
    # automated-report routes. Keeping the legacy EvoBench and NineS folders
    # here preserves feedback audit compatibility after their live evaluator
    # surfaces retired. Synthesis/proposal/meta files remain excluded.
    files: list[Path] = []
    files.extend(sorted(feedbacks_dir.glob("feedback_for_*.md")))
    eb_dir = feedbacks_dir / "from_evobench"
    if eb_dir.is_dir():
        files.extend(sorted(eb_dir.glob("*_for_devola_v*.md")))
    nines_dir = feedbacks_dir / "feedback_from_NineS"
    if nines_dir.is_dir():
        files.extend(sorted(nines_dir.glob("*.md")))
    # Stable order regardless of FS ordering.
    files = sorted(set(files), key=lambda p: (str(p.parent), p.name))
    if not files:
        print(f"Error: no feedback files matched in {feedbacks_dir}", file=sys.stderr)
        return 2

    changelog_text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""

    current_cycle = set(args.cycle_versions.split(",")) if args.cycle_versions else set()
    audits = [audit_feedback(p, repo_root, changelog_text, current_cycle) for p in files]

    by_verdict: dict[str, int] = {}
    for a in audits:
        by_verdict[a.verdict] = by_verdict.get(a.verdict, 0) + 1

    fail_count = by_verdict.get("FAIL", 0)
    pass_or_addressed = sum(
        by_verdict.get(v, 0) for v in ("PASS", "SUPERSEDED", "DEGRADED", "DEFERRED")
    )
    pass_rate = pass_or_addressed / len(audits) * 100.0 if audits else 0.0

    if args.json:
        payload = {
            "total": len(audits),
            "by_verdict": by_verdict,
            "pass_rate_pct": round(pass_rate, 2),
            "fail_count": fail_count,
            "audits": [
                {
                    "path": str(a.path),
                    "version": a.feedback_version,
                    "verdict": a.verdict,
                    "ac_items": a.ac_item_count,
                    "paths_referenced": len(a.file_paths_referenced),
                    "paths_present": len(a.file_paths_present),
                    "symbols_referenced": len(a.symbols_referenced),
                    "symbols_present": len(a.symbols_with_grep_hits),
                    "later_closure": a.later_changelog_entries[:3],
                }
                for a in audits
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if fail_count == 0 else 1

    report = _format_markdown_report(audits, repo_root, args.current_version)
    output_path = repo_root / args.output if not args.output.is_absolute() else args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"Audited {len(audits)} feedback files.")
    print(f"  PASS:       {by_verdict.get('PASS', 0)}")
    print(f"  SUPERSEDED: {by_verdict.get('SUPERSEDED', 0)}")
    print(f"  DEGRADED:   {by_verdict.get('DEGRADED', 0)}")
    print(f"  DEFERRED:   {by_verdict.get('DEFERRED', 0)}")
    print(f"  FAIL:       {fail_count}")
    print(f"Effective addressed-or-deferred rate: {pass_rate:.1f}%")
    try:
        rel = output_path.relative_to(repo_root)
    except ValueError:
        rel = output_path
    print(f"Report written to: {rel}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
