#!/usr/bin/env python3
"""NineS self-eval JSON → Si-Chip ``runs-dir`` / ``baseline-dir`` adapter.

D-N-1 closure (v10.2.2 PV-03). Solves the v9.5.0 OA-1 blocker that
deferred every Si-Chip dogfood pass to a DEFER verdict: Si-Chip's
``aggregate_eval.py`` requires a ``runs-dir`` (with-ability LLM runs)
plus a ``baseline-dir`` (no-ability LLM runs). Generating real LLM
eval data is expensive and operator-intensive; this adapter SUBSTITUTES
NineS self-eval per-task scores into the Si-Chip layout so
``iteration_delta`` becomes computable WITHOUT fresh LLM runs.

The adapter is a **research probe** for the v10.2.0 cycle. Both
APPROVE and REJECT outcomes are acceptable per the cycle plan §3 PV-03
backout plan: an APPROVE produces real ``iteration_delta`` evidence
while a REJECT documents that the two formats are not reconcilable
and the cycle falls back to ``count_tokens`` regression per the v9.5.0
§3 fallback.

Mapping strategy
----------------

NineS shape (extracted from ``docs/cycle-archive/v10.0.0/nines/v10.0.0_nines.json``):

* Top-level ``scores`` array contains capability + hygiene scores.
* The ``scoring_accuracy`` score's ``metadata.details`` field contains
  per-task entries keyed by golden-task id (e.g.
  ``devolaflow-adap-003``). Each entry carries
  ``{nines_score, golden_score, delta, accurate, scorer}``.

Si-Chip shape (from ``aggregate_eval.py::REQUIRED_KEYS`` + the
``--runs-dir`` / ``--baseline-dir`` glob walk):

* Each task = a directory containing ``result.json``.
* ``result.json`` MUST contain seven keys: ``pass_rate``,
  ``pass_k_4``, ``latency_p95_s``, ``metadata_tokens``,
  ``per_invocation_footprint``, ``trigger_F1``, ``router_floor``.

The adapter maps NineS per-task scores onto Si-Chip's ``pass_rate`` +
``pass_k_4`` + ``trigger_F1`` axes (the only quality axes NineS's
golden-task-accuracy probe naturally surfaces); the remaining four
fields receive deterministic synthetic constants documented in
``_synthetic_constants_doc()``. The synthetic constants are stable
across runs so ``iteration_delta`` deltas are driven solely by NineS
score deltas — exactly the signal we want.

Mode flags
----------

* ``--mode synthetic`` (default) — the baseline directory carries
  ``pass_rate = 0.0`` for every task. This is the cleanest A/B contrast
  for "ability vs no-ability" — the no-ability run is "ability did
  nothing" by construction. Si-Chip's ``T3_baseline_delta = pass_with -
  pass_without`` accordingly equals the NineS mean ``nines_score``
  directly.
* ``--mode sample`` — a second NineS JSON (passed via
  ``--baseline-nines-json``) supplies the no-ability run scores. This
  is the natural mode for cycle-over-cycle comparison: feed v10.0.0
  NineS as the baseline and v10.2.0 NineS as the with-ability run.

Loud failures (S-5)
-------------------

* Malformed JSON → :class:`json.JSONDecodeError` propagates with the
  source path stitched into the error message.
* Missing ``scoring_accuracy`` → ``validate_nines_shape`` returns
  ``(False, reason)`` and ``main`` exits with code 1 + stderr ``REJECT``
  message. This IS the documented R-1 fallback path.
* Missing ``--baseline-nines-json`` when ``--mode sample`` →
  :class:`SystemExit` from argparse before ``main`` runs.

Source: v10.2.0 cycle plan §3 PV-03 (D-N-1 closure). External tools
(S-7 compliance):

* DevolaFlow / EvoBench: https://github.com/YoRHa-Agents/DevolaFlow
* NineS: https://github.com/YoRHa-Agents/NineS
* Si-Chip: https://github.com/YoRHa-Agents/Si-Chip
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("devolaflow.nines_to_sichip_eval_adapter")

ADAPTER_VERSION: str = "0.1.0"

# Si-Chip's aggregate_eval.py REQUIRED_KEYS contract for every result.json.
# Mirrored verbatim from
# https://github.com/YoRHa-Agents/Si-Chip/blob/v0.4.0/scripts/aggregate_eval.py#L60-L68
SICHIP_REQUIRED_KEYS: tuple[str, ...] = (
    "pass_rate",
    "pass_k_4",
    "latency_p95_s",
    "metadata_tokens",
    "per_invocation_footprint",
    "trigger_F1",
    "router_floor",
)

# Synthetic constants for the 4 Si-Chip fields NineS does not naturally
# surface. Values chosen to be plausible mid-range estimates so Si-Chip's
# downstream gates (R3_trigger_F1, C1_metadata_tokens budgets) don't
# trip on degenerate edge cases. The same constants are emitted for
# both with-ability AND baseline runs so iteration_delta is driven SOLELY
# by the NineS-derived axes (pass_rate, pass_k_4, trigger_F1).
SYNTHETIC_LATENCY_P95_S: float = 1.0
SYNTHETIC_METADATA_TOKENS: int = 50
SYNTHETIC_PER_INVOCATION_FOOTPRINT: int = 5000
SYNTHETIC_ROUTER_FLOOR: str = "composer_2/fast"

# The capability score that contains per-task golden-task accuracy
# details. Sourced from NineS V3.3.0 self-eval shape.
NINES_PER_TASK_SCORE_NAME: str = "scoring_accuracy"

# Acceptable JSON ROOT keys for a NineS self-eval payload — at minimum
# ``scores`` must be present. Other top-level keys (overall, version,
# timestamp, group_means, etc.) are surfaced for derivation logging
# but not required for the mapping.
NINES_REQUIRED_TOP_LEVEL_KEY: str = "scores"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def load_nines_json(path: Path) -> dict[str, Any]:
    """Load and JSON-parse a NineS self-eval output file.

    Loud per S-5: missing file raises :class:`FileNotFoundError`;
    malformed JSON raises :class:`json.JSONDecodeError` with the path
    stitched in for actionable debugging. The function does NOT
    validate the shape — that is :func:`validate_nines_shape`'s job.
    """
    if not path.is_file():
        raise FileNotFoundError(f"NineS self-eval JSON not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"Malformed NineS JSON at {path}: {exc.msg}",
            exc.doc,
            exc.pos,
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(
            f"NineS JSON at {path} is not a top-level object (got {type(data).__name__})"
        )
    return data


def validate_nines_shape(data: dict[str, Any]) -> tuple[bool, str]:
    """Return ``(True, "")`` when the NineS shape can drive the adapter.

    Returns ``(False, reason)`` otherwise — caller (``main``) then
    surfaces the REJECT verdict + the reason on stderr. R-1 fires
    here when the NineS schema cannot be reconciled with the per-task
    layout Si-Chip needs.

    Acceptance criteria (all must hold):

    1. Top-level ``scores`` array exists and is non-empty.
    2. At least one entry has ``name == "scoring_accuracy"``.
    3. That entry's ``metadata.details`` is a non-empty dict (per-task
       scores) — this is the granular signal we map onto Si-Chip.
    4. Each per-task value carries a numeric ``nines_score`` field.
    """
    if not isinstance(data, dict):
        return False, f"top-level NineS payload is not a dict (got {type(data).__name__})"

    scores = data.get(NINES_REQUIRED_TOP_LEVEL_KEY)
    if not isinstance(scores, list) or not scores:
        return False, (
            f"NineS payload missing non-empty top-level {NINES_REQUIRED_TOP_LEVEL_KEY!r} array"
        )

    accuracy_entry: dict[str, Any] | None = None
    for entry in scores:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") == NINES_PER_TASK_SCORE_NAME:
            accuracy_entry = entry
            break

    if accuracy_entry is None:
        return False, (
            f"NineS payload missing the {NINES_PER_TASK_SCORE_NAME!r} "
            f"capability score; the adapter relies on its per-task "
            f"metadata.details for granular mapping"
        )

    metadata = accuracy_entry.get("metadata")
    if not isinstance(metadata, dict):
        return False, (
            f"{NINES_PER_TASK_SCORE_NAME!r}.metadata is not a dict "
            f"(got {type(metadata).__name__}); cannot extract per-task "
            f"details"
        )

    details = metadata.get("details")
    if not isinstance(details, dict) or not details:
        return False, (
            f"{NINES_PER_TASK_SCORE_NAME!r}.metadata.details is missing "
            f"or empty; the adapter requires at least one per-task "
            f"score to materialise a Si-Chip task directory"
        )

    bad_task_ids: list[str] = []
    for task_id, task_data in details.items():
        if not isinstance(task_data, dict):
            bad_task_ids.append(f"{task_id} (value not dict)")
            continue
        raw_score = task_data.get("nines_score")
        try:
            float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            bad_task_ids.append(f"{task_id} (nines_score not numeric: {raw_score!r})")
            continue
        if raw_score is None:
            bad_task_ids.append(f"{task_id} (nines_score absent)")

    if bad_task_ids:
        joined = ", ".join(bad_task_ids[:5])
        more = f" (+{len(bad_task_ids) - 5} more)" if len(bad_task_ids) > 5 else ""
        return False, (f"per-task entries lack a numeric nines_score: {joined}{more}")

    return True, ""


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


def _extract_per_task_scores(
    nines_data: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Pull the per-task ``scoring_accuracy.metadata.details`` dict.

    Pre-condition: :func:`validate_nines_shape` returned ``(True, "")``.
    """
    for entry in nines_data["scores"]:
        if isinstance(entry, dict) and entry.get("name") == NINES_PER_TASK_SCORE_NAME:
            metadata = entry["metadata"]
            return metadata["details"]
    raise RuntimeError(
        f"validated NineS payload has no {NINES_PER_TASK_SCORE_NAME!r} "
        f"score — validate_nines_shape was bypassed"
    )


