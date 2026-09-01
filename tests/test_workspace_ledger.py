"""v24.0.0 — shared append-only ledger and generated-view primitives."""

from __future__ import annotations

import pytest

from devolaflow.workspace_ledger import (
    LedgerError,
    append_ledger_row,
    detect_view_drift,
    has_symlink_component,
    load_ledger_rows,
    relative_path,
    sha256_bytes,
    sha256_path,
    utc_now,
    write_generated_view,
)

MARKER = "<!-- devolaflow: test marker -->"


@pytest.mark.parametrize(
    ("value", "expect_finding"),
    [
        ("a/b.md", False),
        ("./a/b.md", False),
        ("/etc/passwd", True),
        ("../outside.md", True),
    ],
)
def test_relative_path_refuses_absolute_and_traversal(tmp_path, value, expect_finding):
    resolved, finding = relative_path(tmp_path, value)
    assert (finding is not None) is expect_finding
    if not expect_finding:
        assert resolved is not None


def test_symlink_component_is_detected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    assert has_symlink_component(tmp_path, link / "child.md") is True
    assert has_symlink_component(tmp_path, real / "child.md") is False


def test_append_assigns_sequences_and_never_rewrites(tmp_path):
    ledger = tmp_path / "ledger.yaml"
    first = append_ledger_row(ledger, {"event": "a"}, required_fields=("event",))
    second = append_ledger_row(ledger, {"event": "b"}, required_fields=("event",))
    assert (first["sequence"], second["sequence"]) == (1, 2)
    rows = load_ledger_rows(ledger, required_fields=("sequence", "event"))
    assert [row["event"] for row in rows] == ["a", "b"]
    # The first row's bytes are still present verbatim after the second append.
    assert "event: a" in ledger.read_text(encoding="utf-8")


def test_append_refuses_duplicate_unique_field(tmp_path):
    ledger = tmp_path / "ledger.yaml"
    append_ledger_row(ledger, {"source": "x"}, unique_fields=("source",))
    with pytest.raises(LedgerError, match="refusing duplicate"):
        append_ledger_row(ledger, {"source": "x"}, unique_fields=("source",))


def test_append_refuses_missing_required_field(tmp_path):
    with pytest.raises(LedgerError, match="missing required fields"):
        append_ledger_row(tmp_path / "ledger.yaml", {"a": 1}, required_fields=("b",))


def test_load_rejects_malformed_ledger(tmp_path):
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(LedgerError):
        load_ledger_rows(ledger)


def test_generated_view_refuses_human_authored_file(tmp_path):
    target = tmp_path / "INDEX.md"
    target.write_text("# hand written\n", encoding="utf-8")
    findings = write_generated_view(tmp_path, target, f"{MARKER}\nbody\n", marker=MARKER)
    assert [item.code for item in findings] == ["HUMAN_VIEW"]
    assert target.read_text(encoding="utf-8") == "# hand written\n"


def test_generated_view_writes_and_detects_drift(tmp_path):
    target = tmp_path / "INDEX.md"
    content = f"{MARKER}\nbody\n"
    assert write_generated_view(tmp_path, target, content, marker=MARKER) == ()
    assert detect_view_drift(tmp_path, target, content, marker=MARKER) == ()
    target.write_text(f"{MARKER}\ntampered\n", encoding="utf-8")
    assert [item.code for item in detect_view_drift(tmp_path, target, content, marker=MARKER)] == [
        "VIEW_DRIFT"
    ]


def test_generated_content_must_carry_its_marker(tmp_path):
    with pytest.raises(LedgerError, match="surface marker"):
        write_generated_view(tmp_path, tmp_path / "x.md", "no marker\n", marker=MARKER)


def test_directory_hash_covers_paths_and_content(tmp_path):
    folder = tmp_path / "d"
    (folder / "sub").mkdir(parents=True)
    (folder / "sub" / "a.txt").write_text("alpha", encoding="utf-8")
    before = sha256_path(folder)
    (folder / "sub" / "a.txt").write_text("beta", encoding="utf-8")
    assert sha256_path(folder) != before
    assert sha256_path(folder / "sub" / "a.txt") == sha256_bytes(b"beta")


def test_utc_now_uses_the_canonical_format():
    assert utc_now().endswith("Z")
    assert len(utc_now()) == 20
