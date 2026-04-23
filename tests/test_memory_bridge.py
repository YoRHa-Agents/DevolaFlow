"""Tests for :mod:`devolaflow.agent_workspace.memory_bridge` (v8.2.8).

Closes ``H-006`` from ``.local/research/v8.3.0_gap_analysis.md``. Covers:

* :func:`consolidate_change_on_archive` — happy path, missing change,
  missing learnings.jsonl, dated-folder discovery, malformed JSONL.
* :func:`hydrate_change_context` — all 7 keys, oversized truncation,
  missing artifacts, STATUS.yaml parsing, owned_files parsing,
  learnings parsing.

Per Rule W-9 / SI-10 step 1 — these tests must pass at coverage ≥ 80%
on ``memory_bridge.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from devolaflow.agent_workspace import ChangeNotFoundError
from devolaflow.agent_workspace.memory_bridge import (
    TRUNCATION_SENTINEL,
    MemoryBridgeError,
    consolidate_change_on_archive,
    hydrate_change_context,
)
from devolaflow.learnings import Learning


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Append ``entries`` as JSONL rows to ``path`` (creates parent dirs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")


def _make_archive_folder(
    repo_root: Path,
    change_id: str,
    *,
    date: str = "2026-04-23",
    learnings: list[dict] | None = None,
    create_learnings_file: bool = True,
) -> Path:
    """Create ``.local/.agent/archive/<date>-<change_id>/`` and return the path.

    When ``learnings`` is provided (or ``create_learnings_file=True`` with
    no entries), writes a ``learnings.jsonl`` inside the folder.
    """
    folder = repo_root / ".local" / ".agent" / "archive" / f"{date}-{change_id}"
    folder.mkdir(parents=True, exist_ok=True)
    if learnings is not None:
        _write_jsonl(folder / "learnings.jsonl", learnings)
    elif create_learnings_file:
        (folder / "learnings.jsonl").write_text("", encoding="utf-8")
    return folder


def _make_active_folder(
    repo_root: Path,
    change_id: str,
    *,
    goal: str | None = None,
    acceptance: str | None = None,
    spec: str | None = None,
    tasks: str | None = None,
    status: dict | None = None,
    owned_files: list[str] | None = None,
    learnings: list[dict] | None = None,
) -> Path:
    """Create ``.local/.agent/active/<change_id>/`` and any provided artifacts."""
    folder = repo_root / ".local" / ".agent" / "active" / change_id
    folder.mkdir(parents=True, exist_ok=True)
    if goal is not None:
        (folder / "goal.md").write_text(goal, encoding="utf-8")
    if acceptance is not None:
        (folder / "acceptance.md").write_text(acceptance, encoding="utf-8")
    if spec is not None:
        (folder / "spec.md").write_text(spec, encoding="utf-8")
    if tasks is not None:
        (folder / "tasks.md").write_text(tasks, encoding="utf-8")
    if status is not None:
        (folder / "STATUS.yaml").write_text(yaml.safe_dump(status), encoding="utf-8")
    if owned_files is not None:
        (folder / "owned_files.txt").write_text("\n".join(owned_files) + "\n", encoding="utf-8")
    if learnings is not None:
        _write_jsonl(folder / "learnings.jsonl", learnings)
    return folder


def _learning_dict(**overrides) -> dict:
    """Return a minimal valid Learning row dict with sane defaults."""
    base = {
        "stage": "implement",
        "task_type": "impl",
        "key": "test-key",
        "insight": "test insight",
        "confidence": 0.8,
        "timestamp": "2026-04-23T00:00:00+00:00",
        "ttl_days": 90,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# consolidate_change_on_archive
# ---------------------------------------------------------------------------


class TestConsolidateChangeOnArchive:
    """v8.2.8 — :func:`consolidate_change_on_archive` archive promotion."""

    def test_loads_jsonl_and_promotes(self, tmp_path: Path, monkeypatch) -> None:
        """Archive folder with learnings.jsonl ⇒ consolidate_session called."""
        monkeypatch.chdir(tmp_path)
        _make_archive_folder(
            tmp_path,
            "add-foo",
            learnings=[
                _learning_dict(key="k1", insight="first"),
                _learning_dict(key="k2", insight="second"),
            ],
        )

        result = consolidate_change_on_archive("add-foo")

        assert isinstance(result, dict)
        assert set(result.keys()) == {"promoted", "captured", "skipped"}
        assert result["captured"] == 2, (
            f"both new entries should be captured into the empty global jsonl; got {result}"
        )
        assert result["promoted"] == 0
        assert result["skipped"] == 0
        global_p = tmp_path / ".local" / "memory" / "operational.jsonl"
        assert global_p.exists(), "global JSONL must be created"
        lines = global_p.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_missing_change_raises(self, tmp_path: Path, monkeypatch) -> None:
        """Non-existent change_id ⇒ raises ChangeNotFoundError (S-5 loud)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".local" / ".agent" / "archive").mkdir(parents=True)

        with pytest.raises(ChangeNotFoundError, match="no archive folder found"):
            consolidate_change_on_archive("does-not-exist")

    def test_missing_learnings_jsonl_returns_zero(self, tmp_path: Path, monkeypatch) -> None:
        """Archive folder exists, no learnings.jsonl ⇒ returns {0,0,0}."""
        monkeypatch.chdir(tmp_path)
        _make_archive_folder(tmp_path, "add-foo", create_learnings_file=False)

        result = consolidate_change_on_archive("add-foo")

        assert result == {"promoted": 0, "captured": 0, "skipped": 0}

    def test_finds_dated_folder(self, tmp_path: Path, monkeypatch) -> None:
        """Archive_root contains '2026-04-23-foo' ⇒ resolves change_id='foo'."""
        monkeypatch.chdir(tmp_path)
        _make_archive_folder(
            tmp_path,
            "foo",
            date="2026-04-23",
            learnings=[_learning_dict(key="k1")],
        )

        result = consolidate_change_on_archive("foo")
        assert result["captured"] == 1

    def test_promotes_existing_global_entry(self, tmp_path: Path, monkeypatch) -> None:
        """Pre-existing global entry with same triple ⇒ promoted (not captured)."""
        monkeypatch.chdir(tmp_path)
        global_p = tmp_path / ".local" / "memory" / "operational.jsonl"
        global_p.parent.mkdir(parents=True, exist_ok=True)
        _write_jsonl(
            global_p,
            [_learning_dict(key="shared", confidence=0.5)],
        )
        _make_archive_folder(
            tmp_path,
            "promote-test",
            learnings=[_learning_dict(key="shared", confidence=0.7)],
        )

        result = consolidate_change_on_archive("promote-test")

        assert result["promoted"] == 1
        assert result["captured"] == 0
        lines = global_p.read_text().strip().splitlines()
        assert len(lines) == 1, "no new entry should be appended on promote"
        entry = json.loads(lines[0])
        assert entry["promotion_count"] == 1

    def test_malformed_json_raises_loud(self, tmp_path: Path, monkeypatch) -> None:
        """Malformed JSONL ⇒ MemoryBridgeError (S-5 loud, never silent)."""
        monkeypatch.chdir(tmp_path)
        folder = _make_archive_folder(tmp_path, "bad", create_learnings_file=False)
        (folder / "learnings.jsonl").write_text(
            json.dumps(_learning_dict(key="k1")) + "\n{ NOT JSON }\n",
            encoding="utf-8",
        )

        with pytest.raises(MemoryBridgeError, match="malformed JSON"):
            consolidate_change_on_archive("bad")

    def test_explicit_archive_root_override(self, tmp_path: Path, monkeypatch) -> None:
        """Caller can override ``archive_root`` for sandboxed runs."""
        monkeypatch.chdir(tmp_path)
        custom_archive = tmp_path / "custom" / "archive"
        custom_archive.mkdir(parents=True)
        folder = custom_archive / "2026-04-23-x"
        folder.mkdir()
        _write_jsonl(folder / "learnings.jsonl", [_learning_dict(key="k1")])
        custom_global = tmp_path / "custom" / "ops.jsonl"

        result = consolidate_change_on_archive(
            "x", archive_root=custom_archive, global_jsonl=custom_global
        )

        assert result["captured"] == 1
        assert custom_global.exists()