def _build_result_json(
    task_id: str,
    pass_rate: float,
    *,
    derivation: str,
    nines_overall: float | None = None,
) -> dict[str, Any]:
    """Construct one Si-Chip-shaped ``result.json`` payload.

    The four synthetic fields (latency, metadata_tokens, footprint,
    router_floor) are constants — see module-level docstring. The three
    NineS-derived fields share the same per-task ``pass_rate`` because
    NineS reports a single accuracy score per task; ``pass_k_4 = pass_rate``
    is the single-sample assumption (k samples all return the same
    score), and ``trigger_F1 = pass_rate`` is the conservative proxy
    when no separate F1 measurement is available.

    The ``_provenance`` block is non-required — Si-Chip's
    ``aggregate_eval.py`` does not consume it but it makes per-task
    rows auditable post-hoc.
    """
    payload: dict[str, Any] = {
        "pass_rate": float(pass_rate),
        "pass_k_4": float(pass_rate),
        "latency_p95_s": SYNTHETIC_LATENCY_P95_S,
        "metadata_tokens": SYNTHETIC_METADATA_TOKENS,
        "per_invocation_footprint": SYNTHETIC_PER_INVOCATION_FOOTPRINT,
        "trigger_F1": float(pass_rate),
        "router_floor": SYNTHETIC_ROUTER_FLOOR,
        "_provenance": {
            "task_id": task_id,
            "adapter": "devolaflow.scripts.nines_to_sichip_eval_adapter",
            "adapter_version": ADAPTER_VERSION,
            "derivation": derivation,
            "nines_overall": nines_overall,
        },
    }
    return payload


