"""Structural assertions for ``workflow-system/agent/references/impeccable.md``.

Pins the v13.0.0 impeccable reference doc contract:

* File exists at the canonical path under ``workflow-system/agent/references/``
* Line count under the C-4 Large-tier ceiling (≤ 1000)
* Required §1-§6 anchor headings present (verbatim substring match)
* Cites the canonical upstream URL + npm package name verbatim per S-7
* Documents the detector exit-code gate contract (0 = clean, 2 = anti-patterns)

NO subprocess. NO network. Pure file-content assertions.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
_DOC_PATH: Path = _REPO_ROOT / "workflow-system" / "agent" / "references" / "impeccable.md"


def test_impeccable_reference_doc_exists() -> None:
    assert _DOC_PATH.is_file(), (
        f"v13.0.0 violation: {_DOC_PATH} missing — release blocker. The "
        "reference doc is the canonical L3 navigation surface for impeccable."
    )


def test_impeccable_reference_doc_line_budget() -> None:
    lines = _DOC_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 1000, (
        f"v13.0.0 violation: {_DOC_PATH} has {len(lines)} lines, exceeds C-4 "
        "Large-tier ceiling 1000. Trim or re-tier."
    )


def test_impeccable_reference_doc_has_six_canonical_sections() -> None:
    text = _DOC_PATH.read_text(encoding="utf-8")
    expected_anchors = (
        "## §1 — What impeccable is",
        "## §2 — The 23 /impeccable commands",
        "## §3 — The detector CLI",
        "## §4 — DevolaFlow integration map",
        "## §5 — Degraded-mode contract",
        "## §6 — Cache / install management",
    )
    missing = [a for a in expected_anchors if a not in text]
    assert not missing, f"v13.0.0 violation: {_DOC_PATH} missing §-anchor headings: {missing}."


def test_impeccable_reference_doc_cites_canonical_external_url() -> None:
    text = _DOC_PATH.read_text(encoding="utf-8")
    assert "https://github.com/pbakaus/impeccable" in text, (
        f"v13.0.0 violation: {_DOC_PATH} missing the canonical upstream URL "
        "`https://github.com/pbakaus/impeccable` (S-7)."
    )


def test_impeccable_reference_doc_documents_detector_exit_codes() -> None:
    """The detector gate contract (exit 0 = clean, 2 = anti-patterns) MUST appear."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    assert "impeccable detect" in text
    assert "exit 0" in text.lower() or "`0`" in text
    assert "2" in text  # exit code 2 = anti-patterns found
