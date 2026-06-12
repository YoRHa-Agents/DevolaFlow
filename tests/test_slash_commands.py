"""Tests for the v9.1.2 PV-02 ``/devola:*`` slash commands.

Pins the public CLI contract of
:mod:`devolaflow.skills.slash_commands`:

1. ``propose <topic>`` slugifies + scaffolds a 7-artifact folder.
2. ``apply <change-id>`` flips STATUS.yaml ``state`` to ``IN_PROGRESS``.
3. ``verify <change-id>`` invokes pytest on owned tests + flips to
   ``VERIFYING`` on success (FSM canonical name; the cycle plan
   §PV-02 uses ``VERIFIED`` as a prose alias).
4. ``archive <change-id>`` refuses unless gate passes
   (``state == VERIFYING`` AND ``gate_score >= 8.5``).
5. The happy archive path moves the folder under
   ``.local/.agent/archive/<YYYY-MM-DD>-<id>/``.

All tests use ``tmp_path`` fixtures — zero network I/O, zero writes
outside the per-test scratch directory.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from devolaflow.agent_workspace import ArchiveError, ChangeStore
from devolaflow.skills.slash_commands import (
    ARCHIVE_GATE_THRESHOLD,
    REQUIRE_VERIFY_STATE,
    ProposeError,
    VerifyFailed,
    main,
    run_apply,
    run_archive,
    run_propose,
    run_verify,
    scaffold_change_folder,
    slugify,
)

# Per the cycle plan §PV-02 the propose surface writes the seven
# artifacts in this order. The first six come from
# `Change.to_active_folder` (one-shot YAML+text dump) and the seventh
# is `README.md` written separately as the operator orientation file.
# We assert all seven exist together.
_EXPECTED_ARTIFACTS: tuple[str, ...] = (
    "goal.md",
    "acceptance.md",
    "spec.md",
    "tasks.md",
    "STATUS.yaml",
    "owned_files.txt",
    "README.md",
)


# ── slugify ────────────────────────────────────────────────────────────


def test_propose_slugifies_topic(tmp_path: Path) -> None:
    """``propose 'Add Dark Mode'`` → slug ``add-dark-mode``.

    Pins the slug derivation per the cycle plan §PV-02. The resulting
    folder name MUST match the
    ``schemas/agent-workspace/change-status.yaml#fields.change_id.pattern``
    regex (lowercase kebab-case starting and ending in alphanumeric).
    """
    target = run_propose("Add Dark Mode", tmp_path)
    assert target.name == "add-dark-mode"
    assert target.parent == tmp_path / ".local" / ".agent" / "active"
    assert slugify("Add Dark Mode") == "add-dark-mode"
    assert slugify("v9.1.2 PV-02") == "v9-1-2-pv-02"
    assert slugify("  trim  me  ") == "trim-me"

    with pytest.raises(ProposeError, match="empty slug"):
        slugify("   ")


# ── propose ────────────────────────────────────────────────────────────


def test_propose_creates_change_folder(tmp_path: Path) -> None:
    """``propose foo`` creates ``active/foo/`` with all 7 artifacts.

    Pins the cycle plan §PV-02 verbatim list: goal.md, acceptance.md,
    spec.md, tasks.md, STATUS.yaml, owned_files.txt, README.md.
    Asserts STATUS.yaml carries ``state: PROPOSED`` so subsequent
    ``/devola:apply`` is the legal next FSM transition.
    """
    target = run_propose("foo", tmp_path)
    assert target.is_dir()
    assert target == tmp_path / ".local" / ".agent" / "active" / "foo"

    for name in _EXPECTED_ARTIFACTS:
        artifact = target / name
        assert artifact.is_file(), f"missing artifact: {name}"
        # owned_files.txt is intentionally empty at propose-time per the
        # cycle plan §PV-02 ("operator fills before /devola:apply"); every
        # other artifact carries placeholder text and is non-empty.
        if name != "owned_files.txt":
            assert artifact.stat().st_size > 0, f"empty artifact: {name}"

    status = yaml.safe_load((target / "STATUS.yaml").read_text(encoding="utf-8"))
    assert status["state"] == "PROPOSED"
    assert status["change_id"] == "foo"
    assert status["percent_complete"] == 0


def test_propose_no_change_opt_out_skips_scaffold(tmp_path: Path) -> None:
    """``--no-change`` is the A-6.3 escape hatch; no folder created.

    Returns the repo root unchanged so callers can detect the no-op
    via path equality without parsing stdout.
    """
    result = run_propose("foo", tmp_path, no_change=True)
    assert result == tmp_path
    assert not (tmp_path / ".local" / ".agent" / "active" / "foo").exists()


def test_propose_refuses_existing_folder(tmp_path: Path) -> None:
    """Re-propose against the same slug is a loud error per S-5.

    The operator's contract is to pass a fresh topic; silently
    overwriting an in-flight change folder would lose work and
    invalidate the FSM state.
    """
    scaffold_change_folder("foo", tmp_path)
    with pytest.raises(ProposeError, match="already exists"):
        scaffold_change_folder("foo", tmp_path)


# ── apply ──────────────────────────────────────────────────────────────


def test_apply_sets_in_progress(tmp_path: Path) -> None:
    """``/devola:apply`` flips state PROPOSED → IN_PROGRESS.

    Pins the legal FSM transition per
    ``schemas/agent-workspace/change-status.yaml#state_transitions``.
    The returned :class:`Change` carries the updated state and a
    refreshed ``last_updated`` timestamp.
    """
    scaffold_change_folder("foo", tmp_path)
    updated = run_apply("foo", tmp_path)
    assert updated.state == "IN_PROGRESS"

    # Round-trip: re-load from disk and confirm STATUS.yaml is in sync.
    store = ChangeStore(repo_root=tmp_path)
    fresh = store.get("foo")
    assert fresh.state == "IN_PROGRESS"


# ── verify ─────────────────────────────────────────────────────────────


def test_verify_runs_pytest(tmp_path: Path) -> None:
    """``/devola:verify`` invokes pytest on owned tests + flips to VERIFYING.

    Uses a stub pytest_runner so the test does not actually execute a
    pytest sub-process. Asserts (a) the runner was called with the
    correct cmd / cwd, (b) on returncode 0 the FSM advances to
    VERIFYING, (c) the change is loadable from disk.
    """
    target = scaffold_change_folder("foo", tmp_path)
    # Author a single owned test file so verify has something to target.
    owned_files_path = target / "owned_files.txt"
    owned_files_path.write_text("tests/test_foo.py\n", encoding="utf-8", newline="\n")
    # Apply first — verify requires IN_PROGRESS as the start state.
    run_apply("foo", tmp_path)

    captured: dict[str, object] = {}

    def fake_runner(cmd: list[str], cwd: Path, check: bool) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")  # type: ignore[return-value]

    updated = run_verify("foo", tmp_path, pytest_runner=fake_runner)

    assert updated.state == REQUIRE_VERIFY_STATE == "VERIFYING"
    assert captured["cwd"] == tmp_path
    assert captured["check"] is False
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert "pytest" in cmd
    assert "tests/test_foo.py" in cmd


def test_verify_pytest_failure_keeps_in_progress(tmp_path: Path) -> None:
    """Non-zero pytest exit → VerifyFailed; FSM stays in IN_PROGRESS.

    S-5 explicit error state — the operator must observe the failure
    rather than silently advancing through the FSM with broken tests.
    """
    target = scaffold_change_folder("foo", tmp_path)
    (target / "owned_files.txt").write_text("tests/test_foo.py\n", encoding="utf-8", newline="\n")
    run_apply("foo", tmp_path)

    def failing_runner(cmd: list[str], cwd: Path, check: bool) -> subprocess.CompletedProcess:
        return SimpleNamespace(returncode=1, stdout=b"", stderr=b"")  # type: ignore[return-value]

    with pytest.raises(VerifyFailed, match="returncode=1"):
        run_verify("foo", tmp_path, pytest_runner=failing_runner)

    store = ChangeStore(repo_root=tmp_path)
    assert store.get("foo").state == "IN_PROGRESS"


# ── archive ────────────────────────────────────────────────────────────


def _advance_to_verifying(repo_root: Path, change_id: str, *, gate_score: float) -> None:
    """Helper: walk the FSM PROPOSED → IN_PROGRESS → VERIFYING + set gate_score."""
    run_apply(change_id, repo_root)

    def passing_runner(cmd: list[str], cwd: Path, check: bool) -> subprocess.CompletedProcess:
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")  # type: ignore[return-value]

    run_verify(change_id, repo_root, pytest_runner=passing_runner)

    # Inject gate_score into STATUS.yaml — `archive` requires it per A-4.
    status_path = repo_root / ".local" / ".agent" / "active" / change_id / "STATUS.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    status["gate_score"] = gate_score
    status_path.write_text(
        yaml.safe_dump(status, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
        newline="\n",
    )


def test_archive_requires_gate_pass(tmp_path: Path) -> None:
    """``/devola:archive`` refuses if STATUS.yaml ``state`` != VERIFYING.

    Pins the gate per the cycle plan §PV-02:

      "archive — require gate PASS (STATUS.yaml state == VERIFIED
       AND SI-3 composite >= 8.5 cited)"

    The canonical FSM uses ``VERIFYING`` (not ``VERIFIED``); the
    slash command uses the canonical name.
    """
    scaffold_change_folder("foo", tmp_path)

    # State PROPOSED — refuses.
    with pytest.raises(ArchiveError, match="archive requires state == 'VERIFYING'"):
        run_archive("foo", tmp_path, archive_date="2026-05-01")

    # Advance to IN_PROGRESS — still refuses.
    run_apply("foo", tmp_path)
    with pytest.raises(ArchiveError, match="archive requires state == 'VERIFYING'"):
        run_archive("foo", tmp_path, archive_date="2026-05-01")


def test_archive_requires_gate_score(tmp_path: Path) -> None:
    """Archive refuses when ``gate_score`` is absent or below the W-3 floor."""
    scaffold_change_folder("foo", tmp_path)
    run_apply("foo", tmp_path)

    def passing_runner(cmd: list[str], cwd: Path, check: bool) -> subprocess.CompletedProcess:
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")  # type: ignore[return-value]

    run_verify("foo", tmp_path, pytest_runner=passing_runner)
    # State now VERIFYING but gate_score missing.
    with pytest.raises(ArchiveError, match="no gate_score in STATUS.yaml"):
        run_archive("foo", tmp_path, archive_date="2026-05-01")

    # Inject below-threshold gate_score.
    status_path = tmp_path / ".local" / ".agent" / "active" / "foo" / "STATUS.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    status["gate_score"] = 8.0
    status_path.write_text(
        yaml.safe_dump(status, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(ArchiveError, match=r"below the W-3 / SI-3 floor 8\.50"):
        run_archive("foo", tmp_path, archive_date="2026-05-01")


def test_archive_moves_to_archive_dir(tmp_path: Path) -> None:
    """Happy path: gate PASS → folder moved to ``archive/<date>-<slug>/``.

    Asserts (a) the active folder is gone, (b) the archive folder
    exists at the pinned date prefix, (c) STATUS.yaml carries
    ``state: ARCHIVED`` post-move.
    """
    scaffold_change_folder("foo", tmp_path)
    _advance_to_verifying(tmp_path, "foo", gate_score=ARCHIVE_GATE_THRESHOLD + 0.5)

    archive_path = run_archive("foo", tmp_path, archive_date="2026-05-01")

    assert archive_path == tmp_path / ".local" / ".agent" / "archive" / "2026-05-01-foo"
    assert archive_path.is_dir()
    assert not (tmp_path / ".local" / ".agent" / "active" / "foo").exists()

    archived_status = yaml.safe_load((archive_path / "STATUS.yaml").read_text(encoding="utf-8"))
    assert archived_status["state"] == "ARCHIVED"


# ── CLI surface (main entry point) ─────────────────────────────────────


def test_main_propose_exit_code_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """End-to-end: ``python -m devolaflow.skills.slash_commands propose foo`` exits 0."""
    rc = main(["--repo-root", str(tmp_path), "propose", "foo"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "/devola:propose: created" in out
    assert (tmp_path / ".local" / ".agent" / "active" / "foo").is_dir()


def test_main_propose_no_change_exit_code_zero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--no-change`` opt-out path also exits 0 with a no-op message."""
    rc = main(["--repo-root", str(tmp_path), "propose", "foo", "--no-change"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "--no-change" in out
    assert not (tmp_path / ".local" / ".agent" / "active" / "foo").exists()


def test_main_dispatches_apply_verify_archive_with_exit_codes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v15.0.0 R3: the full ``main()`` lifecycle dispatch — apply/verify/archive.

    Pins the CLI exit-code + stdout/stderr contract for the three
    post-propose subcommands (the pre-R3 suite only drove ``propose``
    through ``main()``): success lines go to stdout with exit 0;
    domain errors (VerifyFailed / ChangeStoreError) go to stderr with
    exit 1 — never a traceback.
    """
    import devolaflow.skills.slash_commands as slash_mod

    assert main(["--repo-root", str(tmp_path), "propose", "foo"]) == 0

    rc = main(["--repo-root", str(tmp_path), "apply", "foo"])
    assert rc == 0
    assert "/devola:apply: foo -> state=IN_PROGRESS" in capsys.readouterr().out

    # verify through main(): inject a passing pytest runner via the
    # documented run_verify kwarg (main itself exposes no runner knob).
    real_run_verify = slash_mod.run_verify

    def passing_runner(cmd: list[str], cwd: Path, check: bool) -> subprocess.CompletedProcess:
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")  # type: ignore[return-value]

    monkeypatch.setattr(
        slash_mod,
        "run_verify",
        lambda cid, root: real_run_verify(cid, root, pytest_runner=passing_runner),
    )
    rc = main(["--repo-root", str(tmp_path), "verify", "foo"])
    assert rc == 0
    assert "/devola:verify: foo -> state=VERIFYING" in capsys.readouterr().out

    # archive through main(): gate satisfied → folder moved, exit 0.
    status_path = tmp_path / ".local" / ".agent" / "active" / "foo" / "STATUS.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    status["gate_score"] = ARCHIVE_GATE_THRESHOLD + 0.5
    status_path.write_text(yaml.safe_dump(status, sort_keys=False), encoding="utf-8")
    rc = main(["--repo-root", str(tmp_path), "archive", "foo", "--archive-date", "2026-06-12"])
    assert rc == 0
    assert "/devola:archive: foo -> " in capsys.readouterr().out
    assert (tmp_path / ".local" / ".agent" / "archive" / "2026-06-12-foo").is_dir()

    # Error paths on STDERR with exit 1 (S-5 — no silent success):
    # a never-proposed id → change-store error; the just-archived id →
    # the ArchiveError gate message (the store still resolves it).
    rc = main(["--repo-root", str(tmp_path), "archive", "ghost", "--archive-date", "2026-06-12"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "change-store error" in captured.err
    assert captured.out == ""
    rc = main(["--repo-root", str(tmp_path), "archive", "foo", "--archive-date", "2026-06-12"])
    assert rc == 1
    assert "archive requires state == 'VERIFYING'" in capsys.readouterr().err


def test_error_guards_invalid_change_id_missing_pytest_and_bad_gate_score(
    tmp_path: Path,
) -> None:
    """v15.0.0 R3: the S-5 loud-failure guards left unexercised pre-R3.

    (a) An explicit ``change_id`` that violates the schema pattern is
        refused at scaffold time. (b) A missing pytest binary surfaces
        as ``VerifyFailed`` (never a silent pass). (c) A non-numeric
        ``gate_score`` is an ``ArchiveError`` naming the bad value.
    (d) ``_safe_relative`` falls back to the absolute string for paths
        outside the base instead of crashing the CLI.
    """
    from devolaflow.skills.slash_commands import _safe_relative

    # (a) explicit change_id must satisfy the schema pattern.
    with pytest.raises(ProposeError, match="does not match the"):
        scaffold_change_folder("ignored topic", tmp_path, change_id="Bad_ID")

    # (b) pytest binary missing → VerifyFailed, not silent success.
    scaffold_change_folder("foo", tmp_path)
    run_apply("foo", tmp_path)

    def missing_pytest(cmd: list[str], cwd: Path, check: bool) -> subprocess.CompletedProcess:
        raise FileNotFoundError("pytest not on PATH")

    with pytest.raises(VerifyFailed, match="FileNotFoundError"):
        run_verify("foo", tmp_path, pytest_runner=missing_pytest)
    store = ChangeStore(repo_root=tmp_path)
    assert store.get("foo").state == "IN_PROGRESS", "FSM must NOT advance on a failed verify"

    # (c) non-numeric gate_score → ArchiveError naming the value.
    _advance_to_verifying(tmp_path, "foo", gate_score=9.0)
    status_path = tmp_path / ".local" / ".agent" / "active" / "foo" / "STATUS.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    status["gate_score"] = "not-a-number"
    status_path.write_text(yaml.safe_dump(status, sort_keys=False), encoding="utf-8")
    with pytest.raises(ArchiveError, match="invalid gate_score 'not-a-number'"):
        run_archive("foo", tmp_path, archive_date="2026-06-12")

    # (d) out-of-base path → absolute-string fallback, no ValueError.
    outside = Path("/somewhere/else/file.txt")
    assert _safe_relative(outside, tmp_path) == str(outside)
    inside = tmp_path / "a" / "b.txt"
    assert _safe_relative(inside, tmp_path) == str(Path("a") / "b.txt")