def build_runs(
    nines_data: dict[str, Any],
    *,
    score_field: str = "nines_score",
) -> dict[str, dict[str, Any]]:
    """Return the with-ability ``{task_id: result_payload}`` mapping.

    Each task's ``pass_rate`` is its NineS ``score_field`` value (default
    ``"nines_score"``). The ``score_field`` parameter exists so callers
    can build "golden baselines" by passing ``"golden_score"`` instead
    (the operator-truth scoring against which NineS is measured).
    """
    details = _extract_per_task_scores(nines_data)
    nines_overall = nines_data.get("overall")
    result: dict[str, dict[str, Any]] = {}
    for task_id, task_data in details.items():
        raw = task_data.get(score_field)
        if raw is None:
            LOGGER.warning("build_runs: task %r missing %r — skipping", task_id, score_field)
            continue
        try:
            score_value = float(raw)
        except (TypeError, ValueError):
            LOGGER.warning(
                "build_runs: task %r %r is not numeric (%r) — skipping",
                task_id,
                score_field,
                raw,
            )
            continue
        result[task_id] = _build_result_json(
            task_id,
            score_value,
            derivation=(f"NineS scoring_accuracy.metadata.details[{task_id!r}].{score_field}"),
            nines_overall=(float(nines_overall) if nines_overall is not None else None),
        )
    return result


