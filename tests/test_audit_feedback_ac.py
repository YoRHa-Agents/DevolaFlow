"""Unit tests for ``scripts/audit_feedback_ac.py`` (DevolaFlow v10.0.0 PV-02).

Covers the public surface of the audit script:
- artifact extraction (file paths, symbols, env flags, version refs)
- AC item counting (numbered lists + severity-tagged rows)
- CHANGELOG closure lookup
- verdict classification matrix (PASS / SUPERSEDED / DEGRADED / DEFERRED / FAIL)
- end-to-end audit on the live ``.local/feedbacks/`` corpus

The S-3 / CP-2 80% coverage floor is met by exercising every classification
branch + the prose extractors via small, focused fixtures.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit_feedback_ac.py"


def _load_script_module():
    """Import the audit script as a module without invoking ``main()``.

    We must register in ``sys.modules`` BEFORE ``exec_module()`` because the
    script defines dataclasses, and ``dataclass`` resolves field annotations
    via ``sys.modules.get(cls.__module__).__dict__``.
    """
    spec = importlib.util.spec_from_file_location("audit_feedback_ac", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_feedback_ac"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def aud():
    return _load_script_module()


def test_script_exists():
    assert SCRIPT_PATH.is_file(), "scripts/audit_feedback_ac.py must exist for v10.0.0 PV-02"


def test_extract_file_paths_anchored_to_repo_dirs(aud):
    text = "See `src/devolaflow/__init__.py` and `workflow-system/agent/SKILL.md`."
    artifacts = aud._extract_artifacts(text)
    assert "src/devolaflow/__init__.py" in artifacts["file_paths"]
    assert "workflow-system/agent/SKILL.md" in artifacts["file_paths"]


def test_extract_file_paths_filters_unanchored_chatter(aud):
    text = "random.txt and foo.py without any directory prefix."
    artifacts = aud._extract_artifacts(text)
    assert "random.txt" not in artifacts["file_paths"]
    assert "foo.py" not in artifacts["file_paths"]


def test_extract_symbols(aud):
    text = "Call `dispatch_wave_tasks` and `AsyncDispatchExecutor` to coordinate."
    artifacts = aud._extract_artifacts(text)
    assert "dispatch_wave_tasks" in artifacts["symbols"]
    assert "AsyncDispatchExecutor" in artifacts["symbols"]


def test_extract_env_flags(aud):
    text = "Set DEVOLAFLOW_WARMUP=1 or DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1."
    artifacts = aud._extract_artifacts(text)
    assert "DEVOLAFLOW_WARMUP" in artifacts["env_flags"]
    assert "DEVOLAFLOW_AUTO_INSTALL_PLUGINS" in artifacts["env_flags"]


def test_extract_version_refs(aud):
    text = "Tagged in v9.7.0 and superseded by 10.0.0."
    artifacts = aud._extract_artifacts(text)
    assert "9.7.0" in artifacts["versions"]
    assert "10.0.0" in artifacts["versions"]


def test_count_ac_items_numbered_list(aud):
    text = "1. First item that is reasonably long\n2. Second item that is also long\n"
    assert aud._count_ac_items(text) == 2


def test_count_ac_items_severity_table(aud):
    text = "| 1 | foo | blocker | bar |\n| 2 | baz | critical | qux |\n"
    assert aud._count_ac_items(text) == 2


def test_count_ac_items_pure_prose_one(aud):
    text = "This is just prose feedback with no enumeration."
    assert aud._count_ac_items(text) == 1


def test_severity_tally(aud):
    text = "blocker critical critical major minor minor minor info positive"
    counts = aud._severity_tally(text)
    assert counts["blocker"] == 1
    assert counts["critical"] == 2
    assert counts["minor"] == 3


def test_parse_version_from_filename_feedback_for_v(aud, tmp_path):
    p = tmp_path / "feedback_for_v7.7.0.md"
    p.write_text("x")
    assert aud._parse_version_from_filename(p) == "7.7.0"


def test_parse_version_from_filename_evobench(aud, tmp_path):
    p = tmp_path / "eb070_for_devola_v3.4.0.md"
    p.write_text("x")
    assert aud._parse_version_from_filename(p) == "3.4.0"


def test_parse_version_from_filename_non_versioned(aud, tmp_path):
    p = tmp_path / "feedback_for_skill.md"
    p.write_text("x")
    assert aud._parse_version_from_filename(p) == "skill"


def test_parse_major_semver(aud):
    assert aud._parse_major("9.7.0") == 9
    assert aud._parse_major("10.0.0") == 10
    assert aud._parse_major("0") == 0
    assert aud._parse_major("skill") is None


def test_later_changelog_entries_finds_closure(aud):
    cl = "## [10.0.0] — 2026-05-02\n## [9.7.0] — 2026-05-02\n## [9.6.0] — 2026-05-02\n"
    closures = aud._later_changelog_entries("9.6.0", cl)
    assert "10.0.0" in closures
    assert "9.7.0" in closures
    assert "9.6.0" in closures


def test_later_changelog_entries_no_closure(aud):
    cl = "## [10.0.0] — 2026-05-02\n"
    closures = aud._later_changelog_entries("11.0.0", cl)
    assert closures == []


def test_classify_deferred(aud):
    a = aud.FeedbackAudit(
        path=Path("test.md"),
        feedback_version="9.2.4",
        raw_size_bytes=100,
        ac_item_count=1,
    )
    verdict = aud._classify(a, current_cycle_versions={"9.2.4"})
    assert verdict == "DEFERRED"


def test_classify_pass_modern_with_full_coverage(aud):
    a = aud.FeedbackAudit(
        path=Path("test.md"),
        feedback_version="9.0.0",
        raw_size_bytes=100,
        ac_item_count=1,
        file_paths_referenced=["src/x.py"],
        file_paths_present=["src/x.py"],
        symbols_referenced=["foo"],
        symbols_with_grep_hits=["foo"],
        later_changelog_entries=["9.7.0"],
    )
    assert aud._classify(a, current_cycle_versions=set()) == "PASS"


def test_classify_superseded_old_no_artifacts(aud):
    a = aud.FeedbackAudit(
        path=Path("test.md"),
        feedback_version="3.0.0",
        raw_size_bytes=100,
        ac_item_count=1,
        later_changelog_entries=["9.7.0"],
    )
    assert aud._classify(a, current_cycle_versions=set()) == "SUPERSEDED"


def test_classify_superseded_old_with_artifacts(aud):
    a = aud.FeedbackAudit(
        path=Path("test.md"),
        feedback_version="3.0.0",
        raw_size_bytes=100,
        ac_item_count=1,
        file_paths_referenced=["src/x.py"],
        file_paths_present=["src/x.py"],
        later_changelog_entries=["9.7.0"],
    )
    assert aud._classify(a, current_cycle_versions=set()) == "SUPERSEDED"


def test_classify_superseded_non_versioned_strong_symbol_survival(aud):
    a = aud.FeedbackAudit(
        path=Path("integration.md"),
        feedback_version="integration_feedback",
        raw_size_bytes=1000,
        ac_item_count=4,
        symbols_referenced=["NineS", "MAPIM", "EvoBench", "DevolaFlow", "vertex"],
        symbols_with_grep_hits=["NineS", "MAPIM", "EvoBench", "DevolaFlow"],
    )
    assert aud._classify(a, current_cycle_versions=set()) == "SUPERSEDED"


def test_classify_degraded_modern_partial(aud):
    # 50% files, 50% symbols → both ratios ≥0.5, so PASS not DEGRADED.  Test
    # the genuinely partial case: 1/3 files (33% < 50%), 2/2 symbols → DEGRADED.
    a2 = aud.FeedbackAudit(
        path=Path("test.md"),
        feedback_version="9.0.0",
        raw_size_bytes=100,
        ac_item_count=1,
        file_paths_referenced=["src/x.py", "src/y.py", "src/z.py"],
        file_paths_present=["src/x.py"],
        symbols_referenced=["foo", "bar"],
        symbols_with_grep_hits=["foo", "bar"],
        later_changelog_entries=["9.7.0"],
    )
    # 1/3 files = 33% (file_ok=False), 2/2 symbols (symbol_ok=True) → DEGRADED
    assert aud._classify(a2, current_cycle_versions=set()) == "DEGRADED"


def test_classify_fail_modern_no_closure_no_files(aud):
    a = aud.FeedbackAudit(
        path=Path("test.md"),
        feedback_version="11.0.0",  # version > MAX
        raw_size_bytes=100,
        ac_item_count=1,
        file_paths_referenced=["src/missing.py"],
        file_paths_present=[],
        later_changelog_entries=[],  # no closure
    )
    assert aud._classify(a, current_cycle_versions=set()) == "FAIL"


def test_check_path_existing(aud):
    assert aud._check_path("README.md", REPO_ROOT)


def test_check_path_with_line_suffix(aud):
    assert aud._check_path("README.md:1-5", REPO_ROOT)


def test_check_path_nonexistent(aud):
    assert not aud._check_path("does/not/exist.py", REPO_ROOT)


def test_grep_symbol_finds_hit(aud):
    # __version__ is canonical and lives in src/devolaflow/__init__.py.
    assert aud._grep_symbol("__version__", REPO_ROOT)


def test_grep_symbol_no_hit(aud):
    # Construct the needle by concatenation so the test file itself doesn't
    # contain it as a contiguous string (which would otherwise grep-hit).
    parts = ["qweRTY", "zxcv__", "N0_match_", "NEVER__", "plzdoNT_", "appearXYZ", "QQQ"]
    needle = "".join(parts)
    assert not aud._grep_symbol(needle, REPO_ROOT)


def test_end_to_end_audit_on_live_corpus(aud):
    """Run the audit against the real .local/feedbacks/ tree."""
    feedbacks_dir = REPO_ROOT / ".local" / "feedbacks"
    if not feedbacks_dir.is_dir():
        pytest.skip("Live feedbacks corpus not present in this checkout")
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    files = sorted(feedbacks_dir.glob("feedback_for_*.md"))
    eb_dir = feedbacks_dir / "from_evobench"
    if eb_dir.is_dir():
        files.extend(sorted(eb_dir.glob("*_for_devola_v*.md")))

    audits = [
        aud.audit_feedback(p, REPO_ROOT, changelog, {"9.2.4"}) for p in files[:5]
    ]  # sample 5 files for speed
    assert len(audits) >= 5
    assert all(a.verdict in {"PASS", "SUPERSEDED", "DEGRADED", "DEFERRED", "FAIL"} for a in audits)
    # The first 5 alphabetic feedbacks include EvoBench v2.x — should not FAIL.
    assert all(a.verdict != "FAIL" for a in audits)


def test_main_default_writes_report_and_exits_zero(aud, tmp_path, monkeypatch):
    """Run main() against the live corpus, write to a tmp output, expect exit 0."""
    out = tmp_path / "report.md"
    rc = aud.main(
        [
            "--feedbacks-dir",
            str(REPO_ROOT / ".local" / "feedbacks"),
            "--changelog",
            str(REPO_ROOT / "CHANGELOG.md"),
            "--output",
            str(out),
            "--current-version",
            "10.0.0",
            "--cycle-versions",
            "9.2.4",
        ]
    )
    assert rc == 0
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert "v10.0.0" in content
    assert "Verdict ledger" in content
    assert "Methodology notes" in content


def test_main_json_mode(aud, capsys):
    """JSON mode should print parseable JSON to stdout."""
    import json as _json

    rc = aud.main(
        [
            "--feedbacks-dir",
            str(REPO_ROOT / ".local" / "feedbacks"),
            "--changelog",
            str(REPO_ROOT / "CHANGELOG.md"),
            "--json",
            "--cycle-versions",
            "9.2.4",
        ]
    )
    captured = capsys.readouterr()
    payload = _json.loads(captured.out)
    assert payload["total"] >= 40, "PV-02 AC#1 — must scan ≥40 feedback files"
    assert "by_verdict" in payload
    assert payload["fail_count"] == 0, (
        "v10.0.0 PV-02: zero AC regressions allowed at MAJOR cycle close — "
        f"got {payload['fail_count']} FAILs"
    )
    assert rc == 0
