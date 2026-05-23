"""Structural assertions for ``workflow-system/agent/references/codegraph.md``.

Pins the v12.5.0 PV-05 D-1.3 codegraph reference doc contract documented at
``.local/research/v12.5.0_codegraph_benefit_analysis.md`` §6.3:

* File exists at the canonical path under ``workflow-system/agent/references/``
* Line count under the C-4 Large-tier ceiling (≤ 1000)
* Required §1-§6 anchor headings present (verbatim substring match)
* Banner-mode external URL referenced verbatim per S-7

NO subprocess. NO network. Pure file-content assertions.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
_DOC_PATH: Path = _REPO_ROOT / "workflow-system" / "agent" / "references" / "codegraph.md"


def test_codegraph_reference_doc_exists() -> None:
    """The reference doc lives at the canonical path."""
    assert _DOC_PATH.is_file(), (
        f"v12.5.0 PV-05 D-1.3 violation: {_DOC_PATH} missing — "
        "release blocker. The reference doc is the canonical L3 "
        "navigation surface for the codegraph integration."
    )


def test_codegraph_reference_doc_line_budget() -> None:
    """The doc fits within the C-4 Large-tier ceiling (≤ 1000 lines)."""
    lines = _DOC_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 1000, (
        f"v12.5.0 PV-05 D-1.3 violation: {_DOC_PATH} has {len(lines)} "
        "lines, exceeds C-4 Large-tier ceiling 1000. Trim or re-tier."
    )


def test_codegraph_reference_doc_has_six_canonical_sections() -> None:
    """§1-§6 anchor headings present per cycle plan §PV-05 deliverable list."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    expected_anchors = (
        "## §1 — What codegraph is",
        "## §2 — The 9 MCP tools",
        "## §3 — CLI surface",
        "## §4 — DevolaFlow integration map",
        "## §5 — Degraded-mode contract",
        "## §6 — Cache management",
    )
    missing = [a for a in expected_anchors if a not in text]
    assert not missing, (
        f"v12.5.0 PV-05 D-1.3 violation: {_DOC_PATH} missing §-anchor "
        f"headings: {missing}. The 6-section structure is the v12.5.0 "
        "PV-05 D-1.3 acceptance criterion."
    )


def test_codegraph_reference_doc_cites_canonical_external_url() -> None:
    """The doc cites the codegraph upstream URL verbatim per S-7."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    assert "https://github.com/colbymchenry/codegraph" in text, (
        f"v12.5.0 PV-05 D-1.3 violation: {_DOC_PATH} missing the "
        "canonical upstream URL `https://github.com/colbymchenry/codegraph`. "
        "Per S-7 every external resource MUST be referenced by its "
        "remote GitHub URL."
    )


def test_codegraph_reference_doc_cites_npm_package() -> None:
    """The doc cites the npm package name verbatim."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    assert "@colbymchenry/codegraph" in text, (
        f"v12.5.0 PV-05 D-1.3 violation: {_DOC_PATH} missing the npm "
        "package name `@colbymchenry/codegraph`. Operators rely on the "
        "verbatim package identifier for `npm install` invocation."
    )


def test_codegraph_reference_doc_cites_upstream_benchmark_metrics() -> None:
    """The doc cites the verbatim upstream benchmark metrics per CO-2 / C-3."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    for metric in ("35%", "70%", "59%", "49%"):
        assert metric in text, (
            f"v12.5.0 PV-05 D-1.3 violation: {_DOC_PATH} missing "
            f"upstream benchmark metric {metric!r}. Per CO-2 / C-3 "
            "verbatim extraction discipline, the 4 published metrics "
            "(35% cheaper / 70% fewer tool calls / 59% fewer tokens / "
            "49% faster) MUST appear verbatim."
        )
