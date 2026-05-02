"""Writing-style benchmark runner.

Scores a corpus and emits a JSON baseline. The output shape is stable
across invocations for a fixed corpus + scorer, so ``git diff`` on
the baseline file is the primary change-detection surface.

Run examples:

  python -m benchmarks.writing_style.runner \\
      --corpus devolaflow \\
      --output benchmarks/writing_style/baselines/v10.1.0_pre.json

  python -m benchmarks.writing_style.runner --corpus both

The exit code is 0 on success, 1 on missing-corpus errors, 2 on
scoring-pipeline errors (e.g. weight-sum invariant violation).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from benchmarks.writing_style.corpus import (
    load_corpus,
    read_docs,
)
from devolaflow.writing_style import (
    StyleError,
    load_profile,
    score_corpus,
)

# The benchmark uses a single baseline scoring profile across all docs
# so the aggregate is comparable against the PV-01 probe baseline
# (69.958) and across cycles. Per-profile transform policy is still
# applied by the humanizer (Q-D) — profiles shape WHICH transforms
# run on a doc, not the scoring of the result.
DEFAULT_SCORING_PROFILE = "documentation_natural"


def run(corpus_name: str, output: Path | None) -> int:
    docs = load_corpus(corpus_name)
    read = read_docs(docs)

    scoring_profile = load_profile(DEFAULT_SCORING_PROFILE)

    items: list[tuple[str, str]] = []
    doc_profiles: dict[str, str] = {}
    skipped: list[str] = []
    for label, text, profile_name, present in read:
        if not present:
            skipped.append(label)
            continue
        items.append((label, text))
        doc_profiles[label] = profile_name

    if not items:
        print("no docs scored (corpus empty or entirely absent)", file=sys.stderr)
        return 1

    try:
        result = score_corpus(items, lambda _label: scoring_profile)
    except StyleError as e:
        print(f"error scoring corpus: {e}", file=sys.stderr)
        return 2

    per_doc: list[dict[str, Any]] = []
    for label, score in result.per_doc.items():
        per_doc.append(
            {
                "label": label,
                "doc_profile": doc_profiles.get(label, DEFAULT_SCORING_PROFILE),
                "scoring_profile": DEFAULT_SCORING_PROFILE,
                "naturalness": score.composite,
                "sub_scores": dict(score.per_feature_subscores),
                "features": asdict(score.features),
            }
        )

    payload = {
        "corpus": corpus_name,
        "doc_count": len(per_doc),
        "word_total": result.word_total,
        "aggregate_naturalness": result.aggregate_naturalness,
        "skipped": skipped,
        "per_doc": per_doc,
    }
    aggregate = result.aggregate_naturalness

    if output is None:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            f"wrote {len(per_doc)} scored docs (agg {aggregate}) to {output}",
            file=sys.stderr,
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--corpus",
        choices=("devolaflow", "human-clean", "both"),
        default="devolaflow",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="write JSON baseline to this path (default: stdout)",
    )
    args = p.parse_args(argv)
    return run(args.corpus, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
