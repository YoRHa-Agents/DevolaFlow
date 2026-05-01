"""Unit contract tests for ``devolaflow.memory_router.cache.consult_for_dispatch``.

Pins the v9.1.4 PV-04 advisory-hint surface that composes the
``.local/memory/cases/index.yaml`` cache into the dispatch payload's
``change_context.memory_case_hits`` sub-field (NEST extension per A-2.3).

Coverage matrix (5 NEW test functions, within W-17 PV-04 budget of +9):

1. ``test_env_flag_off_returns_empty_list`` — R5 strict zero-IO when
   ``DEVOLAFLOW_MEMORY_ROUTER`` is unset (the default). Verifies via
   ``monkeypatch.setattr(Path, "read_text", _watcher)`` that NO
   filesystem read happens on the disabled path.
2. ``test_missing_index_yaml_returns_empty_list`` — env-flag ON but
   ``.local/memory/cases/index.yaml`` absent → ``[]`` (DEBUG log only;
   legitimate new-repo state per the function docstring).
3. ``test_malformed_index_yaml_returns_empty_list_with_warning`` —
   env-flag ON + malformed YAML → ``[]`` + one WARNING captured (S-5
   explicit error state).
4. ``test_keyword_overlap_returns_top_hits`` — env-flag ON + 5
   well-formed cases → top-3 by overlap score; ties broken by
   ``last_accessed`` desc.
5. ``test_expired_and_stale_cases_are_filtered`` — env-flag ON + index
   carrying 1 expired + 1 version-stale + 2 fresh cases → only the 2
   fresh cases returned.

R5 strict additive: `DEVOLAFLOW_MEMORY_ROUTER` is REUSED with the
existing fast-path `MemoryRouter.lookup_case` per W-20 (no new env
flag — the v9.2.0 cycle plan §"Self-iteration constraint compliance
matrix" pins "0 new flags across the entire 7-PV cycle").
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from devolaflow.memory_router import consult_for_dispatch


@pytest.fixture
def fresh_payload() -> dict:
    """Sample dispatch payload with task description matching most fixtures."""
    return {
        "task": {
            "id": "T-PV04-001",
            "type": "code",
            "title": "memory router consultation",
            "description": "implement memory router fast-path consultation for dispatch context",
        },
        "goal": "wire memory consultation into change_context",
    }


def _write_index(repo_root: Path, cases: list[dict], *, last_updated: str = "") -> Path:
    """Helper — write a fully-formed ``.local/memory/cases/index.yaml``."""
    cases_dir = repo_root / ".local" / "memory" / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    index_path = cases_dir / "index.yaml"
    payload = {"last_updated": last_updated or _today_iso(), "cases": cases}
    index_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return index_path


def _today_iso() -> str:
    return datetime.now(UTC).date().isoformat()


def _yesterday_iso() -> str:
    return (datetime.now(UTC).date() - timedelta(days=1)).isoformat()


def _make_case_row(
    case_id: str,
    *,
    workflow_type: str = "feature-implementation",
    task_type: str = "implement",
    summary: str,
    tags: list[str] | None = None,
    version_stamp: str = "9.1.4",
    ttl_days: int = 30,
    last_accessed: str = "",
) -> dict:
    """Build a well-formed case row dict suitable for ``index.yaml``."""
    return {
        "case_id": case_id,
        "workflow_type": workflow_type,
        "task_type": task_type,
        "summary": summary,
        "recipe_path": f".local/memory/cases/{case_id}.md",
        "version_stamp": version_stamp,
        "ttl_days": ttl_days,
        "last_accessed": last_accessed or _today_iso(),
        "tags": tags or [],
    }


def test_env_flag_off_returns_empty_list(
    tmp_path: Path,
    fresh_payload: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R5 strict — env-flag absent → ``[]`` with zero IO.

    Pins the headline R5 strict invariant: when ``DEVOLAFLOW_MEMORY_ROUTER``
    is NOT set to the literal string ``"1"``, ``consult_for_dispatch``
    returns ``[]`` immediately, BEFORE any filesystem read. Verified via a
    ``Path.read_text`` watcher that records call counts; the disabled path
    must produce zero read calls.
    """
    monkeypatch.delenv("DEVOLAFLOW_MEMORY_ROUTER", raising=False)

    # Even if the index exists with content, the env-flag-OFF path must
    # NOT reach into it. We stage a real index to prove the invariant.
    _write_index(
        tmp_path,
        [_make_case_row("c-1", summary="memory router fast-path implementation")],
    )

    read_count = {"n": 0}
    real_read = Path.read_text

    def _watcher(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "index.yaml" and ".local/memory/cases/" in str(self):
            read_count["n"] += 1
        return real_read(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", _watcher)

    result = consult_for_dispatch(fresh_payload, tmp_path)

    assert result == [], f"env-flag OFF MUST return []; got {result!r}"
    assert read_count["n"] == 0, (
        f"R5 strict violation: env-flag-OFF path read .local/memory/cases/index.yaml "
        f"{read_count['n']} times; expected 0 (zero-IO no-op)"
    )

    # Probe the parametrized non-1 variants explicitly — every value other
    # than the literal "1" string must also be OFF. Mirrors the
    # tests/test_handoff_auto_write.py::test_env_flag_any_value_other_than_1
    # parametrization pattern.
    for variant in ("0", "true", "yes", " 1 ", "1.0", "TRUE", ""):
        monkeypatch.setenv("DEVOLAFLOW_MEMORY_ROUTER", variant)
        assert consult_for_dispatch(fresh_payload, tmp_path) == [], (
            f"R5 strict violation: env value {variant!r} must NOT activate; "
            "only the literal string '1' opts in"
        )


def test_missing_index_yaml_returns_empty_list(
    tmp_path: Path,
    fresh_payload: dict,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """env-flag ON + index file absent → ``[]`` + DEBUG log only.

    A fresh consumer repo legitimately has no ``.local/memory/cases/``
    directory yet. The function docstring promises to log DEBUG (NOT
    WARNING) in this case so the operator does not see noise on every
    dispatch from a brand-new repo. We assert the empty result AND the
    absence of any WARNING.
    """
    monkeypatch.setenv("DEVOLAFLOW_MEMORY_ROUTER", "1")
    # tmp_path has NO .local/ directory at all — index is absent.
    assert not (tmp_path / ".local" / "memory" / "cases" / "index.yaml").exists()

    with caplog.at_level(logging.DEBUG, logger="devolaflow.memory_router.cache"):
        result = consult_for_dispatch(fresh_payload, tmp_path)

    assert result == [], f"missing index MUST return []; got {result!r}"
    warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not warning_records, (
        f"missing index MUST NOT log WARNING (legitimate new-repo state); "
        f"captured: {[r.message for r in warning_records]!r}"
    )


def test_malformed_index_yaml_returns_empty_list_with_warning(
    tmp_path: Path,
    fresh_payload: dict,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """env-flag ON + malformed YAML → ``[]`` + WARNING log (S-5 compliance).

    Three malformed shapes covered:

    1. Genuine YAML parse error (invalid `yaml.YAMLError`).
    2. Top-level non-mapping (e.g. a bare list).
    3. ``cases`` key not a list (e.g. a dict).

    Each case must yield ``[]`` (cache-miss is the safe path per R5 strict)
    AND emit exactly one WARNING citing the failure mode and the file path.
    """
    monkeypatch.setenv("DEVOLAFLOW_MEMORY_ROUTER", "1")
    cases_dir = tmp_path / ".local" / "memory" / "cases"
    cases_dir.mkdir(parents=True)
    index_path = cases_dir / "index.yaml"

    # Case 1 — genuine YAML parse error.
    index_path.write_text(
        ":\n  - invalid: [unclosed\n",
        encoding="utf-8",
    )
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="devolaflow.memory_router.cache"):
        result = consult_for_dispatch(fresh_payload, tmp_path)
    assert result == [], "malformed YAML MUST return []"
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warns) >= 1, "malformed YAML MUST emit at least one WARNING (S-5)"
    assert any("not valid YAML" in r.message for r in warns), (
        f"WARNING text must cite the YAML failure; got: {[r.message for r in warns]!r}"
    )

    # Case 2 — top-level non-mapping (a bare list).
    index_path.write_text(
        "- bare\n- list\n",
        encoding="utf-8",
    )
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="devolaflow.memory_router.cache"):
        result = consult_for_dispatch(fresh_payload, tmp_path)
    assert result == [], "bare-list top-level MUST return []"
    assert any("top-level must be a mapping" in r.message for r in caplog.records), (
        f"WARNING text must cite the mapping requirement; got: "
        f"{[r.message for r in caplog.records]!r}"
    )

    # Case 3 — `cases` is a dict instead of a list.
    index_path.write_text(
        "last_updated: 2026-05-01\ncases:\n  not: a list\n",
        encoding="utf-8",
    )
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="devolaflow.memory_router.cache"):
        result = consult_for_dispatch(fresh_payload, tmp_path)
    assert result == [], "non-list cases MUST return []"
    assert any("'cases' key must be a list" in r.message for r in caplog.records), (
        f"WARNING text must cite the cases-list requirement; got: "
        f"{[r.message for r in caplog.records]!r}"
    )


