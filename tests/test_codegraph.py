"""Tests for :mod:`devolaflow.codegraph` (v12.5.0 PV-03 D-1.1).

Comprehensive coverage of the codegraph wrapper package: the thin
subprocess wrapper at :mod:`devolaflow.codegraph._cli` + the public
researcher API at :mod:`devolaflow.codegraph.researcher`.

Test discipline (mirrors ``tests/test_shell_proxy_commands.py`` v12.4.0
PV-04 precedent):

* All ``subprocess.run`` calls MOCKED — codegraph CLI is NOT assumed
  installed in the execution environment. The degraded-mode path is
  the documented contract per
  ``workflow-system/agent/references/degraded-mode.md`` (PV-05).
* All filesystem usage isolated to ``tmp_path``; no project-state
  side-effects.
* No network. No real npm install.

Coverage matrix:

* :func:`is_codegraph_available` — pure ``shutil.which`` probe; both
  branches (binary present, absent).
* :class:`CodegraphInvocationResult` — dataclass shape (frozen, the
  expected 4 fields).
* :class:`CodegraphUnavailableError` — structured ``cause`` constraint
  (one of the 4 enumerated strings).
* :func:`run_codegraph_cli` — argv normalisation (string → shlex.split
  + leading-codegraph requirement), path-missing degraded path,
  non-zero exit degraded path, timeout degraded path, JSON parse
  success + failure, byte-identical CompletedProcess capture.
* :func:`build_context` — happy-path returns stdout, degraded returns
  ``""``, query is shell-quoted (defends against injection).
* :func:`search_symbols` — happy-path returns list, dict-wrapped list
  unwrapped, degraded returns ``[]``, kind filter passed through.
* :func:`get_impact` — happy-path returns dict, degraded returns ``{}``.
* :func:`get_callers` — happy-path returns list, dict-wrapped list
  unwrapped, degraded returns ``[]``.
* :func:`get_affected_tests` — happy-path returns list, empty input
  short-circuits without invoking subprocess (R5 strict zero-IO),
  degraded returns ``[]``, dict-wrapped list unwrapped.
* Degraded-mode WARNING is emitted exactly ONCE per process (sentinel
  ``_DEGRADED_MODE_NOTIFIED``).

Source: ``.local/research/v12.5.0_gap_analysis.md`` §2 D-1 +
``.local/research/v12.5.0_codegraph_benefit_analysis.md`` §6.1 PV-03
acceptance criteria.
"""
# ruff: noqa: SIM117  -- nested `with patch(...)` blocks are deliberately kept
# unmerged for readability in subprocess-mocking test cases (each `with`
# scopes one collaborator). SIM117 false-positives this idiomatic pattern.

from __future__ import annotations

import json
import logging
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from devolaflow.codegraph import (
    CodegraphError,
    CodegraphInvocationResult,
    CodegraphUnavailableError,
    build_context,
    get_affected_tests,
    get_callers,
    get_impact,
    is_codegraph_available,
    run_codegraph_cli,
    search_symbols,
)
from devolaflow.codegraph import researcher as researcher_module

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_degraded_sentinel():
    """Reset the per-process degraded-mode sentinel between tests.

    The sentinel deduplicates the WARNING log; tests that exercise the
    degraded path need a clean slate so the WARNING fires for assertion.
    """
    researcher_module._DEGRADED_MODE_NOTIFIED = False
    yield
    researcher_module._DEGRADED_MODE_NOTIFIED = False


def _mock_completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    """Build a fake :class:`subprocess.CompletedProcess` for ``patch.return_value``."""
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


# ---------------------------------------------------------------------------
# is_codegraph_available — pure shutil.which probe
# ---------------------------------------------------------------------------


class TestIsCodegraphAvailable:
    def test_returns_true_when_binary_present(self) -> None:
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            assert is_codegraph_available() is True

    def test_returns_false_when_binary_absent(self) -> None:
        with patch("devolaflow.codegraph._cli.shutil.which", return_value=None):
            assert is_codegraph_available() is False


# ---------------------------------------------------------------------------
# CodegraphInvocationResult — dataclass shape
# ---------------------------------------------------------------------------


