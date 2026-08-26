"""Command-line entry point for the built-in DevolaFlow harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml

from devolaflow.harness.aggregator import AggregationError, aggregate_ledger
from devolaflow.harness.evaluator import (
    DEFAULT_CROSS_VALIDATION_DELTA,
    DEFAULT_THRESHOLD,
    EvaluationError,
    compare_historical_companion,
    evaluate_harness,
    load_signals,
    render_evaluation,
)
from devolaflow.harness.gap import (
    build_gap_report,
    compare_gap_reports,
    load_gap_report,
    render_capability_review,
)
from devolaflow.harness.probe import (
    load_probe_model_table,
    run_probe,
    sanitize_model_for_filename,
)
from devolaflow.harness.proposal import (
    ProposalError,
    apply_approved_proposal,
    build_proposal,
    write_proposal,
)
from devolaflow.llm_client import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT_S,
    PROVIDER_CHOICES,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m devolaflow.harness",
        description="Aggregate harness telemetry and run deterministic W-3 evaluation.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    aggregate = subcommands.add_parser("aggregate", help="aggregate one harness ledger")
    aggregate.add_argument("--ledger", type=Path, required=True)
    aggregate.add_argument("--output", type=Path)
    evaluate = subcommands.add_parser("evaluate", help="evaluate one harness ledger")
    evaluate.add_argument("--ledger", type=Path, required=True)
    evaluate.add_argument("--signals", type=Path)
    evaluate.add_argument("--repo-root", "--repo", dest="repo_root", type=Path, default=Path("."))
    evaluate.add_argument("--base-ref", "--base", dest="base_ref", default="HEAD~1")
    evaluate.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    evaluate.add_argument("--output", type=Path)
    gap = subcommands.add_parser(
        "gap",
        help="inventory harness coverage gaps across built-in and custom axes",
    )
    gap.add_argument("--ledger", type=Path, required=True)
    gap.add_argument("--repo", "--repo-root", dest="repo_root", type=Path, default=Path("."))
    gap.add_argument("--axes-config", type=Path)
    gap.add_argument("--output", type=Path)
    # Capability-review comparison mode (design §4): both flags together or
    # neither — enforced after parse via parser.error in main().
    gap.add_argument("--compare", type=Path)
    gap.add_argument("--review-output", type=Path)
    cross_validate = subcommands.add_parser(
        "cross-validate",
        help="compare current evaluation with one historical W-3 companion",
    )
    cross_validate.add_argument(
        "--evaluation",
        "--current",
        dest="current_evaluation",
        type=Path,
        required=True,
    )
    cross_validate.add_argument(
        "--companion",
        "--historical",
        dest="historical_companion",
        type=Path,
        required=True,
    )
    cross_validate.add_argument(
        "--max-abs-delta",
        type=float,
        default=DEFAULT_CROSS_VALIDATION_DELTA,
    )
    cross_validate.add_argument("--output", type=Path, required=True)
    probe = subcommands.add_parser(
        "probe",
        help="run one bounded model-compliance probe "
        "(omit --provider/--model to sweep meta.probe_models)",
    )
    # v17.0.0 R5 (D-R5-2): both optional. Given together → single-model
    # probe, byte-identical to the pre-R5 contract. Both omitted → sweep
    # the context_profiles.yaml#meta.probe_models table, one profile per
    # configured (provider, model). Mixed → explicit error (S-5).
    probe.add_argument("--provider", choices=sorted(PROVIDER_CHOICES))
    probe.add_argument("--model")
    probe.add_argument("--cycle", required=True)
    probe.add_argument("--fixtures", type=Path, default=Path("tests/fixtures/harness"))
    probe.add_argument("--fold-mode", choices=("full", "folded"), default="folded")
    probe.add_argument("--baseline-profile", type=Path)
    probe.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    probe.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    probe.add_argument("--output", type=Path)
    propose = subcommands.add_parser("propose", help="build one immutable tuning proposal")
    propose.add_argument("--evaluation", type=Path, required=True)
    propose.add_argument("--targets", type=Path, required=True)
    propose.add_argument("--cycle", required=True)
    propose.add_argument("--output", type=Path, required=True)
    apply = subcommands.add_parser("apply", help="apply one explicitly approved proposal")
    apply.add_argument("--proposal", type=Path, required=True)
    apply.add_argument("--approval", type=Path, required=True)
    apply.add_argument("--repo", dest="repo_root", type=Path, default=Path("."))
    apply.add_argument("--model", dest="model_profile", type=Path)
    apply.add_argument(
        "--config",
        type=Path,
        default=Path("workflow-system/agent/context_profiles.yaml"),
    )
    apply.add_argument(
        "--ledger",
        type=Path,
        default=Path(".local/telemetry/harness.jsonl"),
    )
    return parser


def _write_output(rendered: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(rendered)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")


def _load_yaml(path: Path, *, label: str) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProposalError(f"cannot read {label} {path}: {exc}") from exc


def _load_json(path: Path, *, label: str) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvaluationError(f"cannot read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"{path}: invalid {label} JSON: {exc.msg}") from exc
    if not isinstance(payload, Mapping):
        raise EvaluationError(f"{label} must be a JSON object")
    return payload


def _input_document(path: Path) -> dict[str, str]:
    return {
        "path": path.as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


_PROBE_EXIT_CODES = {"PASS": 0, "FAIL": 1, "PARTIAL": 1, "SKIPPED_NO_KEY": 2}


def _sweep_output_path(output: Path | None, provider: str, model: str) -> Path | None:
    """Derive one per-model output path from the single ``--output`` arg.

    ``profiles/probe.yaml`` + (``mock``, ``m/1``) → ``profiles/probe__mock__m_1.yaml``.
    ``None`` stays ``None`` — :func:`run_probe` then uses its own per-model
    default under ``.local/telemetry/model_profiles/``.
    """

    if output is None:
        return None
    safe_model = sanitize_model_for_filename(model)
    return output.with_name(f"{output.stem}__{provider}__{safe_model}{output.suffix}")


def _run_probe_command(args: argparse.Namespace) -> int:
    """Run the probe subcommand: single-model or config-table sweep.

    v17.0.0 R5 (D-R5-2): with ``--provider``/``--model`` the behaviour is
    byte-identical to the pre-R5 single-model contract. With both omitted,
    every configured ``meta.probe_models`` (provider, model) pair is probed
    and one profile artifact is written per model; the exit code is the
    worst per-model verdict under the single-model mapping. Mixed flag
    usage and an unconfigured table raise explicit errors per S-5.
    """

    if (args.provider is None) != (args.model is None):
        raise ValueError(
            "pass BOTH --provider and --model for a single-model probe, "
            "or NEITHER to sweep the meta.probe_models table"
        )
    if args.model is not None:
        profile = run_probe(
            args.fixtures,
            provider=args.provider,
            model=args.model,
            cycle=args.cycle,
            fold_mode=args.fold_mode,
            baseline_profile=args.baseline_profile,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            output=args.output,
        )
        print(f"harness probe: {profile['status']}")
        return _PROBE_EXIT_CODES[profile["status"]]

    table = load_probe_model_table()
    if not table:
        raise ValueError(
            "--model omitted but meta.probe_models is not configured in "
            "workflow-system/agent/context_profiles.yaml; declare the "
            "table or pass --provider/--model explicitly"
        )
    exit_code = 0
    for entry in table:
        profile = run_probe(
            args.fixtures,
            provider=entry.provider,
            model=entry.model,
            cycle=args.cycle,
            fold_mode=args.fold_mode,
            baseline_profile=args.baseline_profile,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            output=_sweep_output_path(args.output, entry.provider, entry.model),
        )
        print(f"harness probe [{entry.provider}:{entry.model}]: {profile['status']}")
        exit_code = max(exit_code, _PROBE_EXIT_CODES[profile["status"]])
    return exit_code


def main(argv: list[str] | None = None) -> int:
    """Run the harness CLI with command-specific bounded exit semantics."""

    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "gap" and (args.compare is None) != (args.review_output is None):
        parser.error("--compare and --review-output must be given together")
    try:
        if args.command == "aggregate":
            summary = aggregate_ledger(args.ledger)
            if not summary["events"]:
                summary = {key: value for key, value in summary.items() if key != "events"}
            rendered = (
                json.dumps(
                    summary,
                    ensure_ascii=False,
                    indent=2,
                    separators=(",", ": "),
                )
                + "\n"
            )
            _write_output(rendered, args.output)
            return 0

        if args.command == "gap":
            report = build_gap_report(
                args.ledger,
                repo_root=args.repo_root,
                axes_config=args.axes_config,
            )
            _write_output(render_evaluation(report), args.output)
            if args.compare is not None:
                delta = compare_gap_reports(load_gap_report(args.compare), report)
                review = render_capability_review(
                    delta,
                    before_ref=args.compare.as_posix(),
                    after_ref=args.output.as_posix() if args.output else "<stdout>",
                )
                _write_output(review, args.review_output)
            # Exit reflects CURRENT gaps only; the comparison delta is
            # trend-only and never gates (design decision 5).
            summary = report["summary"]
            return 0 if summary["partial"] == 0 and summary["gap"] == 0 else 1

        if args.command == "cross-validate":
            current = _load_json(args.current_evaluation, label="current evaluation")
            companion = _load_json(args.historical_companion, label="historical companion")
            result = compare_historical_companion(
                current,
                companion,
                max_abs_delta=args.max_abs_delta,
            )
            result["input_documents"] = {
                "current_evaluation": _input_document(args.current_evaluation),
                "historical_companion": _input_document(args.historical_companion),
            }
            _write_output(render_evaluation(result), args.output)
            return 0 if result["verdict"] == "PASS" else 1

        if args.command == "probe":
            return _run_probe_command(args)

        if args.command == "propose":
            evaluation = _load_yaml(args.evaluation, label="evaluation")
            raw_targets = _load_yaml(args.targets, label="targets")
            if isinstance(raw_targets, Mapping):
                raw_targets = raw_targets.get("targets")
            if not isinstance(evaluation, Mapping):
                raise ProposalError("evaluation input must be a mapping")
            if isinstance(raw_targets, (str, bytes)) or not isinstance(raw_targets, Sequence):
                raise ProposalError("targets input must be a sequence or a mapping with targets")
            proposal = build_proposal(
                evaluation,
                cycle=args.cycle,
                targets=raw_targets,
            )
            destination = write_proposal(proposal, args.output)
            print(f"harness propose: PROPOSED {destination}")
            return 0

        if args.command == "apply":
            status = apply_approved_proposal(
                args.proposal,
                args.approval,
                repo_root=args.repo_root,
                config_path=args.config,
                ledger_path=args.ledger,
                model_profile=args.model_profile,
            )
            print(f"harness apply: {status}")
            return 1 if status == "CHANGE_REQUIRED" else 0

        injected = load_signals(args.signals) if args.signals is not None else None
        result = evaluate_harness(
            args.ledger,
            signals=injected,
            repo_root=args.repo_root,
            base_ref=args.base_ref,
            threshold=args.threshold,
        )
        rendered = render_evaluation(result)
        _write_output(rendered, args.output)
    except (AggregationError, EvaluationError, OSError, ValueError) as exc:
        print(f"harness {args.command}: {exc}", file=sys.stderr)
        return 2

    return {"READY": 0, "NOT_READY": 1, "INSUFFICIENT": 2}[result["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
