"""Task-stop lifecycle hook — ``test_on_complete``.

Documented in ``workflow-system/agent/SKILL.md`` §"Lifecycle Hooks".
Bound to the ``task_stop`` event by :mod:`devolaflow.lifecycle.__init__`.

Contract: when an L3 task agent reports completion, its status report
MUST claim tests-pass + lint-clean before the wave-level orchestrator
treats the task as truly done. This elevates Invariant **P4** (Bounded
Retry — `tests_failed > 0` should trigger an auto-retry, not a silent
"completed" pass) from prompt-only to deterministic when the caller
opts into ``strict=True``.

The hook accepts both the lean status-report shape (top-level
``tests_passed`` / ``tests_failed`` / ``lint_status``) AND the verbose
shape (nested under a ``metrics`` dict) for backward compatibility with
both ``schemas/lean-report.yaml`` and ``schemas/status-report.schema.yaml``.

Permissive default — warns. Strict mode raises ``HookViolation``;
callers (the wave-level retry classifier) can catch this and route the
task back through a convergence round per P4.

v8.2.0 (PV-03 — Karpathy 4.8 Unified session state) wires this hook to
:mod:`devolaflow.session` as an opt-in unifier. When the payload carries
a ``session_state_path`` key, ``test_on_complete`` additionally builds a
:class:`devolaflow.session.SessionState` from the payload, records the
hook outcome via :meth:`SessionState.record_lifecycle_event`, and
persists the snapshot via :class:`devolaflow.session.SessionStore`. The
legacy direct-:func:`devolaflow.learnings.consolidate_session` path
remains unchanged so existing callers see byte-identical behaviour
(R5 backward compatibility).
"""

from __future__ import annotations

from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "task_stop"

_CLEAN_LINT_TOKENS: frozenset[str] = frozenset(
    {"clean", "pass", "passed", "ok", "green", "0_warnings"}
)


