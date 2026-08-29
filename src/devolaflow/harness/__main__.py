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
from devolaflow.harness.calibration import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RAW_OUTPUT_DIR,
    DEFAULT_REPLICATES,
    DEFAULT_TOTAL_TIMEOUT_SECONDS,
    CalibrationError,
    CalibrationRunner,
    run_calibration,
)
from devolaflow.harness.cli_probe import (
    ARM_CHOICES,
    DEFAULT_TIMEOUT_SECONDS,
    PROBE_EXIT_CODES,
    SUPPORTED_CHANNELS,
    TASK_CLASSES,
    ProbeError,
    build_probe_spec,
    load_channel_configs,
    plan_probe_matrix,
    run_cli_probe,
)
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
from devolaflow.harness.telemetry import (
    TelemetryGateError,
    append_consolidation_metrics,
    append_gate_telemetry,
    append_metric_observation,
    check_gate_telemetry,
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
    evaluate.add_argument("--run-id")
    evaluate.add_argument("--salt")
    evaluate.add_argument("--generated-at")
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
    cli_probe = subcommands.add_parser(
        "probe-cli",
        aliases=["cli-probe"],
        help="run one bounded local Claude/Codex/Kimi CLI probe",
    )
    cli_probe.add_argument("--channel", choices=SUPPORTED_CHANNELS, required=True)
    cli_probe.add_argument("--task-class", choices=TASK_CLASSES, required=True)
    cli_probe.add_argument("--arm", choices=sorted(ARM_CHOICES), required=True)
    cli_probe.add_argument("--seed", required=True)
    cli_probe.add_argument("--replicate", type=int, default=1)
    cli_probe.add_argument("--prompt", required=True)
    cli_probe.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    cli_probe.add_argument("--salt")
    cli_probe.add_argument("--generated-at")
    cli_probe.add_argument("--repo-root", type=Path, default=Path("."))
    cli_probe.add_argument("--output", type=Path)
    cli_probe.add_argument("--command-config", type=Path)
    calibration = subcommands.add_parser(
        "calibration",
        aliases=["calibrate"],
        help="run the real serial CLI calibration matrix and write ROI reports",
    )
    calibration.add_argument("--seed", required=True)
    calibration.add_argument("--salt", required=True)
    calibration.add_argument("--replicates", type=int, default=DEFAULT_REPLICATES)
    calibration.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    calibration.add_argument("--total-timeout", type=float, default=DEFAULT_TOTAL_TIMEOUT_SECONDS)
    calibration.add_argument("--channels", nargs="+", choices=SUPPORTED_CHANNELS)
    calibration.add_argument(
        "--arms",
        nargs=2,
        default=("skill-off", "skill-on"),
        choices=("skill-off", "skill-on"),
    )
    calibration.add_argument(
        "--task-classes",
        "--classes",
        dest="task_classes",
        nargs="+",
        choices=TASK_CLASSES,
    )
    calibration.add_argument("--prompt-prefix", default="")
    calibration.add_argument("--repo-root", type=Path, default=Path("."))
    calibration.add_argument("--output-dir", type=Path, default=Path(DEFAULT_OUTPUT_DIR))
    calibration.add_argument("--raw-output-dir", type=Path, default=Path(DEFAULT_RAW_OUTPUT_DIR))
    calibration.add_argument("--command-config", type=Path)
    calibration.add_argument("--generated-at")
    calibration.add_argument("--dry-run", action="store_true")
    plan = subcommands.add_parser(
        "probe-plan",
        help="dry-run an ordered 4×3×2×N CLI probe matrix",
    )
    plan.add_argument("--replicates", type=int, required=True)
    plan.add_argument("--seed", required=True)
    plan.add_argument(
        "--arms",
        nargs=2,
        default=("skill-off", "skill-on"),
        choices=sorted(ARM_CHOICES),
    )
    plan.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    plan.add_argument("--prompt", default="")
    plan.add_argument("--output", type=Path)
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
    telemetry = subcommands.add_parser("telemetry", help="append or check SI-10 gate evidence")
    telemetry_commands = telemetry.add_subparsers(dest="telemetry_command", required=True)
    append = telemetry_commands.add_parser("append", help="append one SI-10 gate result")
    append.add_argument("--ledger", type=Path, required=True)
    append.add_argument("--pv", required=True)
    append.add_argument("--gate", required=True)
    append.add_argument("--status", choices=("PASS", "FAIL"), required=True)
    append.add_argument("--metadata", type=Path)
    append_metrics = telemetry_commands.add_parser(
        "append-metrics",
        help="append one v18 consolidation measurement envelope",
    )
    append_metrics.add_argument("--ledger", type=Path, required=True)
    append_metrics.add_argument("--agents-md-tokens", type=int)
    append_metrics.add_argument("--suite-wall-seconds", type=float)
    append_metrics.add_argument("--cjk-violations", type=int)
    append_metrics.add_argument("--ghost-loc", type=int)
    append_metrics.add_argument("--timestamp")
    append_metrics.add_argument("--metadata", type=Path)
    append_observation = telemetry_commands.add_parser(
        "append-observation",
        help="append one validated structured metric observation",
    )
    append_observation.add_argument("--ledger", type=Path, required=True)
    append_observation.add_argument("--observation", type=Path, required=True)
    append_observation.add_argument("--metadata", type=Path)
    check = telemetry_commands.add_parser("check", help="check complete SI-10 gate evidence")
    check.add_argument("--ledger", type=Path, required=True)
    check.add_argument("--pv", required=True)
    check.add_argument(
        "--historical",
        action="store_true",
        help="report INSUFFICIENT rather than fail when historical evidence is absent",
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


def _load_optional_metadata(path: Path | None) -> Mapping[str, object] | None:
    if path is None:
        return None
    payload = _load_json(path, label="run metadata")
    direct = payload.get("metadata")
    if isinstance(direct, Mapping):
        return direct
    summary = payload.get("harness_summary")
    if isinstance(summary, Mapping) and isinstance(summary.get("metadata"), Mapping):
        return summary["metadata"]
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


def _run_cli_probe_command(args: argparse.Namespace) -> int:
    spec = build_probe_spec(
        channel=args.channel,
        task_class=args.task_class,
        arm=args.arm,
        seed=args.seed,
        replicate=args.replicate,
        prompt=args.prompt,
        timeout_seconds=args.timeout,
        output_path=args.output,
        salt=args.salt,
        generated_at=args.generated_at,
    )
    result = run_cli_probe(
        spec,
        repo_root=args.repo_root,
        commands=load_channel_configs(args.command_config),
    )
    print(f"harness probe-cli: {result['status']}")
    return PROBE_EXIT_CODES[result["status"]]


def _run_probe_plan_command(args: argparse.Namespace) -> int:
    specs = plan_probe_matrix(
        args.replicates,
        seed=args.seed,
        arms=args.arms,
        prompt=args.prompt,
        timeout_seconds=args.timeout,
    )
    rendered = (
        json.dumps(
            {
                "schema_version": 1,
                "status": "PLAN",
                "count": len(specs),
                "replicates": args.replicates,
                "specs": [spec.as_dict() for spec in specs],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    _write_output(rendered, args.output)
    return 0


def _run_calibration_command(args: argparse.Namespace) -> int:
    commands = load_channel_configs(args.command_config)
    runner = CalibrationRunner(repo_root=args.repo_root, commands=commands)
    channels = args.channels or SUPPORTED_CHANNELS
    task_classes = args.task_classes or TASK_CLASSES
    if args.dry_run:
        specs = runner.plan(
            seed=args.seed,
            salt=args.salt,
            replicates=args.replicates,
            timeout_seconds=args.timeout,
            channels=channels,
            arms=args.arms,
            task_classes=task_classes,
            prompt_prefix=args.prompt_prefix,
            generated_at=args.generated_at,
            raw_output_dir=args.raw_output_dir,
        )
        rendered = (
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "PLAN",
                    "seed": args.seed,
                    "salt": args.salt,
                    "count": len(specs),
                    "task_classes": list(task_classes),
                    "channels": list(channels),
                    "arms": list(args.arms),
                    "replicates": args.replicates,
                    "timeout_seconds": args.timeout,
                    "order": ["task_class", "channel", "arm", "replicate"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        _write_output(rendered, args.output_dir / "v21.1.0_calibration_plan.json")
        return 0

    def progress(index: int, total: int) -> None:
        if index == 1 or index == total or index % 10 == 0:
            print(f"harness calibration: {index}/{total}", file=sys.stderr)

    report = run_calibration(
        repo_root=args.repo_root,
        commands=commands,
        seed=args.seed,
        salt=args.salt,
        replicates=args.replicates,
        timeout_seconds=args.timeout,
        total_timeout_seconds=args.total_timeout,
        channels=channels,
        arms=args.arms,
        task_classes=task_classes,
        prompt_prefix=args.prompt_prefix,
        generated_at=args.generated_at,
        output_dir=args.output_dir,
        raw_output_dir=args.raw_output_dir,
        progress=progress,
    )
    calibration_runner = CalibrationRunner(repo_root=args.repo_root, commands=commands)
    markdown_path, json_path = calibration_runner.write_report(
        report,
        output_dir=args.output_dir,
    )
    counts = report["summary"]["counts"]
    print(
        "harness calibration: "
        f"planned={counts['planned']} observed={counts['observed']} "
        f"completed={counts['completed']} insufficient={counts['insufficient']}"
    )
    if counts["fail"]:
        return 1
    if counts["insufficient"] or counts["unrecorded"]:
        return 2
    print(f"harness calibration reports: {markdown_path}, {json_path}")
    return 0


def _run_telemetry_command(args: argparse.Namespace) -> int:
    if args.telemetry_command == "append":
        destination = append_gate_telemetry(
            args.ledger,
            args.pv,
            args.gate,
            args.status,
            metadata=_load_optional_metadata(args.metadata),
        )
        print(f"harness telemetry: appended {args.pv}/{args.gate} {args.status} to {destination}")
        return 0
    if args.telemetry_command == "append-metrics":
        destination = append_consolidation_metrics(
            args.ledger,
            {
                "agents_md_tokens": args.agents_md_tokens,
                "suite_wall_seconds": args.suite_wall_seconds,
                "cjk_violations": args.cjk_violations,
                "ghost_loc": args.ghost_loc,
            },
            timestamp=args.timestamp,
            metadata=_load_optional_metadata(args.metadata),
        )
        print(f"harness telemetry: appended consolidation metrics to {destination}")
        return 0
    if args.telemetry_command == "append-observation":
        raw_observation = _load_yaml(args.observation, label="metric observation")
        if not isinstance(raw_observation, Mapping):
            raise ValueError("metric observation must be a mapping")
        destination = append_metric_observation(
            args.ledger,
            raw_observation,
            metadata=_load_optional_metadata(args.metadata),
        )
        print(f"harness telemetry: appended metric observation to {destination}")
        return 0

    result = check_gate_telemetry(args.ledger, args.pv, historical=args.historical)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 2 if result["verdict"] == "INSUFFICIENT" else 0


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

        if args.command in {"probe-cli", "cli-probe"}:
            return _run_cli_probe_command(args)

        if args.command == "probe-plan":
            return _run_probe_plan_command(args)

        if args.command in {"calibration", "calibrate"}:
            return _run_calibration_command(args)

        if args.command == "telemetry":
            return _run_telemetry_command(args)

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
            run_id=args.run_id,
            salt=args.salt,
            generated_at=args.generated_at,
        )
        rendered = render_evaluation(result)
        _write_output(rendered, args.output)
    except TelemetryGateError as exc:
        print(f"harness telemetry: {exc}", file=sys.stderr)
        return 1
    except (
        AggregationError,
        CalibrationError,
        EvaluationError,
        OSError,
        ProbeError,
        ValueError,
    ) as exc:
        print(f"harness {args.command}: {exc}", file=sys.stderr)
        return 2

    return {"READY": 0, "NOT_READY": 1, "INSUFFICIENT": 2}[result["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
