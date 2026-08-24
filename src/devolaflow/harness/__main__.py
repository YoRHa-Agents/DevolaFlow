"""Command-line entry point for the built-in DevolaFlow harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from devolaflow.harness.aggregator import AggregationError, aggregate_ledger
from devolaflow.harness.evaluator import (
    DEFAULT_THRESHOLD,
    EvaluationError,
    evaluate_harness,
    load_signals,
    render_evaluation,
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
    return parser


def _write_output(rendered: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(rendered)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Run the harness CLI with READY/NOT_READY/INSUFFICIENT exit semantics."""

    args = _parser().parse_args(argv)
    try:
        if args.command == "aggregate":
            summary = aggregate_ledger(args.ledger)
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
    except (AggregationError, EvaluationError, OSError) as exc:
        print(f"harness {args.command}: {exc}", file=sys.stderr)
        return 2

    return {"READY": 0, "NOT_READY": 1, "INSUFFICIENT": 2}[result["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