def _coerce_int(value: object, default: int = 0) -> int:
    """Best-effort coerce *value* to int; return *default* on failure."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _read_metric(payload: dict[str, Any], metrics: dict[str, Any], key: str) -> Any:
    """Look up *key* in ``payload['metrics']`` first, then top-level ``payload``.

    Returns ``None`` if the key is absent in both scopes. Centralising
    this lookup lets the hook accept either the nested-metrics shape OR
    the flat lean-report shape without branching at every call site.
    """
    if key in metrics:
        return metrics[key]
    if key in payload:
        return payload[key]
    return None


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    """Collect all :class:`HookViolation` instances for *payload*."""
    if not isinstance(payload, dict):
        return [
            HookViolation(
                code="TOC001",
                message="task-stop payload is not a mapping",
                severity="error",
                context={"payload_type": type(payload).__name__},
            )
        ]

    metrics_raw = payload.get("metrics") or {}
    if not isinstance(metrics_raw, dict):
        return [
            HookViolation(
                code="TOC002",
                message="'metrics' field must be a mapping when present",
                severity="error",
                context={"metrics_type": type(metrics_raw).__name__},
            )
        ]

    violations: list[HookViolation] = []

    tests_passed = _read_metric(payload, metrics_raw, "tests_passed")
    tests_failed = _read_metric(payload, metrics_raw, "tests_failed")
    lint_status = _read_metric(payload, metrics_raw, "lint_status")

    if tests_passed is None and tests_failed is None:
        violations.append(
            HookViolation(
                code="TOC003",
                message=(
                    "task-stop status report missing required test result fields "
                    "(tests_passed, tests_failed)"
                ),
                severity="error",
                context={"keys_present": sorted(payload.keys())},
            )
        )
    else:
        failed_count = _coerce_int(tests_failed, default=0)
        if failed_count > 0:
            violations.append(
                HookViolation(
                    code="TOC004",
                    message=(
                        f"P4 retry trigger: completion blocked — {failed_count} test(s) failed"
                    ),
                    severity="blocker",
                    context={
                        "tests_passed": tests_passed,
                        "tests_failed": failed_count,
                    },
                )
            )

    if lint_status is None:
        violations.append(
            HookViolation(
                code="TOC005",
                message=("task-stop status report missing required field: 'lint_status'"),
                severity="error",
                context={"keys_present": sorted(payload.keys())},
            )
        )
    elif str(lint_status).strip().lower() not in _CLEAN_LINT_TOKENS:
        violations.append(
            HookViolation(
                code="TOC006",
                message=(
                    f"P4 retry trigger: completion blocked — lint not clean "
                    f"(status={lint_status!r})"
                ),
                severity="blocker",
                context={"lint_status": lint_status},
            )
        )

    return violations


def _try_consolidate_learnings(payload: dict[str, Any]) -> None:
    """Best-effort persist learnings from a successful task completion."""
    try:
        from devolaflow.learnings import (
            Learning,
            consolidate_session,
            resolve_learnings_path,
        )

        learnings_entries = payload.get("learnings", {}).get("entries", [])
        if not learnings_entries:
            return

        session_id = payload.get("task_id", "unknown")
        jsonl_path = resolve_learnings_path()
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        session_learnings = []
        for entry in learnings_entries:
            if isinstance(entry, dict) and "insight" in entry:
                session_learnings.append(
                    Learning(
                        stage=entry.get("stage", "task"),
                        task_type=entry.get("task_type", "general"),
                        key=entry.get("key", f"{session_id}:{entry.get('insight', '')[:30]}"),
                        insight=entry["insight"],
                        confidence=float(entry.get("confidence", 0.7)),
                        source_task_id=session_id,
                        files=entry.get("files", []),
                        source=entry.get("source", "task_completion"),
                    )
                )

        if session_learnings:
            consolidate_session(session_id, session_learnings, jsonl_path)
    except Exception:
        import logging

        logging.getLogger(__name__).debug("Session consolidation skipped", exc_info=True)


def _try_persist_session_state(
    payload: dict[str, Any],
    *,
    hook_passed: bool,
) -> None:
    """Opt-in: snapshot the session into a SessionStore JSON file.

    PV-03 wiring. Activated when the payload carries a non-empty
    ``session_state_path`` key — typically set by an L1/L2 orchestrator
    that wants the unified session view persisted at task_stop. When
    absent, this helper is a no-op so the legacy
    :func:`_try_consolidate_learnings` path remains the only side effect
    (R5 backward compatibility).

    Records:

    * Lifecycle event ``task_stop`` with ``passed=hook_passed`` (so the
      snapshot reflects whether the hook accepted the report).
    * Pending learnings are extracted from the same payload shape used
      by :func:`_try_consolidate_learnings` for symmetry.
    * Optional legibility verdicts sourced from
      ``payload['legibility']['files']`` (PV-02 integration); each entry
      is fed to :meth:`SessionState.attach_legibility`.

    Errors are logged and swallowed (best-effort) per S-5 — the hook
    must never fail the task because of an opt-in persistence layer.
    """
    if not isinstance(payload, dict):
        return
    state_path = payload.get("session_state_path")
    if not state_path:
        return

    import logging

    log = logging.getLogger(__name__)

    try:
        from devolaflow.learnings import Learning
        from devolaflow.session import SessionStore

        store = SessionStore(state_path)
        session_id = str(payload.get("task_id", "unknown"))
        state = store.load(default_session_id=session_id)
        if not state.session_id:
            state.session_id = session_id

        for entry in payload.get("learnings", {}).get("entries", []) or []:
            if not isinstance(entry, dict) or "insight" not in entry:
                continue
            try:
                state.queue_learning(
                    Learning(
                        stage=entry.get("stage", "task"),
                        task_type=entry.get("task_type", "general"),
                        key=entry.get(
                            "key",
                            f"{session_id}:{entry.get('insight', '')[:30]}",
                        ),
                        insight=entry["insight"],
                        confidence=float(entry.get("confidence", 0.7)),
                        source_task_id=session_id,
                        files=entry.get("files", []),
                        source=entry.get("source", "task_completion"),
                    )
                )
            except (TypeError, ValueError) as exc:
                log.warning("PV-03 lifecycle: skipping malformed learning %r: %s", entry, exc)

        legibility_block = payload.get("legibility") or {}
        if isinstance(legibility_block, dict):
            for legibility_file in legibility_block.get("files", []) or []:
                if not isinstance(legibility_file, dict):
                    continue
                file_path = legibility_file.get("path")
                score = legibility_file.get("score")
                if not file_path or score is None:
                    continue
                try:
                    state.attach_legibility(
                        file_path=str(file_path),
                        score=float(score),
                        findings=list(legibility_file.get("findings") or []),
                    )
                except (TypeError, ValueError) as exc:
                    log.warning(
                        "PV-03 lifecycle: skipping malformed legibility entry %r: %s",
                        legibility_file,
                        exc,
                    )

        violation_codes = [str(code) for code in (payload.get("violation_codes") or []) if code]
        state.record_lifecycle_event(
            event=EVENT,
            passed=hook_passed,
            severity=payload.get("severity"),
            violation_codes=violation_codes,
        )

        store.save(state)
    except Exception:
        log.debug("PV-03 lifecycle session-state persist skipped", exc_info=True)


def test_on_complete(payload: dict[str, Any], *, strict: bool = False) -> HookResult:
    """Verify a status report shows tests-pass + lint-clean.

    On a clean pass (no violations), also persists any learnings entries
    from the payload via :func:`consolidate_session`. Additionally, when
    the payload carries a ``session_state_path`` key, snapshots the
    unified :class:`devolaflow.session.SessionState` to disk via
    :class:`devolaflow.session.SessionStore` (PV-03 opt-in routing —
    the legacy ``consolidate_session`` direct call still runs first so
    callers see no behavioural change).
    """
    violations = _collect_violations(payload)
    result = finalize(EVENT, violations, strict=strict)
    if result.passed:
        _try_consolidate_learnings(payload)
    _try_persist_session_state(payload, hook_passed=result.passed)
    return result


# Tell pytest this is NOT a test function — it's a lifecycle hook that
# happens to be named with a ``test_`` prefix because that's the verbatim
# identifier documented in ``workflow-system/agent/SKILL.md`` §"Lifecycle
# Hooks". Without this, pytest tries to collect it as a test whenever the
# function is imported into a test module and fails to inject the
# ``payload`` fixture. See pytest docs on ``__test__`` attribute.
test_on_complete.__test__ = False  # type: ignore[attr-defined]


__all__ = ["EVENT", "test_on_complete"]
