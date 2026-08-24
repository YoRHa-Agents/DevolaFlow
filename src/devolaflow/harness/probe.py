"""Bounded model-compliance probes over deterministic harness fixtures."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from devolaflow.harness.fixtures import compute_probe_set_hash, load_harness_fixtures
from devolaflow.llm_client import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT_S,
    FAILURE_MODES,
    PROVIDER_CHOICES,
    LLMClient,
)

logger = logging.getLogger(__name__)


def build_probe_prompt(fixture: Mapping[str, Any], *, fold_mode: str = "folded") -> str:
    """Build one deterministic prompt requesting an unfenced lean-report mapping."""

    if not isinstance(fixture, Mapping):
        raise ValueError("fixture must be a mapping")
    if fold_mode not in {"full", "folded"}:
        raise ValueError("fold_mode must be 'full' or 'folded'")
    fixture_id = fixture.get("id")
    dispatch = fixture.get("dispatch")
    expected = fixture.get("expected")
    if not isinstance(fixture_id, str) or not fixture_id.strip():
        raise ValueError("fixture.id must be a non-empty string")
    if not isinstance(dispatch, Mapping) or not isinstance(expected, Mapping):
        raise ValueError("fixture dispatch and expected blocks must be mappings")

    required_keys = expected.get("report_required_keys")
    guard_ids = expected.get("guard_ids")
    required_literals = expected.get("required_literals")
    forbidden_keys = expected.get("report_forbidden_keys")
    if not all(
        isinstance(value, list) and all(isinstance(item, str) for item in value)
        for value in (required_keys, guard_ids, required_literals, forbidden_keys)
    ):
        raise ValueError("fixture response expectations must be string lists")

    dispatch_header = dispatch.get("hdr")
    dispatch_task = dispatch.get("task")
    seed_values: dict[str, Any] = {
        "hdr": {
            "id": f"probe-{fixture_id}",
            "dispatch": (
                dispatch_header.get("id", fixture_id)
                if isinstance(dispatch_header, Mapping)
                else fixture_id
            ),
            "task": (
                dispatch_task.get("id", fixture_id)
                if isinstance(dispatch_task, Mapping)
                else fixture_id
            ),
            "layer": "task",
        },
        "state": {"s": "completed", "pct": 100, "elapsed": 0},
        "artifacts": [
            {
                "path": f"probe/{fixture_id}.yaml",
                "type": "report",
                "delta": " | ".join(required_literals) or "probe contract satisfied",
            }
        ],
        "ac_results": [
            {"id": guard_id, "verdict": "pass", "cmd_digest": "probe contract pass"}
            for guard_id in guard_ids
        ],
        "diff_stats": {"files": 0, "insertions": 0, "deletions": 0},
    }
    mock_seed = {key: seed_values.get(key) for key in required_keys}
    mock_seed_yaml = yaml.safe_dump(
        mock_seed,
        allow_unicode=True,
        default_flow_style=True,
        sort_keys=False,
        width=1_000_000,
    ).strip()
    dispatch_yaml = yaml.safe_dump(
        dict(dispatch),
        allow_unicode=True,
        sort_keys=False,
        width=1_000_000,
    ).rstrip()
    return (
        "Execute the dispatch and return exactly one unfenced YAML mapping with no prose.\n"
        f"Probe mode: {fold_mode}. "
        + (
            "Preserve all invariant and guard constraints; advisory guidance may be folded.\n"
            if fold_mode == "folded"
            else "Preserve invariant, guard, and advisory constraints in full.\n"
        )
        + f"Required top-level keys: {', '.join(required_keys)}.\n"
        + f"Forbidden keys at every nesting depth: {', '.join(forbidden_keys)}.\n"
        + "ac_results must contain each guard exactly once with verdict pass and a "
        + "non-empty cmd_digest: "
        + f"{', '.join(guard_ids)}.\n"
        + "Include these literals case-insensitively: "
        + f"{', '.join(required_literals)}.\n\n"
        + "Stage A snapshot:\n"
        + mock_seed_yaml
        + "\n\nFixture dispatch:\n"
        + dispatch_yaml
        + "\n"
    )


def score_probe_response(fixture: Mapping[str, Any], response_text: str) -> dict[str, float]:
    """Score one response against fixture guards, literals, and lean-report shape."""

    if not isinstance(fixture, Mapping) or not isinstance(response_text, str):
        raise ValueError("fixture must be a mapping and response_text must be a string")
    expected = fixture.get("expected")
    if not isinstance(expected, Mapping):
        raise ValueError("fixture.expected must be a mapping")
    required_keys = expected.get("report_required_keys")
    forbidden_keys = expected.get("report_forbidden_keys")
    guard_ids = expected.get("guard_ids")
    required_literals = expected.get("required_literals")
    if not all(
        isinstance(value, list) and all(isinstance(item, str) for item in value)
        for value in (required_keys, forbidden_keys, guard_ids, required_literals)
    ):
        raise ValueError("fixture response expectations must be string lists")
    forbidden_key_set = set(forbidden_keys) | {"quality_score"}

    documents: list[Any] = []
    with suppress(yaml.YAMLError):
        documents = list(yaml.safe_load_all(response_text))
    report = (
        documents[0]
        if len(documents) == 1 and isinstance(documents[0], Mapping) and "```" not in response_text
        else None
    )

    forbidden_found = False
    if report is not None:
        pending: list[object] = [report]
        seen_containers: set[int] = set()
        while pending:
            value = pending.pop()
            if isinstance(value, Mapping):
                if id(value) in seen_containers:
                    continue
                seen_containers.add(id(value))
                if any(key in forbidden_key_set for key in value if isinstance(key, str)):
                    forbidden_found = True
                pending.extend(value.values())
            elif isinstance(value, list):
                if id(value) in seen_containers:
                    continue
                seen_containers.add(id(value))
                pending.extend(value)

    ac_results = report.get("ac_results") if report is not None else None
    rows_well_formed = isinstance(ac_results, list) and all(
        isinstance(row, Mapping)
        and isinstance(row.get("id"), str)
        and row.get("verdict") in {"pass", "fail", "skip"}
        and isinstance(row.get("cmd_digest"), str)
        and bool(row["cmd_digest"].strip())
        for row in ac_results
    )
    passed_guards = 0
    guards_complete = rows_well_formed
    if isinstance(ac_results, list):
        for guard_id in guard_ids:
            matches = [
                row for row in ac_results if isinstance(row, Mapping) and row.get("id") == guard_id
            ]
            passed = (
                len(matches) == 1
                and matches[0].get("verdict") == "pass"
                and isinstance(matches[0].get("cmd_digest"), str)
                and bool(matches[0]["cmd_digest"].strip())
            )
            passed_guards += int(passed)
            guards_complete = bool(guards_complete and passed)
    else:
        guards_complete = False

    folded_text = response_text.casefold()
    literal_matches = sum(literal.casefold() in folded_text for literal in required_literals)
    denominator = len(guard_ids) + len(required_literals)
    guard_compliance = (passed_guards + literal_matches) / denominator if denominator else 1.0
    schema_valid = bool(
        report is not None
        and not forbidden_found
        and all(key in report for key in required_keys)
        and isinstance(report.get("hdr"), Mapping)
        and isinstance(report.get("state"), Mapping)
        and isinstance(report.get("artifacts"), list)
        and isinstance(report.get("ac_results"), list)
        and isinstance(report.get("diff_stats"), Mapping)
        and guards_complete
    )
    return {
        "guard_compliance": guard_compliance,
        "schema_validity": float(schema_valid),
    }


def run_probe(
    fixtures: str | Path | Iterable[Mapping[str, Any]],
    *,
    provider: str,
    model: str,
    cycle: str,
    fold_mode: str = "folded",
    baseline_profile: str | Path | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = DEFAULT_TIMEOUT_S,
    output: str | Path | None = None,
    client: LLMClient | None = None,
    probed_at: str | None = None,
) -> dict[str, Any]:
    """Run one bounded call per fixture and write the exact model-profile artifact."""

    if provider not in PROVIDER_CHOICES:
        raise ValueError(f"provider must be one of {sorted(PROVIDER_CHOICES)}")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")
    if not isinstance(cycle, str) or not cycle.strip():
        raise ValueError("cycle must be a non-empty string")
    if fold_mode not in {"full", "folded"}:
        raise ValueError("fold_mode must be 'full' or 'folded'")
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("timeout must be a positive number")

    loaded = (
        load_harness_fixtures(fixtures) if isinstance(fixtures, (str, Path)) else tuple(fixtures)
    )
    probe_set_hash = compute_probe_set_hash(loaded)
    baseline_path = Path(baseline_profile) if baseline_profile is not None else None
    baseline_guard: float | None = None
    resolved_client = client or LLMClient(
        provider=provider,
        model=model,
        max_tokens=max_tokens,
        timeout_s=timeout,
    )
    if resolved_client.provider != provider:
        raise ValueError("injected client provider does not match requested provider")

    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "_", model)
    while ".." in safe_model:
        safe_model = safe_model.replace("..", "_")
    safe_model = safe_model.strip("._-") or "model"
    output_path = (
        Path(output)
        if output is not None
        else Path(".local/telemetry/model_profiles") / f"{provider}__{safe_model}.yaml"
    )
    timestamp = probed_at or datetime.now(UTC).isoformat()
    scenarios: list[dict[str, Any]] = []

    if provider != "mock" and not resolved_client.api_key:
        scenarios = [
            {
                "id": fixture["id"],
                "status": "SKIPPED_NO_KEY",
                "model_version_echo": None,
                "tokens_spent": 0,
                "guard_compliance": None,
                "schema_validity": None,
                "failure_mode": "fallback_disabled",
            }
            for fixture in loaded
        ]
        profile: dict[str, Any] = {
            "schema_version": 1,
            "status": "SKIPPED_NO_KEY",
            "provider": provider,
            "model": model,
            "cycle": cycle,
            "probed_at": timestamp,
            "model_version_echo": None,
            "probe_set_hash": probe_set_hash,
            "fold_mode": fold_mode,
            "baseline_profile": str(baseline_path) if baseline_path is not None else None,
            "calls": {"attempted": 0, "succeeded": 0, "failed": 0},
            "tokens_spent": 0,
            "guard_compliance": None,
            "schema_validity": None,
            "fold_delta": None,
            "scenarios": scenarios,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            yaml.safe_dump(profile, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return profile

    if baseline_path is not None:
        if fold_mode != "folded":
            raise ValueError("baseline_profile is valid only for fold_mode='folded'")
        try:
            baseline = yaml.safe_load(baseline_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid baseline profile YAML: {baseline_path}") from exc
        if not isinstance(baseline, Mapping):
            raise ValueError("baseline profile must be a mapping")
        expected_match = {
            "provider": provider,
            "model": model,
            "cycle": cycle,
            "probe_set_hash": probe_set_hash,
            "fold_mode": "full",
        }
        mismatched = [key for key, value in expected_match.items() if baseline.get(key) != value]
        raw_baseline_guard = baseline.get("guard_compliance")
        if mismatched:
            raise ValueError(
                "baseline profile does not match current probe: " + ", ".join(mismatched)
            )
        if (
            isinstance(raw_baseline_guard, bool)
            or not isinstance(raw_baseline_guard, (int, float))
            or not 0.0 <= float(raw_baseline_guard) <= 1.0
        ):
            raise ValueError("baseline profile guard_compliance must be in [0, 1]")
        baseline_guard = float(raw_baseline_guard)

    successful_scores: list[dict[str, float]] = []
    model_echoes: list[str] = []
    total_tokens = 0
    failed_calls = 0
    for fixture in loaded:
        response = None
        try:
            response = resolved_client.complete(build_probe_prompt(fixture, fold_mode=fold_mode))
        except Exception as exc:  # noqa: BLE001 - isolate injected-client contract violations
            logger.warning("harness probe client failure: %s", type(exc).__name__)
        if response is None or response.error is not None:
            failed_calls += 1
            failure_mode = (
                response.error
                if response is not None and response.error in FAILURE_MODES
                else "parse"
            )
            tokens = (
                max(0, response.tokens_in) + max(0, response.tokens_out)
                if response is not None
                else 0
            )
            total_tokens += tokens
            scenarios.append(
                {
                    "id": fixture["id"],
                    "status": "ERROR",
                    "model_version_echo": response.model if response is not None else None,
                    "tokens_spent": tokens,
                    "guard_compliance": None,
                    "schema_validity": None,
                    "failure_mode": failure_mode,
                }
            )
            continue

        score = score_probe_response(fixture, response.text)
        tokens = max(0, response.tokens_in) + max(0, response.tokens_out)
        total_tokens += tokens
        model_echoes.append(response.model)
        successful_scores.append(score)
        scenario_passed = score["guard_compliance"] == 1.0 and score["schema_validity"] == 1.0
        scenarios.append(
            {
                "id": fixture["id"],
                "status": "PASS" if scenario_passed else "FAIL",
                "model_version_echo": response.model,
                "tokens_spent": tokens,
                "guard_compliance": score["guard_compliance"],
                "schema_validity": score["schema_validity"],
                "failure_mode": None,
            }
        )

    guard_compliance = (
        sum(score["guard_compliance"] for score in successful_scores) / len(successful_scores)
        if successful_scores
        else None
    )
    schema_validity = (
        sum(score["schema_validity"] for score in successful_scores) / len(successful_scores)
        if successful_scores
        else None
    )
    unique_echoes = set(model_echoes)
    inconsistent_echo = len(unique_echoes) > 1
    if inconsistent_echo:
        for scenario in scenarios:
            if scenario["status"] != "ERROR":
                scenario["status"] = "PARTIAL"
                scenario["failure_mode"] = "model_echo_mismatch"
    status = (
        "PARTIAL"
        if failed_calls or inconsistent_echo
        else "PASS"
        if guard_compliance == 1.0 and schema_validity == 1.0
        else "FAIL"
    )
    fold_delta = (
        guard_compliance - baseline_guard
        if guard_compliance is not None and baseline_guard is not None
        else None
    )
    profile = {
        "schema_version": 1,
        "status": status,
        "provider": provider,
        "model": model,
        "cycle": cycle,
        "probed_at": timestamp,
        "model_version_echo": next(iter(unique_echoes)) if len(unique_echoes) == 1 else None,
        "probe_set_hash": probe_set_hash,
        "fold_mode": fold_mode,
        "baseline_profile": str(baseline_path) if baseline_path is not None else None,
        "calls": {
            "attempted": len(loaded),
            "succeeded": len(successful_scores),
            "failed": failed_calls,
        },
        "tokens_spent": total_tokens,
        "guard_compliance": guard_compliance,
        "schema_validity": schema_validity,
        "fold_delta": fold_delta,
        "scenarios": scenarios,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(profile, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return profile


__all__ = ["build_probe_prompt", "score_probe_response", "run_probe"]