def test_keyword_overlap_returns_top_hits(
    tmp_path: Path,
    fresh_payload: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """env-flag ON + well-formed index → top-3 by overlap score.

    Stages 5 cases with varying keyword overlap against ``fresh_payload``
    (whose tokens include ``memory``, ``router``, ``consultation``,
    ``dispatch``, ``context``, ``fast-path``, ``implement``, etc.):

    * c-high — strong match (4 overlapping tokens)
    * c-mid-1 — medium match (2 tokens) + last_accessed today
    * c-mid-2 — medium match (2 tokens) + last_accessed yesterday
    * c-low — weak match (1 token)
    * c-zero — no overlap (filtered out entirely)

    Asserts: result length == 3; the strong match is first; mid-tier ties
    are broken by ``last_accessed`` desc (today beats yesterday).
    """
    monkeypatch.setenv("DEVOLAFLOW_MEMORY_ROUTER", "1")

    today = _today_iso()
    yesterday = _yesterday_iso()

    # c-high — strong overlap (multiple tokens from summary + tags +
    # workflow_type/task_type all matching payload).
    # c-mid-1 / c-mid-2 — medium overlap (2 tokens from summary "memory"
    # + task_type "implement"); differ only on last_accessed for the
    # tie-break test.
    # c-low — weak overlap (1 token "dispatch" only); workflow/task type
    # are orthogonal so they don't contribute extra overlap that would
    # promote c-low above c-mid-* on score.
    # c-zero — no overlap (orthogonal workflow/task + unrelated summary
    # + unrelated tags); MUST be filtered out entirely.
    cases = [
        _make_case_row(
            "c-high",
            summary="memory router fast-path consultation for dispatch context",
            tags=["memory", "router"],
            last_accessed=today,
        ),
        _make_case_row(
            "c-mid-1",
            summary="generic memory plumbing helper",
            tags=["memory"],
            last_accessed=today,
        ),
        _make_case_row(
            "c-mid-2",
            summary="generic memory plumbing helper",
            tags=["memory"],
            last_accessed=yesterday,
        ),
        _make_case_row(
            "c-low",
            workflow_type="documentation-only",
            task_type="review",
            summary="dispatch payload normaliser",
            tags=[],
            last_accessed=today,
        ),
        _make_case_row(
            "c-zero",
            workflow_type="research-design-review-refine",
            task_type="audit",
            summary="completely unrelated topic about widgets",
            tags=["widgets"],
            last_accessed=today,
        ),
    ]
    _write_index(tmp_path, cases)

    result = consult_for_dispatch(
        fresh_payload,
        tmp_path,
        current_version="9.1.4",
        today=today,
    )

    assert len(result) == 3, (
        f"expected top-3 hits; got {len(result)}: {[c.case_id for c in result]!r}"
    )
    assert result[0].case_id == "c-high", (
        f"strongest overlap MUST be ranked first; got {result[0].case_id}"
    )
    # Mid-tier tie broken by last_accessed desc — today beats yesterday.
    mid_ids = [c.case_id for c in result[1:3]]
    assert mid_ids == ["c-mid-1", "c-mid-2"], (
        f"mid-tier tie MUST be broken by last_accessed DESC: expected "
        f"['c-mid-1', 'c-mid-2'], got {mid_ids}"
    )
    assert "c-zero" not in [c.case_id for c in result], "zero-overlap case MUST be filtered out"


def test_zero_max_hits_and_empty_keywords_short_circuit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cheap edge-case coverage: ``max_hits=0`` and empty-keyword payloads return ``[]``.

    Two short-circuits in ``consult_for_dispatch`` worth pinning:

    1. ``max_hits=0`` (degenerate cap) → ``[]`` after the env-flag gate but
       BEFORE any filesystem read. Catches a regression that would walk
       the index needlessly.
    2. ``payload`` with no extractable keywords (e.g. empty title +
       missing description) → ``[]`` after env-flag gate but BEFORE
       index parse. Mirrors the "scoring would always be 0" path.

    Both paths are documented in the function docstring; this test
    pins them explicitly so a future refactor that loses the early
    return path fails CI immediately.
    """
    monkeypatch.setenv("DEVOLAFLOW_MEMORY_ROUTER", "1")
    _write_index(
        tmp_path,
        [_make_case_row("c-any", summary="memory router")],
    )

    # max_hits=0 → []
    assert (
        consult_for_dispatch({"task": {"description": "memory router"}}, tmp_path, max_hits=0) == []
    ), "max_hits=0 MUST short-circuit to []"

    # empty payload → []
    assert consult_for_dispatch({}, tmp_path) == [], "empty payload MUST short-circuit to []"

    # task block missing description / title / goal → []
    assert consult_for_dispatch({"task": {"id": "T-001"}}, tmp_path) == [], (
        "task block with no extractable text MUST short-circuit to []"
    )

    # task is not a dict → []
    assert consult_for_dispatch({"task": "not a dict"}, tmp_path) == [], (
        "non-dict task block MUST be defensive — short-circuit to []"
    )


def test_expired_and_stale_cases_are_filtered(
    tmp_path: Path,
    fresh_payload: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """env-flag ON + mixed freshness → only fresh, version-current cases returned.

    Stages 4 cases:

    * c-fresh-a / c-fresh-b — well-formed, version-current, in TTL window
    * c-stale — version_stamp != current_version (filtered by
      ``is_version_stale``)
    * c-expired — last_accessed beyond ttl_days window (filtered by
      ``is_ttl_expired``)

    Asserts: exactly the 2 fresh cases are returned; the order doesn't
    matter (both score identically) but the content does.
    """
    monkeypatch.setenv("DEVOLAFLOW_MEMORY_ROUTER", "1")

    today = _today_iso()
    long_ago = (datetime.now(UTC).date() - timedelta(days=60)).isoformat()

    cases = [
        _make_case_row(
            "c-fresh-a",
            summary="memory router consultation pathway",
            last_accessed=today,
            ttl_days=30,
            version_stamp="9.1.4",
        ),
        _make_case_row(
            "c-fresh-b",
            summary="memory router fast dispatch",
            last_accessed=today,
            ttl_days=30,
            version_stamp="9.1.4",
        ),
        # version-stale case — version_stamp != current_version
        _make_case_row(
            "c-stale",
            summary="memory router consultation pathway",
            last_accessed=today,
            ttl_days=30,
            version_stamp="8.0.0",
        ),
        # ttl-expired case — last_accessed 60 days ago, ttl_days=30
        _make_case_row(
            "c-expired",
            summary="memory router consultation pathway",
            last_accessed=long_ago,
            ttl_days=30,
            version_stamp="9.1.4",
        ),
    ]
    _write_index(tmp_path, cases)

    result = consult_for_dispatch(
        fresh_payload,
        tmp_path,
        current_version="9.1.4",
        today=today,
    )

    returned_ids = {c.case_id for c in result}
    assert returned_ids == {"c-fresh-a", "c-fresh-b"}, (
        f"expected exactly the 2 fresh cases; got {returned_ids}. "
        f"version-stale + TTL-expired cases must be filtered."
    )