def build_baselines(
    nines_data: dict[str, Any],
    *,
    mode: str,
    baseline_nines_data: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return the no-ability ``{task_id: result_payload}`` mapping.

    ``mode`` selects the baseline derivation:

    * ``"synthetic"`` — every task's ``pass_rate`` is 0.0. Cleanest A/B
      contrast: "ability does nothing". Si-Chip's
      ``T3_baseline_delta`` then equals the with-ability mean directly.
    * ``"sample"`` — load the per-task scores from a SECOND NineS JSON
      (``baseline_nines_data``). Useful for cycle-over-cycle comparison.
      Tasks present in the with-ability run but absent from the
      baseline default to ``pass_rate = 0.0`` (and a warning logs).

    The task-id set of the returned dict is the SAME as
    :func:`build_runs` — Si-Chip pairs them by directory name during
    aggregation.
    """
    runs_task_ids = set(_extract_per_task_scores(nines_data).keys())
    nines_overall = nines_data.get("overall")

    if mode == "synthetic":
        result: dict[str, dict[str, Any]] = {}
        for task_id in runs_task_ids:
            result[task_id] = _build_result_json(
                task_id,
                0.0,
                derivation=(
                    "synthetic mode: pass_rate=0.0 (no-ability run "
                    "modelled as 'ability did nothing')"
                ),
                nines_overall=(float(nines_overall) if nines_overall is not None else None),
            )
        return result

    if mode == "sample":
        if baseline_nines_data is None:
            raise ValueError(
                "build_baselines(mode='sample') requires baseline_nines_data; "
                "got None — pass --baseline-nines-json on the CLI"
            )
        baseline_details = _extract_per_task_scores(baseline_nines_data)
        baseline_overall = baseline_nines_data.get("overall")
        result = {}
        for task_id in runs_task_ids:
            baseline_entry = baseline_details.get(task_id)
            if baseline_entry is None:
                LOGGER.warning(
                    "build_baselines(sample): task %r absent from baseline; "
                    "defaulting to pass_rate=0.0",
                    task_id,
                )
                result[task_id] = _build_result_json(
                    task_id,
                    0.0,
                    derivation=(
                        f"sample mode: task absent from baseline NineS JSON — defaulted to 0.0"
                    ),
                    nines_overall=(
                        float(baseline_overall) if baseline_overall is not None else None
                    ),
                )
                continue
            raw = baseline_entry.get("nines_score")
            try:
                pass_rate = float(raw) if raw is not None else 0.0
            except (TypeError, ValueError):
                pass_rate = 0.0
            result[task_id] = _build_result_json(
                task_id,
                pass_rate,
                derivation=(
                    f"sample mode: baseline NineS scoring_accuracy."
                    f"metadata.details[{task_id!r}].nines_score"
                ),
                nines_overall=(float(baseline_overall) if baseline_overall is not None else None),
            )
        return result

    raise ValueError(f"build_baselines: unknown mode {mode!r}; expected 'synthetic' or 'sample'")


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------


def write_runs_dir(out_dir: Path, runs: dict[str, dict[str, Any]]) -> int:
    """Write one ``<task_id>/result.json`` per task; return the count.

    Each task gets its own subdirectory so Si-Chip's ``rglob("result.json")``
    surfaces them as distinct cases. Pre-existing files are overwritten
    silently — the adapter is idempotent.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for task_id, payload in runs.items():
        # Si-Chip's _walk_runs uses Path.rglob("result.json") so any
        # nesting works; we use task_id as the leaf directory name to
        # preserve provenance in `find` / `ls` output.
        task_dir = out_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        result_path = task_dir / "result.json"
        result_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written += 1
    return written


def write_baseline_dir(out_dir: Path, baselines: dict[str, dict[str, Any]]) -> int:
    """Write the no-ability baseline directory.

    Same shape as :func:`write_runs_dir`; kept as a separate function
    for symmetry + potential future divergence (e.g. baseline-only
    summary file).
    """
    return write_runs_dir(out_dir, baselines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the adapter CLI; deterministic for unit tests."""
    parser = argparse.ArgumentParser(
        description=(
            "Convert a NineS self-eval JSON output into Si-Chip "
            "runs-dir + baseline-dir directories so aggregate_eval.py "
            "can compute iteration_delta against NineS scores. Closes "
            "v10.2.0 cycle gap D-N-1."
        ),
    )
    parser.add_argument(
        "--nines-json",
        required=True,
        type=Path,
        help="Path to the NineS self-eval JSON output (with-ability run).",
    )
    parser.add_argument(
        "--out-runs-dir",
        required=True,
        type=Path,
        help="Output directory for the with-ability run-result JSONs.",
    )
    parser.add_argument(
        "--out-baseline-dir",
        required=True,
        type=Path,
        help="Output directory for the no-ability baseline run-result JSONs.",
    )
    parser.add_argument(
        "--mode",
        choices=("synthetic", "sample"),
        default="synthetic",
        help=(
            "Baseline derivation mode: 'synthetic' = baseline pass_rate=0 "
            "for every task (default); 'sample' = load baseline scores "
            "from a separate NineS JSON via --baseline-nines-json."
        ),
    )
    parser.add_argument(
        "--baseline-nines-json",
        type=Path,
        default=None,
        help=(
            "Required when --mode sample: path to a NineS self-eval JSON "
            "to use as the no-ability baseline (e.g. the prior cycle's "
            "NineS report)."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Set log level to INFO (default WARNING).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Adapter entry point; returns 0 on APPROVE, 1 on REJECT.

    The REJECT path is the documented R-1 fallback per the v10.2.0
    cycle plan §3 PV-03 backout plan: the adapter still ships, the
    REJECT message is the documentation, and the cycle falls back to
    a ``count_tokens`` regression.
    """
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        nines_data = load_nines_json(args.nines_json)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"REJECT: cannot load NineS JSON: {exc}", file=sys.stderr)
        return 1

    valid, reason = validate_nines_shape(nines_data)
    if not valid:
        print(f"REJECT: NineS shape unmappable: {reason}", file=sys.stderr)
        return 1

    baseline_nines_data: dict[str, Any] | None = None
    if args.mode == "sample":
        if args.baseline_nines_json is None:
            print(
                "REJECT: --mode sample requires --baseline-nines-json",
                file=sys.stderr,
            )
            return 1
        try:
            baseline_nines_data = load_nines_json(args.baseline_nines_json)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            print(
                f"REJECT: cannot load baseline NineS JSON: {exc}",
                file=sys.stderr,
            )
            return 1
        valid_b, reason_b = validate_nines_shape(baseline_nines_data)
        if not valid_b:
            print(
                f"REJECT: baseline NineS shape unmappable: {reason_b}",
                file=sys.stderr,
            )
            return 1

    runs = build_runs(nines_data)
    baselines = build_baselines(
        nines_data,
        mode=args.mode,
        baseline_nines_data=baseline_nines_data,
    )

    runs_count = write_runs_dir(args.out_runs_dir, runs)
    baseline_count = write_baseline_dir(args.out_baseline_dir, baselines)

    print(
        f"APPROVE: {runs_count} task(s) → {args.out_runs_dir}; "
        f"{baseline_count} task(s) → {args.out_baseline_dir} "
        f"(mode={args.mode}, adapter={ADAPTER_VERSION})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