class TestCodegraphInvocationResult:
    def test_dataclass_is_frozen(self) -> None:
        result = CodegraphInvocationResult(
            stdout="x", stderr="y", returncode=0, args=("codegraph", "--version")
        )
        with pytest.raises((AttributeError, Exception)):
            result.stdout = "mutated"  # type: ignore[misc]

    def test_dataclass_fields(self) -> None:
        result = CodegraphInvocationResult(
            stdout="x", stderr="y", returncode=2, args=("codegraph", "search", "foo")
        )
        assert result.stdout == "x"
        assert result.stderr == "y"
        assert result.returncode == 2
        assert result.args == ("codegraph", "search", "foo")


# ---------------------------------------------------------------------------
# CodegraphUnavailableError — structured cause constraint
# ---------------------------------------------------------------------------


class TestCodegraphUnavailableError:
    def test_carries_structured_cause(self) -> None:
        exc = CodegraphUnavailableError("missing", cause="path_missing")
        assert exc.cause == "path_missing"
        assert "missing" in str(exc)

    @pytest.mark.parametrize(
        "cause",
        ["path_missing", "timeout", "nonzero_exit", "json_parse_error"],
    )
    def test_accepts_each_canonical_cause(self, cause: str) -> None:
        exc = CodegraphUnavailableError(f"reason {cause}", cause=cause)
        assert exc.cause == cause

    def test_inherits_from_codegraph_error(self) -> None:
        exc = CodegraphUnavailableError("x", cause="path_missing")
        assert isinstance(exc, CodegraphError)
        assert isinstance(exc, RuntimeError)


# ---------------------------------------------------------------------------
# run_codegraph_cli — argv normalisation, every degraded path, JSON parse
# ---------------------------------------------------------------------------


