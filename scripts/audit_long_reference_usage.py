#!/usr/bin/env python3
"""Long-reference "actually-used" evidence audit.

Per `.local/research/v11.0.0_patches/D-D-2.md` §2 algorithm. Scans the
repo's `.local/.agent/handoff/` and `.local/.agent/archive/` for
empirical evidence that long references (>500 lines) are actually
referenced by handoff envelopes or research artifacts. Emits a
markdown report (or JSON via `--json`).

Usage:
    python scripts/audit_long_reference_usage.py
    python scripts/audit_long_reference_usage.py --output report.md
    python scripts/audit_long_reference_usage.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

LONG_REFERENCE_THRESHOLD = 500
ENVELOPE_RE = re.compile(
    r"^(?P<from>L[0-3]|operator|human)__"
    r"(?P<to>L[0-3]|operator|human)__"
    r"(?P<change_id>[a-z0-9._-]+)__"
    r"(?P<seq>\d{4})\.yaml$"
)
REFERENCE_TOKEN = re.compile(r"references/([a-z0-9-]+)\.md")


@dataclass(frozen=True)
class EnvelopeRecord:
    path: Path
    from_layer: str
    to_layer: str
    change_id: str
    seq: int
    cited_references: tuple[str, ...]


@dataclass(frozen=True)
class LongRefReport:
    long_references: tuple[str, ...]
    handoff_dir: Path
    archive_dir: Path
    envelopes: tuple[EnvelopeRecord, ...]
    citations: dict[str, int]
    research_citations: dict[str, int]
    archive_count: int


def resolve_repo_root(start: Path | None = None) -> Path:
    p = (start or Path(__file__)).resolve()
    if p.is_file():
        p = p.parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise SystemExit("could not locate repo root (no pyproject.toml)")


def list_long_references(references_dir: Path) -> list[str]:
    out: list[str] = []
    for ref_path in sorted(references_dir.glob("*.md")):
        line_count = sum(1 for _ in ref_path.open(encoding="utf-8"))
        if line_count > LONG_REFERENCE_THRESHOLD:
            out.append(ref_path.name)
    return out


def parse_envelope(path: Path) -> EnvelopeRecord | None:
    m = ENVELOPE_RE.match(path.name)
    if not m:
        return None
    text = path.read_text(encoding="utf-8")
    cited = tuple(sorted(set(f"{n}.md" for n in REFERENCE_TOKEN.findall(text))))
    return EnvelopeRecord(
        path=path,
        from_layer=m.group("from"),
        to_layer=m.group("to"),
        change_id=m.group("change_id"),
        seq=int(m.group("seq")),
        cited_references=cited,
    )


def scan_envelopes(handoff_dir: Path) -> list[EnvelopeRecord]:
    if not handoff_dir.is_dir():
        return []
    out: list[EnvelopeRecord] = []
    for child in sorted(handoff_dir.glob("*.yaml")):
        record = parse_envelope(child)
        if record is not None:
            out.append(record)
    return out


def scan_research_dir(research_dir: Path, long_refs: list[str]) -> dict[str, int]:
    if not research_dir.is_dir():
        return {ref: 0 for ref in long_refs}
    counter: Counter[str] = Counter({ref: 0 for ref in long_refs})
    for path in research_dir.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in REFERENCE_TOKEN.finditer(text):
            target = match.group(1) + ".md"
            if target in counter:
                counter[target] += 1
    return dict(counter)


def build_report(*, repo_root: Path) -> LongRefReport:
    references_dir = repo_root / "workflow-system/agent/references"
    handoff_dir = repo_root / ".local/.agent/handoff"
    archive_dir = repo_root / ".local/.agent/archive"
    research_dir = repo_root / ".local/research"
    long_refs = list_long_references(references_dir)
    envelopes = scan_envelopes(handoff_dir)
    citation_counter: Counter[str] = Counter({ref: 0 for ref in long_refs})
    for env in envelopes:
        for ref in env.cited_references:
            if ref in citation_counter:
                citation_counter[ref] += 1
    research_citations = scan_research_dir(research_dir, long_refs)
    archive_count = (
        sum(1 for c in archive_dir.iterdir() if c.is_dir()) if archive_dir.is_dir() else 0
    )
    return LongRefReport(
        long_references=tuple(long_refs),
        handoff_dir=handoff_dir,
        archive_dir=archive_dir,
        envelopes=tuple(envelopes),
        citations=dict(citation_counter),
        research_citations=research_citations,
        archive_count=archive_count,
    )


def render_markdown(report: LongRefReport) -> str:
    lines: list[str] = []
    lines.append("# Long-Reference Usage Evidence")
    lines.append("")
    lines.append(
        f"- Long references (>{LONG_REFERENCE_THRESHOLD} lines): **{len(report.long_references)}**"
    )
    lines.append(f"- Handoff envelopes scanned: **{len(report.envelopes)}**")
    lines.append(f"- Archive folders: **{report.archive_count}**")
    lines.append("")
    lines.append("## Per-long-reference citation counts")
    lines.append("")
    lines.append(
        "| Reference | Cited by handoff envelopes | Cited under .local/research/ | Disposition |"
    )
    lines.append("|---|---:|---:|---|")
    for ref in report.long_references:
        env_cites = report.citations.get(ref, 0)
        res_cites = report.research_citations.get(ref, 0)
        if env_cites + res_cites == 0:
            disp = "DOWNGRADE candidate (zero observed citations)"
        elif env_cites > 0:
            disp = "KEEP — used in handoff chain"
        else:
            disp = "OPT-IN — research-only signal"
        lines.append(f"| `references/{ref}` | {env_cites} | {res_cites} | {disp} |")
    lines.append("")
    lines.append("## Envelope ledger")
    lines.append("")
    if not report.envelopes:
        lines.append("_No envelopes found in `.local/.agent/handoff/`._")
    else:
        lines.append("| File | from → to | Change ID | Seq | Cited references |")
        lines.append("|---|---|---|---:|---|")
        for env in report.envelopes:
            cited = ", ".join(env.cited_references) if env.cited_references else "—"
            lines.append(
                f"| `{env.path.name}` | {env.from_layer} → {env.to_layer} | "
                f"`{env.change_id}` | {env.seq} | {cited} |"
            )
    lines.append("")
    lines.append("## SKILL.md annotation suggestion")
    lines.append("")
    lines.append(
        "> Long references (>500 lines) are most-relevant for **complex / "
        "change-driven workflows only**. Standard / hotfix dispatches need "
        "not load them. Per D-D-2 audit (this report)."
    )
    lines.append("")
    return "\n".join(lines)


def render_json(report: LongRefReport) -> str:
    return json.dumps(
        {
            "long_references": list(report.long_references),
            "handoff_dir": str(report.handoff_dir),
            "archive_dir": str(report.archive_dir),
            "envelope_count": len(report.envelopes),
            "envelopes": [
                {
                    "name": e.path.name,
                    "from": e.from_layer,
                    "to": e.to_layer,
                    "change_id": e.change_id,
                    "seq": e.seq,
                    "cited_references": list(e.cited_references),
                }
                for e in report.envelopes
            ],
            "citations": report.citations,
            "research_citations": report.research_citations,
            "archive_count": report.archive_count,
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root or resolve_repo_root()
    report = build_report(repo_root=repo_root)
    body = render_json(report) if args.json else render_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
        print(f"[audit] wrote {args.output}")
    else:
        sys.stdout.write(body)
        if not body.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