# ---------------------------------------------------------------------------
# hydrate_change_context
# ---------------------------------------------------------------------------


class TestHydrateChangeContext:
    """v8.2.8 — :func:`hydrate_change_context` artifact loader."""

    def test_returns_seven_keys(self, tmp_path: Path, monkeypatch) -> None:
        """Change with all 7 artifacts ⇒ dict with all 7 keys present."""
        monkeypatch.chdir(tmp_path)
        _make_active_folder(
            tmp_path,
            "add-foo",
            goal="# Goal\nDo X",
            acceptance="# Acceptance\nIt does X",
            spec="# Spec\nDetails",
            tasks="# Tasks\n- T1",
            status={"state": "IN_PROGRESS", "last_updated": "2026-04-23T00:00:00Z"},
            owned_files=["src/foo.py", "tests/test_foo.py"],
            learnings=[_learning_dict(key="k1")],
        )

        result = hydrate_change_context("add-foo")

        expected = {
            "goal",
            "acceptance",
            "spec",
            "tasks",
            "status",
            "owned_files",
            "learnings",
        }
        assert set(result.keys()) == expected, (
            f"hydrate must return exactly the 7 canonical keys; got {set(result.keys())}"
        )

    def test_truncates_oversized_artifacts(self, tmp_path: Path, monkeypatch) -> None:
        """spec.md > 3000 tokens ⇒ truncated with sentinel."""
        monkeypatch.chdir(tmp_path)
        # 3000 tokens ≈ 12000 chars; build something well over.
        oversized = "x" * 20000
        _make_active_folder(
            tmp_path,
            "fat",
            spec=oversized,
            status={"state": "IN_PROGRESS"},
        )

        result = hydrate_change_context("fat")

        assert result["spec"] is not None
        assert TRUNCATION_SENTINEL in result["spec"], (
            f"oversized spec.md must carry the truncation sentinel ({TRUNCATION_SENTINEL!r})"
        )
        # Capped to ~spec budget chars (3000 * 4 = 12000); allow small slack.
        assert len(result["spec"]) <= 12000 + len(TRUNCATION_SENTINEL) + 2

    def test_handles_missing_artifacts(self, tmp_path: Path, monkeypatch) -> None:
        """Change with only goal.md ⇒ other md keys None, list keys empty."""
        monkeypatch.chdir(tmp_path)
        _make_active_folder(
            tmp_path,
            "skinny",
            goal="# Goal only",
            status={"state": "PROPOSED"},
        )

        result = hydrate_change_context("skinny")

        assert result["goal"] == "# Goal only"
        assert result["acceptance"] is None
        assert result["spec"] is None
        assert result["tasks"] is None
        assert result["status"] == {"state": "PROPOSED"}
        assert result["owned_files"] == []
        assert result["learnings"] == []

    def test_parses_status_yaml(self, tmp_path: Path, monkeypatch) -> None:
        """STATUS.yaml ⇒ returns dict with parsed YAML mapping."""
        monkeypatch.chdir(tmp_path)
        status = {
            "state": "VERIFYING",
            "last_updated": "2026-04-23T12:34:56Z",
            "percent_complete": 90,
            "last_handoff_seq": 7,
        }
        _make_active_folder(tmp_path, "status-test", status=status)

        result = hydrate_change_context("status-test")

        assert result["status"]["state"] == "VERIFYING"
        assert result["status"]["last_updated"] == "2026-04-23T12:34:56Z"
        assert result["status"]["percent_complete"] == 90
        assert result["status"]["last_handoff_seq"] == 7

    def test_parses_owned_files(self, tmp_path: Path, monkeypatch) -> None:
        """owned_files.txt ⇒ returns list[str] (one path per line, no blanks)."""
        monkeypatch.chdir(tmp_path)
        _make_active_folder(
            tmp_path,
            "owned-test",
            status={"state": "IN_PROGRESS"},
            owned_files=["src/a.py", "src/b.py", "tests/test_a.py"],
        )

        result = hydrate_change_context("owned-test")

        assert result["owned_files"] == [
            "src/a.py",
            "src/b.py",
            "tests/test_a.py",
        ]

    def test_parses_learnings_jsonl(self, tmp_path: Path, monkeypatch) -> None:
        """learnings.jsonl with 3 entries ⇒ returns list of 3 Learning instances."""
        monkeypatch.chdir(tmp_path)
        _make_active_folder(
            tmp_path,
            "learn-test",
            status={"state": "IN_PROGRESS"},
            learnings=[
                _learning_dict(key="k1", insight="first"),
                _learning_dict(key="k2", insight="second"),
                _learning_dict(key="k3", insight="third"),
            ],
        )

        result = hydrate_change_context("learn-test")

        assert len(result["learnings"]) == 3
        assert all(isinstance(item, Learning) for item in result["learnings"])
        assert {item.key for item in result["learnings"]} == {"k1", "k2", "k3"}
        assert {item.insight for item in result["learnings"]} == {"first", "second", "third"}

    def test_missing_change_raises(self, tmp_path: Path, monkeypatch) -> None:
        """No active folder for change_id ⇒ ChangeNotFoundError (S-5)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".local" / ".agent" / "active").mkdir(parents=True)

        with pytest.raises(ChangeNotFoundError, match="no active folder"):
            hydrate_change_context("missing")

    def test_status_truncation_marker_added_when_oversized(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Oversized STATUS.yaml ⇒ ``_truncated`` key added (YAML stays parseable)."""
        monkeypatch.chdir(tmp_path)
        # 200 token budget = ~800 chars. Build a YAML well over budget but
        # still parseable.
        big_status = {
            "state": "IN_PROGRESS",
            "notes": "x" * 1500,
        }
        _make_active_folder(tmp_path, "big-status", status=big_status)

        result = hydrate_change_context("big-status")

        assert "_truncated" in result["status"]
        assert result["status"]["_truncated"] == TRUNCATION_SENTINEL
        assert result["status"]["state"] == "IN_PROGRESS"

    def test_owned_files_truncation_appends_sentinel(self, tmp_path: Path, monkeypatch) -> None:
        """Oversized owned_files.txt ⇒ truncated list ends with sentinel entry."""
        monkeypatch.chdir(tmp_path)
        # 100 token budget = ~400 chars. ~30 paths of ~20 chars = ~600 chars.
        many_files = [f"src/very_long_module_name_{i:03d}.py" for i in range(30)]
        _make_active_folder(
            tmp_path,
            "many-owned",
            status={"state": "IN_PROGRESS"},
            owned_files=many_files,
        )

        result = hydrate_change_context("many-owned")

        assert result["owned_files"][-1] == TRUNCATION_SENTINEL
        assert len(result["owned_files"]) < len(many_files) + 1, (
            "truncated list should be shorter than original + sentinel"
        )

    def test_explicit_active_root_override(self, tmp_path: Path, monkeypatch) -> None:
        """Caller can override ``active_root`` for sandboxed runs."""
        monkeypatch.chdir(tmp_path)
        custom = tmp_path / "custom-active"
        custom.mkdir()
        folder = custom / "x"
        folder.mkdir()
        (folder / "goal.md").write_text("# Custom goal", encoding="utf-8")
        (folder / "STATUS.yaml").write_text(yaml.safe_dump({"state": "PROPOSED"}), encoding="utf-8")

        result = hydrate_change_context("x", active_root=custom)

        assert result["goal"] == "# Custom goal"
        assert result["status"]["state"] == "PROPOSED"

    def test_learnings_skips_malformed_lines_silently(self, tmp_path: Path, monkeypatch) -> None:
        """Hydrate is read-side; malformed JSONL lines are skipped, not raised.

        Loud-on-malformed is reserved for :func:`consolidate_change_on_archive`
        — hydrate prefers a partial list over a crash so the consumer (an
        agent context injector) still gets useful context.
        """
        monkeypatch.chdir(tmp_path)
        folder = _make_active_folder(
            tmp_path,
            "malformed-learn",
            status={"state": "IN_PROGRESS"},
        )
        (folder / "learnings.jsonl").write_text(
            json.dumps(_learning_dict(key="k1"))
            + "\n{ broken }\n"
            + json.dumps(_learning_dict(key="k2"))
            + "\n",
            encoding="utf-8",
        )

        result = hydrate_change_context("malformed-learn")

        assert len(result["learnings"]) == 2
        assert {item.key for item in result["learnings"]} == {"k1", "k2"}

    def test_learnings_skips_entries_missing_required_fields(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Entries missing stage/task_type/key are dropped (matches archive.py)."""
        monkeypatch.chdir(tmp_path)
        folder = _make_active_folder(
            tmp_path,
            "incomplete",
            status={"state": "IN_PROGRESS"},
        )
        (folder / "learnings.jsonl").write_text(
            json.dumps({"stage": "x", "key": "k1"})
            + "\n"  # missing task_type
            + json.dumps(_learning_dict(key="good"))
            + "\n",
            encoding="utf-8",
        )

        result = hydrate_change_context("incomplete")

        assert len(result["learnings"]) == 1
        assert result["learnings"][0].key == "good"