class TestRunCodegraphCli:
    def test_rejects_non_codegraph_argv(self) -> None:
        with pytest.raises(CodegraphError, match="argv to start with 'codegraph'"):
            run_codegraph_cli(["nines", "search", "foo"])

    def test_rejects_empty_argv(self) -> None:
        with pytest.raises(CodegraphError):
            run_codegraph_cli([])

    def test_path_missing_raises_unavailable(self, caplog: pytest.LogCaptureFixture) -> None:
        with patch("devolaflow.codegraph._cli.shutil.which", return_value=None):
            with caplog.at_level(logging.WARNING, logger="devolaflow.codegraph._cli"):
                with pytest.raises(CodegraphUnavailableError) as exc_info:
                    run_codegraph_cli("codegraph --version")
        assert exc_info.value.cause == "path_missing"
        # WARNING log mentions install path per S-5 + W-20 (env-flag reuse).
        assert any("DEVOLAFLOW_AUTO_INSTALL_PLUGINS" in rec.message for rec in caplog.records)

    def test_timeout_raises_unavailable(self) -> None:
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch(
                "devolaflow.codegraph._cli.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=["codegraph"], timeout=5),
            ):
                with pytest.raises(CodegraphUnavailableError) as exc_info:
                    run_codegraph_cli("codegraph search foo", timeout=5)
        assert exc_info.value.cause == "timeout"

    def test_nonzero_exit_raises_unavailable(self) -> None:
        proc = _mock_completed(stdout="", stderr="indexing failed", returncode=2)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                with pytest.raises(CodegraphUnavailableError) as exc_info:
                    run_codegraph_cli("codegraph search foo")
        assert exc_info.value.cause == "nonzero_exit"

    def test_happy_path_returns_invocation_result(self) -> None:
        proc = _mock_completed(stdout="hello\n", stderr="", returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                result = run_codegraph_cli("codegraph --version")
        assert isinstance(result, CodegraphInvocationResult)
        assert result.stdout == "hello\n"
        assert result.returncode == 0
        assert result.args[0] == "codegraph"

    def test_parse_json_returns_dict(self) -> None:
        proc = _mock_completed(stdout='{"a": 1, "b": [2, 3]}', stderr="", returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                result = run_codegraph_cli("codegraph status --json", parse_json=True)
        assert result == {"a": 1, "b": [2, 3]}

    def test_parse_json_returns_list(self) -> None:
        proc = _mock_completed(stdout='[{"id": 1}, {"id": 2}]', stderr="", returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                result = run_codegraph_cli("codegraph search foo --json", parse_json=True)
        assert result == [{"id": 1}, {"id": 2}]

    def test_parse_json_empty_stdout_raises_unavailable(self) -> None:
        proc = _mock_completed(stdout="", stderr="", returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                with pytest.raises(CodegraphUnavailableError) as exc_info:
                    run_codegraph_cli("codegraph status --json", parse_json=True)
        assert exc_info.value.cause == "json_parse_error"

    def test_parse_json_invalid_raises_unavailable(self) -> None:
        proc = _mock_completed(stdout="not valid json {[}", stderr="", returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                with pytest.raises(CodegraphUnavailableError) as exc_info:
                    run_codegraph_cli("codegraph status --json", parse_json=True)
        assert exc_info.value.cause == "json_parse_error"

    def test_cwd_passed_to_subprocess(self, tmp_path: pytest.TempPathFactory) -> None:
        proc = _mock_completed(stdout="ok\n", returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc) as mock_run:
                run_codegraph_cli("codegraph --version", cwd=str(tmp_path))
        assert mock_run.call_args.kwargs.get("cwd") == str(tmp_path)


# ---------------------------------------------------------------------------
# build_context — researcher API
# ---------------------------------------------------------------------------


class TestBuildContext:
    def test_happy_path_returns_stdout(self) -> None:
        proc = _mock_completed(stdout="# Context\n\nFoo bar.\n", returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                out = build_context("foo bar", max_nodes=10)
        assert "# Context" in out
        assert "Foo bar." in out

    def test_degraded_returns_empty_string(self, caplog: pytest.LogCaptureFixture) -> None:
        with patch("devolaflow.codegraph._cli.shutil.which", return_value=None):
            with caplog.at_level(logging.WARNING, logger="devolaflow.codegraph.researcher"):
                out = build_context("anything")
        assert out == ""
        # Degraded-mode WARNING fired
        assert any("degraded" in rec.message.lower() for rec in caplog.records)

    def test_query_shell_quoted(self) -> None:
        """Query strings with shell metacharacters must NOT inject extra args."""
        proc = _mock_completed(stdout="ok\n", returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc) as mock_run:
                build_context("hello; rm -rf /")
        invoked_argv = mock_run.call_args.args[0]
        assert "codegraph" in invoked_argv
        # The malicious-looking query is one shlex-quoted token, not a separator.
        assert "hello; rm -rf /" in invoked_argv


# ---------------------------------------------------------------------------
# search_symbols — researcher API
# ---------------------------------------------------------------------------


class TestSearchSymbols:
    def test_happy_path_list(self) -> None:
        payload = json.dumps([{"name": "Foo", "kind": "class"}])
        proc = _mock_completed(stdout=payload, returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                out = search_symbols("Foo", limit=5)
        assert out == [{"name": "Foo", "kind": "class"}]

    def test_dict_wrapped_results_unwrapped(self) -> None:
        payload = json.dumps({"results": [{"name": "Bar"}]})
        proc = _mock_completed(stdout=payload, returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                out = search_symbols("Bar")
        assert out == [{"name": "Bar"}]

    def test_kind_filter_passed_through(self) -> None:
        proc = _mock_completed(stdout="[]", returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc) as mock_run:
                search_symbols("foo", kind="function", limit=3)
        invoked = " ".join(mock_run.call_args.args[0])
        assert "--kind" in invoked
        assert "function" in invoked
        assert "--limit" in invoked
        assert "3" in invoked

    def test_degraded_returns_empty_list(self) -> None:
        with patch("devolaflow.codegraph._cli.shutil.which", return_value=None):
            assert search_symbols("any") == []


# ---------------------------------------------------------------------------
# get_impact — researcher API
# ---------------------------------------------------------------------------


class TestGetImpact:
    def test_happy_path_dict(self) -> None:
        payload = json.dumps({"symbol": "Foo", "depth": 3, "affected": ["a", "b"]})
        proc = _mock_completed(stdout=payload, returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                out = get_impact("Foo", depth=3)
        assert out["symbol"] == "Foo"
        assert out["affected"] == ["a", "b"]

    def test_degraded_returns_empty_dict(self) -> None:
        with patch("devolaflow.codegraph._cli.shutil.which", return_value=None):
            assert get_impact("Anything") == {}

    def test_non_dict_response_returns_empty_dict(self) -> None:
        # Defensive: upstream might return a list; researcher treats as
        # degraded-but-no-warning (the run_codegraph_cli succeeded; the
        # shape just doesn't match).
        proc = _mock_completed(stdout="[1, 2, 3]", returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                assert get_impact("Foo") == {}


# ---------------------------------------------------------------------------
# get_callers — researcher API
# ---------------------------------------------------------------------------


class TestGetCallers:
    def test_happy_path_list(self) -> None:
        payload = json.dumps([{"caller": "main"}, {"caller": "test_main"}])
        proc = _mock_completed(stdout=payload, returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                out = get_callers("Foo")
        assert len(out) == 2

    def test_dict_wrapped_callers_unwrapped(self) -> None:
        payload = json.dumps({"callers": [{"caller": "x"}]})
        proc = _mock_completed(stdout=payload, returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                out = get_callers("Foo")
        assert out == [{"caller": "x"}]

    def test_degraded_returns_empty_list(self) -> None:
        with patch("devolaflow.codegraph._cli.shutil.which", return_value=None):
            assert get_callers("Anything") == []


# ---------------------------------------------------------------------------
# get_affected_tests — researcher API + R5 strict zero-IO short-circuit
# ---------------------------------------------------------------------------


class TestGetAffectedTests:
    def test_empty_changed_files_short_circuits_no_subprocess(self) -> None:
        """R5 strict: empty input must NOT spawn a subprocess."""
        with (
            patch("devolaflow.codegraph._cli.subprocess.run") as mock_run,
            patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"),
        ):
            out = get_affected_tests([])
        assert out == []
        assert mock_run.call_count == 0

    def test_happy_path_list(self) -> None:
        payload = json.dumps(["tests/test_a.py", "tests/test_b.py"])
        proc = _mock_completed(stdout=payload, returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                out = get_affected_tests(["src/foo.py", "src/bar.py"])
        assert out == ["tests/test_a.py", "tests/test_b.py"]

    def test_dict_wrapped_unwrapped(self) -> None:
        payload = json.dumps({"affected": ["tests/test_a.py"]})
        proc = _mock_completed(stdout=payload, returncode=0)
        with patch("devolaflow.codegraph._cli.shutil.which", return_value="/usr/bin/codegraph"):
            with patch("devolaflow.codegraph._cli.subprocess.run", return_value=proc):
                out = get_affected_tests(["src/foo.py"])
        assert out == ["tests/test_a.py"]

    def test_degraded_returns_empty_list(self) -> None:
        with patch("devolaflow.codegraph._cli.shutil.which", return_value=None):
            assert get_affected_tests(["src/foo.py"]) == []


# ---------------------------------------------------------------------------
# Degraded-mode WARNING is emitted exactly ONCE per process
# ---------------------------------------------------------------------------


class TestDegradedModeNotificationDeduplication:
    def test_warning_fires_once_then_demotes_to_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """First degraded helper call emits WARNING; subsequent calls log at DEBUG.

        Filters to ``devolaflow.codegraph.researcher`` records only —
        the underlying ``devolaflow.codegraph._cli`` layer logs a
        WARNING per CLI invocation by design (S-5 audit trail). The
        deduplication contract is at the researcher layer (caller-
        facing) where the operator-noise is the actual concern.
        """
        with patch("devolaflow.codegraph._cli.shutil.which", return_value=None):
            with caplog.at_level(logging.DEBUG, logger="devolaflow.codegraph.researcher"):
                build_context("first")
                search_symbols("second")
                get_impact("Third")
                get_callers("Fourth")
                get_affected_tests(["foo.py"])

        # Filter to researcher-layer records only (per docstring above).
        researcher_records = [
            rec for rec in caplog.records if rec.name == "devolaflow.codegraph.researcher"
        ]
        warning_records = [rec for rec in researcher_records if rec.levelno == logging.WARNING]
        debug_records = [rec for rec in researcher_records if rec.levelno == logging.DEBUG]

        # Exactly one researcher-layer WARNING — the first helper call.
        # The remaining 4 helper calls log at DEBUG to preserve
        # auditability without operator-facing log spam.
        assert len(warning_records) == 1, (
            f"Expected exactly 1 researcher-layer degraded-mode WARNING; got "
            f"{len(warning_records)}: {[r.message for r in warning_records]}"
        )
        assert len(debug_records) >= 4
